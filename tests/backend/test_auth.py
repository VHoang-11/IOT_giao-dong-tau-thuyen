import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from conftest import NOAUTH, PASSWORD
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.core import security
from app.core.config import settings
from app.core.passwords import hash_password, verify_password
from app.models import AuditLog, Device, User
from app.models.enums import Role
from app.services import auth as auth_svc
from app.services.auth import limiter
from commands.publisher import set_publisher

DEV = "vessel-demo-01"
SECRET = "test-secret-key-for-unit-tests-0123456789-abcdef"


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


def login(client, username="sup01", password=PASSWORD):
    return client.post("/api/v1/auth/login", data={"username": username, "password": password}, headers=NOAUTH)


def audits(db, action):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)))


def cmd(client, body, headers):
    return client.post(f"/api/v1/devices/{DEV}/commands", json=body, headers=headers)


# ---------------- dang nhap ----------------

def test_login_success_returns_token_that_works(client, db):
    r = login(client, "admin01")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "ADMIN" and body["username"] == "admin01" and body["expires_in"] == 3600
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["username"] == "admin01"
    assert "password_hash" not in me.json()
    assert audits(db, "AUTH_LOGIN")[0].actor == "admin01"


def test_wrong_password_and_unknown_user_look_identical(client, db):
    a = login(client, "sup01", "wrong-password")
    b = login(client, "ghost-user", "wrong-password")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()  # khong lo user nao ton tai
    assert len(audits(db, "AUTH_LOGIN_FAILED")) == 2


def test_inactive_user_cannot_login(client, db):
    u = db.scalar(select(User).where(User.username == "op01"))
    u.is_active = False
    db.commit()
    assert login(client, "op01").status_code == 401


# ---------------- bat buoc dang nhap ----------------

PROTECTED_GET = ["/api/v1/devices", "/api/v1/alarms", "/api/v1/alarms/stats", "/api/v1/commands",
                 "/api/v1/commands/stats", "/api/v1/audit", "/api/v1/users", "/api/v1/auth/me",
                 f"/api/v1/devices/{DEV}/config"]


@pytest.mark.parametrize("path", PROTECTED_GET)
def test_endpoints_require_login(client, path):
    r = client.get(path, headers=NOAUTH)
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"


def test_write_endpoints_require_login(client, device):
    assert client.post(f"/api/v1/devices/{DEV}/commands", json={"cmd": "calibrate_zero"},
                       headers=NOAUTH).status_code == 401
    assert client.post("/api/v1/alarms/1/ack", headers=NOAUTH).status_code == 401
    assert client.put(f"/api/v1/devices/{DEV}/config", json={"profile": "STANDARD"},
                      headers=NOAUTH).status_code == 401


def test_healthz_is_public(client):
    assert client.get("/healthz", headers=NOAUTH).status_code == 200


def _tok(payload, key=SECRET, alg="HS256"):
    return {"Authorization": f"Bearer {jwt.encode(payload, key, algorithm=alg)}"}


def _exp(minutes=10):
    return int((datetime.now(timezone.utc) + timedelta(minutes=minutes)).timestamp())


@pytest.mark.parametrize("make", [
    lambda: {"Authorization": "Bearer not.a.jwt"},
    lambda: {"Authorization": "Bearer "},
    lambda: _tok({"sub": "sup01", "exp": _exp(-5)}),                      # het han
    lambda: _tok({"sub": "sup01", "exp": _exp()}, key="x" * 40),          # sai chu ky
    lambda: _tok({"sub": "sup01", "exp": _exp()}, key=None, alg="none"),  # alg=none
    lambda: _tok({"sub": "sup01"}),                                       # thieu exp
    lambda: _tok({"exp": _exp()}),                                        # thieu sub
    lambda: _tok({"sub": "ghost", "exp": _exp()}),                        # user khong ton tai
    lambda: _tok({"sub": "sup01", "exp": _exp()}, alg="HS512"),           # sai thuat toan da ghim
])
def test_bad_tokens_rejected(client, make):
    assert client.get("/api/v1/devices", headers=make()).status_code == 401


# ---------------- phan quyen ----------------

def test_operator_permissions(client, db, pub, device, auth):
    h = auth("op01")
    assert client.get("/api/v1/devices", headers=h).status_code == 200
    assert client.post("/api/v1/alarms/9999/ack", headers=h).status_code == 404       # du quyen ACK
    assert cmd(client, {"cmd": "mute_alarm"}, h).status_code == 202                      # du quyen mute
    assert cmd(client, {"cmd": "set_profile", "params": {"profile": "STANDARD"}}, h).status_code == 403
    assert cmd(client, {"cmd": "calibrate_zero"}, h).status_code == 403
    assert client.put(f"/api/v1/devices/{DEV}/config", json={"profile": "STANDARD"}, headers=h).status_code == 403
    assert client.post(f"/api/v1/devices/{DEV}/config/rollback", json={}, headers=h).status_code == 403
    assert client.get("/api/v1/audit", headers=h).status_code == 403
    assert client.get("/api/v1/users", headers=h).status_code == 403
    denied = audits(db, "AUTH_DENIED")
    assert denied and all(a.actor == "op01" for a in denied)  # bi tu choi van co dau vet


def test_supervisor_permissions(client, pub, device, auth):
    h = auth("sup01")
    assert cmd(client, {"cmd": "set_profile", "params": {"profile": "SENSITIVE"}}, h).status_code == 202
    assert client.put(f"/api/v1/devices/{DEV}/config", json={"profile": "SENSITIVE"}, headers=h).status_code == 201
    assert client.get("/api/v1/audit", headers=h).status_code == 200
    assert cmd(client, {"cmd": "restart_device"}, h).status_code == 403   # chi Admin
    assert client.get("/api/v1/users", headers=h).status_code == 403


def test_admin_permissions(client, pub, device, auth):
    h = auth("admin01")
    assert cmd(client, {"cmd": "restart_device"}, h).status_code == 202
    assert client.get("/api/v1/users", headers=h).status_code == 200


def test_denied_command_is_not_published(client, pub, device, auth):
    cmd(client, {"cmd": "restart_device"}, auth("op01"))
    assert pub.sent == []


def test_command_issued_by_is_real_username(client, db, pub, device, auth):
    cmd(client, {"cmd": "restart_device"}, auth("admin01"))
    assert pub.sent[0][1]["issued_by"] == "admin01"
    from app.models import Command
    assert db.scalar(select(Command)).issued_by == "admin01"


def test_role_is_read_from_db_not_token(client, db, auth):
    h = auth("admin01")
    assert client.get("/api/v1/users", headers=h).status_code == 200
    u = db.scalar(select(User).where(User.username == "admin01"))
    u.role = Role.OPERATOR
    db.commit()
    assert client.get("/api/v1/users", headers=h).status_code == 403  # ha quyen co hieu luc ngay


def test_disabling_user_invalidates_existing_token(client, db, auth):
    h = auth("sup01")
    assert client.get("/api/v1/devices", headers=h).status_code == 200
    u = db.scalar(select(User).where(User.username == "sup01"))
    u.is_active = False
    db.commit()
    assert client.get("/api/v1/devices", headers=h).status_code == 401


# ---------------- khoa khi dang nhap sai ----------------

def test_lockout_after_repeated_failures_then_recovers(client, db, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(limiter, "clock", lambda: now[0])
    for _ in range(settings.login_max_failures):
        assert login(client, "sup01", "bad-password").status_code == 401
    r = login(client, "sup01", PASSWORD)  # dung mat khau van bi khoa
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    assert login(client, "op01", PASSWORD).status_code == 200  # user khac khong bi anh huong
    now[0] += settings.login_lockout_s + 1
    assert login(client, "sup01", PASSWORD).status_code == 200


def test_successful_login_resets_failure_counter(client, db):
    for _ in range(settings.login_max_failures - 1):
        login(client, "sup01", "bad-password")
    assert login(client, "sup01", PASSWORD).status_code == 200
    for _ in range(settings.login_max_failures - 1):
        assert login(client, "sup01", "bad-password").status_code == 401
    assert login(client, "sup01", PASSWORD).status_code == 200


# ---------------- quan ly nguoi dung ----------------

def test_admin_creates_user_who_can_login(client, db, auth):
    h = auth("admin01")
    r = client.post("/api/v1/users", json={"username": "newbie", "password": "a-good-password"}, headers=h)
    assert r.status_code == 201 and r.json()["role"] == "OPERATOR" and "password" not in r.json()
    assert login(client, "newbie", "a-good-password").status_code == 200
    row = db.scalar(select(User).where(User.username == "newbie"))
    assert row.password_hash.startswith("scrypt$") and "a-good-password" not in row.password_hash


def test_create_user_validation(client, auth):
    h = auth("admin01")
    post = lambda body: client.post("/api/v1/users", json=body, headers=h)  # noqa: E731
    assert post({"username": "sup01", "password": "a-good-password"}).status_code == 409      # trung
    assert post({"username": "has space", "password": "a-good-password"}).status_code == 422  # ky tu cam
    assert post({"username": "ab", "password": "a-good-password"}).status_code == 422         # qua ngan
    assert post({"username": "okname", "password": "short"}).status_code == 422               # mat khau yeu
    assert post({"username": "okname", "password": "x" * 129}).status_code == 422             # qua dai
    assert post({"username": "okname", "password": "a-good-password", "role": "ROOT"}).status_code == 422
    assert post({"username": "okname", "password": "a-good-password", "is_superuser": True}).status_code == 422


def test_passwords_never_written_to_audit(client, db, auth):
    h = auth("admin01")
    client.post("/api/v1/users", json={"username": "newbie", "password": "secret-pass-1"}, headers=h)
    uid = db.scalar(select(User.id).where(User.username == "newbie"))
    client.patch(f"/api/v1/users/{uid}", json={"password": "secret-pass-2"}, headers=h)
    dump = json.dumps([[a.actor, a.action, a.target, a.detail] for a in db.scalars(select(AuditLog))])
    assert "secret-pass" not in dump and PASSWORD not in dump
    assert audits(db, "USER_CREATE") and audits(db, "USER_UPDATE")


def test_cannot_remove_last_admin(client, db, auth):
    h = auth("admin01")
    uid = db.scalar(select(User.id).where(User.username == "admin01"))
    assert client.patch(f"/api/v1/users/{uid}", json={"role": "OPERATOR"}, headers=h).status_code == 409
    assert client.patch(f"/api/v1/users/{uid}", json={"is_active": False}, headers=h).status_code == 409
    client.post("/api/v1/users", json={"username": "admin02", "password": "a-good-password",
                                       "role": "ADMIN"}, headers=h)
    assert client.patch(f"/api/v1/users/{uid}", json={"role": "OPERATOR"}, headers=h).status_code == 200


def test_admin_can_reset_password_and_change_role(client, db, auth):
    h = auth("admin01")
    uid = db.scalar(select(User.id).where(User.username == "op01"))
    assert client.patch(f"/api/v1/users/{uid}", json={"password": "brand-new-pass", "role": "SUPERVISOR"},
                        headers=h).json()["role"] == "SUPERVISOR"
    assert login(client, "op01", PASSWORD).status_code == 401
    assert login(client, "op01", "brand-new-pass").status_code == 200
    assert client.patch("/api/v1/users/9999", json={"role": "ADMIN"}, headers=h).status_code == 404


def test_change_own_password(client, db, auth):
    h = auth("op01")
    url = "/api/v1/auth/change-password"
    assert client.post(url, json={"old_password": "nope", "new_password": "another-pass-1"}, headers=h).status_code == 400
    assert client.post(url, json={"old_password": PASSWORD, "new_password": "short"}, headers=h).status_code == 422
    assert client.post(url, json={"old_password": PASSWORD, "new_password": "another-pass-1"}, headers=h).status_code == 204
    assert login(client, "op01", PASSWORD).status_code == 401
    assert login(client, "op01", "another-pass-1").status_code == 200


# ---------------- WebSocket ----------------

def test_websocket_requires_valid_token(client, db, auth):
    for url in ("/ws/alarms", "/ws/alarms?token=garbage"):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(url):
                pass
    u = db.scalar(select(User).where(User.username == "op01"))
    token = auth("op01")["Authorization"].split()[1]
    u.is_active = False
    db.commit()
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/alarms?token={token}"):
            pass


# ---------------- mat khau / cau hinh bao mat ----------------

def test_password_hashing():
    h1, h2 = hash_password("same-password"), hash_password("same-password")
    assert h1 != h2  # salt ngau nhien
    assert h1.startswith("scrypt$") and verify_password("same-password", h1)
    assert not verify_password("other-password", h1)
    for bad in ("", "garbage", "scrypt$x$y", "md5$1$2$3$4$5", "scrypt$a$8$1$!!$!!"):
        assert verify_password("same-password", bad) is False  # khong nem exception


def test_production_refuses_weak_or_placeholder_secret(monkeypatch):
    monkeypatch.setattr(settings, "env", "production")
    for weak in ("", "change-this-to-a-random-secret", "short"):
        monkeypatch.setattr(settings, "jwt_secret", weak)
        with pytest.raises(security.SecurityConfigError):
            security.validate_security_settings()
    monkeypatch.setattr(settings, "jwt_secret", SECRET)
    security.validate_security_settings()  # manh -> ok


def test_rejects_unsafe_jwt_algorithm(monkeypatch):
    monkeypatch.setattr(settings, "jwt_algorithm", "none")
    with pytest.raises(security.SecurityConfigError):
        security.validate_security_settings()


def test_dev_with_weak_secret_uses_random_secret(monkeypatch):
    monkeypatch.setattr(settings, "env", "dev")
    monkeypatch.setattr(settings, "jwt_secret", "")
    monkeypatch.setattr(security, "_secret_override", None)
    security.validate_security_settings()
    token, _ = security.create_access_token("sup01")
    assert security.decode_token(token)["sub"] == "sup01"
    with pytest.raises(jwt.PyJWTError):  # secret rong khong the dung de xac minh (PyJWT tu choi khoa rong)
        jwt.decode(token, "", algorithms=["HS256"])
    monkeypatch.setattr(security, "_secret_override", None)


# ---------------- bootstrap admin ----------------

def test_bootstrap_admin_only_when_empty_and_password_set(db, monkeypatch):
    monkeypatch.setattr(settings, "admin_password", "initial-admin-pass")
    assert auth_svc.bootstrap_admin(db) is None  # da co user -> khong lam gi
    for u in db.scalars(select(User)).all():
        db.delete(u)
    db.commit()
    monkeypatch.setattr(settings, "admin_password", "")
    assert auth_svc.bootstrap_admin(db) is None  # khong co mat khau -> khong tu doan
    monkeypatch.setattr(settings, "admin_password", "initial-admin-pass")
    u = auth_svc.bootstrap_admin(db)
    assert u.role == Role.ADMIN and verify_password("initial-admin-pass", u.password_hash)
