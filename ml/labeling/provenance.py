from __future__ import annotations

import json
from datetime import datetime, timezone


def label_provenance(*, mode: str, rule_version: str, label: str, evidence_reference: str | None,
                     ambiguity_reason: str | None) -> dict:
    if label in {"NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH"}:
        if not evidence_reference:
            raise ValueError("Nhãn ứng viên phải có evidence_reference đã cấu hình.")
        return {"label": label, "label_status": "PROXY", "label_source": "PROXY_RULE",
                "labeling_method": mode, "rule_version": rule_version,
                "evidence_reference": evidence_reference}
    return {"label": label, "label_status": "REVIEW_REQUIRED" if label == "REVIEW_REQUIRED" else "UNLABELED",
            "label_source": "UNKNOWN", "labeling_method": mode, "rule_version": rule_version,
            "evidence_reference": evidence_reference}


def json_flags(flags: dict) -> str:
    return json.dumps(flags, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def audit_event(old_record: dict, new_record: dict, reviewer_id: str, timestamp: str | None = None) -> dict:
    return {"event_timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "reviewer_id": reviewer_id, "previous": old_record, "replacement": new_record}
