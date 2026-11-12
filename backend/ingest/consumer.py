"""MQTT consumer (paho-mqtt 2.x). Tu dong ket noi lai; subscribe lai moi lan connect."""
import logging
from typing import Optional

import paho.mqtt.client as mqtt

from app.core.config import settings
from app.core.db import SessionLocal
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
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.connected = False

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

    def stop(self) -> None:
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
