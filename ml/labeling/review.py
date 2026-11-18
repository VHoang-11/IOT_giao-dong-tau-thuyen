from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .schemas import LABELS
from .validation import validate_label_record
from .provenance import audit_event

REVIEW_COLUMNS = ("dataset", "session", "segment", "window_start", "window_end", "suggested_label",
                  "queue_stratum", "evidence", "reviewer_decision", "reviewer_notes", "review_timestamp", "review_status")


def build_review_queue(windows: dict[str, pd.DataFrame], per_session: int = 4,
                       candidate_tables: dict[str, pd.DataFrame] | None = None,
                       labeling_config: dict | None = None) -> pd.DataFrame:
    chunks = []
    for dataset, frame in windows.items():
        queue_frame = frame.copy()
        if candidate_tables and dataset in candidate_tables:
            identity = ["dataset_source", "session_id", "segment_id", "window_start_seconds", "window_end_seconds"]
            labels = candidate_tables[dataset][[*identity, "label", "label_status", "ambiguity_reason"]]
            queue_frame = queue_frame.merge(labels, on=identity, validate="one_to_one")
            queue_frame["queue_stratum"] = "UNLABELED"
            queue_frame.loc[queue_frame.label_status.eq("PROXY"), "queue_stratum"] = "CLEAR_PROXY_CANDIDATE"
            queue_frame.loc[queue_frame.label.eq("REVIEW_REQUIRED"), "queue_stratum"] = "CONFLICTING_PHENOTYPES"
            margin = labeling_config.get("review_borderline_relative_margin") if labeling_config else None
            if margin is not None:
                margin = float(margin)
                if not 0.0 <= margin <= 1.0:
                    raise ValueError("review_borderline_relative_margin phải nằm trong [0,1].")
                rules = labeling_config.get("rules", {})
                def is_near(row: pd.Series) -> bool:
                    specs = {
                        "HIGH_ROLL": [("roll_std_60", "roll_std_60_deg")],
                        "PERSISTENT_OFFSET": [("roll_mean_180", "abs_roll_mean_180_deg"),
                                               ("roll_dominant_sign_ratio_180", "dominant_sign_ratio_min")],
                        "AMPLITUDE_GROWTH": [("roll_rms_slope_180", "roll_rms_slope_180_deg_per_min"),
                                             ("roll_rms_trend_r2_180", "trend_r2_min")],
                        "NORMAL": [("roll_std_60", "roll_std_60_max_deg"),
                                   ("roll_mean_180", "abs_roll_mean_180_max_deg")],
                    }
                    for label, measurements in specs.items():
                        rule = rules.get(label, {})
                        if not rule.get("enabled"):
                            continue
                        source = rule.get("by_dataset", {}).get(dataset, rule)
                        for column, threshold_key in measurements:
                            threshold = source.get(threshold_key)
                            value = row.get(column)
                            if threshold is None or value is None or pd.isna(value):
                                continue
                            threshold = float(threshold)
                            value = abs(float(value)) if "abs_" in threshold_key else float(value)
                            if abs(value - threshold) <= margin * max(abs(threshold), 1e-12):
                                return True
                    return False
                near = queue_frame.apply(is_near, axis=1)
                queue_frame.loc[near & ~queue_frame.label.eq("REVIEW_REQUIRED"), "queue_stratum"] = "BORDERLINE_CASE"
            queue_frame = queue_frame.loc[~queue_frame.label_status.isin(("VERIFIED", "HUMAN_REVIEWED"))]
        else:
            queue_frame["label"] = "UNLABELED"
            queue_frame["queue_stratum"] = "UNLABELED"
        for (session, stratum), group in queue_frame.groupby(["session_id", "queue_stratum"], sort=True):
            group = group.sort_values("window_end_seconds", kind="stable")
            indexes = np.unique(np.linspace(0, len(group) - 1, min(per_session, len(group)), dtype=int))
            for _, row in group.iloc[indexes].iterrows():
                chunks.append({"dataset": dataset, "session": str(session), "segment": str(row.segment_id),
                    "window_start": float(row.window_start_seconds), "window_end": float(row.window_end_seconds),
                    "suggested_label": str(row.label), "queue_stratum": str(stratum),
                    "evidence": "Chọn mẫu thời gian phân bố đều trong session và tầng nhãn khả dụng; chưa có ngưỡng/nhãn tham chiếu.",
                    "reviewer_decision": "", "reviewer_notes": "", "review_timestamp": "", "review_status": "PENDING"})
    return pd.DataFrame(chunks, columns=REVIEW_COLUMNS)


def validate_review_decision(record: dict) -> None:
    if record.get("reviewer_decision") not in (*LABELS, ""):
        raise ValueError("Quyết định reviewer không hợp lệ.")
    if record.get("review_status") not in {"PENDING", "ACCEPTED", "REJECTED", "NEEDS_DISCUSSION"}:
        raise ValueError("review_status không hợp lệ.")
    if record.get("review_status") == "ACCEPTED" and (not record.get("reviewer_decision") or not record.get("review_timestamp")):
        raise ValueError("Quyết định ACCEPTED cần label và review_timestamp.")


def promote_review_record(record: dict, reviewer_id: str) -> dict:
    validate_review_decision(record)
    if record["review_status"] != "ACCEPTED":
        raise ValueError("Chỉ áp dụng review decision đã ACCEPTED.")
    result = {"dataset_source": record["dataset"], "session_id": record["session"],
              "segment_id": record["segment"], "window_start_seconds": record["window_start"],
              "window_end_seconds": record["window_end"], "label": record["reviewer_decision"],
              "label_status": "HUMAN_REVIEWED", "label_source": "HUMAN_REVIEW",
              "labeling_method": "manual_review", "rule_version": "human_review_v1",
              "evidence_reference": f"reviewer:{reviewer_id}", "review_status": "ACCEPTED",
              "ambiguity_reason": record.get("reviewer_notes") or None, "quality_flags": "[]",
              "phenotype_flags_json": "{}", "suggested_label": record.get("suggested_label")}
    validate_label_record(result)
    return result


def append_review_event(path: Path, old_record: dict, new_record: dict, reviewer_id: str,
                        timestamp: str | None = None) -> dict:
    """Append event to JSONL without rewriting prior human-review history."""
    if not reviewer_id.strip():
        raise ValueError("reviewer_id không được để trống.")
    validate_label_record(old_record)
    validate_label_record(new_record)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = audit_event(old_record, new_record, reviewer_id, timestamp)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event
