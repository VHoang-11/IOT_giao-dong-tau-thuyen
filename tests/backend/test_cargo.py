"""Multi-Node: Cargo Node (ESP32 thu 2) gui topic svmg/{device_id}/cargo.

Kiem tra: ingest (schema, trung, null), tach khoi telemetry/FSM canh bao dao dong, lien ket tau chinh do Admin dat,
API GET /devices/{id}/cargo, Cargo Node khong nhan lenh/cau hinh/chuyen di.
"""
import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import CargoTelemetry, Device, Telemetry
from app.models.enums import NodeType
from commands.publisher import set_publisher
from ingest.service import SUBSCRIPTIONS, Outcome, handle_message

EX = Path(__file__).resolve().parents[2] / "contracts" / "examples"
MAIN = "vessel-demo-01"
CARGO = "vessel-demo-01-cargo"


def sample(**over) -> dict:
    p = json.loads((EX / "cargo_sample.json").read_text(encoding="utf-8"))
    p.update(over)
    return p


def send(db, payload, dev: str = CARGO, kind: str = "cargo"):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return handle_message(db, f"svmg/{dev}/{kind}", raw)


def count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def link(client, auth, parent=MAIN, dev=CARGO):
    return client.patch(f"/api/v1/devices/{dev}", json={"parent_device_id": parent}, headers=auth("admin01"))


class Pub:
    def __init__(self):
        self.sent = []

    def publish(self, topic, payload, qos=1, retain=False, on_delivered=None):
        self.sent.append(topic)


# ---------------------------------------------------------------- ingest
def test_backend_subscribes_cargo_topic_qos0():
    assert ("svmg/+/cargo", 0) in SUBSCRIPTIONS


def test_cargo_stored_and_marks_cargo_node(db):
    r = send(db, sample())
    assert r.outcome == Outcome.STORED and r.kind == "cargo"
    row = db.scalar(select(CargoTelemetry))
    assert row.cargo_water_pct == 18.5 and row.cargo_temp_c == 27.4 and row.cargo_humidity_pct == 61.2
    assert row.server_rx_time is not None and row.source_mode.value == "SIMULATION"
    dev = db.scalar(select(Device).where(Device.device_id == CARGO))
    assert dev.node_type == NodeType.CARGO and dev.last_seen is not None
    assert dev.parent_device_id is None   # parent_device_id trong payload KHONG tu dong lien ket
    assert row.reported_parent_device_id == MAIN


def test_cargo_does_not_touch_motion_tables(db):
    send(db, sample())
    assert count(db, Telemetry) == 0   # khong tao telemetry/roll/pitch gia


def test_duplicate_cargo_ignored_but_new_boot_accepted(db):
    p = sample()
    assert send(db, p).outcome == Outcome.STORED
    assert send(db, p).outcome == Outcome.DUPLICATE
    assert count(db, CargoTelemetry) == 1
    assert send(db, sample(boot_id="newboot")).outcome == Outcome.STORED   # restart: seq co the trung
    assert count(db, CargoTelemetry) == 2


def test_sensor_fault_nulls_are_stored_as_null_not_zero(db):
    p = sample(sensor_ok=False, cargo_temp_c=None, cargo_humidity_pct=None)
    assert send(db, p).outcome == Outcome.STORED
    row = db.scalar(select(CargoTelemetry))
    assert row.sensor_ok is False and row.cargo_temp_c is None and row.cargo_humidity_pct is None
    assert row.cargo_water_pct == 18.5


@pytest.mark.parametrize("patch", [
    {"cargo_water_pct": 120},
    {"cargo_humidity_pct": -1},
    {"seq": -1},
    {"sensor_ok": "yes"},
    {"cargo_temp_c": "hot"},
])
def test_invalid_cargo_payload_rejected(db, patch):
    r = send(db, sample(**patch))
    assert r.outcome == Outcome.INVALID
    assert count(db, CargoTelemetry) == 0


@pytest.mark.parametrize("missing", ["device_id", "boot_id", "seq", "uptime_ms", "sensor_ok",
                                     "cargo_water_pct", "cargo_temp_c", "cargo_humidity_pct"])
def test_missing_required_field_rejected(db, missing):
    p = sample()
    p.pop(missing)
    assert send(db, p).outcome == Outcome.INVALID


def test_device_id_in_payload_must_match_topic(db):
    r = send(db, sample(device_id="someone-else"))
    assert r.outcome == Outcome.REJECTED
    assert count(db, CargoTelemetry) == 0


def test_nan_and_bad_json_rejected(db):
    assert send(db, b'{"device_id":"%s","boot_id":"b","seq":1,"uptime_ms":1,"sensor_ok":true,'
                    b'"cargo_water_pct":NaN,"cargo_temp_c":1,"cargo_humidity_pct":1}' % CARGO.encode()).outcome == Outcome.INVALID
    assert send(db, b"not json").outcome == Outcome.INVALID


def test_roll_pitch_extra_fields_are_not_stored(db):
    send(db, sample(roll_deg=9.9, pitch_deg=9.9))
    assert count(db, Telemetry) == 0   # cargo handler khong ghi roll/pitch


# ---------------------------------------------------------------- lien ket tau chinh + API
def test_get_cargo_by_main_vessel_aggregates_linked_node(client, db, auth):
    send(db, sample(seq=1, cargo_water_pct=10.0))
    send(db, sample(seq=2, cargo_water_pct=20.0))
    send(db, {"device_id": MAIN, "boot_id": "b", "seq": 1, "uptime_ms": 1, "t_sim_s": 0, "source_mode": "SIMULATION",
              "roll_deg": 0, "pitch_deg": 0, "class_rf": "NORMAL", "alarm_level": "NORMAL", "model_version": "m",
              "config_version": 1, "sensor_ok": True}, dev=MAIN, kind="telemetry")
    # chua gan parent -> tau chinh chua co du lieu ham hang
    assert client.get(f"/api/v1/devices/{MAIN}/cargo").json() == []
    assert link(client, auth).status_code == 200
    rows = client.get(f"/api/v1/devices/{MAIN}/cargo").json()
    assert [r["seq"] for r in rows] == [2, 1]   # moi nhat truoc
    assert rows[0]["device_id"] == CARGO and rows[0]["cargo_water_pct"] == 20.0
    assert "roll_deg" not in rows[0]
    # goi truc tiep bang id cua Cargo Node cung duoc
    assert len(client.get(f"/api/v1/devices/{CARGO}/cargo").json()) == 2
    assert len(client.get(f"/api/v1/devices/{MAIN}/cargo?limit=1").json()) == 1


def test_get_cargo_unknown_device_404_and_requires_login(client, db):
    assert client.get("/api/v1/devices/khong-co/cargo").status_code == 404
    assert client.get(f"/api/v1/devices/{MAIN}/cargo", headers={"Authorization": ""}).status_code == 401


def test_link_requires_admin(client, db, auth):
    send(db, sample())
    for who in ("op01", "sup01"):
        r = client.patch(f"/api/v1/devices/{CARGO}", json={"parent_device_id": MAIN}, headers=auth(who))
        assert r.status_code == 403


def test_link_validation(client, db, auth):
    send(db, sample())
    assert link(client, auth, parent="khong-ton-tai").status_code == 404
    assert link(client, auth, parent=CARGO).status_code == 422          # tu tro vao chinh no
    send(db, {"device_id": MAIN, "boot_id": "b", "seq": 1, "uptime_ms": 1, "t_sim_s": 0, "source_mode": "SIMULATION",
              "roll_deg": 0, "pitch_deg": 0, "class_rf": "NORMAL", "alarm_level": "NORMAL", "model_version": "m",
              "config_version": 1, "sensor_ok": True}, dev=MAIN, kind="telemetry")
    assert link(client, auth).status_code == 200
    d = client.get(f"/api/v1/devices/{CARGO}").json()
    assert d["node_type"] == "CARGO" and d["parent_device_id"] == MAIN
    # tau chinh dang co Cargo Node thi khong the bien thanh Cargo Node
    assert link(client, auth, parent=CARGO, dev=MAIN).status_code == 409
    # Cargo Node khong the lam tau chinh
    send(db, sample(device_id="cargo-2"), dev="cargo-2")
    assert link(client, auth, parent=CARGO, dev="cargo-2").status_code == 409
    # go lien ket
    r = client.patch(f"/api/v1/devices/{CARGO}", json={"parent_device_id": None}, headers=auth("admin01"))
    assert r.status_code == 200 and r.json()["parent_device_id"] is None
    assert client.get(f"/api/v1/devices/{MAIN}/cargo").json() == []


def test_register_cargo_node_in_advance(client, db, auth):
    send(db, {"device_id": MAIN, "boot_id": "b", "seq": 1, "uptime_ms": 1, "t_sim_s": 0, "source_mode": "SIMULATION",
              "roll_deg": 0, "pitch_deg": 0, "class_rf": "NORMAL", "alarm_level": "NORMAL", "model_version": "m",
              "config_version": 1, "sensor_ok": True}, dev=MAIN, kind="telemetry")
    body = {"device_id": CARGO, "source_mode": "SIMULATION", "node_type": "CARGO", "parent_device_id": MAIN}
    r = client.post("/api/v1/devices", json=body, headers=auth("admin01"))
    assert r.status_code == 201 and r.json()["node_type"] == "CARGO" and r.json()["parent_device_id"] == MAIN
    bad = {"device_id": "x1", "source_mode": "SIMULATION", "parent_device_id": MAIN}   # parent voi MOTION -> sai
    assert client.post("/api/v1/devices", json=bad, headers=auth("admin01")).status_code == 422


def test_devices_list_exposes_node_type(client, db):
    send(db, sample())
    row = next(d for d in client.get("/api/v1/devices").json() if d["device_id"] == CARGO)
    assert row["node_type"] == "CARGO"


# ---------------------------------------------------------------- Cargo Node khong nhan lenh/cau hinh/chuyen di
def test_cargo_node_rejects_commands_config_and_voyage(client, db, auth):
    pub = Pub()
    set_publisher(pub)
    send(db, sample())
    r = client.post(f"/api/v1/devices/{CARGO}/commands", json={"cmd": "set_profile", "params": {"profile": "STANDARD"}})
    assert r.status_code == 409 and "Cargo Node" in r.json()["detail"]
    r = client.put(f"/api/v1/devices/{CARGO}/config", json={"profile": "STANDARD"})
    assert r.status_code == 409
    r = client.post("/api/v1/voyages", json={"device_id": CARGO})
    assert r.status_code == 409
    assert pub.sent == []   # khong co gi duoc phat xuong MQTT
