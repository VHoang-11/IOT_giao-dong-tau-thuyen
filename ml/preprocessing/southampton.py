from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook

from .schemas import RawSession


def load_sessions(raw_root: Path) -> list[RawSession]:
    folder = raw_root / "southampton/Raw Data_IMU"
    if not folder.exists():
        raise FileNotFoundError(f"Không tìm thấy thư mục Southampton IMU: {folder}")
    files = sorted(folder.glob("*.csv"), key=lambda p: int(re.search(r"Run(\d+)", p.name).group(1)))
    sessions = []
    wave_metadata = _wave_metadata(raw_root / "southampton/Readme/KCS Test Plan June 2023.xlsx")
    for path in files:
        frame = pd.read_csv(path, skiprows=[1])  # bỏ hàng đơn vị; tên cột vẫn được giữ nguyên
        expected = ["Time Stamp", "Heave", "Roll", "Pitch", "Yaw", "Accelerometer X",
                    "Accelerometer Y", "Accelerometer Z", "Delta Angle X", "Delta Angle Y", "Delta Angle Z"]
        if list(frame.columns) != expected:
            raise ValueError(f"Schema CSV Southampton không khớp tại {path.name}: {list(frame.columns)}")
        numbers = {name: pd.to_numeric(frame[name], errors="coerce").to_numpy(dtype=np.float64) for name in expected}
        times = numbers["Time Stamp"]
        n = len(frame)
        run_id = int(re.search(r"Run(\d+)", path.name).group(1))
        signals = {"heave_m": numbers["Heave"], "roll_deg": numbers["Roll"],
            "pitch_deg": numbers["Pitch"], "yaw_deg": numbers["Yaw"],
            "accel_x_m_s2": numbers["Accelerometer X"], "accel_y_m_s2": numbers["Accelerometer Y"],
            "accel_z_m_s2": numbers["Accelerometer Z"],
            "delta_angle_x_deg_s_raw": numbers["Delta Angle X"],
            "delta_angle_y_deg_s_raw": numbers["Delta Angle Y"],
            "delta_angle_z_deg_s_raw": numbers["Delta Angle Z"],
            # Chưa map sang gyro vì semantical meaning của "Delta Angle" chưa xác nhận.
            "gyro_x_rad_s": np.full(n, np.nan), "gyro_y_rad_s": np.full(n, np.nan)}
        sessions.append(RawSession("southampton", f"southampton_run_{run_id:02d}", str(path), times, signals,
            provenance={"raw_file": path.name, "raw_run_id": run_id, "original_sampling_hz": None,
                "unit_original": {"Time Stamp": "s", "Roll": "degree", "Pitch": "degree",
                    "Accelerometer X/Y/Z": "m/s^2", "Delta Angle X/Y/Z": "degree/s per CSV unit row"},
                "unit_conversions": {}, "timestamp_source": "Time Stamp column, seconds; relative time is reset per run",
                "measured_vs_derived": {"Delta Angle X/Y/Z": "preserved raw rate-like columns; not mapped to canonical gyro pending semantics confirmation",
                    "gyro_x_rad_s": "missing", "gyro_y_rad_s": "missing"},
                "axis_sign_confidence": "low for rate mapping; angle axes preserved as named",
                "wave_condition_test_plan_provenance": wave_metadata.get(run_id, [])},
            warnings=["Delta Angle unit row states degree/s, but physical interpretation/body-axis mapping is not verified; canonical gyro fields remain missing."] ,
            original_row_count=n))
    return sessions


def _wave_metadata(path: Path) -> dict[int, list[dict]]:
    """Đọc điều kiện sóng từ Test Plan chỉ làm provenance, không làm feature/label."""
    if not path.exists():
        return {}
    workbook = load_workbook(path, read_only=True, data_only=True)
    result: dict[int, list[dict]] = {}
    try:
        sheet = workbook[workbook.sheetnames[0]]
        rows = sheet.iter_rows(values_only=True)
        headers = [str(x).strip() if x is not None else "" for x in next(rows, ())]
        indexes = {name: i for i, name in enumerate(headers) if name}
        current_run = None
        for row in rows:
            value = row[indexes["Run Number"]] if indexes.get("Run Number") is not None and indexes["Run Number"] < len(row) else None
            if value is not None:
                try: current_run = int(value)
                except (TypeError, ValueError): pass
            if current_run is None:
                continue
            def get(name):
                i = indexes.get(name)
                return row[i] if i is not None and i < len(row) else None
            frequency, amplitude = get("Wave frequency, Hz"), get("Wave amplitude, m")
            if isinstance(frequency, (int, float)) or isinstance(amplitude, (int, float)):
                result.setdefault(current_run, []).append({"run_id": get("Run ID"),
                    "test_type": get("Type"), "wave_frequency_hz": frequency,
                    "wave_amplitude_m": amplitude, "provenance_only": True})
    finally:
        workbook.close()
    return result
