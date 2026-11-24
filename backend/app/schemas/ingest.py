from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RecentError(BaseModel):
    ts: datetime
    topic: Optional[str] = None
    device_id: Optional[str] = None
    kind: Optional[str] = None
    outcome: str                      # INVALID | REJECTED
    reason: Optional[str] = None      # tai sao bi tu choi (de M1 sua firmware ma khong phai doc log)


class IngestRates(BaseModel):
    """Ty le tren TONG so ban tin da nhan; None khi chua co ban tin nao (khong phai 0)."""
    stored: Optional[float] = None
    duplicate: Optional[float] = None
    invalid: Optional[float] = None
    rejected: Optional[float] = None
    ignored: Optional[float] = None


class IngestStatsOut(BaseModel):
    since: datetime                   # tinh tu luc khoi dong hoac lan reset gan nhat
    total_messages: int
    totals: dict[str, int]            # theo ket qua: STORED, DUPLICATE, INVALID, REJECTED, IGNORED
    rates: IngestRates
    by_kind: dict[str, dict[str, int]]
    by_device: dict[str, dict[str, int]]
    recent_errors: list[RecentError]  # toi da 50, moi nhat truoc
    note: str = ("Bo dem nam trong bo nho tien trinh: mat khi khoi dong lai, khong chia se giua nhieu worker. "
                 "Ti le nhan theo tung chuyen (dua tren seq) xem trong bao cao chuyen di.")
