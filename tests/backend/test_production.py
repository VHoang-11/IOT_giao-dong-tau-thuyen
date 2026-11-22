"""Cau hinh san sang production: tai lieu API, TLS MQTT, phien ban co dinh."""
import importlib
import logging
import re
from pathlib import Path

import paho.mqtt.client as mqtt
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, settings

REPO = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- /docs

@pytest.mark.parametrize("env,override,expected", [
    ("dev", None, True), ("production", None, False), ("Production", None, False),
    ("production", True, True), ("dev", False, False)])
def test_docs_toggle_logic(env, override, expected):
    assert Settings(env=env, docs_enabled=override).docs_on is expected


def test_docs_available_in_dev(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_docs_hidden_in_production_but_api_still_works(monkeypatch):
    import main
    monkeypatch.setattr(settings, "env", "production")
    try:
        importlib.reload(main)
        with TestClient(main.app) as c:
            for path in ("/docs", "/redoc", "/openapi.json"):
                assert c.get(path).status_code == 404, path
            assert c.get("/healthz").status_code == 200
    finally:
        monkeypatch.undo()
        importlib.reload(main)  # tra module ve trang thai dev cho cac test sau


def test_openapi_can_still_be_exported_in_production(monkeypatch):
    """Tai lieu tat o production nhung van xuat file duoc bang script (dung cho contracts/openapi.yaml)."""
    import main
    monkeypatch.setattr(settings, "env", "production")
    try:
        importlib.reload(main)
        assert "/healthz" in main.app.openapi()["paths"]
    finally:
        monkeypatch.undo()
        importlib.reload(main)


# ---------------------------------------------------------------- TLS MQTT

@pytest.fixture()
def tls_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(mqtt.Client, "tls_set", lambda self, **kw: calls.append(kw))
    return calls


def test_mqtt_tls_enabled_uses_given_ca(monkeypatch, tls_calls):
    from ingest.consumer import MqttConsumer
    monkeypatch.setattr(settings, "mqtt_tls", True)
    monkeypatch.setattr(settings, "mqtt_ca_certs", "/etc/ssl/broker-ca.crt")
    MqttConsumer()
    assert tls_calls == [{"ca_certs": "/etc/ssl/broker-ca.crt"}]


def test_mqtt_tls_without_ca_uses_system_store_and_never_disables_verification(monkeypatch, tls_calls):
    from ingest.consumer import MqttConsumer
    monkeypatch.setattr(settings, "mqtt_tls", True)
    monkeypatch.setattr(settings, "mqtt_ca_certs", "")
    MqttConsumer()
    assert tls_calls == [{"ca_certs": None}]
    assert not any("insecure" in k for kw in tls_calls for k in kw)      # khong co duong tat xac minh chung chi


def test_mqtt_plaintext_by_default_and_warns_only_in_production(monkeypatch, tls_calls, caplog):
    from ingest.consumer import MqttConsumer
    MqttConsumer()
    assert tls_calls == []                                               # mac dinh khong TLS
    assert not [r for r in caplog.records if "KHÔNG mã hóa" in r.getMessage() or "KHONG ma hoa" in r.getMessage()]
    monkeypatch.setattr(settings, "env", "production")
    with caplog.at_level(logging.WARNING, logger="svmg.ingest"):
        MqttConsumer()
    assert any("KHONG ma hoa" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------- tai lap duoc

def test_requirements_are_pinned_for_reproducible_builds():
    for name in ("requirements.txt", "requirements-dev.txt"):
        for line in (REPO / "backend" / name).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "-r ")):
                continue
            assert re.match(r"^[A-Za-z0-9_.\-]+(\[[a-z,]+\])?==[0-9][^\s]*$", line), f"{name}: '{line}' chua ghim =="


def test_pinned_versions_match_what_is_installed():
    """Neu co nguoi nang thu vien ma khong cap nhat requirements.txt, test nay bao ngay."""
    from importlib.metadata import version
    for line in (REPO / "backend" / "requirements.txt").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-]+)(?:\[[a-z,]+\])?==(\S+)$", line.strip())
        if m:
            assert version(m.group(1)) == m.group(2), f"{m.group(1)}: requirements ghi {m.group(2)}, dang cai {version(m.group(1))}"


def test_dockerfile_matches_the_tested_python_and_runs_non_root():
    d = (REPO / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert "python:3.13" in d and "USER svmg" in d
    assert "uvicorn" in d and "--host" in d
