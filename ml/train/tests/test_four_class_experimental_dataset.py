"""Test M2-R5c: tương đương nhãn với pilot, Test-G1 không đổi, độ phủ 180 s, ngưỡng đóng băng, seed, S0b, tái lập."""
from __future__ import annotations

import hashlib

import pytest

from ml.train import four_class_experimental_dataset as x
from ml.train import four_class_pilot_dataset as pilot
from ml.train.g1_simulation_dataset import _features, _sha
from simulation.generator.config import DatasetSplit, ScenarioCode

SMALL = {ScenarioCode.S0: (1, 0), ScenarioCode.S3: (1, 1), ScenarioCode.S0B: (1, 0)}
KEYS = ("label", "exclusion_reason", "window_end_seconds", "feature_valid_mask", *_features())


@pytest.fixture(scope="module")
def runner():
    return pilot.make_runner()[0]


@pytest.mark.parametrize("scenario", list(pilot.TARGET))
def test_labels_and_features_equal_pilot(runner, scenario):
    seed = pilot.session_seed(3)
    new, _ = x.generate_session(runner, scenario, DatasetSplit.TRAIN, seed, "test")
    old, _ = pilot.generate_session(runner, scenario, DatasetSplit.TRAIN, seed)
    assert [tuple(r[k] for k in KEYS) for r in new] == [tuple(r[k] for k in KEYS) for r in old]
    for row in new:
        if row["label"] != "ABSTAIN":
            assert 0.0 <= row["target_coverage_180"] <= 1.0
            assert (row["target_coverage_180"] == 1.0) == bool(row["window_all_samples_agree"])


def test_test_g1_is_exactly_the_pilot_test_split():
    sessions = x.pilot_test_g1_sessions()
    assert len(sessions) == sum(counts[2] for counts in pilot.PLAN.values()) == 10
    assert len({seed for _, seed in sessions}) == 10


def test_frozen_candidate_and_seed_disjointness(monkeypatch):
    assert _sha(x.CANDIDATE_PATH) == x.FROZEN_CANDIDATE_SHA256
    new = {x.session_seed(i) for i in range(200)}
    old = {pilot.session_seed(i) for i in range(40)} | set(range(x.G1_SEED_BASE, x.G1_SEED_BASE + 100))
    assert len(new) == 200 and not new & old
    monkeypatch.setattr(x, "FROZEN_CANDIDATE_SHA256", "0" * 64)
    with pytest.raises(RuntimeError):
        x.build_dataset(report=None)


def test_s0b_is_challenge_and_pre_event_abstains(runner):
    rows, meta = x.generate_session(runner, ScenarioCode.S0B, DatasetSplit.TRAIN, x.session_seed(5), "test")
    t0 = meta["events"][0]["t0_s"]
    assert meta["subset"] == "CHALLENGE_S0B" and all(r["subset"] == "CHALLENGE_S0B" for r in rows)
    assert all(r["label"] == "ABSTAIN" for r in rows if r["window_end_seconds"] < t0)


def test_diversity_metric():
    assert x._diversity([3, 1, 0]) == {"windows": 4, "sessions": 2, "effective_sessions": 1.6, "max_session_share": 0.75}


def test_small_build_is_reproducible_and_audited(tmp_path):
    first = x.build_dataset(tmp_path / "a", SMALL, report=None, include_test=False)
    second = x.build_dataset(tmp_path / "b", SMALL, report=None, include_test=False)
    assert first["dataset_sha256"] == second["dataset_sha256"]
    assert first["dataset_sha256"] == hashlib.sha256((tmp_path / "a/windows.csv").read_bytes()).hexdigest()
    assert first["quality_gates"]["no_nan_in_eligible_features"] and first["quality_gates"]["coverage_recorded_for_all_eligible"]
    assert first["g1_seed_audit"]["seed_scheme"].startswith("seed_base+n")
    assert first["feature_names"] == list(_features()) and len(first["feature_names"]) == 23
