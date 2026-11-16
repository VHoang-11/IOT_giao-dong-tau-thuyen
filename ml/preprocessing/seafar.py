from __future__ import annotations

from pathlib import Path

import numpy as np

from .common import iter_json_records
from .schemas import RawSession
from .units import rad_per_minute_to_rad_per_second


def load_sessions(raw_root: Path) -> list[RawSession]:
    path = raw_root / "seafar/cleaned_imu_gps_data.json"
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy dữ liệu Seafar: {path}")
    fields = ("roll_degrees", "pitch_degrees", "roll_rate_rad_min", "pitch_rate_rad_min",
              "yaw_degrees", "accel_x_ms2", "accel_y_ms2", "accel_z_ms2", "heading_degrees",
              "lat_degrees", "lon_degrees", "sog_kph")
    columns = {name: [] for name in fields}
    timestamps = []
    for row in iter_json_records(path):
        timestamps.append(_number(row.get("datetime")) / 1000.0)
        for name in fields:
            columns[name].append(_number(row.get(name)))
    raw = {name: np.asarray(values, dtype=np.float64) for name, values in columns.items()}
    times = np.asarray(timestamps, dtype=np.float64)
    signals = {
        "roll_deg": raw["roll_degrees"], "pitch_deg": raw["pitch_degrees"],
        # Tên cột nguồn khai báo rad/min; giữ nguyên dấu và ghi rõ đây là rate-reported.
        "gyro_x_rad_s": rad_per_minute_to_rad_per_second(raw["roll_rate_rad_min"]),
        "gyro_y_rad_s": rad_per_minute_to_rad_per_second(raw["pitch_rate_rad_min"]),
        "yaw_deg": raw["yaw_degrees"], "accel_x_m_s2": raw["accel_x_ms2"],
        "accel_y_m_s2": raw["accel_y_ms2"], "accel_z_m_s2": raw["accel_z_ms2"],
        "heading_deg": raw["heading_degrees"], "latitude_deg": raw["lat_degrees"],
        "longitude_deg": raw["lon_degrees"], "speed_over_ground_kph": raw["sog_kph"],
    }
    warnings = ["Các trường rate có tên đơn vị rad/min; chưa tìm thấy tài liệu cảm biến xác nhận nguồn phần cứng, trục và quy ước dấu.",
                "Giữ nguyên dấu; ánh xạ roll/pitch rate sang trục x/y chỉ là ánh xạ theo tên trường."]
    return [RawSession("seafar", "seafar_session_001", str(path), times, signals,
        provenance={"timestamp_source": "datetime Unix epoch milliseconds",
            "original_sampling_hz": None, "unit_original": {"roll_deg": "degree", "pitch_deg": "degree",
                "roll_rate_rad_min": "rad/min (source field name)", "acceleration": "field name suffix ms2"},
            "unit_conversions": {"gyro_x_rad_s": "roll_rate_rad_min / 60; sign unchanged",
                "gyro_y_rad_s": "pitch_rate_rad_min / 60; sign unchanged"},
            "signal_measurement": {"gyro_x_rad_s": "direct rate-reported field; hardware gyro lineage unverified",
                "gyro_y_rad_s": "direct rate-reported field; hardware gyro lineage unverified"},
            "axis_sign_confidence": "low; field-name mapping only", "duplicate_policy": "deferred_to_shared_pipeline_policy"},
        warnings=warnings, original_row_count=len(times))]


def _number(value) -> float:
    try:
        result = float(value)
        return result if np.isfinite(result) else float("nan")
    except (TypeError, ValueError):
        return float("nan")
