"""Giam sat mo hinh (G6): nhat quan RF vs Baseline B, va (khi co nguon) drift PSI.

NGUYEN TAC:
- Khong tra ve so khong do duoc. PSI can vector 14 dac trung (contracts/features.md) do thiet bi/M2 cung cap;
  telemetry hien chi luu 3 dac trung tom tat nen drift tra `available=false`, KHONG dien 0.
- Luon kem source_mode (SENSOR/SIMULATION); mau sensor_ok = false bi loai khoi thong ke va duoc dem rieng.
- Lop RF khong bi doi ten thanh 'muc canh bao': lop chuyen dong khac muc canh bao.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Device, Telemetry
from app.models.enums import MotionClass
from app.schemas.monitor import AgreementStats, ClassAgreement, DriftStatus, FEATURE_NAMES
from reports.csvexport import utc


class DeviceNotFound(Exception):
    pass


def _require_device(db: Session, device_id: str) -> None:
    if db.scalar(select(Device.id).where(Device.device_id == device_id)) is None:
        raise DeviceNotFound(f"Không tìm thấy thiết bị '{device_id}'")


def _label(modes: list[str]) -> str:
    return "UNKNOWN" if not modes else (modes[0] if len(modes) == 1 else "MIXED")


def get_agreement(db: Session, device_id: str, voyage_id: Optional[str], limit: int) -> AgreementStats:
    """Ty le class_rf == class_baseline_b tren `limit` mau GAN NHAT (theo gio nhan) co du ca hai nhan."""
    _require_device(db, device_id)
    scope = [Telemetry.device_id == device_id, Telemetry.class_baseline_b.is_not(None)]
    if voyage_id is not None:
        scope.append(Telemetry.voyage_id == voyage_id)

    rows = db.execute(
        select(Telemetry.class_rf, Telemetry.class_baseline_b, Telemetry.source_mode, Telemetry.server_rx_time)
        .where(*scope, Telemetry.sensor_ok.is_(True))
        .order_by(Telemetry.server_rx_time.desc(), Telemetry.id.desc()).limit(limit)).all()
    excluded = db.scalar(select(func.count()).select_from(Telemetry).where(*scope, Telemetry.sensor_ok.is_(False))) or 0

    per_class: dict[str, list[int]] = {}   # lop RF -> [tong, khop]
    matched = 0
    for rf, base, _mode, _rx in rows:
        c = per_class.setdefault(rf.value, [0, 0])
        c[0] += 1
        if rf == base:
            c[1] += 1
            matched += 1
    modes = sorted({m.value for _, _, m, _ in rows})
    n = len(rows)

    notes: list[str] = []
    if n == 0:
        notes.append("Chưa có mẫu nào có đủ cả class_rf và class_baseline_b (và sensor_ok=true) trong phạm vi này.")
    if _label(modes) == "MIXED":
        notes.append("Dữ liệu trộn SENSOR và SIMULATION: cần diễn giải thận trọng.")
    if excluded:
        notes.append(f"{excluded} mẫu sensor_ok=false đã bị loại khỏi thống kê.")
    rf_fault = per_class.get(MotionClass.FAULT.value, [0, 0])[0]
    if rf_fault:
        notes.append(f"{rf_fault} mẫu class_rf=FAULT không thể khớp Baseline B (Baseline không có nhãn FAULT theo hợp đồng).")

    return AgreementStats(
        device_id=device_id, voyage_id=voyage_id, source_label=_label(modes), source_modes=modes,
        samples_considered=n, excluded_sensor_fault=excluded, matched=matched,
        agreement_rate=(matched / n) if n else None,
        by_rf_class={k: ClassAgreement(rf_total=t, matched=m, rate=(m / t) if t else None)
                     for k, (t, m) in sorted(per_class.items())},
        limit=limit,
        first_sample_at=utc(rows[-1][3]) if rows else None, last_sample_at=utc(rows[0][3]) if rows else None,
        notes=notes)


def get_drift(db: Session, device_id: str, window_hours: int) -> DriftStatus:
    """PSI tung dac trung. Hien CHUA KHA DUNG: can vector 14 dac trung + ml/monitor/ tu M2.

    Van tra ve so mau thuc co trong cua so de giao dien biet du lieu co dang chay hay khong.
    Khi M2 giao ml/monitor/: thay phan 'unavailable' bang ket qua PSI that (available=True, source='ml')."""
    _require_device(db, device_id)
    since = datetime.now(tz=timezone.utc) - timedelta(hours=window_hours)
    where = [Telemetry.device_id == device_id, Telemetry.server_rx_time >= since]
    n = db.scalar(select(func.count()).select_from(Telemetry).where(*where)) or 0
    modes = sorted(m.value for m in db.scalars(select(Telemetry.source_mode).where(*where).distinct()))
    return DriftStatus(
        device_id=device_id, window_hours=window_hours, window_samples=n, source_modes=modes,
        available=False, source="unavailable",
        reason=("Chưa có nguồn đặc trưng để tính PSI: telemetry chỉ lưu 3 đặc trưng tóm tắt "
                "(rms_roll_deg, heel_offset_deg, trend_rms_deg_per_min), trong khi hợp đồng có 14 đặc trưng. "
                "Cần M2 cung cấp vector đặc trưng đầy đủ và module ml/monitor/."),
        expected_features=list(FEATURE_NAMES), features=[], flagged_count=None)
