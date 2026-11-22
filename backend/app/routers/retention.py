from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.db import get_db
from app.core.security import require_role
from app.models import User
from app.models.enums import Role
from app.services import retention
from app.services.audit import audit

router = APIRouter(prefix="/api/v1/retention", tags=["retention"], dependencies=[Depends(require_role(Role.ADMIN))])


class RetentionPolicy(BaseModel):
    health_days: Optional[int] = None                    # None = giu mai
    telemetry_without_voyage_days: Optional[int] = None
    interval_s: int
    batch: int


class RetentionStatus(BaseModel):
    enabled: bool
    policy: RetentionPolicy
    rows: dict[str, int]
    oldest: dict[str, Optional[datetime]]
    never_deleted: list[str]


class RetentionRun(BaseModel):
    enabled: bool
    deleted: dict[str, int]
    cutoffs: dict[str, str]


@router.get("/status", response_model=RetentionStatus)
async def retention_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Chính sách dọn dữ liệu đang áp dụng (mặc định TẮT) và số dòng hiện có."""
    return await run_in_threadpool(retention.status, db)


@router.post("/run", response_model=RetentionRun)
async def retention_run(db: Session = Depends(get_db), admin: User = Depends(require_role(Role.ADMIN))) -> dict[str, Any]:
    """Chạy dọn dữ liệu ngay (theo chính sách trong cấu hình). Chính sách tắt thì không xóa gì."""
    audit(db, admin.username, "RETENTION_RUN_MANUAL", None, None)
    db.commit()
    return await run_in_threadpool(retention.purge_old, db)
