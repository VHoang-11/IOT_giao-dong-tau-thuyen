"""Bo dem ban tin MQTT (cho T06 'phuc hoi mang' va T14 'doi tau, chiu tai'): ty le nhan / trung / loi.

- An toan da luong: luong MQTT ghi, luong API doc.
- Gioi han bo nho: so thiet bi theo doi toi da MAX_DEVICES (vuot -> gop vao '_other'); chi giu MAX_RECENT loi gan nhat.
  Neu khong, ke gui hang trieu device_id gia se lam day RAM.
- Nam trong bo nho tien trinh: mat khi khoi dong lai va khong chia se giua nhieu worker (ghi ro trong README).
"""
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

MAX_DEVICES = 1000
MAX_RECENT = 50
MAX_REASON = 200
OVERFLOW_DEVICE = "_other"
UNKNOWN_DEVICE = "_unknown"   # ban tin co topic sai nen khong biet thiet bi
BAD_OUTCOMES = {"INVALID", "REJECTED"}


class IngestStats:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.since = datetime.now(timezone.utc)
            self.by_kind: dict[str, dict[str, int]] = {}
            self.by_device: dict[str, dict[str, int]] = {}
            self.recent: deque[dict[str, Any]] = deque(maxlen=MAX_RECENT)

    def add(self, kind: Optional[str], outcome: str, device_id: Optional[str], topic: Optional[str] = None,
            reason: Optional[str] = None) -> None:
        kind = kind or "unknown"
        with self._lock:
            k = self.by_kind.setdefault(kind, {})
            k[outcome] = k.get(outcome, 0) + 1
            dev = device_id or UNKNOWN_DEVICE
            if dev not in self.by_device and len(self.by_device) >= MAX_DEVICES:
                dev = OVERFLOW_DEVICE
            d = self.by_device.setdefault(dev, {})
            d[outcome] = d.get(outcome, 0) + 1
            if outcome in BAD_OUTCOMES:
                self.recent.append({"ts": datetime.now(timezone.utc), "topic": (topic or "")[:128] or None,
                                    "device_id": device_id, "kind": kind, "outcome": outcome,
                                    "reason": (reason or "")[:MAX_REASON] or None})

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            by_kind = {k: dict(v) for k, v in sorted(self.by_kind.items())}
            by_device = {k: dict(v) for k, v in sorted(self.by_device.items())}
            recent = list(self.recent)
            since = self.since
        totals: dict[str, int] = {}
        for outcomes in by_kind.values():
            for o, n in outcomes.items():
                totals[o] = totals.get(o, 0) + n
        total = sum(totals.values())
        return {"since": since, "total_messages": total, "totals": totals, "by_kind": by_kind,
                "by_device": by_device, "recent_errors": recent[::-1]}   # moi nhat truoc


stats = IngestStats()
