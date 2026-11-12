"""Vong doi canh bao phia server (G2).

NGUYEN TAC AN TOAN:
- Thiet bi (ESP32) moi la noi quyet dinh muc canh bao; backend chi PHAN CHIEU event.
- ACK tren server chi ghi nhan nguoi truc da biet, KHONG tat canh bao cuc bo tren thiet bi.
- Leo thang chi danh dau + thong bao, khong gui lenh xuong thiet bi.
- Khong cho MUTE khi dang CRITICAL (ensure_mute_allowed, M3-04 se goi).
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from alarms.realtime import hub
from app.core.config import settings
from app.models import Alarm, AlarmEvent, Device, Telemetry
from app.models.enums import AlarmLevel, AlarmState, SourceMode
from app.schemas.alarm import AlarmOut, AlarmStats
from app.services.audit import audit
from notify.service import notify_alarm

log = logging.getLogger("svmg.alarms")

ORDER = {AlarmLevel.NORMAL: 0, AlarmLevel.CAUTION: 1, AlarmLevel.WARNING: 2, AlarmLevel.CRITICAL: 3}
SYSTEM_ACTOR = "system"


class AlarmNotFound(Exception):
    pass


class AlarmConflict(Exception):
    pass


class MuteNotAllowed(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _publish(action: str, alarm: Alarm) -> None:
    hub.publish({"type": "alarm", "action": action,
                 "alarm": AlarmOut.model_validate(alarm).model_dump(mode="json")})


def _mark_acked(alarm: Alarm, actor: str, when: datetime) -> None:
    alarm.state = AlarmState.ACKED
    alarm.acked_by = actor
    if alarm.acked_at is None:  # giu moc ACK dau tien de tinh MTTA
        alarm.acked_at = when


def apply_event(db: Session, ev: AlarmEvent) -> Optional[Alarm]:
    """Ap dung 1 ban tin event (da luu + khu trung) vao vong doi canh bao."""
    notify_kind: Optional[str] = None  # thong bao Telegram/email (M3-08), gui SAU khi commit
    alarm = db.scalar(select(Alarm).where(
        Alarm.device_id == ev.device_id, Alarm.boot_id == ev.boot_id, Alarm.alarm_id == ev.alarm_id))
    if alarm is None:
        if ev.level == AlarmLevel.NORMAL:
            return None  # khong co gi de dong
        dev = db.scalar(select(Device).where(Device.device_id == ev.device_id))
        voyage = db.scalar(select(Telemetry.voyage_id).where(Telemetry.device_id == ev.device_id)
                           .order_by(Telemetry.id.desc()).limit(1))
        alarm = Alarm(alarm_id=ev.alarm_id, boot_id=ev.boot_id, device_id=ev.device_id,
                      last_seq=ev.seq, state=AlarmState.ACTIVE, level=ev.level, max_level=ev.level,
                      motion_class=ev.motion_class, voyage_id=voyage,
                      source_mode=dev.source_mode if dev else SourceMode.SIMULATION,
                      opened_at=ev.server_rx_time, escalated=False)
        db.add(alarm)
        action = "opened"
        if ev.level == AlarmLevel.CRITICAL:
            notify_kind = "ALARM_CRITICAL"
    else:
        # bo qua ban tin cu/den muon (seq khong tang) va canh bao da giai toa
        if ev.seq <= alarm.last_seq or alarm.state == AlarmState.CLEARED:
            return None
        alarm.last_seq = ev.seq
        if ev.level == AlarmLevel.NORMAL:
            alarm.state, alarm.level, alarm.cleared_at = AlarmState.CLEARED, AlarmLevel.NORMAL, ev.server_rx_time
            action = "cleared"
        else:
            rising = ORDER[ev.level] > ORDER[alarm.level]
            alarm.level = ev.level
            if ORDER[ev.level] > ORDER[alarm.max_level]:
                alarm.max_level = ev.level
            if ev.motion_class:
                alarm.motion_class = ev.motion_class
            if rising and alarm.state == AlarmState.ACKED:
                # muc nang hon sau khi da ACK -> khong coi la da xu ly, bat nguoi truc xac nhan lai
                alarm.state, alarm.escalated = AlarmState.ACTIVE, True
                audit(db, SYSTEM_ACTOR, "ALARM_REACTIVATED", f"{ev.device_id}:{ev.alarm_id}",
                      {"level": ev.level.value})
                action = "escalated"
                notify_kind = "ALARM_CRITICAL" if ev.level == AlarmLevel.CRITICAL else "ALARM_REACTIVATED"
            else:
                action = "updated"
                if rising and ev.level == AlarmLevel.CRITICAL:
                    notify_kind = "ALARM_CRITICAL"  # vua len CRITICAL: chi bao 1 lan o thoi diem chuyen muc
    if ev.acked_by and alarm.acked_at is None and alarm.state != AlarmState.CLEARED:
        _mark_acked(alarm, ev.acked_by, ev.server_rx_time)  # ACK bang nut tren thiet bi
    db.commit()
    log.info("alarm " + action, extra={"device_id": alarm.device_id, "alarm_id": alarm.alarm_id,
                                       "level": alarm.level.value})
    _publish(action, alarm)
    if notify_kind:
        notify_alarm(notify_kind, alarm)  # luong nen, khong chan, khong nem loi
    return alarm


def ack_alarm(db: Session, pk: int, actor: str, now: Optional[datetime] = None) -> tuple[Alarm, bool]:
    """Nguoi truc ACK. Tra ve (alarm, already_acked). Idempotent."""
    alarm = db.get(Alarm, pk)
    if alarm is None:
        raise AlarmNotFound(f"Không tìm thấy cảnh báo #{pk}")
    if alarm.state == AlarmState.CLEARED:
        raise AlarmConflict("Cảnh báo đã được giải tỏa, không thể ACK")
    if alarm.state == AlarmState.ACKED:
        return alarm, True
    _mark_acked(alarm, actor, now or _now())
    audit(db, actor, "ALARM_ACK", f"alarm:{pk}",
          {"device_id": alarm.device_id, "alarm_id": alarm.alarm_id, "level": alarm.level.value})
    db.commit()
    _publish("acked", alarm)
    return alarm, False


def escalate_overdue(db: Session, now: Optional[datetime] = None,
                     after_s: Optional[int] = None) -> list[Alarm]:
    """Danh dau leo thang cac canh bao ACTIVE chua ai ACK qua `after_s` giay."""
    now = now or _now()
    cutoff = now - timedelta(seconds=after_s if after_s is not None else settings.alarm_escalate_after_s)
    rows = list(db.scalars(select(Alarm).where(
        Alarm.state == AlarmState.ACTIVE, Alarm.escalated.is_(False),
        Alarm.acked_at.is_(None), Alarm.opened_at <= cutoff)))
    for a in rows:
        a.escalated = True
        audit(db, SYSTEM_ACTOR, "ALARM_ESCALATED", f"alarm:{a.id}",
              {"device_id": a.device_id, "level": a.level.value})
    db.commit()
    for a in rows:
        _publish("escalated", a)
        notify_alarm("ALARM_ESCALATED", a)
    return rows


def ensure_mute_allowed(db: Session, device_id: str) -> None:
    """Chan MUTE khi dang CRITICAL. M3-04 (command service) phai goi ham nay truoc khi gui mute_alarm."""
    critical_open = db.scalar(select(Alarm.id).where(
        Alarm.device_id == device_id, Alarm.state != AlarmState.CLEARED,
        Alarm.level == AlarmLevel.CRITICAL).limit(1))
    last_level = db.scalar(select(Telemetry.alarm_level).where(Telemetry.device_id == device_id)
                           .order_by(Telemetry.server_rx_time.desc(), Telemetry.id.desc()).limit(1))
    if critical_open is not None or last_level == AlarmLevel.CRITICAL:
        raise MuteNotAllowed("Không được MUTE khi cảnh báo đang ở mức CRITICAL")


def compute_stats(db: Session, device_id: Optional[str] = None,
                  since: Optional[datetime] = None) -> AlarmStats:
    q = select(Alarm)
    if device_id:
        q = q.where(Alarm.device_id == device_id)
    if since:
        q = q.where(Alarm.opened_at >= since)
    rows = list(db.scalars(q))
    ttas = [AlarmOut.model_validate(a).time_to_ack_s for a in rows if a.acked_at is not None]
    by_level: dict[str, int] = {}
    for a in rows:
        by_level[a.max_level.value] = by_level.get(a.max_level.value, 0) + 1
    total = len(rows)
    esc = sum(1 for a in rows if a.escalated)
    return AlarmStats(
        total=total,
        active=sum(1 for a in rows if a.state == AlarmState.ACTIVE),
        acked=len(ttas),  # so canh bao tung duoc ACK (ke ca da giai toa)
        cleared=sum(1 for a in rows if a.state == AlarmState.CLEARED),
        escalated=esc,
        mtta_s=(sum(ttas) / len(ttas)) if ttas else None,
        escalation_rate=(esc / total) if total else None,
        by_max_level=by_level)
