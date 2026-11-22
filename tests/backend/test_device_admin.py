"""Quan ly thiet bi (Admin) + trang thai hieu chuan (G5)."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from conftest import NOAUTH
from sqlalchemy import select

from app.core.config import settings
from app.models import AuditLog, Device, Telemetry
from app.models.enums import CommandName
from commands import service as cmd_service
from commands.publisher import set_publisher
from ingest.service import Outcome, handle_message
from ingest.stats import stats

EX = Path(__file__).resolve().parents[2] / "contracts" / "examples"
DEV = "vessel-demo-01"
T0 = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


class Pub:
    def __init__(self):
        self.sent = []

    def publish(self, topic, payload, qos=1, retain=False, on_delivered=None):
        self.sent.append((topic, json.loads(payload)))
        if on_delivered:
            on_delivered()


@pytest.fixture()
def pub():
    p = Pub()
    set_publisher(p)
    yield p
    set_publisher(None)


def tele_bytes(seq=1, **over):
    p = json.loads((EX / "telemetry_sample.json").read_text(encoding="utf-8"))
    p.update(seq=seq, **over)
    return json.dumps(p).encode()


def register(client, headers=None, **body):
    body = {"device_id": "ship-1", "source_mode": "SENSOR", **body}
    return client.post("/api/v1/devices", json=body, headers=headers) if headers else client.post("/api/v1/devices", json=body)


def audits(db, action):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)))


# ---------------------------------------------------------------- dang ky

def test_register_requires_admin(client, auth):
    assert register(client).status_code == 403                                   # sup01 (Supervisor)
    assert register(client, auth("op01")).status_code == 403
    assert register(client, NOAUTH).status_code == 401
    assert register(client, auth("admin01")).status_code == 201


def test_register_creates_device_with_explicit_source_mode_and_audit(client, db, auth):
    r = register(client, auth("admin01"), device_id="ship-9", name="  Tàu số 9  ", source_mode="SENSOR")
    assert r.status_code == 201
    d = r.json()
    assert d["device_id"] == "ship-9" and d["name"] == "Tàu số 9" and d["source_mode"] == "SENSOR"
    assert d["enabled"] is True and d["state"] == "offline" and d["last_seen"] is None
    assert audits(db, "DEVICE_REGISTER")[0].detail == {"name": "Tàu số 9", "source_mode": "SENSOR"}
    assert client.get("/api/v1/devices/ship-9").json()["name"] == "Tàu số 9"


@pytest.mark.parametrize("body", [
    {"source_mode": None}, {"device_id": "bad id"}, {"device_id": ""}, {"device_id": "x" * 65},
    {"name": "x" * 129}, {"name": "ten\x00xau"}, {"name": "dong1\ndong2"}, {"source_mode": "REAL"}, {"extra": 1}])
def test_register_validation(client, auth, body):
    payload = {"device_id": "ship-1", "source_mode": "SENSOR", **body}
    assert client.post("/api/v1/devices", json=payload, headers=auth("admin01")).status_code == 422


def test_register_requires_source_mode_no_silent_default(client, auth):
    r = client.post("/api/v1/devices", json={"device_id": "ship-1"}, headers=auth("admin01"))
    assert r.status_code == 422                                                   # khong co mac dinh ngam SIMULATION


def test_register_duplicate_is_409_even_when_device_auto_registered(client, db, auth):
    handle_message(db, f"svmg/{DEV}/telemetry", tele_bytes())                       # tu dang ky qua MQTT
    assert register(client, auth("admin01"), device_id=DEV).status_code == 409
    assert register(client, auth("admin01"), device_id="new").status_code == 201
    assert register(client, auth("admin01"), device_id="new").status_code == 409


# ---------------------------------------------------------------- cap nhat ten / bat-tat

def test_rename_and_clear_name(client, db, auth):
    register(client, auth("admin01"), device_id="ship-1", name="Cu")
    r = client.patch("/api/v1/devices/ship-1", json={"name": "Moi"}, headers=auth("admin01"))
    assert r.status_code == 200 and r.json()["name"] == "Moi"
    assert audits(db, "DEVICE_UPDATE")[0].detail == {"name": ["Cu", "Moi"]}
    assert client.patch("/api/v1/devices/ship-1", json={"name": "   "}, headers=auth("admin01")).json()["name"] is None
    assert client.patch("/api/v1/devices/ship-1", json={"name": None}, headers=auth("admin01")).json()["name"] is None


def test_update_permissions_and_validation(client, auth):
    register(client, auth("admin01"), device_id="ship-1")
    for h, code in ((auth("sup01"), 403), (auth("op01"), 403), (NOAUTH, 401)):
        assert client.patch("/api/v1/devices/ship-1", json={"name": "x"}, headers=h).status_code == code
    adm = auth("admin01")
    assert client.patch("/api/v1/devices/ship-1", json={}, headers=adm).status_code == 422           # rong
    assert client.patch("/api/v1/devices/ship-1", json={"enabled": None}, headers=adm).status_code == 422
    assert client.patch("/api/v1/devices/ship-1", json={"enabled": "maybe"}, headers=adm).status_code == 422
    assert client.patch("/api/v1/devices/ship-1", json={"source_mode": "SENSOR"}, headers=adm).status_code == 422
    assert client.patch("/api/v1/devices/ghost", json={"name": "x"}, headers=adm).status_code == 404


def test_unchanged_update_writes_no_audit(client, db, auth):
    register(client, auth("admin01"), device_id="ship-1", name="A")
    client.patch("/api/v1/devices/ship-1", json={"name": "A", "enabled": True}, headers=auth("admin01"))
    assert audits(db, "DEVICE_UPDATE") == []


def test_no_delete_endpoint_history_is_preserved(client, auth):
    register(client, auth("admin01"))
    assert client.delete("/api/v1/devices/ship-1", headers=auth("admin01")).status_code == 405


# ---------------------------------------------------------------- vo hieu hoa

def test_disabled_device_messages_are_rejected_and_visible_in_stats(client, db, auth):
    handle_message(db, f"svmg/{DEV}/telemetry", tele_bytes(1))
    assert client.patch(f"/api/v1/devices/{DEV}", json={"enabled": False}, headers=auth("admin01")).status_code == 200
    r = handle_message(db, f"svmg/{DEV}/telemetry", tele_bytes(2))
    assert r.outcome == Outcome.REJECTED and "vo hieu hoa" in r.reason
    for kind, p in (("status", {"state": "online"}), ("health", {"device_id": DEV, "free_heap_bytes": 1, "uptime_ms": 1, "sensor_ok": True})):
        assert handle_message(db, f"svmg/{DEV}/{kind}", json.dumps(p).encode()).outcome == Outcome.REJECTED
    assert db.scalar(select(Telemetry).where(Telemetry.seq == 2)) is None             # khong bi luu
    err = stats.snapshot()["recent_errors"][0]
    assert err["outcome"] == "REJECTED" and "vo hieu hoa" in err["reason"]


def test_reenabling_resumes_accepting_messages(client, db, auth):
    handle_message(db, f"svmg/{DEV}/telemetry", tele_bytes(1))
    client.patch(f"/api/v1/devices/{DEV}", json={"enabled": False}, headers=auth("admin01"))
    client.patch(f"/api/v1/devices/{DEV}", json={"enabled": True}, headers=auth("admin01"))
    assert handle_message(db, f"svmg/{DEV}/telemetry", tele_bytes(3)).outcome == Outcome.STORED
    d = audits(db, "DEVICE_UPDATE")
    assert [a.detail["enabled"] for a in d] == [[True, False], [False, True]]


def test_disabled_device_cannot_receive_commands_config_or_voyages(client, db, pub, auth):
    handle_message(db, f"svmg/{DEV}/telemetry", tele_bytes(1))
    client.patch(f"/api/v1/devices/{DEV}", json={"enabled": False}, headers=auth("admin01"))
    r = client.post(f"/api/v1/devices/{DEV}/commands", json={"cmd": "calibrate_zero"})
    assert r.status_code == 409 and "vô hiệu hóa" in r.json()["detail"] and pub.sent == []
    assert audits(db, "CMD_BLOCKED")                                                   # lan bi chan van co dau vet
    assert client.put(f"/api/v1/devices/{DEV}/config", json={"profile": "SENSITIVE"}).status_code == 409
    assert client.post("/api/v1/voyages", json={"device_id": DEV}).status_code == 409
    assert pub.sent == []


def test_disabled_device_history_and_reads_still_work(client, db, auth):
    handle_message(db, f"svmg/{DEV}/telemetry", tele_bytes(1))
    client.patch(f"/api/v1/devices/{DEV}", json={"enabled": False}, headers=auth("admin01"))
    assert client.get(f"/api/v1/devices/{DEV}").json()["enabled"] is False
    assert len(client.get(f"/api/v1/devices/{DEV}/telemetry").json()) == 1


def test_existing_devices_default_to_enabled(client, db):
    db.add(Device(device_id="legacy"))
    db.commit()
    assert client.get("/api/v1/devices/legacy").json()["enabled"] is True


# ---------------------------------------------------------------- AUTO_REGISTER_DEVICES

def test_auto_register_on_by_default(db):
    assert handle_message(db, f"svmg/{DEV}/telemetry", tele_bytes()).outcome == Outcome.STORED
    assert db.scalar(select(Device).where(Device.device_id == DEV)) is not None


def test_strict_mode_accepts_only_preregistered_devices(client, db, auth, monkeypatch):
    monkeypatch.setattr(settings, "auto_register_devices", False)
    r = handle_message(db, f"svmg/{DEV}/telemetry", tele_bytes())
    assert r.outcome == Outcome.REJECTED and "chua duoc Admin dang ky" in r.reason
    assert db.scalar(select(Device).where(Device.device_id == DEV)) is None          # KHONG tu tao thiet bi
    register(client, auth("admin01"), device_id=DEV, source_mode="SIMULATION")
    assert handle_message(db, f"svmg/{DEV}/telemetry", tele_bytes()).outcome == Outcome.STORED


def test_registered_device_source_mode_follows_real_telemetry(client, db, auth):
    register(client, auth("admin01"), device_id=DEV, source_mode="SENSOR")
    handle_message(db, f"svmg/{DEV}/telemetry", tele_bytes(source_mode="SIMULATION"))
    assert client.get(f"/api/v1/devices/{DEV}").json()["source_mode"] == "SIMULATION"   # theo ban tin that


# ---------------------------------------------------------------- hieu chuan (G5)

def fleet(client, dev=DEV):
    return {d["device_id"]: d for d in client.get("/api/v1/health/devices").json()}[dev]


def test_calibration_fields_are_null_when_never_calibrated(client, db):
    db.add(Device(device_id=DEV))
    db.commit()
    d = fleet(client)
    assert d["last_calibrated_at"] is None and d["last_calibration_state"] is None   # None, khong phai 'khong can'


def test_calibration_reports_last_applied_and_last_attempt(client, db, pub):
    db.add(Device(device_id=DEV))
    db.commit()
    c1, _ = cmd_service.create_command(db, DEV, CommandName.calibrate_zero, {}, 30, "sup01", now=T0)
    handle_message(db, f"svmg/{DEV}/cmd/ack", json.dumps({"cmd_id": c1.cmd_id, "result": "APPLIED"}).encode(),
                   rx_time=T0 + timedelta(seconds=3))
    d = fleet(client)
    assert d["last_calibration_state"] == "APPLIED" and d["last_calibrated_at"].startswith("2026-01-01T12:00:03")
    # lan thu hai bi tu choi: 'lan hieu chuan gan nhat' van la lan APPLIED, nhung trang thai lan gui gan nhat la REJECTED
    c2, _ = cmd_service.create_command(db, DEV, CommandName.calibrate_zero, {}, 30, "sup01", now=T0 + timedelta(hours=1))
    handle_message(db, f"svmg/{DEV}/cmd/ack", json.dumps({"cmd_id": c2.cmd_id, "result": "REJECTED"}).encode(),
                   rx_time=T0 + timedelta(hours=1, seconds=2))
    d = fleet(client)
    assert d["last_calibration_state"] == "REJECTED" and d["last_calibrated_at"].startswith("2026-01-01T12:00:03")
    assert d["last_calibrated_at"].endswith(("Z", "+00:00"))


def test_calibration_ignores_other_commands_and_other_devices(client, db, pub):
    db.add_all([Device(device_id=DEV), Device(device_id="other")])
    db.commit()
    c, _ = cmd_service.create_command(db, DEV, CommandName.restart_device, {}, 30, "admin01", now=T0)
    handle_message(db, f"svmg/{DEV}/cmd/ack", json.dumps({"cmd_id": c.cmd_id, "result": "APPLIED"}).encode())
    c2, _ = cmd_service.create_command(db, "other", CommandName.calibrate_zero, {}, 30, "sup01", now=T0)
    handle_message(db, "svmg/other/cmd/ack", json.dumps({"cmd_id": c2.cmd_id, "result": "APPLIED"}).encode())
    assert fleet(client)["last_calibrated_at"] is None                                  # restart khong phai hieu chuan
    assert fleet(client, "other")["last_calibrated_at"] is not None


def test_calibration_pending_command_shows_state_but_no_calibrated_time(client, db, pub):
    db.add(Device(device_id=DEV))
    db.commit()
    cmd_service.create_command(db, DEV, CommandName.calibrate_zero, {}, 30, "sup01", now=T0)    # chua co ACK
    d = fleet(client)
    assert d["last_calibration_state"] == "DELIVERED" and d["last_calibrated_at"] is None
