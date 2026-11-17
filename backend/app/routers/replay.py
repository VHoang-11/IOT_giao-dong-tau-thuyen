from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.db import get_db
from app.core.security import get_current_user
from app.schemas.replay import ReplayResponse
from app.schemas.voyage import VOYAGE_ID_PATTERN
from app.services import voyages as vsvc
from replay.service import Filters, ReplayError, build_replay

# Xem lai chuyen di: dang nhap la du (moi vai tro >= OPERATOR).
router = APIRouter(prefix="/api/v1/voyages", tags=["replay"], dependencies=[Depends(get_current_user)])


@router.get("/{voyage_id}/replay", response_model=ReplayResponse)
async def replay_voyage(
    voyage_id: str = Path(..., pattern=VOYAGE_ID_PATTERN),
    from_time: Optional[datetime] = Query(None, description="Giờ server (ISO 8601; thiếu múi giờ thì coi là UTC)"),
    to_time: Optional[datetime] = Query(None),
    from_t_sim: Optional[float] = Query(None, allow_inf_nan=False, description="Theo t_sim_s của thiết bị"),
    to_t_sim: Optional[float] = Query(None, allow_inf_nan=False),
    limit: int = Query(1000, ge=1, le=5000, description="Số mẫu telemetry mỗi trang"),
    cursor: Optional[str] = Query(None, max_length=200, description="next_cursor của trang trước"),
    db: Session = Depends(get_db),
) -> ReplayResponse:
    """Dữ liệu để phát lại một chuyến. Tốc độ ×1–×60 do giao diện tự xử lý.

    Sắp xếp theo (server_rx_time, id). Chọn MỘT trục lọc: from_time/to_time hoặc from_t_sim/to_t_sim.
    `truncated=true` nghĩa là còn trang sau: gọi lại với `cursor=next_cursor` (giữ nguyên các tham số lọc).
    """
    try:
        voyage = vsvc.get_voyage(db, voyage_id)
    except vsvc.VoyageNotFound as e:
        raise HTTPException(404, str(e))
    try:
        return await run_in_threadpool(build_replay, db, voyage,
                                       Filters(from_time, to_time, from_t_sim, to_t_sim), limit, cursor)
    except ReplayError as e:
        raise HTTPException(422, str(e))
