"""Vong doi lenh (G3): SENT -> DELIVERED -> APPLIED / REJECTED / TIMEOUT.

NGUYEN TAC AN TOAN:
- Lenh tu xa KHONG tat duoc canh bao cuc bo (whitelist lenh + extra='forbid' o params.py).
- KHONG cho MUTE khi dang CRITICAL (kiem tra truoc khi gui; lan bi chan van ghi audit).
- Lenh het TTL bi danh dau TIMEOUT; ACK den muon KHONG lam lenh 'song lai'.
- cmd_id idempotent: gui lai cung cmd_id -> tra ket qua cu, khong gui lan hai.
"""
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alarms.realtime import hub
from alarms.service import MuteNotAllowed, ensure_mute_allowed
from app.core.db import SessionLocal
from app.models import Command, Device
from app.models.enums import CommandName, CommandState, Role
from app.services.audit import audit
from commands import config_service
from commands.config_service import DeviceNotFound  # noqa: F401  (re-export cho router)
from commands.params import CommandInvalid, validate_params
from commands.publisher import PublishFailed, get_publisher
from ingest.validator import validate

log = logging.getLogger("svmg.commands")

SYSTEM_ACTOR = "system"
FINAL_STATES = (CommandState.APPLIED, CommandState.REJECTED, CommandState.TIMEOUT)

# Vai tro toi thieu de gui tung lenh (README: Operator ACK/mute; Supervisor cau hinh; Admin restart).
# TODO M3-05: router dung bang nay de enforce RBAC.
REQUIRED_ROLE: dict[CommandName, Role] = {
    CommandName.mute_alarm: Role.OPERATOR,
    CommandName.set_profile: Role.SUPERVISOR,
    CommandName.set_threshold: Role.SUPERVISOR,
    CommandName.calibrate_zero: Role.SUPERVISOR,
    CommandName.start_voyage: Role.SUPERVISOR,
    CommandName.stop_voyage: Role.SUPERVISOR,
    CommandName.restart_device: Role.ADMIN,
}


class CommandBlocked(Exception):
    """Bi chan boi quy tac an toan (HTTP 409)."""


class CommandConflict(Exception):
    """cmd_id da dung cho lenh khac (HTTP 409)."""


class CommandNotFound(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None)


def _broadcast(action: str, c: Command) -> None:
    from app.schemas.command import CommandOut
    hub.publish({"type": "command", "action": action,
                 "command": CommandOut.model_validate(c).model_dump(mode="json")})


def cmd_topic(device_id: str) -> str:
    return f"svmg/{device_id}/cmd"


def _find_command(db: Session, cmd_id: str) -> Optional[Command]:
    return db.scalar(select(Command).where(Command.cmd_id == cmd_id))


def _replay(existing: Command, device_id: str, cmd: CommandName, clean: dict[str, Any]) -> Command:
    """Gui lai cung cmd_id: cung noi dung -> tra ket qua cu; khac noi dung -> conflict."""
    if (existing.device_id, existing.cmd, existing.params or {}) == (device_id, cmd.value, clean):
        return existing
    raise CommandConflict(f"cmd_id '{existing.cmd_id}' đã được dùng cho một lệnh khác")


def create_command(db: Session, device_id: str, cmd: CommandName, params: dict[str, Any],
                   ttl_s: int, actor: str, cmd_id: Optional[str] = None,
                   now: Optional[datetime] = None) -> tuple[Command, bool]:
    """Tao + gui lenh. Tra ve (command, created); created=False neu la gui lai cmd_id cu."""
    if db.scalar(select(Device.id).where(Device.device_id == device_id)) is None:
        raise DeviceNotFound(f"Không tìm thấy thiết bị '{device_id}'")
    clean = validate_params(cmd, params)
    cmd_id = cmd_id or "c-" + uuid.uuid4().hex[:8]

    existing = _find_command(db, cmd_id)
    if existing is not None:  # idempotent
        return _replay(existing, device_id, cmd, clean), False

    if cmd == CommandName.mute_alarm:
        try:
            ensure_mute_allowed(db, device_id)
        except MuteNotAllowed as e:
            audit(db, actor, "CMD_BLOCKED", f"{device_id}:{cmd_id}", {"cmd": cmd.value, "reason": str(e)})
            db.commit()  # lan bi chan van phai de lai dau vet
            raise CommandBlocked(str(e)) from e

    payload = {"cmd_id": cmd_id, "cmd": cmd.value, "params": clean, "ttl_s": ttl_s, "issued_by": actor}
    errs = validate("cmd", payload)
    if errs:
        raise CommandInvalid("Lệnh không khớp hợp đồng: " + "; ".join(errs[:3]))

    row = Command(cmd_id=cmd_id, device_id=device_id, cmd=cmd.value, params=clean, ttl_s=ttl_s,
                  issued_by=actor, state=CommandState.SENT, created_at=now or _now())
    db.add(row)
    audit(db, actor, "CMD_SENT", f"{device_id}:{cmd_id}", {"cmd": cmd.value, "params": clean, "ttl_s": ttl_s})
    try:
        db.commit()  # ghi TRUOC khi gui: PUBACK co the ve nhanh hon commit
    except IntegrityError:
        # Hai request cung cmd_id den sat nhau: ca hai deu thay 'chua ton tai', request cham hon vi pham unique.
        # Coi nhu gui lai (idempotent), KHONG gui lenh lan hai.
        db.rollback()
        existing = _find_command(db, cmd_id)
        if existing is None:
            raise
        return _replay(existing, device_id, cmd, clean), False
    try:
        get_publisher().publish(cmd_topic(device_id), json.dumps(payload), qos=1, retain=False,
                                on_delivered=lambda: mark_delivered(cmd_id))
    except PublishFailed as e:
        row.state, row.reason, row.finished_at = CommandState.TIMEOUT, "Không gửi được tới broker", _now()
        audit(db, SYSTEM_ACTOR, "CMD_PUBLISH_FAILED", f"{device_id}:{cmd_id}", {"error": str(e)})
        db.commit()
        _broadcast("timeout", row)
        raise
    log.info("command sent", extra={"device_id": device_id, "cmd_id": cmd_id, "cmd": cmd.value})
    _broadcast("sent", row)
    return row, True


def mark_delivered(cmd_id: str) -> None:
    """Goi tu luong MQTT khi broker PUBACK. Mo session rieng."""
    db = SessionLocal()
    try:
        c = db.scalar(select(Command).where(Command.cmd_id == cmd_id))
        if c is not None and c.state == CommandState.SENT:
            c.state, c.delivered_at = CommandState.DELIVERED, _now()
            db.commit()
            _broadcast("delivered", c)
    except Exception:
        db.rollback()
        log.exception("mark_delivered failed", extra={"cmd_id": cmd_id})
    finally:
        db.close()


def handle_ack(db: Session, device_id: str, p: dict[str, Any], rx: datetime) -> tuple[str, Optional[Command]]:
    """Xu ly bao cao tu thiet bi. Tra ve (ket_qua, command):
    applied|rejected -> da chuyen trang thai; unknown | mismatch | duplicate | late."""
    c = db.scalar(select(Command).where(Command.cmd_id == p["cmd_id"]))
    if c is None:
        return "unknown", None
    if c.device_id != device_id:
        return "mismatch", c  # thiet bi nay khong duoc ACK lenh cua tau khac
    if c.state in (CommandState.APPLIED, CommandState.REJECTED):
        return "duplicate", c
    if c.state == CommandState.TIMEOUT:
        # lenh da het han: thiet bi lam theo TTL cua no; KHONG hoi sinh lenh, chi ghi nhan bat thuong
        audit(db, f"device:{device_id}", "CMD_LATE_ACK", f"{device_id}:{c.cmd_id}", {"result": p["result"]})
        db.commit()
        return "late", c
    new = CommandState(p["result"])
    c.state, c.reason, c.finished_at = new, p.get("reason"), rx
    c.delivered_at = c.delivered_at or rx
    if new == CommandState.APPLIED:
        config_service.mark_applied(db, device_id, p.get("config_version"))
    audit(db, f"device:{device_id}", "CMD_ACK", f"{device_id}:{c.cmd_id}",
          {"result": new.value, "reason": p.get("reason")})
    db.commit()
    _broadcast(new.value.lower(), c)
    return new.value.lower(), c


def expire_overdue(db: Session, now: Optional[datetime] = None) -> list[Command]:
    """Danh dau TIMEOUT cac lenh SENT/DELIVERED da qua ttl_s."""
    now = now or _now()
    rows = [c for c in db.scalars(select(Command).where(
        Command.state.in_((CommandState.SENT, CommandState.DELIVERED))))
        if _naive(c.created_at) + timedelta(seconds=c.ttl_s) <= _naive(now)]
    for c in rows:
        c.state, c.reason, c.finished_at = CommandState.TIMEOUT, "Hết hạn TTL, thiết bị không phản hồi", now
        audit(db, SYSTEM_ACTOR, "CMD_TIMEOUT", f"{c.device_id}:{c.cmd_id}", {"ttl_s": c.ttl_s})
    db.commit()
    for c in rows:
        _broadcast("timeout", c)
    return rows


def command_stats(db: Session, device_id: Optional[str] = None) -> dict[str, Any]:
    """Thong ke cho T10: dem theo trang thai, RTT (tu luc tao den luc thiet bi tra loi)."""
    q = select(Command)
    if device_id:
        q = q.where(Command.device_id == device_id)
    rows = list(db.scalars(q))
    by_state: dict[str, int] = {}
    for c in rows:
        by_state[c.state.value] = by_state.get(c.state.value, 0) + 1
    rtts = sorted((_naive(c.finished_at) - _naive(c.created_at)).total_seconds()
                  for c in rows if c.state in (CommandState.APPLIED, CommandState.REJECTED) and c.finished_at)
    p95 = rtts[min(len(rtts) - 1, int(0.95 * len(rtts)))] if rtts else None
    return {"total": len(rows), "by_state": by_state,
            "rtt_mean_s": (sum(rtts) / len(rtts)) if rtts else None, "rtt_p95_s": p95,
            "rtt_max_s": rtts[-1] if rtts else None,
            "timeout_rate": (by_state.get("TIMEOUT", 0) / len(rows)) if rows else None}
