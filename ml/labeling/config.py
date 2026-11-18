from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: Path) -> tuple[dict[str, Any], Path]:
    path = path.resolve()
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Cấu hình labeling phải là YAML mapping.")
    root = path.parents[2]
    for key, value in config["paths"].items():
        resolved = Path(value)
        config["paths"][key] = resolved if resolved.is_absolute() else root / resolved
    external_path = config["labeling"].get("external_annotations_path")
    if external_path:
        external_path = Path(external_path)
        config["labeling"]["external_annotations_path"] = external_path if external_path.is_absolute() else root / external_path
    mode = config["labeling"]["mode"]
    if mode not in {"feasibility", "exploratory_proxy"}:
        raise ValueError("mode chỉ nhận feasibility hoặc exploratory_proxy.")
    if config["labeling"]["labeling_window_seconds"] != 180:
        raise ValueError("Bản hiện tại căn nhãn theo endpoint đủ cửa sổ 180 giây.")
    if config["labeling"].get("primary_class_policy") not in {"REVIEW_REQUIRED", "PRIORITY"}:
        raise ValueError("primary_class_policy chỉ nhận REVIEW_REQUIRED hoặc PRIORITY.")
    margin = config["labeling"].get("review_borderline_relative_margin")
    if margin is not None and not 0.0 <= float(margin) <= 1.0:
        raise ValueError("review_borderline_relative_margin phải nằm trong [0,1].")
    return config, root
