import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"  # in-memory cho test
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def client(db):
    with TestClient(app) as c:
        yield c
