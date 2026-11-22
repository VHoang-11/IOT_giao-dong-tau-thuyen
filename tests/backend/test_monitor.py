"""Monitor API (G6).

Quy tac duoc khoa o day:
- KHONG bao gio tra PSI/so lieu gia: drift chua co nguon -> available=false + ly do, khong co so 0 nao.
- Luon kem source_mode; mau sensor_ok=false bi loai va dem rieng.
- Lop chuyen dong RF khong bi doi ten thanh 'muc canh bao'.
"""
from datetime import datetime, timedelta, timezone

import pytest
from conftest import NOAUTH

from sqlalchemy import select

from app.core.config import settings
from app.models import Device, Telemetry
from app.models.enums import AlarmLevel, MotionClass, SourceMode

T0 = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
DEV = "monitor-dev-01"
N, H, P, A, U, F = (MotionClass.NORMAL, MotionClass.HIGH_ROLL, MotionClass.PERSISTENT_OFFSET,
                    MotionClass.AMPLITUDE_GROWTH, MotionClass.UNKNOWN, MotionClass.FAULT)


def tele(i, rf=N, base=N, voyage="V-1", dev=DEV, ok=True, mode=SourceMode.SIMULATION, rx=None, boot="b1"):
    return Telemetry(
        device_id=dev, boot_id=boot, seq=i, t_sim_s=float(i), uptime_ms=i, source_mode=mode, voyage_id=voyage,
        roll_deg=1.0, pitch_deg=0.0, class_rf=rf, class_baseline_b=base, alarm_level=AlarmLevel.NORMAL,
        model_version="rf_v1", config_version=1, sensor_ok=ok, server_rx_time=rx or T0 + timedelta(seconds=i))


@pytest.fixture()
def dev(db):
    db.add(Device(device_id=DEV))
    db.commit()


def agreement(client, **p):
    r = client.get("/api/v1/monitor/agreement", params={"device_id": DEV, **p})
    assert r.status_code == 200, r.text
    return r.json()


def drift(client, **p):
    r = client.get("/api/v1/monitor/drift", params={"device_id": DEV, **p})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- quyen va tham so

@pytest.mark.parametrize("path", ["agreement", "drift"])
def test_requires_login_and_valid_device(client, dev, path):
    url = f"/api/v1/monitor/{path}"
    assert client.get(url, params={"device_id": DEV}, headers=NOAUTH).status_code == 401
    assert client.get(url).status_code == 422                                          # thieu device_id
    assert client.get(url, params={"device_id": "bad id!"}).status_code == 422
    assert client.get(url, params={"device_id": "x" * 65}).status_code == 422
    assert client.get(url, params={"device_id": "ghost"}).status_code == 404           # thiet bi khong ton tai


def test_operator_can_view(client, dev, auth):
    for path in ("agreement", "drift"):
        assert client.get(f"/api/v1/monitor/{path}", params={"device_id": DEV}, headers=auth("op01")).status_code == 200


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 10001}, {"voyage_id": ""}, {"voyage_id": "bad id"}])
def test_agreement_parameter_validation(client, dev, params):
    assert client.get("/api/v1/monitor/agreement", params={"device_id": DEV, **params}).status_code == 422


@pytest.mark.parametrize("hours", [0, 169, -1])
def test_drift_window_validation(client, dev, hours):
    assert client.get("/api/v1/monitor/drift", params={"device_id": DEV, "window_hours": hours}).status_code == 422


# ---------------------------------------------------------------- agreement

def test_agreement_without_data_is_null_not_zero(client, dev):
    s = agreement(client)
    assert s["samples_considered"] == 0 and s["agreement_rate"] is None and s["by_rf_class"] == {}
    assert s["source_label"] == "UNKNOWN" and s["source_modes"] == [] and s["first_sample_at"] is None
    assert any("Chưa có mẫu" in n for n in s["notes"])


def test_agreement_exact_numbers_and_per_class(client, db, dev):
    db.add_all([tele(0, N, N), tele(1, N, N), tele(2, N, H),          # NORMAL: 2/3 khop
                tele(3, H, H), tele(4, H, N),                          # HIGH_ROLL: 1/2
                tele(5, P, P), tele(6, A, A), tele(7, A, A)])          # 1/1 va 2/2
    db.commit()
    s = agreement(client)
    assert s["samples_considered"] == 8 and s["matched"] == 6 and s["agreement_rate"] == pytest.approx(6 / 8)
    assert s["by_rf_class"]["NORMAL"] == {"rf_total": 3, "matched": 2, "rate": pytest.approx(2 / 3)}
    assert s["by_rf_class"]["HIGH_ROLL"] == {"rf_total": 2, "matched": 1, "rate": 0.5}
    assert set(s["by_rf_class"]) == {"NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH"}


def test_agreement_does_not_rename_motion_classes_as_alarm_levels(client, db, dev):
    db.add_all([tele(0, H, H), tele(1, P, P), tele(2, A, A)])
    db.commit()
    text = str(agreement(client)).lower()
    assert "warning" not in text and "critical" not in text        # lop chuyen dong != muc canh bao


def test_agreement_excludes_and_counts_sensor_faults(client, db, dev):
    db.add_all([tele(0, N, N), tele(1, N, N), tele(2, N, H, ok=False), tele(3, F, U, ok=False)])
    db.commit()
    s = agreement(client)
    assert s["samples_considered"] == 2 and s["matched"] == 2 and s["agreement_rate"] == 1.0
    assert s["excluded_sensor_fault"] == 2                                          # mau loi duoc dem rieng
    assert any("sensor_ok=false" in n for n in s["notes"])


def test_agreement_ignores_samples_without_baseline(client, db, dev):
    db.add_all([tele(0, N, N), tele(1, N, None), tele(2, H, None)])
    db.commit()
    assert agreement(client)["samples_considered"] == 1


def test_agreement_always_reports_source_mode(client, db, dev):
    db.add_all([tele(0, mode=SourceMode.SIMULATION)])
    db.commit()
    s = agreement(client)
    assert s["source_label"] == "SIMULATION" and s["source_modes"] == ["SIMULATION"]
    db.add(tele(1, mode=SourceMode.SENSOR))
    db.commit()
    s = agreement(client)
    assert s["source_label"] == "MIXED" and s["source_modes"] == ["SENSOR", "SIMULATION"]
    assert any("trộn SENSOR và SIMULATION" in n for n in s["notes"])


def test_agreement_rf_fault_can_never_match_and_is_explained(client, db, dev):
    db.add_all([tele(0, N, N), tele(1, F, U)])                      # sensor_ok = true nhung RF khong chac chan
    db.commit()
    s = agreement(client)
    assert s["by_rf_class"]["FAULT"]["matched"] == 0
    assert any("FAULT" in n and "Baseline" in n for n in s["notes"])


def test_agreement_filters_by_voyage_and_device(client, db, dev):
    db.add(Device(device_id="other"))
    db.add_all([tele(0, voyage="V-1"), tele(1, N, H, voyage="V-1"), tele(2, voyage="V-2"),
                tele(3, voyage="V-1", dev="other")])
    db.commit()
    assert agreement(client)["samples_considered"] == 3
    v1 = agreement(client, voyage_id="V-1")
    assert v1["samples_considered"] == 2 and v1["matched"] == 1 and v1["voyage_id"] == "V-1"
    assert agreement(client, voyage_id="V-NONE")["agreement_rate"] is None


def test_agreement_limit_takes_the_most_recent_samples_by_time_not_by_id(client, db, dev):
    # chen mau CU (khop) SAU mau moi (khong khop): 'gan nhat' phai theo gio nhan, khong theo id
    db.add_all([tele(10, N, H, rx=T0 + timedelta(hours=2)), tele(11, N, H, rx=T0 + timedelta(hours=3))])
    db.commit()
    db.add_all([tele(i, N, N, rx=T0 + timedelta(minutes=i)) for i in range(5)])   # id lon hon nhung cu hon
    db.commit()
    s = agreement(client, limit=2)
    assert s["samples_considered"] == 2 and s["matched"] == 0                   # 2 mau moi nhat theo thoi gian
    assert agreement(client, limit=7)["samples_considered"] == 7
    assert s["first_sample_at"] < s["last_sample_at"]


def test_agreement_timestamps_are_utc(client, db, dev):
    db.add(tele(0))
    db.commit()
    s = agreement(client)
    assert s["first_sample_at"].endswith(("Z", "+00:00")) and s["last_sample_at"].endswith(("Z", "+00:00"))


# ---------------------------------------------------------------- drift: khong bao gio so gia

def test_drift_is_unavailable_and_returns_no_fabricated_numbers(client, db, dev):
    db.add_all([tele(i, rx=datetime.now(timezone.utc) - timedelta(minutes=i)) for i in range(3)])
    db.commit()
    d = drift(client)
    assert d["available"] is False and d["source"] == "unavailable"
    assert d["features"] == [] and d["flagged_count"] is None                   # None, KHONG phai 0
    assert "psi" not in str(d["features"]).lower()
    assert "mock" not in str(d).lower() and "0.0" not in str(d["features"])
    assert "M2" in d["reason"] and "đặc trưng" in d["reason"]


def test_drift_still_reports_real_window_sample_count_and_sources(client, db, dev):
    now = datetime.now(timezone.utc)
    db.add_all([tele(0, rx=now - timedelta(minutes=30)), tele(1, rx=now - timedelta(minutes=10), mode=SourceMode.SENSOR),
                tele(2, rx=now - timedelta(hours=5)), tele(3, rx=now - timedelta(days=3))])
    db.commit()
    d = drift(client, window_hours=1)
    assert d["window_samples"] == 2 and d["source_modes"] == ["SENSOR", "SIMULATION"] and d["window_hours"] == 1
    assert drift(client, window_hours=24)["window_samples"] == 3
    assert drift(client, window_hours=168)["window_samples"] == 4


def _write_contract(tmp_path, monkeypatch, **over):
    """Hop dong gia lap NGAN, chi de thu cau truc doc file (khong phai hop dong that cua M1/M2)."""
    import json
    c = {"feature_schema_version": "test-v1", "preprocessing_version": "pp-test", "feature_count": 2,
         "features": [{"index": 1, "name": "feat_b", "unit": "deg"}, {"index": 0, "name": "feat_a", "unit": "deg"}]}
    c.update(over)
    f = tmp_path / "features.json"
    f.write_text(json.dumps(c), encoding="utf-8")
    monkeypatch.setattr(settings, "feature_contract_path", str(f))


def test_drift_reads_expected_features_from_contract_file_in_index_order(client, dev, tmp_path, monkeypatch):
    _write_contract(tmp_path, monkeypatch)
    d = drift(client)
    assert d["expected_features"] == ["feat_a", "feat_b"] and d["feature_contract_available"] is True
    assert d["feature_schema_version"] == "test-v1" and d["feature_count"] == 2
    assert "2 đặc trưng" in d["reason"]


def test_drift_without_contract_file_lists_nothing_and_does_not_guess(client, dev, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "feature_contract_path", str(tmp_path / "missing.json"))
    d = drift(client)
    assert d["expected_features"] == [] and d["feature_contract_available"] is False
    assert d["schema_match"] is None and d["available"] is False


def test_drift_ignores_self_contradicting_contract(client, dev, tmp_path, monkeypatch):
    _write_contract(tmp_path, monkeypatch, feature_count=5)          # khai bao 5 nhung chi co 2 dac trung
    assert drift(client)["feature_contract_available"] is False


def test_schema_match_compares_device_report_with_contract(client, db, dev, tmp_path, monkeypatch):
    _write_contract(tmp_path, monkeypatch)
    assert drift(client)["schema_match"] is None                      # thiet bi chua bao -> khong ket luan
    d = db.scalar(select(Device))
    d.feature_schema_version, d.feature_count, d.preprocessing_version = "test-v1", 2, "pp-test"
    db.commit()
    assert drift(client)["schema_match"] is True
    d.feature_count = 14                                              # firmware cu
    db.commit()
    r = drift(client)
    assert r["schema_match"] is False and r["device_feature_count"] == 14


def test_real_contract_file_loads_if_present():
    from pathlib import Path
    from monitor.feature_contract import contract_path, load_contract
    if not Path(contract_path()).exists():
        pytest.skip("contracts/features23.json chua co trong nhanh nay (se co sau khi merge main)")
    fc = load_contract()
    assert fc is not None and fc.count == len(fc.names) == 23


def test_empty_window_has_zero_samples_but_is_still_unavailable(client, dev):
    d = drift(client)
    assert d["window_samples"] == 0 and d["source_modes"] == [] and d["available"] is False
