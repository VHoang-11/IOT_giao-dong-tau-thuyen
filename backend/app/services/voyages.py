"""Vong doi chuyen di (G4). Tach khoi lenh start_voyage: chuyen di la ban ghi trong backend,
bao cao gom telemetry theo truong voyage_id co san trong hop dong."""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Device, Voyage
from app.models.enums import VoyageStatus
from app.services.audit import audit

log = logging.getLogger("svmg.voyages")


class VoyageNotFound(Exception):
    pass


class VoyageConflict(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_voyage(db: Session, voyage_id: str) -> Voyage:
    v = db.scalar(select(Voyage).where(Voyage.voyage_id == voyage_id))
    if v is None:
        raise VoyageNotFound(f"Không tìm thấy chuyến đi '{voyage_id}'")
    return v


def _active_voyage(db: Session, device_id: str) -> Optional[Voyage]:
    return db.scalar(select(Voyage).where(Voyage.device_id == device_id, Voyage.status == VoyageStatus.ACTIVE))


def _next_voyage_id(db: Session, now: datetime) -> str:
    """V-YYYY-NNN theo so chuyen da co trong nam (mau theo vi du trong hop dong); trung thi tang tiep."""
    prefix = f"V-{now.year}-"
    n = (db.scalar(select(func.count()).select_from(Voyage).where(Voyage.voyage_id.like(prefix + "%"))) or 0) + 1
    while db.scalar(select(Voyage.id).where(Voyage.voyage_id == f"{prefix}{n:03d}")) is not None:
        n += 1
    return f"{prefix}{n:03d}"


def start_voyage(db: Session, actor: str, device_id: str, voyage_id: Optional[str] = None,
                 now: Optional[datetime] = None) -> Voyage:
    now = now or _now()
    dev = db.scalar(select(Device).where(Device.device_id == device_id))
    if dev is None:
        raise VoyageNotFound(f"Không tìm thấy thiết bị '{device_id}'")
    active = _active_voyage(db, device_id)
    if active is not None:
        raise VoyageConflict(f"Thiết bị '{device_id}' đang có chuyến '{active.voyage_id}' chưa kết thúc")
    if voyage_id and db.scalar(select(Voyage.id).where(Voyage.voyage_id == voyage_id)) is not None:
        raise VoyageConflict(f"Mã chuyến '{voyage_id}' đã tồn tại")
    v = Voyage(voyage_id=voyage_id or _next_voyage_id(db, now), device_id=device_id, source_mode=dev.source_mode,
               status=VoyageStatus.ACTIVE, started_by=actor, started_at=now)
    db.add(v)
    audit(db, actor, "VOYAGE_START", v.voyage_id, {"device_id": device_id})
    try:
        db.commit()
    except IntegrityError:
        # hai request cung luc: chi muc duy nhat 'moi thiet bi 1 chuyen ACTIVE' (hoac voyage_id) chan nguoi den sau
        db.rollback()
        raise VoyageConflict("Có thay đổi đồng thời (thiết bị đã có chuyến đang chạy hoặc mã chuyến bị trùng), vui lòng thử lại") from None
    log.info("voyage started", extra={"device_id": device_id, "voyage_id": v.voyage_id})
    return v


def end_voyage(db: Session, actor: str, voyage_id: str, now: Optional[datetime] = None) -> Voyage:
    v = get_voyage(db, voyage_id)
    if v.status == VoyageStatus.ENDED:
        raise VoyageConflict(f"Chuyến '{voyage_id}' đã kết thúc")
    v.status, v.ended_at, v.ended_by = VoyageStatus.ENDED, now or _now(), actor
    audit(db, actor, "VOYAGE_END", v.voyage_id, {"device_id": v.device_id})
    db.commit()
    log.info("voyage ended", extra={"device_id": v.device_id, "voyage_id": v.voyage_id})
    return v
