import csv
import hashlib
import io
import json
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from conftest import NOAUTH
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import AuditLog, Device, Telemetry, Voyage
from app.models.enums import AlarmLevel, CommandName, MotionClass, SourceMode, VoyageStatus
from app.services import voyages as vsvc
from commands import service as cmd_service
from commands.publisher import set_publisher
from ingest.service import handle_message
from reports import metrics
from reports.csvexport import TELEMETRY_COLUMNS

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
DEV = "vessel-demo-01"
VID = "V-TEST-001"


# ---------------------------------------------------------------- helpers

def tele(i, voyage=VID, dev=DEV, boot="b1", seq=None, roll=1.0, pitch=0.5, rms=2.0, heel=0.1, cls=MotionClass.NORMAL,
         base=None, ok=True, mode=SourceMode.SIMULATION, rx=None, level=AlarmLevel.NORMAL, scenario=None):
    return Telemetry(
        device_id=dev, boot_id=boot, seq=i if seq is None else seq, t_sim_s=float(i), uptime_ms=i * 1000,
        source_mode=mode, scenario_id=scenario, voyage_id=voyage, roll_deg=roll, pitch_deg=pitch,
        rms_roll_deg=rms, heel_offset_deg=heel, class_rf=cls, class_baseline_b=base, alarm_level=level,
        model_version="rf_v1", config_version=1, sensor_ok=ok,
        server_rx_time=rx or T0 + timedelta(seconds=i))


@pytest.fixture()
def device(db):
    db.add(Device(device_id=DEV, source_mode=SourceMode.SIMULATION))
    db.commit()


@pytest.fixture()
def voyage(db, device, client):
    r = client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": VID})
    assert r.status_code == 201
    return db.scalar(select(Voyage).where(Voyage.voyage_id == VID))


def end(client, vid=VID):
    return client.post(f"/api/v1/voyages/{vid}/end")


def summary(client, vid=VID):
    r = client.get(f"/api/v1/voyages/{vid}/summary")
    assert r.status_code == 200, r.text
    return r.json()


def audits(db, action):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)))


class FakePublisher:
    def publish(self, topic, payload, qos=1, retain=False, on_delivered=None):
        if on_delivered:
            on_delivered()


# ---------------------------------------------------------------- vong doi chuyen di

def test_start_end_voyage_lifecycle_and_audit(client, db, device):
    r = client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": VID})
    assert r.status_code == 201
    v = r.json()
    assert v["status"] == "ACTIVE" and v["started_by"] == "sup01" and v["source_mode"] == "SIMULATION"
    assert audits(db, "VOYAGE_START")[0].actor == "sup01"
    e = end(client)
    assert e.status_code == 200 and e.json()["status"] == "ENDED" and e.json()["ended_by"] == "sup01"
    assert e.json()["ended_at"]
    assert audits(db, "VOYAGE_END")[0].target == VID
    assert end(client).status_code == 409                    # da ket thuc
    assert end(client, "V-NOPE").status_code == 404


def test_generated_voyage_ids_follow_year_counter(client, db, device):
    year = datetime.now(timezone.utc).year
    a = client.post("/api/v1/voyages", json={"device_id": DEV}).json()
    assert a["voyage_id"] == f"V-{year}-001"
    end(client, a["voyage_id"])
    b = client.post("/api/v1/voyages", json={"device_id": DEV}).json()
    assert b["voyage_id"] == f"V-{year}-002"


def test_one_active_voyage_per_device(client, db, device):
    assert client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-A"}).status_code == 201
    r = client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-B"})
    assert r.status_code == 409 and "V-A" in r.json()["detail"]
    db.add(Device(device_id="vessel-2"))
    db.commit()
    assert client.post("/api/v1/voyages", json={"device_id": "vessel-2", "voyage_id": "V-C"}).status_code == 201
    end(client, "V-A")
    assert client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-B"}).status_code == 201


def test_database_itself_blocks_two_active_voyages(db, device):
    """Chi muc duy nhat co dieu kien o CSDL: ngay ca khi code kiem tra bi bo qua."""
    db.add(Voyage(voyage_id="V-1", device_id=DEV, source_mode=SourceMode.SIMULATION, started_by="x"))
    db.commit()
    db.add(Voyage(voyage_id="V-2", device_id=DEV, source_mode=SourceMode.SIMULATION, started_by="x"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(Voyage(voyage_id="V-3", device_id=DEV, source_mode=SourceMode.SIMULATION, started_by="x",
                  status=VoyageStatus.ENDED))                 # chuyen DA KET THUC thi khong bi chan
    db.commit()


def test_concurrent_start_race_returns_409_not_500(client, db, device, monkeypatch):
    client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-A"})
    monkeypatch.setattr(vsvc, "_active_voyage", lambda db_, dev_: None)  # request kia chua thay chuyen V-A
    r = client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-B"})
    assert r.status_code == 409 and "thử lại" in r.json()["detail"]
    assert db.scalar(select(Voyage).where(Voyage.voyage_id == "V-B")) is None


def test_voyage_validation_and_errors(client, db, device):
    post = lambda body: client.post("/api/v1/voyages", json=body)  # noqa: E731
    assert post({"device_id": "ghost"}).status_code == 404
    assert post({"device_id": DEV, "voyage_id": "bad id!"}).status_code == 422
    assert post({"device_id": DEV, "voyage_id": "x" * 65}).status_code == 422
    assert post({"device_id": DEV, "extra": 1}).status_code == 422
    assert post({}).status_code == 422
    assert post({"device_id": DEV, "voyage_id": VID}).status_code == 201
    end(client)
    assert post({"device_id": DEV, "voyage_id": VID}).status_code == 409       # trung ma chuyen
    assert client.get("/api/v1/voyages/bad%20id").status_code == 422
    assert client.get("/api/v1/voyages/V-NOPE").status_code == 404


def test_voyage_permissions(client, db, device, auth):
    op, admin = auth("op01"), auth("admin01")
    assert client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": VID}, headers=op).status_code == 403
    assert client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": VID}, headers=NOAUTH).status_code == 401
    assert client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": VID}, headers=admin).status_code == 201
    assert client.post(f"/api/v1/voyages/{VID}/end", headers=op).status_code == 403
    # xem thi Operator duoc
    for path in ("", f"/{VID}", f"/{VID}/summary", f"/{VID}/telemetry.csv", f"/{VID}/alarms.csv", f"/{VID}/report.pdf"):
        assert client.get(f"/api/v1/voyages{path}", headers=op).status_code == 200, path
        assert client.get(f"/api/v1/voyages{path}", headers=NOAUTH).status_code == 401, path


def test_list_voyages_filters(client, db, device):
    db.add(Device(device_id="vessel-2"))
    db.commit()
    client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-A"})
    end(client, "V-A")
    client.post("/api/v1/voyages", json={"device_id": DEV, "voyage_id": "V-B"})
    client.post("/api/v1/voyages", json={"device_id": "vessel-2", "voyage_id": "V-C"})
    ids = lambda q: sorted(v["voyage_id"] for v in client.get(f"/api/v1/voyages?{q}").json())  # noqa: E731
    assert ids("") == ["V-A", "V-B", "V-C"]
    assert ids("status=ACTIVE") == ["V-B", "V-C"] and ids("status=ENDED") == ["V-A"]
    assert ids(f"device_id={DEV}") == ["V-A", "V-B"]
    assert client.get("/api/v1/voyages?status=NOPE").status_code == 422


# ---------------------------------------------------------------- so lieu bao cao (kiem tra tung con so)

def test_summary_numbers_are_exact(client, db, voyage):
    rolls = [1, -2, 3, -4, 5, -6, 7, -8, 9, -10]
    rows = []
    for i, r in enumerate(rolls):
        rows.append(tele(i, roll=float(r), pitch=-float(i) / 2, heel=-float(i) / 10, rms=2.0,
                         cls=MotionClass.NORMAL if i < 6 else MotionClass.HIGH_ROLL,
                         base=MotionClass.NORMAL if i < 8 else None))
    rows.append(tele(10, roll=99.0, pitch=99.0, heel=99.0, rms=50.0, ok=False, cls=MotionClass.FAULT))  # loi cam bien
    db.add_all(rows)
    db.commit()
    s = summary(client)
    m, q = s["motion"], s["data_quality"]
    assert q["samples"] == 11 and q["sensor_fault_samples"] == 1 and m["samples_used"] == 10
    assert m["max_abs_roll_deg"] == 10 and m["p95_abs_roll_deg"] == 10      # nearest-rank: ceil(.95*10)=10 -> |roll| lon nhat
    assert m["mean_rms_roll_deg"] == 2.0                                     # rms=50 cua mau loi bi loai
    assert m["max_abs_pitch_deg"] == 4.5 and m["max_abs_heel_offset_deg"] == pytest.approx(0.9)
    assert s["class_rf"]["counts"] == {"FAULT": 1, "HIGH_ROLL": 4, "NORMAL": 6}
    assert s["class_rf"]["share"]["NORMAL"] == pytest.approx(6 / 11)
    assert s["class_baseline_b"]["counts"] == {"NORMAL": 8}
    assert s["rf_baseline_agreement_rate"] == pytest.approx(6 / 8)           # 8 mau co ca hai; RF==B o 6 mau dau
    assert q["expected_samples"] == 11 and q["received_rate"] == 1.0
    assert s["telemetry_rows"] == 11 and s["duration_s"] == 10.0
    assert "sensor_ok=false" in " ".join(s["notes"])


def test_p95_uses_nearest_rank_on_larger_sample(client, db, voyage):
    db.add_all(tele(i, roll=float(i + 1)) for i in range(100))               # |roll| = 1..100
    db.commit()
    assert summary(client)["motion"]["p95_abs_roll_deg"] == 95               # ceil(.95*100)=95 -> phan tu thu 95


def test_received_rate_is_computed_per_boot_and_counts_gaps(client, db, voyage):
    a = [tele(i, boot="bootA", seq=s) for i, s in enumerate([0, 1, 2, 5, 6])]            # thieu seq 3,4
    b = [tele(10 + i, boot="bootB", seq=s) for i, s in enumerate([0, 1, 2])]             # seq dem lai sau khoi dong
    db.add_all(a + b)
    db.commit()
    q = summary(client)["data_quality"]
    assert (q["samples"], q["expected_samples"], q["missing_samples"], q["boots"]) == (8, 10, 2, 2)
    assert q["received_rate"] == pytest.approx(0.8)
    notes = " ".join(summary(client)["notes"])
    assert "Thiếu 2" in notes and "khởi động lại 1 lần" in notes


@pytest.mark.parametrize("modes,label", [
    ([SourceMode.SIMULATION], "SIMULATION"), ([SourceMode.SENSOR], "SENSOR"),
    ([SourceMode.SIMULATION, SourceMode.SENSOR], "MIXED"), ([], "UNKNOWN")])
def test_source_label(client, db, voyage, modes, label):
    db.add_all(tele(i, mode=m) for i, m in enumerate(modes))
    db.commit()
    s = summary(client)
    assert s["source_label"] == label
    if label == "MIXED":
        assert "trộn SENSOR và SIMULATION" in " ".join(s["notes"])


def test_provisional_flag_follows_voyage_status(client, db, voyage):
    db.add(tele(0))
    db.commit()
    s = summary(client)
    assert s["provisional"] is True and "TẠM THỜI" in " ".join(s["notes"])
    end(client)
    s = summary(client)
    assert s["provisional"] is False and "TẠM THỜI" not in " ".join(s["notes"])


def test_voyage_with_no_telemetry_is_reported_honestly(client, db, voyage):
    s = summary(client)
    assert s["telemetry_rows"] == 0 and s["source_label"] == "UNKNOWN" and s["duration_s"] is None
    assert s["data_quality"]["received_rate"] is None and s["motion"]["max_abs_roll_deg"] is None
    assert s["false_alarms_per_hour"] is None and s["alarms"]["total"] == 0
    assert "Chưa có telemetry nào mang voyage_id này" in " ".join(s["notes"])
    csv_body = client.get(f"/api/v1/voyages/{VID}/telemetry.csv").content.decode("utf-8-sig")
    assert len(csv_body.strip().splitlines()) == 1                           # chi co dong tieu de
    assert client.get(f"/api/v1/voyages/{VID}/report.pdf").content.startswith(b"%PDF")


def test_only_this_voyage_and_device_are_counted(client, db, voyage):
    db.add(Device(device_id="vessel-2"))
    db.add_all([tele(0), tele(1), tele(2, voyage="V-OTHER"), tele(3, dev="vessel-2"), tele(4, voyage=None)])
    db.commit()
    assert summary(client)["telemetry_rows"] == 2


def test_false_alarms_per_hour_is_none_when_nothing_was_labeled(client, db, voyage):
    """'0 canh bao sai/gio' khi chua ai danh gia se la ket luan chua co can cu -> phai la None."""
    db.add_all([tele(0), tele(1, rx=T0 + timedelta(hours=1))])
    db.commit()
    p = {"device_id": DEV, "boot_id": "b1", "seq": 50, "type": "ALARM_STATE", "alarm_id": "A-1", "level": "WARNING",
         "class": "HIGH_ROLL", "t_sim_s": 1.0}
    handle_message(db, f"svmg/{DEV}/event", json.dumps(p).encode(), rx_time=T0)
    s = summary(client)
    assert s["duration_s"] == 3600 and s["alarms"]["total"] == 1 and s["alarms"]["labeled"] == 0
    assert s["false_alarms_per_hour"] is None


def test_alarms_commands_and_false_alarm_rate_per_hour(client, db, voyage, auth):
    set_publisher(FakePublisher())
    try:
        def tele_msg(seq, rx, voyage_id):
            p = {"device_id": DEV, "boot_id": "b1", "seq": seq, "t_sim_s": 1.0, "uptime_ms": 1, "source_mode": "SIMULATION",
                 "voyage_id": voyage_id, "roll_deg": 1.0, "pitch_deg": 0.0, "class_rf": "NORMAL", "alarm_level": "NORMAL",
                 "model_version": "rf_v1", "config_version": 1, "sensor_ok": True}
            handle_message(db, f"svmg/{DEV}/telemetry", json.dumps(p).encode(), rx_time=rx)

        def event(seq, alarm_id, level="WARNING"):
            p = {"device_id": DEV, "boot_id": "b1", "seq": seq, "type": "ALARM_STATE", "alarm_id": alarm_id,
                 "level": level, "class": "HIGH_ROLL", "t_sim_s": 1.0}
            handle_message(db, f"svmg/{DEV}/event", json.dumps(p).encode(), rx_time=T0)

        tele_msg(1, T0, VID)
        event(2, "A-1")                                    # canh bao thuoc chuyen VID
        event(3, "A-2", "CRITICAL")
        tele_msg(4, T0 + timedelta(seconds=3600), VID)     # 1 gio du lieu
        tele_msg(5, T0 + timedelta(seconds=3601), "V-OTHER")
        event(6, "A-3")                                    # canh bao thuoc chuyen khac -> khong tinh
        a1 = client.get("/api/v1/alarms").json()
        ids = {a["alarm_id"]: a["id"] for a in a1}
        client.put(f"/api/v1/alarms/{ids['A-1']}/label", json={"label": "FALSE_ALARM"})
        client.put(f"/api/v1/alarms/{ids['A-2']}/label", json={"label": "TRUE_ALARM"})
        cmd_service.create_command(db, DEV, CommandName.calibrate_zero, {}, 30, "sup01", now=T0 + timedelta(seconds=60))
        cmd_service.create_command(db, DEV, CommandName.calibrate_zero, {}, 30, "sup01", now=T0 + timedelta(hours=5))
        s = summary(client)
        assert s["duration_s"] == 3600
        assert s["alarms"]["total"] == 2 and s["alarms"]["by_max_level"] == {"WARNING": 1, "CRITICAL": 1}
        assert s["alarms"]["by_label"] == {"FALSE_ALARM": 1, "TRUE_ALARM": 1}
        assert s["alarms"]["false_alarm_rate"] == 0.5
        assert s["false_alarms_per_hour"] == pytest.approx(1.0)       # 1 canh bao sai / 1 gio
        assert s["commands"]["total"] == 1                             # lenh luc +5h nam ngoai khoang co du lieu
    finally:
        set_publisher(None)


# ---------------------------------------------------------------- CSV

def parse_csv(content: bytes):
    return list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))


def test_telemetry_csv_format_order_and_headers(client, db, voyage):
    db.add_all([tele(2, roll=3.0), tele(0, roll=1.0), tele(1, roll=2.0)])
    db.commit()
    r = client.get(f"/api/v1/voyages/{VID}/telemetry.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"] == f'attachment; filename="{VID}-telemetry.csv"'
    assert r.headers["cache-control"] == "no-store"
    assert r.content.startswith(b"\xef\xbb\xbf")                     # BOM de Excel doc dung UTF-8
    rows = parse_csv(r.content)
    assert rows[0] == TELEMETRY_COLUMNS
    assert [row[TELEMETRY_COLUMNS.index("roll_deg")] for row in rows[1:]] == ["1.0", "2.0", "3.0"]  # theo thoi gian nhan
    row = dict(zip(TELEMETRY_COLUMNS, rows[1]))
    assert row["source_mode"] == "SIMULATION" and row["voyage_id"] == VID and row["sensor_ok"] == "true"
    assert row["server_rx_time"].endswith("Z") and row["class_baseline_b"] == ""


def test_csv_neutralises_formula_injection(client, db, voyage):
    db.add(tele(0, scenario="=cmd|' /C calc'!A0"))
    db.add(tele(1, scenario="@SUM(1+1)"))
    db.add(tele(2, scenario="S3"))
    db.commit()
    rows = parse_csv(client.get(f"/api/v1/voyages/{VID}/telemetry.csv").content)
    col = [r[TELEMETRY_COLUMNS.index("scenario_id")] for r in rows[1:]]
    assert col == ["'=cmd|' /C calc'!A0", "'@SUM(1+1)", "S3"]


def test_summary_hash_matches_downloaded_csv_byte_for_byte(client, db, voyage):
    db.add_all(tele(i, roll=float(i) / 3, scenario="S3" if i % 2 else None) for i in range(25))
    db.commit()
    s = summary(client)
    body = client.get(f"/api/v1/voyages/{VID}/telemetry.csv").content
    assert hashlib.sha256(body).hexdigest() == s["telemetry_csv_sha256"]
    assert s["telemetry_rows"] == 25
    db.add(tele(99))
    db.commit()
    assert summary(client)["telemetry_csv_sha256"] != s["telemetry_csv_sha256"]   # du lieu doi -> dau van tay doi


def test_alarms_csv(client, db, voyage):
    p = {"device_id": DEV, "boot_id": "b1", "seq": 1, "t_sim_s": 1.0, "uptime_ms": 1, "source_mode": "SIMULATION",
         "voyage_id": VID, "roll_deg": 1.0, "pitch_deg": 0.0, "class_rf": "NORMAL", "alarm_level": "NORMAL",
         "model_version": "rf_v1", "config_version": 1, "sensor_ok": True}
    handle_message(db, f"svmg/{DEV}/telemetry", json.dumps(p).encode())
    e = {"device_id": DEV, "boot_id": "b1", "seq": 2, "type": "ALARM_STATE", "alarm_id": "A-1", "level": "WARNING",
         "class": "HIGH_ROLL", "t_sim_s": 1.0}
    handle_message(db, f"svmg/{DEV}/event", json.dumps(e).encode())
    r = client.get(f"/api/v1/voyages/{VID}/alarms.csv")
    assert r.headers["content-disposition"] == f'attachment; filename="{VID}-alarms.csv"'
    rows = parse_csv(r.content)
    assert rows[0][:3] == ["id", "alarm_id", "device_id"] and len(rows) == 2
    row = dict(zip(rows[0], rows[1]))
    assert row["alarm_id"] == "A-1" and row["voyage_id"] == VID and row["source_mode"] == "SIMULATION"


def test_exports_for_unknown_voyage_are_404(client):
    for path in ("summary", "telemetry.csv", "alarms.csv", "report.pdf"):
        assert client.get(f"/api/v1/voyages/V-NOPE/{path}").status_code == 404


# ---------------------------------------------------------------- PDF

def test_vietnamese_glyphs_exist_in_bundled_fonts():
    from reportlab.pdfbase.ttfonts import TTFont
    from reports.pdf import FONT_DIR
    viet = "aàáảãạăằắẳẵặâầấẩẫậeèéẻẽẹêềếểễệiìíỉĩịoòóỏõọôồốổỗộơờớởỡợuùúủũụưừứửữựyỳýỷỹỵđ°±≤≥"
    chars = set(viet + viet.upper())
    for name in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
        f = TTFont("t_" + name, str(FONT_DIR / name))
        assert [c for c in sorted(chars) if ord(c) not in f.face.charToGlyph] == []
    assert (FONT_DIR / "LICENSE_DEJAVU").exists()   # giay phep font phai di kem


def test_pdf_has_vietnamese_text_banner_and_fingerprint(client, db, voyage):
    plumber = pytest.importorskip("pdfplumber")
    db.add_all(tele(i, roll=float(i % 7) - 3, cls=MotionClass.HIGH_ROLL if i % 5 == 0 else MotionClass.NORMAL)
               for i in range(60))
    db.commit()
    r = client.get(f"/api/v1/voyages/{VID}/report.pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"] == f'attachment; filename="{VID}-report.pdf"'
    assert r.content.startswith(b"%PDF") and b"DejaVu" in r.content        # font da duoc nhung
    with plumber.open(io.BytesIO(r.content)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    for must in ("Báo cáo chuyến đi", VID, DEV, "DỮ LIỆU MÔ PHỎNG (SIMULATION)", "SỐ LIỆU TẠM THỜI",
                 "Chất lượng dữ liệu", "Chuyển động", "Phân loại chuyển động", "Cảnh báo", "KHÔNG phải hệ thống an toàn hàng hải"):
        assert must in text, must
    assert summary(client)["telemetry_csv_sha256"] in text.replace("\n", "")   # dau van tay in tren bao cao
    assert "20°" not in text                                                    # khong ve/ghi nguong nao


def test_pdf_banner_for_sensor_and_mixed(client, db, voyage):
    plumber = pytest.importorskip("pdfplumber")
    db.add_all([tele(0, mode=SourceMode.SENSOR), tele(1, mode=SourceMode.SIMULATION)])
    db.commit()
    end(client)
    with plumber.open(io.BytesIO(client.get(f"/api/v1/voyages/{VID}/report.pdf").content)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    assert "DỮ LIỆU TRỘN SENSOR + SIMULATION" in text and "SỐ LIỆU TẠM THỜI" not in text and "ĐÃ KẾT THÚC" in text


def test_pdf_escapes_markup_in_dynamic_text(client, db, voyage):
    from reports.pdf import build_pdf
    db.add(tele(0))
    db.commit()
    s, series = metrics.compute_summary(db, db.scalar(select(Voyage)))
    s.notes = ["<b>đậm & </i> <script>alert(1)</script> &amp; ]]>"]
    s.voyage.device_id = "a<b>&c"
    s.voyage.started_by = "x</para>y"
    assert build_pdf(s, series).startswith(b"%PDF")        # khong nem loi parse XML


def test_pdf_is_built_off_the_event_loop(client, db, voyage, monkeypatch):
    seen = {}
    import app.routers.voyages as router_mod
    real = router_mod.build_pdf

    def spy(s, series):
        seen["thread"] = threading.current_thread().name
        return real(s, series)

    monkeypatch.setattr(router_mod, "build_pdf", spy)
    from alarms.realtime import hub
    import asyncio

    async def name():
        return threading.current_thread().name

    assert client.get(f"/api/v1/voyages/{VID}/report.pdf").status_code == 200
    assert seen["thread"] != asyncio.run_coroutine_threadsafe(name(), hub.loop).result(timeout=5)


# ---------------------------------------------------------------- bieu do / hieu nang

def test_downsample_limits_points_but_keeps_shape():
    series = [(float(i), float(i)) for i in range(10_000)]
    out = metrics.downsample(series, 500)
    assert len(out) == 500 and out[0] == series[0] and out == sorted(out)
    small = series[:300]
    assert metrics.downsample(small, 500) == small


def test_large_voyage_report_is_fast_and_chart_is_bounded(client, db, voyage):
    db.bulk_save_objects([tele(i, roll=float((i % 40) - 20)) for i in range(6000)])
    db.commit()
    t = time.perf_counter()
    s, series = metrics.compute_summary(db, db.scalar(select(Voyage)))
    assert s.telemetry_rows == 6000 and len(series) <= 500
    pdf = client.get(f"/api/v1/voyages/{VID}/report.pdf")
    assert pdf.status_code == 200
    assert time.perf_counter() - t < 15
