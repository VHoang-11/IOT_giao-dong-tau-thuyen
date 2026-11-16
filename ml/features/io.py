from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def load_config(path: Path) -> tuple[dict[str, Any], Path]:
    path = path.resolve()
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Cấu hình feature phải là YAML mapping.")
    repo_root = path.parents[2]
    for key in ("processed_root", "feature_root", "report_root", "preprocessing_config"):
        value = Path(payload["paths"][key])
        payload["paths"][key] = value if value.is_absolute() else repo_root / value
    settings = payload["features"]
    if settings["target_sampling_hz"] <= 0 or settings["window_stride_seconds"] <= 0:
        raise ValueError("Sampling Rate và window stride phải lớn hơn 0.")
    if not 0 < settings["minimum_valid_fraction"] <= 1:
        raise ValueError("minimum_valid_fraction phải thuộc (0,1].")
    return payload, repo_root


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def relative_path(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()
