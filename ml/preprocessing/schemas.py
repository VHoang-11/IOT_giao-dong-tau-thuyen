from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class RawSession:
    """Một phiên nguồn độc lập trước khi chuẩn hóa."""
    dataset_source: str
    session_id: str
    raw_reference: str
    time_seconds: np.ndarray
    signals: dict[str, np.ndarray]
    required_signals: tuple[str, ...] = ("roll_deg", "pitch_deg")
    provenance: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    original_row_count: int = 0


@dataclass
class ProcessedSegment:
    dataset_source: str
    session_id: str
    segment_id: str
    frame: pd.DataFrame
    provenance: dict[str, Any]
    quality: dict[str, Any]
    aligned: dict[str, dict[str, np.ndarray]]


def nullable_float_array(values: Any) -> np.ndarray:
    """Chuyển giá trị số thành float64; giá trị lỗi/non-finite thành NaN."""
    return pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=np.float64, na_value=np.nan)


def session_path(raw_root: Path, relative: str) -> Path:
    path = raw_root / relative
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy dữ liệu đầu vào: {path}")
    return path
