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
    from ingest.stats import stats
    limiter._fails.clear()
    limiter._locked_until.clear()
    stats.reset()  # bo dem ingest la trang thai toan cuc: dat lai de cac test khong anh huong nhau
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


def firmware_mute_state(db, device_id="vessel-demo-01", boot="b1", level="WARNING", alarm_state="ACTIVE", alarm_id="A-1"):
    """Dung trang thai ma FIRMWARE xet khi mute (core/src/alarm_fsm.c): canh bao cua boot + telemetry moi nhat o muc `level`.
    Chi ghi vao CSDL test trong bo nho. Tra ve Alarm."""
    from datetime import datetime, timezone

    from app.models import Alarm, Telemetry
    from app.models.enums import AlarmLevel, AlarmState, MotionClass, SourceMode
    now = datetime.now(timezone.utc)
    a = Alarm(alarm_id=alarm_id, boot_id=boot, device_id=device_id, last_seq=1, state=AlarmState(alarm_state),
              level=AlarmLevel(level), max_level=AlarmLevel(level), source_mode=SourceMode.SIMULATION, opened_at=now,
              escalated=False)
    db.add(a)
    db.add(Telemetry(device_id=device_id, boot_id=boot, seq=1000 + db.query(Telemetry).count(), t_sim_s=1.0, uptime_ms=1,
                     source_mode=SourceMode.SIMULATION, roll_deg=0.0, pitch_deg=0.0, class_rf=MotionClass.UNKNOWN,
                     alarm_level=AlarmLevel(level), model_version="none", config_version=1, sensor_ok=True, server_rx_time=now))
    db.commit()
    return a
