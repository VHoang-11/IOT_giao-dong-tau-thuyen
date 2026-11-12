import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


def test_healthz():
    with TestClient(app) as c:
        r = c.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
