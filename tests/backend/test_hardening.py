"""Test chứng minh các lỗi tìm thấy khi tự rà soát code M3-02..M3-08, và giữ chúng không quay lại."""
import asyncio
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from conftest import NOAUTH, PASSWORD
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError

from alarms.realtime import AlarmHub, hub
from app.core.config import settings
from app.models import Command, Device, DeviceConfigVersion, Telemetry
from app.services import auth as auth_svc
from app.services.auth import limiter
from commands import config_service, service
from commands.publisher import set_publisher
from ingest.service import Outcome, handle_message
from notify.service import Message, dispatcher

DEV = "vessel-demo-01"
REPO = Path(__file__).resolve().parents[2]
EX = REPO / "contracts" / "examples"


def telemetry_bytes(**over) -> bytes:
    p = json.loads((EX / "telemetry_sample.json").read_text(encoding="utf-8"))
    p.update(over)
    return json.dumps(p).encode()


class FakePublisher:
    def __init__(self):
        self.sent = []

    def publish(self, topic, payload, qos=1, retain=False, on_delivered=None):
        self.sent.append((topic, json.loads(payload), qos, retain))
        if on_delivered:
            on_delivered()


@pytest.fixture()
def pub():
    p = FakePublisher()
    set_publisher(p)
    yield p
    set_publisher(None)


@pytest.fixture()
def device(db):
    db.add(Device(device_id=DEV, config_version=7))
    db.commit()


def loop_thread_name() -> str:
    async def name():
        return threading.current_thread().name
    return asyncio.run_coroutine_threadsafe(name(), hub.loop).result(timeout=5)


# ============ A. NaN / Infinity tu thiet bi lam hong API ============

@pytest.mark.parametrize("bad", [b"NaN", b"Infinity", b"-Infinity", b"1e999"])
def test_nan_and_infinity_rejected_and_api_stays_healthy(client, db, bad):
    raw = telemetry_bytes().replace(b'"roll_deg": 8.4', b'"roll_deg": ' + bad)
    assert b'"roll_deg": ' + bad in raw
    r = handle_message(db, f"svmg/{DEV}/telemetry", raw)
    assert r.outcome == Outcome.INVALID, "NaN/Infinity phai bi tu choi (JSON chuan khong co)"
    assert db.scalar(select(Telemetry)) is None
    assert client.get(f"/api/v1/devices/{DEV}/telemetry").status_code == 200


# ============ G. chuoi dai bat thuong ============

@pytest.mark.parametrize("field", ["boot_id", "voyage_id", "scenario_id", "model_version"])
def test_oversized_strings_rejected(db, field):
    r = handle_message(db, f"svmg/{DEV}/telemetry", telemetry_bytes(**{field: "x" * 500}))
    assert r.outcome == Outcome.INVALID and "dài" in (r.reason or "")
    assert db.scalar(select(Telemetry)) is None


def test_oversized_alarm_id_rejected(db):
    p = {"device_id": DEV, "boot_id": "b", "seq": 1, "type": "ALARM_STATE", "alarm_id": "A" * 500,
         "level": "WARNING", "t_sim_s": 1.0}
    assert handle_message(db, f"svmg/{DEV}/event", json.dumps(p).encode()).outcome == Outcome.INVALID


# ============ C. race: hai request cung luc -> 500 ============

def test_cmd_id_race_is_handled_as_idempotent_not_500(client, db, pub, device, monkeypatch):
    first, _ = service.create_command(db, DEV, service.CommandName.calibrate_zero, {}, 30, "sup01", cmd_id="c-race")
    n_sent = len(pub.sent)
    real = service._find_command
    calls = {"n": 0}

    def racy(db_, cmd_id):  # lan kiem tra dau 'chua thay' (request kia chua commit), sau do thay
        calls["n"] += 1
        return None if calls["n"] == 1 else real(db_, cmd_id)

    monkeypatch.setattr(service, "_find_command", racy)
    c, created = service.create_command(db, DEV, service.CommandName.calibrate_zero, {}, 30, "sup01", cmd_id="c-race")
    assert created is False and c.cmd_id == "c-race"
    assert len(pub.sent) == n_sent                      # khong gui lan hai
    assert len(list(db.scalars(select(Command)))) == 1


def test_config_version_race_returns_409_not_500(client, db, pub, device, monkeypatch):
    assert client.put(f"/api/v1/devices/{DEV}/config", json={"profile": "SENSITIVE"}).status_code == 201
    monkeypatch.setattr(config_service, "history", lambda db_, dev_: [])  # request kia khong thay ban v8
    r = client.put(f"/api/v1/devices/{DEV}/config", json={"profile": "CONSERVATIVE"})
    assert r.status_code == 409 and "thử lại" in r.json()["detail"]
    assert len(list(db.scalars(select(DeviceConfigVersion)))) == 1


# ============ D. khong tu bia gia tri cau hinh mac dinh ============

def test_first_config_contains_only_what_caller_sent(client, db, pub, device):
    r = client.put(f"/api/v1/devices/{DEV}/config", json={"profile": "SENSITIVE"})
    assert r.status_code == 201
    assert set(r.json()["payload"]) == {"profile", "config_version", "crc"}  # khong them debounce_n, mai_caution...
    assert set(pub.sent[-1][1]) == {"profile", "config_version", "crc"}


def test_first_config_without_profile_is_rejected(client, pub, device):
    r = client.put(f"/api/v1/devices/{DEV}/config", json={"debounce_n": 3})
    assert r.status_code == 422 and pub.sent == []  # schema hop dong bat buoc 'profile'


def test_later_updates_merge_with_previous_version(client, pub, device):
    client.put(f"/api/v1/devices/{DEV}/config", json={"profile": "SENSITIVE", "debounce_n": 2})
    p = client.put(f"/api/v1/devices/{DEV}/config", json={"mai_caution": 60}).json()["payload"]
    assert p["profile"] == "SENSITIVE" and p["debounce_n"] == 2 and p["mai_caution"] == 60


# ============ B. chan event loop ============

def test_notify_test_runs_off_the_event_loop(client, auth, monkeypatch):
    seen = {}

    def fake_send_now(msg):
        seen["thread"] = threading.current_thread().name
        return {"telegram": "ok"}

    monkeypatch.setattr(dispatcher, "send_now", fake_send_now)
    assert client.post("/api/v1/notify/test", headers=auth("admin01")).status_code == 200
    assert seen["thread"] != loop_thread_name(), "gui mang dong bo tren event loop se dong bang moi request"


def test_password_hashing_runs_off_the_event_loop(client, db, monkeypatch):
    seen = []
    real = auth_svc.verify_password

    def spy(pw, stored):
        seen.append(threading.current_thread().name)
        return real(pw, stored)

    monkeypatch.setattr(auth_svc, "verify_password", spy)
    r = client.post("/api/v1/auth/login", data={"username": "sup01", "password": PASSWORD}, headers=NOAUTH)
    assert r.status_code == 200 and seen and seen[0] != loop_thread_name()


# ============ E. WebSocket: 1 client cham chan tat ca ============

def test_slow_websocket_client_does_not_block_others():
    class Slow:
        async def send_json(self, _):
            await asyncio.sleep(3600)

    class Good:
        def __init__(self):
            self.got = []

        async def send_json(self, m):
            self.got.append(m)

    async def run():
        h = AlarmHub()
        h.send_timeout_s = 0.05
        slow, good = Slow(), Good()
        h.clients = {slow, good}
        await asyncio.wait_for(h._broadcast({"x": 1}), timeout=2)
        return h, slow, good

    h, slow, good = asyncio.run(run())
    assert good.got == [{"x": 1}] and slow not in h.clients  # client cham bi loai


# ============ F. dang nhap: bo nho, flood, mat khau khong lo, ten phan biet hoa/thuong ============

def test_login_limiter_memory_is_bounded():
    for i in range(auth_svc.MAX_TRACKED_KEYS + 500):
        limiter.fail(f"user{i}|1.2.3.4")
    assert len(limiter._fails) <= auth_svc.MAX_TRACKED_KEYS


def test_per_ip_flood_with_random_usernames_is_blocked(client, db):
    n = settings.login_max_failures * auth_svc.IP_FAILURE_MULTIPLIER
    for i in range(n):
        client.post("/api/v1/auth/login", data={"username": f"nobody{i}", "password": "x" * 10}, headers=NOAUTH)
    r = client.post("/api/v1/auth/login", data={"username": "sup01", "password": PASSWORD}, headers=NOAUTH)
    assert r.status_code == 429  # doi ten lien tuc cung khong lach duoc


def test_oversized_password_rejected_cheaply(client, db):
    r = client.post("/api/v1/auth/login", data={"username": "sup01", "password": "p" * 200_000}, headers=NOAUTH)
    assert r.status_code == 401


def test_usernames_are_case_insensitively_unique(client, auth):
    r = client.post("/api/v1/users", json={"username": "SUP01", "password": "a-good-password"},
                    headers=auth("admin01"))
    assert r.status_code == 409


# ============ H. SQLite nhieu luong ============

def test_sqlite_file_engine_uses_wal_and_busy_timeout(tmp_path):
    from app.core.db import build_engine
    eng = build_engine(f"sqlite:///{tmp_path / 'x.db'}")
    with eng.connect() as c:
        assert c.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert c.execute(text("PRAGMA busy_timeout")).scalar() >= 5000
    eng.dispose()


# ============ I. Docker khong dong goi bi mat ============

def test_dockerignore_excludes_secrets_and_runs_non_root():
    ignore = (REPO / "backend" / ".dockerignore").read_text(encoding="utf-8").splitlines()
    for must in (".env", "*.db", "venv", "tests"):
        assert any(line.strip().startswith(must) for line in ignore), f"{must} phai nam trong .dockerignore"
    assert "USER " in (REPO / "backend" / "Dockerfile").read_text(encoding="utf-8")


# ============ J. notify: bo nho cooldown ============

def test_notify_cooldown_table_is_pruned(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "1:T")
    monkeypatch.setattr(settings, "telegram_chat_id", "1")
    dispatcher.set_client(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": True}))))
    dispatcher._last.clear()
    now = [0.0]
    dispatcher.clock = lambda: now[0]
    try:
        for i in range(3000):
            now[0] += settings.notify_cooldown_s + 1
            dispatcher.submit(Message(kind="ALARM_CRITICAL", title="t", text="x", device_id=DEV, alarm_id=f"A-{i}"))
        dispatcher.wait_idle(timeout=20)
        assert len(dispatcher._last) < 2100
    finally:
        import time
        dispatcher.clock = time.monotonic
        dispatcher.set_client(None)
        dispatcher._last.clear()
