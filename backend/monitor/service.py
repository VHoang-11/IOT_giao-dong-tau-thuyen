"""Giam sat mo hinh (G6): nhat quan RF vs Baseline B, va (khi co nguon) drift PSI.

NGUYEN TAC:
- Khong tra ve so khong do duoc. PSI can vector dac trung day du (contracts/features23.json) do thiet bi/M2 cung cap;
  telemetry hien chi luu 3 dac trung tom tat nen drift tra `available=false`, KHONG dien 0.
- Luon kem source_mode (SENSOR/SIMULATION); mau sensor_ok = false bi loai khoi thong ke va duoc dem rieng.
- Lop RF khong bi doi ten thanh 'muc canh bao': lop chuyen dong khac muc canh bao.
- Dong thuan chi tinh tren cap ma CA HAI mo hinh co lop phan loai hop le; UNKNOWN/FAULT bi loai va dem rieng.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Device, Telemetry
from app.models.enums import CLASSIFIED_MOTION_CLASSES, SourceMode
from app.schemas.monitor import AgreementStats, ClassAgreement, DriftStatus, ModeAgreement
from monitor.feature_contract import load_contract
from reports.csvexport import utc


class DeviceNotFound(Exception):
    pass


def _require_device(db: Session, device_id: str) -> None:
    if db.scalar(select(Device.id).where(Device.device_id == device_id)) is None:
        raise DeviceNotFound(f"Không tìm thấy thiết bị '{device_id}'")


def _label(modes: list[str]) -> str:
    return "UNKNOWN" if not modes else (modes[0] if len(modes) == 1 else "MIXED")


def _tally(rows) -> tuple[int, int, dict[str, ClassAgreement]]:
    per_class: dict[str, list[int]] = {}   # lop RF -> [tong, khop]
    for rf, base, _mode, _rx in rows:
        c = per_class.setdefault(rf.value, [0, 0])
        c[0] += 1
        c[1] += rf == base
    matched = sum(m for _, m in per_class.values())
    return matched, len(rows), {k: ClassAgreement(rf_total=t, matched=m, rate=(m / t) if t else None)
                                for k, (t, m) in sorted(per_class.items())}


def get_agreement(db: Session, device_id: str, voyage_id: Optional[str], limit: int,
                  source_mode: Optional[SourceMode] = None) -> AgreementStats:
    """Ty le class_rf == class_baseline_b tren `limit` CAP HOP LE gan nhat (theo gio nhan).

    Cap hop le = sensor_ok=true VA ca hai nhan thuoc lop phan loai (NORMAL/HIGH_ROLL/PERSISTENT_OFFSET/
    AMPLITUDE_GROWTH). UNKNOWN/FAULT la 'khong ket luan': bi loai va dem rieng, UNKNOWN==UNKNOWN KHONG la dong thuan.
    Khong tron nguon: khi co ca SENSOR va SIMULATION (va khong loc source_mode) thi agreement_rate=None, xem by_source_mode."""
    _require_device(db, device_id)
    scope = [Telemetry.device_id == device_id, Telemetry.class_baseline_b.is_not(None)]
    if voyage_id is not None:
        scope.append(Telemetry.voyage_id == voyage_id)
    if source_mode is not None:
        scope.append(Telemetry.source_mode == source_mode)
    ok = Telemetry.sensor_ok.is_(True)
    valid = [Telemetry.class_rf.in_(CLASSIFIED_MOTION_CLASSES), Telemetry.class_baseline_b.in_(CLASSIFIED_MOTION_CLASSES)]

    rows = db.execute(
        select(Telemetry.class_rf, Telemetry.class_baseline_b, Telemetry.source_mode, Telemetry.server_rx_time)
        .where(*scope, ok, *valid)
        .order_by(Telemetry.server_rx_time.desc(), Telemetry.id.desc()).limit(limit)).all()
    excluded = db.scalar(select(func.count()).select_from(Telemetry).where(*scope, Telemetry.sensor_ok.is_(False))) or 0
    invalid = or_(Telemetry.class_rf.not_in(CLASSIFIED_MOTION_CLASSES), Telemetry.class_baseline_b.not_in(CLASSIFIED_MOTION_CLASSES))
    unclassified = db.scalar(select(func.count()).select_from(Telemetry).where(*scope, ok, invalid)) or 0
    labels: dict[str, int] = {}
    for col, name in ((Telemetry.class_rf, "class_rf"), (Telemetry.class_baseline_b, "class_baseline_b")):
        for value, count in db.execute(select(col, func.count()).where(*scope, ok, col.not_in(CLASSIFIED_MOTION_CLASSES))
                                       .group_by(col)).all():
            labels[f"{name}={value.value}"] = count

    modes = sorted({m.value for _, _, m, _ in rows})
    by_mode = {}
    for mode in modes:
        sub = [r for r in rows if r[2].value == mode]
        m, n, per = _tally(sub)
        by_mode[mode] = ModeAgreement(samples_considered=n, matched=m, agreement_rate=m / n, by_rf_class=per)
    matched, n, per_class = _tally(rows)
    mixed = _label(modes) == "MIXED"
    status = "INSUFFICIENT_DATA" if n == 0 else ("MIXED_SOURCES" if mixed else "OK")

    notes: list[str] = []
    if n == 0:
        notes.append("Chưa đủ dữ liệu để đánh giá đồng thuận: không có cặp nào mà cả Random Forest và Baseline B "
                     "đều có nhãn phân loại hợp lệ (sensor_ok=true) trong phạm vi này.")
    if mixed:
        notes.append("Dữ liệu trộn SENSOR và SIMULATION: không gộp thành một tỉ lệ; xem theo từng nguồn (by_source_mode).")
    if unclassified:
        detail = ", ".join(f"{k}: {v}" for k, v in sorted(labels.items()))
        notes.append(f"{unclassified} mẫu có nhãn không phải lớp phân loại (UNKNOWN/FAULT) đã bị loại ({detail}); "
                     "hai mô hình cùng UNKNOWN không được tính là đồng thuận.")
    if excluded:
        notes.append(f"{excluded} mẫu sensor_ok=false đã bị loại khỏi thống kê.")

    return AgreementStats(
        device_id=device_id, voyage_id=voyage_id, source_label=_label(modes), source_modes=modes, status=status,
        samples_considered=n, excluded_sensor_fault=excluded, excluded_unclassified=unclassified, unclassified_labels=labels,
        matched=matched, agreement_rate=(matched / n) if status == "OK" else None,
        by_rf_class=per_class if not mixed else {}, by_source_mode=by_mode, limit=limit,
        first_sample_at=utc(rows[-1][3]) if rows else None, last_sample_at=utc(rows[0][3]) if rows else None,
        notes=notes)


def get_drift(db: Session, device_id: str, window_hours: int) -> DriftStatus:
    """PSI tung dac trung. Hien CHUA KHA DUNG: can vector dac trung + ml/monitor/ tu M2.

    Van tra ve so mau thuc co trong cua so de giao dien biet du lieu co dang chay hay khong, kem hop dong dac trung
    va viec thiet bi bao cung phien ban hay khong (firmware cu 14 dac trung vs hop dong 23 -> schema_match=false).
    Khi M2 giao ml/monitor/: thay phan 'unavailable' bang ket qua PSI that (available=True, source='ml')."""
    _require_device(db, device_id)
    dev = db.scalar(select(Device).where(Device.device_id == device_id))
    since = datetime.now(tz=timezone.utc) - timedelta(hours=window_hours)
    where = [Telemetry.device_id == device_id, Telemetry.server_rx_time >= since]
    n = db.scalar(select(func.count()).select_from(Telemetry).where(*where)) or 0
    modes = sorted(m.value for m in db.scalars(select(Telemetry.source_mode).where(*where).distinct()))
    fc = load_contract()
    match: Optional[bool] = None
    if fc is not None and dev.feature_schema_version is not None:
        match = (dev.feature_schema_version == fc.schema_version
                 and (dev.feature_count is None or dev.feature_count == fc.count)
                 and (dev.preprocessing_version is None or dev.preprocessing_version == fc.preprocessing_version))
    count = fc.count if fc else "?"
    return DriftStatus(
        device_id=device_id, window_hours=window_hours, window_samples=n, source_modes=modes,
        available=False, source="unavailable",
        reason=(f"Chưa có nguồn đặc trưng để tính PSI: telemetry chỉ lưu 3 đặc trưng tóm tắt "
                f"(rms_roll_deg, heel_offset_deg, trend_rms_deg_per_min), trong khi hợp đồng có {count} đặc trưng. "
                "Cần M2 cung cấp vector đặc trưng đầy đủ và module ml/monitor/."),
        expected_features=list(fc.names) if fc else [], feature_contract_available=fc is not None,
        feature_schema_version=fc.schema_version if fc else None, feature_count=fc.count if fc else None,
        device_feature_schema_version=dev.feature_schema_version, device_feature_count=dev.feature_count,
        schema_match=match, features=[], flagged_count=None)
