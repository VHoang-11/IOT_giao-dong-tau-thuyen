from __future__ import annotations

import numpy as np


def rad_per_minute_to_rad_per_second(values):
    """Đổi rate rad/min sang rad/s, giữ nguyên quy ước dấu."""
    return np.asarray(values, dtype=np.float64) / 60.0


def degree_per_second_to_rad_per_second(values):
    """Đổi degree/s sang rad/s; chỉ gọi khi ngữ nghĩa rate đã được xác nhận."""
    return np.deg2rad(np.asarray(values, dtype=np.float64))
