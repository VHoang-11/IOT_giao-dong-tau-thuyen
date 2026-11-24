from __future__ import annotations

import json
from itertools import combinations

import pandas as pd


def _cohen_kappa(left: list[str], right: list[str]) -> float | None:
    if not left:
        return None
    labels = sorted(set(left) | set(right))
    observed = sum(a == b for a, b in zip(left, right)) / len(left)
    left_rate = {label: left.count(label) / len(left) for label in labels}
    right_rate = {label: right.count(label) / len(right) for label in labels}
    expected = sum(left_rate[label] * right_rate[label] for label in labels)
    return None if abs(1.0 - expected) < 1e-12 else (observed - expected) / (1.0 - expected)


def inter_reviewer_agreement(decisions: pd.DataFrame) -> dict:
    required = {"review_sample_id", "reviewer_id", "reviewer_decision", "review_status", "phenotype_flags_json"}
    if missing := required - set(decisions.columns):
        raise ValueError(f"Decision ledger thiếu cột: {sorted(missing)}")
    accepted = decisions.loc[decisions.review_status.eq("ACCEPTED") & decisions.reviewer_decision.fillna("").ne("")].copy()
    reviewers = sorted(accepted.reviewer_id.dropna().astype(str).unique())
    pairs = []
    for left_reviewer, right_reviewer in combinations(reviewers, 2):
        left = accepted.loc[accepted.reviewer_id.eq(left_reviewer)].set_index("review_sample_id")
        right = accepted.loc[accepted.reviewer_id.eq(right_reviewer)].set_index("review_sample_id")
        common = left.index.intersection(right.index)
        if not len(common):
            continue
        left_labels = left.loc[common, "reviewer_decision"].astype(str).tolist()
        right_labels = right.loc[common, "reviewer_decision"].astype(str).tolist()
        flags = {}
        for phenotype in ("HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH"):
            lvalues, rvalues = [], []
            for sample_id in common:
                lvalues.append(json.loads(left.loc[sample_id, "phenotype_flags_json"]).get(phenotype))
                rvalues.append(json.loads(right.loc[sample_id, "phenotype_flags_json"]).get(phenotype))
            scored = [(a, b) for a, b in zip(lvalues, rvalues) if a is not None and b is not None]
            flags[phenotype] = {"paired_decisions": len(scored),
                "exact_agreement": sum(a == b for a, b in scored) / len(scored) if scored else None}
        pairs.append({"reviewers": [left_reviewer, right_reviewer], "overlapping_samples": int(len(common)),
                      "exact_agreement": sum(a == b for a, b in zip(left_labels, right_labels)) / len(common),
                      "cohen_kappa": _cohen_kappa(left_labels, right_labels), "phenotype_flag_agreement": flags})
    if not pairs:
        return {"status": "NOT_CALCULATED", "reason_vi": "Chưa có ít nhất hai reviewer với quyết định ACCEPTED trên cùng sample.",
                "reviewer_count": len(reviewers), "pairwise_results": []}
    return {"status": "CALCULATED_ON_PAIRED_HUMAN_DECISIONS", "reviewer_count": len(reviewers),
            "pairwise_results": pairs,
            "limitation_vi": "Kappa/đồng thuận chỉ mô tả sự thống nhất giữa reviewer trên các sample chung; không chứng minh nhãn là hazard ground truth."}
