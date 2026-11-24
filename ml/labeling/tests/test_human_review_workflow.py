from __future__ import annotations

import base64
import json
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image, ImageDraw

from ml.labeling.human_review_workflow import (
    ANNOTATION_SCHEMA_VERSION,
    build_human_record,
    build_quality_summary,
    build_review_batches,
    load_feature_review,
    load_review_plot,
    review_plot_data_uri,
    recover_decision_ledger,
    save_human_decision,
    write_review_batches,
)
from ml.labeling.pilot_schema import PILOT_COLUMNS, empty_phenotype_flags


def test_review_plot_loader_rejects_missing_or_invalid_image_content(tmp_path):
    record = {"plot_path": "ml/data/labels/annotation_pilot/figures/sample.png"}
    with pytest.raises(FileNotFoundError, match="Không tìm thấy signal plot"):
        load_review_plot(tmp_path, record)

    image_path = tmp_path / record["plot_path"]
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"not a PNG image")
    with pytest.raises(ValueError, match="hỏng hoặc không giải mã được"):
        load_review_plot(tmp_path, record)

    image = Image.new("RGB", (320, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.line((10, 50, 310, 50), fill="#2563eb", width=3)
    draw.line((10, 130, 310, 130), fill="#ea580c", width=3)
    image.save(image_path, format="PNG")
    content = load_review_plot(tmp_path, record)
    assert content.startswith(b"\x89PNG\r\n\x1a\n")
    with Image.open(BytesIO(content)) as loaded:
        assert loaded.format == "PNG"
        assert loaded.size == (320, 180)
    data_uri = review_plot_data_uri(content)
    assert data_uri.startswith("data:image/png;base64,")
    assert base64.b64decode(data_uri.partition(",")[2]) == content


@pytest.mark.skipif(not (Path(__file__).resolve().parents[3] / "ml/data/labels/annotation_pilot/annotation_pilot.csv").is_file(),
                    reason="Pilot artifacts (gitignored, từ dữ liệu thật) không có trong môi trường này.")
def test_actual_pilot_hohai_chart_contains_roll_and_pitch_plot_content():
    repo_root = Path(__file__).resolve().parents[3]
    batch_path = repo_root / "ml/data/labels/annotation_pilot/batches/pilot_29.csv"
    forms = pd.read_csv(batch_path, keep_default_na=False)
    record = forms.loc[forms.dataset_source.eq("hohai")].iloc[0].to_dict()
    content = load_review_plot(repo_root, record)
    import numpy as np

    with Image.open(BytesIO(content)).convert("RGB") as image:
        pixels = np.asarray(image)
        blue_line_pixels = (pixels[:, :, 2] > pixels[:, :, 0] * 1.25) & (pixels[:, :, 2] > 100)
        orange_line_pixels = (pixels[:, :, 0] > pixels[:, :, 2] * 1.2) & (pixels[:, :, 0] > 150)
        assert image.width > 300 and image.height > 200
        assert blue_line_pixels.sum() > 50
        assert orange_line_pixels.sum() > 50


@pytest.mark.skipif(not (Path(__file__).resolve().parents[3] / "ml/data/labels/annotation_pilot/annotation_pilot.csv").is_file(),
                    reason="Pilot artifacts (gitignored, từ dữ liệu thật) không có trong môi trường này.")
def test_all_92_annotation_records_have_valid_pngs_for_inline_delivery():
    repo_root = Path(__file__).resolve().parents[3]
    forms_path = repo_root / "ml/data/labels/annotation_pilot/annotation_pilot.csv"
    forms = pd.read_csv(forms_path, keep_default_na=False)
    assert len(forms) == 92
    for record in forms.to_dict("records"):
        content = load_review_plot(repo_root, record)
        assert review_plot_data_uri(content).startswith("data:image/png;base64,")


def _make_forms() -> pd.DataFrame:
    records = []
    for index in range(4):
        records.append(_form_record("seafar", "seafar_session_001", f"segment_{index}", index))
    for session_index in range(21):
        for window_index in range(4):
            records.append(_form_record("hohai", f"hohai_session_{session_index:02d}", "segment_001", window_index))
    for index in range(4):
        records.append(_form_record("southampton", "southampton_run_14", "segment_001", index))
    return pd.DataFrame(records, columns=PILOT_COLUMNS)


def _form_record(dataset: str, session: str, segment: str, index: int) -> dict:
    start = 10.0 * index
    return {
        "review_sample_id": f"PILOT-{dataset}-{session}-{segment}-{index}",
        "dataset_source": dataset, "session_id": session, "segment_id": segment,
        "window_start_seconds": start, "window_end_seconds": start + 180.0,
        "context_start_seconds": start - 180.0, "context_end_seconds": start,
        "context_available_seconds": 180.0, "context_coverage_fraction": 1.0,
        "plot_path": f"ml/data/labels/annotation_pilot/figures/{dataset}/sample.png",
        "experiment_metadata_json": "{}", "experiment_metadata_reference": "",
        "quality_flags_json": "[]", "queue_suggested_label": "UNLABELED",
        "evidence_category": "UNVERIFIED", "evidence_reference": "", "reviewer_id": "",
        "reviewer_decision": "", "phenotype_flags_json": empty_phenotype_flags(),
        "reviewer_notes": "", "review_timestamp_utc": "", "review_status": "PENDING",
        "label_status": "UNLABELED", "label_source": "UNKNOWN", "ambiguity_reason": "",
    }


def test_deterministic_batch_selection_covers_23_sessions_without_mutating_queue(tmp_path):
    forms = _make_forms()
    before = forms.copy(deep=True)
    initial_a, extended_a = build_review_batches(forms)
    initial_b, extended_b = build_review_batches(forms)
    assert len(initial_a) == 29
    assert initial_a.session_id.nunique() == 23
    assert len(extended_a) == 63
    assert initial_a.dataset_source.value_counts().to_dict() == {"hohai": 21, "seafar": 4, "southampton": 4}
    assert extended_a.dataset_source.eq("hohai").all()
    assert forms.equals(before)
    assert initial_a.review_id.tolist() == initial_b.review_id.tolist()
    assert extended_a.review_id.tolist() == extended_b.review_id.tolist()
    write_review_batches(tmp_path, forms, tmp_path / "batch-a")
    write_review_batches(tmp_path, forms, tmp_path / "batch-b")
    for filename in ("pilot_29.csv", "extended_63.csv"):
        assert (tmp_path / "batch-a" / filename).read_bytes() == (tmp_path / "batch-b" / filename).read_bytes()


def test_feature_review_matches_exact_session_segment_and_endpoint(tmp_path):
    feature_dir = tmp_path / "ml/data/features/seafar"
    feature_dir.mkdir(parents=True)
    pd.DataFrame([{"window_id": "W1", "roll_rms_60": 1.25, "roll_std_60": 1.0,
                   "roll_mean_60": 0.5, "roll_peak_to_peak_60": 4.0, "roll_abs_p95_60": 2.0,
                   "roll_abs_max_60": 2.0, "roll_iqr_60": 1.0, "roll_diff_rms_60": 0.2,
                   "roll_mean_180": 0.5, "roll_median_180": 0.5, "roll_mean_abs_180": 1.0,
                   "roll_dominant_sign_ratio_180": 0.8, "roll_segment_mean_std_180": 0.1,
                   "roll_mean_shift_180": 0.0, "roll_rms_early_60": 1.0, "roll_rms_late_60": 1.2,
                   "roll_rms_ratio_180": 1.2, "roll_rms_slope_180": 0.1, "roll_rms_trend_r2_180": 0.9,
                   "roll_p95_trend_slope_180": 0.1, "pitch_rms_60": 0.5, "pitch_std_60": 0.4,
                   "pitch_peak_to_peak_60": 2.0}]).to_parquet(feature_dir / "feature_values.parquet", index=False)
    pd.DataFrame([{"window_id": "W1", "session_id": "session-a", "segment_id": "segment-a",
                   "window_end_seconds": 180.0, "validity_json": json.dumps({
                       "roll_rms_60": {"status": "VALID", "reason": ""}})}]).to_parquet(
                           feature_dir / "feature_metadata.parquet", index=False)
    record = _form_record("seafar", "session-a", "segment-a", 0)
    result = load_feature_review(tmp_path, record)
    assert len(result) == 23
    assert result.loc[result["Đặc trưng"].eq("roll_rms_60"), "Giá trị"].iloc[0] == 1.25
    assert result.loc[result["Đặc trưng"].eq("roll_rms_60"), "Trạng thái"].iloc[0] == "VALID"
    record["segment_id"] = "different-segment"
    with pytest.raises(ValueError, match="(?i)không khớp duy nhất"):
        load_feature_review(tmp_path, record)


def test_human_review_requires_evidence_and_positive_normal_envelope():
    form = _form_record("seafar", "session-a", "segment-a", 0)
    with pytest.raises(ValueError, match="evidence reference"):
        build_human_record(form, reviewer_id="r1", evidence_category="VERIFIED_OPERATIONAL_HAZARD",
            reviewer_decision="HIGH_ROLL", phenotype_flags={"HIGH_ROLL": True,
                "PERSISTENT_OFFSET": False, "AMPLITUDE_GROWTH": False}, evidence_reference="",
            reviewer_notes="Có tín hiệu dao động.", review_status="ACCEPTED",
            review_timestamp_utc="2026-11-17T10:00:00Z")
    with pytest.raises(ValueError, match="NORMAL cần đánh giá rõ"):
        build_human_record(form, reviewer_id="r1", evidence_category="VERIFIED_NORMAL_ENVELOPE",
            reviewer_decision="NORMAL", phenotype_flags={"HIGH_ROLL": None,
                "PERSISTENT_OFFSET": False, "AMPLITUDE_GROWTH": False},
            evidence_reference="approved-envelope-v1", reviewer_notes="Kiểm tra envelope.",
            review_status="ACCEPTED", review_timestamp_utc="2026-11-17T10:00:00Z")
    with pytest.raises(ValueError, match="Không gán NORMAL theo proxy"):
        build_human_record(form, reviewer_id="r1", evidence_category="PROXY_RULE",
            reviewer_decision="NORMAL", phenotype_flags={"HIGH_ROLL": False,
                "PERSISTENT_OFFSET": False, "AMPLITUDE_GROWTH": False},
            evidence_reference="rule-config-v1", reviewer_notes="Proxy fixture.",
            review_status="ACCEPTED", review_timestamp_utc="2026-11-17T10:00:00Z")


def _write_one_form_repo(repo_root: Path) -> str:
    output = repo_root / "ml/data/labels/annotation_pilot"
    output.mkdir(parents=True)
    record = _form_record("seafar", "session-a", "segment-a", 0)
    record["review_sample_id"] = "PILOT-one"
    pd.DataFrame([record], columns=PILOT_COLUMNS).to_csv(output / "annotation_pilot.csv", index=False)
    return record["review_sample_id"]


def test_actual_decision_save_audit_and_duplicate_protection(tmp_path):
    review_id = _write_one_form_repo(tmp_path)
    common = {"evidence_category": "OBSERVED_MOTION_PHENOTYPE", "reviewer_decision": "HIGH_ROLL",
        "phenotype_flags": {"HIGH_ROLL": True, "PERSISTENT_OFFSET": False, "AMPLITUDE_GROWTH": False},
        "evidence_reference": "ml/data/labels/annotation_pilot/figures/seafar/sample.png",
        "reviewer_notes": "Quan sát unit fixture; chỉ kiểm tra schema.", "review_status": "ACCEPTED",
        "review_timestamp_utc": "2026-11-17T10:00:00Z"}
    first = save_human_decision(tmp_path, review_id, reviewer_id="reviewer-a", **common)
    assert first["label_status"] == "HUMAN_REVIEWED"
    assert first["review_id"] == review_id
    assert first["annotation_schema_version"] == ANNOTATION_SCHEMA_VERSION
    ledger_path = tmp_path / "ml/data/labels/annotation_pilot/review_decisions.csv"
    audit_path = tmp_path / "ml/data/labels/annotation_pilot/review_audit.jsonl"
    assert len(pd.read_csv(ledger_path)) == 1
    assert len(audit_path.read_text(encoding="utf-8").splitlines()) == 1
    with pytest.raises(ValueError, match="không ghi đè"):
        save_human_decision(tmp_path, review_id, reviewer_id="reviewer-a", **common)
    second = save_human_decision(tmp_path, review_id, reviewer_id="reviewer-b", **{
        **common, "reviewer_decision": "PERSISTENT_OFFSET", "phenotype_flags": {
            "HIGH_ROLL": False, "PERSISTENT_OFFSET": True, "AMPLITUDE_GROWTH": False},
        "review_timestamp_utc": "2026-11-17T10:05:00Z"})
    assert second["label_status"] == "HUMAN_REVIEWED"
    assert len(pd.read_csv(ledger_path)) == 2
    ledger_path.unlink()
    recovered = recover_decision_ledger(tmp_path)
    assert len(recovered) == 2
    assert len(audit_path.read_text(encoding="utf-8").splitlines()) == 2
    assert recovered.decision_id.nunique() == 2


def test_quality_summary_counts_actual_reviews_and_reports_conflicting_reviewers(tmp_path):
    output = tmp_path / "ml/data/labels/annotation_pilot"
    output.mkdir(parents=True)
    forms = _make_forms()
    forms.to_csv(output / "annotation_pilot.csv", index=False)
    review_id = forms.iloc[4].review_sample_id
    common = {"evidence_category": "OBSERVED_MOTION_PHENOTYPE",
        "evidence_reference": "ml/data/labels/annotation_pilot/figures/hohai/sample.png",
        "reviewer_notes": "Fixture unit test.", "review_status": "ACCEPTED"}
    save_human_decision(tmp_path, review_id, reviewer_id="r1", reviewer_decision="HIGH_ROLL",
        phenotype_flags={"HIGH_ROLL": True, "PERSISTENT_OFFSET": False, "AMPLITUDE_GROWTH": False},
        review_timestamp_utc="2026-11-17T10:00:00Z", **common)
    save_human_decision(tmp_path, review_id, reviewer_id="r2", reviewer_decision="PERSISTENT_OFFSET",
        phenotype_flags={"HIGH_ROLL": False, "PERSISTENT_OFFSET": True, "AMPLITUDE_GROWTH": False},
        review_timestamp_utc="2026-11-17T10:01:00Z", **common)
    summary = build_quality_summary(tmp_path, forms)
    assert summary["reviewed_decisions"] == 2
    assert summary["reviewed_samples"] == 1
    assert summary["unreviewed_samples"] == 91
    assert len(summary["conflicting_review_ids"]) == 1
    assert summary["inter_reviewer_agreement"]["status"] == "CALCULATED_ON_PAIRED_HUMAN_DECISIONS"
