"""Xu ly 1 ban tin MQTT: parse topic -> validate -> chong trung -> luu DB.

Ham thuan (khong phu thuoc broker) de test duoc. consumer.py goi ham nay.
"""
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alarms.service import apply_event
from app.models import AlarmEvent, Device, DeviceHealth, Telemetry
from app.models.enums import AlarmLevel, DeviceState, MotionClass, SourceMode
from ingest.validator import validate

log = logging.getLogger("svmg.ingest")

MAX_PAYLOAD_BYTES = 16 * 1024
TOPIC_RE = re.compile(r"^svmg/([A-Za-z0-9_.-]{1,64})/(telemetry|event|status|health|cmd/ack)$")
SUBSCRIPTIONS = [("svmg/+/telemetry", 0), ("svmg/+/event", 1), ("svmg/+/status", 1),
                 ("svmg/+/health", 0), ("svmg/+/cmd/ack", 1)]


class Outcome(str, Enum):
    STORED = "STORED"
    DUPLICATE = "DUPLICATE"
    INVALID = "INVALID"    # sai JSON / sai schema
    REJECTED = "REJECTED"  # device_id trong payload khac topic
    IGNORED = "IGNORED"    # topic khong xu ly o WP nay


@dataclass
class Result:
    outcome: Outcome
    kind: Optional[str] = None
    device_id: Optional[str] = None
    reason: Optional[str] = None


class Stats:
    """Bo dem don gian de do ti le ban tin nhan/trung/loi (T06, T14)."""
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def add(self, r: Result) -> None:
        k = f"{r.kind or 'unknown'}.{r.outcome.value}"
        self.counts[k] = self.counts.get(k, 0) + 1


stats = Stats()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_or_create_device(db: Session, device_id: str) -> Device:
    dev = db.scalar(select(Device).where(Device.device_id == device_id))
    if dev is None:
        dev = Device(device_id=device_id)
        db.add(dev)
        db.flush()
    return dev


def _commit_or_duplicate(db: Session) -> bool:
    """Commit; True neu thanh cong, False neu vi pham unique (ban tin trung)."""
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


def _dedup_exists(db: Session, model, device_id: str, boot_id: str, seq: int) -> bool:
    return db.scalar(select(model.id).where(
        model.device_id == device_id, model.boot_id == boot_id, model.seq == seq)) is not None


def _handle_telemetry(db: Session, dev_id: str, p: dict[str, Any], rx: datetime) -> Result:
    if _dedup_exists(db, Telemetry, dev_id, p["boot_id"], p["seq"]):
        return Result(Outcome.DUPLICATE, "telemetry", dev_id)
    dev = _get_or_create_device(db, dev_id)
    dev.last_seen = rx
    dev.source_mode = SourceMode(p["source_mode"])
    dev.model_version = p["model_version"]
    dev.config_version = p["config_version"]
    dev.boot_id = p["boot_id"]
    bb = p.get("class_baseline_b")
    db.add(Telemetry(
        device_id=dev_id, boot_id=p["boot_id"], seq=p["seq"], t_sim_s=p["t_sim_s"],
        uptime_ms=p["uptime_ms"], timewarp=p.get("timewarp", 1),
        source_mode=SourceMode(p["source_mode"]), synthetic=p.get("synthetic"),
        scenario_id=p.get("scenario_id"), voyage_id=p.get("voyage_id"),
        roll_deg=p["roll_deg"], pitch_deg=p["pitch_deg"], rms_roll_deg=p.get("rms_roll_deg"),
        heel_offset_deg=p.get("heel_offset_deg"), trend_rms_deg_per_min=p.get("trend_rms_deg_per_min"),
        class_rf=MotionClass(p["class_rf"]), class_baseline_b=MotionClass(bb) if bb else None,
        mai=p.get("mai"), alarm_level=AlarmLevel(p["alarm_level"]),
        model_version=p["model_version"], config_version=p["config_version"],
        sensor_ok=p["sensor_ok"], server_rx_time=rx))
    ok = _commit_or_duplicate(db)
    return Result(Outcome.STORED if ok else Outcome.DUPLICATE, "telemetry", dev_id)


def _handle_event(db: Session, dev_id: str, p: dict[str, Any], rx: datetime) -> Result:
    if _dedup_exists(db, AlarmEvent, dev_id, p["boot_id"], p["seq"]):
        return Result(Outcome.DUPLICATE, "event", dev_id)
    dev = _get_or_create_device(db, dev_id)
    dev.last_seen = rx
    prev, cls = p.get("prev_level"), p.get("class")
    ev = AlarmEvent(
        device_id=dev_id, boot_id=p["boot_id"], seq=p["seq"], alarm_id=p["alarm_id"],
        level=AlarmLevel(p["level"]), prev_level=AlarmLevel(prev) if prev else None,
        motion_class=MotionClass(cls) if cls else None, t_sim_s=p["t_sim_s"],
        acked_by=p.get("acked_by"), server_rx_time=rx)
    db.add(ev)
    if not _commit_or_duplicate(db):
        return Result(Outcome.DUPLICATE, "event", dev_id)
    try:
        apply_event(db, ev)  # M3-03: cap nhat vong doi canh bao (event tho da luu ben tren)
    except Exception:
        db.rollback()
        log.exception("apply_event failed", extra={"device_id": dev_id, "alarm_id": p["alarm_id"]})
    return Result(Outcome.STORED, "event", dev_id)


def _handle_status(db: Session, dev_id: str, p: dict[str, Any], rx: datetime) -> Result:
    dev = _get_or_create_device(db, dev_id)
    dev.state = DeviceState(p["state"])  # offline (LWT) cung di qua day
    dev.last_seen = rx
    for src, dst in (("fw", "fw"), ("model_version", "model_version"),
                     ("config_version", "config_version"), ("boot_id", "boot_id")):
        if src in p:
            setattr(dev, dst, p[src])
    db.commit()
    return Result(Outcome.STORED, "status", dev_id)


def _handle_health(db: Session, dev_id: str, p: dict[str, Any], rx: datetime) -> Result:
    dev = _get_or_create_device(db, dev_id)
    dev.last_seen = rx
    db.add(DeviceHealth(
        device_id=dev_id, free_heap_bytes=p["free_heap_bytes"],
        min_free_heap_bytes=p.get("min_free_heap_bytes"), uptime_ms=p["uptime_ms"],
        sensor_ok=p["sensor_ok"], i2c_errors=p.get("i2c_errors"), inference_ms=p.get("inference_ms"),
        mqtt_reconnects=p.get("mqtt_reconnects"), buffer_used=p.get("buffer_used"),
        buffer_capacity=p.get("buffer_capacity"), server_rx_time=rx))
    db.commit()
    return Result(Outcome.STORED, "health", dev_id)


_HANDLERS = {"telemetry": _handle_telemetry, "event": _handle_event,
             "status": _handle_status, "health": _handle_health}


def handle_message(db: Session, topic: str, payload: bytes, rx_time: Optional[datetime] = None) -> Result:
    """Xu ly 1 ban tin. Khong nem exception ra ngoai vi loi du lieu - tra ve Result."""
    rx = rx_time or _utcnow()  # luon gan server_rx_time
    result = _process(db, topic, payload, rx)
    stats.add(result)
    level = logging.INFO if result.outcome in (Outcome.STORED, Outcome.DUPLICATE, Outcome.IGNORED) else logging.WARNING
    log.log(level, "mqtt message", extra={"topic": topic, "device_id": result.device_id,
                                          "kind": result.kind, "outcome": result.outcome.value,
                                          "reason": result.reason})
    return result


def _process(db: Session, topic: str, payload: bytes, rx: datetime) -> Result:
    m = TOPIC_RE.match(topic)
    if not m:
        return Result(Outcome.INVALID, None, None, "topic khong thuoc svmg/{device_id}/...")
    dev_id, kind = m.group(1), m.group(2)
    if len(payload) > MAX_PAYLOAD_BYTES:
        return Result(Outcome.INVALID, kind, dev_id, "payload qua lon")
    try:
        data = json.loads(payload)
    except (UnicodeDecodeError, ValueError) as e:
        return Result(Outcome.INVALID, kind, dev_id, f"JSON loi: {e}")
    errs = validate(kind, data)
    if errs:
        return Result(Outcome.INVALID, kind, dev_id, "; ".join(errs[:5]))
    if "device_id" in data and data["device_id"] != dev_id:
        return Result(Outcome.REJECTED, kind, dev_id,
                      f"device_id payload '{data['device_id']}' khac topic '{dev_id}'")
    if kind == "cmd/ack":
        # TODO: M3-04 - cap nhat vong doi lenh (SENT -> APPLIED/REJECTED)
        return Result(Outcome.IGNORED, kind, dev_id, "xu ly o M3-04")
    return _HANDLERS[kind](db, dev_id, data, rx)
