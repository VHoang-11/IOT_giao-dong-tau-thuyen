from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import assert_role, current_actor, get_current_user, require_role
from app.models import AuditLog, Command, User
from app.models.enums import CommandState, Role
from app.schemas.command import (
    AuditOut, CommandOut, CommandRequest, CommandStats, ConfigOut, ConfigUpdate, RollbackRequest,
)
from commands import config_service, service
from commands.params import CommandInvalid
from commands.publisher import PublishFailed

# Mac dinh: phai dang nhap. Cac route ghi (gui lenh, doi cau hinh) siet quyen tung route ben duoi.
router = APIRouter(tags=["commands"], dependencies=[Depends(get_current_user)])
_SUPERVISOR = [Depends(require_role(Role.SUPERVISOR))]


def _http(e: Exception) -> HTTPException:
    """Doi exception nghiep vu -> ma HTTP ro rang."""
    if isinstance(e, (service.DeviceNotFound, service.CommandNotFound)):
        return HTTPException(404, str(e))
    if isinstance(e, CommandInvalid):
        return HTTPException(422, str(e))
    if isinstance(e, PublishFailed):
        return HTTPException(503, f"Không gửi được tới thiết bị: {e}")
    return HTTPException(409, str(e))  # CommandBlocked / CommandConflict / ConfigConflict


@router.post("/api/v1/devices/{device_id}/commands", response_model=CommandOut, status_code=202)
async def send_command(device_id: str, body: CommandRequest, response: Response,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Command:
    """Gui lenh. Vai tro toi thieu tuy lenh (service.REQUIRED_ROLE). Gui lai cung cmd_id -> 200, khong gui lan hai."""
    assert_role(db, user, service.REQUIRED_ROLE[body.cmd], f"cmd:{body.cmd.value}")
    try:
        cmd, created = service.create_command(db, device_id, body.cmd, body.params, body.ttl_s,
                                              user.username, body.cmd_id)
    except (service.DeviceNotFound, CommandInvalid, PublishFailed, service.CommandBlocked,
            service.CommandConflict) as e:
        raise _http(e)
    if not created:
        response.status_code = 200
    return cmd


@router.get("/api/v1/commands", response_model=list[CommandOut])
async def list_commands(device_id: Optional[str] = None, state: Optional[CommandState] = None,
                        limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)) -> list[Command]:
    q = select(Command).order_by(Command.created_at.desc(), Command.id.desc()).limit(limit)
    if device_id:
        q = q.where(Command.device_id == device_id)
    if state:
        q = q.where(Command.state == state)
    return list(db.scalars(q))


@router.get("/api/v1/commands/stats", response_model=CommandStats)
async def command_stats(device_id: Optional[str] = None, db: Session = Depends(get_db)) -> CommandStats:
    return CommandStats(**service.command_stats(db, device_id))


@router.get("/api/v1/commands/{cmd_id}", response_model=CommandOut)
async def get_command(cmd_id: str, db: Session = Depends(get_db)) -> Command:
    c = db.scalar(select(Command).where(Command.cmd_id == cmd_id))
    if c is None:
        raise HTTPException(404, f"Không tìm thấy lệnh '{cmd_id}'")
    return c


# ---------- cau hinh co phien ban ----------

def _config_out(row) -> ConfigOut:
    return ConfigOut.model_validate(row)


@router.get("/api/v1/devices/{device_id}/config", response_model=list[ConfigOut])
async def config_history(device_id: str, db: Session = Depends(get_db)):
    """Lich su cau hinh, moi nhat truoc."""
    return config_service.history(db, device_id)


@router.put("/api/v1/devices/{device_id}/config", response_model=ConfigOut, status_code=201,
            dependencies=_SUPERVISOR)
async def update_config(device_id: str, body: ConfigUpdate, db: Session = Depends(get_db),
                        actor: str = Depends(current_actor)):
    try:
        return config_service.update_config(db, device_id, body.model_dump(exclude_none=True), actor)
    except (config_service.DeviceNotFound, CommandInvalid, PublishFailed) as e:
        raise _http(e)


@router.post("/api/v1/devices/{device_id}/config/rollback", response_model=ConfigOut, status_code=201,
             dependencies=_SUPERVISOR)
async def rollback_config(device_id: str, body: RollbackRequest, db: Session = Depends(get_db),
                          actor: str = Depends(current_actor)):
    """Rollback = tao phien ban MOI co noi dung cua ban cu (thiet bi chi nhan version lon hon)."""
    try:
        return config_service.rollback_config(db, device_id, actor, body.to_version)
    except (config_service.DeviceNotFound, config_service.ConfigConflict, CommandInvalid, PublishFailed) as e:
        raise _http(e)


# ---------- nhat ky kiem toan ----------

@router.get("/api/v1/audit", response_model=list[AuditOut], dependencies=_SUPERVISOR)
async def list_audit(actor: Optional[str] = None, action: Optional[str] = None,
                     limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)) -> list[AuditLog]:
    q = select(AuditLog).order_by(AuditLog.ts.desc(), AuditLog.id.desc()).limit(limit)
    if actor:
        q = q.where(AuditLog.actor == actor)
    if action:
        q = q.where(AuditLog.action == action)
    return list(db.scalars(q))
