from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import require_role
from app.models import User
from app.models.enums import Role
from app.services.audit import audit
from notify.service import Message, dispatcher

router = APIRouter(prefix="/api/v1/notify", tags=["notify"])


class ChannelStatus(BaseModel):
    name: str
    configured: bool


class NotifyStatus(BaseModel):
    channels: list[ChannelStatus]
    stats: dict[str, int]
    cooldown_s: int


class TestResult(BaseModel):
    results: dict[str, str]


@router.get("/status", response_model=NotifyStatus)
async def notify_status(_: User = Depends(require_role(Role.ADMIN))) -> NotifyStatus:
    """Kenh nao da cau hinh + bo dem gui/loi. KHONG tra ve token/URL."""
    return NotifyStatus(
        channels=[ChannelStatus(name=c.name, configured=c.configured()) for c in dispatcher.channels],
        stats=dict(dispatcher.stats), cooldown_s=settings.notify_cooldown_s)


@router.post("/test", response_model=TestResult)
async def notify_test(admin: User = Depends(require_role(Role.ADMIN)), db: Session = Depends(get_db)) -> TestResult:
    """Gui 1 tin thu toi moi kenh da cau hinh (dong bo) de kiem tra token/webhook."""
    # Gui mang dong bo co the cho vai giay (timeout x so lan thu lai): PHAI chay ngoai event loop,
    # neu khong moi request va moi WebSocket deu dung im.
    results = await run_in_threadpool(dispatcher.send_now, Message(
        kind="TEST", title="Tin nhắn thử", text=f"Kiểm tra kênh thông báo do {admin.username} yêu cầu."))
    audit(db, admin.username, "NOTIFY_TEST", None, {"results": results})
    db.commit()
    return TestResult(results=results)
