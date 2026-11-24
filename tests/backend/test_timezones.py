"""Moi moc thoi gian tra ra tu API phai co mui gio UTC.

Neu khong, SQLite tra datetime khong mui gio, JSON khong co 'Z', va JavaScript hieu la GIO DIA PHUONG
-> dashboard o Viet Nam (UTC+7) lech 7 tieng.
"""
import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import Device, Telemetry, Voyage
from app.models.enums import AlarmLevel, MotionClass, SourceMode
from app.models.tables import UTCDateTime
from ingest.service import handle_message

DEV = "vessel-demo-01"
TZ_SUFFIX = re.compile(r"(Z|[+-]\d{2}:\d{2})$")


def walk(obj, path="$"):
    """Duyet JSON, tra ve (duong_dan, chuoi) cua moi chuoi trong giong ISO-datetime."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")
    elif isinstance(obj, str) and re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", obj):
        yield path, obj


@pytest.fixture()
def populated(client, db):
    """Co du moi loai ban ghi co thoi gian: thiet bi, telemetry, canh bao, lenh, chuyen di, health, audit."""
    from commands import service as cmd_service
    from commands.publisher import set_publisher

    class P:
        def publish(self, *a, on_delivered=None, **k):
            if on_delivered:
                on_delivered()

    set_publisher(P())
    tele = {"device_id": DEV, "boot_id": "b1", "seq": 1, "t_sim_s": 1.0, "uptime_ms": 1, "source_mode": "SIMULATION",
            "voyage_id": "V-TZ", "roll_deg": 1.0, "pitch_deg": 0.0, "class_rf": "NORMAL", "alarm_level": "NORMAL",
            "model_version": "m", "config_version": 1, "sensor_ok": True}
    handle_message(db, f"svmg/{DEV}/telemetry", json.dumps(tele).encode())
    handle_message(db, f"svmg/{DEV}/health", json.dumps(
        {"device_id": DEV, "free_heap_bytes": 1, "uptime_ms": 1, "sensor_ok": True}).encode())
    handle_message(db, f"svmg/{DEV}/event", json.dumps(
        {"device_id": DEV, "boot_id": "b1", "seq": 2, "type": "ALARM_STATE", "alarm_id": "A-1", "level": "WARNING",
         "class": "HIGH_ROLL", "t_sim_s": 1.0}).encode())
    client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-TZ"})
    cmd_service.create_command(db, DEV, cmd_service.CommandName.calibrate_zero, {}, 60, "sup01")
    alarm_id = client.get("/api/v1/alarms").json()[0]["id"]
    client.post(f"/api/v1/alarms/{alarm_id}/ack")
    client.put(f"/api/v1/alarms/{alarm_id}/label", json={"label": "TRUE_ALARM"})
    yield alarm_id
    set_publisher(None)


@pytest.mark.parametrize("path", [
    "/api/v1/devices", f"/api/v1/devices/{DEV}", f"/api/v1/devices/{DEV}/telemetry", f"/api/v1/devices/{DEV}/health",
    "/api/v1/health/devices", "/api/v1/alarms", "/api/v1/commands", "/api/v1/voyages", "/api/v1/voyages/V-TZ",
    "/api/v1/voyages/V-TZ/summary", "/api/v1/voyages/V-TZ/replay", "/api/v1/audit", "/api/v1/users",
    "/api/v1/auth/me",
])
def test_every_api_timestamp_has_a_timezone(client, populated, auth, path):
    body = client.get(path, headers=auth("admin01"))  # Admin xem duoc moi API (vd. /users chi danh cho Admin)
    assert body.status_code == 200, path
    stamps = list(walk(body.json()))
    assert stamps, f"{path} khong co moc thoi gian nao de kiem tra"
    bad = [(p, s) for p, s in stamps if not TZ_SUFFIX.search(s)]
    assert bad == [], f"{path}: moc thoi gian thieu mui gio: {bad[:3]}"
    for _, s in stamps:
        assert datetime.fromisoformat(s.replace("Z", "+00:00")).utcoffset() == timedelta(0)  # dung la UTC


def test_alarm_and_command_timestamps_are_utc(client, populated):
    for a in client.get("/api/v1/alarms").json():
        for k in ("opened_at", "acked_at", "labeled_at"):
            assert TZ_SUFFIX.search(a[k]), k
    assert TZ_SUFFIX.search(client.get("/api/v1/commands").json()[0]["created_at"])


def test_utc_datetime_type_normalises_input_and_output(db):
    t = UTCDateTime()
    vn = timezone(timedelta(hours=7))
    aware_vn = datetime(2026, 1, 1, 19, 0, 0, tzinfo=vn)                    # 19:00 gio VN = 12:00 UTC
    assert t.process_bind_param(aware_vn, None) == datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert t.process_bind_param(datetime(2026, 1, 1, 12, 0), None).tzinfo == timezone.utc   # khong mui gio -> coi la UTC
    assert t.process_bind_param(None, None) is None and t.process_result_value(None, None) is None
    out = t.process_result_value(datetime(2026, 1, 1, 12, 0), None)          # SQLite tra ve khong mui gio
    assert out.tzinfo == timezone.utc and out.hour == 12
    assert t.process_result_value(aware_vn, None) == datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_roundtrip_through_database_keeps_instant_and_is_aware(db):
    vn = timezone(timedelta(hours=7))
    db.add(Device(device_id="tz-dev", last_seen=datetime(2026, 3, 5, 19, 30, tzinfo=vn)))
    db.commit()
    db.expire_all()
    got = db.scalar(select(Device).where(Device.device_id == "tz-dev")).last_seen
    assert got.tzinfo is not None and got == datetime(2026, 3, 5, 12, 30, tzinfo=timezone.utc)


def test_time_filters_still_work_with_aware_values(client, db):
    """Loc theo thoi gian (SQL) phai dung sau khi doi kieu cot: so sanh theo moc thoi gian that."""
    db.add(Device(device_id=DEV))
    db.add(Voyage(voyage_id="V-F", device_id=DEV, source_mode=SourceMode.SIMULATION, started_by="x"))
    base = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    db.add_all(Telemetry(
        device_id=DEV, boot_id="b", seq=i, t_sim_s=float(i), uptime_ms=1, source_mode=SourceMode.SIMULATION,
        voyage_id="V-F", roll_deg=0.0, pitch_deg=0.0, class_rf=MotionClass.NORMAL, alarm_level=AlarmLevel.NORMAL,
        model_version="m", config_version=1, sensor_ok=True, server_rx_time=base + timedelta(hours=i)) for i in range(5))
    db.commit()
    r = client.get("/api/v1/voyages/V-F/replay", params={"from_time": "2026-01-01T14:00:00+02:00"})  # = 12:00 UTC
    assert [t["seq"] for t in r.json()["telemetry"]] == [0, 1, 2, 3, 4]
    r = client.get("/api/v1/voyages/V-F/replay", params={"from_time": "2026-01-01T21:00:00+07:00"})  # = 14:00 UTC
    assert [t["seq"] for t in r.json()["telemetry"]] == [2, 3, 4]
