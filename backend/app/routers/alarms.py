from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from alarms import service
from alarms.realtime import hub
from app.core.db import SessionLocal, get_db
from app.core.security import current_actor, get_current_user, user_from_token
from app.models import Alarm
from app.models.enums import AlarmState
from app.schemas.alarm import AckResult, AlarmOut, AlarmStats

# REST: dang nhap la du (ACK la quyen toi thieu OPERATOR, ma moi vai tro >= OPERATOR).
router = APIRouter(tags=["alarms"], dependencies=[Depends(get_current_user)])
# WebSocket khong dung duoc OAuth2PasswordBearer (can Request) -> router rieng, xac thuc bang ?token=
ws_router = APIRouter(tags=["alarms"])


@router.get("/api/v1/alarms", response_model=list[AlarmOut])
async def list_alarms(
    device_id: Optional[str] = None,
    state: Optional[AlarmState] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[Alarm]:
    q = select(Alarm).order_by(Alarm.opened_at.desc(), Alarm.id.desc()).limit(limit)
    if device_id:
        q = q.where(Alarm.device_id == device_id)
    if state:
        q = q.where(Alarm.state == state)
    return list(db.scalars(q))


# Dat truoc /{alarm_pk} de "stats" khong bi hieu la id
@router.get("/api/v1/alarms/stats", response_model=AlarmStats)
async def alarm_stats(device_id: Optional[str] = None, since: Optional[datetime] = None,
                      db: Session = Depends(get_db)) -> AlarmStats:
    return service.compute_stats(db, device_id, since)


@router.get("/api/v1/alarms/{alarm_pk}", response_model=AlarmOut)
async def get_alarm(alarm_pk: int, db: Session = Depends(get_db)) -> Alarm:
    alarm = db.get(Alarm, alarm_pk)
    if alarm is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy cảnh báo #{alarm_pk}")
    return alarm


@router.post("/api/v1/alarms/{alarm_pk}/ack", response_model=AckResult)
async def ack_alarm(alarm_pk: int, db: Session = Depends(get_db),
                    actor: str = Depends(current_actor)) -> AckResult:
    """ACK ghi nhan nguoi truc da biet. KHONG tat canh bao cuc bo tren thiet bi."""
    try:
        alarm, already = service.ack_alarm(db, alarm_pk, actor)
    except service.AlarmNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except service.AlarmConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    return AckResult(alarm=AlarmOut.model_validate(alarm), already_acked=already)


@ws_router.websocket("/ws/alarms")
async def ws_alarms(ws: WebSocket, token: Optional[str] = Query(None)) -> None:
    """Ket noi: ws://host/ws/alarms?token=<JWT>. Sai/thieu token -> tu choi (1008).
    Han che: token nam trong URL (co the vao log proxy); phien WS khong tu ngat khi token het han."""
    with SessionLocal() as db:
        user = user_from_token(db, token)
    if user is None:
        await ws.close(code=1008)
        return
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()  # giu ket noi; client khong can gui gi
    except WebSocketDisconnect:
        hub.disconnect(ws)
