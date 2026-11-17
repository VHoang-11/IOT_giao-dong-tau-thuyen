from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.labeling.ai_assisted_review import PROTECTED_PATHS, protected_checksums
from ml.labeling.proxy_rules import (ABSTAIN, NEG, POS, apply_rules, fit_calibration, load_spec,
                                     session_weighted_quantile, window_statistics)
from ml.train.grouping import audit_split, experiment_group, inner_group_folds, leave_one_group_out
from ml.train.predict import predict_frame
from ml.train.rf_poc import FEATURE_ORDER, feature_schema, make_model, serialize_model, validate_feature_frame

REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC = load_spec(REPO_ROOT / "ml/labeling/proxy_spec.yaml")
PROXY_ROOT = REPO_ROOT / "ml/data/labels/proxy_v1"


def _row(window_id, group, s60=0.3, log_ratio=0.0, pattern="+-+-+-+-+", sign_ratio=0.5, dataset="hohai", **extra):
    row = {"window_id": window_id, "dataset_source": dataset, "session_id": f"{group}-s", "experiment_group": group,
           "angle23_complete": True, "statistics_valid": True, "roll_std_60": s60, "log_centered_std_ratio": log_ratio,
           "sub_block_mean_sign_pattern": pattern,
           "sub_block_mean_sign_changes": sum(a != b for a, b in zip(pattern, pattern[1:])),
           "roll_dominant_sign_ratio_180_stat": sign_ratio, "context_coverage_ok": True, "context_all_same_sign": False,
           "monotonic_centered_blocks": False, "context_fraction": 1.0, "late_block_exceeds_context": False}
    row.update(extra)
    return row


def _synthetic(n_groups=4, per_group=20):
    rows = []
    for g in range(n_groups):
        for i in range(per_group):
            rows.append(_row(f"w{g}-{i}", f"hohai|T{g}", s60=0.1 + 0.02 * i, log_ratio=0.01 * i))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ rule & calibration


def test_proxy_rules_are_deterministic():
    data = _synthetic()
    cal = fit_calibration(data, ["hohai|T0", "hohai|T1", "hohai|T2"], SPEC)
    first, second = apply_rules(data, cal, SPEC), apply_rules(data, cal, SPEC)
    pd.testing.assert_frame_equal(first, second)
    assert cal["calibration_id"] == fit_calibration(data, ["hohai|T2", "hohai|T1", "hohai|T0"], SPEC)["calibration_id"]


def test_calibration_uses_training_groups_only():
    data = _synthetic()
    train = ["hohai|T0", "hohai|T1", "hohai|T2"]
    base = fit_calibration(data, train, SPEC)
    poisoned = data.copy()
    poisoned.loc[poisoned.experiment_group.eq("hohai|T3"), ["roll_std_60", "log_centered_std_ratio"]] = 99.0
    after = fit_calibration(poisoned, train, SPEC)
    assert base["domains"]["hohai"]["RELATIVE_HIGH_ROLL"] == after["domains"]["hohai"]["RELATIVE_HIGH_ROLL"]
    assert base["domains"]["hohai"]["train_groups"] == train


def test_session_weighted_quantile_gives_each_session_equal_weight():
    values = np.array([0.0] * 100 + [10.0])
    sessions = np.array(["a"] * 100 + ["b"])
    assert session_weighted_quantile(values, sessions, 0.75) == 10.0


def test_abstain_band_uncalibrated_domain_and_no_proxy_triggered():
    data = _synthetic()
    cal = fit_calibration(data, ["hohai|T0", "hohai|T1", "hohai|T2"], SPEC)
    t = cal["domains"]["hohai"]["RELATIVE_HIGH_ROLL"]
    mid = (t["positive_threshold"] + t["negative_threshold"]) / 2
    rows = pd.DataFrame([_row("band", "hohai|T3", s60=mid),
                         _row("quiet", "hohai|T3", s60=0.0, log_ratio=-1.0),
                         _row("seafar", "seafar|s1", dataset="seafar")])
    out = apply_rules(rows, cal, SPEC).set_index("window_id")
    assert out.loc["band", "RELATIVE_HIGH_ROLL_status"] == ABSTAIN
    assert out.loc["band", "RELATIVE_HIGH_ROLL_reason"] == "BOUNDARY_BAND"
    assert out.loc["quiet", "proxy_window_status"] == "NO_PROXY_TRIGGERED"
    assert out.loc["seafar", "RELATIVE_HIGH_ROLL_status"] == ABSTAIN
    assert out.loc["seafar", "AMPLITUDE_GROWTH_reason"].startswith("SINGLE_SESSION")
    assert out.loc["seafar", "proxy_window_status"] == "ABSTAIN"


def test_multi_label_keeps_every_positive_phenotype():
    data = _synthetic()
    cal = fit_calibration(data, ["hohai|T0", "hohai|T1", "hohai|T2"], SPEC)
    row = _row("both", "hohai|T3", s60=10.0, pattern="+" * 9, sign_ratio=1.0, context_all_same_sign=True)
    out = apply_rules(pd.DataFrame([row]), cal, SPEC).iloc[0]
    assert out.RELATIVE_HIGH_ROLL_status == POS and out.PERSISTENT_OFFSET_status == POS
    assert out.multi_label and json.loads(out.proxy_phenotypes) == ["RELATIVE_HIGH_ROLL", "PERSISTENT_OFFSET"]
    assert out.offset_reference == "SENSOR_DATUM_UNVERIFIED" and not bool(out.physical_heel_claim)


def test_offset_without_context_or_crossing_datum_abstains():
    data = _synthetic()
    cal = fit_calibration(data, ["hohai|T0", "hohai|T1", "hohai|T2"], SPEC)
    rows = pd.DataFrame([_row("noctx", "hohai|T3", pattern="+" * 9, sign_ratio=1.0, context_coverage_ok=False),
                         _row("cross", "hohai|T3", pattern="+" * 9, sign_ratio=0.8),
                         _row("neg", "hohai|T3", pattern="++++-++++", sign_ratio=0.8)])
    out = apply_rules(rows, cal, SPEC).set_index("window_id")
    assert out.loc["noctx", "PERSISTENT_OFFSET_status"] == ABSTAIN
    assert out.loc["cross", "PERSISTENT_OFFSET_reason"] == "SIGNED_BIAS_BUT_OSCILLATION_CROSSES_DATUM"
    assert out.loc["neg", "PERSISTENT_OFFSET_status"] == NEG


def test_growth_requires_temporal_consistency_not_ratio_alone():
    data = _synthetic()
    cal = fit_calibration(data, ["hohai|T0", "hohai|T1", "hohai|T2"], SPEC)
    high = cal["domains"]["hohai"]["AMPLITUDE_GROWTH"]["positive_threshold"] + 1.0
    rows = pd.DataFrame([_row("ratio_only", "hohai|T3", log_ratio=high),
                         _row("transient", "hohai|T3", log_ratio=high, monotonic_centered_blocks=True),
                         _row("sustained", "hohai|T3", log_ratio=high, monotonic_centered_blocks=True,
                              late_block_exceeds_context=True)])
    out = apply_rules(rows, cal, SPEC).set_index("window_id")
    assert out.loc["ratio_only", "AMPLITUDE_GROWTH_reason"] == "HIGH_RATIO_NOT_MONOTONIC"
    assert out.loc["transient", "AMPLITUDE_GROWTH_reason"] == "HIGH_RATIO_NOT_ABOVE_RECENT_HISTORY"
    assert out.loc["sustained", "AMPLITUDE_GROWTH_status"] == POS


def test_missing_or_invalid_signals_abstain():
    data = _synthetic()
    cal = fit_calibration(data, ["hohai|T0", "hohai|T1", "hohai|T2"], SPEC)
    rows = pd.DataFrame([_row("incomplete", "hohai|T3", angle23_complete=False),
                         _row("invalid", "hohai|T3", statistics_valid=False)])
    out = apply_rules(rows, cal, SPEC).set_index("window_id")
    assert set(out.loc["incomplete", [f"{t}_reason" for t in SPEC["targets"]]]) == {"INCOMPLETE_ANGLE_FEATURES"}
    assert set(out.loc["invalid", [f"{t}_status" for t in SPEC["targets"]]]) == {ABSTAIN}


# ------------------------------------------------------------------ causal windows


def test_window_statistics_ignore_samples_after_endpoint():
    t = np.round(np.arange(0.1, 500.0, 0.1), 6)
    rng = np.random.default_rng(0)
    roll = np.sin(2 * np.pi * t / 1.8) + 0.01 * rng.standard_normal(len(t))
    end = 400.0
    base = window_statistics(t, roll, end, float(t[0]), float(t[-1]), SPEC)
    future = roll.copy()
    future[t > end] = 50.0
    changed = window_statistics(t, future, end, float(t[0]), float(t[-1]), SPEC)
    for key, value in base.items():
        if key != "seconds_after_endpoint_in_segment" and key != "near_segment_end_audit":
            assert changed[key] == value or (isinstance(value, float) and math.isnan(value) and math.isnan(changed[key]))
    assert base["statistics_valid"]


def test_window_with_gap_is_invalid():
    t = np.round(np.arange(0.1, 400.0, 0.1), 6)
    keep = ~((t > 300) & (t < 302))
    stats = window_statistics(t[keep], np.sin(t[keep]), 380.0, 0.1, 399.9, SPEC)
    assert not stats["statistics_valid"]


# ------------------------------------------------------------------ grouping & leakage


def test_hohai_group_is_test_condition_not_session():
    assert experiment_group("hohai", "Berth_D_T8_Type_A") == experiment_group("hohai", "Berth_B_T8_Type_A") == "hohai|T8"
    assert experiment_group("seafar", "seafar_session_001") == "seafar|seafar_session_001"
    with pytest.raises(ValueError):
        experiment_group("hohai", "unknown_sheet")


def test_outer_and_inner_folds_isolate_groups():
    groups = pd.Series([f"g{i % 5}" for i in range(50)])
    folds = leave_one_group_out(groups)
    assert len(folds) == 5
    for fold in folds:
        assert not set(fold["test_groups"]) & set(fold["train_groups"])
    for fit, val in inner_group_folds(groups, 3):
        assert not set(groups.iloc[fit]) & set(groups.iloc[val])


def test_split_audit_detects_shared_segment_and_overlap():
    frame = pd.DataFrame({"dataset_source": "hohai", "session_id": ["a", "a", "b"], "segment_id": "s0",
                          "experiment_group": ["g1", "g1", "g2"], "window_start_seconds": [0.0, 10.0, 0.0],
                          "window_end_seconds": [180.0, 190.0, 180.0], "roll_std_60": [0.1, 0.2, 0.3]})
    assert audit_split(frame, [0], [2])["passed"]
    leaky = audit_split(frame, [0], [1])
    assert not leaky["passed"] and leaky["overlapping_intervals"] == 1


# ------------------------------------------------------------------ model schema & reproducibility


def _features(n=60, seed=0):
    rng = np.random.default_rng(seed)
    X = pd.DataFrame(rng.normal(size=(n, len(FEATURE_ORDER))), columns=list(FEATURE_ORDER))
    y = (X.roll_std_60 > 0.5).astype(int)
    return X, y


def test_feature_schema_validation_rejects_missing_and_nonfinite():
    X, _ = _features()
    with pytest.raises(ValueError):
        validate_feature_frame(X.drop(columns=["roll_std_60"]), list(FEATURE_ORDER))
    X.loc[0, "pitch_std_60"] = np.nan
    with pytest.raises(ValueError, match="không được thay bằng 0"):
        validate_feature_frame(X, list(FEATURE_ORDER))
    assert feature_schema()["count"] == 23


def test_serialized_model_is_reproducible(tmp_path):
    X, y = _features()
    params = {"max_depth": 4, "min_samples_leaf": 2, "class_weight": None}
    config = {"n_estimators": 10, "max_features": "sqrt"}
    a = make_model(params, config, 7).fit(X.to_numpy(), y)
    b = make_model(params, config, 7).fit(X.to_numpy(), y)
    assert serialize_model(a, tmp_path / "a.joblib") == serialize_model(b, tmp_path / "b.joblib")
    # n_jobs=-1 cộng xác suất các cây song song (thứ tự không cố định, lệch ~1e-16); n_jobs=1 cho tổng xác định.
    a.set_params(n_jobs=1), b.set_params(n_jobs=1)
    np.testing.assert_array_equal(a.predict_proba(X.to_numpy()), b.predict_proba(X.to_numpy()))


def test_predict_frame_abstains_on_invalid_or_out_of_domain_inputs():
    X, y = _features()
    model = make_model({"max_depth": 3, "min_samples_leaf": 1, "class_weight": None},
                       {"n_estimators": 5, "max_features": "sqrt"}, 1).fit(X.to_numpy(), y)
    card = {"domain": "hohai", "target": "RELATIVE_HIGH_ROLL", "model_version": "test",
            "feature_ranges": {f: [float(X[f].min()), float(X[f].max())] for f in FEATURE_ORDER},
            "selection": {"probability_threshold": 0.5}}
    frame = X.iloc[:4].copy()
    frame["dataset_source"] = ["hohai", "seafar", "hohai", "hohai"]
    frame.loc[frame.index[2], "roll_mean_60"] = np.nan
    frame.loc[frame.index[3], "pitch_rms_60"] = 1e6
    out = predict_frame(model, card, frame)
    assert out.proxy_prediction.iloc[0] in {"POS", "NEG"}
    assert list(out.abstain_reason.iloc[1:]) == ["OUT_OF_TRAINING_DOMAIN", "NON_FINITE_FEATURE", "FEATURE_OUTSIDE_TRAINING_RANGE"]
    assert set(out.label_source) == {"RF_PROXY_REPRODUCTION"}
    with pytest.raises(ValueError):
        predict_frame(model, card, frame.drop(columns=["roll_iqr_60"]))


# ------------------------------------------------------------------ artifacts & ledgers


@pytest.mark.skipif(not (PROXY_ROOT / "proxy_labels_oof.parquet").is_file(), reason="Chưa dựng proxy dataset.")
def test_proxy_artifacts_preserve_provenance_and_cover_each_window_once():
    measurements = pd.read_parquet(PROXY_ROOT / "measurements.parquet")
    labels = pd.read_parquet(PROXY_ROOT / "proxy_labels_oof.parquet")
    assert len(labels) == len(measurements) and not labels.window_id.duplicated().any()
    assert set(labels.rule_version) == {SPEC["rule_version"]} and labels.calibration_id.str.startswith("cal-").all()
    assert set(labels.label_source) == {"PROXY_RULE"} and not labels.physical_heel_claim.any()
    for column in ("raw_reference", "preprocessing_configuration_sha256", "feature_extractor_version",
                   "invalid_features_json", "quality_flags_json", "experiment_group"):
        assert measurements[column].notna().all(), column
    assert json.loads(labels.supporting_measurements_json.iloc[0])
    by_fold = pd.read_parquet(PROXY_ROOT / "proxy_labels_by_fold.parquet")
    hohai = measurements.set_index("window_id").experiment_group
    for fold, group in by_fold.groupby("fold"):
        test_groups = set(group.loc[group.split_role.eq("test"), "window_id"].map(hohai))
        train_groups = set(group.loc[group.split_role.eq("train"), "window_id"].map(hohai))
        assert len(test_groups) == 1 and not test_groups & train_groups


@pytest.mark.skipif(not (PROXY_ROOT / "measurements.parquet").is_file(), reason="Chưa dựng proxy dataset.")
def test_labeling_and_rules_do_not_mutate_human_review_ledgers():
    from ml.labeling.proxy_dataset import out_of_fold_labels
    assert Path("ml/data/labels/annotation_pilot/review_decisions.csv") in PROTECTED_PATHS
    before = protected_checksums(REPO_ROOT)
    measurements = pd.read_parquet(PROXY_ROOT / "measurements.parquet")
    labels, calibrations, _ = out_of_fold_labels(measurements, SPEC)
    assert protected_checksums(REPO_ROOT) == before
    assert len(calibrations) == 9 and len(labels) == len(measurements)
