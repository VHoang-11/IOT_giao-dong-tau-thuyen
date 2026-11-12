import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from alarms import service
from app.core.config import settings
from app.models import AuditLog
from ingest.service import handle_message
from notify.service import Message, dispatcher

DEV = "vessel-demo-01"
T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
TOKEN = "123456:SECRET-BOT-TOKEN"
HOOK = "https://hooks.example.test/mail"


class Net:
    """Mang gia (httpx.MockTransport): ghi lai moi request, tra ve theo kich ban."""
    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.script = []  # danh sach (status, json) lan luot; het thi dung 'default'
        self.default = (200, {"ok": True})
        self.raise_exc = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.raise_exc:
            raise self.raise_exc(f"cannot connect to {request.url}")  # co y nhet URL (chua token) vao thong bao loi
        status, body = self.script.pop(0) if self.script else self.default
        return httpx.Response(status, json=body)

    def bodies(self):
        return [json.loads(r.content) for r in self.requests]


@pytest.fixture()
def net(monkeypatch):
    n = Net()
    dispatcher.set_client(httpx.Client(transport=httpx.MockTransport(n.handler)))
    dispatcher._last.clear()
    dispatcher.stats.clear()
    monkeypatch.setattr(settings, "notify_backoff_s", 0.0)
    yield n
    dispatcher.wait_idle()
    dispatcher.set_client(None)
    dispatcher._last.clear()


@pytest.fixture()
def telegram(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", TOKEN)
    monkeypatch.setattr(settings, "telegram_chat_id", "-1001")


@pytest.fixture()
def email(monkeypatch):
    monkeypatch.setattr(settings, "email_webhook_url", HOOK)


def event(db, level, seq, alarm_id="A-1", dev=DEV, acked_by=None):
    p = {"device_id": dev, "boot_id": "b1", "seq": seq, "type": "ALARM_STATE", "alarm_id": alarm_id,
         "level": level, "class": "HIGH_ROLL", "t_sim_s": 1.0, "acked_by": acked_by}
    handle_message(db, f"svmg/{dev}/event", json.dumps(p).encode(), rx_time=T0)
    dispatcher.wait_idle()


def status(db, state, dev=DEV):
    handle_message(db, f"svmg/{dev}/status", json.dumps({"state": state}).encode())
    dispatcher.wait_idle()


# ---------------- khi nao gui ----------------

def test_no_channels_configured_is_silent(db, net):
    event(db, "CRITICAL", 1)
    assert net.requests == [] and dispatcher.active_channels() == []


def test_critical_alarm_sends_telegram(db, net, telegram):
    event(db, "CRITICAL", 1)
    assert len(net.requests) == 1
    req = net.requests[0]
    assert str(req.url) == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    body = net.bodies()[0]
    assert body["chat_id"] == "-1001" and "parse_mode" not in body  # khong parse_mode -> khong bi chen markup
    text = body["text"]
    assert DEV in text and "CRITICAL" in text and "A-1" in text
    assert "[SVMG][SIMULATION]" in text and "MÔ PHỎNG" in text     # luon gan nhan nguon du lieu
    assert "dự báo lật tàu" not in text.lower()


def test_only_transition_to_critical_notifies_once(db, net, telegram):
    event(db, "CAUTION", 1)
    event(db, "WARNING", 2)
    assert net.requests == []                    # CAUTION/WARNING khong gui ngay
    event(db, "CRITICAL", 3)
    event(db, "CRITICAL", 4)                     # van CRITICAL -> khong bao lai
    assert len(net.requests) == 1


def test_reactivation_after_ack_notifies(db, net, telegram):
    event(db, "CAUTION", 1)
    a = db.scalar(select(service.Alarm))
    service.ack_alarm(db, a.id, "alice")
    event(db, "WARNING", 2)                      # nang hon sau khi da ACK
    assert len(net.requests) == 1 and "Cần xác nhận lại" in net.bodies()[0]["text"]


def test_escalation_notifies_once(db, net, telegram):
    event(db, "WARNING", 1)
    assert net.requests == []
    service.escalate_overdue(db, now=T0 + timedelta(seconds=61), after_s=60)
    service.escalate_overdue(db, now=T0 + timedelta(seconds=200), after_s=60)  # khong lap
    dispatcher.wait_idle()
    assert len(net.requests) == 1 and "chưa có ai xác nhận" in net.bodies()[0]["text"]


def test_device_offline_notifies_only_on_transition(db, net, telegram):
    status(db, "offline")                        # chua tung online -> khong bao
    assert net.requests == []
    status(db, "online")
    status(db, "offline")
    status(db, "offline")                        # LWT gui lai -> khong bao lap
    assert len(net.requests) == 1 and "mất kết nối" in net.bodies()[0]["text"]


def test_sensor_mode_is_labelled_not_simulation(db, net, telegram):
    from app.models import Device
    from app.models.enums import SourceMode
    db.add(Device(device_id=DEV, source_mode=SourceMode.SENSOR))
    db.commit()
    event(db, "CRITICAL", 1)
    text = net.bodies()[0]["text"]
    assert "[SVMG][SENSOR]" in text and "không phải hệ thống an toàn hàng hải" in text


# ---------------- chong spam ----------------

def test_cooldown_suppresses_duplicates_then_allows_again(net, telegram):
    now = [100.0]
    dispatcher.clock = lambda: now[0]
    try:
        m = Message(kind="ALARM_CRITICAL", title="t", text="x", device_id=DEV, alarm_id="A-1")
        assert dispatcher.submit(m) is True
        assert dispatcher.submit(m) is False              # trong cooldown
        assert dispatcher.submit(Message(kind="ALARM_CRITICAL", title="t", text="x",
                                         device_id=DEV, alarm_id="A-2")) is True  # canh bao khac
        now[0] += settings.notify_cooldown_s + 1
        assert dispatcher.submit(m) is True               # het cooldown
        dispatcher.wait_idle()
        assert dispatcher.stats["suppressed"] == 1 and len(net.requests) == 3
    finally:
        import time
        dispatcher.clock = time.monotonic


# ---------------- loi mang / retry / khong lo token ----------------

def test_retries_then_succeeds(db, net, telegram):
    net.script = [(500, {}), (502, {})]  # 2 lan loi roi OK (notify_retries = 2)
    event(db, "CRITICAL", 1)
    assert len(net.requests) == 3 and dispatcher.stats["telegram.sent"] == 1


def test_permanent_failure_never_breaks_alarm_processing(db, net, telegram, caplog):
    net.default = (401, {"ok": False})
    with caplog.at_level(logging.DEBUG):
        event(db, "CRITICAL", 1)
    assert len(net.requests) == 3 and dispatcher.stats["telegram.failed"] == 1
    a = db.scalar(select(service.Alarm))
    assert a is not None and a.level.value == "CRITICAL"   # canh bao van duoc xu ly binh thuong
    dump = " ".join(str(r.__dict__) + r.getMessage() for r in caplog.records)
    assert TOKEN not in dump                                # token khong lo ra log


def test_network_error_message_with_url_is_scrubbed(db, net, telegram, caplog):
    net.raise_exc = httpx.ConnectError                        # str(e) chua URL co token
    with caplog.at_level(logging.DEBUG):
        event(db, "CRITICAL", 1)
    assert dispatcher.stats["telegram.failed"] == 1
    # kiem tra TUNG ban ghi log, ke ca truong 'extra' (caplog.text khong in cac truong nay)
    dump = " ".join(str(r.__dict__) + r.getMessage() for r in caplog.records)
    assert TOKEN not in dump
    assert [r.error for r in caplog.records if hasattr(r, "error")] == ["ConnectError"]


def test_telegram_200_but_ok_false_is_failure(db, net, telegram):
    net.default = (200, {"ok": False, "description": "chat not found"})
    event(db, "CRITICAL", 1)
    assert dispatcher.stats["telegram.failed"] == 1


def test_httpx_request_logging_is_silenced():
    """httpx ghi URL (co bot token) o INFO -> phai bi tat."""
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING


# ---------------- email webhook ----------------

def test_email_webhook_payload(db, net, email):
    event(db, "CRITICAL", 1)
    assert len(net.requests) == 1 and str(net.requests[0].url) == HOOK
    p = net.bodies()[0]
    assert p["kind"] == "ALARM_CRITICAL" and p["device_id"] == DEV and p["source_mode"] == "SIMULATION"
    assert p["subject"] and "CRITICAL" in p["text"] and p["ts"]


def test_both_channels_one_failing_does_not_block_other(db, net, telegram, email):
    def handler(request):
        net.requests.append(request)
        return httpx.Response(500 if "telegram" in str(request.url) else 200, json={"ok": True})
    dispatcher.set_client(httpx.Client(transport=httpx.MockTransport(handler)))
    event(db, "CRITICAL", 1)
    assert dispatcher.stats["email_webhook.sent"] == 1 and dispatcher.stats["telegram.failed"] == 1


def test_long_text_is_truncated(net, telegram):
    dispatcher.submit(Message(kind="TEST", title="t", text="x" * 10000))
    dispatcher.wait_idle()
    assert len(net.bodies()[0]["text"]) <= 4000


# ---------------- endpoint ----------------

def test_notify_endpoints_admin_only_and_no_secrets(client, db, net, telegram, auth):
    assert client.get("/api/v1/notify/status", headers=auth("sup01")).status_code == 403
    assert client.post("/api/v1/notify/test", headers=auth("op01")).status_code == 403
    r = client.get("/api/v1/notify/status", headers=auth("admin01"))
    assert r.status_code == 200
    assert {"name": "telegram", "configured": True} in r.json()["channels"]
    assert TOKEN not in r.text and "-1001" not in r.text


def test_notify_test_reports_per_channel_and_audits(client, db, net, telegram, auth):
    r = client.post("/api/v1/notify/test", headers=auth("admin01"))
    assert r.status_code == 200 and r.json()["results"] == {"telegram": "ok"}
    assert db.scalar(select(AuditLog).where(AuditLog.action == "NOTIFY_TEST")).actor == "admin01"
    net.default = (401, {"ok": False})
    assert client.post("/api/v1/notify/test", headers=auth("admin01")).json()["results"] == {
        "telegram": "failed: http_401"}
