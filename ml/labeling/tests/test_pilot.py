from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from ml.labeling.pilot import prepare_annotation_pilot
from ml.labeling.pilot_decisions import (append_annotation_revision, materialize_decisions,
                                         validate_decision_ledger)
from ml.labeling.agreement import inter_reviewer_agreement
from ml.labeling.pilot_schema import (
    PILOT_COLUMNS,
    derive_pilot_status,
    empty_phenotype_flags,
    validate_pilot_annotation,
)


def make_record(**overrides):
    record = {
        "review_sample_id": "PILOT-test",
        "dataset_source": "seafar",
        "session_id": "session-a",
        "segment_id": "segment-1",
        "window_start_seconds": 180.0,
        "window_end_seconds": 360.0,
        "context_start_seconds": 0.0,
        "context_end_seconds": 180.0,
        "context_available_seconds": 180.0,
        "context_coverage_fraction": 1.0,
        "plot_path": "figure.png",
        "experiment_metadata_json": "{}",
        "experiment_metadata_reference": "",
        "quality_flags_json": "[]",
        "queue_suggested_label": "UNLABELED",
        "evidence_category": "UNVERIFIED",
        "evidence_reference": "",
        "reviewer_id": "",
        "reviewer_decision": "",
        "phenotype_flags_json": empty_phenotype_flags(),
        "reviewer_notes": "",
        "review_timestamp_utc": "",
        "review_status": "PENDING",
        "label_status": "UNLABELED",
        "label_source": "UNKNOWN",
        "ambiguity_reason": "",
    }
    record.update(overrides)
    return record


def _write_minimal_pilot_inputs(root: Path, *, queue_end: float = 360.0,
                                metadata_end: float = 360.0) -> None:
    dataset, session, segment = "seafar", "session-a", "segment-1"
    processed = root / "ml/data/processed/seafar/session-a/segment-1"
    processed.mkdir(parents=True, exist_ok=True)
    time_seconds = pd.Series(range(0, 3610, 1), dtype="float64") / 10.0
    pd.DataFrame({
        "dataset_source": dataset,
        "session_id": session,
        "segment_id": segment,
        "time_seconds": time_seconds,
        "roll_deg": 2.0 * (time_seconds % 10.0),
        "pitch_deg": 0.5 * (time_seconds % 10.0),
    }).to_parquet(processed / "timeseries.parquet", index=False)
    (processed / "provenance.json").write_text(json.dumps({
        "dataset_source": dataset,
        "session_id": session,
        "segment_id": segment,
        "target_sampling_hz_effective": 10.0,
        "raw_reference": "ml/data/raw/seafar/cleaned_imu_gps_data.json",
        "warnings": [],
    }), encoding="utf-8")
    metadata_dir = root / "ml/data/features/seafar"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{
        "session_id": session,
        "segment_id": segment,
        "window_end_seconds": metadata_end,
        "validity_json": "{}",
        "source_metadata_json": "{}",
    }]).to_parquet(metadata_dir / "feature_metadata.parquet", index=False)
    queue_dir = root / "ml/data/labels"
    queue_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{
        "dataset": dataset,
        "session": session,
        "segment": segment,
        "window_start": queue_end - 180.0,
        "window_end": queue_end,
        "suggested_label": "UNLABELED",
        "queue_stratum": "unlabeled",
        "evidence": "",
        "reviewer_decision": "",
        "reviewer_notes": "",
        "review_timestamp": "",
        "review_status": "PENDING",
    }]).to_csv(queue_dir / "review_queue.csv", index=False)


def test_pending_annotation_cannot_be_promoted_to_verified_or_human_reviewed():
    base = make_record()
    validate_pilot_annotation(base)
    invalid_verified = make_record(evidence_category="UNVERIFIED", label_status="VERIFIED",
                                   label_source="EXTERNAL_REFERENCE", evidence_reference="ref")
    with pytest.raises(ValueError, match="VERIFIED cần evidence"):
        validate_pilot_annotation(invalid_verified)
    invalid_human = make_record(label_status="HUMAN_REVIEWED", label_source="HUMAN_REVIEW")
    with pytest.raises(ValueError, match="chưa ACCEPTED"):
        validate_pilot_annotation(invalid_human)


def test_observed_phenotype_requires_actual_acceptance_and_preserves_overlap():
    pending = make_record(evidence_category="OBSERVED_MOTION_PHENOTYPE")
    accepted = {
        **pending,
        "reviewer_id": "reviewer-1",
        "reviewer_decision": "HIGH_ROLL",
        "phenotype_flags_json": json.dumps({
            "HIGH_ROLL": True,
            "PERSISTENT_OFFSET": True,
            "AMPLITUDE_GROWTH": None,
        }),
        "review_timestamp_utc": "2026-11-17T10:00:00Z",
        "review_status": "ACCEPTED",
        "label_status": "HUMAN_REVIEWED",
        "label_source": "HUMAN_REVIEW",
        "ambiguity_reason": "Hai phenotype cùng xuất hiện trong cửa sổ.",
    }
    validate_pilot_annotation(accepted)
    without_reason = {**accepted, "ambiguity_reason": ""}
    with pytest.raises(ValueError, match="chồng lấn"):
        validate_pilot_annotation(without_reason)
    assert json.loads(accepted["phenotype_flags_json"])["PERSISTENT_OFFSET"] is True


def test_verified_normal_requires_positive_envelope_reference():
    candidate = make_record(
        evidence_category="VERIFIED_NORMAL_ENVELOPE",
        evidence_reference="operating-envelope-v1",
        reviewer_id="reviewer-1",
        reviewer_decision="NORMAL",
        review_timestamp_utc="2026-11-17T10:00:00Z",
        review_status="ACCEPTED",
    )
    normalized = derive_pilot_status(candidate)
    assert normalized["label_status"] == "VERIFIED"
    assert normalized["label_source"] == "EXTERNAL_REFERENCE"


def test_revision_audit_is_append_only_and_keeps_sample_identity(tmp_path):
    previous = make_record()
    replacement = {
        **previous,
        "evidence_category": "OBSERVED_MOTION_PHENOTYPE",
        "reviewer_id": "reviewer-1",
        "reviewer_decision": "HIGH_ROLL",
        "phenotype_flags_json": json.dumps({"HIGH_ROLL": True, "PERSISTENT_OFFSET": False,
                                             "AMPLITUDE_GROWTH": False}),
        "review_timestamp_utc": "2026-11-17T10:00:00Z",
        "review_status": "ACCEPTED",
        "label_status": "HUMAN_REVIEWED",
        "label_source": "HUMAN_REVIEW",
    }
    path = tmp_path / "review_audit.jsonl"
    event = append_annotation_revision(path, previous, replacement, "reviewer-1")
    assert event["previous"] == previous
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[0])["replacement"] == replacement
    changed_identity = {**replacement, "session_id": "other-session"}
    with pytest.raises(ValueError, match="danh tính"):
        append_annotation_revision(path, previous, changed_identity, "reviewer-1")
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1


def test_decision_ledger_rejects_unknown_samples_and_duplicate_reviewer_rows():
    columns = ["review_sample_id", "reviewer_id", "reviewer_decision", "phenotype_flags_json",
               "evidence_category", "evidence_reference", "reviewer_notes", "review_timestamp_utc",
               "review_status", "ambiguity_reason"]
    row = {column: "" for column in columns}
    row.update({"review_sample_id": "unknown", "reviewer_id": "r1", "reviewer_decision": "HIGH_ROLL",
                "phenotype_flags_json": empty_phenotype_flags(), "evidence_category": "UNVERIFIED",
                "review_timestamp_utc": "2026-11-17T10:00:00Z", "review_status": "ACCEPTED"})
    with pytest.raises(ValueError, match="không thuộc pilot"):
        validate_decision_ledger(pd.DataFrame([row], columns=columns), {"valid"})
    row["review_sample_id"] = "valid"
    with pytest.raises(ValueError, match="một bản ghi"):
        validate_decision_ledger(pd.DataFrame([row, row], columns=columns), {"valid"})
    with pytest.raises(ValueError, match="UNVERIFIED không đủ"):
        validate_decision_ledger(pd.DataFrame([row], columns=columns), {"valid"})


def test_proxy_and_unverified_decisions_keep_their_evidence_status():
    pending_proxy = make_record(evidence_category="PROXY_RULE")
    with pytest.raises(ValueError, match="evidence_reference"):
        derive_pilot_status(pending_proxy)
    pending_proxy["evidence_reference"] = "rule-config-v1"
    proxy = derive_pilot_status(pending_proxy)
    assert proxy["label_status"] == "PROXY"
    assert proxy["label_source"] == "PROXY_RULE"
    with pytest.raises(ValueError, match="UNVERIFIED không đủ"):
        derive_pilot_status(make_record(
            reviewer_id="reviewer-1", reviewer_decision="HIGH_ROLL",
            review_timestamp_utc="2026-11-17T10:00:00Z", review_status="ACCEPTED"))


def test_real_decision_ledger_materializes_as_reviewed_phenotype():
    form = make_record()
    decision = {
        "review_sample_id": form["review_sample_id"], "reviewer_id": "reviewer-1",
        "reviewer_decision": "HIGH_ROLL", "phenotype_flags_json": json.dumps({
            "HIGH_ROLL": True, "PERSISTENT_OFFSET": False, "AMPLITUDE_GROWTH": False}),
        "evidence_category": "OBSERVED_MOTION_PHENOTYPE", "evidence_reference": "",
        "reviewer_notes": "Quan sát thử nghiệm unit.", "review_timestamp_utc": "2026-11-17T10:00:00Z",
        "review_status": "ACCEPTED", "ambiguity_reason": "",
    }
    materialized = materialize_decisions(pd.DataFrame([form]), pd.DataFrame([decision]))
    assert materialized.iloc[0].label_status == "HUMAN_REVIEWED"
    assert materialized.iloc[0].label_source == "HUMAN_REVIEW"
    assert materialized.iloc[0].evidence_category == "OBSERVED_MOTION_PHENOTYPE"


def test_inter_reviewer_agreement_requires_paired_actual_reviews():
    empty = pd.DataFrame(columns=["review_sample_id", "reviewer_id", "reviewer_decision", "review_status",
                                  "phenotype_flags_json"])
    assert inter_reviewer_agreement(empty)["status"] == "NOT_CALCULATED"
    flags = json.dumps({"HIGH_ROLL": True, "PERSISTENT_OFFSET": False, "AMPLITUDE_GROWTH": None})
    paired = pd.DataFrame([
        {"review_sample_id": "s1", "reviewer_id": "r1", "reviewer_decision": "HIGH_ROLL",
         "review_status": "ACCEPTED", "phenotype_flags_json": flags},
        {"review_sample_id": "s1", "reviewer_id": "r2", "reviewer_decision": "HIGH_ROLL",
         "review_status": "ACCEPTED", "phenotype_flags_json": flags},
    ])
    result = inter_reviewer_agreement(paired)
    assert result["status"] == "CALCULATED_ON_PAIRED_HUMAN_DECISIONS"
    assert result["pairwise_results"][0]["overlapping_samples"] == 1
    assert result["pairwise_results"][0]["exact_agreement"] == 1.0


def test_session_window_matching_and_pilot_generation_are_reproducible(tmp_path):
    _write_minimal_pilot_inputs(tmp_path)
    queue = tmp_path / "ml/data/labels/review_queue.csv"
    output_a = tmp_path / "ml/data/labels/pilot-a"
    output_b = tmp_path / "ml/data/labels/pilot-b"
    forms_a, summary_a = prepare_annotation_pilot(tmp_path, queue, output_a, dpi=30)
    forms_b, summary_b = prepare_annotation_pilot(tmp_path, queue, output_b, dpi=30)
    assert tuple(forms_a.columns) == PILOT_COLUMNS
    assert forms_a.review_sample_id.tolist() == forms_b.review_sample_id.tolist()
    assert forms_a.loc[0, "window_start_seconds"] == 180.0
    assert forms_a.loc[0, "window_end_seconds"] == 360.0
    assert forms_a.loc[0, "context_available_seconds"] == pytest.approx(180.0)
    assert (tmp_path / forms_a.loc[0, "plot_path"]).is_file()
    assert summary_a["pilot_samples"] == summary_b["pilot_samples"] == 1


def test_queue_window_must_match_feature_metadata_exactly(tmp_path):
    _write_minimal_pilot_inputs(tmp_path, queue_end=359.0)
    queue = tmp_path / "ml/data/labels/review_queue.csv"
    with pytest.raises(ValueError, match="không khớp duy nhất"):
        prepare_annotation_pilot(tmp_path, queue, tmp_path / "out", dpi=30)
    rows = pd.read_csv(queue)
    rows.loc[0, "window_end"] = 361.0
    rows.loc[0, "window_start"] = 181.0
    rows.to_csv(queue, index=False)
    with pytest.raises(ValueError, match="không khớp duy nhất"):
        prepare_annotation_pilot(tmp_path, queue, tmp_path / "out2", dpi=30)
