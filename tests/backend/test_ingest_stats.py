import json
import threading
from pathlib import Path

import pytest
from conftest import NOAUTH
from sqlalchemy import select

from app.models import AuditLog
from ingest import stats as stats_mod
from ingest.service import handle_message
from ingest.stats import IngestStats, stats

EX = Path(__file__).resolve().parents[2] / "contracts" / "examples"
DEV = "vessel-demo-01"


def tele(seq=125, **over):
    p = json.loads((EX / "telemetry_sample.json").read_text(encoding="utf-8"))
    p.update(seq=seq, **over)
    return json.dumps(p).encode()


def send(db, kind, payload, dev=DEV):
    return handle_message(db, f"svmg/{dev}/{kind}", payload)


def get(client, headers=None):
    r = client.get("/api/v1/ingest/stats", **({"headers": headers} if headers else {}))
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- quyen

def test_permissions(client, auth):
    assert client.get("/api/v1/ingest/stats", headers=NOAUTH).status_code == 401
    assert client.get("/api/v1/ingest/stats", headers=auth("op01")).status_code == 403       # Operator khong xem
    assert client.get("/api/v1/ingest/stats", headers=auth("sup01")).status_code == 200
    assert client.post("/api/v1/ingest/stats/reset", headers=auth("sup01")).status_code == 403   # reset chi Admin
    assert client.post("/api/v1/ingest/stats/reset", headers=NOAUTH).status_code == 401


# ---------------------------------------------------------------- dem dung

def test_empty_stats_have_null_rates_not_zero(client):
    s = get(client)
    assert s["total_messages"] == 0 and s["totals"] == {} and s["recent_errors"] == []
    assert all(v is None for v in s["rates"].values())
    assert s["since"].endswith(("Z", "+00:00"))


def test_counts_each_outcome_by_kind_device_and_computes_rates(client, db):
    send(db, "telemetry", tele(1))                                           # STORED
    send(db, "telemetry", tele(2))                                           # STORED
    send(db, "telemetry", tele(2))                                           # DUPLICATE
    send(db, "telemetry", tele(3, class_rf="CAPSIZE_FORECAST"))              # INVALID
    send(db, "telemetry", tele(4), dev="vessel-other")                       # REJECTED: device_id payload khac topic
    s = get(client)
    assert s["total_messages"] == 5
    assert s["totals"] == {"STORED": 2, "DUPLICATE": 1, "INVALID": 1, "REJECTED": 1}
    assert s["by_kind"]["telemetry"] == {"STORED": 2, "DUPLICATE": 1, "INVALID": 1, "REJECTED": 1}
    assert s["by_device"][DEV] == {"STORED": 2, "DUPLICATE": 1, "INVALID": 1}
    assert s["by_device"]["vessel-other"] == {"REJECTED": 1}
    r = s["rates"]
    assert r["stored"] == pytest.approx(0.4) and r["duplicate"] == pytest.approx(0.2)
    assert r["invalid"] == pytest.approx(0.2) and r["rejected"] == pytest.approx(0.2) and r["ignored"] is None or r["ignored"] == 0


def test_counts_other_message_kinds(client, db):
    send(db, "status", json.dumps({"state": "online"}).encode())
    send(db, "health", json.dumps({"device_id": DEV, "free_heap_bytes": 1, "uptime_ms": 1, "sensor_ok": True}).encode())
    s = get(client)
    assert s["by_kind"]["status"] == {"STORED": 1} and s["by_kind"]["health"] == {"STORED": 1}


def test_bad_topic_counts_under_unknown(client, db):
    handle_message(db, "other/x/telemetry", b"{}")
    s = get(client)
    assert s["by_device"] == {"_unknown": {"INVALID": 1}} and s["by_kind"]["unknown"] == {"INVALID": 1}


# ---------------------------------------------------------------- loi gan day (de M1 tu sua firmware)

def test_recent_errors_explain_why_a_message_was_rejected(client, db):
    send(db, "telemetry", tele(1, class_rf="CAPSIZE_FORECAST"))
    send(db, "telemetry", b"{not json")
    send(db, "telemetry", tele(2), dev="vessel-other")
    send(db, "telemetry", tele(3))                                           # hop le: khong vao danh sach loi
    errs = get(client)["recent_errors"]
    assert len(errs) == 3 and [e["outcome"] for e in errs] == ["REJECTED", "INVALID", "INVALID"]   # moi nhat truoc
    assert errs[0]["device_id"] == "vessel-other" and "khac topic" in errs[0]["reason"]
    assert "JSON" in errs[1]["reason"] and "class_rf" in errs[2]["reason"]
    assert errs[2]["topic"] == f"svmg/{DEV}/telemetry" and errs[2]["ts"].endswith(("Z", "+00:00"))


def test_recent_errors_are_bounded_and_reasons_truncated():
    s = IngestStats()
    for i in range(stats_mod.MAX_RECENT + 25):
        s.add("telemetry", "INVALID", DEV, "t", "x" * 1000)
    snap = s.snapshot()
    assert len(snap["recent_errors"]) == stats_mod.MAX_RECENT
    assert all(len(e["reason"]) == stats_mod.MAX_REASON for e in snap["recent_errors"])


def test_device_table_is_bounded_against_device_id_flooding():
    s = IngestStats()
    for i in range(stats_mod.MAX_DEVICES + 500):
        s.add("telemetry", "STORED", f"dev-{i}")
    snap = s.snapshot()
    assert len(snap["by_device"]) == stats_mod.MAX_DEVICES + 1                # +1 = nhom '_other'
    assert snap["by_device"]["_other"]["STORED"] == 500
    assert snap["total_messages"] == stats_mod.MAX_DEVICES + 500               # tong van dung


# ---------------------------------------------------------------- reset + audit

def test_reset_clears_counters_and_is_audited(client, db, auth):
    send(db, "telemetry", tele(1))
    send(db, "telemetry", b"nope")
    assert get(client)["total_messages"] == 2
    r = client.post("/api/v1/ingest/stats/reset", headers=auth("admin01"))
    assert r.status_code == 204
    s = get(client)
    assert s["total_messages"] == 0 and s["recent_errors"] == [] and s["by_device"] == {}
    row = db.scalar(select(AuditLog).where(AuditLog.action == "INGEST_STATS_RESET"))
    assert row.actor == "admin01" and row.detail == {"messages_before_reset": 2}


# ---------------------------------------------------------------- da luong

def test_concurrent_writers_do_not_lose_counts():
    s = IngestStats()

    def work():
        for _ in range(2000):
            s.add("telemetry", "STORED", DEV)

    threads = [threading.Thread(target=work) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert s.snapshot()["total_messages"] == 16000


def test_global_stats_object_is_the_one_used_by_ingest(db):
    send(db, "telemetry", tele(1))
    assert stats.snapshot()["totals"] == {"STORED": 1}
