from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.db import get_db
from app.core.security import get_current_user, require_role
from app.models import User, Voyage
from app.models.enums import Role, VoyageStatus
from app.schemas.voyage import VOYAGE_ID_PATTERN, ReportSummary, VoyageCreate, VoyageOut
from app.services import voyages as svc
from reports.csvexport import iter_alarms_csv, iter_telemetry_csv
from reports.metrics import compute_summary
from reports.pdf import build_pdf

# Xem chuyen di / bao cao: dang nhap la du. Tao / ket thuc chuyen: tu SUPERVISOR tro len.
router = APIRouter(prefix="/api/v1/voyages", tags=["voyages"], dependencies=[Depends(get_current_user)])
_SUPERVISOR = [Depends(require_role(Role.SUPERVISOR))]
VoyageIdPath = Path(..., pattern=VOYAGE_ID_PATTERN)
_NO_STORE = {"Cache-Control": "no-store"}  # bao cao chua du lieu van hanh: khong de cache o trinh duyet/proxy chung


def _get(db: Session, voyage_id: str) -> Voyage:
    try:
        return svc.get_voyage(db, voyage_id)
    except svc.VoyageNotFound as e:
        raise HTTPException(404, str(e))


@router.post("", response_model=VoyageOut, status_code=201)
async def start_voyage(body: VoyageCreate, db: Session = Depends(get_db),
                       user: User = Depends(require_role(Role.SUPERVISOR))) -> Voyage:
    """Tao chuyen di (moi thiet bi toi da 1 chuyen dang chay). KHONG tu gui lenh start_voyage xuong thiet bi."""
    try:
        return svc.start_voyage(db, user.username, body.device_id, body.voyage_id)
    except svc.VoyageNotFound as e:
        raise HTTPException(404, str(e))
    except svc.VoyageConflict as e:
        raise HTTPException(409, str(e))


@router.get("", response_model=list[VoyageOut])
async def list_voyages(device_id: Optional[str] = None, status: Optional[VoyageStatus] = None,
                       limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)) -> list[Voyage]:
    q = select(Voyage).order_by(Voyage.started_at.desc(), Voyage.id.desc()).limit(limit)
    if device_id:
        q = q.where(Voyage.device_id == device_id)
    if status:
        q = q.where(Voyage.status == status)
    return list(db.scalars(q))


@router.get("/{voyage_id}", response_model=VoyageOut)
async def get_voyage(voyage_id: str = VoyageIdPath, db: Session = Depends(get_db)) -> Voyage:
    return _get(db, voyage_id)


@router.post("/{voyage_id}/end", response_model=VoyageOut, dependencies=_SUPERVISOR)
async def end_voyage(voyage_id: str = VoyageIdPath, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)) -> Voyage:
    try:
        return svc.end_voyage(db, user.username, voyage_id)
    except svc.VoyageNotFound as e:
        raise HTTPException(404, str(e))
    except svc.VoyageConflict as e:
        raise HTTPException(409, str(e))


@router.get("/{voyage_id}/summary", response_model=ReportSummary)
async def voyage_summary(response: Response, voyage_id: str = VoyageIdPath,
                         db: Session = Depends(get_db)) -> ReportSummary:
    """So lieu bao cao, tinh lai tu du lieu goc moi lan goi (cong thuc: xem reports/metrics.py va README)."""
    v = _get(db, voyage_id)
    summary, _ = await run_in_threadpool(compute_summary, db, v)  # duyet nhieu dong -> ngoai event loop
    response.headers.update(_NO_STORE)
    return summary


def _csv_response(gen, filename: str) -> StreamingResponse:
    return StreamingResponse(gen, media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"', **_NO_STORE})


@router.get("/{voyage_id}/telemetry.csv")
async def telemetry_csv(voyage_id: str = VoyageIdPath, db: Session = Depends(get_db)) -> StreamingResponse:
    v = _get(db, voyage_id)
    return _csv_response(iter_telemetry_csv(v.device_id, v.voyage_id), f"{v.voyage_id}-telemetry.csv")


@router.get("/{voyage_id}/alarms.csv")
async def alarms_csv(voyage_id: str = VoyageIdPath, db: Session = Depends(get_db)) -> StreamingResponse:
    v = _get(db, voyage_id)
    return _csv_response(iter_alarms_csv(v.device_id, v.voyage_id), f"{v.voyage_id}-alarms.csv")


def _make_pdf(db: Session, v: Voyage) -> bytes:
    summary, series = compute_summary(db, v)
    return build_pdf(summary, series)


@router.get("/{voyage_id}/report.pdf")
async def report_pdf(voyage_id: str = VoyageIdPath, db: Session = Depends(get_db)) -> Response:
    v = _get(db, voyage_id)
    pdf = await run_in_threadpool(_make_pdf, db, v)  # dung PDF ton CPU -> ngoai event loop
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{v.voyage_id}-report.pdf"', **_NO_STORE})
