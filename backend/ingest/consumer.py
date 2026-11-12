"""MQTT consumer (paho-mqtt 2.x). Tu dong ket noi lai; subscribe lai moi lan connect."""
import logging
import threading
from typing import Callable, Optional

import paho.mqtt.client as mqtt

from app.core.config import settings
from app.core.db import SessionLocal
from commands.publisher import PublishFailed, set_publisher
from ingest.service import SUBSCRIPTIONS, handle_message

log = logging.getLogger("svmg.ingest")


class MqttConsumer:
    def __init__(self) -> None:
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="svmg-backend-ingest")
        if settings.mqtt_user:
            self.client.username_pw_set(settings.mqtt_user, settings.mqtt_pass)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.connected = False
        self._lock = threading.Lock()
        self._callbacks: dict[int, Callable[[], None]] = {}  # mid -> on_delivered
        self._early: set[int] = set()                         # PUBACK ve truoc khi dang ky callback

    # ---- Publisher (commands/publisher.py) ----
    def publish(self, topic: str, payload: str, qos: int = 1, retain: bool = False,
                on_delivered: Optional[Callable[[], None]] = None) -> None:
        # AN TOAN: khong de paho xep hang khi mat ket noi - lenh se toi thiet bi qua han TTL
        # va thiet bi (dem TTL tu luc nhan) van thuc thi muon.
        if not self.connected:
            raise PublishFailed("Chưa kết nối tới MQTT broker")
        info = self.client.publish(topic, payload, qos=qos, retain=retain)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise PublishFailed(f"publish lỗi rc={info.rc}")
        if on_delivered is None:
            return
        with self._lock:
            fire = info.mid in self._early
            if fire:
                self._early.discard(info.mid)
            else:
                self._callbacks[info.mid] = on_delivered
        if fire:
            on_delivered()

    def _on_publish(self, client, userdata, mid, reason_code=None, properties=None):
        with self._lock:
            cb = self._callbacks.pop(mid, None)
            if cb is None:
                if len(self._early) > 1000:  # chan ro ri bo nho
                    self._early.clear()
                self._early.add(mid)
        if cb is not None:
            cb()

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code.is_failure:
            log.error("mqtt connect failed", extra={"reason": str(reason_code)})
            return
        self.connected = True
        client.subscribe(SUBSCRIPTIONS)  # subscribe lai sau moi lan reconnect
        log.info("mqtt connected", extra={"broker": settings.mqtt_broker})

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self.connected = False
        log.warning("mqtt disconnected", extra={"reason": str(reason_code)})

    def _on_message(self, client, userdata, msg):
        db = SessionLocal()
        try:
            handle_message(db, msg.topic, msg.payload)
        except Exception:  # loi bat ngo khong duoc lam chet vong lap MQTT
            db.rollback()
            log.exception("ingest error", extra={"topic": msg.topic})
        finally:
            db.close()

    def start(self) -> None:
        self.client.connect_async(settings.mqtt_broker, settings.mqtt_port, keepalive=30)
        self.client.loop_start()
        set_publisher(self)  # command/config service gui qua cung ket noi nay

    def stop(self) -> None:
        set_publisher(None)
        self.client.loop_stop()
        self.client.disconnect()


consumer: Optional[MqttConsumer] = None


def start_consumer() -> None:
    global consumer
    consumer = MqttConsumer()
    consumer.start()


def stop_consumer() -> None:
    if consumer is not None:
        consumer.stop()
