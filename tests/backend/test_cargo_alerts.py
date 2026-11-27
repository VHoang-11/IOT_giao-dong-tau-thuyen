"""Cảnh báo hầm hàng: ngưỡng (ngay dưới / bằng / ngay trên), cấu hình, UNKNOWN khi thiếu dữ liệu, vòng đời ACK/CLEARED.

Prototype hỗ trợ giám sát, KHÔNG phải thiết bị an toàn hàng hải được chứng nhận. Test này kiểm tra logic ngưỡng,
không chứng minh tuân thủ SOLAS/IMO.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import Alarm, AuditLog, CargoAlert, Telemetry
from app.models.enums import AlarmState
from cargo import thresholds as th
from cargo.evaluator import (CRITICAL, NORMAL, NOT_CONFIGURED, OUT_OF_RANGE, SENSOR_FAULT, STALE, UNKNOWN, VALUE_MISSING,
                             WARNING, classify, data_class, evaluate, overall, water_mm)
from ingest.service import Outcome, handle_message

EX = Path(__file__).resolve().parents[2] / "contracts" / "examples"
MAIN = "vessel-demo-01"
CARGO = "vessel-demo-01-cargo"
_seq = [100]


def eff(depth=10000.0, scale=5000.0, calibrated=False, overrides=None):
    class C:
        cargo_hold_depth_mm = depth
        water_sensor_full_scale_mm = scale
        thresholds = overrides
        sensor_calibrated = calibrated
        version = 1
        vessel_type = None
        cargo_type = None
    return th.resolve(C())


def ev(e, water_pct=0.0, temp=25.0, hum=50.0, sensor_ok=True, fresh=True, has_sample=True):
    return evaluate(e, has_sample=has_sample, fresh=fresh, sensor_ok=sensor_ok, water_pct=water_pct, temp_c=temp,
                    humidity_pct=hum)


# ================================================================ ngưỡng nhiệt độ: 35 / 40
@pytest.mark.parametrize("t,expect", [
    (34.99, NORMAL), (35.0, WARNING), (35.01, WARNING),
    (39.99, WARNING), (40.0, CRITICAL), (40.01, CRITICAL),
])
def test_temperature_boundaries(t, expect):
    assert ev(eff(), temp=t)["TEMPERATURE"].state == expect


# ================================================================ ngưỡng độ ẩm: 75 / 90
@pytest.mark.parametrize("h,expect", [
    (74.99, NORMAL), (75.0, WARNING), (75.01, WARNING),
    (89.99, WARNING), (90.0, CRITICAL), (90.01, CRITICAL),
])
def test_humidity_boundaries(h, expect):
    assert ev(eff(), hum=h)["HUMIDITY"].state == expect


# ================================================================ nước xâm nhập (mm): 500 / min(0.15 × depth, 2000)
def mm_to_pct(mm, scale):
    return mm * 100.0 / scale


@pytest.mark.parametrize("mm,expect", [
    (499.99, NORMAL), (500.0, WARNING), (500.01, WARNING),
    (1499.99, WARNING), (1500.0, CRITICAL), (1500.01, CRITICAL),    # depth 10000 -> 0.15×10000 = 1500
])
def test_water_boundaries_depth_10000(mm, expect):
    e = eff(depth=10000.0, scale=5000.0)
    assert e.water_critical_mm == 1500.0
    assert ev(e, water_pct=mm_to_pct(mm, 5000.0))["WATER"].state == expect


@pytest.mark.parametrize("mm,expect", [(1999.99, WARNING), (2000.0, CRITICAL), (2000.01, CRITICAL)])
def test_water_critical_is_capped_at_2000mm_for_deep_holds(mm, expect):
    e = eff(depth=30000.0, scale=10000.0)          # 0.15×30000 = 4500 -> bị chặn ở 2000
    assert e.water_critical_mm == 2000.0
    assert ev(e, water_pct=mm_to_pct(mm, 10000.0))["WATER"].state == expect


def test_water_pct_is_converted_to_mm_using_configured_scale():
    assert water_mm(10.0, 5000.0) == 500.0          # đúng 500 mm (không lệch do số thực nhị phân)
    assert ev(eff(), water_pct=10.0)["WATER"].state == WARNING
    assert ev(eff(), water_pct=10.0)["WATER"].value == 500.0
    assert ev(eff(depth=10000.0, scale=2500.0), water_pct=10.0)["WATER"].state == NORMAL   # 250 mm


def test_water_thresholds_follow_hold_depth():
    assert eff(depth=4000.0, scale=1000.0).water_critical_mm == 600.0
    assert eff(depth=4000.0, scale=1000.0).water_warning_mm == 500.0


def test_old_percent_thresholds_35_and_70_are_not_used():
    # 35 % và 70 % của thang đo KHÔNG tự động là WARNING/CRITICAL (chỉ khi quy ra mm vượt ngưỡng mm)
    e = eff(depth=10000.0, scale=1000.0)
    assert ev(e, water_pct=35.0)["WATER"].state == NORMAL      # 350 mm
    assert ev(e, water_pct=70.0)["WATER"].state == WARNING     # 700 mm: WARNING vì ≥ 500 mm, không phải CRITICAL


# ================================================================ cấu hình hợp lệ / không hợp lệ
@pytest.mark.parametrize("depth", [0, -1, 100_001])
def test_invalid_depth_rejected(depth):
    with pytest.raises(th.ConfigInvalid):
        th.validate(depth, None, None)


def test_critical_must_exceed_warning():
    with pytest.raises(th.ConfigInvalid, match="quá nhỏ"):
        th.validate(3333.0, None, None)             # 0.15×3333 = 499.95 ≤ 500
    with pytest.raises(th.ConfigInvalid, match="quá nhỏ"):
        th.validate(3000.0, None, None)
    th.validate(3334.0, None, None)                 # 500.1 > 500: hợp lệ


@pytest.mark.parametrize("ov", [
    {"temperature": {"warning": 40, "critical": 40}},
    {"temperature": {"warning": 41, "critical": 40}},
    {"humidity": {"warning": 90, "critical": 80}},
    {"humidity": {"warning": 75, "critical": 101}},
    {"water": {"warning_mm": 0}},
    {"water": {"critical_cap_mm": 400}},
    {"water": {"critical_fraction_of_depth": 1.5}},
    {"unknown": {"x": 1}},
    {"temperature": {"bogus": 1}},
])
def test_invalid_threshold_overrides_rejected(ov):
    with pytest.raises(th.ConfigInvalid):
        th.validate(10000.0, None, ov)


def test_full_scale_cannot_exceed_depth():
    with pytest.raises(th.ConfigInvalid):
        th.validate(5000.0, 6000.0, None)


def test_overrides_change_boundaries_and_are_flagged_non_default():
    e = eff(overrides={"temperature": {"warning": 30, "critical": 33}})
    assert not e.is_default_thresholds
    assert ev(e, temp=30.0)["TEMPERATURE"].state == WARNING and ev(e, temp=33.0)["TEMPERATURE"].state == CRITICAL
    assert eff().is_default_thresholds


# ================================================================ không mặc định NORMAL khi thiếu/hỏng dữ liệu
def test_no_config_water_is_unknown_not_normal_but_dht_metrics_work():
    e = th.resolve(None)
    assert e.missing == ["cargo_hold_depth_mm", "water_sensor_full_scale_mm"]
    r = ev(e, water_pct=50.0)
    assert r["WATER"].state == UNKNOWN and r["WATER"].reason == NOT_CONFIGURED
    assert r["TEMPERATURE"].state == NORMAL and r["HUMIDITY"].state == NORMAL
    assert overall(r) == UNKNOWN                    # còn chỉ số UNKNOWN ⇒ tổng hợp KHÔNG phải NORMAL


def test_depth_without_scale_is_still_unknown():
    r = ev(eff(depth=10000.0, scale=None), water_pct=50.0)
    assert r["WATER"].state == UNKNOWN and r["WATER"].reason == NOT_CONFIGURED


def test_no_sample_and_stale_are_unknown_for_every_metric():
    for kw, reason in ((dict(has_sample=False), "NO_DATA"), (dict(fresh=False), STALE)):
        r = ev(eff(), **kw)
        assert {m.state for m in r.values()} == {UNKNOWN} and {m.reason for m in r.values()} == {reason}
        assert all(m.value is None for m in r.values())     # không hiển thị số cũ như thời gian thực
        assert overall(r) == UNKNOWN


def test_sensor_fault_makes_dht_metrics_unknown_but_water_still_evaluated():
    r = ev(eff(), sensor_ok=False, temp=None, hum=None, water_pct=50.0)
    assert r["TEMPERATURE"].reason == SENSOR_FAULT and r["HUMIDITY"].reason == SENSOR_FAULT
    assert r["WATER"].state == CRITICAL and overall(r) == CRITICAL    # nước CRITICAL vẫn được báo


@pytest.mark.parametrize("kw,metric", [
    (dict(water_pct=None), "WATER"), (dict(temp=None), "TEMPERATURE"), (dict(hum=None), "HUMIDITY")])
def test_missing_value_is_unknown(kw, metric):
    assert ev(eff(), **kw)[metric].reason == VALUE_MISSING


@pytest.mark.parametrize("kw,metric", [
    (dict(water_pct=100.1), "WATER"), (dict(water_pct=-0.1), "WATER"),
    (dict(temp=80.1), "TEMPERATURE"), (dict(temp=-40.1), "TEMPERATURE"),
    (dict(hum=100.1), "HUMIDITY"), (dict(hum=-0.1), "HUMIDITY")])
def test_out_of_range_is_unknown(kw, metric):
    r = ev(eff(), **kw)[metric]
    assert r.state == UNKNOWN and r.reason == OUT_OF_RANGE


def test_overall_worst_state_wins_over_unknown():
    assert overall(ev(eff(), temp=41.0, hum=None)) == CRITICAL
    assert overall(ev(eff(), temp=36.0)) == WARNING
    assert overall(ev(eff(), water_pct=0.0, temp=20.0, hum=50.0)) == NORMAL


def test_data_class_distinguishes_simulation_uncalibrated_and_calibrated():
    assert data_class("SIMULATION", True) == "SIMULATION"
    assert data_class("SENSOR", False) == "SENSOR_UNCALIBRATED"
    assert data_class("SENSOR", True) == "SENSOR_CALIBRATED"


def test_classify_is_pure_threshold_comparison():
    assert classify(1.0, 2.0, 3.0) == NORMAL and classify(2.0, 2.0, 3.0) == WARNING and classify(3.0, 2.0, 3.0) == CRITICAL


# ================================================================ API + vòng đời cảnh báo (CSDL)
def cargo_msg(**over):
    _seq[0] += 1
    p = json.loads((EX / "cargo_sample.json").read_text(encoding="utf-8"))
    p.update(seq=_seq[0], cargo_water_pct=0.0, cargo_temp_c=25.0, cargo_humidity_pct=50.0)
    p.update(over)
    return p


def send(db, p=None, **over):
    p = p or cargo_msg(**over)
    r = handle_message(db, f"svmg/{CARGO}/cargo", json.dumps(p).encode())
    assert r.outcome == Outcome.STORED, r
    return r


def setup(client, db, auth, depth=10000.0, scale=5000.0, link=True):
    send(db)
    if link:
        send_motion(db)
        assert client.patch(f"/api/v1/devices/{CARGO}", json={"parent_device_id": MAIN}, headers=auth("admin01")).status_code == 200
    if depth is not None or scale is not None:
        r = client.put(f"/api/v1/devices/{CARGO}/cargo/config",
                       json={"cargo_hold_depth_mm": depth, "water_sensor_full_scale_mm": scale})
        assert r.status_code == 200, r.text


def send_motion(db):
    handle_message(db, f"svmg/{MAIN}/telemetry", json.dumps({
        "device_id": MAIN, "boot_id": "b", "seq": 1, "uptime_ms": 1, "t_sim_s": 0, "source_mode": "SIMULATION",
        "roll_deg": 0, "pitch_deg": 0, "class_rf": "NORMAL", "alarm_level": "NORMAL", "model_version": "m",
        "config_version": 1, "sensor_ok": True}).encode())


def alerts(client, state=None):
    q = f"?state={state}" if state else ""
    return client.get(f"/api/v1/devices/{MAIN}/cargo/alerts{q}").json()


def test_default_status_without_config_is_unknown_for_water(client, db, auth):
    setup(client, db, auth, depth=None, scale=None)
    s = client.get(f"/api/v1/devices/{MAIN}/cargo/status").json()
    water = next(m for m in s["nodes"][0]["metrics"] if m["metric"] == "WATER")
    assert water["state"] == "UNKNOWN" and water["reason"] == "NOT_CONFIGURED"
    assert s["state"] == "UNKNOWN" and s["nodes"][0]["missing_config"] == ["cargo_hold_depth_mm", "water_sensor_full_scale_mm"]
    assert "chưa phải thiết bị an toàn hàng hải" in s["disclaimer"]
    assert s["nodes"][0]["data_class"] == "SIMULATION"


def test_status_with_no_cargo_node_is_unknown_no_node(client, db):
    send_motion(db)
    s = client.get(f"/api/v1/devices/{MAIN}/cargo/status").json()
    assert s["state"] == "UNKNOWN" and s["link"] == "NO_NODE" and s["nodes"] == []
    assert client.get("/api/v1/devices/khong-co/cargo/status").status_code == 404


def test_status_reports_thresholds_units_references(client, db, auth):
    setup(client, db, auth)
    n = client.get(f"/api/v1/devices/{MAIN}/cargo/status").json()["nodes"][0]
    byname = {m["metric"]: m for m in n["metrics"]}
    assert byname["WATER"]["unit"] == "mm" and byname["WATER"]["warning"] == 500 and byname["WATER"]["critical"] == 1500
    assert byname["TEMPERATURE"]["basis"] == "AIR_IN_HOLD" and "KHÔNG phải" in byname["TEMPERATURE"]["note"]
    assert any("10.3390/app132312878" in r for r in byname["TEMPERATURE"]["reference"])
    assert any("SOLAS" in r for r in byname["WATER"]["reference"])
    assert n["threshold_version"].startswith("bulk-dry-agri-prototype@v1")


def test_status_becomes_stale_unknown_when_node_goes_silent(client, db, auth, monkeypatch):
    setup(client, db, auth)
    send(db, cargo_water_pct=0.0)
    from cargo import service
    later = datetime.now(timezone.utc) + timedelta(seconds=120)
    with db.no_autoflush:
        s = service.build_status(db, MAIN, now=later)
    assert s["link"] == "STALE" and s["state"] == "UNKNOWN"
    assert {m["state"] for m in s["nodes"][0]["metrics"]} == {"UNKNOWN"}
    assert s["nodes"][0]["raw_water_pct"] is None


def test_alert_opens_at_threshold_and_clears_when_back_to_normal(client, db, auth):
    setup(client, db, auth)
    send(db, cargo_temp_c=34.99)
    assert alerts(client) == []
    send(db, cargo_temp_c=35.0)
    a = alerts(client)[0]
    assert (a["metric"], a["level"], a["state"], a["value"], a["unit"]) == ("TEMPERATURE", "WARNING", "ACTIVE", 35.0, "°C")
    assert a["threshold_warning"] == 35 and a["threshold_critical"] == 40 and a["data_class"] == "SIMULATION"
    assert a["threshold_version"].startswith("bulk-dry-agri-prototype@v1")
    send(db, cargo_temp_c=40.0)
    a = alerts(client)[0]
    assert a["level"] == "CRITICAL" and a["max_level"] == "CRITICAL" and len(alerts(client)) == 1
    send(db, cargo_temp_c=34.0)
    a = alerts(client)[0]
    assert a["state"] == "CLEARED" and a["level"] == "NORMAL" and a["max_level"] == "CRITICAL" and a["cleared_at"]


def test_ack_does_not_clear_and_higher_level_after_ack_reactivates(client, db, auth):
    setup(client, db, auth)
    send(db, cargo_humidity_pct=76.0)
    pk = alerts(client)[0]["id"]
    r = client.post(f"/api/v1/cargo/alerts/{pk}/ack", headers=auth("op01"))
    assert r.status_code == 200 and r.json()["state"] == "ACKED" and r.json()["acked_by"] == "op01"
    assert client.post(f"/api/v1/cargo/alerts/{pk}/ack", headers=auth("op01")).json()["state"] == "ACKED"   # idempotent
    send(db, cargo_humidity_pct=77.0)
    assert alerts(client)[0]["state"] == "ACKED"                                      # cùng mức: vẫn ACKED
    send(db, cargo_humidity_pct=90.0)
    a = alerts(client)[0]
    assert a["state"] == "ACTIVE" and a["escalated"] and a["level"] == "CRITICAL"     # nặng hơn sau ACK: bật lại
    send(db, cargo_humidity_pct=10.0)
    assert alerts(client)[0]["state"] == "CLEARED"
    assert client.post(f"/api/v1/cargo/alerts/{pk}/ack", headers=auth("op01")).status_code == 409
    assert client.post("/api/v1/cargo/alerts/99999/ack", headers=auth("op01")).status_code == 404
    assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "CARGO_ALERT_ACK")) >= 1


def test_unknown_data_does_not_clear_open_alert_nor_open_new_one(client, db, auth):
    setup(client, db, auth)
    send(db, cargo_temp_c=41.0)
    assert alerts(client)[0]["state"] == "ACTIVE"
    send(db, sensor_ok=False, cargo_temp_c=None, cargo_humidity_pct=None)             # DHT hỏng: không kết luận
    a = [x for x in alerts(client) if x["metric"] == "TEMPERATURE"][0]
    assert a["state"] == "ACTIVE" and a["level"] == "CRITICAL"                       # KHÔNG tự giải tỏa vì thiếu dữ liệu
    assert [x for x in alerts(client) if x["metric"] == "HUMIDITY"] == []


def test_water_alert_uses_mm_and_configured_depth(client, db, auth):
    setup(client, db, auth, depth=10000.0, scale=5000.0)
    send(db, cargo_water_pct=9.99)             # 499.5 mm
    assert alerts(client) == []
    send(db, cargo_water_pct=10.0)             # 500 mm
    a = alerts(client)[0]
    assert (a["metric"], a["level"], a["unit"], a["value"]) == ("WATER", "WARNING", "mm", 500.0)
    assert a["threshold_warning"] == 500 and a["threshold_critical"] == 1500
    send(db, cargo_water_pct=30.0)             # 1500 mm
    assert alerts(client)[0]["level"] == "CRITICAL"


def test_water_alerts_not_raised_until_hold_is_configured(client, db, auth):
    setup(client, db, auth, depth=None, scale=None)
    send(db, cargo_water_pct=100.0)
    assert alerts(client) == []                # không giả định kích thước hầm: không mở cảnh báo nước


def test_sensor_data_class_changes_with_calibration_flag(client, db, auth):
    send(db, source_mode="SENSOR")
    send_motion(db)
    client.patch(f"/api/v1/devices/{CARGO}", json={"parent_device_id": MAIN}, headers=auth("admin01"))
    s = client.get(f"/api/v1/devices/{MAIN}/cargo/status").json()["nodes"][0]
    assert s["data_class"] == "SENSOR_UNCALIBRATED"
    client.put(f"/api/v1/devices/{CARGO}/cargo/config", json={"sensor_calibrated": True})
    assert client.get(f"/api/v1/devices/{MAIN}/cargo/status").json()["nodes"][0]["data_class"] == "SENSOR_CALIBRATED"
    send(db, source_mode="SENSOR", cargo_temp_c=36.0)
    assert alerts(client)[0]["data_class"] == "SENSOR_CALIBRATED"


# ================================================================ cấu hình: quyền, kiểm tra, audit, phiên bản
def test_config_requires_supervisor_and_validates(client, db, auth):
    setup(client, db, auth, depth=None, scale=None)
    url = f"/api/v1/devices/{CARGO}/cargo/config"
    assert client.put(url, json={"cargo_hold_depth_mm": 10000}, headers=auth("op01")).status_code == 403
    assert client.put(url, json={"cargo_hold_depth_mm": 3000}).status_code == 422            # CRITICAL ≤ WARNING
    assert client.put(url, json={"cargo_hold_depth_mm": -5}).status_code == 422
    assert client.put(url, json={"water_sensor_full_scale_mm": 100, "cargo_hold_depth_mm": 50}).status_code == 422
    assert client.put(url, json={"thresholds": {"temperature": {"warning": 50, "critical": 40}}}).status_code == 422
    assert client.put(url, json={"bogus": 1}).status_code == 422
    assert client.get(url).json()["configured"] is False                                     # lỗi không ghi gì
    r = client.put(url, json={"cargo_hold_depth_mm": 10000, "water_sensor_full_scale_mm": 5000,
                              "vessel_type": "bulk-carrier", "cargo_type": "rice"})
    assert r.status_code == 200
    c = r.json()
    assert c["version"] == 1 and c["configured"] and c["missing_fields"] == [] and c["vessel_type"] == "bulk-carrier"
    assert c["effective_thresholds"]["water"]["critical_mm"] == 1500.0 and c["uses_default_thresholds"] is True
    r2 = client.put(url, json={"thresholds": {"temperature": {"warning": 30, "critical": 33}}}).json()
    assert r2["version"] == 2 and r2["uses_default_thresholds"] is False
    assert r2["effective_thresholds"]["temperature"]["warning"] == 30 and r2["threshold_version"].endswith("+cfg2")
    r3 = client.put(url, json={"thresholds": None}).json()                                   # null = quay về mặc định
    assert r3["uses_default_thresholds"] is True and r3["version"] == 3
    log = db.scalars(select(AuditLog).where(AuditLog.action == "CARGO_CONFIG_UPDATE").order_by(AuditLog.id)).all()
    assert len(log) == 3 and log[0].detail["before"]["cargo_hold_depth_mm"] is None and log[0].detail["after"]["cargo_hold_depth_mm"] == 10000


def test_config_only_on_cargo_node_and_main_resolves_single_node(client, db, auth):
    setup(client, db, auth, depth=None, scale=None)
    assert client.put(f"/api/v1/devices/{MAIN}/cargo/config", json={"sensor_calibrated": True}).status_code == 200   # 1 Cargo Node: dùng id tàu
    send_motion(db)
    assert client.get("/api/v1/devices/khong-co/cargo/config").status_code == 404


def test_cargo_alerts_are_separate_from_motion_alarms(client, db, auth):
    setup(client, db, auth)
    send(db, cargo_temp_c=45.0, cargo_humidity_pct=95.0)
    assert len(alerts(client)) == 2
    assert db.scalar(select(func.count()).select_from(Alarm)) == 0                  # không đụng bảng alarms (FSM dao động)
    assert client.get(f"/api/v1/alarms?device_id={MAIN}").json() == []
    assert db.scalar(select(func.count()).select_from(Telemetry)) == 1             # chỉ telemetry thử của tàu chính


def test_late_or_duplicate_sample_does_not_flip_state(client, db, auth):
    setup(client, db, auth)
    hi = cargo_msg(cargo_temp_c=41.0)
    send(db, hi)
    lo_old = {**cargo_msg(cargo_temp_c=20.0), "seq": hi["seq"] - 50}                 # seq cũ hơn bản đang giữ
    send(db, lo_old)
    assert alerts(client)[0]["state"] == "ACTIVE"
