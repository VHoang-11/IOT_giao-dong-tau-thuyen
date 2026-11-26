"""Backend khop voi THIET BI THAT (M1): firmware/lib/svmg_msg/src/msg.cpp va firmware/docs/CONTRACT_PROPOSALS.md.

Cac ban tin ben duoi dung DUNG dang thiet bi phat (theo msg.cpp): khong co voyage_id, bo cac truong tuy chon khi du lieu
chua du, co truong phu (acked, data_status, sea_state), acked_by la 'device_button' / 'remote'.
Day la payload kiem thu dat trong file test, khong phai du lieu that.
"""
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import Alarm, Device, Telemetry
from ingest.service import Outcome, handle_message

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
DEV = "vessel-demo-01"


def device_telemetry(seq, boot="a1b2c3d4", unknown_data=False, **over):
    """Dang telemetry cua M1: KHONG co voyage_id; data UNKNOWN thi bo mai/rms/heel/trend; co truong phu."""
    p = {"device_id": DEV, "boot_id": boot, "seq": seq, "t_sim_s": 100.0 + seq, "uptime_ms": 1000 * seq, "timewarp": 1,
         "source_mode": "SIMULATION", "synthetic": True, "scenario_id": "S0", "roll_deg": 1.25, "pitch_deg": 0.1,
         "class_rf": "UNKNOWN", "alarm_level": "NORMAL", "model_version": "stub", "config_version": 7,
         "sensor_ok": True, "acked": False, "data_status": 0, "sea_state": 2}
    if not unknown_data:
        p.update(rms_roll_deg=0.9, heel_offset_deg=0.05, trend_rms_deg_per_min=0.01, mai=12, class_baseline_b="NORMAL")
    p.update(over)
    return p


def device_event(seq, level, alarm_id="A-0001", prev="NORMAL", acked_by=None, boot="a1b2c3d4"):
    return {"device_id": DEV, "boot_id": boot, "seq": seq, "type": "ALARM_STATE", "alarm_id": alarm_id, "level": level,
            "prev_level": prev, "class": "HIGH_ROLL", "t_sim_s": 100.0 + seq, "acked_by": acked_by}


def send(db, kind, payload, rx):
    return handle_message(db, f"svmg/{DEV}/{kind}", json.dumps(payload).encode(), rx_time=rx)


def summary(client, vid):
    r = client.get(f"/api/v1/voyages/{vid}/summary")
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture()
def registered(db):
    send(db, "telemetry", device_telemetry(0), T0 - timedelta(minutes=10))     # thiet bi tu dang ky, TRUOC khi co chuyen


# ================= B8: voyage_id khong do thiet bi phat -> backend gan =================

def test_real_device_telemetry_is_accepted_even_without_optional_fields(db):
    assert send(db, "telemetry", device_telemetry(1, unknown_data=True), T0).outcome == Outcome.STORED
    t = db.scalar(select(Telemetry).where(Telemetry.seq == 1))
    assert t.mai is None and t.rms_roll_deg is None and t.heel_offset_deg is None and t.class_baseline_b is None
    assert t.voyage_id is None                                                  # chua co chuyen nao dang chay


def test_telemetry_is_attributed_to_the_active_voyage_at_receipt_time(client, db, registered):
    send(db, "telemetry", device_telemetry(1), T0 - timedelta(minutes=1))       # TRUOC khi bat dau chuyen
    assert client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-REAL-1"}).status_code == 201
    for i in range(2, 7):
        send(db, "telemetry", device_telemetry(i), T0 + timedelta(seconds=5 * i))   # trong chuyen, khong co voyage_id
    assert client.post("/api/v1/voyages/V-REAL-1/end").status_code == 200
    send(db, "telemetry", device_telemetry(7), T0 + timedelta(minutes=5))       # SAU khi ket thuc chuyen
    s = summary(client, "V-REAL-1")
    assert s["telemetry_rows"] == 5 and s["data_quality"]["samples"] == 5       # dung 5 mau thuoc chuyen
    rows = {t.seq: t.voyage_id for t in db.scalars(select(Telemetry))}
    assert rows == {0: None, 1: None, 2: "V-REAL-1", 3: "V-REAL-1", 4: "V-REAL-1", 5: "V-REAL-1", 6: "V-REAL-1", 7: None}


def test_report_csv_and_replay_find_the_attributed_samples(client, db, registered):
    client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-REAL-2"})
    for i in range(1, 6):
        send(db, "telemetry", device_telemetry(i), T0 + timedelta(seconds=i))
    csv_rows = client.get("/api/v1/voyages/V-REAL-2/telemetry.csv").content.decode("utf-8-sig").strip().splitlines()
    assert len(csv_rows) == 1 + 5
    replay = client.get("/api/v1/voyages/V-REAL-2/replay").json()
    assert [t["seq"] for t in replay["telemetry"]] == [1, 2, 3, 4, 5] and replay["meta"]["total_samples"] == 5
    assert replay["telemetry"][0]["source_mode"] == "SIMULATION"


def test_two_devices_are_attributed_to_their_own_voyages(client, db):
    for dev in ("ship-a", "ship-b"):
        handle_message(db, f"svmg/{dev}/telemetry", json.dumps(device_telemetry(0, device_id=dev)).encode(), rx_time=T0)
        client.post("/api/v1/voyages", json={"device_id": dev, "voyage_id": f"V-{dev}"})
    for dev in ("ship-a", "ship-b"):
        for i in (1, 2):
            handle_message(db, f"svmg/{dev}/telemetry", json.dumps(device_telemetry(i, device_id=dev)).encode(),
                           rx_time=T0 + timedelta(seconds=i))
    assert summary(client, "V-ship-a")["telemetry_rows"] == 2 and summary(client, "V-ship-b")["telemetry_rows"] == 2


def test_voyage_id_sent_by_a_source_is_kept_not_overwritten(client, db, registered):
    client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-ACTIVE"})
    send(db, "telemetry", device_telemetry(1, voyage_id="V-FROM-SOURCE"), T0)
    assert db.scalar(select(Telemetry).where(Telemetry.seq == 1)).voyage_id == "V-FROM-SOURCE"


def test_explicit_null_voyage_id_is_treated_as_missing(client, db, registered):
    client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-ACTIVE"})
    send(db, "telemetry", device_telemetry(1, voyage_id=None), T0)
    assert db.scalar(select(Telemetry).where(Telemetry.seq == 1)).voyage_id == "V-ACTIVE"


def test_alarm_opened_in_a_voyage_belongs_to_it_even_before_the_next_telemetry(client, db, registered):
    client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-REAL-3"})
    send(db, "event", device_event(1, "WARNING", prev="NORMAL"), T0)          # chua co telemetry nao trong chuyen
    assert db.scalar(select(Alarm)).voyage_id == "V-REAL-3"
    assert summary(client, "V-REAL-3")["alarms"]["total"] == 1


def test_alarm_outside_any_voyage_has_no_voyage(db, registered):
    send(db, "event", device_event(1, "WARNING"), T0)
    assert db.scalar(select(Alarm)).voyage_id is None


# ================= B7: seq dung chung telemetry + event =================

def test_seq_used_by_events_is_not_counted_as_lost_telemetry(client, db, registered):
    client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-SEQ"})
    # seq 1..10: telemetry o 1,2,4,5,6,8,9,10; event o 3 va 7 -> khong mat ban tin nao
    for i in (1, 2, 4, 5, 6, 8, 9, 10):
        send(db, "telemetry", device_telemetry(i), T0 + timedelta(seconds=i))
    send(db, "event", device_event(3, "CAUTION"), T0 + timedelta(seconds=3))
    send(db, "event", device_event(7, "NORMAL", prev="CAUTION"), T0 + timedelta(seconds=7))
    q = summary(client, "V-SEQ")["data_quality"]
    assert (q["samples"], q["expected_samples"], q["missing_samples"], q["seq_used_by_events"]) == (8, 8, 0, 2)
    assert q["received_rate"] == 1.0


def test_unexplained_gaps_are_unclassified_not_assumed_lost(client, db, registered):
    client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-SEQ2"})
    for i in (1, 2, 5, 6, 10):                                                  # khoang trong 3,4,7,8,9; seq 3 la event
        send(db, "telemetry", device_telemetry(i), T0 + timedelta(seconds=i))
    send(db, "event", device_event(3, "CAUTION"), T0 + timedelta(seconds=3))
    q = summary(client, "V-SEQ2")["data_quality"]
    assert q["receive_status"] == "INSUFFICIENT_EVIDENCE" and q["samples"] == 5
    assert (q["seq_span"], q["seq_gaps"], q["seq_used_by_events"], q["seq_gaps_unclassified"]) == (10, 5, 1, 4)
    assert q["received_rate"] is None and q["expected_samples"] is None and q["missing_samples"] is None   # khong doan
    assert q["received_rate_lower_bound"] == pytest.approx(5 / 9)               # truong hop xau nhat


# ================= seq dung chung voi health (health khong gui seq) =================

def device_health(uptime_ms):
    return {"device_id": DEV, "free_heap_bytes": 150000, "uptime_ms": uptime_ms, "sensor_ok": True}


def _voyage_with(client, db, vid, seqs, health_at=(), events=(), boot="a1b2c3d4", step=5):
    client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": vid})
    for s in seqs:
        send(db, "telemetry", device_telemetry(s, boot=boot), T0 + timedelta(seconds=s * step))
    for s in events:
        send(db, "event", device_event(s, "CAUTION", boot=boot), T0 + timedelta(seconds=s * step))
    for t in health_at:                                                        # giay ke tu T0
        send(db, "health", device_health(int(t * 1000)), T0 + timedelta(seconds=t))
    return summary(client, vid)["data_quality"]


def test_health_between_neighbours_explains_gap_by_timing(client, db, registered):
    q = _voyage_with(client, db, "V-H1", [1, 2, 3, 5, 6], health_at=[22])      # seq 4 trong (15s..25s), health luc 22s
    assert q["receive_status"] == "NO_LOSS_EVIDENCE" and q["seq_gaps_health_timing"] == 1 and q["seq_gaps_unclassified"] == 0
    assert q["received_rate"] is None and q["received_rate_lower_bound"] == pytest.approx(5 / 6)


def test_health_outside_the_gap_window_explains_nothing(client, db, registered):
    q = _voyage_with(client, db, "V-H2", [1, 2, 3, 5, 6], health_at=[7, 28])   # 7s nam giua seq 1-2, 28s giua seq 5-6
    assert q["seq_gaps_health_timing"] == 0 and q["seq_gaps_unclassified"] == 1 and q["receive_status"] == "INSUFFICIENT_EVIDENCE"


def test_one_health_message_explains_at_most_one_seq(client, db, registered):
    q = _voyage_with(client, db, "V-H3", [1, 2, 5, 6], health_at=[17])         # 2 seq trong (3,4), chi 1 health
    assert q["seq_gaps_health_timing"] == 1 and q["seq_gaps_unclassified"] == 1


def test_events_and_health_interleaved_with_telemetry_are_all_accounted(client, db, registered):
    q = _voyage_with(client, db, "V-H4", [1, 2, 4, 5, 7, 8], health_at=[17], events=[6])   # 3 = health, 6 = event
    assert (q["seq_used_by_events"], q["seq_gaps_health_timing"], q["seq_gaps_unclassified"]) == (1, 1, 0)
    assert q["receive_status"] == "NO_LOSS_EVIDENCE"


def test_gaps_are_classified_per_boot(client, db, registered):
    client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-H5"})
    for s in (1, 2, 4):
        send(db, "telemetry", device_telemetry(s, boot="bootAAAA"), T0 + timedelta(seconds=s))
    for s in (1, 2, 4):                                                          # seq dem lai sau khoi dong
        send(db, "telemetry", device_telemetry(s, boot="bootBBBB"), T0 + timedelta(seconds=100 + s))
    send(db, "event", device_event(3, "CAUTION", boot="bootAAAA"), T0 + timedelta(seconds=3))   # chi boot A co event seq 3
    q = summary(client, "V-H5")["data_quality"]
    assert q["seq_used_by_events"] == 1 and q["seq_gaps_unclassified"] == 1 and q["receive_status"] == "INSUFFICIENT_EVIDENCE"


def test_late_telemetry_outside_the_voyage_is_verified_not_lost(client, db, registered):
    client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-H6"})
    for s in (1, 2, 4):
        send(db, "telemetry", device_telemetry(s), T0 + timedelta(seconds=s))
    client.post("/api/v1/voyages/V-H6/end")
    send(db, "telemetry", device_telemetry(3), T0 + timedelta(seconds=60))       # den tre sau khi ket thuc chuyen
    q = summary(client, "V-H6")["data_quality"]
    assert q["seq_telemetry_outside_voyage"] == 1 and q["receive_status"] == "VERIFIED"
    assert (q["expected_samples"], q["missing_samples"], q["received_rate"]) == (4, 0, 1.0)


def test_regression_v_2026_001_shared_seq_with_30s_health(client, db, registered):
    """Tai hien hinh dang chuyen V-2026-001: telemetry seq 472..544, 11 seq trong, moi seq trong co dung 1 health
    nhan giua hai telemetry ke ben (health ~30 s). Cong thuc cu bao 84,9% 'ty le nhan'; thuc te khong co bang chung mat goi."""
    gaps = [475, 481, 488, 495, 501, 508, 514, 521, 528, 534, 541]
    seqs = [s for s in range(472, 545) if s not in gaps]
    q = _voyage_with(client, db, "V-REG", seqs, health_at=[g * 5 for g in gaps], step=5)
    assert q["samples"] == 62 and q["seq_span"] == 73 and q["seq_gaps"] == 11
    assert q["seq_gaps_health_timing"] == 11 and q["seq_gaps_unclassified"] == 0 and q["receive_status"] == "NO_LOSS_EVIDENCE"
    assert q["received_rate"] is None and q["missing_samples"] is None
    assert q["received_rate_lower_bound"] == pytest.approx(62 / 73)            # 84,9% chi la can duoi


def test_events_of_other_boots_do_not_affect_the_count(client, db, registered):
    client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-SEQ3"})
    for i in (1, 2, 3):
        send(db, "telemetry", device_telemetry(i, boot="bootAAAA"), T0 + timedelta(seconds=i))
    send(db, "event", device_event(2, "CAUTION", boot="bootBBBB"), T0 + timedelta(seconds=2))   # boot khac, cung seq
    q = summary(client, "V-SEQ3")["data_quality"]
    assert q["expected_samples"] == 3 and q["seq_used_by_events"] == 0 and q["received_rate"] == 1.0


# ================= B1: ACK tu thiet bi =================

def test_ack_from_device_button_and_remote_are_recorded(db, registered):
    send(db, "event", device_event(1, "WARNING"), T0)
    send(db, "event", device_event(2, "WARNING", prev="WARNING", acked_by="device_button"), T0 + timedelta(seconds=20))
    a = db.scalar(select(Alarm))
    assert a.state.value == "ACKED" and a.acked_by == "device_button"
    assert (a.acked_at - a.opened_at).total_seconds() == 20                      # MTTA tu acked_by cua thiet bi
    send(db, "event", device_event(3, "WARNING", alarm_id="A-0002", prev="NORMAL"), T0 + timedelta(seconds=30))
    send(db, "event", device_event(4, "WARNING", alarm_id="A-0002", prev="WARNING", acked_by="remote"), T0 + timedelta(seconds=40))
    assert db.scalar(select(Alarm).where(Alarm.alarm_id == "A-0002")).acked_by == "remote"


def test_remote_ack_event_after_server_ack_does_not_change_who_acked(client, db, registered, auth):
    send(db, "event", device_event(1, "WARNING"), T0)
    pk = db.scalar(select(Alarm)).id
    assert client.post(f"/api/v1/alarms/{pk}/ack", headers=auth("op01")).status_code == 200
    send(db, "event", device_event(2, "WARNING", prev="WARNING", acked_by="remote"), T0 + timedelta(seconds=5))
    assert db.scalar(select(Alarm)).acked_by == "op01"                           # nguoi truc that, khong bi doi thanh 'remote'


def test_cleared_event_is_alarm_state_normal_with_same_alarm_id(db, registered):
    send(db, "event", device_event(1, "WARNING"), T0)
    send(db, "event", device_event(2, "NORMAL", prev="WARNING"), T0 + timedelta(seconds=30))
    assert db.scalar(select(Alarm)).state.value == "CLEARED"


def test_status_extras_from_device_are_accepted(db):
    p = {"state": "online", "fw": "1.0.0", "model_version": "stub", "feature_schema_version": "svmg-angle-23-v1",
         "preprocessing_version": "imu-cf-bw4-20to10-v1", "feature_count": 23, "config_version": 0, "boot_id": "a1b2c3d4"}
    assert send(db, "status", p, T0).outcome == Outcome.STORED
    assert db.scalar(select(Device)).fw == "1.0.0"


def test_health_extras_from_device_are_accepted(db):
    p = {"device_id": DEV, "feature_schema_version": "svmg-angle-23-v1", "preprocessing_version": "x", "feature_count": 23,
         "feature_valid_mask": 8388607, "data_status": 0, "feature_update_us_last": 900, "feature_update_us_max": 1500,
         "free_heap_bytes": 200000, "min_free_heap_bytes": 150000, "uptime_ms": 30000, "sensor_ok": True, "i2c_errors": 0,
         "inference_ms": 0.4, "mqtt_reconnects": 0, "buffer_used": 0, "buffer_capacity": 64}
    assert send(db, "health", p, T0).outcome == Outcome.STORED


# ================= ack cau hinh: cmd_id = "cfg-<ver>" (khong co ban ghi Command) =================

def _cfg_row(db, ver):
    from app.models import DeviceConfigVersion
    return db.scalar(select(DeviceConfigVersion).where(DeviceConfigVersion.config_version == ver))


class _Pub:
    def publish(self, topic, payload, qos=1, retain=False, on_delivered=None):
        if on_delivered:
            on_delivered()


@pytest.fixture()
def with_config(client, db, registered):
    from commands.publisher import set_publisher
    set_publisher(_Pub())
    r = client.put(f"/api/v1/devices/{DEV}/config", json={"profile": "SENSITIVE"})
    assert r.status_code == 201, r.text
    yield r.json()["config_version"]
    set_publisher(None)


def test_config_ack_applied_marks_version_applied(db, with_config):
    r = send(db, "cmd/ack", {"cmd_id": f"cfg-{with_config}", "result": "APPLIED", "config_version": with_config}, T0)
    assert r.outcome == Outcome.STORED
    assert _cfg_row(db, with_config).applied is True


def test_config_ack_rejected_keeps_version_unapplied_and_stores_reason(db, with_config):
    r = send(db, "cmd/ack", {"cmd_id": f"cfg-{with_config}", "result": "REJECTED", "reason": "crc mismatch"}, T0)
    assert r.outcome == Outcome.STORED
    row = _cfg_row(db, with_config)
    assert row.applied is False and row.rejected_reason == "crc mismatch"


def test_config_ack_is_idempotent_and_ignores_unknown_version(db, with_config):
    ack = {"cmd_id": f"cfg-{with_config}", "result": "APPLIED"}
    assert send(db, "cmd/ack", ack, T0).outcome == Outcome.STORED
    assert send(db, "cmd/ack", ack, T0).outcome == Outcome.DUPLICATE
    assert send(db, "cmd/ack", {"cmd_id": "cfg-999", "result": "APPLIED"}, T0).outcome == Outcome.IGNORED


def test_config_ack_exposed_in_api(client, db, with_config):
    send(db, "cmd/ack", {"cmd_id": f"cfg-{with_config}", "result": "REJECTED", "reason": "x"}, T0)
    rows = client.get(f"/api/v1/devices/{DEV}/config").json()
    assert rows[0]["applied"] is False and rows[0]["rejected_reason"] == "x"


# ================= CRC cau hinh khop vector vang cua M1 (tests/firmware/tools/crosscheck_crc.py) =================

CFG8 = {"config_version": 8, "profile": "SENSITIVE", "debounce_n": 2, "phi_hard_deg": 20, "mai_caution": 70,
        "report_interval_s": 5, "primary_model": "RF"}


def test_crc_matches_m1_golden_vectors():
    from commands.config_service import compute_crc
    assert compute_crc(CFG8) == "4fa6"
    assert compute_crc({**CFG8, "phi_hard_deg": 20.0}) == "0902"      # 20.0 va 20 khac chuoi -> khac CRC
    assert compute_crc({**CFG8, "crc": "ffff"}) == "4fa6"             # truong crc bi bo qua


def test_whole_floats_are_sent_as_integers_so_device_rebuilds_same_string():
    from commands.config_service import normalize_numbers
    assert json.dumps(normalize_numbers({"phi_hard_deg": 20.0, "x": 17.5, "ok": True, "n": 3})) == \
        '{"phi_hard_deg": 20, "x": 17.5, "ok": true, "n": 3}'


def test_published_config_has_no_trailing_point_zero_and_valid_crc(client, db, with_config):
    from commands.config_service import compute_crc
    r = client.put(f"/api/v1/devices/{DEV}/config", json={"phi_hard_deg": 20.0})
    assert r.status_code == 201, r.text
    p = r.json()["payload"]
    assert isinstance(p["phi_hard_deg"], int)
    assert p["crc"] == compute_crc(p)


@pytest.mark.xfail(strict=True, reason="contracts/examples/config_sample.json co crc 9c1e sai; dung la 4fa6 (can M1 sua hop dong)")
def test_contract_example_config_crc_is_correct():
    from commands.config_service import compute_crc
    ex = json.loads((Path(__file__).resolve().parents[2] / "contracts" / "examples" / "config_sample.json").read_text(encoding="utf-8"))
    assert compute_crc(ex) == ex["crc"]


# ================= WebSocket /ws/telemetry =================

def _wait_clients(n=1):
    import time
    from alarms.realtime import telemetry_hub
    for _ in range(200):
        if len(telemetry_hub.clients) >= n:
            return
        time.sleep(0.01)
    raise AssertionError("client WS chua dang ky")


def test_ws_telemetry_rejects_missing_or_bad_token(client):
    from starlette.websockets import WebSocketDisconnect
    for url in ("/ws/telemetry", "/ws/telemetry?token=garbage"):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(url):
                pass


def test_ws_telemetry_pushes_stored_samples_and_status(client, db, auth):
    token = auth("op01")["Authorization"].split()[1]
    with client.websocket_connect(f"/ws/telemetry?token={token}") as ws:
        _wait_clients()
        send(db, "telemetry", device_telemetry(1), T0)
        m = ws.receive_json()
        assert m["type"] == "telemetry" and m["device_id"] == DEV and m["seq"] == 1
        assert m["source_mode"] == "SIMULATION" and m["server_rx_time"].endswith("Z")
        send(db, "telemetry", device_telemetry(1), T0)            # trung -> khong phat lai
        send(db, "status", {"state": "online", "boot_id": "a1b2c3d4"}, T0)
        m = ws.receive_json()
        assert m == {"type": "device_status", "device_id": DEV, "state": "online", "last_seen": m["last_seen"]}


def test_ws_telemetry_device_filter(client, db, auth):
    token = auth("op01")["Authorization"].split()[1]
    with client.websocket_connect(f"/ws/telemetry?token={token}&device_id=other-dev") as ws:
        _wait_clients()
        send(db, "telemetry", device_telemetry(1), T0)            # thiet bi khac -> khong den client nay
        handle_message(db, "svmg/other-dev/telemetry",
                       json.dumps({**device_telemetry(1), "device_id": "other-dev"}).encode(), rx_time=T0)
        assert ws.receive_json()["device_id"] == "other-dev"


def test_status_and_health_store_device_reported_feature_schema(db):
    send(db, "status", {"state": "online", "feature_schema_version": "svmg-angle-23-v1",
                        "preprocessing_version": "p1", "feature_count": 23}, T0)
    d = db.scalar(select(Device))
    assert (d.feature_schema_version, d.preprocessing_version, d.feature_count) == ("svmg-angle-23-v1", "p1", 23)


# ================= POST /alarms/{id}/ack day ack_alarm xuong thiet bi (best-effort) =================

class _RecPub:
    def __init__(self):
        self.sent = []

    def publish(self, topic, payload, qos=1, retain=False, on_delivered=None):
        self.sent.append((topic, json.loads(payload)))
        if on_delivered:
            on_delivered()


@pytest.fixture()
def ack_alarm_in_contract(tmp_path, monkeypatch):
    """Hop dong GIA LAP trong tmp: ban sao schemas + them 'ack_alarm' vao enum (de thu hanh vi khi M1 chap nhan)."""
    import shutil
    from app.core.config import settings
    from ingest import validator
    src = Path(__file__).resolve().parents[2] / "contracts" / "schemas"
    dst = tmp_path / "schemas"
    shutil.copytree(src, dst)
    f = dst / "command.json"
    c = json.loads(f.read_text(encoding="utf-8"))
    c["properties"]["cmd"]["enum"].append("ack_alarm")
    f.write_text(json.dumps(c), encoding="utf-8")
    monkeypatch.setattr(settings, "contracts_dir", str(dst))
    validator._validator.cache_clear()
    yield
    monkeypatch.undo()
    validator._validator.cache_clear()


def _open_alarm(db):
    send(db, "telemetry", device_telemetry(1), T0)                   # thiet bi bao boot_id a1b2c3d4
    send(db, "event", device_event(2, "WARNING"), T0)
    return db.scalar(select(Alarm)).id


def test_ack_succeeds_even_when_contract_has_no_ack_alarm_command(client, db, auth):
    from commands.publisher import set_publisher
    pub = _RecPub()
    set_publisher(pub)
    try:
        pk = _open_alarm(db)
        r = client.post(f"/api/v1/alarms/{pk}/ack", headers=auth("op01"))
        assert r.status_code == 200 and r.json()["alarm"]["state"] == "ACKED"
        assert r.json()["device_ack"] == "unsupported" and pub.sent == []
    finally:
        set_publisher(None)


def test_ack_is_pushed_to_device_when_contract_allows_it(client, db, auth, ack_alarm_in_contract):
    from commands.publisher import set_publisher
    pub = _RecPub()
    set_publisher(pub)
    try:
        pk = _open_alarm(db)
        r = client.post(f"/api/v1/alarms/{pk}/ack", headers=auth("op01"))
        assert r.json()["device_ack"] == "sent"
        topic, msg = pub.sent[0]
        assert topic == f"svmg/{DEV}/cmd" and msg["cmd"] == "ack_alarm" and msg["params"] == {"alarm_id": "A-0001"}
        assert msg["issued_by"] == "op01"
        r2 = client.post(f"/api/v1/alarms/{pk}/ack", headers=auth("op01"))   # ACK lai: khong gui lan hai
        assert r2.json()["already_acked"] is True and r2.json()["device_ack"] == "not_applicable" and len(pub.sent) == 1
    finally:
        set_publisher(None)


def test_ack_not_pushed_when_device_rebooted_since_the_alarm(client, db, auth, ack_alarm_in_contract):
    from commands.publisher import set_publisher
    pub = _RecPub()
    set_publisher(pub)
    try:
        pk = _open_alarm(db)
        send(db, "telemetry", device_telemetry(1, boot="newboot1"), T0 + timedelta(seconds=5))
        r = client.post(f"/api/v1/alarms/{pk}/ack", headers=auth("op01"))
        assert r.status_code == 200 and r.json()["device_ack"] == "not_applicable" and pub.sent == []
    finally:
        set_publisher(None)


def test_ack_survives_publish_failure(client, db, auth, ack_alarm_in_contract):
    from commands.publisher import set_publisher
    set_publisher(None)                                              # chua co kenh MQTT
    pk = _open_alarm(db)
    r = client.post(f"/api/v1/alarms/{pk}/ack", headers=auth("op01"))
    assert r.status_code == 200 and r.json()["alarm"]["state"] == "ACKED" and r.json()["device_ack"] == "failed"
