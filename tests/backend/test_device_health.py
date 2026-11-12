import json
from datetime import datetime, timedelta, timezone

from conftest import NOAUTH

from app.core.config import settings
from app.models import Device
from ingest.service import handle_message


def health(db, dev, **over):
    p = {"device_id": dev, "free_heap_bytes": 200000, "uptime_ms": 5000, "sensor_ok": True}
    p.update(over)
    handle_message(db, f"svmg/{dev}/health", json.dumps(p).encode())


def test_requires_login(client):
    assert client.get("/api/v1/health/devices", headers=NOAUTH).status_code == 401
    assert client.get("/api/v1/devices/x/health", headers=NOAUTH).status_code == 401


def test_fleet_health_stale_flags(client, db):
    now = datetime.now(timezone.utc)
    db.add_all([Device(device_id="fresh", last_seen=now),
                Device(device_id="old", last_seen=now - timedelta(seconds=settings.health_stale_s + 60)),
                Device(device_id="never")])
    db.commit()
    rows = {r["device_id"]: r for r in client.get("/api/v1/health/devices").json()}
    assert rows["fresh"]["stale"] is False and rows["fresh"]["seconds_since_seen"] < 5
    assert rows["old"]["stale"] is True
    assert rows["never"]["stale"] is True and rows["never"]["seconds_since_seen"] is None  # chua tung thay
    assert all(r["source_mode"] in ("SENSOR", "SIMULATION") for r in rows.values())


def test_fleet_health_returns_latest_per_device(client, db):
    health(db, "vessel-1", free_heap_bytes=100000, uptime_ms=1000)
    health(db, "vessel-1", free_heap_bytes=90000, uptime_ms=31000, sensor_ok=False, i2c_errors=3)
    health(db, "vessel-2", free_heap_bytes=150000, buffer_used=50, buffer_capacity=200)
    rows = {r["device_id"]: r for r in client.get("/api/v1/health/devices").json()}
    assert rows["vessel-1"]["latest"]["free_heap_bytes"] == 90000      # ban moi nhat
    assert rows["vessel-1"]["latest"]["sensor_ok"] is False and rows["vessel-1"]["latest"]["i2c_errors"] == 3
    assert rows["vessel-2"]["latest"]["buffer_used_pct"] == 25.0
    assert rows["vessel-1"]["latest"]["buffer_used_pct"] is None        # thieu du lieu -> None, khong doan


def test_device_without_health_has_no_latest(client, db):
    db.add(Device(device_id="quiet", last_seen=datetime.now(timezone.utc)))
    db.commit()
    row = [r for r in client.get("/api/v1/health/devices").json() if r["device_id"] == "quiet"][0]
    assert row["latest"] is None and row["stale"] is False


def test_health_history_order_limit_and_404(client, db):
    for i in range(5):
        health(db, "vessel-1", uptime_ms=i * 30000)
    rows = client.get("/api/v1/devices/vessel-1/health?limit=3").json()
    assert [r["uptime_ms"] for r in rows] == [120000, 90000, 60000]     # moi nhat truoc
    assert client.get("/api/v1/devices/vessel-1/health?limit=0").status_code == 422
    assert client.get("/api/v1/devices/ghost/health").status_code == 404
