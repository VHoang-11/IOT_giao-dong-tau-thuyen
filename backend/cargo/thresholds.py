"""Bộ ngưỡng cảnh báo hầm hàng (mặc định + cấu hình theo tàu/hầm) và kiểm tra tính hợp lệ.

PROTOTYPE hỗ trợ giám sát, KHÔNG phải thiết bị an toàn hàng hải được chứng nhận; các ngưỡng KHÔNG đồng nghĩa với
việc hệ thống tuân thủ/đạt chứng nhận SOLAS hay IMO. Nguồn tham chiếu dưới đây ghi lại đúng như nhóm cung cấp
(chưa được hệ thống kiểm chứng độc lập).
"""
from dataclasses import dataclass, field
from typing import Any, Optional

PROFILE_KEY = "bulk-dry-agri-prototype"
PROFILE_VERSION = 1
PROFILE_SCOPE = "Tàu chở hàng rời vận chuyển hàng nông sản khô (prototype nghiên cứu/đào tạo)"
DISCLAIMER = ("Prototype hỗ trợ giám sát, chưa phải thiết bị an toàn hàng hải được chứng nhận; "
              "không tuyên bố đạt chứng nhận SOLAS/IMO.")

# Giới hạn vật lý hợp lý của cảm biến (ngoài khoảng này = giá trị không hợp lệ, KHÔNG coi là NORMAL)
DHT22_TEMP_RANGE_C = (-40.0, 80.0)
HUMIDITY_RANGE_PCT = (0.0, 100.0)
WATER_PCT_RANGE = (0.0, 100.0)
MAX_HOLD_DEPTH_MM = 100_000.0

DEFAULTS: dict[str, dict[str, float]] = {
    "water": {"warning_mm": 500.0, "critical_fraction_of_depth": 0.15, "critical_cap_mm": 2000.0},
    "temperature": {"warning": 35.0, "critical": 40.0},
    "humidity": {"warning": 75.0, "critical": 90.0},
}

# Nguồn tham chiếu + ghi chú phạm vi
REFERENCES: dict[str, dict[str, Any]] = {
    "water": {
        "unit": "mm",
        "reference": ["SOLAS Chapter XII, Regulation 12", "IMO Resolution MSC.188(79)/Rev.2"],
        "note": "NORMAL < 500 mm; WARNING ≥ 500 mm; CRITICAL ≥ min(0,15 × chiều sâu hầm, 2000 mm). "
                "Cần cargo_hold_depth_mm và water_sensor_full_scale_mm (đổi % chiết áp ra mm) do người cấu hình khai báo; "
                "hệ thống KHÔNG giả định kích thước hầm hàng.",
    },
    "temperature": {
        "unit": "°C", "basis": "AIR_IN_HOLD",
        "reference": ["Wang & Zhou (2023), Bulk Grain Cargo Hold Condensation Based on Computational Fluid Dynamics, "
                      "Applied Sciences, DOI: 10.3390/app132312878"],
        "note": "Ngưỡng kỹ thuật của prototype tham chiếu nghiên cứu hàng nông sản, KHÔNG phải quy định nhiệt độ bắt buộc của IMO. "
                "DHT22 đo nhiệt độ KHÔNG KHÍ trong hầm, không phải nhiệt độ khối hàng.",
    },
    "humidity": {
        "unit": "%RH", "basis": "AIR_IN_HOLD",
        "reference": ["IMO/ILO/UNECE CTU Code (2014)", "Food Science & Nutrition (2024), DOI: 10.1002/fsn3.4302"],
        "note": "Ngưỡng 90 % là ngưỡng rủi ro cao do nhóm đề xuất dựa trên nghiên cứu thực nghiệm, KHÔNG phải ngưỡng cảnh báo "
                "quốc tế bắt buộc. Đo độ ẩm tương đối của không khí trong hầm.",
    },
}

METRICS = ("WATER", "TEMPERATURE", "HUMIDITY")


class ConfigInvalid(ValueError):
    """Cấu hình ngưỡng/hầm hàng không hợp lệ (422)."""


@dataclass
class Effective:
    """Ngưỡng hiệu lực sau khi gộp mặc định + cấu hình, kèm danh sách trường còn thiếu/không hợp lệ."""
    water_warning_mm: float
    water_critical_mm: Optional[float]
    temp_warning: float
    temp_critical: float
    hum_warning: float
    hum_critical: float
    depth_mm: Optional[float]
    full_scale_mm: Optional[float]
    calibrated: bool
    vessel_type: Optional[str]
    cargo_type: Optional[str]
    config_version: int
    is_default_thresholds: bool
    missing: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def version_label(self) -> str:
        base = f"{PROFILE_KEY}@v{PROFILE_VERSION}"
        return base if self.config_version == 0 else f"{base}+cfg{self.config_version}"

    @property
    def water_configured(self) -> bool:
        return self.water_critical_mm is not None and self.full_scale_mm is not None and not self.errors


def water_critical_mm(depth_mm: float, fraction: float, cap_mm: float) -> float:
    """CRITICAL = min(fraction × chiều sâu hầm, cap)."""
    return min(fraction * depth_mm, cap_mm)


def _pair(name: str, w: float, c: float, lo: float, hi: float) -> None:
    if not (lo <= w <= hi and lo <= c <= hi):
        raise ConfigInvalid(f"{name}: ngưỡng ngoài khoảng cho phép {lo:g}..{hi:g}")
    if not c > w:
        raise ConfigInvalid(f"{name}: ngưỡng CRITICAL ({c:g}) phải lớn hơn ngưỡng WARNING ({w:g})")


def merge_thresholds(overrides: Optional[dict[str, Any]]) -> dict[str, dict[str, float]]:
    out = {k: dict(v) for k, v in DEFAULTS.items()}
    for group, vals in (overrides or {}).items():
        if group not in out:
            raise ConfigInvalid(f"Nhóm ngưỡng lạ: '{group}'")
        for k, v in (vals or {}).items():
            if k not in out[group]:
                raise ConfigInvalid(f"Tham số ngưỡng lạ: '{group}.{k}'")
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ConfigInvalid(f"'{group}.{k}' phải là số")
            out[group][k] = float(v)
    return out


def validate(depth_mm: Optional[float], full_scale_mm: Optional[float],
             overrides: Optional[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Kiểm tra cấu hình; ném ConfigInvalid nếu sai. Trả về ngưỡng đã gộp."""
    t = merge_thresholds(overrides)
    w = t["water"]
    if not w["warning_mm"] > 0:
        raise ConfigInvalid("water.warning_mm phải > 0")
    if not 0 < w["critical_fraction_of_depth"] <= 1:
        raise ConfigInvalid("water.critical_fraction_of_depth phải trong (0, 1]")
    if not w["critical_cap_mm"] > w["warning_mm"]:
        raise ConfigInvalid("water.critical_cap_mm phải lớn hơn water.warning_mm")
    if depth_mm is not None:
        if not 0 < depth_mm <= MAX_HOLD_DEPTH_MM:
            raise ConfigInvalid(f"cargo_hold_depth_mm phải trong (0, {MAX_HOLD_DEPTH_MM:.0f}] mm")
        crit = water_critical_mm(depth_mm, w["critical_fraction_of_depth"], w["critical_cap_mm"])
        if not crit > w["warning_mm"]:
            raise ConfigInvalid(
                f"Chiều sâu hầm {depth_mm:g} mm quá nhỏ: ngưỡng CRITICAL nước ({crit:g} mm) không cao hơn WARNING "
                f"({w['warning_mm']:g} mm). Cần chiều sâu > {w['warning_mm'] / w['critical_fraction_of_depth']:g} mm")
    if full_scale_mm is not None:
        if not full_scale_mm > 0:
            raise ConfigInvalid("water_sensor_full_scale_mm phải > 0")
        if depth_mm is not None and full_scale_mm > depth_mm:
            raise ConfigInvalid("water_sensor_full_scale_mm không được lớn hơn cargo_hold_depth_mm")
    _pair("temperature", t["temperature"]["warning"], t["temperature"]["critical"], *DHT22_TEMP_RANGE_C)
    _pair("humidity", t["humidity"]["warning"], t["humidity"]["critical"], 0.0, 100.0)
    return t


def resolve(cfg: Any) -> Effective:
    """Ngưỡng hiệu lực từ một dòng cấu hình (hoặc None = chưa cấu hình: chỉ dùng bộ mặc định, thiếu chiều sâu hầm)."""
    depth = getattr(cfg, "cargo_hold_depth_mm", None)
    scale = getattr(cfg, "water_sensor_full_scale_mm", None)
    overrides = getattr(cfg, "thresholds", None)
    errors: list[str] = []
    try:
        t = validate(depth, scale, overrides)
    except ConfigInvalid as e:      # dữ liệu cũ/hỏng: quay về mặc định nhưng BÁO LỖI, không im lặng
        errors.append(str(e))
        t = merge_thresholds(None)
        depth = scale = None
    missing = []
    if depth is None:
        missing.append("cargo_hold_depth_mm")
    if scale is None:
        missing.append("water_sensor_full_scale_mm")
    w = t["water"]
    crit = None if depth is None else water_critical_mm(depth, w["critical_fraction_of_depth"], w["critical_cap_mm"])
    return Effective(
        water_warning_mm=w["warning_mm"], water_critical_mm=crit,
        temp_warning=t["temperature"]["warning"], temp_critical=t["temperature"]["critical"],
        hum_warning=t["humidity"]["warning"], hum_critical=t["humidity"]["critical"],
        depth_mm=depth, full_scale_mm=scale, calibrated=bool(getattr(cfg, "sensor_calibrated", False)),
        vessel_type=getattr(cfg, "vessel_type", None), cargo_type=getattr(cfg, "cargo_type", None),
        config_version=int(getattr(cfg, "version", 0) or 0),
        is_default_thresholds=t == merge_thresholds(None), missing=missing, errors=errors)
