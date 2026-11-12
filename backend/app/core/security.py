"""JWT + RBAC (3 vai tro: OPERATOR < SUPERVISOR < ADMIN).

NGUYEN TAC:
- Vai tro va trang thai kich hoat lay tu DB moi request, KHONG tin claim trong token
  -> ha quyen / khoa tai khoan co hieu luc ngay.
- Thuat toan JWT bi ghim (chi HS*), bat buoc co exp -> chan alg=none va token vinh vien.
- Secret rong/mau: production tu choi khoi dong; dev sinh secret ngau nhien (token mat khi restart).
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models import User
from app.models.enums import Role
from app.services.audit import audit

log = logging.getLogger("svmg.security")

RANK = {Role.OPERATOR: 1, Role.SUPERVISOR: 2, Role.ADMIN: 3}
ALLOWED_ALGS = {"HS256", "HS384", "HS512"}
PLACEHOLDER_SECRETS = {"", "change-this-to-a-random-secret", "change_me", "secret"}
MIN_SECRET_LEN = 32

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
_secret_override: Optional[str] = None


class SecurityConfigError(RuntimeError):
    pass


def validate_security_settings() -> None:
    """Goi luc khoi dong."""
    global _secret_override
    if settings.jwt_algorithm not in ALLOWED_ALGS:
        raise SecurityConfigError(f"JWT_ALGORITHM phải thuộc {sorted(ALLOWED_ALGS)}")
    weak = settings.jwt_secret in PLACEHOLDER_SECRETS or len(settings.jwt_secret) < MIN_SECRET_LEN
    if not weak:
        _secret_override = None
        return
    if settings.env.lower() == "production":
        raise SecurityConfigError(f"JWT_SECRET rỗng/yếu (cần ≥ {MIN_SECRET_LEN} ký tự, không dùng giá trị mẫu)")
    _secret_override = secrets.token_urlsafe(48)
    log.warning("JWT_SECRET rong/yeu: dung secret ngau nhien cho phien nay (token se mat khi restart). "
                "Dat JWT_SECRET trong .env.")


def _secret() -> str:
    if _secret_override is not None:
        return _secret_override
    if settings.jwt_secret in PLACEHOLDER_SECRETS or len(settings.jwt_secret) < MIN_SECRET_LEN:
        validate_security_settings()  # chua khoi dong qua lifespan (vd. script) -> van khong dung secret yeu
        if _secret_override is not None:
            return _secret_override
    return settings.jwt_secret


def create_access_token(username: str, now: Optional[datetime] = None) -> tuple[str, int]:
    """Tra ve (token, expires_in_s)."""
    now = now or datetime.now(timezone.utc)
    ttl = timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": username, "iat": int(now.timestamp()), "exp": int((now + ttl).timestamp())}
    return jwt.encode(payload, _secret(), algorithm=settings.jwt_algorithm), int(ttl.total_seconds())


def decode_token(token: str) -> dict:
    """Nem jwt.InvalidTokenError neu sai chu ky / het han / thieu claim / alg la."""
    return jwt.decode(token, _secret(), algorithms=[settings.jwt_algorithm],
                      options={"require": ["exp", "sub"]})


def user_from_token(db: Session, token: Optional[str]) -> Optional[User]:
    if not token:
        return None
    try:
        sub = decode_token(token)["sub"]
    except (jwt.InvalidTokenError, KeyError):
        return None
    user = db.scalar(select(User).where(User.username == sub))
    return user if user is not None and user.is_active else None


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="Chưa đăng nhập hoặc phiên không hợp lệ",
                         headers={"WWW-Authenticate": "Bearer"})


def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    user = user_from_token(db, token)
    if user is None:
        raise _unauthorized()
    return user


def assert_role(db: Session, user: User, min_role: Role, what: str) -> None:
    """403 + audit AUTH_DENIED neu khong du quyen."""
    if RANK[user.role] < RANK[min_role]:
        audit(db, user.username, "AUTH_DENIED", what, {"role": user.role.value, "required": min_role.value})
        db.commit()  # lan bi tu choi van phai de lai dau vet
        raise HTTPException(status_code=403,
                            detail=f"Cần quyền tối thiểu {min_role.value} (bạn là {user.role.value})")


def require_role(min_role: Role):
    """Dependency factory: Depends(require_role(Role.SUPERVISOR))."""
    def dep(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        assert_role(db, user, min_role, "endpoint")
        return user
    return dep


def current_actor(user: User = Depends(get_current_user)) -> str:
    """Ten nguoi thao tac that (dung cho audit, issued_by...)."""
    return user.username
