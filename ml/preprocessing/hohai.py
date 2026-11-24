from __future__ import annotations

from pathlib import Path

import numpy as np
from openpyxl import load_workbook

from .schemas import RawSession

HOHAI_SAMPLING_HZ = 50.0


def load_sessions(raw_root: Path) -> list[RawSession]:
    path = raw_root / "hohai/6-DOF ship motions Data.xlsx"
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy workbook Hohai: {path}")
    workbook = load_workbook(path, read_only=True, data_only=True)
    sessions = []
    try:
        for sheet in workbook.worksheets:
            rows = sheet.iter_rows(values_only=True)
            headers = [str(value).strip() if value is not None else "" for value in next(rows, ())]
            required = ("Sway", "Surge", "Heave", "Roll", "Pitch", "Yaw")
            if tuple(headers) != required:
                raise ValueError(f"Schema sheet Hohai không khớp tại {sheet.title}: {headers}")
            values = []
            for row in rows:
                if not any(v is not None for v in row):
                    continue
                values.append([_num(row[i] if i < len(row) else None) for i in range(len(headers))])
            matrix = np.asarray(values, dtype=np.float64)
            if not len(matrix):
                continue
            n = len(matrix)
            signals = {"sway_m": matrix[:, 0], "surge_m": matrix[:, 1], "heave_m": matrix[:, 2],
                       "roll_deg": matrix[:, 3], "pitch_deg": matrix[:, 4], "yaw_deg": matrix[:, 5],
                       "gyro_x_rad_s": np.full(n, np.nan), "gyro_y_rad_s": np.full(n, np.nan)}
            times = np.arange(n, dtype=np.float64) / HOHAI_SAMPLING_HZ
            sessions.append(RawSession("hohai", _safe_id(sheet.title), f"{path}::{sheet.title}", times, signals,
                provenance={"raw_file": path.name, "raw_sheet": sheet.title, "original_sampling_hz": 50.0,
                    "target_sampling_hz": None, "unit_original": {"Roll": "degree", "Pitch": "degree",
                        "Yaw": "degree", "Sway": "m", "Surge": "m", "Heave": "m"},
                    "unit_conversions": {}, "timestamp_source": "INFERRED_FROM_SAMPLE_INDEX",
                    "measured_vs_derived": {"gyro_x_rad_s": "missing; không có gyro đo trực tiếp",
                        "gyro_y_rad_s": "missing; không có gyro đo trực tiếp"},
                    "axis_sign_confidence": "medium for documented DOF labels; mounting convention unknown"},
                warnings=["Thời gian tương đối được suy ra từ chỉ số mẫu ở 50 Hz; không thể phát hiện dropout giữa các mẫu.",
                          "Không có gyroscope đo trực tiếp; trường gyro giữ missing."] , original_row_count=n))
    finally:
        workbook.close()
    return sessions


def _num(value) -> float:
    try:
        number = float(value)
        return number if np.isfinite(number) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def _safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)
