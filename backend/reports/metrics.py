"""Tinh so lieu bao cao chuyen di TU DU LIEU GOC (khong luu ket qua da tinh -> luon khop du lieu hien co,
va co the tinh lai doc lap).

CONG THUC (de M4/T11 tinh lai):
- samples            = so ban ghi telemetry co (device_id, voyage_id) cua chuyen
- CHAT LUONG NHAN (bang chung, khong suy doan): firmware dung MOT bo dem seq cho telemetry, event, health, trace
  (app.cpp: SEQ). Health tieu thu seq nhung KHONG gui seq/boot_id -> khoang trong seq KHONG dong nghia mat goi.
  Theo tung boot_id, moi seq trong dai [seq_min, seq_max] khong co telemetry cua chuyen duoc phan loai:
    * seq_used_by_events           : co AlarmEvent cung (device, boot, seq)            -> DA XAC MINH, khong phai telemetry
    * seq_telemetry_outside_voyage : co telemetry cung (device, boot, seq) o chuyen khac / khong chuyen (den tre)
                                     -> DA XAC MINH da nhan
    * seq_gaps_health_timing       : con lai, ghep 1-1 voi ban tin health nhan GIUA hai telemetry ke ben cung boot
                                     -> PHU HOP health theo thoi gian (khong xac minh tuyet doi vi health khong mang seq)
    * seq_gaps_unclassified        : con lai -> CHUA PHAN LOAI (co the mat telemetry/health/event hoac ban tin khac)
  receive_status / received_rate:
    VERIFIED              moi khoang trong da xac minh -> expected = samples + outside, missing = 0, received_rate = 1
    NO_LOSS_EVIDENCE      khoang trong con lai deu khop health theo thoi gian -> received_rate = None (khong co bang chung mat goi)
    INSUFFICIENT_EVIDENCE con khoang trong chua phan loai -> received_rate = None
    NO_DATA               chuyen chua co telemetry
  received_rate_lower_bound = (samples + outside) / (samples + outside + health_timing + unclassified): truong hop XAU NHAT
  coi moi khoang trong chua xac minh la telemetry bi mat (cung la cong thuc 'ty le nhan' cu, chi la can duoi).
- thong ke chuyen dong (roll/pitch/heel/rms) CHI tren mau sensor_ok = true; mau sensor_ok = false chi duoc DEM rieng
- p95_abs_roll_deg   = nearest-rank: sorted(|roll|)[ceil(0.95 * n) - 1]
- mean_rms_roll_deg  = trung binh rms_roll_deg do THIET BI gui (backend khong tu tinh lai tu roll)
- phan bo lop        = dem theo SO MAU (khong phai theo thoi gian); tinh tren tat ca mau
- rf_baseline_agreement_rate = (#mau class_rf == class_baseline_b) / (#mau ma CA HAI la lop phan loai hop le)
                       [UNKNOWN/FAULT bi loai: hai mo hinh cung UNKNOWN KHONG phai dong thuan; khong co cap -> None]
- duration_s         = last_sample_at - first_sample_at   (theo server_rx_time)
- false_alarms_per_hour = (#canh bao FALSE_ALARM) / (duration_s / 3600), chi khi duration_s > 0 VA co it nhat
                          1 canh bao da duoc danh gia (neu khong: None, vi '0' se la ket luan chua co can cu)
"""
import hashlib
import math
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from alarms.service import compute_stats
from app.models import AlarmEvent, Command, DeviceHealth, Telemetry, Voyage
from app.models.enums import is_classified_pair
from app.schemas.voyage import (
    CommandSummary, DataQuality, Distribution, MotionStats, ReportSummary, VoyageOut,
)
from reports.csvexport import TELEMETRY_COLUMNS, header_line, telemetry_line, telemetry_query, utc


def _percentile_nearest_rank(sorted_vals: list[float], q: float) -> Optional[float]:
    if not sorted_vals:
        return None
    k = max(0, math.ceil(q * len(sorted_vals)) - 1)
    return sorted_vals[k]


def _distribution(counts: dict[str, int]) -> Distribution:
    total = sum(counts.values())
    return Distribution(counts=dict(sorted(counts.items())),
                        share={k: v / total for k, v in sorted(counts.items())} if total else {})


def downsample(series: list[tuple[float, float]], max_points: int = 500) -> list[tuple[float, float]]:
    """Lay mau deu de ve bieu do (khong anh huong so lieu thong ke)."""
    if len(series) <= max_points:
        return series
    step = len(series) / max_points
    return [series[int(i * step)] for i in range(max_points)]


class _Pass:
    """Mot luot duyet telemetry: gom moi so lieu + bam CSV cung luc."""

    def __init__(self) -> None:
        self.hasher = hashlib.sha256()
        self.hasher.update(header_line(TELEMETRY_COLUMNS).encode("utf-8"))
        self.rows = 0
        self.first: Optional[datetime] = None
        self.last: Optional[datetime] = None
        self.sources: set[str] = set()
        self.boots: dict[str, list[int]] = {}      # boot_id -> [seq_min, seq_max, count]
        self.points: dict[str, list[tuple[int, datetime]]] = {}   # boot_id -> [(seq, server_rx_time)] cho phan loai khoang trong
        self.cls_rf: dict[str, int] = {}
        self.cls_b: dict[str, int] = {}
        self.levels: dict[str, int] = {}
        self.both = 0
        self.unclassified = 0   # co Baseline nhung RF hoac Baseline la UNKNOWN/FAULT: khong vao ty le dong thuan
        self.agree = 0
        self.fault = 0
        self.abs_roll: list[float] = []
        self.max_pitch: Optional[float] = None
        self.max_heel: Optional[float] = None
        self.rms_sum = 0.0
        self.rms_n = 0
        self.series: list[tuple[datetime, float]] = []

    def add(self, t) -> None:
        self.hasher.update(telemetry_line(t).encode("utf-8"))
        self.rows += 1
        rx = utc(t.server_rx_time)
        self.first = self.first or rx
        self.last = rx
        self.sources.add(t.source_mode.value)
        b = self.boots.setdefault(t.boot_id, [t.seq, t.seq, 0])
        b[0], b[1], b[2] = min(b[0], t.seq), max(b[1], t.seq), b[2] + 1
        self.points.setdefault(t.boot_id, []).append((t.seq, rx))
        self.cls_rf[t.class_rf.value] = self.cls_rf.get(t.class_rf.value, 0) + 1
        self.levels[t.alarm_level.value] = self.levels.get(t.alarm_level.value, 0) + 1
        if t.class_baseline_b is not None:
            self.cls_b[t.class_baseline_b.value] = self.cls_b.get(t.class_baseline_b.value, 0) + 1
            if is_classified_pair(t.class_rf, t.class_baseline_b):
                self.both += 1
                self.agree += t.class_rf == t.class_baseline_b
            else:
                self.unclassified += 1
        if not t.sensor_ok:
            self.fault += 1  # so do loi: khong dua vao thong ke chuyen dong
            return
        self.abs_roll.append(abs(t.roll_deg))
        self.series.append((rx, t.roll_deg))
        p = abs(t.pitch_deg)
        self.max_pitch = p if self.max_pitch is None else max(self.max_pitch, p)
        if t.heel_offset_deg is not None:
            h = abs(t.heel_offset_deg)
            self.max_heel = h if self.max_heel is None else max(self.max_heel, h)
        if t.rms_roll_deg is not None:
            self.rms_sum += t.rms_roll_deg
            self.rms_n += 1


def seq_accounting(db: Session, voyage: Voyage, p: "_Pass") -> dict:
    """Phan loai khoang trong seq theo BANG CHUNG (xem docstring dau tep). Khong bao gio coi khoang trong la mat goi."""
    span = sum(hi - lo + 1 for lo, hi, _ in p.boots.values())
    events = outside = timing = unclassified = 0
    health: list[tuple[int, datetime]] = []
    if p.first and p.last:
        health = sorted(((hid, utc(rx)) for hid, rx in db.execute(
            select(DeviceHealth.id, DeviceHealth.server_rx_time).where(
                DeviceHealth.device_id == voyage.device_id, DeviceHealth.server_rx_time.between(p.first, p.last)))),
            key=lambda h: h[1])
    used: set[int] = set()
    for boot, (lo, hi, _) in p.boots.items():
        pts = sorted(p.points[boot])
        have = {sq for sq, _ in pts}
        if hi - lo + 1 == len(have):
            continue
        in_boot = [Telemetry.device_id == voyage.device_id, Telemetry.boot_id == boot, Telemetry.seq.between(lo, hi)]
        ev = set(db.scalars(select(AlarmEvent.seq).where(AlarmEvent.device_id == voyage.device_id, AlarmEvent.boot_id == boot,
                                                         AlarmEvent.seq.between(lo, hi)))) - have
        out = set(db.scalars(select(Telemetry.seq).where(*in_boot, or_(Telemetry.voyage_id.is_(None),
                                                                        Telemetry.voyage_id != voyage.voyage_id)))) - have - ev
        events, outside = events + len(ev), outside + len(out)
        for (sa, ra), (sb, rb) in zip(pts, pts[1:]):            # tung doan seq trong giua hai telemetry ke ben cung boot
            run = [sq for sq in range(sa + 1, sb) if sq not in ev and sq not in out]
            if not run:
                continue
            t0, t1 = min(ra, rb), max(ra, rb)
            cands = [hid for hid, hrx in health if hid not in used and t0 < hrx < t1]
            k = min(len(run), len(cands))                        # moi ban tin health giai thich toi da MOT seq
            used.update(cands[:k])
            timing, unclassified = timing + k, unclassified + len(run) - k
    received = p.rows + outside
    worst = received + timing + unclassified
    status = ("NO_DATA" if p.rows == 0 else "VERIFIED" if timing == 0 and unclassified == 0
              else "NO_LOSS_EVIDENCE" if unclassified == 0 else "INSUFFICIENT_EVIDENCE")
    notes: list[str] = []
    if status == "VERIFIED" and span > p.rows:
        notes.append(f"{span - p.rows} khoảng trống seq đã xác minh không phải telemetry bị mất ({events} seq của sự kiện cảnh báo, "
                     f"{outside} telemetry ghi nhận ngoài chuyến).")
    if timing:
        notes.append(f"{timing} khoảng trống seq trùng thời điểm bản tin health (health dùng chung bộ đếm seq nhưng không gửi seq): "
                     "phù hợp health, không phải bằng chứng mất telemetry; chưa xác minh tuyệt đối nên không tính tỉ lệ nhận.")
    if unclassified:
        notes.append(f"{unclassified} khoảng trống seq chưa phân loại (có thể là telemetry, health hoặc sự kiện bị mất, hay bản tin khác): "
                     "chưa đủ bằng chứng để tính tỉ lệ nhận telemetry.")
    if status in ("NO_LOSS_EVIDENCE", "INSUFFICIENT_EVIDENCE"):
        notes.append(f"Cận dưới tỉ lệ nhận (coi mọi khoảng trống chưa xác minh là telemetry mất): {received / worst * 100:.1f}%.")
    return {"receive_status": status, "expected_samples": received if status == "VERIFIED" else None,
            "missing_samples": 0 if status == "VERIFIED" else None,
            "received_rate": 1.0 if status == "VERIFIED" else None,
            "received_rate_lower_bound": (received / worst) if worst else None,
            "seq_span": span, "seq_gaps": span - p.rows, "seq_used_by_events": events, "seq_telemetry_outside_voyage": outside,
            "seq_gaps_health_timing": timing, "seq_gaps_unclassified": unclassified, "notes": notes}


def compute_summary(db: Session, voyage: Voyage, now: Optional[datetime] = None) -> tuple[ReportSummary, list[tuple[float, float]]]:
    """Tra ve (ReportSummary, series_roll [(giay_ke_tu_mau_dau, roll_deg)] da lay mau thua de ve bieu do)."""
    p = _Pass()
    for (t,) in db.execute(telemetry_query(voyage.device_id, voyage.voyage_id)):
        p.add(t)

    q = seq_accounting(db, voyage, p)
    duration = (p.last - p.first).total_seconds() if p.first and p.last else None
    alarms = compute_stats(db, device_id=voyage.device_id, voyage_id=voyage.voyage_id)
    false_n = alarms.by_label.get("FALSE_ALARM", 0)

    cmd_by_state: dict[str, int] = {}
    if p.first and p.last:
        for c in db.scalars(select(Command).where(Command.device_id == voyage.device_id)):
            if p.first <= utc(c.created_at) <= p.last:
                cmd_by_state[c.state.value] = cmd_by_state.get(c.state.value, 0) + 1

    sources = sorted(p.sources)
    label = "UNKNOWN" if not sources else (sources[0] if len(sources) == 1 else "MIXED")
    provisional = voyage.status.value == "ACTIVE"

    notes: list[str] = []
    if provisional:
        notes.append("Chuyến đi đang chạy: số liệu chỉ là TẠM THỜI, sẽ thay đổi khi có thêm dữ liệu.")
    if p.rows == 0:
        notes.append("Chưa có telemetry nào mang voyage_id này từ thiết bị "
                     f"'{voyage.device_id}': báo cáo chưa có số liệu.")
    if label == "MIXED":
        notes.append("Dữ liệu trộn SENSOR và SIMULATION trong cùng một chuyến: cần diễn giải thận trọng; "
                     "không gộp tỉ lệ đồng thuận RF – Baseline B của hai nguồn.")
    notes += q.pop("notes")
    if p.fault:
        notes.append(f"{p.fault} mẫu có sensor_ok=false đã bị loại khỏi thống kê chuyển động.")
    if p.unclassified:
        notes.append(f"{p.unclassified} mẫu có RF hoặc Baseline B là UNKNOWN/FAULT không được tính vào tỉ lệ đồng thuận"
                     + ("; chưa đủ dữ liệu để đánh giá đồng thuận." if not p.both else "."))
    if p.boots and len(p.boots) > 1:
        notes.append(f"Thiết bị khởi động lại {len(p.boots) - 1} lần trong chuyến (seq được tính riêng theo từng boot_id).")

    series: list[tuple[float, float]] = []
    if p.first:
        series = downsample([((rx - p.first).total_seconds(), roll) for rx, roll in p.series])

    abs_sorted = sorted(p.abs_roll)
    summary = ReportSummary(
        voyage=VoyageOut.model_validate(voyage),
        provisional=provisional,
        generated_at=now or datetime.now(timezone.utc),
        source_label=label, source_modes=sources,
        first_sample_at=p.first, last_sample_at=p.last, duration_s=duration,
        data_quality=DataQuality(
            samples=p.rows, **q, boots=len(p.boots),
            sensor_fault_samples=p.fault),
        motion=MotionStats(
            samples_used=len(abs_sorted),
            max_abs_roll_deg=abs_sorted[-1] if abs_sorted else None,
            p95_abs_roll_deg=_percentile_nearest_rank(abs_sorted, 0.95),
            mean_rms_roll_deg=(p.rms_sum / p.rms_n) if p.rms_n else None,
            max_abs_pitch_deg=p.max_pitch, max_abs_heel_offset_deg=p.max_heel),
        class_rf=_distribution(p.cls_rf), class_baseline_b=_distribution(p.cls_b),
        # Khong tron nguon: chuyen co ca SENSOR va SIMULATION -> None (mot ty le chung se gay hieu nham)
        rf_baseline_agreement_rate=(p.agree / p.both) if p.both and label != "MIXED" else None,
        alarm_levels=_distribution(p.levels), alarms=alarms,
        # None (khong phai 0) khi chua co canh bao nao duoc danh gia: '0 canh bao sai' se la ket luan chua co can cu
        false_alarms_per_hour=(false_n / (duration / 3600.0)) if duration and duration > 0 and alarms.labeled > 0 else None,
        commands=CommandSummary(total=sum(cmd_by_state.values()), by_state=cmd_by_state),
        notes=notes, telemetry_rows=p.rows, telemetry_csv_sha256=p.hasher.hexdigest())
    return summary, series
