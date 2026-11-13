"""Tinh so lieu bao cao chuyen di TU DU LIEU GOC (khong luu ket qua da tinh -> luon khop du lieu hien co,
va co the tinh lai doc lap).

CONG THUC (de M4/T11 tinh lai):
- samples            = so ban ghi telemetry co (device_id, voyage_id) cua chuyen
- expected_samples   = tong tren tung boot_id cua (seq_max - seq_min + 1)        [seq dem lai sau moi lan khoi dong]
- received_rate      = samples / expected_samples
- thong ke chuyen dong (roll/pitch/heel/rms) CHI tren mau sensor_ok = true; mau sensor_ok = false chi duoc DEM rieng
- p95_abs_roll_deg   = nearest-rank: sorted(|roll|)[ceil(0.95 * n) - 1]
- mean_rms_roll_deg  = trung binh rms_roll_deg do THIET BI gui (backend khong tu tinh lai tu roll)
- phan bo lop        = dem theo SO MAU (khong phai theo thoi gian); tinh tren tat ca mau
- rf_baseline_agreement_rate = (#mau class_rf == class_baseline_b) / (#mau co ca hai)
- duration_s         = last_sample_at - first_sample_at   (theo server_rx_time)
- false_alarms_per_hour = (#canh bao FALSE_ALARM) / (duration_s / 3600), chi khi duration_s > 0 VA co it nhat
                          1 canh bao da duoc danh gia (neu khong: None, vi '0' se la ket luan chua co can cu)
"""
import hashlib
import math
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from alarms.service import compute_stats
from app.models import Command, Voyage
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
        self.cls_rf: dict[str, int] = {}
        self.cls_b: dict[str, int] = {}
        self.levels: dict[str, int] = {}
        self.both = 0
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
        self.cls_rf[t.class_rf.value] = self.cls_rf.get(t.class_rf.value, 0) + 1
        self.levels[t.alarm_level.value] = self.levels.get(t.alarm_level.value, 0) + 1
        if t.class_baseline_b is not None:
            self.cls_b[t.class_baseline_b.value] = self.cls_b.get(t.class_baseline_b.value, 0) + 1
            self.both += 1
            self.agree += t.class_rf == t.class_baseline_b
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


def compute_summary(db: Session, voyage: Voyage, now: Optional[datetime] = None) -> tuple[ReportSummary, list[tuple[float, float]]]:
    """Tra ve (ReportSummary, series_roll [(giay_ke_tu_mau_dau, roll_deg)] da lay mau thua de ve bieu do)."""
    p = _Pass()
    for (t,) in db.execute(telemetry_query(voyage.device_id, voyage.voyage_id)):
        p.add(t)

    expected = sum(b[1] - b[0] + 1 for b in p.boots.values())
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
        notes.append("Dữ liệu trộn SENSOR và SIMULATION trong cùng một chuyến: cần diễn giải thận trọng.")
    if expected > p.rows:
        notes.append(f"Thiếu {expected - p.rows} bản tin so với dải seq đã nhận (mất gói hoặc chưa gửi lại dữ liệu đệm).")
    if p.fault:
        notes.append(f"{p.fault} mẫu có sensor_ok=false đã bị loại khỏi thống kê chuyển động.")
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
            samples=p.rows, expected_samples=expected, missing_samples=max(0, expected - p.rows),
            received_rate=(p.rows / expected) if expected else None, boots=len(p.boots),
            sensor_fault_samples=p.fault),
        motion=MotionStats(
            samples_used=len(abs_sorted),
            max_abs_roll_deg=abs_sorted[-1] if abs_sorted else None,
            p95_abs_roll_deg=_percentile_nearest_rank(abs_sorted, 0.95),
            mean_rms_roll_deg=(p.rms_sum / p.rms_n) if p.rms_n else None,
            max_abs_pitch_deg=p.max_pitch, max_abs_heel_offset_deg=p.max_heel),
        class_rf=_distribution(p.cls_rf), class_baseline_b=_distribution(p.cls_b),
        rf_baseline_agreement_rate=(p.agree / p.both) if p.both else None,
        alarm_levels=_distribution(p.levels), alarms=alarms,
        # None (khong phai 0) khi chua co canh bao nao duoc danh gia: '0 canh bao sai' se la ket luan chua co can cu
        false_alarms_per_hour=(false_n / (duration / 3600.0)) if duration and duration > 0 and alarms.labeled > 0 else None,
        commands=CommandSummary(total=sum(cmd_by_state.values()), by_state=cmd_by_state),
        notes=notes, telemetry_rows=p.rows, telemetry_csv_sha256=p.hasher.hexdigest())
    return summary, series
