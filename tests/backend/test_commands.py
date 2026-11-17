import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import AuditLog, Command, Device, DeviceConfigVersion
from app.models.enums import CommandName, CommandState
from commands import service
from commands.publisher import PublishFailed, set_publisher
from ingest.service import Outcome, handle_message
from ingest.validator import validate

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
DEV = "vessel-demo-01"


class FakePublisher:
    def __init__(self):
        self.sent = []          # (topic, payload_dict, qos, retain)
        self.fail = False
        self.deliver = True     # tu goi on_delivered nhu khi broker PUBACK

    def publish(self, topic, payload, qos=1, retain=False, on_delivered=None):
        if self.fail:
            raise PublishFailed("broker down")
        self.sent.append((topic, json.loads(payload), qos, retain))
        if on_delivered and self.deliver:
            on_delivered()


@pytest.fixture()
def pub():
    p = FakePublisher()
    set_publisher(p)
    yield p
    set_publisher(None)


@pytest.fixture()
def device(db):
    d = Device(device_id=DEV, config_version=7)
    db.add(d)
    db.commit()
    return d


def send(client, body, dev=DEV):
    return client.post(f"/api/v1/devices/{dev}/commands", json=body)


def ack(db, payload, dev=DEV, rx=T0):
    return handle_message(db, f"svmg/{dev}/cmd/ack", json.dumps(payload).encode(), rx_time=rx)


def audits(db, action):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)))


def event(db, level, seq, alarm_id="A-1"):
    p = {"device_id": DEV, "boot_id": "b1", "seq": seq, "type": "ALARM_STATE", "alarm_id": alarm_id,
         "level": level, "t_sim_s": 1.0}
    handle_message(db, f"svmg/{DEV}/event", json.dumps(p).encode(), rx_time=T0)


# ---------------- vong doi lenh ----------------

def test_send_command_publishes_valid_payload_and_becomes_delivered(client, db, pub, device):
    r = send(client, {"cmd": "set_profile", "params": {"profile": "SENSITIVE"}, "ttl_s": 30})
    assert r.status_code == 202
    topic, payload, qos, retain = pub.sent[0]
    assert topic == f"svmg/{DEV}/cmd" and qos == 1 and retain is False
    assert validate("cmd", payload) == []  # khop hop dong
    assert payload["issued_by"] == "sup01" and payload["ttl_s"] == 30
    c = db.scalar(select(Command))
    db.refresh(c)
    assert c.state == CommandState.DELIVERED and c.delivered_at is not None
    assert audits(db, "CMD_SENT")


def test_ack_applied_and_duplicate_ack(client, db, pub, device):
    cid = send(client, {"cmd": "calibrate_zero"}).json()["cmd_id"]
    r = ack(db, {"cmd_id": cid, "result": "APPLIED", "config_version": None, "reason": None})
    assert r.outcome == Outcome.STORED
    body = client.get(f"/api/v1/commands/{cid}").json()
    assert body["state"] == "APPLIED" and body["rtt_s"] is not None
    assert ack(db, {"cmd_id": cid, "result": "APPLIED"}).outcome == Outcome.DUPLICATE


def test_ack_rejected_keeps_reason(client, db, pub, device):
    cid = send(client, {"cmd": "calibrate_zero"}).json()["cmd_id"]
    ack(db, {"cmd_id": cid, "result": "REJECTED", "reason": "FORBIDDEN_STATE"})
    body = client.get(f"/api/v1/commands/{cid}").json()
    assert body["state"] == "REJECTED" and body["reason"] == "FORBIDDEN_STATE"


def test_ack_for_unknown_or_other_device_command(client, db, pub, device):
    cid = send(client, {"cmd": "calibrate_zero"}).json()["cmd_id"]
    assert ack(db, {"cmd_id": "nope", "result": "APPLIED"}).outcome == Outcome.IGNORED
    r = ack(db, {"cmd_id": cid, "result": "APPLIED"}, dev="vessel-other")
    assert r.outcome == Outcome.REJECTED
    assert client.get(f"/api/v1/commands/{cid}").json()["state"] == "DELIVERED"  # khong bi doi


# ---------------- idempotent ----------------

def test_same_cmd_id_is_idempotent(client, db, pub, device):
    body = {"cmd": "set_profile", "params": {"profile": "SENSITIVE"}, "cmd_id": "c-fixed"}
    assert send(client, body).status_code == 202
    again = send(client, body)
    assert again.status_code == 200 and again.json()["cmd_id"] == "c-fixed"
    assert len(pub.sent) == 1  # khong gui lan hai
    other = send(client, {**body, "params": {"profile": "CONSERVATIVE"}})
    assert other.status_code == 409


# ---------------- an toan ----------------

@pytest.mark.parametrize("body", [
    {"cmd": "set_threshold", "params": {"phi_hard_deg": 30}},      # ngoai 15-25
    {"cmd": "set_threshold", "params": {"phi_hard_deg": 10}},
    {"cmd": "set_threshold", "params": {}},                          # rong
    {"cmd": "set_threshold", "params": {"alarm_enabled": False}},   # co tat canh bao -> cam
    {"cmd": "set_profile", "params": {"profile": "OFF"}},
    {"cmd": "set_profile", "params": {"profile": "STANDARD", "mute": True}},
    {"cmd": "mute_alarm", "params": {"duration_s": 99999}},
    {"cmd": "restart_device", "params": {"x": 1}},
    {"cmd": "disable_alarm"},                                        # khong co trong whitelist
    {"cmd": "calibrate_zero", "ttl_s": 0},
    {"cmd": "calibrate_zero", "ttl_s": 301},
])
def test_unsafe_or_invalid_commands_rejected_and_not_published(client, pub, device, auth, body):
    # dung ADMIN de moi lenh deu du quyen: test nay kiem tra THAM SO, khong kiem tra phan quyen
    r = client.post(f"/api/v1/devices/{DEV}/commands", json=body, headers=auth("admin01"))
    assert r.status_code == 422
    assert pub.sent == []


def test_mute_blocked_when_critical_and_audited(client, db, pub, device):
    event(db, "CRITICAL", 1)
    r = send(client, {"cmd": "mute_alarm"})
    assert r.status_code == 409 and "CRITICAL" in r.json()["detail"]
    assert pub.sent == [] and db.scalar(select(Command)) is None
    assert audits(db, "CMD_BLOCKED")  # lan bi chan van co dau vet


def test_mute_allowed_below_critical(client, db, pub, device):
    event(db, "CAUTION", 1)
    assert send(client, {"cmd": "mute_alarm", "params": {"duration_s": 60}}).status_code == 202


def test_unknown_device_404(client, pub):
    assert send(client, {"cmd": "calibrate_zero"}, dev="ghost").status_code == 404


# ---------------- TTL / timeout ----------------

def test_ttl_expiry_and_late_ack_does_not_resurrect(client, db, pub, device):
    c, _ = service.create_command(db, DEV, CommandName.restart_device, {}, 30, "bob", now=T0)
    assert service.expire_overdue(db, now=T0 + timedelta(seconds=29)) == []
    done = service.expire_overdue(db, now=T0 + timedelta(seconds=31))
    assert [x.cmd_id for x in done] == [c.cmd_id]
    assert audits(db, "CMD_TIMEOUT")
    r = ack(db, {"cmd_id": c.cmd_id, "result": "APPLIED"})
    assert r.outcome == Outcome.IGNORED
    db.refresh(c)
    assert c.state == CommandState.TIMEOUT  # van TIMEOUT
    assert audits(db, "CMD_LATE_ACK")


def test_finished_commands_not_expired(client, db, pub, device):
    c, _ = service.create_command(db, DEV, CommandName.calibrate_zero, {}, 30, "bob", now=T0)
    ack(db, {"cmd_id": c.cmd_id, "result": "APPLIED"}, rx=T0 + timedelta(seconds=2))
    assert service.expire_overdue(db, now=T0 + timedelta(hours=1)) == []


def test_publish_failure_returns_503_and_marks_timeout(client, db, pub, device):
    pub.fail = True
    r = send(client, {"cmd": "calibrate_zero", "cmd_id": "c-down"})
    assert r.status_code == 503
    assert client.get("/api/v1/commands/c-down").json()["state"] == "TIMEOUT"
    assert audits(db, "CMD_PUBLISH_FAILED")


def test_no_publisher_configured_returns_503(client, device):
    set_publisher(None)
    assert send(client, {"cmd": "calibrate_zero"}).status_code == 503


def test_stats_rtt_and_timeout_rate(client, db, pub, device):
    c1, _ = service.create_command(db, DEV, CommandName.calibrate_zero, {}, 30, "a", now=T0)
    ack(db, {"cmd_id": c1.cmd_id, "result": "APPLIED"}, rx=T0 + timedelta(seconds=2))
    service.create_command(db, DEV, CommandName.calibrate_zero, {}, 10, "a", now=T0)
    service.expire_overdue(db, now=T0 + timedelta(seconds=11))
    s = client.get("/api/v1/commands/stats").json()
    assert s["total"] == 2 and s["by_state"] == {"APPLIED": 1, "TIMEOUT": 1}
    assert s["rtt_mean_s"] == 2 and s["timeout_rate"] == 0.5


def test_audit_endpoint(client, pub, device):
    send(client, {"cmd": "calibrate_zero"})
    rows = client.get("/api/v1/audit?action=CMD_SENT").json()
    assert rows and rows[0]["actor"] == "sup01" and rows[0]["detail"]["cmd"] == "calibrate_zero"


# ---------------- cau hinh co phien ban + rollback ----------------

def put_cfg(client, body):
    return client.put(f"/api/v1/devices/{DEV}/config", json=body)


def test_config_update_versioning_crc_and_retained_publish(client, db, pub, device):
    r = put_cfg(client, {"profile": "SENSITIVE", "phi_hard_deg": 22})
    assert r.status_code == 201
    p = r.json()["payload"]
    assert p["config_version"] == 8  # thiet bi dang o v7 -> v8
    assert p["profile"] == "SENSITIVE" and p["phi_hard_deg"] == 22
    assert "mai_caution" not in p  # backend khong tu dien gia tri mac dinh thay M1
    topic, sent, qos, retain = pub.sent[-1]
    assert topic == f"svmg/{DEV}/config" and retain is True and qos == 1
    assert validate("config", sent) == [] and sent["crc"] == p["crc"]
    assert put_cfg(client, {"debounce_n": 4}).json()["payload"]["config_version"] == 9
    versions = [h["config_version"] for h in client.get(f"/api/v1/devices/{DEV}/config").json()]
    assert versions == [9, 8]  # moi nhat truoc
    assert audits(db, "CONFIG_UPDATE")


def test_config_rejects_out_of_range(client, pub, device):
    assert put_cfg(client, {"phi_hard_deg": 30}).status_code == 422
    assert put_cfg(client, {}).status_code == 422
    assert put_cfg(client, {"alarm_enabled": False}).status_code == 422
    assert pub.sent == []


def test_rollback_creates_new_higher_version_with_old_content(client, db, pub, device):
    put_cfg(client, {"profile": "SENSITIVE"})      # v8
    put_cfg(client, {"profile": "CONSERVATIVE"})   # v9
    r = client.post(f"/api/v1/devices/{DEV}/config/rollback", json={})
    assert r.status_code == 201
    p = r.json()["payload"]
    assert p["config_version"] == 10 and p["profile"] == "SENSITIVE"  # so moi, noi dung cu
    assert pub.sent[-1][3] is True
    assert audits(db, "CONFIG_ROLLBACK")[0].detail == {"from_version": 9, "restored_from_version": 8}
    r2 = client.post(f"/api/v1/devices/{DEV}/config/rollback", json={"to_version": 9})
    assert r2.status_code == 201 and r2.json()["payload"]["profile"] == "CONSERVATIVE"


def test_rollback_conflicts(client, pub, device):
    assert client.post(f"/api/v1/devices/{DEV}/config/rollback", json={}).status_code == 409  # chua co gi
    put_cfg(client, {"profile": "SENSITIVE"})
    assert client.post(f"/api/v1/devices/{DEV}/config/rollback", json={}).status_code == 409  # chi co 1 ban
    put_cfg(client, {"profile": "CONSERVATIVE"})
    assert client.post(f"/api/v1/devices/{DEV}/config/rollback", json={"to_version": 99}).status_code == 409
    assert client.post(f"/api/v1/devices/{DEV}/config/rollback", json={"to_version": 9}).status_code == 409


def test_config_applied_when_device_reports_version(client, db, pub, device):
    put_cfg(client, {"profile": "SENSITIVE"})  # v8, applied=False
    row = db.scalar(select(DeviceConfigVersion).where(DeviceConfigVersion.config_version == 8))
    assert row.applied is False
    handle_message(db, f"svmg/{DEV}/status", json.dumps({"state": "online", "config_version": 8}).encode())
    db.refresh(row)
    assert row.applied is True


def test_config_applied_via_command_ack(client, db, pub, device):
    put_cfg(client, {"profile": "SENSITIVE"})
    cid = send(client, {"cmd": "calibrate_zero"}).json()["cmd_id"]
    ack(db, {"cmd_id": cid, "result": "APPLIED", "config_version": 8})
    row = db.scalar(select(DeviceConfigVersion).where(DeviceConfigVersion.config_version == 8))
    db.refresh(row)
    assert row.applied is True


def test_config_publish_failure_leaves_no_version(client, db, pub, device):
    pub.fail = True
    assert put_cfg(client, {"profile": "SENSITIVE"}).status_code == 503
    assert db.scalar(select(DeviceConfigVersion)) is None  # rollback toan bo, khong de ban 'ma'
    assert put_cfg(client, {"profile": "SENSITIVE"}).status_code == 503
    pub.fail = False
    assert put_cfg(client, {"profile": "SENSITIVE"}).json()["payload"]["config_version"] == 8
