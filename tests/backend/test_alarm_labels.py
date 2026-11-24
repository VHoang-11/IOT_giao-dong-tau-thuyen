import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from conftest import NOAUTH
from sqlalchemy import select

from alarms import service
from alarms.realtime import hub
from app.models import Alarm, AuditLog
from app.models.enums import AlarmState
from ingest.service import handle_message

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
DEV = "vessel-demo-01"
_seq = {"n": 0}


def make_alarm(db, level="WARNING", alarm_id=None, dev=DEV, clear=False):
    """Tao canh bao that qua duong ingest (khong ghi thang vao DB)."""
    _seq["n"] += 1
    alarm_id = alarm_id or f"A-{_seq['n']}"
    for lv in ([level, "NORMAL"] if clear else [level]):
        _seq["n"] += 1
        p = {"device_id": dev, "boot_id": "b1", "seq": _seq["n"], "type": "ALARM_STATE", "alarm_id": alarm_id,
             "level": lv, "class": "HIGH_ROLL", "t_sim_s": 1.0}
        handle_message(db, f"svmg/{dev}/event", json.dumps(p).encode(), rx_time=T0)
    return db.scalar(select(Alarm).where(Alarm.alarm_id == alarm_id, Alarm.device_id == dev))


def label(client, pk, value, headers=None):
    kw = {"headers": headers} if headers else {}
    return client.put(f"/api/v1/alarms/{pk}/label", json={"label": value}, **kw)


def audits(db, action):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)))


# ---------------- gan nhan + phan quyen ----------------

def test_supervisor_labels_alarm_and_it_is_recorded(client, db):
    a = make_alarm(db)
    r = label(client, a.id, "FALSE_ALARM")
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == "FALSE_ALARM" and body["labeled_by"] == "sup01" and body["labeled_at"]
    assert client.get(f"/api/v1/alarms/{a.id}").json()["label"] == "FALSE_ALARM"
    row = audits(db, "ALARM_LABEL")[0]
    assert row.actor == "sup01" and row.detail["from"] is None and row.detail["to"] == "FALSE_ALARM"


def test_operator_cannot_label_and_attempt_is_audited(client, db, auth):
    a = make_alarm(db)
    assert label(client, a.id, "TRUE_ALARM", auth("op01")).status_code == 403
    assert client.get(f"/api/v1/alarms/{a.id}").json()["label"] is None
    assert audits(db, "AUTH_DENIED")[0].actor == "op01"
    assert audits(db, "ALARM_LABEL") == []


def test_admin_can_label_and_anonymous_cannot(client, db, auth):
    a = make_alarm(db)
    assert label(client, a.id, "TRUE_ALARM", auth("admin01")).status_code == 200
    assert label(client, a.id, "FALSE_ALARM", NOAUTH).status_code == 401


@pytest.mark.parametrize("bad", ["false_alarm", "WRONG", "", None, 1, True])
def test_invalid_label_values_rejected(client, db, bad):
    a = make_alarm(db)
    assert label(client, a.id, bad).status_code == 422
    assert client.put(f"/api/v1/alarms/{a.id}/label", json={}).status_code == 422
    assert client.put(f"/api/v1/alarms/{a.id}/label", json={"label": "UNCLEAR", "x": 1}).status_code == 422
    assert client.get(f"/api/v1/alarms/{a.id}").json()["label"] is None


def test_unknown_alarm_404(client):
    assert label(client, 9999, "UNCLEAR").status_code == 404


def test_relabel_overwrites_and_audits_transition_same_label_is_noop(client, db):
    a = make_alarm(db)
    label(client, a.id, "FALSE_ALARM")
    assert label(client, a.id, "FALSE_ALARM").status_code == 200   # gan lai cung nhan
    assert len(audits(db, "ALARM_LABEL")) == 1                      # khong ghi audit thua
    r = label(client, a.id, "TRUE_ALARM")
    assert r.json()["label"] == "TRUE_ALARM"
    last = audits(db, "ALARM_LABEL")[-1]
    assert last.detail["from"] == "FALSE_ALARM" and last.detail["to"] == "TRUE_ALARM"


def test_can_label_active_acked_and_cleared_alarms(client, db):
    active = make_alarm(db)
    cleared = make_alarm(db, clear=True)
    acked = make_alarm(db)
    service.ack_alarm(db, acked.id, "alice")
    for a in (active, cleared, acked):
        assert label(client, a.id, "UNCLEAR").status_code == 200


# ---------------- AN TOAN: nhan khong dong vao vong doi canh bao ----------------

def test_labeling_never_changes_alarm_lifecycle(client, db):
    a = make_alarm(db, level="CRITICAL")
    before = (a.state, a.level, a.max_level, a.acked_at, a.acked_by, a.escalated, a.cleared_at)
    assert label(client, a.id, "FALSE_ALARM").status_code == 200
    db.refresh(a)
    assert (a.state, a.level, a.max_level, a.acked_at, a.acked_by, a.escalated, a.cleared_at) == before
    assert a.state == AlarmState.ACTIVE and a.acked_at is None  # gan 'SAI' KHONG tu ACK / tat canh bao


def test_false_alarm_label_does_not_block_escalation(client, db):
    a = make_alarm(db)
    label(client, a.id, "FALSE_ALARM")
    done = service.escalate_overdue(db, now=T0 + timedelta(seconds=61), after_s=60)
    assert [x.id for x in done] == [a.id]   # van leo thang binh thuong


def test_labeled_alarm_can_still_be_acked_and_cleared(client, db):
    a = make_alarm(db)
    label(client, a.id, "FALSE_ALARM")
    assert client.post(f"/api/v1/alarms/{a.id}/ack").status_code == 200
    make_alarm(db, level="NORMAL", alarm_id=a.alarm_id)  # su kien giai toa cung alarm_id
    db.refresh(a)
    assert a.state == AlarmState.CLEARED and a.label == "FALSE_ALARM"


def test_new_events_do_not_erase_label(client, db):
    a = make_alarm(db, level="CAUTION")
    label(client, a.id, "TRUE_ALARM")
    make_alarm(db, level="WARNING", alarm_id=a.alarm_id)
    db.refresh(a)
    assert a.level.value == "WARNING" and a.label == "TRUE_ALARM"


# ---------------- loc danh sach ----------------

def test_list_filters_by_label_and_unlabeled(client, db):
    a, b, c = make_alarm(db), make_alarm(db), make_alarm(db)
    label(client, a.id, "FALSE_ALARM")
    label(client, b.id, "TRUE_ALARM")
    ids = lambda q: sorted(x["id"] for x in client.get(f"/api/v1/alarms?{q}").json())  # noqa: E731
    assert ids("label=FALSE_ALARM") == [a.id]
    assert ids("label=TRUE_ALARM") == [b.id]
    assert ids("unlabeled=true") == [c.id]
    assert ids("") == sorted([a.id, b.id, c.id])
    assert client.get("/api/v1/alarms?label=NOPE").status_code == 422
    assert client.get("/api/v1/alarms?label=FALSE_ALARM&unlabeled=true").status_code == 422


# ---------------- thong ke ----------------

def test_stats_without_any_label_has_no_false_alarm_rate(client, db):
    make_alarm(db)
    s = client.get("/api/v1/alarms/stats").json()
    assert s["labeled"] == 0 and s["by_label"] == {} and s["label_coverage"] == 0
    assert s["false_alarm_rate"] is None            # chua ket luan -> None, KHONG phai 0%
    assert client.get("/api/v1/alarms/stats?device_id=ghost").json()["label_coverage"] is None


def test_false_alarm_rate_counts_only_concluded_alarms(client, db):
    alarms = [make_alarm(db) for _ in range(6)]
    for a, v in zip(alarms, ["FALSE_ALARM", "TRUE_ALARM", "TRUE_ALARM", "UNCLEAR"]):
        label(client, a.id, v)                      # 2 alarm cuoi chua danh gia
    s = client.get("/api/v1/alarms/stats").json()
    assert s["total"] == 6 and s["labeled"] == 4
    assert s["by_label"] == {"FALSE_ALARM": 1, "TRUE_ALARM": 2, "UNCLEAR": 1}
    assert s["label_coverage"] == pytest.approx(4 / 6)
    assert s["false_alarm_rate"] == pytest.approx(1 / 3)   # 1/(1+2): UNCLEAR va chua danh gia KHONG tinh


def test_stats_respects_device_filter(client, db):
    a = make_alarm(db, dev="vessel-1")
    b = make_alarm(db, dev="vessel-2")
    label(client, a.id, "FALSE_ALARM")
    label(client, b.id, "TRUE_ALARM")
    assert client.get("/api/v1/alarms/stats?device_id=vessel-1").json()["false_alarm_rate"] == 1.0
    assert client.get("/api/v1/alarms/stats?device_id=vessel-2").json()["false_alarm_rate"] == 0.0


# ---------------- thoi gian thuc ----------------

def test_label_is_broadcast_over_websocket(client, db, auth):
    a = make_alarm(db)
    token = auth("op01")["Authorization"].split()[1]
    with client.websocket_connect(f"/ws/alarms?token={token}") as ws:
        for _ in range(100):
            if hub.clients:
                break
            time.sleep(0.01)
        label(client, a.id, "FALSE_ALARM")
        msg = ws.receive_json()
        assert msg["action"] == "labeled" and msg["alarm"]["label"] == "FALSE_ALARM"
        assert msg["alarm"]["source_mode"] == "SIMULATION"
