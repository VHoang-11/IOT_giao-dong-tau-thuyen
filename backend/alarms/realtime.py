"""Phat thoi gian thuc qua WebSocket.

Consumer MQTT (paho) chay tren luong rieng, WebSocket chay tren event loop cua FastAPI,
nen publish() dung run_coroutine_threadsafe de chuyen tin an toan giua hai luong.
"""
import asyncio
import logging
from typing import Any, Optional

from fastapi import WebSocket

log = logging.getLogger("svmg.realtime")


class AlarmHub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def _broadcast(self, message: dict[str, Any]) -> None:
        for ws in list(self.clients):
            try:
                await ws.send_json(message)
            except Exception:  # client da dong -> bo ra khoi danh sach
                self.clients.discard(ws)

    def publish(self, message: dict[str, Any]) -> None:
        """Goi duoc tu bat ky luong nao. Khong co client/loop thi bo qua."""
        if self.loop is None or not self.clients:
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(message), self.loop)


hub = AlarmHub()
