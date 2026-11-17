from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import Device, Telemetry
from app.schemas.device import DeviceOut, TelemetryOut

# Xem du lieu: moi vai tro (OPERATOR tro len) deu duoc, nhung phai dang nhap.
router = APIRouter(prefix="/api/v1/devices", tags=["devices"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[DeviceOut])
async def list_devices(db: Session = Depends(get_db)) -> list[Device]:
    return list(db.scalars(select(Device).order_by(Device.device_id)))


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(device_id: str, db: Session = Depends(get_db)) -> Device:
    dev = db.scalar(select(Device).where(Device.device_id == device_id))
    if dev is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy thiết bị '{device_id}'")
    return dev


@router.get("/{device_id}/telemetry", response_model=list[TelemetryOut])
async def get_telemetry(
    device_id: str,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[Telemetry]:
    q = (select(Telemetry).where(Telemetry.device_id == device_id)
         .order_by(Telemetry.server_rx_time.desc(), Telemetry.id.desc()).limit(limit))
    return list(db.scalars(q))
