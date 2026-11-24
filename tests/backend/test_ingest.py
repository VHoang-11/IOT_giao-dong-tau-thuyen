import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import AlarmEvent, Device, DeviceHealth, Telemetry
from app.models.enums import DeviceState
from ingest.service import Outcome, handle_message

EX = Path(__file__).resolve().parents[2] / "contracts" / "examples"
DEV = "vessel-demo-01"


def ex(name: str) -> dict:
    return json.loads((EX / f"{name}.json").read_text(encoding="utf-8"))


def send(db, kind: str, payload, dev: str = DEV):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return handle_message(db, f"svmg/{dev}/{kind}", raw)


def count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def test_telemetry_stored_with_rx_time_and_autoregister(db):
    r = send(db, "telemetry", ex("telemetry_sample"))
    assert r.outcome == Outcome.STORED
    t = db.scalar(select(Telemetry))
    assert t.server_rx_time is not None and t.source_mode.value == "SIMULATION"
    dev = db.scalar(select(Device))
    assert dev.device_id == DEV and dev.last_seen is not None


def test_duplicate_telemetry_ignored(db):
    p = ex("telemetry_sample")
    assert send(db, "telemetry", p).outcome == Outcome.STORED
    assert send(db, "telemetry", p).outcome == Outcome.DUPLICATE
    assert count(db, Telemetry) == 1
    p2 = {**p, "boot_id": "new-boot"}  # restart -> boot_id moi, seq co the trung so
    assert send(db, "telemetry", p2).outcome == Outcome.STORED
    assert count(db, Telemetry) == 2


def test_invalid_schema_rejected_and_not_stored(db):
    bad = ex("telemetry_sample")
    bad["class_rf"] = "CAPSIZE_FORECAST"
    r = send(db, "telemetry", bad)
    assert r.outcome == Outcome.INVALID and count(db, Telemetry) == 0
    del bad["roll_deg"]
    assert send(db, "telemetry", bad).outcome == Outcome.INVALID


def test_missing_source_mode_rejected(db):
    p = ex("telemetry_sample")
    del p["source_mode"]
    assert send(db, "telemetry", p).outcome == Outcome.INVALID


def test_bad_json_and_bad_topic(db):
    assert send(db, "telemetry", b"{not json").outcome == Outcome.INVALID
    assert handle_message(db, "other/x/telemetry", b"{}").outcome == Outcome.INVALID
    assert handle_message(db, "svmg/a b/telemetry", b"{}").outcome == Outcome.INVALID


def test_device_id_must_match_topic(db):
    r = send(db, "telemetry", ex("telemetry_sample"), dev="vessel-other")
    assert r.outcome == Outcome.REJECTED and count(db, Telemetry) == 0


def test_event_stored_and_deduped(db):
    e = ex("event_sample")
    assert send(db, "event", e).outcome == Outcome.STORED
    assert send(db, "event", e).outcome == Outcome.DUPLICATE
    assert count(db, AlarmEvent) == 1


def test_status_online_then_lwt_offline(db):
    send(db, "status", ex("status_online"))
    dev = db.scalar(select(Device))
    assert dev.state == DeviceState.online and dev.fw == "1.0.0" and dev.config_version == 8
    send(db, "status", ex("status_offline_lwt"))
    db.refresh(dev)
    assert dev.state == DeviceState.offline and dev.fw == "1.0.0"  # giu thong tin cu


def test_health_stored(db):
    h = {"device_id": DEV, "free_heap_bytes": 200000, "uptime_ms": 5000, "sensor_ok": False}
    assert send(db, "health", h).outcome == Outcome.STORED
    assert db.scalar(select(DeviceHealth)).sensor_ok is False


def test_cmd_ack_valid_is_ignored_until_m3_04(db):
    assert send(db, "cmd/ack", ex("command_ack_applied")).outcome == Outcome.IGNORED
    assert send(db, "cmd/ack", {"cmd_id": "x", "result": "MAYBE"}).outcome == Outcome.INVALID


@pytest.mark.parametrize("n", [50])
def test_offline_buffer_resync_is_idempotent(db, n):
    """T06: thiet bi gui lai cac ban tin dem offline (co ban da nhan) -> khong nhan doi."""
    base = ex("telemetry_sample")
    msgs = [{**base, "seq": i} for i in range(n)]
    for m in msgs[:30]:
        send(db, "telemetry", m)
    for m in msgs:  # gui lai toan bo
        send(db, "telemetry", m)
    assert count(db, Telemetry) == n
