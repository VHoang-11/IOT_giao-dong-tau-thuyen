import csv
import io
import json
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from conftest import NOAUTH
from sqlalchemy import select

from app.models import Alarm, Device, Telemetry, Voyage
from app.models.enums import AlarmLevel, CommandName, MotionClass, SourceMode
from commands import service as cmd_service
from commands.publisher import set_publisher
from ingest.service import handle_message
from replay.service import decode_cursor, encode_cursor
from reports.csvexport import TELEMETRY_COLUMNS

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
DEV = "vessel-demo-01"
VID = "V-REPLAY-1"
URL = f"/api/v1/voyages/{VID}/replay"


def tele(i, voyage=VID, dev=DEV, boot="b1", seq=None, t_sim=None, rx=None, roll=None, mode=SourceMode.SIMULATION,
         ok=True, warp=1, base=None):
    return Telemetry(
        device_id=dev, boot_id=boot, seq=i if seq is None else seq, t_sim_s=float(i) if t_sim is None else t_sim,
        uptime_ms=i * 1000, timewarp=warp, source_mode=mode, voyage_id=voyage,
        roll_deg=float(i) / 4 if roll is None else roll, pitch_deg=0.5, rms_roll_deg=1.5, heel_offset_deg=0.1,
        class_rf=MotionClass.NORMAL, class_baseline_b=base, alarm_level=AlarmLevel.NORMAL, mai=10,
        model_version="rf_v1", config_version=1, sensor_ok=ok, server_rx_time=rx or T0 + timedelta(seconds=i))


@pytest.fixture()
def voyage(db, client):
    db.add(Device(device_id=DEV))
    db.commit()
    assert client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": VID}).status_code == 201
    return db.scalar(select(Voyage).where(Voyage.voyage_id == VID))


def get(client, **params):
    r = client.get(URL, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def all_pages(client, limit, **params):
    """Di qua tat ca cac trang bang next_cursor. Tra ve danh sach cac trang."""
    pages, cursor = [], None
    for _ in range(500):
        p = dict(params, limit=limit)
        if cursor:
            p["cursor"] = cursor
        page = get(client, **p)
        pages.append(page)
        if not page["truncated"]:
            return pages
        cursor = page["next_cursor"]
    raise AssertionError("khong ket thuc phan trang")


def ident(t):
    return (t["boot_id"], t["seq"])


def event(db, seq, alarm_id, level, rx, dev=DEV):
    p = {"device_id": dev, "boot_id": "b1", "seq": seq, "type": "ALARM_STATE", "alarm_id": alarm_id,
         "level": level, "class": "HIGH_ROLL", "t_sim_s": float(seq)}
    handle_message(db, f"svmg/{dev}/event", json.dumps(p).encode(), rx_time=rx)


def telemetry_msg(db, seq, rx, voyage_id=VID, dev=DEV):
    p = {"device_id": dev, "boot_id": "b1", "seq": seq, "t_sim_s": float(seq), "uptime_ms": 1, "source_mode": "SIMULATION",
         "voyage_id": voyage_id, "roll_deg": 1.0, "pitch_deg": 0.0, "class_rf": "NORMAL", "alarm_level": "NORMAL",
         "model_version": "rf_v1", "config_version": 1, "sensor_ok": True}
    handle_message(db, f"svmg/{dev}/telemetry", json.dumps(p).encode(), rx_time=rx)


# ---------------------------------------------------------------- quyen va tham so

def test_requires_login_and_voyage_must_exist(client, voyage, auth):
    assert client.get(URL, headers=NOAUTH).status_code == 401
    assert client.get(URL, headers=auth("op01")).status_code == 200            # moi vai tro deu xem duoc
    assert client.get("/api/v1/voyages/V-NOPE/replay").status_code == 404
    assert client.get("/api/v1/voyages/bad%20id/replay").status_code == 422


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": 5001}, {"cursor": "!!!"}, {"cursor": "e30"},
    {"from_time": "2026-01-02T00:00:00Z", "to_time": "2026-01-01T00:00:00Z"},
    {"from_t_sim": 10, "to_t_sim": 5},
    {"from_time": "2026-01-01T00:00:00Z", "from_t_sim": 1},           # tron hai truc
    {"to_time": "2026-01-01T00:00:00Z", "to_t_sim": 1},
    {"from_t_sim": "nan"}, {"to_t_sim": "inf"}, {"from_time": "khong-phai-ngay"},
])
def test_invalid_parameters_rejected(client, voyage, params):
    assert client.get(URL, params=params).status_code == 422


def test_cursor_roundtrip_and_tamper_detection():
    c = encode_cursor(T0, 42)
    assert decode_cursor(c) == (T0, 42)
    import base64
    bad = base64.urlsafe_b64encode(json.dumps({"rx": "2026-01-01T12:00:00", "id": 1}).encode()).decode()  # thieu mui gio
    from replay.service import ReplayError
    for broken in (bad, "abc", base64.urlsafe_b64encode(b'{"rx":"2026-01-01T12:00:00+00:00","id":"x"}').decode()):
        with pytest.raises(ReplayError):
            decode_cursor(broken)


# ---------------------------------------------------------------- du lieu va thu tu

def test_basic_replay_fields_order_and_flags(client, db, voyage):
    db.add_all([tele(2, roll=3.0), tele(0, roll=1.0, mode=SourceMode.SENSOR, ok=False), tele(1, roll=2.0, base=MotionClass.HIGH_ROLL)])
    db.commit()
    r = get(client)
    t = r["telemetry"]
    assert [x["roll_deg"] for x in t] == [1.0, 2.0, 3.0]                     # tang dan theo thoi gian nhan
    assert t[0]["source_mode"] == "SENSOR" and t[0]["sensor_ok"] is False     # nhan nguon + loi cam bien luon di kem
    assert t[1]["class_baseline_b"] == "HIGH_ROLL" and t[2]["class_baseline_b"] is None
    for k in ("boot_id", "seq", "t_sim_s", "timewarp", "server_rx_time", "roll_deg", "pitch_deg", "rms_roll_deg",
              "mai", "class_rf", "alarm_level", "scenario_id"):
        assert k in t[0], k
    assert t[0]["server_rx_time"].endswith("Z") or "+00:00" in t[0]["server_rx_time"]    # co mui gio
    assert r["truncated"] is False and r["next_cursor"] is None and r["limit"] == 1000


def test_replay_values_equal_database_rows(client, db, voyage):
    db.add_all(tele(i, roll=(i % 9) - 4.25) for i in range(40))
    db.commit()
    got = get(client)["telemetry"]
    rows = list(db.scalars(select(Telemetry).order_by(Telemetry.server_rx_time, Telemetry.id)))
    assert len(got) == len(rows) == 40
    for g, row in zip(got, rows):
        assert (g["boot_id"], g["seq"], g["roll_deg"], g["pitch_deg"], g["class_rf"], g["mai"]) == (
            row.boot_id, row.seq, row.roll_deg, row.pitch_deg, row.class_rf.value, row.mai)


def test_only_this_voyage_and_device(client, db, voyage):
    db.add(Device(device_id="vessel-2"))
    db.add_all([tele(0), tele(1), tele(2, voyage="V-OTHER"), tele(3, dev="vessel-2"), tele(4, voyage=None)])
    db.commit()
    r = get(client)
    assert [t["seq"] for t in r["telemetry"]] == [0, 1] and r["meta"]["total_samples"] == 2


def test_empty_voyage_is_valid_response(client, voyage):
    r = get(client)
    assert r["telemetry"] == r["alarm_events"] == r["alarms"] == r["commands"] == []
    m = r["meta"]
    assert m["total_samples"] == 0 and m["first_sample_at"] is None and m["t_sim_monotonic"] is None
    assert m["duration_wall_s"] is None and m["boots"] == 0 and m["source_modes"] == [] and m["timewarps"] == []


# ---------------------------------------------------------------- phan trang: khong mat, khong lap

def test_pagination_concatenates_to_exactly_the_csv_export(client, db, voyage):
    db.add_all(tele(i, roll=float(i) / 7) for i in range(53))
    db.commit()
    pages = all_pages(client, limit=10)
    assert [len(p["telemetry"]) for p in pages] == [10, 10, 10, 10, 10, 3]
    assert [p["truncated"] for p in pages] == [True] * 5 + [False] and pages[-1]["next_cursor"] is None
    replayed = [ident(t) for p in pages for t in p["telemetry"]]
    assert len(set(replayed)) == 53                                          # khong lap
    body = client.get(f"/api/v1/voyages/{VID}/telemetry.csv").content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(body)))[1:]
    exported = [(r[TELEMETRY_COLUMNS.index("boot_id")], int(r[TELEMETRY_COLUMNS.index("seq")])) for r in rows]
    assert replayed == exported                                              # T15: khop file goc, dung thu tu


def test_pagination_with_identical_timestamps_across_page_boundary(client, db, voyage):
    db.add_all(tele(i, rx=T0) for i in range(30))                            # 30 mau CUNG server_rx_time
    db.commit()
    pages = all_pages(client, limit=7)
    ids = [t["seq"] for p in pages for t in p["telemetry"]]
    assert sorted(ids) == list(range(30)) and len(ids) == 30                 # khong mat, khong lap


@pytest.mark.parametrize("limit", [1, 2, 3, 5, 11, 50, 5000])
def test_pagination_is_correct_for_many_limits(client, db, voyage, limit):
    db.add_all(tele(i) for i in range(20))
    db.commit()
    seqs = [t["seq"] for p in all_pages(client, limit) for t in p["telemetry"]]
    assert seqs == list(range(20))


# ---------------------------------------------------------------- loc theo thoi gian

def test_time_window_filter_is_inclusive_and_naive_means_utc(client, db, voyage):
    db.add_all(tele(i) for i in range(10))
    db.commit()
    lo, hi = (T0 + timedelta(seconds=3)).isoformat(), (T0 + timedelta(seconds=6)).isoformat()
    r = get(client, from_time=lo, to_time=hi)
    assert [t["seq"] for t in r["telemetry"]] == [3, 4, 5, 6]
    assert r["meta"]["window_samples"] == 4 and r["meta"]["total_samples"] == 10   # window != toan chuyen
    naive = get(client, from_time="2026-01-01T12:00:03", to_time="2026-01-01T12:00:06")
    assert [t["seq"] for t in naive["telemetry"]] == [3, 4, 5, 6]                  # thieu mui gio -> UTC
    assert get(client, from_time=(T0 + timedelta(seconds=7)).isoformat())["telemetry"][0]["seq"] == 7
    assert get(client, to_time=(T0 + timedelta(seconds=1)).isoformat())["telemetry"][-1]["seq"] == 1


def test_t_sim_window_filter(client, db, voyage):
    db.add_all(tele(i, t_sim=i * 10.0) for i in range(10))
    db.commit()
    r = get(client, from_t_sim=25, to_t_sim=60)
    assert [t["seq"] for t in r["telemetry"]] == [3, 4, 5, 6]
    assert get(client, from_t_sim=1000)["telemetry"] == []
    assert get(client, from_t_sim=1000)["meta"]["total_samples"] == 10             # meta van day du


def test_empty_window_returns_empty_data_but_full_meta(client, db, voyage):
    db.add_all(tele(i) for i in range(5))
    db.commit()
    r = get(client, from_time=(T0 + timedelta(days=1)).isoformat())
    assert r["telemetry"] == [] and r["meta"]["total_samples"] == 5 and r["meta"]["window_samples"] == 0


# ---------------------------------------------------------------- canh bao / su kien / lenh

@pytest.fixture()
def busy_voyage(client, db, voyage):
    """30 mau (moi giay) + cac su kien canh bao + lenh, co ca moc trung dung ranh gioi trang."""
    set_publisher(type("P", (), {"publish": lambda self, *a, on_delivered=None, **k: on_delivered and on_delivered()})())
    for i in range(30):
        telemetry_msg(db, i, T0 + timedelta(seconds=i))
    event(db, 100, "A-1", "CAUTION", T0 + timedelta(seconds=2))
    event(db, 101, "A-1", "WARNING", T0 + timedelta(seconds=9))     # dung moc cuoi trang 1 (limit 10 -> mau seq 9)
    event(db, 102, "A-1", "NORMAL", T0 + timedelta(seconds=25))
    event(db, 103, "A-2", "CRITICAL", T0 + timedelta(seconds=10))   # dung moc dau trang 2
    event(db, 104, "A-2", "NORMAL", T0 + timedelta(seconds=10))     # cung moc voi event truoc
    event(db, 105, "A-X", "WARNING", T0 + timedelta(seconds=5))     # canh bao cua CHUYEN KHAC (se doi voyage ben duoi)
    cmd_service.create_command(db, DEV, CommandName.calibrate_zero, {}, 60, "sup01", cmd_id="c-1", now=T0 + timedelta(seconds=9))
    cmd_service.create_command(db, DEV, CommandName.calibrate_zero, {}, 60, "sup01", cmd_id="c-2", now=T0 + timedelta(seconds=10))
    cmd_service.create_command(db, DEV, CommandName.calibrate_zero, {}, 60, "sup01", cmd_id="c-3", now=T0 + timedelta(seconds=28))
    other = db.scalar(select(Alarm).where(Alarm.alarm_id == "A-X"))
    other.voyage_id = "V-OTHER"
    db.commit()
    yield
    set_publisher(None)


def test_every_event_and_command_appears_exactly_once_across_pages(client, busy_voyage):
    pages = all_pages(client, limit=10)
    assert len(pages) == 3
    events = [(e["alarm_id"], e["seq"]) for p in pages for e in p["alarm_events"]]
    assert sorted(events) == sorted([("A-1", 100), ("A-1", 101), ("A-1", 102), ("A-2", 103), ("A-2", 104)])
    assert len(events) == len(set(events))                                   # khong lap du qua ranh gioi trang
    cmds = [c["cmd_id"] for p in pages for c in p["commands"]]
    assert sorted(cmds) == ["c-1", "c-2", "c-3"] and len(cmds) == 3
    assert all("A-X" != e[0] for e in events)                                # su kien cua chuyen khac khong lan vao


def test_events_come_in_ascending_time_order_within_and_across_pages(client, busy_voyage):
    pages = all_pages(client, limit=10)
    times = [e["server_rx_time"] for p in pages for e in p["alarm_events"]]
    assert times == sorted(times)


def test_no_pagination_returns_everything_at_once(client, busy_voyage):
    r = get(client)
    assert len(r["telemetry"]) == 30 and len(r["alarm_events"]) == 5 and len(r["commands"]) == 3
    ids = {a["alarm_id"]: a for a in r["alarms"]}
    assert set(ids) == {"A-1", "A-2"} and ids["A-1"]["state"] == "CLEARED" and ids["A-1"]["max_level"] == "WARNING"
    assert ids["A-1"]["source_mode"] == "SIMULATION" and ids["A-1"]["opened_at"].endswith(("Z", "+00:00"))


def test_alarm_active_across_pages_is_present_on_each_page(client, busy_voyage):
    """A-1 mo luc +2s va dong luc +25s: phai co mat o ca 3 trang de giao dien ve duoc khoang hoat dong."""
    pages = all_pages(client, limit=10)
    for p in pages:
        assert "A-1" in {a["alarm_id"] for a in p["alarms"]}
    assert "A-2" not in {a["alarm_id"] for a in pages[2]["alarms"]}           # A-2 da giai toa luc +10s


def test_labels_appear_in_replay_for_review(client, db, busy_voyage):
    a = db.scalar(select(Alarm).where(Alarm.alarm_id == "A-1"))
    assert client.put(f"/api/v1/alarms/{a.id}/label", json={"label": "FALSE_ALARM"}).status_code == 200
    got = {x["alarm_id"]: x for x in get(client)["alarms"]}
    assert got["A-1"]["label"] == "FALSE_ALARM" and got["A-1"]["labeled_by"] == "sup01" and got["A-2"]["label"] is None


def test_event_window_for_time_axis_uses_requested_bounds(client, busy_voyage):
    r = get(client, from_time=(T0 + timedelta(seconds=9)).isoformat(), to_time=(T0 + timedelta(seconds=10)).isoformat())
    assert sorted(e["seq"] for e in r["alarm_events"]) == [101, 103, 104]
    assert sorted(c["cmd_id"] for c in r["commands"]) == ["c-1", "c-2"]


def test_t_sim_axis_scopes_events_to_returned_samples(client, busy_voyage):
    r = get(client, from_t_sim=8, to_t_sim=11)                               # mau seq 8..11 (t_sim = seq)
    assert sorted(e["seq"] for e in r["alarm_events"]) == [101, 103, 104]
    assert get(client, from_t_sim=900)["alarm_events"] == []                  # cua so rong -> khong keo ca chuyen vao


# ---------------------------------------------------------------- meta

def test_meta_numbers(client, db, voyage):
    db.add_all([tele(0, warp=1), tele(1, warp=10, mode=SourceMode.SENSOR), tele(2, boot="b2", seq=0, t_sim=2.0, warp=10)])
    db.commit()
    m = get(client)["meta"]
    assert (m["voyage_id"], m["device_id"], m["status"]) == (VID, DEV, "ACTIVE")
    assert m["total_samples"] == 3 and m["boots"] == 2 and m["source_modes"] == ["SENSOR", "SIMULATION"]
    assert m["timewarps"] == [1, 10] and m["duration_wall_s"] == 2.0
    assert m["t_sim_min_s"] == 0.0 and m["t_sim_max_s"] == 2.0 and m["t_sim_monotonic"] is True


def test_meta_flags_t_sim_that_restarts_after_reboot(client, db, voyage):
    """Dung truong hop hop dong chua noi ro: t_sim_s dem lai sau khi khoi dong lai -> khong duoc tin lam truc thoi gian."""
    db.add_all([tele(0, t_sim=100.0), tele(1, t_sim=110.0), tele(2, boot="b2", seq=0, t_sim=0.0), tele(3, boot="b2", seq=1, t_sim=10.0)])
    db.commit()
    r = get(client)
    assert r["meta"]["t_sim_monotonic"] is False and r["meta"]["boots"] == 2
    assert [ident(t) for t in r["telemetry"]] == [("b1", 0), ("b1", 1), ("b2", 0), ("b2", 1)]   # thu tu van dung theo gio nhan


def test_meta_status_changes_when_voyage_ends(client, db, voyage):
    assert get(client)["meta"]["status"] == "ACTIVE"
    client.post(f"/api/v1/voyages/{VID}/end")
    assert get(client)["meta"]["status"] == "ENDED"


# ---------------------------------------------------------------- hieu nang / ha tang

def test_replay_runs_off_the_event_loop(client, db, voyage, monkeypatch):
    import app.routers.replay as mod
    from alarms.realtime import hub
    import asyncio
    seen = {}
    real = mod.build_replay

    def spy(*a, **k):
        seen["thread"] = threading.current_thread().name
        return real(*a, **k)

    monkeypatch.setattr(mod, "build_replay", spy)

    async def name():
        return threading.current_thread().name

    assert client.get(URL).status_code == 200
    assert seen["thread"] != asyncio.run_coroutine_threadsafe(name(), hub.loop).result(timeout=5)


def test_large_voyage_pages_quickly_and_completely(client, db, voyage):
    db.bulk_save_objects([tele(i) for i in range(6000)])
    db.commit()
    t = time.perf_counter()
    pages = all_pages(client, limit=1000)
    assert len(pages) == 6 and sum(len(p["telemetry"]) for p in pages) == 6000
    assert time.perf_counter() - t < 20
