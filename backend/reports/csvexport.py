"""Xuat CSV telemetry / canh bao cua mot chuyen di.

- Dinh dang xac dinh (deterministic): cung du lieu -> cung byte -> cung SHA-256 (dung lam 'dau van tay' cho T11).
- Chong CSV/Formula injection: chuoi do thiet bi gui bat dau bang = + - @ (hoac tab/CR) duoc chen dau ' de
  Excel/Sheets khong thuc thi thanh cong thuc.
- Streaming: khong nap ca bang vao bo nho; moi generator tu mo Session rieng (session cua request da dong
  truoc khi response streaming bat dau).
"""
import csv
import io
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterator, Optional

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Alarm, Telemetry

BOM = "﻿"  # de Excel doc dung UTF-8
YIELD_PER = 500

TELEMETRY_COLUMNS = [
    "device_id", "boot_id", "seq", "server_rx_time", "t_sim_s", "source_mode", "scenario_id", "voyage_id",
    "roll_deg", "pitch_deg", "rms_roll_deg", "heel_offset_deg", "trend_rms_deg_per_min",
    "class_rf", "class_baseline_b", "mai", "alarm_level", "sensor_ok", "model_version", "config_version",
]
ALARM_COLUMNS = [
    "id", "alarm_id", "device_id", "boot_id", "voyage_id", "state", "level", "max_level", "motion_class",
    "source_mode", "opened_at", "acked_at", "acked_by", "time_to_ack_s", "cleared_at", "escalated",
    "label", "labeled_by", "labeled_at",
]
_DANGEROUS_PREFIX = ("=", "+", "-", "@", "\t", "\r")


def utc(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite tra datetime khong mui gio; moi gia tri trong he thong deu la UTC."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, Enum):
        return str(v.value)
    if isinstance(v, datetime):
        return utc(v).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, str):
        return "'" + v if v.startswith(_DANGEROUS_PREFIX) else v
    return str(v)


def _line(values: list[Any]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\r\n").writerow([_cell(v) for v in values])
    return buf.getvalue()


def header_line(columns: list[str]) -> str:
    return BOM + _line(columns)  # BOM nam o dau file, ngay truoc dong tieu de


def telemetry_line(t: Telemetry) -> str:
    return _line([getattr(t, c) for c in TELEMETRY_COLUMNS])


def telemetry_query(device_id: str, voyage_id: str):
    return (select(Telemetry).where(Telemetry.device_id == device_id, Telemetry.voyage_id == voyage_id)
            .order_by(Telemetry.server_rx_time, Telemetry.id).execution_options(yield_per=YIELD_PER))


def iter_telemetry_csv(device_id: str, voyage_id: str) -> Iterator[str]:
    yield header_line(TELEMETRY_COLUMNS)
    with SessionLocal() as db:
        for (t,) in db.execute(telemetry_query(device_id, voyage_id)):
            yield telemetry_line(t)


def _time_to_ack(a: Alarm) -> Optional[float]:
    if a.acked_at is None:
        return None
    return (utc(a.acked_at) - utc(a.opened_at)).total_seconds()


def iter_alarms_csv(device_id: str, voyage_id: str) -> Iterator[str]:
    yield header_line(ALARM_COLUMNS)
    q = (select(Alarm).where(Alarm.device_id == device_id, Alarm.voyage_id == voyage_id)
         .order_by(Alarm.opened_at, Alarm.id).execution_options(yield_per=YIELD_PER))
    with SessionLocal() as db:
        for (a,) in db.execute(q):
            row = [getattr(a, c) if c != "time_to_ack_s" else _time_to_ack(a) for c in ALARM_COLUMNS]
            yield _line(row)
