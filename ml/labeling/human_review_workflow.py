from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import fcntl
from io import BytesIO
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import pandas as pd

from .agreement import inter_reviewer_agreement
from .pilot_decisions import (ANNOTATION_SCHEMA_VERSION, DECISION_COLUMNS, decision_template,
                              materialize_decisions, validate_decision_ledger)
from .pilot_schema import PHENOTYPE_FLAGS, derive_pilot_status, validate_pilot_annotation
from .provenance import audit_event

INITIAL_BATCH_NAME = "pilot_29"
EXTENDED_BATCH_NAME = "extended_63"
ANGLE_FEATURES = (
    "roll_rms_60", "roll_std_60", "roll_mean_60", "roll_peak_to_peak_60",
    "roll_abs_p95_60", "roll_abs_max_60", "roll_iqr_60", "roll_diff_rms_60",
    "roll_mean_180", "roll_median_180", "roll_mean_abs_180", "roll_dominant_sign_ratio_180",
    "roll_segment_mean_std_180", "roll_mean_shift_180", "roll_rms_early_60", "roll_rms_late_60",
    "roll_rms_ratio_180", "roll_rms_slope_180", "roll_rms_trend_r2_180", "roll_p95_trend_slope_180",
    "pitch_rms_60", "pitch_std_60", "pitch_peak_to_peak_60",
)
BATCH_COLUMNS = ("review_id", "batch_name", "selection_reason")


def _repo_path(repo_root: Path, value: str | Path) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else repo_root / candidate


def load_pilot_forms(repo_root: Path, forms_path: Path | None = None) -> pd.DataFrame:
    path = forms_path or repo_root / "ml/data/labels/annotation_pilot/annotation_pilot.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy form pilot: {path}")
    forms = pd.read_csv(path, keep_default_na=False)
    required = {"review_sample_id", "dataset_source", "session_id", "segment_id",
                "window_start_seconds", "window_end_seconds", "plot_path", "quality_flags_json"}
    if missing := required - set(forms.columns):
        raise ValueError(f"Form pilot thiếu cột: {sorted(missing)}")
    if forms.review_sample_id.duplicated().any():
        raise ValueError("review_sample_id trong form pilot phải duy nhất.")
    return forms


def build_review_batches(forms: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tạo pilot 29 mẫu và batch mở rộng 63 Hohai theo quy tắc deterministic."""
    if forms.review_sample_id.duplicated().any():
        raise ValueError("review_sample_id phải duy nhất trước khi lập batch.")
    chosen: dict[str, str] = {}
    seafar = forms.loc[forms.dataset_source.eq("seafar")]
    southampton = forms.loc[forms.dataset_source.eq("southampton")]
    for row in pd.concat([seafar, southampton]).itertuples(index=False):
        chosen[row.review_sample_id] = "Giữ toàn bộ mẫu Seafar và Southampton theo phạm vi pilot đã định."
    hohai = forms.loc[forms.dataset_source.eq("hohai")]
    for session, group in hohai.groupby("session_id", sort=True):
        ordered = group.sort_values(["window_end_seconds", "window_start_seconds", "review_sample_id"], kind="stable")
        median_index = (len(ordered) - 1) // 2
        selected = ordered.iloc[median_index]
        chosen[selected.review_sample_id] = (
            f"Đại diện session Hohai `{session}`: chọn cửa sổ ở median temporal rank "
            f"({median_index + 1}/{len(ordered)} sau sắp xếp endpoint tăng dần)."
        )
    initial = forms.loc[forms.review_sample_id.isin(chosen)].copy()
    initial["review_id"] = initial.review_sample_id
    initial["annotation_schema_version"] = ANNOTATION_SCHEMA_VERSION
    initial["batch_name"] = INITIAL_BATCH_NAME
    initial["selection_reason"] = initial.review_sample_id.map(chosen)
    initial = initial.sort_values(["dataset_source", "session_id", "window_end_seconds", "review_id"], kind="stable")
    extended = forms.loc[forms.dataset_source.eq("hohai") & ~forms.review_sample_id.isin(chosen)].copy()
    extended["review_id"] = extended.review_sample_id
    extended["annotation_schema_version"] = ANNOTATION_SCHEMA_VERSION
    extended["batch_name"] = EXTENDED_BATCH_NAME
    extended["selection_reason"] = "Mẫu Hohai còn lại sau khi chọn một cửa sổ đại diện cho mỗi session."
    extended = extended.sort_values(["session_id", "window_end_seconds", "review_id"], kind="stable")
    if len(initial) != 29 or len(extended) != 63:
        raise ValueError(f"Batch không đúng quy mô yêu cầu: pilot={len(initial)}, extended={len(extended)}.")
    if initial.session_id.nunique() != 23:
        raise ValueError("Pilot batch phải phủ đủ 23 session đóng góp.")
    if set(initial.review_id) & set(extended.review_id):
        raise ValueError("Pilot và extended batch bị trùng review_id.")
    if set(initial.review_id) | set(extended.review_id) != set(forms.review_sample_id):
        raise ValueError("Hai batch phải phân hoạch đầy đủ 92 record mà không làm thay đổi queue.")
    return initial.reset_index(drop=True), extended.reset_index(drop=True)


def write_review_batches(repo_root: Path, forms: pd.DataFrame | None = None,
                         output_dir: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    forms = forms if forms is not None else load_pilot_forms(repo_root)
    initial, extended = build_review_batches(forms)
    output_dir = output_dir or repo_root / "ml/data/labels/annotation_pilot/batches"
    output_dir.mkdir(parents=True, exist_ok=True)
    initial.to_csv(output_dir / "pilot_29.csv", index=False)
    extended.to_csv(output_dir / "extended_63.csv", index=False)
    return initial, extended


def load_feature_review(repo_root: Path, form_record: dict) -> pd.DataFrame:
    dataset = str(form_record["dataset_source"])
    base = repo_root / "ml/data/features" / dataset
    values_path, metadata_path = base / "feature_values.parquet", base / "feature_metadata.parquet"
    if not values_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(f"Thiếu feature artifact để review: {dataset}")
    metadata = pd.read_parquet(metadata_path)
    mask = (metadata.session_id.astype(str).eq(str(form_record["session_id"]))
            & metadata.segment_id.astype(str).eq(str(form_record["segment_id"]))
            & ((pd.to_numeric(metadata.window_end_seconds) - float(form_record["window_end_seconds"])).abs() <= 1e-6))
    matched = metadata.loc[mask]
    if len(matched) != 1:
        raise ValueError("Không khớp duy nhất feature row theo dataset/session/segment/window endpoint.")
    window_id = matched.iloc[0].window_id
    values = pd.read_parquet(values_path)
    selected = values.loc[values.window_id.astype(str).eq(str(window_id))]
    if len(selected) != 1:
        raise ValueError("Không tìm thấy duy nhất feature values theo window_id.")
    validity = json.loads(matched.iloc[0].validity_json)
    row = selected.iloc[0]
    records = []
    for feature in ANGLE_FEATURES:
        detail = validity.get(feature, {})
        value = row.get(feature)
        records.append({"Đặc trưng": feature, "Giá trị": None if pd.isna(value) else float(value),
                        "Trạng thái": detail.get("status", "KHÔNG_CÓ_METADATA"),
                        "Lý do": detail.get("reason", "")})
    return pd.DataFrame(records)


def load_review_plot(repo_root: Path, form_record: dict) -> bytes:
    """Nạp và kiểm tra PNG trước khi giao nội dung ảnh cho giao diện review."""
    root = repo_root.resolve()
    raw_path = str(form_record.get("plot_path", "")).strip()
    if not raw_path:
        raise ValueError("Thiếu plot_path cho record review.")
    relative_path = Path(raw_path)
    if relative_path.is_absolute():
        raise ValueError("plot_path phải là đường dẫn tương đối trong repository.")
    plot_path = (root / relative_path).resolve()
    if root not in plot_path.parents:
        raise ValueError("plot_path nằm ngoài repository.")
    if not plot_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy signal plot: {relative_path}")
    if plot_path.suffix.lower() != ".png":
        raise ValueError(f"Signal plot phải là PNG: {relative_path}")

    content = plot_path.read_bytes()
    try:
        from PIL import Image

        with Image.open(BytesIO(content)) as image:
            if image.format != "PNG" or image.width < 2 or image.height < 2:
                raise ValueError("Signal plot PNG không có kích thước hợp lệ.")
            image.verify()
    except (OSError, SyntaxError) as exc:
        raise ValueError(f"Signal plot hỏng hoặc không giải mã được: {relative_path}") from exc
    return content


def review_plot_data_uri(png_bytes: bytes) -> str:
    """Đóng gói PNG thành data URI để không phụ thuộc endpoint media Streamlit."""
    if not isinstance(png_bytes, bytes) or not png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Không thể đóng gói nội dung không phải PNG thành data URI.")
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")


def _decision_id(review_id: str, reviewer_id: str, timestamp: str) -> str:
    digest = hashlib.sha256(f"{review_id}|{reviewer_id}|{timestamp}".encode("utf-8")).hexdigest()[:20]
    return f"DEC-{digest}"


def build_human_record(form_record: dict, *, reviewer_id: str, evidence_category: str,
                       reviewer_decision: str, phenotype_flags: dict[str, bool | None],
                       evidence_reference: str, reviewer_notes: str, review_status: str,
                       ambiguity_reason: str = "", review_timestamp_utc: str | None = None) -> dict:
    reviewer_id = reviewer_id.strip()
    if not reviewer_id:
        raise ValueError("Nhập reviewer_id trước khi lưu.")
    if review_status not in {"ACCEPTED", "NEEDS_DISCUSSION", "REJECTED"}:
        raise ValueError("Human submission phải là quyết định đã xử lý, không thể lưu PENDING.")
    if not reviewer_notes.strip():
        raise ValueError("Ghi chú reviewer là trường bắt buộc.")
    timestamp = review_timestamp_utc or datetime.now(timezone.utc).isoformat()
    reference = evidence_reference.strip()
    if not reference:
        raise ValueError("Mỗi quyết định cần evidence reference tới tín hiệu, tài liệu hoặc rule đã xem.")
    if evidence_category in {"VERIFIED_OPERATIONAL_HAZARD", "VERIFIED_NORMAL_ENVELOPE", "PROXY_RULE"}:
        if not reference or reference == str(form_record.get("plot_path", "")):
            raise ValueError("Loại evidence VERIFIED/PROXY cần tham chiếu nguồn độc lập; signal plot không đủ.")
    if evidence_category == "PROXY_RULE" and reviewer_decision == "NORMAL":
        raise ValueError("Không gán NORMAL theo proxy; cần operating envelope verified.")
    record = dict(form_record)
    record.update({"review_id": form_record["review_sample_id"],
        "annotation_schema_version": ANNOTATION_SCHEMA_VERSION,
        "evidence_category": evidence_category, "evidence_reference": reference,
        "reviewer_id": reviewer_id, "reviewer_decision": reviewer_decision,
        "phenotype_flags_json": json.dumps(phenotype_flags, ensure_ascii=False, sort_keys=True),
        "reviewer_notes": reviewer_notes.strip(), "review_timestamp_utc": timestamp,
        "review_status": review_status, "ambiguity_reason": ambiguity_reason.strip()})
    derived = derive_pilot_status(record)
    derived["decision_id"] = _decision_id(record["review_id"], reviewer_id, timestamp)
    validate_pilot_annotation(derived)
    return derived


def _decision_row(record: dict) -> dict:
    return {"review_sample_id": record["review_sample_id"], "review_id": record["review_id"],
        "decision_id": record["decision_id"], "annotation_schema_version": record["annotation_schema_version"],
        "reviewer_id": record["reviewer_id"], "reviewer_decision": record["reviewer_decision"],
        "phenotype_flags_json": record["phenotype_flags_json"], "evidence_category": record["evidence_category"],
        "evidence_reference": record["evidence_reference"], "reviewer_notes": record["reviewer_notes"],
        "review_timestamp_utc": record["review_timestamp_utc"], "review_status": record["review_status"],
        "ambiguity_reason": record["ambiguity_reason"]}


def _read_events(audit_path: Path) -> list[dict]:
    if not audit_path.is_file():
        return []
    events = []
    for index, line in enumerate(audit_path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Audit JSONL hỏng tại dòng {index}; không được tiếp tục ghi quyết định.") from exc
        if not isinstance(event, dict) or not isinstance(event.get("replacement"), dict):
            raise ValueError(f"Audit event dòng {index} không có replacement record hợp lệ.")
        events.append(event)
    return events


def _atomic_write_ledger(path: Path, decisions: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent,
                                     prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        decisions.to_csv(stream, index=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def recover_decision_ledger(repo_root: Path, forms: pd.DataFrame | None = None) -> pd.DataFrame:
    forms = forms if forms is not None else load_pilot_forms(repo_root)
    output = repo_root / "ml/data/labels/annotation_pilot"
    ledger_path, audit_path = output / "review_decisions.csv", output / "review_audit.jsonl"
    if ledger_path.is_file():
        existing = pd.read_csv(ledger_path, keep_default_na=False)
        if existing.empty and set(existing.columns) != set(DECISION_COLUMNS):
            existing = decision_template()
    else:
        existing = decision_template()
    events = _read_events(audit_path)
    by_id = {}
    for event in events:
        replacement = event["replacement"]
        row = _decision_row(replacement)
        if (row["review_sample_id"], row["reviewer_id"]) in by_id:
            raise ValueError("Audit history có nhiều quyết định cho cùng sample/reviewer; cần xử lý revision rõ ràng.")
        by_id[(row["review_sample_id"], row["reviewer_id"])] = row
    if not existing.empty:
        validate_decision_ledger(existing, set(forms.review_sample_id.astype(str)))
        for row in existing.to_dict("records"):
            key = (str(row["review_sample_id"]), str(row["reviewer_id"]))
            if key not in by_id or by_id[key]["decision_id"] != row["decision_id"]:
                raise ValueError("Decision ledger có record không đối chiếu được với audit JSONL; dừng để tránh mất lịch sử.")
    existing_ids = set(existing.decision_id.astype(str)) if not existing.empty else set()
    recovered = [row for row in by_id.values() if row["decision_id"] not in existing_ids]
    if recovered:
        existing = pd.concat([existing, pd.DataFrame(recovered, columns=DECISION_COLUMNS)], ignore_index=True)
    validate_decision_ledger(existing, set(forms.review_sample_id.astype(str)))
    materialize_decisions(forms, existing)
    if not ledger_path.is_file() or recovered or set(pd.read_csv(ledger_path, nrows=0).columns) != set(DECISION_COLUMNS):
        _atomic_write_ledger(ledger_path, existing)
    return existing


def _save_human_decision_locked(repo_root: Path, forms: pd.DataFrame, review_id: str, *, reviewer_id: str,
                                evidence_category: str, reviewer_decision: str,
                                phenotype_flags: dict[str, bool | None], evidence_reference: str,
                                reviewer_notes: str, review_status: str,
                                ambiguity_reason: str, review_timestamp_utc: str | None) -> dict:
    matched = forms.loc[forms.review_sample_id.astype(str).eq(str(review_id))]
    if len(matched) != 1:
        raise ValueError("review_id không khớp duy nhất record trong pilot form.")
    ledger = recover_decision_ledger(repo_root, forms)
    if ((ledger.review_sample_id.astype(str) == str(review_id))
            & (ledger.reviewer_id.astype(str) == reviewer_id.strip())).any():
        raise ValueError("Reviewer đã gửi quyết định cho mẫu này; không ghi đè hoặc gửi trùng.")
    base = matched.iloc[0].to_dict()
    record = build_human_record(base, reviewer_id=reviewer_id, evidence_category=evidence_category,
        reviewer_decision=reviewer_decision, phenotype_flags=phenotype_flags,
        evidence_reference=evidence_reference, reviewer_notes=reviewer_notes,
        review_status=review_status, ambiguity_reason=ambiguity_reason,
        review_timestamp_utc=review_timestamp_utc)
    candidate = pd.DataFrame([_decision_row(record)], columns=DECISION_COLUMNS)
    validate_decision_ledger(candidate, set(forms.review_sample_id.astype(str)))
    event = audit_event(base, record, reviewer_id, record["review_timestamp_utc"])
    audit_path = repo_root / "ml/data/labels/annotation_pilot/review_audit.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    updated = pd.concat([ledger, candidate], ignore_index=True)
    _atomic_write_ledger(repo_root / "ml/data/labels/annotation_pilot/review_decisions.csv", updated)
    return record


def save_human_decision(repo_root: Path, review_id: str, *, reviewer_id: str,
                        evidence_category: str, reviewer_decision: str,
                        phenotype_flags: dict[str, bool | None], evidence_reference: str,
                        reviewer_notes: str, review_status: str,
                        ambiguity_reason: str = "", review_timestamp_utc: str | None = None) -> dict:
    forms = load_pilot_forms(repo_root)
    lock_path = repo_root / "ml/data/labels/annotation_pilot/review.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_stream:
        fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
        try:
            return _save_human_decision_locked(repo_root, forms, review_id,
                reviewer_id=reviewer_id, evidence_category=evidence_category,
                reviewer_decision=reviewer_decision, phenotype_flags=phenotype_flags,
                evidence_reference=evidence_reference, reviewer_notes=reviewer_notes,
                review_status=review_status, ambiguity_reason=ambiguity_reason,
                review_timestamp_utc=review_timestamp_utc)
        finally:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)


def _window_overlap_stats(frame: pd.DataFrame) -> dict:
    pair_total = overlap_total = window_total = 0
    by_dataset = {}
    id_column = "review_id" if "review_id" in frame else "review_sample_id"
    for dataset, dataset_frame in frame.groupby("dataset_source", sort=True):
        pairs = overlapping = 0
        involved = set()
        for _, group in dataset_frame.groupby(["session_id", "segment_id"], sort=True):
            windows = group[[id_column, "window_start_seconds", "window_end_seconds"]].drop_duplicates(
                subset=["window_start_seconds", "window_end_seconds"])
            records = list(windows.itertuples(index=False, name=None))
            for left, right in combinations(records, 2):
                left_id, left_start, left_end = left
                right_id, right_start, right_end = right
                pairs += 1
                if max(float(left_start), float(right_start)) < min(float(left_end), float(right_end)):
                    overlapping += 1
                    involved.update((str(left_id), str(right_id)))
        by_dataset[dataset] = {"comparable_window_pairs": pairs, "overlapping_window_pairs": overlapping,
            "overlap_fraction": overlapping / pairs if pairs else None,
            "windows_involved_in_overlap": len(involved)}
        pair_total += pairs
        overlap_total += overlapping
        window_total += len(involved)
    return {"comparable_window_pairs": pair_total, "overlapping_window_pairs": overlap_total,
            "overlap_fraction": overlap_total / pair_total if pair_total else None,
            "windows_involved_in_overlap": window_total, "by_dataset": by_dataset,
            "nominal_adjacent_window_overlap_fraction": 170 / 180}


def build_quality_summary(repo_root: Path, forms: pd.DataFrame | None = None,
                          initial: pd.DataFrame | None = None,
                          extended: pd.DataFrame | None = None) -> dict:
    forms = forms if forms is not None else load_pilot_forms(repo_root)
    if initial is None or extended is None:
        initial, extended = build_review_batches(forms)
    ledger = recover_decision_ledger(repo_root, forms)
    reviewed = ledger.loc[ledger.review_status.isin(("ACCEPTED", "REJECTED", "NEEDS_DISCUSSION"))]
    reviewed_samples = set(reviewed.review_sample_id.astype(str))
    materialized = materialize_decisions(forms, ledger)
    accepted = materialized.loc[materialized.review_status.eq("ACCEPTED")]
    phenotype_counts = {flag: 0 for flag in PHENOTYPE_FLAGS}
    ambiguous_records = 0
    for row in materialized.to_dict("records"):
        flags = json.loads(row["phenotype_flags_json"])
        for name, value in flags.items():
            phenotype_counts[name] += int(value is True)
        ambiguous_records += int(row["review_status"] == "NEEDS_DISCUSSION"
                                 or bool(row.get("ambiguity_reason"))
                                 or sum(value is True for value in flags.values()) > 1)
    conflicts = []
    if not accepted.empty:
        for review_id, group in accepted.groupby("review_sample_id", sort=True):
            decisions = sorted(set(group.reviewer_decision.astype(str)))
            phenotype_conflicts = {}
            for flag in PHENOTYPE_FLAGS:
                assessed = {json.loads(value).get(flag) for value in group.phenotype_flags_json
                            if json.loads(value).get(flag) is not None}
                if len(assessed) > 1:
                    phenotype_conflicts[flag] = sorted(assessed)
            if len(decisions) > 1 or phenotype_conflicts:
                conflicts.append({"review_id": review_id, "decisions": decisions,
                    "phenotype_conflicts": phenotype_conflicts,
                    "reviewers": sorted(group.reviewer_id.astype(str).unique())})
    agreement = inter_reviewer_agreement(ledger)
    by_dataset = {}
    batch_coverage = {}
    for dataset in sorted(forms.dataset_source.unique()):
        source = forms.loc[forms.dataset_source.eq(dataset)]
        source_reviews = reviewed.loc[reviewed.review_sample_id.astype(str).isin(source.review_sample_id.astype(str))]
        source_materialized = materialized.loc[materialized.dataset_source.eq(dataset)]
        source_accepted = source_materialized.loc[source_materialized.review_status.eq("ACCEPTED")]
        by_dataset[dataset] = {
            "queue_records": int(len(source)), "independent_sessions": int(source.session_id.nunique()),
            "reviewed_samples": int(source_reviews.review_sample_id.nunique()),
            "review_decisions": int(len(source_reviews)), "unreviewed_samples": int(len(source) - source_reviews.review_sample_id.nunique()),
            "accepted_class_counts": {label: int(source_accepted.reviewer_decision.eq(label).sum())
                for label in ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH", "REVIEW_REQUIRED", "UNLABELED")},
            "phenotype_flag_counts": {flag: int(sum(json.loads(value).get(flag) is True
                for value in source_materialized.phenotype_flags_json)) for flag in PHENOTYPE_FLAGS},
            "ambiguous_decisions": int(sum(row["dataset_source"] == dataset and (
                row["review_status"] == "NEEDS_DISCUSSION" or bool(row.get("ambiguity_reason"))
                or sum(value is True for value in json.loads(row["phenotype_flags_json"]).values()) > 1)
                for row in materialized.to_dict("records"))),
        }
        for batch_name, batch in ((INITIAL_BATCH_NAME, initial), (EXTENDED_BATCH_NAME, extended)):
            selected = batch.loc[batch.dataset_source.eq(dataset)]
            batch_coverage[f"{batch_name}:{dataset}"] = {"records": int(len(selected)),
                "sessions": int(selected.session_id.nunique())}
    distinct = forms.drop_duplicates(["review_sample_id"])
    session_coverage = []
    for (dataset, session), source in forms.groupby(["dataset_source", "session_id"], sort=True):
        ids = set(source.review_sample_id.astype(str))
        session_reviews = reviewed.loc[reviewed.review_sample_id.astype(str).isin(ids)]
        session_accepted = accepted.loc[accepted.review_sample_id.astype(str).isin(ids)]
        session_phenotypes = {flag: int(sum(json.loads(value).get(flag) is True
            for value in materialized.loc[materialized.review_sample_id.astype(str).isin(ids), "phenotype_flags_json"]))
            for flag in PHENOTYPE_FLAGS}
        session_coverage.append({"dataset_source": dataset, "session_id": session,
            "queue_records": int(len(source)), "reviewed_samples": int(session_reviews.review_sample_id.nunique()),
            "review_decisions": int(len(session_reviews)),
            "unreviewed_samples": int(len(source) - session_reviews.review_sample_id.nunique()),
            "pilot_records": int(source.review_sample_id.isin(initial.review_id).sum()),
            "extended_records": int(source.review_sample_id.isin(extended.review_id).sum()),
            "accepted_class_counts": {label: int(session_accepted.reviewer_decision.eq(label).sum())
                for label in ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH", "REVIEW_REQUIRED", "UNLABELED")},
            "phenotype_flag_counts": session_phenotypes})
    prior_summary_path = repo_root / "ml/reports/labeling/labeling_summary.json"
    if prior_summary_path.is_file():
        prior_summary = json.loads(prior_summary_path.read_text(encoding="utf-8"))
        eligible_by_dataset = {name: int(item["eligible_windows_180s_angle23"])
            for name, item in prior_summary.get("datasets", {}).items()
            if item.get("eligible_windows_180s_angle23") is not None}
    else:
        eligible_by_dataset = {}
    return {
        "annotation_schema_version": ANNOTATION_SCHEMA_VERSION,
        "eligible_23_feature_windows_by_dataset": eligible_by_dataset,
        "eligible_23_feature_windows_total": sum(eligible_by_dataset.values()) if eligible_by_dataset else None,
        "queue_records": int(len(forms)), "reviewed_decisions": int(len(reviewed)),
        "reviewed_samples": int(len(reviewed_samples)), "unreviewed_samples": int(len(forms) - len(reviewed_samples)),
        "verified_external_labels": int(materialized.label_status.eq("VERIFIED").sum()),
        "human_reviewed_phenotypes": int(materialized.label_status.eq("HUMAN_REVIEWED").sum()),
        "proxy_labels": int(materialized.label_status.eq("PROXY").sum()),
        "unlabeled_decisions": int(materialized.label_status.eq("UNLABELED").sum()),
        "needs_discussion": int(materialized.review_status.eq("NEEDS_DISCUSSION").sum()),
        "ambiguous_records": int(ambiguous_records), "conflicting_review_ids": conflicts,
        "accepted_class_counts": {label: int(accepted.reviewer_decision.eq(label).sum())
            for label in ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH", "REVIEW_REQUIRED", "UNLABELED")},
        "phenotype_flag_counts": phenotype_counts,
        "evidence_category_counts": {category: int(accepted.evidence_category.eq(category).sum())
            for category in ("OBSERVED_MOTION_PHENOTYPE", "VERIFIED_OPERATIONAL_HAZARD",
                             "VERIFIED_NORMAL_ENVELOPE", "PROXY_RULE", "UNVERIFIED")},
        "reviewer_count": int(reviewed.reviewer_id.nunique()), "inter_reviewer_agreement": agreement,
        "sessions_in_queue": int(forms.session_id.nunique()), "sessions_in_initial_batch": int(initial.session_id.nunique()),
        "initial_batch_records": int(len(initial)), "extended_batch_records": int(len(extended)),
        "datasets": by_dataset, "batch_coverage": batch_coverage,
        "session_coverage": session_coverage,
        "queue_overlap": _window_overlap_stats(distinct),
        "initial_batch_overlap": _window_overlap_stats(initial),
        "interpretation_vi": "Cửa sổ overlap là các quan sát phụ thuộc theo thời gian, không phải số mẫu độc lập; số reviewed chỉ tăng khi có decision ledger hợp lệ.",
    }


def write_human_reports(repo_root: Path, summary: dict) -> None:
    report_dir = repo_root / "ml/reports/labeling"
    report_dir.mkdir(parents=True, exist_ok=True)
    guide = ["# Hướng dẫn thực hiện Human Review", "", "## Chuẩn bị artifact review", "",
        "Từ thư mục gốc repository, kích hoạt môi trường dự án rồi chạy:", "",
        "```bash", "python -m ml.labeling.human_review_workflow --prepare-batches", "```", "",
        "Lệnh tạo hai batch dưới `ml/data/labels/annotation_pilot/batches/` mà không thay đổi queue gốc:", "",
        "- `pilot_29.csv`: đủ 23 session; Seafar 4, Hohai 21 (mỗi session một đại diện), Southampton 4.",
        "- `extended_63.csv`: 63 cửa sổ Hohai còn lại.", "",
        "Quy tắc chọn Hohai: sắp theo endpoint, start và review ID; lấy hạng trung vị thấp (lower median), xác định bởi `floor((n-1)/2)`. Cách này chọn cửa sổ theo thời gian, không dùng nhãn hay giá trị feature để ưu tiên lớp. Các batch chỉ là bản sao tham chiếu, không chứa annotation.", "",
        "## Cài môi trường", "", "Từ repository root, dùng Python 3.14 theo môi trường M2:", "",
        "```bash", "python3.14 -m venv .venv", "source .venv/bin/activate",
        "python -m pip install -r ml/labeling/requirements.txt", "```", "",
        "## Mở giao diện và thực hiện review", "", "```bash", "python -m streamlit run ml/labeling/review_app.py", "```", "",
        "Trong trình duyệt trên máy local:", "", "1. Chọn batch pilot 29 hoặc batch mở rộng 63.",
        "2. Nhập `reviewer_id` cá nhân; không dùng ID chung cho nhiều người.",
        "3. Chọn `review_id`; kiểm tra dataset/session/segment/window, biểu đồ Roll/Pitch, bối cảnh trước cửa sổ, cờ chất lượng, metadata và bảng 23 angle features kèm validity.",
        "4. Đánh dấu từng phenotype là chưa đánh giá/không quan sát/quan sát; chọn evidence category, quyết định, evidence reference, ghi chú và ambiguity reason khi cần.",
        "5. Nhấn lưu. Hệ thống kiểm tra schema, provenance, category-transition và trùng cặp mẫu/reviewer. Gửi cùng mẫu bởi reviewer khác được giữ như một đánh giá độc lập.", "",
        "Không chọn `NORMAL` nếu không có operating envelope dương tính và evidence reference. `OBSERVED_MOTION_PHENOTYPE` chỉ là quan sát chuyển động; không xác nhận hazard. `VERIFIED_OPERATIONAL_HAZARD` và `VERIFIED_NORMAL_ENVELOPE` bắt buộc có tham chiếu external độc lập.", "",
        "## Lưu quyết định và audit trail", "", "Ledger hiện tại được ghi tại `ml/data/labels/annotation_pilot/review_decisions.csv`; mỗi hàng có `review_id`, `decision_id`, reviewer, annotation schema version, decision, phenotype flags, evidence, timestamp UTC và trạng thái. Audit append-only nằm tại `ml/data/labels/annotation_pilot/review_audit.jsonl`. Cả hai tệp cùng batch/plots bị `.gitignore` loại khỏi Git.", "",
        "Cùng reviewer không thể gửi trùng cùng review ID; giao diện từ chối ghi đè. Nếu phát hiện lỗi trong quyết định, giữ nguyên file audit hiện tại và liên hệ người phụ trách để thực hiện quy trình sửa đổi có version riêng; không xóa/sửa dòng cũ bằng spreadsheet.", "",
        "## Tái tạo báo cáo và kiểm thử", "", "```bash", "python -m ml.labeling.human_review_workflow --refresh-reports", "python -m pytest ml/labeling/tests ml/features/tests ml/preprocessing/tests ml/audit -q", "```", "",
        "Các report Markdown nhỏ được lưu trong `ml/reports/labeling/`. Không cần backend, MQTT hoặc kết nối ESP32.",
        "", "## Giải thích kỹ thuật phục vụ vấn đáp cá nhân", "",
        "- **Em đã làm gì?** Tạo batch xác định, giao diện xem signal/feature và lưu annotation có provenance.",
        "- **Vì sao giữ reviewer ID và audit JSONL?** Để truy về người đưa quyết định và giữ lịch sử append-only; CSV là ledger dễ đọc để phân tích.",
        "- **Tại sao có ba lớp evidence?** Quan sát phenotype, hazard verified và dữ liệu chưa đủ bằng chứng có ý nghĩa khác nhau; không thể xem hình Roll/Pitch là ground truth an toàn.",
        "- **Kết quả thực tế?** Hiện batch có 29+63 record phủ 23 session, nhưng 0 quyết định thật; hệ thống không tự gán nhãn.",
        "- **Rủi ro còn lại?** Cửa sổ trùng lặp phụ thuộc thời gian; review phải blind với `queue_suggested_label` khi phù hợp và split theo session.", ""]
    (report_dir / "human_review_execution_guide.md").write_text("\n".join(guide), encoding="utf-8")

    labels = summary["accepted_class_counts"]
    lines = ["# Đánh giá chất lượng Human Annotation", "", "## Kết quả hiện trạng", "",
        f"Review queue giữ nguyên **{summary['queue_records']} record**, gồm **{summary['initial_batch_records']} mẫu pilot / {summary['sessions_in_initial_batch']} session** và **{summary['extended_batch_records']} mẫu mở rộng**. Ledger hiện có **{summary['reviewed_decisions']} quyết định**, trên **{summary['reviewed_samples']} review ID**; còn **{summary['unreviewed_samples']} record chưa review**.", "",
        f"Đã có {summary['verified_external_labels']} nhãn external VERIFIED, {summary['human_reviewed_phenotypes']} phenotype HUMAN_REVIEWED và {summary['proxy_labels']} proxy. Số liệu bằng 0 phản ánh artifact hiện có, không chứng minh trạng thái vật lý không xuất hiện.", "",
        "## Độ phủ theo nguồn/session", "", "| Nguồn | Queue | Session | Đã review | Chưa review | Pilot record | Pilot session | Extended record |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for dataset, item in summary["datasets"].items():
        pilot_key, extended_key = f"{INITIAL_BATCH_NAME}:{dataset}", f"{EXTENDED_BATCH_NAME}:{dataset}"
        lines.append(f"| {dataset.capitalize()} | {item['queue_records']} | {item['independent_sessions']} | {item['reviewed_samples']} | {item['unreviewed_samples']} | {summary['batch_coverage'][pilot_key]['records']} | {summary['batch_coverage'][pilot_key]['sessions']} | {summary['batch_coverage'][extended_key]['records']} |")
    lines += ["", "### Độ phủ theo từng session độc lập", "",
        "| Nguồn | Session | Queue | Đã review | Chưa review | Pilot | Extended | Lớp ACCEPTED |", "|---|---|---:|---:|---:|---:|---:|---|"]
    for item in summary["session_coverage"]:
        classes = ", ".join(f"{name}: {count}" for name, count in item["accepted_class_counts"].items() if count) or "Chưa có quyết định lớp"
        lines.append(f"| {item['dataset_source'].capitalize()} | `{item['session_id']}` | {item['queue_records']} | {item['reviewed_samples']} | {item['unreviewed_samples']} | {item['pilot_records']} | {item['extended_records']} | {classes} |")
    lines += ["", "## Phân bố lớp, phenotype và bằng chứng", "",
        "### Quyết định ACCEPTED theo lớp", "", "| Lớp | Số quyết định |", "|---|---:|"]
    lines += [f"| `{name}` | {count} |" for name, count in labels.items()]
    lines += ["", "### Lớp ACCEPTED theo nguồn", "", "| Nguồn | NORMAL | HIGH_ROLL | PERSISTENT_OFFSET | AMPLITUDE_GROWTH | REVIEW_REQUIRED | UNLABELED |", "|---|---:|---:|---:|---:|---:|---:|"]
    for dataset, item in summary["datasets"].items():
        counts = item["accepted_class_counts"]
        lines.append(f"| {dataset.capitalize()} | " + " | ".join(str(counts[label]) for label in ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH", "REVIEW_REQUIRED", "UNLABELED")) + " |")
    lines += ["", "### Phenotype flags và evidence category", "", "| Nhóm | Giá trị | Số record ACCEPTED |", "|---|---|---:|"]
    lines += [f"| Phenotype | `{name}` | {count} |" for name, count in summary["phenotype_flag_counts"].items()]
    lines += [f"| Evidence | `{name}` | {count} |" for name, count in summary["evidence_category_counts"].items()]
    lines += ["", f"Mẫu mơ hồ hoặc cần thảo luận: **{summary['ambiguous_records']}**; review ID có bất đồng: **{len(summary['conflicting_review_ids'])}**.", "",
        "## Bằng chứng độc lập theo nguồn", "",
        "- **Seafar:** telemetry từ một session tàu thật; audit hiện có không ghi nhận event, incident hoặc operating-state annotation độc lập. Offset Roll không tự xác nhận hazard hay NORMAL.",
        "- **Hohai:** 21 session mô hình thử nghiệm; tên sheet/configuration không phải nhãn. Workbook không kèm event/hazard labels; sampling 50 Hz là metadata thí nghiệm, không phải evidence vận hành.",
        "- **Southampton:** điều kiện sóng trong Test Plan là provenance của thí nghiệm; 4 mẫu pilot cùng thuộc Run 14 và không có hazard reference độc lập.",
        "- Chưa thấy operating envelope NORMAL được chấp thuận cho bất kỳ nguồn nào. Xem [kiểm kê evidence trước đó](label_evidence_report.md) để biết nguồn tài liệu đã kiểm tra.", "",
        "## Độ độc lập của đánh giá và mức nhất trí", "",
        f"Trong toàn bộ feature windows, stride 10 giây trên cửa sổ 180 giây nghĩa là hai cửa sổ kề chia sẻ 170 giây (94,4%). Riêng review queue thưa có {summary['queue_overlap']['overlapping_window_pairs']} cặp giao nhau trên {summary['queue_overlap']['comparable_window_pairs']} cặp trong cùng segment ({summary['queue_overlap']['overlap_fraction']:.1%}); {summary['queue_overlap']['windows_involved_in_overlap']} record có tham gia giao nhau. Pilot 29 mẫu có {summary['initial_batch_overlap']['overlapping_window_pairs']} cặp giao nhau trên {summary['initial_batch_overlap']['comparable_window_pairs']} cặp so sánh, liên quan {summary['initial_batch_overlap']['windows_involved_in_overlap']} mẫu. Các cặp này tập trung ở Southampton Run 14; hiện vẫn có 0 quyết định human review. Cửa sổ overlap là quan sát phụ thuộc, không phải session độc lập.", ""]
    if summary["inter_reviewer_agreement"]["status"] == "NOT_CALCULATED":
        lines.append("Chưa tính mức nhất trí giữa reviewer: " + summary["inter_reviewer_agreement"]["reason_vi"])
    else:
        lines.append("Mức nhất trí giữa reviewer được tính trên các quyết định ACCEPTED cùng sample. Kết quả mô tả độ nhất trí giữa người đánh giá, không phải xác thực hazard: `" + json.dumps(summary["inter_reviewer_agreement"], ensure_ascii=False, sort_keys=True) + "`.")
    lines += ["", "## Rủi ro và giới hạn", "",
        "- Không có verified external reference hoặc human decisions tại thời điểm sinh báo cáo này.",
        "- Human review dựa trên Roll/Pitch có thể ghi nhận phenotype; không chứng minh operating hazard hay normal operating envelope.",
        "- Hohai và Southampton là nguồn model-scale; không gộp ngưỡng với Seafar như cùng miền vật lý.",
        "- Cửa sổ 180 giây stride 10 giây overlap cao; mọi đánh giá mô hình phải chia theo session/run/vessel, không random theo window.",
        "- Nếu nhãn được định nghĩa từ cùng đặc trưng Roll dùng huấn luyện, kết quả dễ vòng lặp; đồng thuận với proxy không phải kiểm định an toàn.", "",
        "## Giải thích kỹ thuật phục vụ vấn đáp cá nhân", "",
        "**Độ phủ** tính theo review ID và session, không xem mỗi cửa sổ feature là mẫu độc lập. **Tính mơ hồ** giữ đồng thời các phenotype flags và ghi lý do, không ép về một lớp. **Mức nhất trí** chỉ tính khi có ít nhất hai reviewer thật cùng đánh giá một mẫu. **Kết quả hiện tại** là chưa có reviewer, nên chưa lớp nào được xác nhận; điều này không đồng nghĩa chuyển động bất thường không tồn tại.", ""]
    (report_dir / "human_annotation_quality_report.md").write_text("\n".join(lines), encoding="utf-8")

    eligible_total = summary["eligible_23_feature_windows_total"]
    eligible_display = f"{eligible_total:,}".replace(",", ".") if eligible_total is not None else "Chưa có số liệu"
    readiness = ["# Đánh giá mức sẵn sàng huấn luyện", "", "## Quyết định hiện tại", "",
        "**Chưa đủ điều kiện huấn luyện Machine Learning có giám sát cho bốn lớp hazard.** Hiện chưa có quyết định review của con người hoặc nhãn tham chiếu external. 92 cửa sổ review không phải 92 quan sát độc lập; queue phủ 23 session.", "",
        "| Lựa chọn | Trạng thái | Bằng chứng hiện có | Bằng chứng còn thiếu / rủi ro |", "|---|---|---|---|"]
    readiness += [
        f"| Huấn luyện có giám sát bốn lớp hazard đã xác minh | CHƯA ĐỦ | {eligible_display} cửa sổ đủ 23 đặc trưng; {summary['sessions_in_initial_batch']} session trong pilot | 0 nhãn VERIFIED; cần tham chiếu sự kiện/điều kiện vận hành và miền NORMAL; chưa đo độ phủ lớp; có nguy cơ rò rỉ do cửa sổ chồng lấn và khác biệt quy mô vật lý |",
        "| Nghiên cứu phân loại phenotype chuyển động quan sát được | CHƯA SẴN SÀNG HUẤN LUYỆN | Có chuỗi thời gian Roll/Pitch; pilot 29 hồ sơ phủ 23 session | 0 quyết định reviewer; cần ít nhất hai reviewer đánh giá chồng lặp để đo mức nhất trí; phenotype không đồng nghĩa hazard |",
        "| Thử nghiệm kỹ thuật bằng proxy rule (nhãn suy ra theo quy tắc) | CHỈ CÓ THỂ LÀM SAU KHI DUYỆT RULE | Có cửa sổ feature và provenance | Ngưỡng mô phỏng chưa phải giới hạn hazard; nhãn vòng lặp nếu mô hình dùng cùng đặc trưng; chỉ báo cáo mức khớp với proxy, không tuyên bố an toàn |",
        "| Thu thập thêm dữ liệu có nhãn độc lập | KHUYẾN NGHỊ | Nguồn hiện tại chưa có nhãn tham chiếu external | Cần nhật ký vận hành/sự kiện có timestamp, miền NORMAL, scale/ngữ cảnh và xác minh chuyên gia |", "",
        "## Điều kiện trước huấn luyện có giám sát", "",
        "1. Đánh giá 29 mẫu pilot; lưu reviewer ID, bằng chứng, ghi chú, thời điểm và audit trail.",
        "2. Có ít nhất hai reviewer độc lập cùng đánh giá tập con, sau đó báo mức nhất trí và trường hợp bất đồng.",
        "3. Xác minh hazard bằng tham chiếu vận hành độc lập; định nghĩa NORMAL bằng miền hoạt động dương tính đã được chấp thuận.",
        "4. Xử lý phenotype chồng lấn và cửa sổ NEEDS_DISCUSSION trước khi tạo nhãn huấn luyện.",
        "5. Chia tập theo session/run/vessel, không chia ngẫu nhiên các cửa sổ chồng lấn.",
        "6. Giữ tập kiểm thử độc lập với rule/feature đã định nghĩa proxy; phân tích riêng theo quy mô và nguồn dữ liệu.", "",
        "## Giải thích kỹ thuật phục vụ vấn đáp cá nhân", "",
        "Không thể suy mức sẵn sàng từ số cửa sổ đơn thuần: các cửa sổ chồng lấn mạnh và tập trung trong số session hữu hạn. Human review có thể xác nhận phenotype chuyển động quan sát được nhưng không thay thế nhãn tham chiếu vận hành độc lập. Bước phù hợp hiện nay là hoàn thành pilot, đo mức nhất trí giữa reviewer và thu thập nhãn sự kiện/điều kiện vận hành. Sau đó mới quyết định nghiên cứu phenotype, thử nghiệm proxy có giới hạn hay huấn luyện nhận diện hazard.", ""]
    (report_dir / "training_readiness_assessment.md").write_text("\n".join(readiness), encoding="utf-8")


def write_quality_summary(repo_root: Path, summary: dict) -> Path:
    path = repo_root / "ml/data/labels/annotation_pilot/human_annotation_quality_summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return path


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Chuẩn bị batch và báo cáo Human Review.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--prepare-batches", action="store_true")
    parser.add_argument("--refresh-reports", action="store_true")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    if args.prepare_batches:
        initial, extended = write_review_batches(repo_root)
        print(f"[THÔNG TIN] Đã tạo pilot {len(initial)} mẫu/{initial.session_id.nunique()} session và extended {len(extended)} mẫu.")
    if args.refresh_reports:
        summary = build_quality_summary(repo_root)
        write_human_reports(repo_root, summary)
        write_quality_summary(repo_root, summary)
        print(f"[THÔNG TIN] Đã cập nhật báo cáo; quyết định reviewer: {summary['reviewed_decisions']}; chưa review: {summary['unreviewed_samples']}.")
    if not args.prepare_batches and not args.refresh_reports:
        parser.error("Chọn --prepare-batches hoặc --refresh-reports.")


if __name__ == "__main__":
    main()
