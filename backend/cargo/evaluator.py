"""Bộ đánh giá trạng thái hầm hàng (thuần, không truy cập CSDL). Backend là nguồn xác định trạng thái chính thức.

Quy tắc an toàn: dữ liệu thiếu / cũ / mất kết nối / không hợp lệ / chưa cấu hình → UNKNOWN (kèm lý do),
KHÔNG BAO GIỜ mặc định NORMAL.
"""
from dataclasses import dataclass
from typing import Optional

from cargo.thresholds import DHT22_TEMP_RANGE_C, HUMIDITY_RANGE_PCT, REFERENCES, WATER_PCT_RANGE, Effective

NORMAL, WARNING, CRITICAL, UNKNOWN = "NORMAL", "WARNING", "CRITICAL", "UNKNOWN"
SEVERITY = {NORMAL: 0, WARNING: 1, CRITICAL: 2}

# Lý do UNKNOWN
NO_DATA, STALE, SENSOR_FAULT, VALUE_MISSING, OUT_OF_RANGE, NOT_CONFIGURED = (
    "NO_DATA", "STALE", "SENSOR_FAULT", "VALUE_MISSING", "OUT_OF_RANGE", "NOT_CONFIGURED")

# Phân loại dữ liệu
SIMULATION, SENSOR_UNCALIBRATED, SENSOR_CALIBRATED = "SIMULATION", "SENSOR_UNCALIBRATED", "SENSOR_CALIBRATED"


def data_class(source_mode: str, calibrated: bool) -> str:
    """Phân biệt dữ liệu mô phỏng / cảm biến chưa hiệu chuẩn / cảm biến đã hiệu chuẩn (dữ liệu thực tế)."""
    if source_mode == "SIMULATION":
        return SIMULATION
    return SENSOR_CALIBRATED if calibrated else SENSOR_UNCALIBRATED


def classify(value: float, warning: float, critical: float) -> str:
    """NORMAL: < warning;  WARNING: warning ≤ v < critical;  CRITICAL: ≥ critical."""
    if value >= critical:
        return CRITICAL
    if value >= warning:
        return WARNING
    return NORMAL


@dataclass
class MetricEval:
    metric: str                       # WATER | TEMPERATURE | HUMIDITY
    state: str                        # NORMAL | WARNING | CRITICAL | UNKNOWN
    value: Optional[float]            # theo đơn vị `unit` (nước: mm); None nếu không đánh giá được
    unit: str
    reason: Optional[str] = None      # chỉ khi UNKNOWN
    warning: Optional[float] = None
    critical: Optional[float] = None
    detail: Optional[str] = None


def _unknown(metric: str, unit: str, reason: str, detail: Optional[str] = None, **kw) -> MetricEval:
    return MetricEval(metric, UNKNOWN, None, unit, reason, detail=detail, **kw)


def water_mm(pct: float, full_scale_mm: float) -> float:
    return round(pct * full_scale_mm / 100.0, 6)   # làm tròn để loại nhiễu nhị phân sát ngưỡng


def evaluate(eff: Effective, *, has_sample: bool, fresh: bool, sensor_ok: bool,
             water_pct: Optional[float], temp_c: Optional[float],
             humidity_pct: Optional[float]) -> dict[str, MetricEval]:
    units = {"WATER": REFERENCES["water"]["unit"], "TEMPERATURE": REFERENCES["temperature"]["unit"],
             "HUMIDITY": REFERENCES["humidity"]["unit"]}
    if not has_sample or not fresh:
        reason = NO_DATA if not has_sample else STALE
        why = ("Chưa nhận bản tin hầm hàng nào" if not has_sample
               else "Cargo Node không gửi dữ liệu mới (mất kết nối/dữ liệu cũ)")
        return {m: _unknown(m, u, reason, why) for m, u in units.items()}

    out: dict[str, MetricEval] = {}

    # --- Nước xâm nhập (mm) ---
    u = units["WATER"]
    wk = dict(warning=eff.water_warning_mm, critical=eff.water_critical_mm)
    if eff.errors or not eff.water_configured:
        miss = list(eff.missing) + list(eff.errors)
        out["WATER"] = _unknown("WATER", u, NOT_CONFIGURED,
                                "Thiếu/không hợp lệ: " + ", ".join(miss or ["cấu hình hầm hàng"]), **wk)
    elif water_pct is None:
        out["WATER"] = _unknown("WATER", u, VALUE_MISSING, "Cargo Node không gửi mực nước", **wk)
    elif not WATER_PCT_RANGE[0] <= water_pct <= WATER_PCT_RANGE[1]:
        out["WATER"] = _unknown("WATER", u, OUT_OF_RANGE, f"cargo_water_pct={water_pct} ngoài 0..100", **wk)
    else:
        mm = water_mm(water_pct, eff.full_scale_mm)  # type: ignore[arg-type]
        out["WATER"] = MetricEval("WATER", classify(mm, eff.water_warning_mm, eff.water_critical_mm), mm, u,  # type: ignore[arg-type]
                                  warning=eff.water_warning_mm, critical=eff.water_critical_mm)

    # --- Nhiệt độ không khí / độ ẩm (DHT22): cần sensor_ok ---
    for metric, v, lo_hi, w, c, key in (
            ("TEMPERATURE", temp_c, DHT22_TEMP_RANGE_C, eff.temp_warning, eff.temp_critical, "nhiệt độ"),
            ("HUMIDITY", humidity_pct, HUMIDITY_RANGE_PCT, eff.hum_warning, eff.hum_critical, "độ ẩm")):
        u = units[metric]
        if not sensor_ok:
            out[metric] = _unknown(metric, u, SENSOR_FAULT, f"DHT22 báo sensor_ok=false: không đánh giá {key}", warning=w, critical=c)
        elif v is None:
            out[metric] = _unknown(metric, u, VALUE_MISSING, f"Cargo Node không gửi {key}", warning=w, critical=c)
        elif not lo_hi[0] <= v <= lo_hi[1]:
            out[metric] = _unknown(metric, u, OUT_OF_RANGE,
                                   f"{key} = {v} ngoài khoảng hợp lệ {lo_hi[0]:g}..{lo_hi[1]:g}", warning=w, critical=c)
        else:
            out[metric] = MetricEval(metric, classify(v, w, c), v, u, warning=w, critical=c)
    return out


def overall(evals: dict[str, MetricEval]) -> str:
    """CRITICAL/WARNING nếu có; còn lại UNKNOWN nếu bất kỳ chỉ số nào không đánh giá được; chỉ NORMAL khi tất cả NORMAL."""
    known = [SEVERITY[e.state] for e in evals.values() if e.state in SEVERITY]
    worst = max(known) if known else -1
    if worst >= SEVERITY[CRITICAL]:
        return CRITICAL
    if worst >= SEVERITY[WARNING]:
        return WARNING
    if any(e.state == UNKNOWN for e in evals.values()) or not evals:
        return UNKNOWN
    return NORMAL
