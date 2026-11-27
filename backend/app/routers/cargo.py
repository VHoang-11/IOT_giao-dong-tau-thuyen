"""Cảnh báo hầm hàng (Cargo Node): trạng thái chính thức, cảnh báo ACK/CLEARED, cấu hình hầm/ngưỡng.

Backend là nguồn xác định trạng thái; frontend chỉ hiển thị. Prototype hỗ trợ giám sát, chưa được chứng nhận SOLAS/IMO.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_actor, get_current_user, require_role
from app.models import CargoAlert, User
from app.models.enums import AlarmState, Role
from app.schemas.cargo_alert import CargoAlertOut, CargoConfigIn, CargoConfigOut, CargoStatusOut
from cargo import service
from cargo.thresholds import ConfigInvalid

router = APIRouter(tags=["cargo"], dependencies=[Depends(get_current_user)])


def _http(e: Exception) -> HTTPException:
    if isinstance(e, service.CargoNotFound):
        return HTTPException(404, str(e))
    if isinstance(e, ConfigInvalid):
        return HTTPException(422, str(e))
    return HTTPException(409, str(e))


@router.get("/api/v1/devices/{device_id}/cargo/status", response_model=CargoStatusOut)
async def cargo_status(device_id: str, db: Session = Depends(get_db)) -> dict:
    """Trạng thái chính thức từng chỉ số (nước mm, nhiệt độ, độ ẩm). Thiếu/cũ/lỗi dữ liệu ⇒ UNKNOWN kèm lý do, không bao giờ NORMAL."""
    try:
        return service.build_status(db, device_id)
    except service.CargoNotFound as e:
        raise _http(e)


@router.get("/api/v1/devices/{device_id}/cargo/alerts", response_model=list[CargoAlertOut])
async def cargo_alerts(device_id: str, state: Optional[AlarmState] = None, limit: int = Query(100, ge=1, le=1000),
                       db: Session = Depends(get_db)) -> list[CargoAlert]:
    try:
        return service.list_alerts(db, device_id, state, limit)
    except service.CargoNotFound as e:
        raise _http(e)


@router.post("/api/v1/cargo/alerts/{alert_id}/ack", response_model=CargoAlertOut)
async def ack_cargo_alert(alert_id: int, db: Session = Depends(get_db), actor: str = Depends(current_actor)) -> CargoAlert:
    """ACK ghi nhận người trực đã biết (OPERATOR trở lên). Không đồng nghĩa với giải tỏa: chỉ CLEARED khi chỉ số trở về NORMAL."""
    try:
        alert, _ = service.ack_alert(db, alert_id, actor)
    except (service.CargoNotFound, service.CargoConflict) as e:
        raise _http(e)
    return alert


@router.get("/api/v1/devices/{device_id}/cargo/config", response_model=CargoConfigOut)
async def get_cargo_config(device_id: str, db: Session = Depends(get_db)) -> dict:
    """Cấu hình hầm hàng + ngưỡng hiệu lực (kèm nguồn tham chiếu, đơn vị, phiên bản) và các trường còn thiếu."""
    try:
        nodes = service.cargo_nodes(db, device_id)
    except service.CargoNotFound as e:
        raise _http(e)
    if len(nodes) != 1:
        raise HTTPException(409, "Chỉ định đúng một Cargo Node (thiết bị chính không có hoặc có nhiều Cargo Node)")
    return service.config_view(db, nodes[0].device_id)


@router.put("/api/v1/devices/{device_id}/cargo/config", response_model=CargoConfigOut)
async def put_cargo_config(device_id: str, body: CargoConfigIn, db: Session = Depends(get_db),
                           user: User = Depends(require_role(Role.SUPERVISOR))) -> dict:
    """Đặt chiều sâu hầm, thang đo cảm biến nước, loại tàu/hàng, trạng thái hiệu chuẩn và (tuỳ chọn) ghi đè ngưỡng. SUPERVISOR trở lên."""
    try:
        nodes = service.cargo_nodes(db, device_id)
        if len(nodes) != 1:
            raise service.CargoConflict("Chỉ định đúng một Cargo Node (thiết bị chính không có hoặc có nhiều Cargo Node)")
        service.update_config(db, nodes[0], {k: getattr(body, k) for k in body.model_fields_set}, user.username)
    except (service.CargoNotFound, service.CargoConflict, ConfigInvalid) as e:
        raise _http(e)
    return service.config_view(db, nodes[0].device_id)
