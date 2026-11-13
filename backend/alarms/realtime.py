"""Phat thoi gian thuc qua WebSocket.

Consumer MQTT (paho) chay tren luong rieng, WebSocket chay tren event loop cua FastAPI,
nen publish() dung run_coroutine_threadsafe de chuyen tin an toan giua hai luong.
"""
import asyncio
import logging
from contextlib import suppress
from typing import Any, Optional

from fastapi import WebSocket

log = logging.getLogger("svmg.realtime")


class AlarmHub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.send_timeout_s: float = 2.0

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def _send(self, ws: WebSocket, message: dict[str, Any]) -> None:
        try:
            await asyncio.wait_for(ws.send_json(message), timeout=self.send_timeout_s)
        except Exception:  # client da dong HOAC qua cham -> loai ra, khong de anh huong client khac
            self.clients.discard(ws)
            with suppress(Exception):
                await asyncio.wait_for(ws.close(), timeout=1.0)

    async def _broadcast(self, message: dict[str, Any]) -> None:
        # Gui SONG SONG: truoc day gui tuan tu, 1 client treo la canh bao CRITICAL khong toi duoc ai.
        await asyncio.gather(*(self._send(ws, message) for ws in list(self.clients)))

    def publish(self, message: dict[str, Any]) -> None:
        """Goi duoc tu bat ky luong nao. Khong co client/loop thi bo qua."""
        if self.loop is None or not self.clients:
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(message), self.loop)


hub = AlarmHub()
