"""CSDL SVMG (M3-01). Thoi gian luu UTC. Moi du lieu do deu mang source_mode."""
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import (
    AlarmLevel, AlarmState, CommandState, DeviceState, MotionClass, Role, SourceMode, VoyageStatus,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _enum(e):
    return Enum(e, native_enum=False, length=32, validate_strings=True)


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(128))
    source_mode: Mapped[SourceMode] = mapped_column(_enum(SourceMode), default=SourceMode.SIMULATION)
    state: Mapped[DeviceState] = mapped_column(_enum(DeviceState), default=DeviceState.offline)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fw: Mapped[Optional[str]] = mapped_column(String(32))
    boot_id: Mapped[Optional[str]] = mapped_column(String(64))
    model_version: Mapped[Optional[str]] = mapped_column(String(32))
    config_version: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Telemetry(Base):
    __tablename__ = "telemetry"
    __table_args__ = (
        UniqueConstraint("device_id", "boot_id", "seq", name="uq_telemetry_dedup"),
        Index("ix_telemetry_dev_rx", "device_id", "server_rx_time"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    boot_id: Mapped[str] = mapped_column(String(64))
    seq: Mapped[int] = mapped_column(Integer)
    t_sim_s: Mapped[float] = mapped_column(Float)
    uptime_ms: Mapped[int] = mapped_column(Integer)
    timewarp: Mapped[int] = mapped_column(Integer, default=1)
    source_mode: Mapped[SourceMode] = mapped_column(_enum(SourceMode))
    synthetic: Mapped[Optional[bool]] = mapped_column(Boolean)
    scenario_id: Mapped[Optional[str]] = mapped_column(String(32))
    voyage_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    roll_deg: Mapped[float] = mapped_column(Float)
    pitch_deg: Mapped[float] = mapped_column(Float)
    rms_roll_deg: Mapped[Optional[float]] = mapped_column(Float)
    heel_offset_deg: Mapped[Optional[float]] = mapped_column(Float)
    trend_rms_deg_per_min: Mapped[Optional[float]] = mapped_column(Float)
    class_rf: Mapped[MotionClass] = mapped_column(_enum(MotionClass))
    class_baseline_b: Mapped[Optional[MotionClass]] = mapped_column(_enum(MotionClass))
    mai: Mapped[Optional[int]] = mapped_column(Integer)
    alarm_level: Mapped[AlarmLevel] = mapped_column(_enum(AlarmLevel))
    model_version: Mapped[str] = mapped_column(String(32))
    config_version: Mapped[int] = mapped_column(Integer)
    sensor_ok: Mapped[bool] = mapped_column(Boolean)
    server_rx_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AlarmEvent(Base):
    """Ban tin `event` tho tu thiet bi (ALARM_STATE)."""
    __tablename__ = "alarm_events"
    __table_args__ = (UniqueConstraint("device_id", "boot_id", "seq", name="uq_event_dedup"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    boot_id: Mapped[str] = mapped_column(String(64))
    seq: Mapped[int] = mapped_column(Integer)
    alarm_id: Mapped[str] = mapped_column(String(64), index=True)
    level: Mapped[AlarmLevel] = mapped_column(_enum(AlarmLevel))
    prev_level: Mapped[Optional[AlarmLevel]] = mapped_column(_enum(AlarmLevel))
    motion_class: Mapped[Optional[MotionClass]] = mapped_column(_enum(MotionClass))
    t_sim_s: Mapped[float] = mapped_column(Float)
    acked_by: Mapped[Optional[str]] = mapped_column(String(64))
    server_rx_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Alarm(Base):
    """Vong doi canh bao phia server (M3-03): ACK, leo thang, giai toa, MTTA."""
    __tablename__ = "alarms"
    # alarm_id do thiet bi tu sinh (A-0001...), co the trung giua cac tau/lan khoi dong
    # -> dinh danh that la (device_id, boot_id, alarm_id).
    __table_args__ = (UniqueConstraint("device_id", "boot_id", "alarm_id", name="uq_alarm_identity"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    alarm_id: Mapped[str] = mapped_column(String(64), index=True)
    boot_id: Mapped[str] = mapped_column(String(64))
    last_seq: Mapped[int] = mapped_column(Integer, default=-1)  # seq event moi nhat da ap dung
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    voyage_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    state: Mapped[AlarmState] = mapped_column(_enum(AlarmState), default=AlarmState.ACTIVE)
    level: Mapped[AlarmLevel] = mapped_column(_enum(AlarmLevel))
    max_level: Mapped[AlarmLevel] = mapped_column(_enum(AlarmLevel))
    motion_class: Mapped[Optional[MotionClass]] = mapped_column(_enum(MotionClass))
    source_mode: Mapped[SourceMode] = mapped_column(_enum(SourceMode))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    acked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    acked_by: Mapped[Optional[str]] = mapped_column(String(64))
    cleared_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    label: Mapped[Optional[str]] = mapped_column(String(16))  # AlarmLabel: dung/sai/chua ro (G4)
    labeled_by: Mapped[Optional[str]] = mapped_column(String(64))
    labeled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Command(Base):
    __tablename__ = "commands"
    id: Mapped[int] = mapped_column(primary_key=True)
    cmd_id: Mapped[str] = mapped_column(String(64), unique=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    cmd: Mapped[str] = mapped_column(String(32))
    params: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    ttl_s: Mapped[int] = mapped_column(Integer)
    issued_by: Mapped[str] = mapped_column(String(64))
    state: Mapped[CommandState] = mapped_column(_enum(CommandState), default=CommandState.SENT)
    reason: Mapped[Optional[str]] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class DeviceConfigVersion(Base):
    __tablename__ = "device_configs"
    __table_args__ = (UniqueConstraint("device_id", "config_version", name="uq_cfg_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    config_version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    applied: Mapped[bool] = mapped_column(Boolean, default=False)


class DeviceHealth(Base):
    __tablename__ = "device_health"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    free_heap_bytes: Mapped[int] = mapped_column(Integer)
    min_free_heap_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    uptime_ms: Mapped[int] = mapped_column(Integer)
    sensor_ok: Mapped[bool] = mapped_column(Boolean)
    i2c_errors: Mapped[Optional[int]] = mapped_column(Integer)
    inference_ms: Mapped[Optional[float]] = mapped_column(Float)
    mqtt_reconnects: Mapped[Optional[int]] = mapped_column(Integer)
    buffer_used: Mapped[Optional[int]] = mapped_column(Integer)
    buffer_capacity: Mapped[Optional[int]] = mapped_column(Integer)
    server_rx_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[Role] = mapped_column(_enum(Role), default=Role.OPERATOR)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Voyage(Base):
    __tablename__ = "voyages"
    __table_args__ = (
        # DB tu chan: moi thiet bi chi co TOI DA 1 chuyen dang chay (khong chi dua vao code kiem tra, vi code bi race)
        Index("uq_voyage_one_active_per_device", "device_id", unique=True,
              sqlite_where=text("status = 'ACTIVE'"), postgresql_where=text("status = 'ACTIVE'")),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    voyage_id: Mapped[str] = mapped_column(String(64), unique=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    source_mode: Mapped[SourceMode] = mapped_column(_enum(SourceMode))
    status: Mapped[VoyageStatus] = mapped_column(_enum(VoyageStatus), default=VoyageStatus.ACTIVE)
    started_by: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ended_by: Mapped[Optional[str]] = mapped_column(String(64))


class AuditLog(Base):
    """Nhat ky kiem toan: ai lam gi luc nao. Chi them, khong sua/xoa."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[Optional[str]] = mapped_column(String(128))
    detail: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
