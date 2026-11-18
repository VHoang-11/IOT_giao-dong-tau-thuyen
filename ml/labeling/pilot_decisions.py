from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .agreement import inter_reviewer_agreement
from .pilot_schema import (EVIDENCE_CATEGORIES, PHENOTYPE_FLAGS, PILOT_IDENTITY,
                           PILOT_LABELS, derive_pilot_status, validate_pilot_annotation)
from .provenance import audit_event

DECISION_COLUMNS = ("review_sample_id", "reviewer_id", "reviewer_decision", "phenotype_flags_json",
                    "evidence_category", "evidence_reference", "reviewer_notes", "review_timestamp_utc",
                    "review_status", "ambiguity_reason")


def decision_template() -> pd.DataFrame:
    return pd.DataFrame(columns=DECISION_COLUMNS)


def validate_decision_ledger(decisions: pd.DataFrame, valid_sample_ids: set[str]) -> None:
    if missing := set(DECISION_COLUMNS) - set(decisions.columns):
        raise ValueError(f"Decision ledger thiếu cột: {sorted(missing)}")
    if decisions.duplicated(["review_sample_id", "reviewer_id"]).any():
        raise ValueError("Một reviewer chỉ được có một bản ghi cho mỗi review_sample_id.")
    unknown_ids = set(decisions.review_sample_id.astype(str)) - valid_sample_ids
    if unknown_ids:
        raise ValueError(f"Decision ledger chứa sample ID không thuộc pilot: {sorted(unknown_ids)[:5]}")
    for row in decisions.to_dict("records"):
        status = str(row.get("review_status") or "")
        decision = str(row.get("reviewer_decision") or "")
        reviewer = str(row.get("reviewer_id") or "").strip()
        if status not in {"PENDING", "ACCEPTED", "REJECTED", "NEEDS_DISCUSSION"}:
            raise ValueError("review_status trong decision ledger không hợp lệ.")
        if decision and decision not in PILOT_LABELS:
            raise ValueError("reviewer_decision trong decision ledger không hợp lệ.")
        if status == "PENDING" and decision:
            raise ValueError("PENDING không được mang reviewer decision.")
        if status != "PENDING" and (not reviewer or not decision or not str(row.get("review_timestamp_utc") or "").strip()):
            raise ValueError("Quyết định thực cần reviewer_id, reviewer_decision và timestamp.")
        if row.get("evidence_category") not in EVIDENCE_CATEGORIES:
            raise ValueError("evidence_category trong decision ledger không hợp lệ.")
        try:
            flags = json.loads(row["phenotype_flags_json"] or "{}")
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("phenotype_flags_json không phải JSON hợp lệ.") from exc
        if not isinstance(flags, dict) or set(flags) != set(PHENOTYPE_FLAGS):
            raise ValueError("phenotype_flags_json phải khai báo đủ phenotype flags.")
        if any(value not in (True, False, None) for value in flags.values()):
            raise ValueError("Phenotype flag chỉ nhận true/false/null.")
        if sum(value is True for value in flags.values()) > 1 and not str(row.get("ambiguity_reason") or "").strip():
            raise ValueError("Nhiều phenotype đồng thời cần ambiguity_reason.")
        category = row["evidence_category"]
        evidence_ref = str(row.get("evidence_reference") or "").strip()
        if category in {"VERIFIED_OPERATIONAL_HAZARD", "VERIFIED_NORMAL_ENVELOPE", "PROXY_RULE"} and status == "ACCEPTED" and not evidence_ref:
            raise ValueError("Bằng chứng verified/proxy cần evidence_reference.")
        if status == "ACCEPTED":
            if category == "VERIFIED_NORMAL_ENVELOPE" and decision != "NORMAL":
                raise ValueError("VERIFIED_NORMAL_ENVELOPE chỉ hỗ trợ quyết định NORMAL.")
            if category == "VERIFIED_OPERATIONAL_HAZARD" and decision not in {"HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH"}:
                raise ValueError("VERIFIED_OPERATIONAL_HAZARD cần một phenotype hazard được xác định.")
            if category == "OBSERVED_MOTION_PHENOTYPE" and decision not in PHENOTYPE_FLAGS:
                raise ValueError("OBSERVED_MOTION_PHENOTYPE chỉ hỗ trợ các phenotype Roll đã định nghĩa.")
            if category == "UNVERIFIED" and decision not in {"REVIEW_REQUIRED", "UNLABELED"}:
                raise ValueError("UNVERIFIED không đủ để xác nhận phenotype hoặc hazard.")
            if category == "PROXY_RULE" and decision not in {"NORMAL", *PHENOTYPE_FLAGS}:
                raise ValueError("PROXY_RULE cần decision thuộc một trong các class ứng viên.")


def build_decision_summary(decisions: pd.DataFrame, valid_sample_ids: set[str]) -> dict:
    validate_decision_ledger(decisions, valid_sample_ids)
    actual = decisions.loc[decisions.review_status.eq("ACCEPTED") & decisions.reviewer_decision.ne("")]
    agreement = inter_reviewer_agreement(decisions)
    return {"decision_records": int(len(decisions)), "accepted_decisions": int(len(actual)),
            "reviewer_count": int(actual.reviewer_id.nunique()), "class_counts": {label: int(actual.reviewer_decision.eq(label).sum())
                for label in PILOT_LABELS}, "agreement": agreement}


def materialize_decisions(forms: pd.DataFrame, decisions: pd.DataFrame) -> pd.DataFrame:
    """Ghép decision ledger với context mẫu; mỗi reviewer vẫn là một record riêng."""
    valid_ids = set(forms.review_sample_id.astype(str))
    validate_decision_ledger(decisions, valid_ids)
    base_by_id = forms.set_index("review_sample_id", drop=False).to_dict("index")
    materialized = []
    for decision in decisions.to_dict("records"):
        if decision["review_status"] == "PENDING":
            continue
        sample_id = str(decision["review_sample_id"])
        record = dict(base_by_id[sample_id])
        for key in ("evidence_category", "evidence_reference", "reviewer_id", "reviewer_decision",
                    "phenotype_flags_json", "reviewer_notes", "review_timestamp_utc", "review_status",
                    "ambiguity_reason"):
            record[key] = decision[key]
        materialized.append(derive_pilot_status(record))
    return pd.DataFrame(materialized, columns=forms.columns)


def load_decisions(path: Path, valid_sample_ids: set[str]) -> pd.DataFrame:
    frame = pd.read_csv(path, keep_default_na=False) if path.is_file() else decision_template()
    validate_decision_ledger(frame, valid_sample_ids)
    return frame


def append_annotation_revision(path: Path, previous: dict, replacement: dict,
                               reviewer_id: str, timestamp: str | None = None) -> dict:
    """Ghi một revision nối tiếp; không sửa/xóa các event đã tồn tại."""
    reviewer_id = reviewer_id.strip()
    if not reviewer_id:
        raise ValueError("Revision cần reviewer_id thật.")
    if any(str(previous.get(key)) != str(replacement.get(key)) for key in PILOT_IDENTITY):
        raise ValueError("Revision không được đổi danh tính sample/window.")
    if replacement.get("reviewer_id") != reviewer_id:
        raise ValueError("reviewer_id của revision phải khớp record mới.")
    validate_pilot_annotation(replacement)
    if replacement.get("review_status") == "PENDING":
        raise ValueError("Revision phải ghi lại một quyết định review đã xử lý.")
    event = audit_event(previous, replacement, reviewer_id, timestamp)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
    return event
