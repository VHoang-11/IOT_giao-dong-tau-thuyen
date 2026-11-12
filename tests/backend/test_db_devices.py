import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Device, Telemetry
from app.models.enums import AlarmLevel, MotionClass, SourceMode


def _tele(**kw):
    base = dict(device_id="vessel-demo-01", boot_id="b1", seq=1, t_sim_s=1.0, uptime_ms=1000,
                source_mode=SourceMode.SIMULATION, roll_deg=1.5, pitch_deg=0.2,
                class_rf=MotionClass.NORMAL, alarm_level=AlarmLevel.NORMAL,
                model_version="rf-0", config_version=1, sensor_ok=True)
    base.update(kw)
    return Telemetry(**base)


def test_list_and_get_device(client, db):
    db.add(Device(device_id="vessel-demo-01"))
    db.commit()
    assert [d["device_id"] for d in client.get("/api/v1/devices").json()] == ["vessel-demo-01"]
    assert client.get("/api/v1/devices/vessel-demo-01").json()["source_mode"] == "SIMULATION"
    assert client.get("/api/v1/devices/none").status_code == 404


def test_telemetry_endpoint_exposes_source_mode(client, db):
    db.add_all([_tele(seq=1), _tele(seq=2)])
    db.commit()
    rows = client.get("/api/v1/devices/vessel-demo-01/telemetry?limit=1").json()
    assert len(rows) == 1 and rows[0]["source_mode"] == "SIMULATION"
    assert client.get("/api/v1/devices/x/telemetry?limit=0").status_code == 422


def test_dedup_unique_key(db):
    db.add(_tele())
    db.commit()
    db.add(_tele())  # cung (device_id, boot_id, seq)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(_tele(boot_id="b2"))  # boot_id moi -> hop le
    db.commit()
