from __future__ import annotations

import math
from pathlib import Path

import pytest

from ml.labeling.ai_assisted_review import (
    ALLOWED_SUGGESTIONS, BATCH_PATH, _assert_output_path, analyze_record, evaluate_rules, load_batch,
    mann_kendall_exact_increasing,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_mann_kendall_exact_matches_permutation_probabilities():
    s, p = mann_kendall_exact_increasing([1, 2, 3])
    assert s == 3 and math.isclose(p, 1 / 6)
    s, p = mann_kendall_exact_increasing(list(range(9)))
    assert s == 36 and math.isclose(p, 1 / math.factorial(9))
    s, p = mann_kendall_exact_increasing(list(range(9))[::-1])
    assert s == -36 and math.isclose(p, 1.0)
    with pytest.raises(ValueError):
        mann_kendall_exact_increasing([1.0, 2.0])


def _metrics(mean, sign_ratio, pattern, ctx_same, block_std, sub_std, p, ctx_sub_std=None):
    ctx_sub = ctx_sub_std if ctx_sub_std is not None else [0.1] * 9
    return {
        "roll": {"mean": mean, "dominant_sign_ratio": sign_ratio},
        "blocks_60s": {"centered_std": block_std},
        "sub_blocks_20s": {"mean_sign_pattern": pattern, "mann_kendall_p_one_sided": p, "centered_std": sub_std},
        "context": {"samples": 1800, "mean": mean, "all_same_sign_as_window": ctx_same,
                    "sub_block_std_20s": ctx_sub, "max_valid_sub_block_std": max(ctx_sub)},
    }


def test_rules_suggest_single_consistent_offset_but_never_normal_or_high_roll():
    flat = [0.05] * 9
    result = evaluate_rules(_metrics(3.1, 1.0, "+" * 9, True, [0.05, 0.05, 0.05], flat, 0.9), 29)
    assert result["suggested_label"] == "PERSISTENT_OFFSET"
    assert result["flags"]["HIGH_ROLL"].startswith("NOT_ASSESSABLE")
    assert result["flags"]["NORMAL"].startswith("NOT_ASSESSABLE")


def test_rules_return_unlabeled_not_normal_for_small_quiet_signal():
    sub = [0.2, 0.3, 0.25, 0.22, 0.28, 0.21, 0.26, 0.24, 0.23]
    result = evaluate_rules(_metrics(0.001, 0.5, "+-+-+-+-+", False, [0.3, 0.25, 0.24], sub, 0.8), 29)
    assert result["suggested_label"] == "UNLABELED"
    assert result["suggested_label"] in ALLOWED_SUGGESTIONS


def test_rules_mark_overlapping_phenotypes_for_review():
    growing = [0.01, 0.01, 0.02, 0.02, 0.02, 0.06, 0.1, 0.12, 0.13]
    result = evaluate_rules(_metrics(0.7, 1.0, "+" * 9, True, [0.02, 0.04, 0.12], growing, 0.0004, [0.02] * 9), 29)
    assert result["flags"]["AMPLITUDE_GROWTH"] == "OBSERVED_CONSISTENT"
    assert result["suggested_label"] == "REVIEW_REQUIRED"


def test_nominal_p_value_without_bonferroni_is_only_weak_growth():
    sub = [0.24, 0.26, 0.31, 0.37, 0.56, 0.27, 0.26, 0.5, 0.66]
    result = evaluate_rules(_metrics(0.0, 0.5, "+-+-+-+-+", False, [0.28, 0.42, 0.50], sub, 0.0376, [0.47] * 9), 29)
    assert result["flags"]["AMPLITUDE_GROWTH"] == "OBSERVED_WEAK"
    assert result["suggested_label"] == "REVIEW_REQUIRED"


def test_output_guard_refuses_human_review_ledgers(tmp_path):
    with pytest.raises(PermissionError):
        _assert_output_path(tmp_path, tmp_path / "ml/data/labels/annotation_pilot/review_decisions.csv")
    with pytest.raises(PermissionError):
        _assert_output_path(tmp_path, tmp_path / "ml/data/labels/annotation_pilot/review_audit.jsonl")
    _assert_output_path(tmp_path, tmp_path / "ml/data/labels/ai_assisted_review/x.csv")


@pytest.mark.skipif(not (REPO_ROOT / BATCH_PATH).is_file(), reason="Pilot artifacts không có trong môi trường này.")
def test_actual_pilot_records_match_feature_table():
    batch = load_batch(REPO_ROOT)
    assert len(batch) == 29
    cache: dict = {}
    for dataset in ("hohai", "seafar", "southampton"):
        record = next(batch.loc[batch.dataset_source.eq(dataset)].itertuples(index=False))
        metrics = analyze_record(REPO_ROOT, record, cache)
        assert metrics["boundary_check"]["passed"]
        assert metrics["feature_parity"]["passed"], metrics["feature_parity"]
