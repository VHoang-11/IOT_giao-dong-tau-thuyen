"""Don du lieu cu (retention). MAC DINH TAT (0 ngay = giu mai).

AN TOAN - chi dong vao:
  * device_health cu hon RETENTION_HEALTH_DAYS
  * telemetry KHONG thuoc chuyen nao (voyage_id IS NULL) cu hon RETENTION_TELEMETRY_DAYS
KHONG BAO GIO xoa: telemetry co voyage_id (nguon cua bao cao/replay/T11/T15), canh bao, su kien canh bao, lenh,
cau hinh, chuyen di, nhat ky kiem toan.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import DeviceHealth, Telemetry
from app.services.audit import audit

log = logging.getLogger("svmg.retention")
SYSTEM_ACTOR = "system"


def retention_enabled() -> bool:
    return settings.retention_health_days > 0 or settings.retention_telemetry_days > 0


def _delete_in_batches(db: Session, model, condition) -> int:
    """Xoa tung lo nho va commit tung lo: khong giu khoa DB lau, ban tin MQTT van ghi xen ke duoc."""
    total = 0
    while True:
        ids = select(model.id).where(condition).limit(settings.retention_batch)
        n = db.execute(delete(model).where(model.id.in_(ids))).rowcount or 0
        db.commit()
        total += n
        if n < settings.retention_batch:
            return total


def purge_old(db: Session, now: Optional[datetime] = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    deleted = {"device_health": 0, "telemetry_without_voyage": 0}
    cutoffs: dict[str, str] = {}
    if settings.retention_health_days > 0:
        cut = now - timedelta(days=settings.retention_health_days)
        cutoffs["device_health"] = cut.isoformat()
        deleted["device_health"] = _delete_in_batches(db, DeviceHealth, DeviceHealth.server_rx_time < cut)
    if settings.retention_telemetry_days > 0:
        cut = now - timedelta(days=settings.retention_telemetry_days)
        cutoffs["telemetry_without_voyage"] = cut.isoformat()
        deleted["telemetry_without_voyage"] = _delete_in_batches(
            db, Telemetry, (Telemetry.server_rx_time < cut) & Telemetry.voyage_id.is_(None))
    if any(deleted.values()):
        audit(db, SYSTEM_ACTOR, "RETENTION_PURGE", None, {"deleted": deleted, "cutoffs": cutoffs})
        db.commit()
        log.info("retention purge", extra={"deleted": deleted})
    return {"enabled": retention_enabled(), "deleted": deleted, "cutoffs": cutoffs}


def status(db: Session) -> dict[str, Any]:
    def count(model, *cond):
        return db.scalar(select(func.count()).select_from(model).where(*cond)) or 0

    return {
        "enabled": retention_enabled(),
        "policy": {"health_days": settings.retention_health_days or None,
                   "telemetry_without_voyage_days": settings.retention_telemetry_days or None,
                   "interval_s": settings.retention_interval_s, "batch": settings.retention_batch},
        "rows": {"device_health": count(DeviceHealth), "telemetry": count(Telemetry),
                 "telemetry_without_voyage": count(Telemetry, Telemetry.voyage_id.is_(None)),
                 "telemetry_protected_by_voyage": count(Telemetry, Telemetry.voyage_id.is_not(None))},
        "oldest": {"device_health": db.scalar(select(func.min(DeviceHealth.server_rx_time))),
                   "telemetry": db.scalar(select(func.min(Telemetry.server_rx_time)))},
        "never_deleted": ["telemetry thuộc chuyến đi", "cảnh báo và sự kiện cảnh báo", "lệnh", "cấu hình",
                          "chuyến đi", "nhật ký kiểm toán"],
    }
