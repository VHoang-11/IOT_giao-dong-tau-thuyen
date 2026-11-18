from __future__ import annotations

import math

from .schemas import LABELS, LABEL_SOURCES, LABEL_STATUSES, REVIEW_STATUSES


def validate_label_record(record: dict) -> None:
    for key in ("dataset_source", "session_id", "segment_id", "window_start_seconds", "window_end_seconds",
                "label", "label_status", "label_source", "labeling_method", "rule_version", "review_status"):
        if key not in record:
            raise ValueError(f"Thiếu trường nhãn bắt buộc: {key}")
    if record["label"] not in LABELS or record["label_source"] not in LABEL_SOURCES:
        raise ValueError("Giá trị label/label_source không nằm trong schema.")
    if record["label_status"] not in LABEL_STATUSES or record["review_status"] not in REVIEW_STATUSES:
        raise ValueError("Giá trị label_status/review_status không hợp lệ.")
    if not math.isfinite(float(record["window_start_seconds"])) or not math.isfinite(float(record["window_end_seconds"])) or float(record["window_end_seconds"]) <= float(record["window_start_seconds"]):
        raise ValueError("window_end_seconds phải lớn hơn window_start_seconds.")
    evidence = record.get("evidence_reference")
    has_evidence = isinstance(evidence, str) and bool(evidence.strip())
    if record["label_status"] == "VERIFIED" and (record["label_source"] != "EXTERNAL_REFERENCE" or not has_evidence):
        raise ValueError("Không thể xác minh nhãn nếu thiếu external reference.")
    if record["label_status"] == "HUMAN_REVIEWED" and record["label_source"] != "HUMAN_REVIEW":
        raise ValueError("Nhãn human-reviewed phải có label_source HUMAN_REVIEW.")
    if record["label_status"] == "PROXY" and record["label_source"] != "PROXY_RULE":
        raise ValueError("Proxy label phải giữ nguồn PROXY_RULE.")
