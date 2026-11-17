from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_user
from app.models import Device, DeviceHealth
from app.schemas.device_health import DeviceHealthOut, DeviceHealthSummary

router = APIRouter(tags=["health"], dependencies=[Depends(get_current_user)])


def _naive_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


@router.get("/api/v1/health/devices", response_model=list[DeviceHealthSummary])
async def fleet_health(db: Session = Depends(get_db)) -> list[DeviceHealthSummary]:
    """Tong quan suc khoe moi thiet bi: ban health moi nhat + co 'stale'."""
    latest_ids = select(func.max(DeviceHealth.id)).group_by(DeviceHealth.device_id)
    latest = {h.device_id: h for h in db.scalars(select(DeviceHealth).where(DeviceHealth.id.in_(latest_ids)))}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    out = []
    for d in db.scalars(select(Device).order_by(Device.device_id)):
        age = (now - _naive_utc(d.last_seen)).total_seconds() if d.last_seen else None
        h = latest.get(d.device_id)
        out.append(DeviceHealthSummary(
            device_id=d.device_id, state=d.state, source_mode=d.source_mode, last_seen=d.last_seen,
            seconds_since_seen=age, stale=age is None or age > settings.health_stale_s,
            latest=DeviceHealthOut.model_validate(h) if h else None))
    return out


@router.get("/api/v1/devices/{device_id}/health", response_model=list[DeviceHealthOut])
async def device_health_history(device_id: str, limit: int = Query(100, ge=1, le=1000),
                                db: Session = Depends(get_db)) -> list[DeviceHealth]:
    if db.scalar(select(Device.id).where(Device.device_id == device_id)) is None:
        raise HTTPException(404, f"Không tìm thấy thiết bị '{device_id}'")
    q = (select(DeviceHealth).where(DeviceHealth.device_id == device_id)
         .order_by(DeviceHealth.server_rx_time.desc(), DeviceHealth.id.desc()).limit(limit))
    return list(db.scalars(q))
