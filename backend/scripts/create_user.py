"""Tao/dat lai nguoi dung tu dong lenh (khong qua API).

  python scripts/create_user.py <username> <OPERATOR|SUPERVISOR|ADMIN>
Mat khau duoc hoi bang getpass (khong hien tren man hinh, khong nam trong lich su lenh).
Dung de tao admin dau tien thay cho ADMIN_PASSWORD trong .env.
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: E402,F401
from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.models.enums import Role  # noqa: E402
from app.services import auth  # noqa: E402


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[2].upper() not in Role.__members__:
        print(__doc__)
        return 2
    username, role = sys.argv[1], Role[sys.argv[2].upper()]
    pw = getpass.getpass("Mật khẩu: ")
    if pw != getpass.getpass("Nhập lại: "):
        print("Hai mật khẩu không khớp")
        return 1
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        try:
            auth.create_user(db, "cli", username, pw, role)
        except (auth.UserConflict, auth.InvalidInput) as e:
            print(f"Lỗi: {e}")
            return 1
    print(f"Đã tạo {username} ({role.value})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
