from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role
from app.models import User
from app.models.enums import Role
from app.schemas.ingest import IngestRates, IngestStatsOut, RecentError
from app.services.audit import audit
from ingest.stats import stats

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])


@router.get("/stats", response_model=IngestStatsOut, dependencies=[Depends(require_role(Role.SUPERVISOR))])
async def ingest_stats() -> IngestStatsOut:
    """Số đếm bản tin MQTT đã nhận (đo T06/T14) và 50 bản tin bị từ chối gần nhất kèm lý do."""
    s = stats.snapshot()
    total = s["total_messages"]
    rate = lambda k: (s["totals"].get(k, 0) / total) if total else None  # noqa: E731
    return IngestStatsOut(
        since=s["since"], total_messages=total, totals=s["totals"],
        rates=IngestRates(stored=rate("STORED"), duplicate=rate("DUPLICATE"), invalid=rate("INVALID"),
                          rejected=rate("REJECTED"), ignored=rate("IGNORED")),
        by_kind=s["by_kind"], by_device=s["by_device"],
        recent_errors=[RecentError(**e) for e in s["recent_errors"]])


@router.post("/stats/reset", status_code=204)
async def reset_ingest_stats(admin: User = Depends(require_role(Role.ADMIN)), db: Session = Depends(get_db)) -> Response:
    """Đặt lại bộ đếm (dùng trước mỗi lần chạy thí nghiệm). Có ghi nhật ký kiểm toán."""
    before = stats.snapshot()["total_messages"]
    stats.reset()
    audit(db, admin.username, "INGEST_STATS_RESET", None, {"messages_before_reset": before})
    db.commit()
    return Response(status_code=204)
