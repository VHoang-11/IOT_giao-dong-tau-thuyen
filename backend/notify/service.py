"""Thong bao Telegram / email webhook (M3-08).

NGUYEN TAC:
- KHONG BAO GIO chan luong xu ly MQTT: gui o luong nen, loi chi ghi log (khong nem exception).
- KHONG ghi token/URL vao log: URL Telegram chua BOT TOKEN va str(HTTPStatusError) co ca URL
  -> chi log ten kenh, loai thong bao, ten loai loi va ma HTTP.
- Moi tin nhan gan nhan SENSOR/SIMULATION; khong dung cum 'du bao lat tau'.
- Chong spam: cung (loai, thiet bi, canh bao) khong gui lai trong notify_cooldown_s.
"""
import logging
import threading
import time
from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional, Protocol

import httpx

from app.core.config import settings

log = logging.getLogger("svmg.notify")

MAX_TEXT = 4000  # Telegram gioi han 4096 ky tu
MAX_COOLDOWN_KEYS = 1000
_FOOTER = {
    "SIMULATION": "Dữ liệu MÔ PHỎNG — chỉ phục vụ đồ án.",
    "SENSOR": "Dữ liệu từ cảm biến — nguyên mẫu nghiên cứu, không phải hệ thống an toàn hàng hải.",
}


@dataclass
class Message:
    kind: str                       # ALARM_CRITICAL | ALARM_ESCALATED | ALARM_REACTIVATED | DEVICE_OFFLINE | TEST
    title: str
    text: str
    device_id: Optional[str] = None
    source_mode: str = "SIMULATION"
    alarm_id: Optional[str] = None
    level: Optional[str] = None


class Channel(Protocol):
    name: str

    def configured(self) -> bool: ...
    def send(self, client: httpx.Client, msg: Message) -> None: ...


class SendError(Exception):
    """Loi gui da duoc lam sach (khong chua URL/token)."""


class TelegramChannel:
    name = "telegram"

    def configured(self) -> bool:
        return bool(settings.telegram_bot_token and settings.telegram_chat_id)

    def send(self, client: httpx.Client, msg: Message) -> None:
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        try:
            r = client.post(url, json={"chat_id": settings.telegram_chat_id, "text": _compose(msg),
                                       "disable_web_page_preview": True})  # khong parse_mode -> khong bi chen markup
            ok = r.status_code == 200 and r.json().get("ok") is True
        except httpx.HTTPError as e:
            raise SendError(type(e).__name__) from None  # from None: bo chuoi exception co the chua URL
        except ValueError:
            raise SendError("invalid_response") from None
        if not ok:
            raise SendError(f"http_{r.status_code}")


class EmailWebhookChannel:
    name = "email_webhook"

    def configured(self) -> bool:
        return bool(settings.email_webhook_url)

    def send(self, client: httpx.Client, msg: Message) -> None:
        payload = {"subject": msg.title, "text": _compose(msg), "kind": msg.kind, "level": msg.level,
                   "device_id": msg.device_id, "alarm_id": msg.alarm_id, "source_mode": msg.source_mode,
                   "ts": datetime.now(timezone.utc).isoformat()}
        try:
            r = client.post(settings.email_webhook_url, json=payload)
        except httpx.HTTPError as e:
            raise SendError(type(e).__name__) from None
        if not 200 <= r.status_code < 300:
            raise SendError(f"http_{r.status_code}")


def _compose(msg: Message) -> str:
    text = f"[SVMG][{msg.source_mode}] {msg.title}\n{msg.text}\n{_FOOTER.get(msg.source_mode, '')}"
    return text[:MAX_TEXT]


class Dispatcher:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.stats: Counter = Counter()
        self._lock = threading.Lock()
        self._last: dict[tuple, float] = {}
        self._pending: set[Future] = set()
        self._pool: Optional[ThreadPoolExecutor] = None
        self._client: Optional[httpx.Client] = None
        self.channels: list[Channel] = [TelegramChannel(), EmailWebhookChannel()]

    # ---- test hook ----
    def set_client(self, client: Optional[httpx.Client]) -> None:
        self._client = client

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=settings.notify_timeout_s)
        return self._client

    def active_channels(self) -> list[Channel]:
        return [c for c in self.channels if c.configured()]

    def submit(self, msg: Message, bypass_cooldown: bool = False) -> bool:
        """Dua vao hang doi gui nen. Tra ve True neu duoc nhan (co kenh + khong bi cooldown)."""
        chans = self.active_channels()
        if not chans:
            return False
        key = (msg.kind, msg.device_id, msg.alarm_id)
        now = self.clock()
        with self._lock:
            last = self._last.get(key)
            if not bypass_cooldown and last is not None and now - last < settings.notify_cooldown_s:
                self.stats["suppressed"] += 1
                return False
            self._last[key] = now
            if len(self._last) > MAX_COOLDOWN_KEYS:
                # muc het cooldown khong con tac dung -> don de bang khong phinh mai theo so canh bao
                cutoff = now - settings.notify_cooldown_s
                self._last = {k: t for k, t in self._last.items() if t > cutoff}
            if self._pool is None:
                self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="notify")
            fut = self._pool.submit(self._deliver, msg, chans)
            self._pending.add(fut)
        fut.add_done_callback(self._done)
        return True

    def _done(self, fut: Future) -> None:
        with self._lock:
            self._pending.discard(fut)

    def _deliver(self, msg: Message, chans: list[Channel]) -> dict[str, str]:
        results: dict[str, str] = {}
        for ch in chans:
            results[ch.name] = self._send_with_retry(ch, msg)
        return results

    def _send_with_retry(self, ch: Channel, msg: Message) -> str:
        err = "unknown"
        for attempt in range(settings.notify_retries + 1):
            try:
                ch.send(self._http(), msg)
                self.stats[f"{ch.name}.sent"] += 1
                return "ok"
            except SendError as e:
                err = str(e)
            except Exception as e:  # khong bao gio de loi cua kenh thong bao lan ra ngoai
                err = type(e).__name__
            if attempt < settings.notify_retries:
                time.sleep(settings.notify_backoff_s * (2 ** attempt))
        self.stats[f"{ch.name}.failed"] += 1
        log.warning("notify failed", extra={"channel": ch.name, "kind": msg.kind, "error": err})
        return f"failed: {err}"

    def send_now(self, msg: Message) -> dict[str, str]:
        """Gui dong bo (dung cho /notify/test de bao ket qua tung kenh)."""
        return self._deliver(msg, self.active_channels())

    def wait_idle(self, timeout: float = 5.0) -> None:
        with self._lock:
            pending = list(self._pending)
        wait(pending, timeout=timeout)

    def shutdown(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=False)
            self._pool = None


dispatcher = Dispatcher()


# ---------- tao thong diep ----------

def alarm_message(kind: str, alarm) -> Message:
    lvl = alarm.level.value
    cls = alarm.motion_class.value if alarm.motion_class else "chưa rõ"
    where = f"{alarm.device_id} · cảnh báo {alarm.alarm_id}"
    if kind == "ALARM_CRITICAL":
        title, text = f"CRITICAL — {alarm.device_id}", (
            f"{where}: mức CRITICAL (lớp chuyển động: {cls}). Cần người trực xác nhận trên dashboard.")
    elif kind == "ALARM_ESCALATED":
        title, text = f"Cảnh báo chưa xác nhận — {alarm.device_id}", (
            f"{where}: mức {lvl} chưa có ai xác nhận sau {settings.alarm_escalate_after_s}s (lớp: {cls}).")
    else:  # ALARM_REACTIVATED
        title, text = f"Cảnh báo nặng hơn — {alarm.device_id}", (
            f"{where}: đã xác nhận nhưng mức tăng lên {lvl} (lớp: {cls}). Cần xác nhận lại.")
    return Message(kind=kind, title=title, text=text, device_id=alarm.device_id,
                   source_mode=alarm.source_mode.value, alarm_id=alarm.alarm_id, level=lvl)


def notify_alarm(kind: str, alarm) -> None:
    """Goi tu alarm service. Khong bao gio nem exception."""
    try:
        dispatcher.submit(alarm_message(kind, alarm))
    except Exception:
        log.exception("notify_alarm failed", extra={"kind": kind})


def notify_device_offline(device_id: str, source_mode: str) -> None:
    try:
        dispatcher.submit(Message(
            kind="DEVICE_OFFLINE", title=f"Thiết bị mất kết nối — {device_id}",
            text=f"{device_id} đã ngắt kết nối (LWT offline). Cảnh báo cục bộ trên thiết bị vẫn hoạt động độc lập.",
            device_id=device_id, source_mode=source_mode))
    except Exception:
        log.exception("notify_device_offline failed")
