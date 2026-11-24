"""Bam mat khau bang scrypt (thu vien chuan, khong phu thuoc passlib/bcrypt).

Dinh dang luu: scrypt$N$r$p$<salt_b64>$<hash_b64>  (tham so nam trong chuoi -> nang cap duoc ve sau).
"""
import base64
import hashlib
import hmac
import os

_N, _R, _P, _DKLEN = 2 ** 14, 8, 1, 32
MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 128  # chan DoS bang mat khau cuc dai


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def hash_password(password: str, *, n: int = _N) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=n, r=_R, p=_P, dklen=_DKLEN)
    return f"scrypt${n}${_R}${_P}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    """So sanh hang-thoi-gian-khong-doi. Chuoi luu hong -> False (khong nem exception)."""
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt, expected = base64.b64decode(salt_b64), base64.b64decode(hash_b64)
        dk = hashlib.scrypt(password.encode(), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError):
        return False


# Hash gia de login voi user khong ton tai van ton cung thoi gian -> khong lo user nao co that.
DUMMY_HASH = hash_password("dummy-password-for-timing")
