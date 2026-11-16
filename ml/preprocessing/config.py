from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: Path) -> dict[str, Any]:
    """Đọc YAML và chuẩn hóa các đường dẫn tương đối theo gốc repository."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Tệp cấu hình phải chứa một YAML mapping.")
    root = path.resolve().parents[2]
    for key in ("raw_root", "processed_root", "report_root"):
        value = Path(payload["paths"][key])
        payload["paths"][key] = value if value.is_absolute() else root / value
    settings = payload.get("preprocessing", {})
    if settings.get("target_sampling_hz", 0) <= 0:
        raise ValueError("target_sampling_hz phải lớn hơn 0.")
    if not 0 < settings.get("valid_fraction_threshold", 0) <= 1:
        raise ValueError("valid_fraction_threshold phải thuộc (0, 1].")
    return payload
