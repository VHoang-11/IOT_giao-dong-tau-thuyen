from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .evidence_audit import _matching_provenance
from .pilot_schema import (PILOT_COLUMNS, PILOT_IDENTITY, REVIEW_FORM_FIELDS, derive_pilot_status,
                           empty_phenotype_flags, validate_pilot_annotation)


QUEUE_TO_PILOT = {
    "dataset": "dataset_source", "session": "session_id", "segment": "segment_id",
    "window_start": "window_start_seconds", "window_end": "window_end_seconds",
}


def _sample_id(row: pd.Series) -> str:
    key = "|".join(str(row[name]) for name in PILOT_IDENTITY)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return f"PILOT-{digest}"


def _safe_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sample_quality(feature_row: pd.Series, source_metadata: dict, inherited_quality: str | None,
                    context_coverage: float) -> list[str]:
    flags = []
    validity = json.loads(feature_row.validity_json)
    for name, detail in sorted(validity.items()):
        if detail.get("status") != "VALID":
            flags.append(f"FEATURE:{name}:{detail.get('status')}")
    flags.extend(str(item) for item in source_metadata.get("warnings", []))
    if inherited_quality:
        try:
            previous_flags = json.loads(inherited_quality)
            flags.extend(str(item) for item in previous_flags)
        except (TypeError, json.JSONDecodeError):
            flags.append(f"PARENT_QUALITY_FLAG:{inherited_quality}")
    if context_coverage < 0.999:
        flags.append("PRECEDING_CONTEXT_PARTIAL_OR_UNAVAILABLE")
    flags.append("WINDOWS_OVERLAP_BY_180S_WINDOW_AND_10S_STRIDE")
    return list(dict.fromkeys(flags))


def _metadata_reference(dataset: str, provenance: dict) -> str | None:
    if dataset == "southampton" and provenance.get("wave_condition_test_plan_provenance"):
        return "ml/data/raw/southampton/Readme/KCS Test Plan June 2023.xlsx"
    if dataset == "hohai":
        return f"{provenance.get('raw_reference', '')}; units/rate documentation: ml/data/raw/hohai/Data Description Example.pdf"
    return provenance.get("raw_reference")


def select_review_signal(frame: pd.DataFrame, start: float, end: float,
                         context_seconds: float) -> pd.DataFrame:
    """Lấy context quá khứ cùng cửa sổ, không đưa quan sát sau endpoint vào hình review."""
    segment_first = float(frame["time_seconds"].iloc[0])
    plot_lower = max(start - context_seconds, segment_first)
    return frame.loc[(frame.time_seconds > plot_lower) & (frame.time_seconds <= end),
                     ["time_seconds", "roll_deg", "pitch_deg"]].copy()


def _plot_sample(frame: pd.DataFrame, record: dict, output: Path, context_seconds: float, dpi: int) -> tuple[float, float, float]:
    start = float(record["window_start_seconds"])
    end = float(record["window_end_seconds"])
    target_context_start = start - context_seconds
    plot_lower = max(target_context_start, float(frame["time_seconds"].iloc[0]))
    data = select_review_signal(frame, start, end, context_seconds)
    if data.empty or not ((data.time_seconds > start) & (data.time_seconds <= end)).any():
        raise ValueError(f"Không tìm thấy tín hiệu trong cửa sổ review: {record['review_sample_id']}")
    fs = float(record.get("target_sampling_hz_effective", 10.0) or 10.0)
    context_count = int(((data.time_seconds > plot_lower) & (data.time_seconds <= start)).sum())
    context_span = min(context_seconds, max(0.0, start - plot_lower))
    expected_context = int(round(context_seconds * fs))
    context_coverage = min(1.0, context_count / expected_context) if expected_context else 1.0
    available_context = context_count / fs if fs > 0 else 0.0
    rel_time = data.time_seconds.to_numpy(dtype=float) - start
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.unicode_minus": False, "font.size": 8})
    fig, axes = plt.subplots(2, 1, figsize=(9.2, 4.8), sharex=True)
    for axis, channel, color, title in ((axes[0], "roll_deg", "#2563eb", "Tín hiệu Roll"),
                                        (axes[1], "pitch_deg", "#ea580c", "Tín hiệu Pitch")):
        axis.plot(rel_time, pd.to_numeric(data[channel], errors="coerce"), color=color, linewidth=.8,
                  label=title)
        axis.axvspan(0.0, end - start, color="#dbeafe", alpha=.45, label="Cửa sổ review 180 giây")
        axis.axvline(0.0, color="black", linestyle="--", linewidth=.8, label="Bắt đầu cửa sổ")
        axis.axvline(end - start, color="green", linestyle=":", linewidth=.8, label="Kết thúc cửa sổ")
        axis.set_ylabel(f"{title.split()[-1]} (độ)")
        axis.grid(alpha=.2)
        axis.legend(loc="upper right", fontsize=7)
    axes[1].set_xlabel("Thời gian tương đối với đầu cửa sổ review (giây)")
    fig.suptitle(f"{record['review_sample_id']} · {record['dataset_source']} · {record['session_id']} / {record['segment_id']}\n"
                 f"Bối cảnh trước cửa sổ khả dụng: {available_context:.1f}/{context_seconds:.0f} giây")
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=dpi)
    plt.close(fig)
    target_count = int(((data.time_seconds > start) & (data.time_seconds <= end)).sum())
    return available_context, context_coverage, target_count


def _preserve_existing_reviews(generated: pd.DataFrame, existing_path: Path) -> pd.DataFrame:
    if not existing_path.is_file():
        return generated
    old = pd.read_csv(existing_path, keep_default_na=False)
    if "review_sample_id" not in old or old.review_sample_id.duplicated().any():
        raise ValueError("Pilot form hiện có thiếu ID ổn định hoặc chứa ID trùng; không ghi đè.")
    if set(old.review_sample_id) - set(generated.review_sample_id):
        raise ValueError("Pilot form có sample ID không còn trong review queue; cần đối soát thủ công.")
    old_by_id = old.set_index("review_sample_id")
    merged = generated.set_index("review_sample_id")
    for sample_id, old_row in old_by_id.iterrows():
        if sample_id not in merged.index:
            continue
        for column in REVIEW_FORM_FIELDS:
            if column in old_row.index and old_row[column] != "":
                merged.loc[sample_id, column] = old_row[column]
    return merged.reset_index()


def prepare_annotation_pilot(repo_root: Path, queue_path: Path, output_root: Path,
                             context_seconds: float = 180.0, dpi: int = 100,
                             existing_form_path: Path | None = None) -> tuple[pd.DataFrame, dict]:
    if context_seconds < 0 or not math.isfinite(context_seconds):
        raise ValueError("context_seconds phải hữu hạn và không âm.")
    queue = pd.read_csv(queue_path, keep_default_na=False)
    feature_meta: dict[str, pd.DataFrame] = {}
    inherited_labels: dict[str, pd.DataFrame] = {}
    for dataset in queue.dataset.unique():
        feature_meta[dataset] = pd.read_parquet(repo_root / "ml/data/features" / dataset / "feature_metadata.parquet")
        label_path = repo_root / "ml/data/labels/feasibility" / dataset / "unlabeled_windows.parquet"
        inherited_labels[dataset] = pd.read_parquet(label_path) if label_path.is_file() else pd.DataFrame()
    segment_cache: dict[tuple[str, str, str], tuple[pd.DataFrame, Path, dict, str]] = {}
    records = []
    target_counts = []
    for queue_row in queue.itertuples(index=False):
        ds, session, segment = str(queue_row.dataset), str(queue_row.session), str(queue_row.segment)
        identity = (ds, session, segment)
        if identity not in segment_cache:
            candidates = list((repo_root / "ml/data/processed" / ds).glob("**/timeseries.parquet"))
            matched = []
            for path in candidates:
                frame_head = pd.read_parquet(path, columns=["dataset_source", "session_id", "segment_id"])
                if (str(frame_head.dataset_source.iloc[0]), str(frame_head.session_id.iloc[0]),
                    str(frame_head.segment_id.iloc[0])) == identity:
                    matched.append(path)
            if len(matched) != 1:
                raise ValueError(f"Không xác định duy nhất segment processed cho {identity}: {len(matched)}.")
            path = matched[0]
            frame = pd.read_parquet(path)
            provenance, provenance_path = _matching_provenance(repo_root, ds, session, segment)
            if len(frame) < 2 or not frame.time_seconds.is_monotonic_increasing:
                raise ValueError(f"Time Series không tăng nghiêm ngặt: {identity}")
            segment_cache[identity] = (frame, path, provenance, provenance_path)
        frame, data_path, provenance, provenance_path = segment_cache[identity]
        start, end = float(queue_row.window_start), float(queue_row.window_end)
        meta = feature_meta[ds]
        mask = (meta.session_id.astype(str).eq(session) & meta.segment_id.astype(str).eq(segment)
                & ((pd.to_numeric(meta.window_end_seconds) - end).abs() <= 1e-6))
        matched_meta = meta.loc[mask]
        if len(matched_meta) != 1:
            raise ValueError(f"Queue window không khớp duy nhất feature metadata: {identity}/{end}.")
        feature_row = matched_meta.iloc[0]
        if not math.isclose(start, end - 180.0, abs_tol=1e-6):
            raise ValueError("Review queue phải dùng đúng cửa sổ endpoint trailing 180 giây.")
        label_row = inherited_labels[ds]
        inherited_quality = None
        if not label_row.empty:
            selected = label_row.loc[label_row.session_id.astype(str).eq(session)
                & label_row.segment_id.astype(str).eq(segment)
                & ((pd.to_numeric(label_row.window_end_seconds) - end).abs() <= 1e-6)]
            if len(selected) == 1:
                inherited_quality = selected.iloc[0].get("quality_flags")
        sample_id = _sample_id(pd.Series({"dataset_source": ds, "session_id": session, "segment_id": segment,
                                          "window_start_seconds": start, "window_end_seconds": end}))
        figure_path = output_root / "figures" / ds / f"{sample_id}.png"
        context_available, context_coverage, target_count = _plot_sample(frame, {"review_sample_id": sample_id,
            "dataset_source": ds, "session_id": session, "segment_id": segment, "window_start_seconds": start,
            "window_end_seconds": end, "target_sampling_hz_effective": provenance.get("target_sampling_hz_effective", 10.0)},
            figure_path, context_seconds, dpi)
        source_metadata = json.loads(feature_row.source_metadata_json)
        quality_flags = _sample_quality(feature_row, source_metadata, inherited_quality, context_coverage)
        relevant_metadata = {key: provenance.get(key) for key in (
            "raw_file", "raw_sheet", "raw_run_id", "raw_reference", "original_sampling_hz", "unit_original",
            "timestamp_source", "source_class", "wave_condition_test_plan_provenance", "axis_sign_confidence", "warnings")
            if key in provenance}
        record = {"review_sample_id": sample_id, "dataset_source": ds, "session_id": session,
            "segment_id": segment, "window_start_seconds": start, "window_end_seconds": end,
            "context_start_seconds": start - context_seconds, "context_end_seconds": start,
            "context_available_seconds": context_available,
            "context_coverage_fraction": context_coverage,
            "plot_path": figure_path.relative_to(repo_root).as_posix(),
            "experiment_metadata_json": _safe_json(relevant_metadata),
            "experiment_metadata_reference": _metadata_reference(ds, provenance),
            "quality_flags_json": _safe_json(quality_flags), "queue_suggested_label": queue_row.suggested_label,
            "evidence_category": "UNVERIFIED", "evidence_reference": "", "reviewer_id": "",
            "reviewer_decision": "", "phenotype_flags_json": empty_phenotype_flags(),
            "reviewer_notes": "", "review_timestamp_utc": "", "review_status": "PENDING",
            "label_status": "UNLABELED", "label_source": "UNKNOWN", "ambiguity_reason": ""}
        validate_pilot_annotation(record)
        records.append(record)
        target_counts.append(target_count)
    forms = pd.DataFrame(records, columns=PILOT_COLUMNS)
    if forms.review_sample_id.duplicated().any():
        raise ValueError("Sinh trùng review_sample_id; pilot không tái lập.")
    if existing_form_path:
        forms = _preserve_existing_reviews(forms, existing_form_path)
        forms = pd.DataFrame([derive_pilot_status(record) for record in forms.to_dict("records")], columns=PILOT_COLUMNS)
    summary = {"pilot_samples": int(len(forms)), "datasets": {},
        "reviewed_decisions": int((forms.review_status.isin(("ACCEPTED", "REJECTED", "NEEDS_DISCUSSION")) & forms.reviewer_decision.ne("")).sum()),
        "human_reviewed_labels": int(forms.label_status.eq("HUMAN_REVIEWED").sum()),
        "verified_operational_hazard_labels": int((forms.label_status.eq("VERIFIED") & forms.evidence_category.eq("VERIFIED_OPERATIONAL_HAZARD")).sum()),
        "proxy_labels": int(forms.label_status.eq("PROXY").sum()),
        "unlabeled_or_pending": int(forms.label_status.eq("UNLABELED").sum()),
        "ambiguous_samples": int(forms.review_status.eq("NEEDS_DISCUSSION").sum()),
        "overlapping_phenotype_samples": int(sum(len([v for v in json.loads(text).values() if v is True]) > 1 for text in forms.phenotype_flags_json)),
        "inter_reviewer_agreement_status": "NOT_CALCULATED_NO_TWO_REVIEWERS",
        "window_sample_count_min": int(min(target_counts)) if target_counts else 0,
        "window_sample_count_max": int(max(target_counts)) if target_counts else 0,
        "preceding_context_seconds_requested": context_seconds}
    for ds, group in forms.groupby("dataset_source", sort=True):
        summary["datasets"][ds] = {"samples": int(len(group)),
            "sessions": int(group.session_id.nunique()),
            "reviewed_decisions": int((group.review_status.isin(("ACCEPTED", "REJECTED", "NEEDS_DISCUSSION")) & group.reviewer_decision.ne("")).sum()),
            "human_reviewed": int(group.label_status.eq("HUMAN_REVIEWED").sum()),
            "verified_hazard": int((group.label_status.eq("VERIFIED") & group.evidence_category.eq("VERIFIED_OPERATIONAL_HAZARD")).sum()),
            "proxy": int(group.label_status.eq("PROXY").sum()), "unlabeled": int(group.label_status.eq("UNLABELED").sum()),
            "ambiguous": int(group.review_status.eq("NEEDS_DISCUSSION").sum()),
            "median_context_coverage_fraction": float(group.context_coverage_fraction.median()),
            "class_counts": {name: int(group.loc[group.review_status.eq("ACCEPTED"), "reviewer_decision"].eq(name).sum())
                for name in ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH", "REVIEW_REQUIRED")}
                | {"UNLABELED": int(group.label_status.eq("UNLABELED").sum())}}
    return forms, summary


def annotation_form_template() -> pd.DataFrame:
    return pd.DataFrame(columns=PILOT_COLUMNS)
