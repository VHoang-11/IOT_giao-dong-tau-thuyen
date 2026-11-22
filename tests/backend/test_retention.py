"""Don du lieu cu: mac dinh TAT; khi bat chi dong vao device_health va telemetry khong thuoc chuyen nao."""
from datetime import datetime, timedelta, timezone

import pytest
from conftest import NOAUTH
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.config import Settings, settings
from app.models import (
    Alarm, AlarmEvent, AuditLog, Command, Device, DeviceConfigVersion, DeviceHealth, Telemetry, Voyage,
)
from app.models.enums import AlarmLevel, MotionClass, SourceMode
from app.services import retention

NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
DEV = "vessel-demo-01"


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def health(i, age_days):
    return DeviceHealth(device_id=DEV, free_heap_bytes=1000 + i, uptime_ms=i, sensor_ok=True,
                        server_rx_time=NOW - timedelta(days=age_days, seconds=i))


def tele(i, age_days, voyage=None, boot="b1"):
    return Telemetry(device_id=DEV, boot_id=boot, seq=i, t_sim_s=float(i), uptime_ms=i, source_mode=SourceMode.SIMULATION,
                     voyage_id=voyage, roll_deg=1.0, pitch_deg=0.0, class_rf=MotionClass.NORMAL,
                     alarm_level=AlarmLevel.NORMAL, model_version="m", config_version=1, sensor_ok=True,
                     server_rx_time=NOW - timedelta(days=age_days, seconds=i))


@pytest.fixture()
def policy(monkeypatch):
    def set_(health_days=0, telemetry_days=0, batch=5000):
        monkeypatch.setattr(settings, "retention_health_days", health_days)
        monkeypatch.setattr(settings, "retention_telemetry_days", telemetry_days)
        monkeypatch.setattr(settings, "retention_batch", batch)
    return set_


# ---------------------------------------------------------------- mac dinh tat

def test_disabled_by_default_and_deletes_nothing(db):
    s = Settings()
    assert (s.retention_health_days, s.retention_telemetry_days) == (0, 0)
    assert retention.retention_enabled() is False
    db.add_all([health(1, 3650), tele(1, 3650)])
    db.commit()
    r = retention.purge_old(db, NOW)
    assert r == {"enabled": False, "deleted": {"device_health": 0, "telemetry_without_voyage": 0}, "cutoffs": {}}
    assert count(db, DeviceHealth) == 1 and count(db, Telemetry) == 1
    assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "RETENTION_PURGE")) == 0


@pytest.mark.parametrize("field", ["retention_health_days", "retention_telemetry_days"])
def test_negative_days_rejected(field):
    with pytest.raises(ValidationError):
        Settings(**{field: -1})


def test_interval_and_batch_have_sane_minimums():
    with pytest.raises(ValidationError):
        Settings(retention_interval_s=1)
    with pytest.raises(ValidationError):
        Settings(retention_batch=0)


# ---------------------------------------------------------------- device_health

def test_health_older_than_cutoff_deleted_recent_kept(db, policy):
    policy(health_days=30)
    db.add_all([health(1, 31), health(2, 90), health(3, 29), health(4, 0)])
    db.commit()
    r = retention.purge_old(db, NOW)
    assert r["deleted"]["device_health"] == 2 and count(db, DeviceHealth) == 2
    assert {h.free_heap_bytes for h in db.scalars(select(DeviceHealth))} == {1003, 1004}


def test_health_boundary_exactly_at_cutoff_is_kept(db, policy):
    policy(health_days=30)
    db.add(DeviceHealth(device_id=DEV, free_heap_bytes=1, uptime_ms=1, sensor_ok=True,
                        server_rx_time=NOW - timedelta(days=30)))
    db.commit()
    assert retention.purge_old(db, NOW)["deleted"]["device_health"] == 0       # dieu kien la '<' chat


# ---------------------------------------------------------------- telemetry: chi loai khong thuoc chuyen

def test_old_telemetry_without_voyage_deleted(db, policy):
    policy(telemetry_days=7)
    db.add_all([tele(1, 30), tele(2, 8), tele(3, 6), tele(4, 0)])
    db.commit()
    r = retention.purge_old(db, NOW)
    assert r["deleted"]["telemetry_without_voyage"] == 2
    assert sorted(t.seq for t in db.scalars(select(Telemetry))) == [3, 4]


def test_telemetry_belonging_to_a_voyage_is_NEVER_deleted_however_old(db, policy):
    policy(health_days=1, telemetry_days=1)
    db.add_all([tele(1, 3650, voyage="V-ACTIVE"), tele(2, 3650, voyage="V-ENDED"), tele(3, 3650, voyage=None)])
    db.commit()
    retention.purge_old(db, NOW)
    assert sorted(t.seq for t in db.scalars(select(Telemetry))) == [1, 2]          # chi mau khong co chuyen bi xoa


def test_only_the_configured_table_is_touched(db, policy):
    policy(health_days=30, telemetry_days=0)
    db.add_all([health(1, 90), tele(1, 90)])
    db.commit()
    retention.purge_old(db, NOW)
    assert count(db, DeviceHealth) == 0 and count(db, Telemetry) == 1
    policy(health_days=0, telemetry_days=30)
    db.add(health(2, 90))
    db.commit()
    retention.purge_old(db, NOW)
    assert count(db, DeviceHealth) == 1 and count(db, Telemetry) == 0


# ---------------------------------------------------------------- khong bao gio xoa

def test_never_deletes_alarms_commands_voyages_configs_audit(db, policy):
    policy(health_days=1, telemetry_days=1)
    old = NOW - timedelta(days=3650)
    db.add(Device(device_id=DEV))
    db.add_all([
        Alarm(alarm_id="A-1", boot_id="b", device_id=DEV, level=AlarmLevel.WARNING, max_level=AlarmLevel.WARNING,
              source_mode=SourceMode.SIMULATION, opened_at=old),
        AlarmEvent(device_id=DEV, boot_id="b", seq=1, alarm_id="A-1", level=AlarmLevel.WARNING, t_sim_s=1.0, server_rx_time=old),
        Command(cmd_id="c-1", device_id=DEV, cmd="calibrate_zero", ttl_s=30, issued_by="x", created_at=old),
        Voyage(voyage_id="V-1", device_id=DEV, source_mode=SourceMode.SIMULATION, started_by="x", started_at=old),
        DeviceConfigVersion(device_id=DEV, config_version=1, payload={"profile": "STANDARD"}, created_by="x", created_at=old),
        AuditLog(actor="x", action="OLD", ts=old),
        health(1, 3650), tele(1, 3650)])
    db.commit()
    audit_before = count(db, AuditLog)
    retention.purge_old(db, NOW)
    for model in (Alarm, AlarmEvent, Command, Voyage, DeviceConfigVersion, Device):
        assert count(db, model) == 1, model.__name__
    assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "OLD")) == 1   # audit cu con nguyen
    assert count(db, DeviceHealth) == 0 and count(db, Telemetry) == 0 and count(db, AuditLog) == audit_before + 1


# ---------------------------------------------------------------- lo nho + audit

def test_deletes_in_small_batches_and_commits_each(db, policy, monkeypatch):
    policy(telemetry_days=1, batch=3)
    db.add_all(tele(i, 30) for i in range(10))
    db.commit()
    commits = []
    real = db.commit
    monkeypatch.setattr(db, "commit", lambda: (commits.append(1), real())[1])
    assert retention.purge_old(db, NOW)["deleted"]["telemetry_without_voyage"] == 10
    assert count(db, Telemetry) == 0
    assert len(commits) >= 4 + 1                                                # >= 4 lo (3+3+3+1) + 1 audit


def test_batch_boundary_exact_multiple(db, policy):
    policy(telemetry_days=1, batch=5)
    db.add_all(tele(i, 30) for i in range(10))                                  # dung 2 lo day
    db.commit()
    assert retention.purge_old(db, NOW)["deleted"]["telemetry_without_voyage"] == 10


def test_purge_is_audited_with_counts_and_cutoffs_only_when_something_deleted(db, policy):
    policy(health_days=30)
    retention.purge_old(db, NOW)
    assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "RETENTION_PURGE")) == 0
    db.add(health(1, 60))
    db.commit()
    retention.purge_old(db, NOW)
    row = db.scalar(select(AuditLog).where(AuditLog.action == "RETENTION_PURGE"))
    assert row.actor == "system" and row.detail["deleted"]["device_health"] == 1
    assert "device_health" in row.detail["cutoffs"]


def test_running_twice_is_idempotent(db, policy):
    policy(health_days=30)
    db.add_all([health(1, 90), health(2, 1)])
    db.commit()
    assert retention.purge_old(db, NOW)["deleted"]["device_health"] == 1
    assert retention.purge_old(db, NOW)["deleted"]["device_health"] == 0
    assert count(db, DeviceHealth) == 1


# ---------------------------------------------------------------- API

def test_endpoints_admin_only(client, auth):
    for path, method in (("/api/v1/retention/status", "get"), ("/api/v1/retention/run", "post")):
        call = getattr(client, method)
        assert call(path, headers=NOAUTH).status_code == 401
        assert call(path, headers=auth("op01")).status_code == 403
        assert call(path).status_code == 403                                     # sup01
        assert call(path, headers=auth("admin01")).status_code == 200


def test_status_reports_policy_counts_and_protected_rows(client, db, policy, auth):
    policy(health_days=30, telemetry_days=7)
    db.add_all([health(1, 100), tele(1, 50), tele(2, 50, voyage="V-1")])
    db.commit()
    s = client.get("/api/v1/retention/status", headers=auth("admin01")).json()
    assert s["enabled"] is True
    assert s["policy"] == {"health_days": 30, "telemetry_without_voyage_days": 7, "interval_s": 3600, "batch": 5000}
    assert s["rows"] == {"device_health": 1, "telemetry": 2, "telemetry_without_voyage": 1, "telemetry_protected_by_voyage": 1}
    assert any("chuyến đi" in x for x in s["never_deleted"]) and any("kiểm toán" in x for x in s["never_deleted"])
    assert s["oldest"]["telemetry"].endswith(("Z", "+00:00"))


def test_status_when_disabled_shows_null_policy(client, auth):
    s = client.get("/api/v1/retention/status", headers=auth("admin01")).json()
    assert s["enabled"] is False and s["policy"]["health_days"] is None and s["policy"]["telemetry_without_voyage_days"] is None


def test_manual_run_when_disabled_deletes_nothing_and_is_audited(client, db, auth):
    db.add_all([health(1, 3650), tele(1, 3650)])
    db.commit()
    r = client.post("/api/v1/retention/run", headers=auth("admin01")).json()
    assert r["enabled"] is False and r["deleted"] == {"device_health": 0, "telemetry_without_voyage": 0}
    assert count(db, DeviceHealth) == 1 and count(db, Telemetry) == 1
    assert db.scalar(select(AuditLog).where(AuditLog.action == "RETENTION_RUN_MANUAL")).actor == "admin01"


def test_manual_run_applies_policy(client, db, policy, auth):
    policy(health_days=1)
    now = datetime.now(timezone.utc)
    db.add_all([DeviceHealth(device_id=DEV, free_heap_bytes=1, uptime_ms=1, sensor_ok=True, server_rx_time=now - timedelta(days=5)),
                DeviceHealth(device_id=DEV, free_heap_bytes=2, uptime_ms=2, sensor_ok=True, server_rx_time=now)])
    db.commit()
    r = client.post("/api/v1/retention/run", headers=auth("admin01")).json()
    assert r["enabled"] is True and r["deleted"]["device_health"] == 1 and count(db, DeviceHealth) == 1


def test_background_loop_only_started_when_enabled(policy):
    assert retention.retention_enabled() is False
    policy(health_days=1)
    assert retention.retention_enabled() is True
    policy(telemetry_days=1)
    assert retention.retention_enabled() is True
