import copy
import json

import pandas as pd
import pytest

from ml.labeling.annotations import apply_external_annotations, load_external_annotations
from ml.labeling.feasibility import load_eligible_windows
from ml.labeling.provenance import audit_event
from ml.labeling.review import append_review_event, build_review_queue, promote_review_record, validate_review_decision
from ml.labeling.rules import classify_candidate
from ml.labeling.schemas import ANGLE_ONLY_23
from ml.labeling.validation import validate_label_record


def default_config(mode="feasibility"):
    return {"labeling": {"mode": mode, "rule_version": "test_v1", "primary_class_policy": "REVIEW_REQUIRED",
            "primary_class_priority": ["HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH"],
            "rules": {"HIGH_ROLL": {"enabled": False, "dataset_scope": ["seafar"], "roll_std_60_deg": None, "evidence_reference": None},
                      "PERSISTENT_OFFSET": {"enabled": False, "abs_roll_mean_180_deg": None, "dominant_sign_ratio_min": None, "evidence_reference": None},
                      "AMPLITUDE_GROWTH": {"enabled": False, "roll_rms_slope_180_deg_per_min": None, "trend_r2_min": None, "evidence_reference": None},
                      "NORMAL": {"enabled": False, "roll_std_60_max_deg": None, "abs_roll_mean_180_max_deg": None, "evidence_reference": None}}}}


def row(**updates):
    values = {"dataset_source": "seafar", "roll_std_60": .2, "roll_mean_180": 0.0, "roll_dominant_sign_ratio_180": .7,
              "roll_rms_slope_180": 0.0, "roll_rms_trend_r2_180": .5}
    values.update(updates)
    return values


def test_feasibility_never_assigns_normal_by_absence():
    result = classify_candidate(row(), default_config())
    assert result["label"] == "UNLABELED"
    assert result["label_source"] == "UNKNOWN"


def test_high_roll_boundary_and_proxy_provenance():
    config = default_config("exploratory_proxy")
    config["labeling"]["rules"]["HIGH_ROLL"] = {"enabled": True, "dataset_scope": ["seafar"], "roll_std_60_deg": .2, "evidence_reference": "reviewed-spec-v1"}
    result = classify_candidate(row(), config)
    assert result["label"] == "HIGH_ROLL"
    assert result["label_status"] == "PROXY"
    assert result["label_source"] == "PROXY_RULE"


def test_enabled_rule_requires_threshold_and_reference():
    config = default_config("exploratory_proxy")
    config["labeling"]["rules"]["HIGH_ROLL"]["dataset_scope"] = ["seafar"]
    config["labeling"]["rules"]["HIGH_ROLL"]["enabled"] = True
    with pytest.raises(ValueError, match="ngưỡng"):
        classify_candidate(row(), config)


def test_rule_threshold_cannot_leak_across_dataset_scales():
    config = default_config("exploratory_proxy")
    config["labeling"]["rules"]["HIGH_ROLL"] = {"enabled": True, "dataset_scope": ["seafar"],
        "roll_std_60_deg": .2, "evidence_reference": "reference"}
    with pytest.raises(ValueError, match="dataset_scope"):
        classify_candidate(row(dataset_source="hohai"), config)


def test_multiple_phenotypes_preserved_and_review_required():
    config = default_config("exploratory_proxy")
    config["labeling"]["rules"]["HIGH_ROLL"] = {"enabled": True, "dataset_scope": ["seafar"], "roll_std_60_deg": .1, "evidence_reference": "ref"}
    config["labeling"]["rules"]["PERSISTENT_OFFSET"] = {"enabled": True, "dataset_scope": ["seafar"], "abs_roll_mean_180_deg": .1,
        "dominant_sign_ratio_min": .6, "evidence_reference": "ref"}
    result = classify_candidate(row(roll_mean_180=.2), config)
    flags = json.loads(result["phenotype_flags_json"])
    assert result["label"] == "REVIEW_REQUIRED"
    assert flags["HIGH_ROLL"] == flags["PERSISTENT_OFFSET"] == "CANDIDATE"


def test_priority_does_not_discard_flags():
    config = default_config("exploratory_proxy")
    config["labeling"]["primary_class_policy"] = "PRIORITY"
    config["labeling"]["rules"]["HIGH_ROLL"] = {"enabled": True, "dataset_scope": ["seafar"], "roll_std_60_deg": .1, "evidence_reference": "ref"}
    config["labeling"]["rules"]["PERSISTENT_OFFSET"] = {"enabled": True, "dataset_scope": ["seafar"], "abs_roll_mean_180_deg": .1,
        "dominant_sign_ratio_min": .6, "evidence_reference": "ref"}
    result = classify_candidate(row(roll_mean_180=.2), config)
    assert result["label"] == "HIGH_ROLL"
    assert "Nhiều phenotype" in result["ambiguity_reason"]
    assert json.loads(result["phenotype_flags_json"])["PERSISTENT_OFFSET"] == "CANDIDATE"


def test_normal_requires_positive_envelope_evidence():
    config = default_config("exploratory_proxy")
    config["labeling"]["rules"]["NORMAL"] = {"enabled": True, "dataset_scope": ["seafar"], "roll_std_60_max_deg": .3,
        "abs_roll_mean_180_max_deg": .1, "evidence_reference": "accepted-operating-envelope"}
    result = classify_candidate(row(), config)
    assert result["label"] == "NORMAL"
    assert result["label_status"] == "PROXY"


def test_causal_identity_window_and_no_session_merge(tmp_path):
    dataset = "seafar"
    d = tmp_path / dataset
    d.mkdir()
    vals = pd.DataFrame({"window_id": ["a", "b"], **{name: [1.0, 1.0] for name in ANGLE_ONLY_23}})
    statuses = {name: {"status": "VALID"} for name in ANGLE_ONLY_23}
    statuses[ANGLE_ONLY_23[0]] = {"status": "INVALID_INPUT"}
    meta = pd.DataFrame({"window_id": ["a", "b"], "dataset_source": [dataset, dataset],
                         "session_id": ["s1", "s2"], "segment_id": ["g1", "g2"],
                         "window_end_seconds": [180.0, 180.0],
                         "validity_json": [json.dumps({name: {"status": "VALID"} for name in ANGLE_ONLY_23}),
                                           json.dumps(statuses)]})
    vals.to_parquet(d / "feature_values.parquet")
    meta.to_parquet(d / "feature_metadata.parquet")
    eligible = load_eligible_windows(tmp_path, (dataset,))[dataset]
    assert len(eligible) == 1
    assert eligible.iloc[0].session_id == "s1"
    assert eligible.iloc[0].window_start_seconds == 0.0
    assert eligible.iloc[0].window_end_seconds == 180.0


def test_deterministic_review_queue_and_no_fake_review():
    data = pd.DataFrame([{"session_id": "s1", "segment_id": "g1", "window_end_seconds": x,
                          "window_start_seconds": x - 180} for x in (180, 190, 200, 210, 220)])
    first = build_review_queue({"seafar": data}, 3)
    second = build_review_queue({"seafar": data}, 3)
    pd.testing.assert_frame_equal(first, second)
    assert list(first.window_end) == [180.0, 200.0, 220.0]
    assert first.reviewer_decision.eq("").all()
    assert first.queue_stratum.eq("UNLABELED").all()


def test_review_queue_stratifies_available_proxy_and_conflict_cases():
    data = pd.DataFrame([{"window_id": f"w{i}", "dataset_source": "seafar", "session_id": "s1", "segment_id": "g1",
                          "window_end_seconds": 180 + i * 10, "window_start_seconds": i * 10} for i in range(4)])
    labels = pd.DataFrame({"dataset_source": ["seafar"] * 4, "session_id": ["s1"] * 4,
        "segment_id": ["g1"] * 4, "window_start_seconds": [i * 10 for i in range(4)],
        "window_end_seconds": [180 + i * 10 for i in range(4)],
        "label": ["HIGH_ROLL", "REVIEW_REQUIRED", "UNLABELED", "UNLABELED"],
        "label_status": ["PROXY", "REVIEW_REQUIRED", "UNLABELED", "UNLABELED"],
        "ambiguity_reason": [None, "overlap", None, None]})
    queue = build_review_queue({"seafar": data}, 1, {"seafar": labels})
    assert set(queue.queue_stratum) == {"CLEAR_PROXY_CANDIDATE", "CONFLICTING_PHENOTYPES", "UNLABELED"}


def test_borderline_queue_requires_explicit_configured_margin():
    data = pd.DataFrame([{"dataset_source": "seafar", "session_id": "s1", "segment_id": "g1",
        "window_start_seconds": 0, "window_end_seconds": 180, "roll_std_60": .99}])
    labels = pd.DataFrame([{"dataset_source": "seafar", "session_id": "s1", "segment_id": "g1",
        "window_start_seconds": 0, "window_end_seconds": 180, "label": "UNLABELED",
        "label_status": "UNLABELED", "ambiguity_reason": None}])
    rules = {"review_borderline_relative_margin": .02,
        "rules": {"HIGH_ROLL": {"enabled": True, "dataset_scope": ["seafar"],
                                  "roll_std_60_deg": 1.0, "evidence_reference": "reference"}}}
    queue = build_review_queue({"seafar": data}, 1, {"seafar": labels}, rules)
    assert queue.iloc[0].queue_stratum == "BORDERLINE_CASE"


def test_proxy_cannot_be_promoted_to_verified():
    record = {"dataset_source": "seafar", "session_id": "s", "segment_id": "g",
              "window_start_seconds": 0, "window_end_seconds": 180, "label": "HIGH_ROLL",
              "label_status": "VERIFIED", "label_source": "PROXY_RULE", "labeling_method": "rule",
              "rule_version": "v1", "evidence_reference": "rule", "review_status": "PENDING"}
    with pytest.raises(ValueError, match="external reference"):
        validate_label_record(record)


def test_review_record_promotion_is_human_review_only():
    record = {"dataset": "seafar", "session": "s", "segment": "g", "window_start": 0,
              "window_end": 180, "suggested_label": "UNLABELED", "reviewer_decision": "HIGH_ROLL",
              "reviewer_notes": "review evidence", "review_timestamp": "2026-01-01T00:00:00Z",
              "review_status": "ACCEPTED"}
    output = promote_review_record(record, "reviewer-1")
    assert output["label_status"] == "HUMAN_REVIEWED"
    assert output["label_source"] == "HUMAN_REVIEW"
    assert output["evidence_reference"] == "reviewer:reviewer-1"


def test_review_acceptance_requires_timestamp():
    record = {"reviewer_decision": "NORMAL", "review_status": "ACCEPTED", "review_timestamp": ""}
    with pytest.raises(ValueError, match="review_timestamp"):
        validate_review_decision(record)


def test_audit_event_preserves_before_after():
    event = audit_event({"label": "UNLABELED"}, {"label": "HIGH_ROLL"}, "r1", "t")
    assert event["previous"]["label"] == "UNLABELED"
    assert event["replacement"]["label"] == "HIGH_ROLL"
    assert event["reviewer_id"] == "r1"


def test_review_audit_is_append_only(tmp_path):
    path = tmp_path / "review_audit.jsonl"
    old = {"dataset_source": "seafar", "session_id": "s", "segment_id": "g", "window_start_seconds": 0,
           "window_end_seconds": 180, "label": "UNLABELED", "label_status": "UNLABELED", "label_source": "UNKNOWN",
           "labeling_method": "feasibility", "rule_version": "v1", "review_status": "NOT_REVIEWED"}
    new = {**old, "label": "HIGH_ROLL", "label_status": "HUMAN_REVIEWED", "label_source": "HUMAN_REVIEW",
           "labeling_method": "manual_review", "evidence_reference": "reviewer:r1", "review_status": "ACCEPTED"}
    append_review_event(path, old, new, "r1", "t1")
    newer = {**new, "label": "REVIEW_REQUIRED", "review_status": "NEEDS_DISCUSSION"}
    append_review_event(path, new, newer, "r2", "t2")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["reviewer_id"] == "r1"
    assert json.loads(lines[1])["reviewer_id"] == "r2"


def test_external_reference_requires_evidence_and_exact_window(tmp_path):
    source = tmp_path / "external.csv"
    pd.DataFrame([{"dataset_source": "seafar", "session_id": "s", "segment_id": "g",
                   "window_start_seconds": 0, "window_end_seconds": 180, "label": "HIGH_ROLL",
                   "evidence_reference": "event-log-7"}]).to_csv(source, index=False)
    external = load_external_annotations(source)
    assert external.iloc[0].label_status == "VERIFIED"
    base = {"dataset_source": "seafar", "session_id": "s", "segment_id": "g",
            "window_start_seconds": 0.0, "window_end_seconds": 180.0, "label": "UNLABELED",
            "label_status": "UNLABELED", "label_source": "UNKNOWN", "labeling_method": "feasibility",
            "rule_version": "v1", "evidence_reference": None, "review_status": "NOT_REVIEWED",
            "ambiguity_reason": None, "quality_flags": "[]", "phenotype_flags_json": "{}", "suggested_label": None}
    candidate = pd.DataFrame([base])
    applied = apply_external_annotations(candidate, external)
    assert applied.iloc[0].label == "HIGH_ROLL"
    assert applied.iloc[0].label_status == "VERIFIED"
    unmatched = external.copy()
    unmatched.loc[0, "session_id"] = "different-session"
    with pytest.raises(ValueError, match="không khớp"):
        apply_external_annotations(candidate, unmatched)


def test_external_reference_without_evidence_is_rejected(tmp_path):
    source = tmp_path / "external.csv"
    pd.DataFrame([{"dataset_source": "seafar", "session_id": "s", "segment_id": "g",
                   "window_start_seconds": 0, "window_end_seconds": 180, "label": "NORMAL",
                   "evidence_reference": ""}]).to_csv(source, index=False)
    with pytest.raises(ValueError, match="external reference"):
        load_external_annotations(source)
