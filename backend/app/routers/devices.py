from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user, require_role
from app.models import Device, Telemetry, User
from app.models.enums import Role
from app.schemas.device import DeviceCreate, DeviceOut, DeviceUpdate, TelemetryOut
from app.services.audit import audit

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


@router.post("", response_model=DeviceOut, status_code=201)
async def register_device(body: DeviceCreate, db: Session = Depends(get_db),
                          admin: User = Depends(require_role(Role.ADMIN))) -> Device:
    """Đăng ký thiết bị trước khi nó gửi bản tin đầu tiên (Admin). Bắt buộc nêu rõ SENSOR hay SIMULATION."""
    if db.scalar(select(Device.id).where(Device.device_id == body.device_id)) is not None:
        raise HTTPException(status_code=409, detail=f"Thiết bị '{body.device_id}' đã tồn tại")
    dev = Device(device_id=body.device_id, name=body.name, source_mode=body.source_mode)
    db.add(dev)
    audit(db, admin.username, "DEVICE_REGISTER", body.device_id,
          {"name": body.name, "source_mode": body.source_mode.value})
    try:
        db.commit()
    except IntegrityError:  # hai Admin dang ky cung luc
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Thiết bị '{body.device_id}' đã tồn tại") from None
    return dev


@router.patch("/{device_id}", response_model=DeviceOut)
async def update_device(device_id: str, body: DeviceUpdate, db: Session = Depends(get_db),
                        admin: User = Depends(require_role(Role.ADMIN))) -> Device:
    """Đặt tên / bật-tắt thiết bị (Admin). Tắt (`enabled=false`): bản tin bị từ chối, không nhận lệnh, cấu hình,
    chuyến mới. KHÔNG xóa thiết bị để giữ lịch sử và báo cáo."""
    dev = db.scalar(select(Device).where(Device.device_id == device_id))
    if dev is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy thiết bị '{device_id}'")
    changes: dict = {}
    if "name" in body.model_fields_set and body.name != dev.name:
        changes["name"] = [dev.name, body.name]
        dev.name = body.name
    if "enabled" in body.model_fields_set:
        if body.enabled is None:
            raise HTTPException(status_code=422, detail="enabled phải là true hoặc false")
        if body.enabled != dev.enabled:
            changes["enabled"] = [dev.enabled, body.enabled]
            dev.enabled = body.enabled
    if changes:
        audit(db, admin.username, "DEVICE_UPDATE", device_id, changes)
        db.commit()
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
