import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from alarms import service
from alarms.realtime import hub
from app.models import Alarm, AuditLog
from app.models.enums import AlarmLevel, AlarmState
from ingest.service import Outcome, handle_message

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
DEV = "vessel-demo-01"


def event(db, level, seq, alarm_id="A-1", dev=DEV, boot="b1", acked_by=None, rx=T0):
    payload = {"device_id": dev, "boot_id": boot, "seq": seq, "type": "ALARM_STATE",
               "alarm_id": alarm_id, "level": level, "class": "HIGH_ROLL", "t_sim_s": float(seq),
               "acked_by": acked_by}
    r = handle_message(db, f"svmg/{dev}/event", json.dumps(payload).encode(), rx_time=rx)
    assert r.outcome == Outcome.STORED
    return db.scalar(select(Alarm).where(Alarm.device_id == dev, Alarm.alarm_id == alarm_id,
                                         Alarm.boot_id == boot))


def audits(db, action):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)))


def test_lifecycle_open_update_clear(db):
    a = event(db, "CAUTION", 1)
    assert a.state == AlarmState.ACTIVE and a.level.value == "CAUTION" and a.source_mode.value == "SIMULATION"
    a = event(db, "CRITICAL", 2)
    assert a.level.value == "CRITICAL" and a.max_level.value == "CRITICAL"
    a = event(db, "NORMAL", 3)
    assert a.state == AlarmState.CLEARED and a.cleared_at is not None


def test_normal_event_without_open_alarm_creates_nothing(db):
    assert event(db, "NORMAL", 1) is None


def test_stale_event_ignored(db):
    event(db, "WARNING", 5)
    a = event(db, "CAUTION", 3)  # seq cu den muon -> khong ha muc
    assert a.level.value == "WARNING" and a.last_seq == 5


def test_cleared_alarm_not_reopened(db):
    event(db, "CAUTION", 1)
    event(db, "NORMAL", 2)
    a = event(db, "WARNING", 3)  # den muon sau khi da giai toa
    assert a.state == AlarmState.CLEARED


def test_same_alarm_id_on_different_device_or_boot_are_separate(db):
    event(db, "CAUTION", 1, dev="vessel-1")
    event(db, "CAUTION", 1, dev="vessel-2")
    event(db, "CAUTION", 1, dev="vessel-1", boot="b2")
    assert len(list(db.scalars(select(Alarm)))) == 3


def test_ack_api_and_mtta(db, client):
    a = event(db, "WARNING", 1, rx=T0)
    alarm, already = service.ack_alarm(db, a.id, "alice", now=T0 + timedelta(seconds=30))
    assert not already and alarm.state == AlarmState.ACKED
    stats = client.get("/api/v1/alarms/stats").json()
    assert stats["mtta_s"] == 30 and stats["acked"] == 1 and stats["total"] == 1
    assert audits(db, "ALARM_ACK")[0].actor == "alice"


def test_ack_endpoint_idempotent_404_409(db, client):
    a = event(db, "WARNING", 1)
    r = client.post(f"/api/v1/alarms/{a.id}/ack")
    assert r.status_code == 200 and r.json()["already_acked"] is False
    assert r.json()["alarm"]["source_mode"] == "SIMULATION"
    assert client.post(f"/api/v1/alarms/{a.id}/ack").json()["already_acked"] is True
    assert client.post("/api/v1/alarms/9999/ack").status_code == 404
    event(db, "NORMAL", 2)
    b = event(db, "CAUTION", 3, alarm_id="A-2")  # seq la bo dem cua ca thiet bi, khong lap
    event(db, "NORMAL", 4, alarm_id="A-2")
    assert client.post(f"/api/v1/alarms/{b.id}/ack").status_code == 409


def test_higher_level_after_ack_reactivates(db):
    a = event(db, "CAUTION", 1)
    service.ack_alarm(db, a.id, "alice", now=T0 + timedelta(seconds=10))
    a = event(db, "CRITICAL", 2)
    assert a.state == AlarmState.ACTIVE and a.escalated is True
    assert a.acked_at is not None  # giu moc ACK dau tien cho MTTA
    assert audits(db, "ALARM_REACTIVATED")


def test_lower_level_after_ack_stays_acked(db):
    a = event(db, "WARNING", 1)
    service.ack_alarm(db, a.id, "alice")
    a = event(db, "CAUTION", 2)
    assert a.state == AlarmState.ACKED and a.escalated is False


def test_device_side_ack_recorded(db):
    a = event(db, "WARNING", 1, acked_by="button")
    assert a.state == AlarmState.ACKED and a.acked_by == "button"


def test_escalate_overdue_only_unacked(db):
    a1 = event(db, "WARNING", 1, alarm_id="A-1", rx=T0)
    a2 = event(db, "WARNING", 2, alarm_id="A-2", rx=T0)
    service.ack_alarm(db, a2.id, "alice", now=T0 + timedelta(seconds=5))
    assert service.escalate_overdue(db, now=T0 + timedelta(seconds=30), after_s=60) == []
    done = service.escalate_overdue(db, now=T0 + timedelta(seconds=61), after_s=60)
    assert [x.id for x in done] == [a1.id]
    assert service.escalate_overdue(db, now=T0 + timedelta(seconds=120), after_s=60) == []  # khong lap
    assert audits(db, "ALARM_ESCALATED")[0].actor == "system"


def test_mute_follows_firmware_rule_warning_and_not_acked(db):
    """Dong bo svmg_alarm_mute: chi WARNING va chua ACK; CRITICAL luon bi chan; CAUTION/NORMAL thiet bi tu choi."""
    from conftest import firmware_mute_state
    firmware_mute_state(db, level="CAUTION")
    with pytest.raises(service.MuteNotAllowed, match="WARNING"):
        service.ensure_mute_allowed(db, DEV)                          # firmware tra FORBIDDEN_STATE -> chan truoc
    a = firmware_mute_state(db, level="WARNING", alarm_id="A-2")
    service.ensure_mute_allowed(db, DEV)                              # WARNING chua ACK -> cho phep
    service.ack_alarm(db, a.id, "alice")
    with pytest.raises(service.MuteNotAllowed):                       # da ACK -> thiet bi khong cho mute
        service.ensure_mute_allowed(db, DEV)
    firmware_mute_state(db, level="CRITICAL", alarm_id="A-3")
    with pytest.raises(service.MuteNotAllowed, match="CRITICAL"):
        service.ensure_mute_allowed(db, DEV)


def test_previous_boot_alarm_is_history_and_does_not_block_mute(db, client):
    """A-0002 cua boot cu (CRITICAL, ACKED, khong bao gio duoc dong) khong duoc chan mute cua boot moi; lich su giu nguyen."""
    from conftest import firmware_mute_state
    from app.models import Device
    db.add(Device(device_id=DEV, boot_id="newboot"))
    db.commit()
    old = firmware_mute_state(db, boot="oldboot", level="CRITICAL", alarm_state="ACKED", alarm_id="A-0002")
    with pytest.raises(service.MuteNotAllowed):                       # boot moi chua co WARNING -> van khong mute duoc
        service.ensure_mute_allowed(db, DEV)
    firmware_mute_state(db, boot="newboot", level="WARNING", alarm_id="A-0001")
    service.ensure_mute_allowed(db, DEV)                              # canh bao boot cu khong con chan
    db.refresh(old)
    assert old.state == AlarmState.ACKED and old.level == AlarmLevel.CRITICAL   # khong xoa, khong tu dong giai toa
    rows = {a["alarm_id"]: a for a in client.get("/api/v1/alarms").json()}
    assert rows["A-0002"]["boot_current"] is False and rows["A-0001"]["boot_current"] is True
    s = client.get("/api/v1/alarms/stats").json()
    assert s["open_previous_boot"] == 1 and s["active"] == 1


def test_critical_on_current_boot_still_blocks_even_with_old_boot_history(db):
    from conftest import firmware_mute_state
    from app.models import Device
    db.add(Device(device_id=DEV, boot_id="newboot"))
    db.commit()
    firmware_mute_state(db, boot="newboot", level="CRITICAL")
    with pytest.raises(service.MuteNotAllowed, match="CRITICAL"):
        service.ensure_mute_allowed(db, DEV)


def test_stats_empty_and_filters(db, client):
    s = client.get("/api/v1/alarms/stats").json()
    assert s["total"] == 0 and s["mtta_s"] is None and s["escalation_rate"] is None
    event(db, "CRITICAL", 1, dev="vessel-1")
    event(db, "CAUTION", 1, dev="vessel-2")
    assert client.get("/api/v1/alarms/stats?device_id=vessel-1").json()["by_max_level"] == {"CRITICAL": 1}
    assert len(client.get("/api/v1/alarms?state=ACTIVE").json()) == 2


def test_websocket_receives_open_and_ack(db, client, auth):
    token = auth("op01")["Authorization"].split()[1]
    with client.websocket_connect(f"/ws/alarms?token={token}") as ws:
        for _ in range(100):  # cho server dang ky client
            if hub.clients:
                break
            time.sleep(0.01)
        a = event(db, "WARNING", 1)  # goi tu luong test, khac luong event loop
        msg = ws.receive_json()
        assert msg["type"] == "alarm" and msg["action"] == "opened"
        assert msg["alarm"]["source_mode"] == "SIMULATION"
        client.post(f"/api/v1/alarms/{a.id}/ack")
        assert ws.receive_json()["action"] == "acked"
