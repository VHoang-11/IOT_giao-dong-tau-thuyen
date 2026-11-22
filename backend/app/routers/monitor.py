"""Monitor router (G6): GET /api/v1/monitor/agreement, /drift. Dang nhap la du (moi vai tro >= OPERATOR)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.db import get_db
from app.core.security import get_current_user
from app.schemas.monitor import AgreementStats, DriftStatus
from monitor.service import DeviceNotFound, get_agreement, get_drift

router = APIRouter(prefix="/api/v1/monitor", tags=["monitor"], dependencies=[Depends(get_current_user)])

_DEVICE = Query(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$", description="Mã thiết bị (bắt buộc)")


@router.get("/agreement", response_model=AgreementStats)
async def monitor_agreement(
    device_id: str = _DEVICE,
    voyage_id: Optional[str] = Query(None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$",
                                     description="Giới hạn theo một chuyến; bỏ trống = toàn bộ thiết bị"),
    limit: int = Query(1000, ge=1, le=10000, description="Lấy tối đa N mẫu gần nhất có đủ RF và Baseline"),
    db: Session = Depends(get_db),
) -> AgreementStats:
    """Tỉ lệ Random Forest trùng Baseline B. Đây là độ **nhất quán** giữa hai mô hình, không phải độ chính xác
    (không có nhãn thật) và không phải dự báo nguy hiểm. Mẫu `sensor_ok=false` bị loại và được đếm riêng.
    `agreement_rate = null` khi chưa có mẫu nào đủ điều kiện (không phải 0%)."""
    try:
        return await run_in_threadpool(get_agreement, db, device_id, voyage_id, limit)
    except DeviceNotFound as e:
        raise HTTPException(404, str(e))


@router.get("/drift", response_model=DriftStatus)
async def monitor_drift(
    device_id: str = _DEVICE,
    window_hours: int = Query(24, ge=1, le=168, description="Cửa sổ thời gian (giờ; mặc định 24, tối đa 168)"),
    db: Session = Depends(get_db),
) -> DriftStatus:
    """Drift PSI từng đặc trưng. **Hiện chưa khả dụng** (`available=false`, kèm `reason`): cần M2 cung cấp
    vector 14 đặc trưng và module `ml/monitor/`. Endpoint không bao giờ trả PSI giả."""
    try:
        return await run_in_threadpool(get_drift, db, device_id, window_hours)
    except DeviceNotFound as e:
        raise HTTPException(404, str(e))
