from __future__ import annotations

import json
import math

PILOT_LABELS = ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH",
                "REVIEW_REQUIRED", "UNLABELED")
PHENOTYPE_FLAGS = ("HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH")
EVIDENCE_CATEGORIES = ("OBSERVED_MOTION_PHENOTYPE", "VERIFIED_OPERATIONAL_HAZARD",
                       "VERIFIED_NORMAL_ENVELOPE", "PROXY_RULE", "UNVERIFIED")
PILOT_STATUS = ("UNLABELED", "HUMAN_REVIEWED", "VERIFIED", "PROXY", "REVIEW_REQUIRED")
PILOT_REVIEW_STATUS = ("PENDING", "ACCEPTED", "REJECTED", "NEEDS_DISCUSSION")

PILOT_COLUMNS = (
    "review_sample_id", "dataset_source", "session_id", "segment_id",
    "window_start_seconds", "window_end_seconds", "context_start_seconds",
    "context_end_seconds", "context_available_seconds", "context_coverage_fraction",
    "plot_path", "experiment_metadata_json", "experiment_metadata_reference",
    "quality_flags_json", "queue_suggested_label", "evidence_category",
    "evidence_reference", "reviewer_id", "reviewer_decision", "phenotype_flags_json",
    "reviewer_notes", "review_timestamp_utc", "review_status", "label_status",
    "label_source", "ambiguity_reason",
)

PILOT_IDENTITY = ("dataset_source", "session_id", "segment_id", "window_start_seconds", "window_end_seconds")
REVIEW_FORM_FIELDS = ("evidence_category", "evidence_reference", "reviewer_id", "reviewer_decision",
                      "phenotype_flags_json", "reviewer_notes", "review_timestamp_utc",
                      "review_status", "label_status", "label_source", "ambiguity_reason")


def empty_phenotype_flags() -> str:
    return json.dumps({name: None for name in PHENOTYPE_FLAGS}, sort_keys=True)


def validate_pilot_annotation(record: dict) -> None:
    required = set(PILOT_COLUMNS)
    missing = required - set(record)
    if missing:
        raise ValueError(f"Thiếu trường pilot bắt buộc: {sorted(missing)}")
    if record["evidence_category"] not in EVIDENCE_CATEGORIES:
        raise ValueError("evidence_category không hợp lệ.")
    if record["review_status"] not in PILOT_REVIEW_STATUS or record["label_status"] not in PILOT_STATUS:
        raise ValueError("Trạng thái annotation không hợp lệ.")
    if record["reviewer_decision"] not in (*PILOT_LABELS, ""):
        raise ValueError("reviewer_decision không thuộc taxonomy.")
    if not math.isfinite(float(record["window_start_seconds"])) or not math.isfinite(float(record["window_end_seconds"])):
        raise ValueError("Window timestamp phải là số hữu hạn.")
    if float(record["window_end_seconds"]) <= float(record["window_start_seconds"]):
        raise ValueError("window_end_seconds phải lớn hơn window_start_seconds.")
    if not 0.0 <= float(record["context_coverage_fraction"]) <= 1.0:
        raise ValueError("context_coverage_fraction phải nằm trong [0,1].")
    try:
        flags = json.loads(record["phenotype_flags_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("phenotype_flags_json phải là JSON object hợp lệ.") from exc
    if not isinstance(flags, dict) or set(flags) != set(PHENOTYPE_FLAGS):
        raise ValueError("phenotype_flags_json phải có đủ ba phenotype flags đã định nghĩa.")
    if any(value not in (True, False, None) for value in flags.values()):
        raise ValueError("Phenotype flags chỉ nhận true, false hoặc null khi chưa đánh giá.")
    selected = [name for name, enabled in flags.items() if enabled is True]
    if len(selected) > 1 and not str(record.get("ambiguity_reason") or "").strip():
        raise ValueError("Các phenotype chồng lấn cần ambiguity_reason; không được bỏ cờ.")
    reviewed = record["review_status"] in {"ACCEPTED", "REJECTED", "NEEDS_DISCUSSION"}
    if reviewed and (not str(record.get("reviewer_id") or "").strip()
                     or not str(record.get("review_timestamp_utc") or "").strip()
                     or not record.get("reviewer_decision")):
        raise ValueError("Review đã xử lý cần reviewer, quyết định và timestamp thật.")
    if record["review_status"] == "PENDING" and record.get("reviewer_decision"):
        raise ValueError("Review PENDING không được mang quyết định reviewer.")
    if record["label_status"] == "HUMAN_REVIEWED" and record["review_status"] != "ACCEPTED":
        raise ValueError("Không thể gán HUMAN_REVIEWED nếu reviewer chưa ACCEPTED quyết định.")
    if record["label_status"] == "HUMAN_REVIEWED" and record["label_source"] != "HUMAN_REVIEW":
        raise ValueError("HUMAN_REVIEWED phải có label_source HUMAN_REVIEW.")
    if record["label_status"] == "HUMAN_REVIEWED" and record["evidence_category"] != "OBSERVED_MOTION_PHENOTYPE":
        raise ValueError("HUMAN_REVIEWED chỉ biểu thị phenotype đã được người xem xác nhận.")
    if record["label_status"] == "VERIFIED":
        if record["evidence_category"] not in {"VERIFIED_OPERATIONAL_HAZARD", "VERIFIED_NORMAL_ENVELOPE"}:
            raise ValueError("VERIFIED cần evidence loại operational hazard hoặc normal envelope đã xác nhận.")
        if not str(record.get("evidence_reference") or "").strip() or record["label_source"] != "EXTERNAL_REFERENCE":
            raise ValueError("VERIFIED cần external evidence reference; nhận xét thị giác không đủ.")
    if record["evidence_category"] == "OBSERVED_MOTION_PHENOTYPE" and record["label_status"] == "VERIFIED":
        raise ValueError("Quan sát chuyển động không tự xác nhận hazard vận hành.")
    if record["evidence_category"] == "PROXY_RULE":
        rejected_proxy = record["review_status"] in {"REJECTED", "NEEDS_DISCUSSION"} \
            and record["label_status"] == "REVIEW_REQUIRED" and record["label_source"] == "HUMAN_REVIEW"
        if not rejected_proxy and (record["label_status"] != "PROXY" or record["label_source"] != "PROXY_RULE"):
            raise ValueError("Nhãn theo proxy phải giữ status/source PROXY.")
        if not str(record.get("evidence_reference") or "").strip():
            raise ValueError("Proxy cần evidence_reference đến rule/config đã dùng.")
    if record["reviewer_decision"] == "NORMAL" and record["label_status"] == "HUMAN_REVIEWED":
        if record["evidence_category"] != "VERIFIED_NORMAL_ENVELOPE":
            raise ValueError("NORMAL cần operating envelope dương tính được xác nhận, không chỉ quan sát không bất thường.")


def derive_pilot_status(record: dict) -> dict:
    """Suy status machine-readable từ evidence đã khai báo; không tạo quyết định reviewer."""
    output = dict(record)
    if output["review_status"] == "PENDING":
        if output["evidence_category"] == "PROXY_RULE":
            output["label_status"], output["label_source"] = "PROXY", "PROXY_RULE"
        else:
            output["label_status"], output["label_source"] = "UNLABELED", "UNKNOWN"
    elif output["review_status"] in {"REJECTED", "NEEDS_DISCUSSION"}:
        output["label_status"], output["label_source"] = "REVIEW_REQUIRED", "HUMAN_REVIEW"
    else:
        category = output["evidence_category"]
        decision = output["reviewer_decision"]
        if category == "VERIFIED_NORMAL_ENVELOPE":
            if decision != "NORMAL":
                raise ValueError("Verified normal envelope chỉ hỗ trợ quyết định NORMAL.")
            output["label_status"], output["label_source"] = "VERIFIED", "EXTERNAL_REFERENCE"
        elif category == "VERIFIED_OPERATIONAL_HAZARD":
            if decision not in {"HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH"}:
                raise ValueError("Verified hazard cần phenotype hazard được xác định.")
            output["label_status"], output["label_source"] = "VERIFIED", "EXTERNAL_REFERENCE"
        elif category == "OBSERVED_MOTION_PHENOTYPE":
            if decision in {"NORMAL", "REVIEW_REQUIRED", "UNLABELED"}:
                raise ValueError("Quan sát chuyển động không đủ để kết luận NORMAL/hazard; dùng category phù hợp.")
            output["label_status"], output["label_source"] = "HUMAN_REVIEWED", "HUMAN_REVIEW"
        elif category == "PROXY_RULE":
            output["label_status"], output["label_source"] = "PROXY", "PROXY_RULE"
        else:
            if decision not in {"REVIEW_REQUIRED", "UNLABELED"}:
                raise ValueError("Evidence UNVERIFIED không đủ để xác nhận phenotype hoặc hazard.")
            output["label_status"], output["label_source"] = decision, "HUMAN_REVIEW"
    validate_pilot_annotation(output)
    return output
