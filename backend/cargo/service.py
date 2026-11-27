"""Vòng đời cảnh báo hầm hàng + trạng thái chính thức + cấu hình. Backend là nguồn xác định; frontend chỉ hiển thị.

Tái sử dụng KHÁI NIỆM của alarms/service.py (ACTIVE→ACKED→CLEARED, mức cao hơn sau ACK ⇒ bật lại ACTIVE, audit, vai trò ACK)
và enum AlarmState/AlarmLevel, nhưng lưu ở bảng riêng `cargo_alerts` (xem README: bảng `alarms` gắn chặt với luồng event của
thiết bị, thống kê MTTA/nhãn, replay chuyến, mute/ACK xuống thiết bị).
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import CargoAlert, CargoHoldConfig, CargoTelemetry, Device
from app.models.enums import AlarmLevel, AlarmState, NodeType
from app.services.audit import audit
from cargo import thresholds as th
from cargo.evaluator import (NORMAL, SEVERITY, UNKNOWN, MetricEval, data_class, evaluate, overall)

log = logging.getLogger("svmg.cargo")


class CargoNotFound(Exception):
    pass


class CargoConflict(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def get_config(db: Session, device_id: str) -> Optional[CargoHoldConfig]:
    return db.scalar(select(CargoHoldConfig).where(CargoHoldConfig.device_id == device_id))


def cargo_nodes(db: Session, device_id: str) -> list[Device]:
    """Cargo Node của một tàu chính, hoặc chính Cargo Node đó. 404 nếu thiết bị không tồn tại."""
    dev = db.scalar(select(Device).where(Device.device_id == device_id))
    if dev is None:
        raise CargoNotFound(f"Không tìm thấy thiết bị '{device_id}'")
    if dev.node_type == NodeType.CARGO:
        return [dev]
    return list(db.scalars(select(Device).where(Device.parent_device_id == device_id,
                                                 Device.node_type == NodeType.CARGO).order_by(Device.device_id)))


# ---------------------------------------------------------------- vòng đời cảnh báo (gọi khi nhận bản tin cargo)
def apply_sample(db: Session, row: CargoTelemetry) -> list[CargoAlert]:
    """Đánh giá 1 bản ghi hầm hàng mới nhận và mở/cập nhật/giải tỏa cảnh báo. UNKNOWN (thiếu/lỗi dữ liệu) KHÔNG giải tỏa
    cảnh báo đang mở và không mở cảnh báo mới (không có gì để khẳng định)."""
    dev = db.scalar(select(Device).where(Device.device_id == row.device_id))
    parent = dev.parent_device_id if dev else None
    eff = th.resolve(get_config(db, row.device_id))
    cls = data_class(row.source_mode.value, eff.calibrated)
    evals = evaluate(eff, has_sample=True, fresh=True, sensor_ok=row.sensor_ok, water_pct=row.cargo_water_pct,
                     temp_c=row.cargo_temp_c, humidity_pct=row.cargo_humidity_pct)
    changed: list[CargoAlert] = []
    for metric, ev in evals.items():
        if ev.state == UNKNOWN:
            continue
        open_ = db.scalar(select(CargoAlert).where(CargoAlert.device_id == row.device_id, CargoAlert.metric == metric,
                                                   CargoAlert.state != AlarmState.CLEARED))
        level = AlarmLevel(ev.state)
        if open_ is None:
            if ev.state == NORMAL:
                continue
            open_ = CargoAlert(
                device_id=row.device_id, parent_device_id=parent, metric=metric, state=AlarmState.ACTIVE, level=level,
                max_level=level, value=ev.value, peak_value=ev.value, unit=ev.unit, source_mode=row.source_mode,
                data_class=cls, threshold_warning=ev.warning, threshold_critical=ev.critical,
                threshold_version=eff.version_label, last_boot_id=row.boot_id, last_seq=row.seq,
                opened_at=row.server_rx_time, escalated=False)
            db.add(open_)
        else:
            if row.boot_id == open_.last_boot_id and row.seq <= open_.last_seq:
                continue                                  # bản tin cũ/đến muộn
            rising = SEVERITY[ev.state] > SEVERITY[open_.level.value]
            open_.last_boot_id, open_.last_seq = row.boot_id, row.seq
            open_.value, open_.unit, open_.data_class, open_.source_mode = ev.value, ev.unit, cls, row.source_mode
            open_.threshold_warning, open_.threshold_critical = ev.warning, ev.critical
            open_.threshold_version = eff.version_label
            if ev.state == NORMAL:
                open_.state, open_.level, open_.cleared_at = AlarmState.CLEARED, AlarmLevel.NORMAL, row.server_rx_time
            else:
                open_.level = level
                if ev.value is not None and ev.value > open_.peak_value:
                    open_.peak_value = ev.value
                if SEVERITY[ev.state] > SEVERITY[open_.max_level.value]:
                    open_.max_level = level
                if rising and open_.state == AlarmState.ACKED:
                    # mức nặng hơn sau khi đã ACK ⇒ không coi là đã xử lý, bắt người trực xác nhận lại (như alarms/service.py)
                    open_.state, open_.escalated = AlarmState.ACTIVE, True
                    audit(db, "system", "CARGO_ALERT_REACTIVATED", f"{row.device_id}:{metric}", {"level": ev.state})
        changed.append(open_)
    try:
        db.commit()
    except IntegrityError:                                # hai bản tin xử lý song song: chỉ muc duy nhất 1 cảnh báo mở/chỉ số
        db.rollback()
        log.warning("cargo alert race", extra={"device_id": row.device_id})
        return []
    for a in changed:
        log.info("cargo alert", extra={"device_id": a.device_id, "metric": a.metric, "level": a.level.value,
                                       "state": a.state.value})
    return changed


def ack_alert(db: Session, pk: int, actor: str, now: Optional[datetime] = None) -> tuple[CargoAlert, bool]:
    """Người trực ACK (idempotent). ACK ≠ giải tỏa: chỉ ghi nhận đã biết."""
    a = db.get(CargoAlert, pk)
    if a is None:
        raise CargoNotFound(f"Không tìm thấy cảnh báo hầm hàng #{pk}")
    if a.state == AlarmState.CLEARED:
        raise CargoConflict("Cảnh báo đã được giải tỏa, không thể ACK")
    if a.state == AlarmState.ACKED:
        return a, True
    a.state, a.acked_by = AlarmState.ACKED, actor
    if a.acked_at is None:
        a.acked_at = now or _now()
    audit(db, actor, "CARGO_ALERT_ACK", f"cargo-alert:{pk}",
          {"device_id": a.device_id, "metric": a.metric, "level": a.level.value})
    db.commit()
    return a, False


def list_alerts(db: Session, device_id: str, state: Optional[AlarmState], limit: int) -> list[CargoAlert]:
    ids = [n.device_id for n in cargo_nodes(db, device_id)]
    if not ids:
        return []
    q = select(CargoAlert).where(CargoAlert.device_id.in_(ids))
    if state is not None:
        q = q.where(CargoAlert.state == state)
    return list(db.scalars(q.order_by(CargoAlert.opened_at.desc(), CargoAlert.id.desc()).limit(limit)))


# ---------------------------------------------------------------- trạng thái chính thức
def _metric_dict(ev: MetricEval) -> dict[str, Any]:
    key = {"WATER": "water", "TEMPERATURE": "temperature", "HUMIDITY": "humidity"}[ev.metric]
    ref = th.REFERENCES[key]
    return {"metric": ev.metric, "state": ev.state, "value": ev.value, "unit": ev.unit, "reason": ev.reason,
            "detail": ev.detail, "warning": ev.warning, "critical": ev.critical, "basis": ref.get("basis"),
            "reference": ref["reference"], "note": ref["note"]}


def node_status(db: Session, node: Device, now: Optional[datetime] = None) -> dict[str, Any]:
    now = now or _now()
    latest = db.scalar(select(CargoTelemetry).where(CargoTelemetry.device_id == node.device_id)
                       .order_by(CargoTelemetry.server_rx_time.desc(), CargoTelemetry.id.desc()).limit(1))
    cfg = get_config(db, node.device_id)
    eff = th.resolve(cfg)
    stale_after = settings.cargo_stale_s
    age = None if latest is None else max(0.0, (now - _aware(latest.server_rx_time)).total_seconds())
    fresh = latest is not None and age is not None and age <= stale_after
    evals = evaluate(eff, has_sample=latest is not None, fresh=fresh, sensor_ok=bool(latest and latest.sensor_ok),
                     water_pct=latest.cargo_water_pct if latest else None,
                     temp_c=latest.cargo_temp_c if latest else None,
                     humidity_pct=latest.cargo_humidity_pct if latest else None)
    open_n = len(list(db.scalars(select(CargoAlert.id).where(CargoAlert.device_id == node.device_id,
                                                              CargoAlert.state != AlarmState.CLEARED))))
    return {
        "device_id": node.device_id,
        "link": "NO_DATA" if latest is None else ("ONLINE" if fresh else "STALE"),
        "last_sample_at": latest.server_rx_time if latest else None,
        "age_s": age, "stale_after_s": stale_after,
        "sensor_ok": latest.sensor_ok if latest else None,
        "source_mode": latest.source_mode if latest else node.source_mode,
        "data_class": data_class((latest.source_mode if latest else node.source_mode).value, eff.calibrated),
        "raw_water_pct": latest.cargo_water_pct if (latest and fresh) else None,
        "state": overall(evals), "metrics": [_metric_dict(e) for e in evals.values()],
        "config_version": eff.config_version, "threshold_version": eff.version_label,
        "missing_config": eff.missing, "config_errors": eff.errors, "open_alerts": open_n,
    }


def build_status(db: Session, device_id: str, now: Optional[datetime] = None) -> dict[str, Any]:
    nodes = [node_status(db, n, now) for n in cargo_nodes(db, device_id)]
    if not nodes:
        state, link = UNKNOWN, "NO_NODE"
    else:
        sev = [SEVERITY[n["state"]] for n in nodes if n["state"] in SEVERITY]
        worst = max(sev) if sev else -1
        state = "CRITICAL" if worst == 2 else "WARNING" if worst == 1 else (
            UNKNOWN if any(n["state"] == UNKNOWN for n in nodes) else NORMAL)
        link = "ONLINE" if any(n["link"] == "ONLINE" for n in nodes) else (
            "STALE" if any(n["link"] == "STALE" for n in nodes) else "NO_DATA")
    return {"device_id": device_id, "state": state, "link": link, "nodes": nodes, "profile": th.PROFILE_KEY,
            "profile_scope": th.PROFILE_SCOPE, "disclaimer": th.DISCLAIMER}


# ---------------------------------------------------------------- cấu hình
def effective_dict(eff: th.Effective) -> dict[str, Any]:
    r = th.REFERENCES
    return {
        "water": {"unit": "mm", "warning_mm": eff.water_warning_mm, "critical_mm": eff.water_critical_mm,
                  "rule": "critical = min(critical_fraction_of_depth × cargo_hold_depth_mm, critical_cap_mm)",
                  **{k: th.merge_thresholds(None)["water"][k] for k in ("critical_fraction_of_depth", "critical_cap_mm")},
                  "reference": r["water"]["reference"], "note": r["water"]["note"]},
        "temperature": {"unit": "°C", "basis": "AIR_IN_HOLD", "warning": eff.temp_warning, "critical": eff.temp_critical,
                        "reference": r["temperature"]["reference"], "note": r["temperature"]["note"]},
        "humidity": {"unit": "%RH", "basis": "AIR_IN_HOLD", "warning": eff.hum_warning, "critical": eff.hum_critical,
                     "reference": r["humidity"]["reference"], "note": r["humidity"]["note"]},
    }


def config_view(db: Session, device_id: str) -> dict[str, Any]:
    cfg = get_config(db, device_id)
    eff = th.resolve(cfg)
    ed = effective_dict(eff)
    if cfg and cfg.thresholds:   # hiển thị đúng giá trị tham số water đã ghi đè
        w = th.merge_thresholds(cfg.thresholds)["water"]
        ed["water"].update(critical_fraction_of_depth=w["critical_fraction_of_depth"], critical_cap_mm=w["critical_cap_mm"])
    return {
        "device_id": device_id, "configured": cfg is not None, "version": eff.config_version,
        "vessel_type": eff.vessel_type, "cargo_type": eff.cargo_type, "cargo_hold_depth_mm": eff.depth_mm,
        "water_sensor_full_scale_mm": eff.full_scale_mm, "sensor_calibrated": eff.calibrated,
        "effective_thresholds": ed, "threshold_version": eff.version_label,
        "uses_default_thresholds": eff.is_default_thresholds, "missing_fields": eff.missing, "errors": eff.errors,
        "updated_by": cfg.updated_by if cfg else None, "updated_at": cfg.updated_at if cfg else None,
        "profile": th.PROFILE_KEY, "profile_scope": th.PROFILE_SCOPE, "disclaimer": th.DISCLAIMER,
    }


def update_config(db: Session, node: Device, fields: dict[str, Any], actor: str) -> CargoHoldConfig:
    """Cập nhật từng phần. Kiểm tra trên giá trị SAU KHI gộp; sai ⇒ th.ConfigInvalid (422), không ghi gì."""
    if node.node_type != NodeType.CARGO:
        raise CargoConflict(f"'{node.device_id}' không phải Cargo Node; cấu hình hầm hàng đặt trên Cargo Node")
    cfg = get_config(db, node.device_id)
    cur = {
        "vessel_type": cfg.vessel_type if cfg else None, "cargo_type": cfg.cargo_type if cfg else None,
        "cargo_hold_depth_mm": cfg.cargo_hold_depth_mm if cfg else None,
        "water_sensor_full_scale_mm": cfg.water_sensor_full_scale_mm if cfg else None,
        "sensor_calibrated": bool(cfg.sensor_calibrated) if cfg else False,
        "thresholds": cfg.thresholds if cfg else None,
    }
    new = {**cur, **fields}
    th.validate(new["cargo_hold_depth_mm"], new["water_sensor_full_scale_mm"], new["thresholds"])
    if cfg is None:
        cfg = CargoHoldConfig(device_id=node.device_id, version=1, updated_by=actor)
        db.add(cfg)
    else:
        cfg.version = (cfg.version or 0) + 1
    for k, v in new.items():
        setattr(cfg, k, v)
    cfg.updated_by, cfg.updated_at = actor, _now()
    audit(db, actor, "CARGO_CONFIG_UPDATE", node.device_id,
          {"version": cfg.version, "before": cur, "after": new, "threshold_profile": th.PROFILE_KEY})
    db.commit()
    return cfg
