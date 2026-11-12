"""Cau hinh thiet bi co phien ban + rollback (G3).

Quy tac cua hop dong: thiet bi CHI ap dung config_version > hien tai.
=> Rollback khong 'lui' so phien ban: no tao phien ban MOI (so lon hon) mang noi dung cua ban cu.
"""
import binascii
import json
import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Device, DeviceConfigVersion
from app.services.audit import audit
from commands.params import CommandInvalid
from commands.publisher import PublishFailed, get_publisher
from ingest.validator import validate

log = logging.getLogger("svmg.config")

DEFAULT_CONFIG: dict[str, Any] = {
    "profile": "STANDARD", "debounce_n": 3, "phi_hard_deg": 20.0,
    "mai_caution": 70, "report_interval_s": 5, "primary_model": "RF",
}


class DeviceNotFound(Exception):
    pass


class ConfigConflict(Exception):
    pass


def compute_crc(payload: dict[str, Any]) -> str:
    """CRC-16/CCITT-FALSE tren JSON chuan hoa (khoa sap xep, khong khoang trang, bo truong crc).
    TODO: thong nhat thuat toan voi M1 (firmware) - hop dong moi cho vi du 4 ky tu hex."""
    body = {k: v for k, v in payload.items() if k != "crc"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return f"{binascii.crc_hqx(canon, 0xFFFF):04x}"


def config_topic(device_id: str) -> str:
    return f"svmg/{device_id}/config"


def history(db: Session, device_id: str) -> list[DeviceConfigVersion]:
    return list(db.scalars(select(DeviceConfigVersion)
                           .where(DeviceConfigVersion.device_id == device_id)
                           .order_by(DeviceConfigVersion.config_version.desc())))


def _device(db: Session, device_id: str) -> Device:
    dev = db.scalar(select(Device).where(Device.device_id == device_id))
    if dev is None:
        raise DeviceNotFound(f"Không tìm thấy thiết bị '{device_id}'")
    return dev


def _publish_new_version(db: Session, dev: Device, body: dict[str, Any], actor: str,
                         action: str, detail: dict[str, Any]) -> DeviceConfigVersion:
    existing = history(db, dev.device_id)
    # so phien ban phai vuot ca ban server da tao lan ban thiet bi dang bao cao
    version = max([r.config_version for r in existing] + [dev.config_version or 0]) + 1
    payload = {**body, "config_version": version}
    payload["crc"] = compute_crc(payload)
    errs = validate("config", payload)
    if errs:
        raise CommandInvalid("Cấu hình không hợp lệ: " + "; ".join(errs[:3]))
    row = DeviceConfigVersion(device_id=dev.device_id, config_version=version, payload=payload,
                              created_by=actor, applied=False)
    db.add(row)
    audit(db, actor, action, f"{dev.device_id}:v{version}", detail)
    db.flush()
    try:
        # retained: thiet bi ket noi lai van nhan duoc cau hinh moi nhat
        get_publisher().publish(config_topic(dev.device_id), json.dumps(payload), qos=1, retain=True)
    except PublishFailed:
        db.rollback()
        raise
    db.commit()
    log.info("config published", extra={"device_id": dev.device_id, "config_version": version})
    return row


def update_config(db: Session, device_id: str, changes: dict[str, Any], actor: str) -> DeviceConfigVersion:
    dev = _device(db, device_id)
    existing = history(db, device_id)
    base = {k: v for k, v in (existing[0].payload if existing else DEFAULT_CONFIG).items()
            if k not in ("config_version", "crc")}
    return _publish_new_version(db, dev, {**base, **changes}, actor, "CONFIG_UPDATE",
                                {"changes": changes})


def rollback_config(db: Session, device_id: str, actor: str,
                    to_version: Optional[int] = None) -> DeviceConfigVersion:
    dev = _device(db, device_id)
    existing = history(db, device_id)  # moi nhat truoc
    if not existing:
        raise ConfigConflict("Thiết bị chưa có phiên bản cấu hình nào")
    if to_version is None:
        if len(existing) < 2:
            raise ConfigConflict("Không có phiên bản trước để rollback")
        target = existing[1]
    else:
        target = next((r for r in existing if r.config_version == to_version), None)
        if target is None:
            raise ConfigConflict(f"Không có cấu hình phiên bản {to_version}")
        if target.config_version == existing[0].config_version:
            raise ConfigConflict("Phiên bản này đang là bản mới nhất")
    body = {k: v for k, v in target.payload.items() if k not in ("config_version", "crc")}
    return _publish_new_version(db, dev, body, actor, "CONFIG_ROLLBACK",
                                {"from_version": existing[0].config_version,
                                 "restored_from_version": target.config_version})


def mark_applied(db: Session, device_id: str, version: Optional[int]) -> None:
    """Thiet bi bao dang dung config_version nay (qua ACK hoac status) -> danh dau da ap dung."""
    if version is None:
        return
    row = db.scalar(select(DeviceConfigVersion).where(
        DeviceConfigVersion.device_id == device_id, DeviceConfigVersion.config_version == version))
    if row is not None and not row.applied:
        row.applied = True
        db.commit()
