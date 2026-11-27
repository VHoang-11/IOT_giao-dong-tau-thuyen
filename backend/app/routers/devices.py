from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user, require_role
from app.models import CargoTelemetry, Device, Telemetry, User
from app.models.enums import NodeType, Role
from app.schemas.device import CargoOut, DeviceCreate, DeviceOut, DeviceUpdate, TelemetryOut
from app.services.audit import audit

# Xem du lieu: moi vai tro (OPERATOR tro len) deu duoc, nhung phai dang nhap.
router = APIRouter(prefix="/api/v1/devices", tags=["devices"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[DeviceOut])
async def list_devices(db: Session = Depends(get_db)) -> list[Device]:
    return list(db.scalars(select(Device).order_by(Device.device_id)))


def _check_parent(db: Session, device_id: str, parent_id: str) -> None:
    """Cargo Node chi duoc gan vao mot Motion Node (tau chinh) da ton tai; khong lien ket vong, khong xich nhieu cap."""
    if parent_id == device_id:
        raise HTTPException(status_code=422, detail="parent_device_id không được trùng chính thiết bị")
    parent = db.scalar(select(Device).where(Device.device_id == parent_id))
    if parent is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy thiết bị chính '{parent_id}'")
    if parent.node_type != NodeType.MOTION:
        raise HTTPException(status_code=409, detail=f"'{parent_id}' là Cargo Node, không thể làm thiết bị chính")


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
    if body.parent_device_id is not None:
        _check_parent(db, body.device_id, body.parent_device_id)
    dev = Device(device_id=body.device_id, name=body.name, source_mode=body.source_mode,
                 node_type=body.node_type, parent_device_id=body.parent_device_id)
    db.add(dev)
    detail = {"name": body.name, "source_mode": body.source_mode.value}
    if body.node_type == NodeType.CARGO:   # giu nguyen dinh dang cu cho thiet bi thuong
        detail.update(node_type=body.node_type.value, parent_device_id=body.parent_device_id)
    audit(db, admin.username, "DEVICE_REGISTER", body.device_id, detail)
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
    if "parent_device_id" in body.model_fields_set and body.parent_device_id != dev.parent_device_id:
        if body.parent_device_id is not None:
            _check_parent(db, device_id, body.parent_device_id)
            if db.scalar(select(Device.id).where(Device.parent_device_id == device_id)) is not None:
                raise HTTPException(status_code=409,
                                    detail=f"'{device_id}' đang là thiết bị chính của Cargo Node khác, không thể gán làm Cargo Node")
            if dev.node_type != NodeType.CARGO:
                changes["node_type"] = [dev.node_type.value, NodeType.CARGO.value]
                dev.node_type = NodeType.CARGO   # gan vao tau chinh nghia la Cargo Node
        changes["parent_device_id"] = [dev.parent_device_id, body.parent_device_id]
        dev.parent_device_id = body.parent_device_id
    if changes:
        audit(db, admin.username, "DEVICE_UPDATE", device_id, changes)
        db.commit()
    return dev


@router.get("/{device_id}/cargo", response_model=list[CargoOut])
async def get_cargo(
    device_id: str,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[CargoTelemetry]:
    """Du lieu ham hang (moi nhat truoc). `device_id` la tau chinh (gop moi Cargo Node gan vao no theo
    `parent_device_id`) hoac chinh Cargo Node. Gia tri khong doc duoc la null (khong phai 0)."""
    dev = db.scalar(select(Device).where(Device.device_id == device_id))
    if dev is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy thiết bị '{device_id}'")
    if dev.node_type == NodeType.CARGO:
        ids = [dev.device_id]
    else:
        ids = list(db.scalars(select(Device.device_id).where(Device.parent_device_id == device_id,
                                                           Device.node_type == NodeType.CARGO)))
    if not ids:
        return []
    q = (select(CargoTelemetry).where(CargoTelemetry.device_id.in_(ids))
         .order_by(CargoTelemetry.server_rx_time.desc(), CargoTelemetry.id.desc()).limit(limit))
    return list(db.scalars(q))


@router.get("/{device_id}/telemetry", response_model=list[TelemetryOut])
async def get_telemetry(
    device_id: str,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[Telemetry]:
    q = (select(Telemetry).where(Telemetry.device_id == device_id)
         .order_by(Telemetry.server_rx_time.desc(), Telemetry.id.desc()).limit(limit))
    return list(db.scalars(q))
