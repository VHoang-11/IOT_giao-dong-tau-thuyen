"""Cong gui MQTT cho command/config service.

Tach thanh 'interface' de: (1) test dung ban gia, khong can broker; (2) service khong phu thuoc paho.
Consumer (ingest/consumer.py) dang ky implementation that khi khoi dong.
"""
from typing import Callable, Optional, Protocol


class PublishFailed(Exception):
    """Khong gui duoc toi broker (HTTP 503)."""


class Publisher(Protocol):
    def publish(self, topic: str, payload: str, qos: int = 1, retain: bool = False,
                on_delivered: Optional[Callable[[], None]] = None) -> None:
        """Gui ban tin. on_delivered duoc goi khi broker xac nhan (PUBACK). Loi -> PublishFailed."""


_publisher: Optional[Publisher] = None


def set_publisher(p: Optional[Publisher]) -> None:
    global _publisher
    _publisher = p


def get_publisher() -> Publisher:
    if _publisher is None:
        raise PublishFailed("Kênh MQTT chưa sẵn sàng")
    return _publisher
