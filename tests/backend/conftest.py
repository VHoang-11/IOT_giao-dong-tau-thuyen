import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"  # in-memory cho test
os.environ["MQTT_ENABLED"] = "false"
os.environ["ALARM_ESCALATION_ENABLED"] = "false"  # test goi escalate_overdue truc tiep
os.environ["JWT_SECRET"] = "test-secret-key-for-unit-tests-0123456789-abcdef"
os.environ["ADMIN_PASSWORD"] = ""  # khong tu tao admin khi test
# AN TOAN: .env cua may dev co the chua token that -> ep rong de test KHONG BAO GIO gui tin that
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = ""
os.environ["EMAIL_WEBHOOK_URL"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.core.passwords import hash_password  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.models import User  # noqa: E402
from app.models.enums import Role  # noqa: E402
from main import app  # noqa: E402

USERS = {"op01": Role.OPERATOR, "sup01": Role.SUPERVISOR, "admin01": Role.ADMIN}
PASSWORD = "correct-horse-battery"
_HASH = hash_password(PASSWORD)  # bam 1 lan cho ca phien test (scrypt cham co chu y)
NOAUTH = {"Authorization": ""}   # ghi de header mac dinh cua client -> request an danh


def bearer(username: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(username)[0]}"}


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = SessionLocal()
    s.add_all(User(username=n, password_hash=_HASH, role=r) for n, r in USERS.items())
    s.commit()
    from app.services.auth import limiter
    limiter._fails.clear()
    limiter._locked_until.clear()
    yield s
    s.close()


@pytest.fixture()
def auth():
    """auth('op01') -> header Authorization cua user do."""
    return bearer


@pytest.fixture()
def client(db):
    """Mac dinh dang nhap la supervisor 'sup01' (khop vi du hop dong). Muon doi quyen: truyen headers=auth(...)."""
    with TestClient(app, headers=bearer("sup01")) as c:
        yield c
