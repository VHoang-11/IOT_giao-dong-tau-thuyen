from __future__ import annotations

from typing import Any

import math

from .provenance import json_flags, label_provenance


def _threshold(rule: dict, key: str) -> float:
    value = rule.get(key)
    if value is None or not math.isfinite(float(value)):
        raise ValueError(f"Quy tắc bật nhưng thiếu ngưỡng hữu hạn: {key}")
    return float(value)


def _source_rule(rule: dict, dataset: str) -> dict:
    if "by_dataset" in rule:
        if dataset not in rule["by_dataset"]:
            raise ValueError(f"Quy tắc chưa được cấu hình riêng cho dataset {dataset}.")
        return rule["by_dataset"][dataset]
    scope = rule.get("dataset_scope", [])
    if dataset not in scope:
        raise ValueError("Ngưỡng chung chỉ hợp lệ nếu dataset_scope liệt kê rõ nguồn áp dụng.")
    return rule


def classify_candidate(row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    settings = config["labeling"]
    rules = settings["rules"]
    dataset = str(row.get("dataset_source", ""))
    flags = {name: "NOT_EVALUATED" for name in ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH")}
    evidence: dict[str, str] = {}
    if settings["mode"] == "exploratory_proxy":
        high = rules["HIGH_ROLL"]
        if high.get("enabled"):
            source = _source_rule(high, dataset)
            threshold = _threshold(source, "roll_std_60_deg")
            if not source.get("evidence_reference"):
                raise ValueError("Quy tắc proxy cần evidence_reference độc lập và được ghi rõ.")
            flags["HIGH_ROLL"] = "CANDIDATE" if float(row["roll_std_60"]) >= threshold else "NOT_CANDIDATE"
            evidence["HIGH_ROLL"] = source["evidence_reference"]

        offset = rules["PERSISTENT_OFFSET"]
        if offset.get("enabled"):
            source = _source_rule(offset, dataset)
            angle = _threshold(source, "abs_roll_mean_180_deg")
            sign = _threshold(source, "dominant_sign_ratio_min")
            if not source.get("evidence_reference"):
                raise ValueError("Quy tắc proxy cần evidence_reference độc lập và được ghi rõ.")
            match = abs(float(row["roll_mean_180"])) >= angle and float(row["roll_dominant_sign_ratio_180"]) >= sign
            flags["PERSISTENT_OFFSET"] = "CANDIDATE" if match else "NOT_CANDIDATE"
            evidence["PERSISTENT_OFFSET"] = source["evidence_reference"]

        growth = rules["AMPLITUDE_GROWTH"]
        if growth.get("enabled"):
            source = _source_rule(growth, dataset)
            slope = _threshold(source, "roll_rms_slope_180_deg_per_min")
            r2 = _threshold(source, "trend_r2_min")
            if not source.get("evidence_reference"):
                raise ValueError("Quy tắc proxy cần evidence_reference độc lập và được ghi rõ.")
            match = float(row["roll_rms_slope_180"]) >= slope and float(row["roll_rms_trend_r2_180"]) >= r2
            flags["AMPLITUDE_GROWTH"] = "CANDIDATE" if match else "NOT_CANDIDATE"
            evidence["AMPLITUDE_GROWTH"] = source["evidence_reference"]

        normal = rules["NORMAL"]
        if normal.get("enabled"):
            source = _source_rule(normal, dataset)
            std_max = _threshold(source, "roll_std_60_max_deg")
            mean_max = _threshold(source, "abs_roll_mean_180_max_deg")
            if not source.get("evidence_reference"):
                raise ValueError("NORMAL cần tài liệu envelope vận hành được chấp nhận.")
            abnormalities = [name for name in ("HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH")
                             if flags[name] == "CANDIDATE"]
            match = float(row["roll_std_60"]) <= std_max and abs(float(row["roll_mean_180"])) <= mean_max
            flags["NORMAL"] = "CANDIDATE" if match and not abnormalities else "NOT_CANDIDATE"
            evidence["NORMAL"] = source["evidence_reference"]

    candidates = [name for name, value in flags.items() if value == "CANDIDATE"]
    ambiguity = None
    suggested = None
    label = "UNLABELED"
    if len(candidates) > 1:
        ambiguity = "NHIỀU phenotype ứng viên đồng thời; giữ nguyên toàn bộ cờ và cần người duyệt."
        label = "REVIEW_REQUIRED"
    elif len(candidates) == 1:
        suggested = candidates[0]
        label = suggested
    elif any(value != "NOT_EVALUATED" for value in flags.values()):
        # Các quy tắc đã chạy nhưng không có proxy dương tính không tạo nhãn NORMAL.
        label = "UNLABELED"

    if len(candidates) > 1 and settings.get("primary_class_policy") == "PRIORITY":
        priority = settings.get("primary_class_priority", [])
        selected = next((name for name in priority if name in candidates), None)
        if selected:
            suggested = selected
            label = selected
            ambiguity = "Nhiều phenotype cùng xuất hiện; lớp chính theo thứ tự ưu tiên cấu hình, các cờ vẫn được bảo toàn."

    chosen_reference = evidence.get(suggested) if suggested else None
    provenance = label_provenance(mode=settings["mode"], rule_version=settings["rule_version"],
                                  label=label, evidence_reference=chosen_reference,
                                  ambiguity_reason=ambiguity)
    return {**provenance, "review_status": "PENDING" if ambiguity or candidates else "NOT_REVIEWED",
            "ambiguity_reason": ambiguity, "phenotype_flags_json": json_flags(flags),
            "suggested_label": suggested}
