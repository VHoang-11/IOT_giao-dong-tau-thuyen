"""Dang nhap + quan ly nguoi dung."""
import logging
import re
import time
from typing import Callable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.passwords import DUMMY_HASH, MAX_PASSWORD_LEN, MIN_PASSWORD_LEN, hash_password, verify_password
from app.models import User
from app.models.enums import Role
from app.services.audit import audit

log = logging.getLogger("svmg.auth")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,64}$")
MAX_TRACKED_KEYS = 10_000     # so muc toi da bo gioi han dang nhap giu trong bo nho
IP_FAILURE_MULTIPLIER = 4     # nguong khoa theo IP = login_max_failures x 4 (chong doi username lien tuc)


class AuthFailed(Exception):
    """Sai ten dang nhap/mat khau/tai khoan bi khoa. Thong diep co y chung chung."""


class TooManyAttempts(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("Đăng nhập sai quá nhiều lần, thử lại sau")
        self.retry_after = retry_after


class UserConflict(Exception):
    pass


class UserNotFound(Exception):
    pass


class InvalidInput(Exception):
    """Du lieu nguoi dung khong hop le (HTTP 422)."""


class WeakPassword(InvalidInput):
    pass


class LoginLimiter:
    """Khoa tam theo (username, ip) sau N lan sai. Bo nho trong tien trinh (don gian, du cho do an).
    Han che: reset khi restart, khong chia se giua nhieu worker."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self._fails: dict[str, int] = {}
        self._locked_until: dict[str, float] = {}

    def check(self, key: str) -> None:
        until = self._locked_until.get(key)
        if until is not None:
            remaining = until - self.clock()
            if remaining > 0:
                raise TooManyAttempts(int(remaining) + 1)
            self._locked_until.pop(key, None)
            self._fails.pop(key, None)

    def fail(self, key: str, max_failures: Optional[int] = None) -> None:
        limit = max_failures if max_failures is not None else settings.login_max_failures
        n = self._fails.get(key, 0) + 1
        self._fails[key] = n
        if n >= limit:
            self._locked_until[key] = self.clock() + settings.login_lockout_s
        if len(self._fails) > MAX_TRACKED_KEYS:
            self._evict()

    def success(self, key: str) -> None:
        self._fails.pop(key, None)
        self._locked_until.pop(key, None)

    def _evict(self) -> None:
        """Gioi han bo nho: ke tan cong thu hang trieu username ngau nhien khong the lam day RAM.
        Uu tien bo cac muc cu CHUA bi khoa; chi khi toan bo deu dang bi khoa moi bo muc khoa cu nhat."""
        for k in list(self._fails):
            if len(self._fails) <= MAX_TRACKED_KEYS:
                return
            if k not in self._locked_until:
                self._fails.pop(k)
        for k in list(self._fails):
            if len(self._fails) <= MAX_TRACKED_KEYS:
                return
            self._fails.pop(k)
            self._locked_until.pop(k, None)


limiter = LoginLimiter()


def check_password_policy(pw: str) -> None:
    if not (MIN_PASSWORD_LEN <= len(pw) <= MAX_PASSWORD_LEN):
        raise WeakPassword(f"Mật khẩu phải dài {MIN_PASSWORD_LEN}–{MAX_PASSWORD_LEN} ký tự")


def authenticate(db: Session, username: str, password: str, ip: str = "?") -> User:
    key = f"{username.lower()}|{ip}"   # khoa theo (user, IP)
    ip_key = f"ip|{ip}"                # khoa theo IP: doi username lien tuc van bi chan (va khong lam day bang audit)
    limiter.check(ip_key)
    limiter.check(key)  # ca username khong ton tai cung dem -> khong lo user nao co that
    user = db.scalar(select(User).where(User.username == username))
    if len(password) > MAX_PASSWORD_LEN:
        ok = False  # mat khau vo ly: khong ton CPU bam
    else:
        # luon chay 1 lan verify (hash gia neu khong co user) de thoi gian khong tiet lo user ton tai
        ok = verify_password(password, user.password_hash if user else DUMMY_HASH)
    if user is None or not ok or not user.is_active:
        limiter.fail(key)
        limiter.fail(ip_key, settings.login_max_failures * IP_FAILURE_MULTIPLIER)
        audit(db, username[:64], "AUTH_LOGIN_FAILED", None, {"ip": ip})
        db.commit()
        raise AuthFailed("Sai tên đăng nhập hoặc mật khẩu")
    limiter.success(key)  # chi xoa dem cua (user, IP); dem theo IP khong bi reset boi 1 lan dang nhap dung
    audit(db, user.username, "AUTH_LOGIN", None, {"ip": ip})
    db.commit()
    return user


def _active_admins(db: Session, excluding_id: Optional[int] = None) -> int:
    q = select(func.count()).select_from(User).where(User.role == Role.ADMIN, User.is_active.is_(True))
    if excluding_id is not None:
        q = q.where(User.id != excluding_id)
    return db.scalar(q) or 0


def create_user(db: Session, actor: str, username: str, password: str, role: Role) -> User:
    if not USERNAME_RE.match(username):
        raise InvalidInput("Tên đăng nhập chỉ gồm chữ, số, '_', '.', '-' (3–64 ký tự)")
    check_password_policy(password)
    # khong phan biet hoa/thuong: 'SUP01' va 'sup01' la cung 1 nguoi (tranh nham lan khi doc audit)
    if db.scalar(select(User.id).where(func.lower(User.username) == username.lower())) is not None:
        raise UserConflict(f"Tên đăng nhập '{username}' đã tồn tại")
    user = User(username=username, password_hash=hash_password(password), role=role, is_active=True)
    db.add(user)
    audit(db, actor, "USER_CREATE", username, {"role": role.value})
    db.commit()
    return user


def update_user(db: Session, actor: str, user_id: int, role: Optional[Role] = None,
                is_active: Optional[bool] = None, password: Optional[str] = None) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFound(f"Không tìm thấy người dùng #{user_id}")
    new_role = role if role is not None else user.role
    new_active = is_active if is_active is not None else user.is_active
    demoting_admin = user.role == Role.ADMIN and user.is_active and (new_role != Role.ADMIN or not new_active)
    if demoting_admin and _active_admins(db, excluding_id=user.id) == 0:
        raise UserConflict("Không thể hạ quyền/khóa admin cuối cùng của hệ thống")
    detail: dict = {}
    if role is not None and role != user.role:
        detail["role"] = [user.role.value, role.value]
        user.role = role
    if is_active is not None and is_active != user.is_active:
        detail["is_active"] = [user.is_active, is_active]
        user.is_active = is_active
    if password is not None:
        check_password_policy(password)
        user.password_hash = hash_password(password)
        detail["password"] = "reset"  # khong bao gio ghi mat khau vao audit
    audit(db, actor, "USER_UPDATE", user.username, detail)
    db.commit()
    return user


def change_own_password(db: Session, user: User, old: str, new: str) -> None:
    if not verify_password(old, user.password_hash):
        audit(db, user.username, "AUTH_PASSWORD_CHANGE_FAILED", None, None)
        db.commit()
        raise AuthFailed("Mật khẩu hiện tại không đúng")
    check_password_policy(new)
    user.password_hash = hash_password(new)
    audit(db, user.username, "AUTH_PASSWORD_CHANGE", None, None)
    db.commit()


def bootstrap_admin(db: Session) -> Optional[User]:
    """Tao admin dau tien neu bang users rong va ADMIN_PASSWORD duoc dat. Khong bao gio tu doan mat khau."""
    if db.scalar(select(func.count()).select_from(User)) or not settings.admin_password:
        return None
    user = create_user(db, "system", settings.admin_username, settings.admin_password, Role.ADMIN)
    log.warning("da tao tai khoan admin dau tien", extra={"username": user.username})
    return user
