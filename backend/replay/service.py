"""Replay: lay lai du lieu cua mot chuyen theo khoang thoi gian de GIAO DIEN phat lai (toc do x1-x60 la viec cua client).

NGUYEN TAC (T15 'replay khop du lieu goc'):
- Thu tu tang dan theo (server_rx_time, id), KHONG theo t_sim_s: hop dong khong noi t_sim_s co dem lai sau khi
  thiet bi khoi dong lai hay khong. meta.t_sim_monotonic cho client biet truc t_sim_s co dang tin khong.
- Phan trang bang con tro; KHONG bao gio cat du lieu am tham (truncated + next_cursor). Noi cac trang lai = telemetry.csv.
- Canh bao/su kien/lenh duoc chia theo khoang thoi gian server cua tung trang: moi su kien xuat hien DUNG 1 LAN.
"""
import base64
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import Alarm, AlarmEvent, Command, Telemetry, Voyage
from app.schemas.alarm import AlarmOut
from app.schemas.replay import (
    ReplayAlarmEvent, ReplayCommand, ReplayMeta, ReplayResponse, ReplayTelemetry,
)
from reports.csvexport import utc


class ReplayError(Exception):
    """Tham so khong hop le (HTTP 422)."""


@dataclass
class Filters:
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    from_t_sim: Optional[float] = None
    to_t_sim: Optional[float] = None

    @property
    def uses_time(self) -> bool:
        return self.from_time is not None or self.to_time is not None

    @property
    def uses_t_sim(self) -> bool:
        return self.from_t_sim is not None or self.to_t_sim is not None


def validate_filters(f: Filters) -> None:
    if f.uses_time and f.uses_t_sim:
        raise ReplayError("Không dùng đồng thời from_time/to_time và from_t_sim/to_t_sim (chọn một trục thời gian)")
    if f.from_time and f.to_time and utc(f.from_time) > utc(f.to_time):
        raise ReplayError("from_time phải nhỏ hơn hoặc bằng to_time")
    if f.from_t_sim is not None and f.to_t_sim is not None and f.from_t_sim > f.to_t_sim:
        raise ReplayError("from_t_sim phải nhỏ hơn hoặc bằng to_t_sim")


# ---------------------------------------------------------------- con tro

def encode_cursor(rx: datetime, row_id: int) -> str:
    raw = json.dumps({"rx": utc(rx).isoformat(), "id": row_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        d = json.loads(raw)
        rx = datetime.fromisoformat(d["rx"])
        row_id = d["id"]
        if not isinstance(row_id, int) or isinstance(row_id, bool) or rx.tzinfo is None:
            raise ValueError
        return utc(rx), row_id
    except (ValueError, KeyError, TypeError):
        raise ReplayError("cursor không hợp lệ") from None


# ---------------------------------------------------------------- truy van

def _base(voyage: Voyage):
    return [Telemetry.device_id == voyage.device_id, Telemetry.voyage_id == voyage.voyage_id]


def _filter_conditions(f: Filters) -> list:
    c = []
    if f.from_time is not None:
        c.append(Telemetry.server_rx_time >= utc(f.from_time))
    if f.to_time is not None:
        c.append(Telemetry.server_rx_time <= utc(f.to_time))
    if f.from_t_sim is not None:
        c.append(Telemetry.t_sim_s >= f.from_t_sim)
    if f.to_t_sim is not None:
        c.append(Telemetry.t_sim_s <= f.to_t_sim)
    return c


def _window(col, lo: Optional[datetime], lo_inclusive: bool, hi: Optional[datetime]) -> list:
    c = []
    if lo is not None:
        c.append(col >= lo if lo_inclusive else col > lo)
    if hi is not None:
        c.append(col <= hi)
    return c


def _meta(db: Session, voyage: Voyage, f: Filters) -> ReplayMeta:
    base = _base(voyage)
    n, first, last, tmin, tmax, boots = db.execute(select(
        func.count(), func.min(Telemetry.server_rx_time), func.max(Telemetry.server_rx_time),
        func.min(Telemetry.t_sim_s), func.max(Telemetry.t_sim_s), func.count(func.distinct(Telemetry.boot_id))
    ).where(*base)).one()
    window_n = db.scalar(select(func.count()).select_from(Telemetry).where(*base, *_filter_conditions(f))) or 0
    # .distinct() (khong phai func.distinct) de giu kieu Enum cua cot
    modes = sorted(m.value for m in db.scalars(select(Telemetry.source_mode).where(*base).distinct()))
    warps = sorted(w for w in db.scalars(select(Telemetry.timewarp).where(*base).distinct()) if w is not None)
    monotonic: Optional[bool] = None
    if n:
        sub = select(Telemetry.t_sim_s.label("t"),
                     func.lag(Telemetry.t_sim_s).over(order_by=(Telemetry.server_rx_time, Telemetry.id)).label("p")
                     ).where(*base).subquery()
        drops = db.scalar(select(func.count()).select_from(sub).where(sub.c.p.is_not(None), sub.c.t < sub.c.p)) or 0
        monotonic = drops == 0
    first, last = utc(first), utc(last)
    return ReplayMeta(
        voyage_id=voyage.voyage_id, device_id=voyage.device_id, status=voyage.status, source_modes=modes,
        total_samples=n, window_samples=window_n, boots=boots, first_sample_at=first, last_sample_at=last,
        duration_wall_s=(last - first).total_seconds() if first and last else None,
        t_sim_min_s=tmin, t_sim_max_s=tmax, t_sim_monotonic=monotonic, timewarps=[int(w) for w in warps])


def _tele(t: Telemetry) -> ReplayTelemetry:
    return ReplayTelemetry(
        boot_id=t.boot_id, seq=t.seq, t_sim_s=t.t_sim_s, timewarp=t.timewarp or 1,
        server_rx_time=utc(t.server_rx_time), source_mode=t.source_mode, sensor_ok=t.sensor_ok,
        scenario_id=t.scenario_id, roll_deg=t.roll_deg, pitch_deg=t.pitch_deg, rms_roll_deg=t.rms_roll_deg,
        heel_offset_deg=t.heel_offset_deg, trend_rms_deg_per_min=t.trend_rms_deg_per_min,
        class_rf=t.class_rf, class_baseline_b=t.class_baseline_b, mai=t.mai, alarm_level=t.alarm_level,
        model_version=t.model_version, config_version=t.config_version)


def _alarm_out(a: Alarm) -> AlarmOut:
    out = AlarmOut.model_validate(a)  # DB co the tra datetime khong mui gio -> chuan hoa ve UTC de dong nhat voi phan con lai
    return out.model_copy(update={k: utc(getattr(out, k)) for k in ("opened_at", "acked_at", "cleared_at", "labeled_at")})


def build_replay(db: Session, voyage: Voyage, f: Filters, limit: int, cursor: Optional[str]) -> ReplayResponse:
    validate_filters(f)
    cur = decode_cursor(cursor) if cursor else None

    q = select(Telemetry).where(*_base(voyage), *_filter_conditions(f))
    if cur:
        rx, rid = cur
        q = q.where(or_(Telemetry.server_rx_time > rx, and_(Telemetry.server_rx_time == rx, Telemetry.id > rid)))
    rows = list(db.scalars(q.order_by(Telemetry.server_rx_time, Telemetry.id).limit(limit + 1)))
    truncated = len(rows) > limit
    rows = rows[:limit]

    # Khoang thoi gian server cua trang nay, dung de chia deu canh bao/su kien/lenh giua cac trang
    first_rx = utc(rows[0].server_rx_time) if rows else None
    last_rx = utc(rows[-1].server_rx_time) if rows else None
    if cur:
        lo, lo_inclusive = cur[0], False                  # trang truoc da bao gom den ca moc cur.rx
    elif f.uses_time:
        lo, lo_inclusive = (utc(f.from_time) if f.from_time else None), True
    elif f.uses_t_sim:
        lo, lo_inclusive = first_rx, True                 # truc t_sim: khoang cua cac mau tra ve
    else:
        lo, lo_inclusive = None, True
    if truncated:
        hi = last_rx
    elif f.uses_time:
        hi = utc(f.to_time) if f.to_time else None
    elif f.uses_t_sim:
        hi = last_rx
    else:
        hi = None
    nothing_to_join = f.uses_t_sim and not rows and not cur   # cua so t_sim rong: khong co moc server de gioi han

    events: list[AlarmEvent] = []
    alarms: list[Alarm] = []
    commands: list[Command] = []
    if not nothing_to_join:
        ev_q = (select(AlarmEvent)
                .join(Alarm, and_(Alarm.device_id == AlarmEvent.device_id, Alarm.boot_id == AlarmEvent.boot_id,
                                  Alarm.alarm_id == AlarmEvent.alarm_id))
                .where(Alarm.voyage_id == voyage.voyage_id, AlarmEvent.device_id == voyage.device_id,
                       *_window(AlarmEvent.server_rx_time, lo, lo_inclusive, hi))
                .order_by(AlarmEvent.server_rx_time, AlarmEvent.id))
        events = list(db.scalars(ev_q))
        al_q = select(Alarm).where(Alarm.device_id == voyage.device_id, Alarm.voyage_id == voyage.voyage_id)
        if hi is not None:
            al_q = al_q.where(Alarm.opened_at <= hi)
        if lo is not None:
            al_q = al_q.where(or_(Alarm.cleared_at.is_(None), Alarm.cleared_at >= lo))
        alarms = list(db.scalars(al_q.order_by(Alarm.opened_at, Alarm.id)))
        cmd_q = (select(Command).where(Command.device_id == voyage.device_id,
                                       *_window(Command.created_at, lo, lo_inclusive, hi))
                 .order_by(Command.created_at, Command.id))
        commands = list(db.scalars(cmd_q))

    return ReplayResponse(
        meta=_meta(db, voyage, f),
        telemetry=[_tele(t) for t in rows],
        alarm_events=[ReplayAlarmEvent(
            boot_id=e.boot_id, seq=e.seq, alarm_id=e.alarm_id, level=e.level, prev_level=e.prev_level,
            motion_class=e.motion_class, t_sim_s=e.t_sim_s, acked_by=e.acked_by,
            server_rx_time=utc(e.server_rx_time)) for e in events],
        alarms=[_alarm_out(a) for a in alarms],
        commands=[ReplayCommand(
            cmd_id=c.cmd_id, cmd=c.cmd, params=c.params, state=c.state, issued_by=c.issued_by, reason=c.reason,
            created_at=utc(c.created_at), finished_at=utc(c.finished_at)) for c in commands],
        limit=limit, truncated=truncated,
        next_cursor=encode_cursor(rows[-1].server_rx_time, rows[-1].id) if truncated else None)
