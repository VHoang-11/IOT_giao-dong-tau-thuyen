"""Tich hop MQTT THAT: consumer.py (code that cua backend) <-> broker (TCP that) <-> 'thiet bi' dung paho.

Khong can Docker: dung broker MQTT thuan Python `amqtt` chay trong test (cai trong requirements-dev.txt; thieu thi
ca file nay tu bo qua). Phu cac duong ma test don vi KHONG cham toi: ket noi, subscribe, nhan tin, PUBACK, LWT,
retained, ket noi lai, tu choi gui lenh khi mat ket noi.

Du lieu trong file nay la payload kiem thu toi thieu, chi song trong test (DB file tam, bi xoa sau test).
"""
import asyncio
import json
import logging
import socket
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("amqtt", reason="cai amqtt (requirements-dev.txt) de chay test tich hop MQTT that")

import paho.mqtt.client as mqtt  # noqa: E402
from amqtt.broker import Broker  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import Base, build_engine  # noqa: E402
from app.models import Alarm, Command, Device, DeviceConfigVersion, Telemetry  # noqa: E402
from app.models.enums import CommandName, CommandState, DeviceState  # noqa: E402
from commands import config_service, service as cmd_service  # noqa: E402
from commands.publisher import PublishFailed  # noqa: E402
from ingest import consumer as consumer_mod  # noqa: E402
from ingest.stats import stats  # noqa: E402
from ingest.validator import validate  # noqa: E402

for noisy in ("amqtt", "transitions", "asyncio"):
    logging.getLogger(noisy).setLevel(logging.ERROR)

EX = Path(__file__).resolve().parents[2] / "contracts" / "examples"
DEV = "vessel-demo-01"


# ---------------------------------------------------------------- ha tang test

def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class BrokerThread:
    """Broker amqtt chay tren event loop rieng. Co the stop() roi start() lai tren cung cong (thu ket noi lai)."""

    def __init__(self, port: int):
        self.port = port
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        self.broker = None

    def _config(self):
        return {"listeners": {"default": {"type": "tcp", "bind": f"127.0.0.1:{self.port}"}}, "sys_interval": 0,
                "auth": {"allow-anonymous": True, "plugins": ["auth_anonymous"]}, "topic-check": {"enabled": False}}

    def start(self):
        async def go():
            self.broker = Broker(self._config())
            await self.broker.start()
        asyncio.run_coroutine_threadsafe(go(), self.loop).result(15)

    def stop(self):
        if self.broker is not None:
            asyncio.run_coroutine_threadsafe(self.broker.shutdown(), self.loop).result(15)
            self.broker = None

    def close(self):
        self.stop()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(5)


def eventually(fn, timeout=10.0, interval=0.05, what="dieu kien"):
    end = time.monotonic() + timeout
    last = None
    while time.monotonic() < end:
        last = fn()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f"het {timeout}s ma chua thay: {what} (gia tri cuoi: {last!r})")


class FakeDevice:
    """Thiet bi ESP32 gia (paho): gui telemetry/event/status/ack, nhan cmd va config."""

    def __init__(self, port: int, dev: str = DEV, will: bool = False, client_id: str = None):
        self.dev, self.port = dev, port
        self.cmds: list[dict] = []
        self.configs: list[tuple[dict, bool]] = []   # (payload, retain)
        self.log: list[tuple[str, dict, bool]] = []  # moi tin nhan nhan duoc (topic, payload, retain) de chan doan
        self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id or f"fake-{dev}")
        if will:
            self.c.will_set(f"svmg/{dev}/status", json.dumps({"state": "offline"}), qos=1, retain=True)
        self.c.on_connect = lambda c, u, f, rc, p=None: c.subscribe([(f"svmg/{dev}/cmd", 1), (f"svmg/{dev}/config", 1)])
        self.c.on_message = self._on_message
        self.c.connect("127.0.0.1", port)
        self.c.loop_start()
        time.sleep(0.5)  # cho SUBACK

    def _on_message(self, c, u, msg):
        data = json.loads(msg.payload)
        self.log.append((msg.topic, data, msg.retain))
        if msg.topic.endswith("/cmd"):
            self.cmds.append(data)
        elif msg.topic.endswith("/config"):
            self.configs.append((data, msg.retain))

    def pub(self, kind: str, payload, qos: int = 0, raw: bool = False):
        body = payload if raw else json.dumps(payload)
        info = self.c.publish(f"svmg/{self.dev}/{kind}", body, qos=qos)
        info.wait_for_publish(5)

    def drop(self):
        """Mat mang dot ngot (khong gui DISCONNECT) -> broker phat LWT."""
        self.c._sock.shutdown(socket.SHUT_RDWR)
        self.c._sock.close()
        self.c.loop_stop()

    def close(self):
        self.c.loop_stop()
        try:
            self.c.disconnect()
        except Exception:
            pass


def tele(seq, dev=DEV, **over):
    p = json.loads((EX / "telemetry_sample.json").read_text(encoding="utf-8"))
    p.update(device_id=dev, seq=seq, **over)
    return p


def event(seq, level, alarm_id="A-1", dev=DEV):
    return {"device_id": dev, "boot_id": "a3f9", "seq": seq, "type": "ALARM_STATE", "alarm_id": alarm_id,
            "level": level, "class": "HIGH_ROLL", "t_sim_s": float(seq)}


@pytest.fixture()
def broker():
    """Moi test mot broker MOI: tin retained (vd. LWT 'offline') cua test truoc khong ro ri sang test sau."""
    b = BrokerThread(free_port())
    b.start()
    yield b
    b.close()


@pytest.fixture()
def sess(tmp_path, monkeypatch):
    """DB file tam (WAL) dung chung giua luong MQTT cua consumer va luong test."""
    engine = build_engine(f"sqlite:///{tmp_path / 'integration.db'}")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(consumer_mod, "SessionLocal", maker)
    monkeypatch.setattr(cmd_service, "SessionLocal", maker)
    stats.reset()
    yield maker
    engine.dispose()


def start_backend(port: int, monkeypatch) -> consumer_mod.MqttConsumer:
    monkeypatch.setattr(settings, "mqtt_broker", "127.0.0.1")
    monkeypatch.setattr(settings, "mqtt_port", port)
    monkeypatch.setattr(settings, "mqtt_user", "")
    monkeypatch.setattr(settings, "mqtt_tls", False)
    c = consumer_mod.MqttConsumer()
    c.start()
    eventually(lambda: c.connected, what="backend ket noi broker")
    time.sleep(0.5)  # cho SUBACK cua cac topic svmg/+/...
    return c


@pytest.fixture()
def backend(broker, sess, monkeypatch):
    c = start_backend(broker.port, monkeypatch)
    yield c
    c.stop()


@pytest.fixture()
def device(broker, backend):
    d = FakeDevice(broker.port)
    yield d
    d.close()


def one(sess, stmt):
    with sess() as db:
        return db.scalar(stmt)


def rows(sess, model):
    with sess() as db:
        return list(db.scalars(select(model)))


# ---------------------------------------------------------------- nhan du lieu qua mang that

def test_telemetry_travels_through_real_broker_into_database(device, sess):
    device.pub("telemetry", tele(1))
    t = eventually(lambda: one(sess, select(Telemetry)), what="telemetry duoc luu")
    assert (t.device_id, t.boot_id, t.seq, t.source_mode.value) == (DEV, "a3f9", 1, "SIMULATION")
    assert t.server_rx_time is not None and t.roll_deg == 8.4
    dev = one(sess, select(Device))
    assert dev.device_id == DEV and dev.last_seen is not None                    # tu dang ky + last_seen
    assert stats.snapshot()["by_kind"]["telemetry"] == {"STORED": 1}


def test_alarm_lifecycle_driven_by_events_over_mqtt(device, sess):
    device.pub("telemetry", tele(1))
    device.pub("event", event(2, "WARNING"), qos=1)
    a = eventually(lambda: one(sess, select(Alarm)), what="canh bao duoc mo")
    assert a.level.value == "WARNING" and a.state.value == "ACTIVE" and a.alarm_id == "A-1"
    device.pub("event", event(3, "NORMAL"), qos=1)
    eventually(lambda: one(sess, select(Alarm)).state.value == "CLEARED", what="canh bao giai toa")


def test_resend_after_outage_is_idempotent_T06(device, sess):
    """Thiet bi gui seq 1-10, mat mang, roi gui lai toan bo bo dem seq 1-20: dung 20 ban ghi, 10 ban tin bi coi la trung."""
    for i in range(1, 11):
        device.pub("telemetry", tele(i))
    eventually(lambda: len(rows(sess, Telemetry)) == 10, what="10 ban tin dau")
    for i in range(1, 21):
        device.pub("telemetry", tele(i))
    eventually(lambda: len(rows(sess, Telemetry)) == 20, what="du 20 ban tin sau khi gui lai")
    eventually(lambda: stats.snapshot()["by_kind"]["telemetry"].get("DUPLICATE") == 10, what="10 ban tin trung duoc dem")
    assert sorted(t.seq for t in rows(sess, Telemetry)) == list(range(1, 21))
    assert stats.snapshot()["by_kind"]["telemetry"]["STORED"] == 20


def test_bad_foreign_and_oversized_payloads_are_rejected_with_reasons(device, sess):
    device.pub("telemetry", b'{"device_id":"%s","boot_id":"a","seq":1,"t_sim_s":NaN}' % DEV.encode(), raw=True)
    device.pub("telemetry", tele(2, dev="vessel-other"))                         # device_id payload khac topic
    device.pub("telemetry", tele(3, class_rf="CAPSIZE_FORECAST"))
    device.pub("telemetry", tele(4, boot_id="x" * 500))
    device.pub("telemetry", b"{khong phai json", raw=True)
    device.pub("telemetry", tele(5))                                             # hop le -> ban tin DUY NHAT duoc luu
    eventually(lambda: stats.snapshot()["total_messages"] == 6, what="du 6 ban tin duoc xu ly")
    assert [t.seq for t in rows(sess, Telemetry)] == [5]
    totals = stats.snapshot()["totals"]
    assert totals == {"STORED": 1, "INVALID": 4, "REJECTED": 1}
    reasons = " | ".join(e["reason"] for e in stats.snapshot()["recent_errors"])
    assert "khac topic" in reasons and "quá dài" in reasons and "class_rf" in reasons


def test_disabled_device_is_ignored_over_mqtt(device, sess):
    device.pub("telemetry", tele(1))
    eventually(lambda: len(rows(sess, Telemetry)) == 1, what="mau dau duoc luu")
    with sess() as db:
        d = db.scalar(select(Device))
        d.enabled = False
        db.commit()
    device.pub("telemetry", tele(2))
    eventually(lambda: stats.snapshot()["totals"].get("REJECTED") == 1, what="ban tin bi tu choi")
    assert [t.seq for t in rows(sess, Telemetry)] == [1]


def test_consumer_survives_an_internal_error_and_keeps_working(device, sess, monkeypatch):
    real = consumer_mod.handle_message
    monkeypatch.setattr(consumer_mod, "handle_message", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("loi gia lap")))
    device.pub("telemetry", tele(1))
    time.sleep(0.8)
    assert rows(sess, Telemetry) == []                                           # ban tin dau mat (loi), nhung...
    monkeypatch.setattr(consumer_mod, "handle_message", real)
    device.pub("telemetry", tele(2))
    eventually(lambda: [t.seq for t in rows(sess, Telemetry)] == [2], what="consumer van song va xu ly ban tin sau")


# ---------------------------------------------------------------- LWT / status

def test_lwt_marks_device_offline_and_notifies_exactly_once(broker, backend, sess, monkeypatch):
    calls = []
    monkeypatch.setattr("ingest.service.notify_device_offline", lambda dev, mode: calls.append((dev, mode)))
    d = FakeDevice(broker.port, will=True, client_id="lwt-device")
    try:
        d.pub("status", {"state": "online", "fw": "1.0.0", "boot_id": "a3f9", "config_version": 1}, qos=1)
        eventually(lambda: (one(sess, select(Device)) or Device()).state == DeviceState.online, what="thiet bi online")
        d.drop()                                                                  # rot mang dot ngot -> broker phat LWT
        eventually(lambda: one(sess, select(Device)).state == DeviceState.offline, timeout=15, what="LWT lam thiet bi offline")
        time.sleep(0.5)
        assert calls == [(DEV, "SIMULATION")]                                     # chi bao 1 lan (chuyen online -> offline)
        assert one(sess, select(Device)).fw == "1.0.0"                            # thong tin cu duoc giu
    finally:
        d.close()


# ---------------------------------------------------------------- lenh va cau hinh qua mang that

def test_command_round_trip_delivered_then_applied(device, sess):
    device.pub("telemetry", tele(1))
    eventually(lambda: one(sess, select(Device)), what="thiet bi duoc dang ky")
    with sess() as db:
        cmd, created = cmd_service.create_command(db, DEV, CommandName.set_profile, {"profile": "SENSITIVE"}, 30, "sup01")
    assert created
    got = eventually(lambda: device.cmds, what="thiet bi nhan lenh tu broker")[0]
    assert validate("cmd", got) == []                                            # dung hop dong
    assert got["cmd_id"] == cmd.cmd_id and got["params"] == {"profile": "SENSITIVE"} and got["issued_by"] == "sup01"
    eventually(lambda: one(sess, select(Command)).state in (CommandState.DELIVERED, CommandState.APPLIED), what="DELIVERED nho PUBACK that")
    device.pub("cmd/ack", {"cmd_id": cmd.cmd_id, "result": "APPLIED", "config_version": None, "reason": None}, qos=1)
    c = eventually(lambda: (lambda x: x if x.state == CommandState.APPLIED else None)(one(sess, select(Command))),
                   what="lenh APPLIED")
    assert c.delivered_at is not None and c.finished_at >= c.created_at


def test_command_rejected_by_device_is_recorded(device, sess):
    device.pub("telemetry", tele(1))
    eventually(lambda: one(sess, select(Device)), what="dang ky")
    with sess() as db:
        cmd, _ = cmd_service.create_command(db, DEV, CommandName.calibrate_zero, {}, 30, "sup01")
    eventually(lambda: device.cmds, what="nhan lenh")
    device.pub("cmd/ack", {"cmd_id": cmd.cmd_id, "result": "REJECTED", "reason": "FORBIDDEN_STATE"}, qos=1)
    c = eventually(lambda: (lambda x: x if x.state == CommandState.REJECTED else None)(one(sess, select(Command))), what="REJECTED")
    assert c.reason == "FORBIDDEN_STATE"


def test_mute_is_blocked_and_never_reaches_the_device_when_critical(device, sess):
    device.pub("telemetry", tele(1))
    device.pub("event", event(2, "CRITICAL"), qos=1)
    eventually(lambda: one(sess, select(Alarm)), what="canh bao CRITICAL")
    with sess() as db:
        with pytest.raises(cmd_service.CommandBlocked):
            cmd_service.create_command(db, DEV, CommandName.mute_alarm, {}, 30, "op01")
    time.sleep(1.0)
    assert device.cmds == []                                                      # KHONG co lenh nao toi thiet bi


def test_config_is_retained_so_a_device_connecting_later_still_gets_it(broker, device, sess):
    device.pub("telemetry", tele(1))
    eventually(lambda: one(sess, select(Device)), what="dang ky")
    with sess() as db:
        row = config_service.update_config(db, DEV, {"profile": "SENSITIVE", "debounce_n": 2}, "sup01")
    live, retained_flag = eventually(lambda: device.configs, what="thiet bi dang online nhan config")[0]
    assert isinstance(live, dict) and "config_version" in live, f"nhan duoc: {device.log}"
    assert live["config_version"] == row.config_version and live["profile"] == "SENSITIVE" and validate("config", live) == []
    late = FakeDevice(broker.port, client_id="late-device")                       # thiet bi bat sau
    try:
        got, was_retained = eventually(lambda: late.configs, what="config retained toi thiet bi den sau")[0]
        assert was_retained is True and got == live
    finally:
        late.close()
    assert one(sess, select(DeviceConfigVersion)).config_version == row.config_version


# ---------------------------------------------------------------- mat broker / ket noi lai

def test_broker_outage_refuses_commands_instead_of_queueing_and_recovers(sess, monkeypatch):
    b = BrokerThread(free_port())
    b.start()
    backend = start_backend(b.port, monkeypatch)
    dev = FakeDevice(b.port, client_id="outage-device")
    try:
        dev.pub("telemetry", tele(1))
        eventually(lambda: one(sess, select(Telemetry)), what="mau dau")
        b.stop()                                                                   # broker CHET
        eventually(lambda: backend.connected is False, timeout=15, what="backend nhan ra mat ket noi")
        with sess() as db:
            with pytest.raises(PublishFailed):
                cmd_service.create_command(db, DEV, CommandName.restart_device, {}, 30, "admin01", cmd_id="c-outage")
        failed = one(sess, select(Command).where(Command.cmd_id == "c-outage"))
        assert failed.state == CommandState.TIMEOUT and "broker" in failed.reason   # ghi nhan ro, khong im lang
        # paho QoS>0 khi mat ket noi: publish() tra loi NO_CONN nhung van GIU tin trong hang doi noi bo va TU GUI LAI
        # sau khi ket noi lai -> lenh het han van toi thiet bi. Backend phai chan truoc khi goi publish() de hang doi RONG.
        # (Kiem tra truc tiep hang doi, vi thiet bi chua kip subscribe lai nen 'dev.cmds == []' mot minh khong chung minh gi.)
        assert len(backend.client._out_messages) == 0, "lenh dang nam trong hang doi cua paho: se bi gui muon sau khi noi lai"
        b.start()                                                                   # broker song lai tren cung cong
        eventually(lambda: backend.connected, timeout=30, what="backend tu ket noi lai")
        time.sleep(1.0)
        dev.pub("telemetry", tele(2))
        eventually(lambda: sorted(t.seq for t in rows(sess, Telemetry)) == [1, 2], timeout=20,
                   what="ban tin sau khi ket noi lai duoc nhan (chung to da subscribe lai)")
        assert dev.cmds == []                                                       # lenh hong KHONG bi xep hang roi gui muon
    finally:
        dev.close()
        backend.stop()
        b.close()
