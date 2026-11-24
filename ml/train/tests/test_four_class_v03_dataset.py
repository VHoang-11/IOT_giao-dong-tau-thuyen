"""Test M2-R5d (v0.3): cùng session/nhãn với v0.2, pitch khác 0, đủ 23/23, nhân quả, tái lập, provenance."""
from __future__ import annotations

import csv
import hashlib
import math

import pytest

from ml.train import four_class_experimental_dataset as v02
from ml.train import four_class_pilot_dataset as pilot
from ml.train import four_class_v03_dataset as v03
from ml.train.g1_simulation_dataset import _core_rows, _features
from simulation.generator import pitch_imu as P
from simulation.generator.config import DatasetSplit, LabelingVersion, ScenarioCode

KEYS = ("session_id", "seed", "scenario", "split", "subset", "label", "exclusion_reason", "window_end_seconds",
        "target_coverage_180")
SMALL = {ScenarioCode.S0: (1, 0), ScenarioCode.S3: (1, 1)}


@pytest.fixture(scope="module")
def base_runner():
    return pilot.make_runner()[0]


@pytest.mark.parametrize("scenario", list(v02.TARGET))
def test_labels_sessions_equal_v02_and_pitch_features_present(base_runner, scenario):
    seed = v02.session_seed(2)
    new, session = v03.generate_session(v03.PitchIMURunner(base_runner), scenario, DatasetSplit.TRAIN, seed, "test")
    old, _ = v02.generate_session(base_runner, scenario, DatasetSplit.TRAIN, seed, "test")
    assert [tuple(r[k] for k in KEYS) for r in new] == [tuple(r[k] for k in KEYS) for r in old]
    eligible = [r for r in new if r["label"] != "ABSTAIN"]
    assert all(r["feature_valid_mask"] == (1 << 23) - 1 and all(math.isfinite(float(r[n])) for n in _features()) for r in eligible)
    assert any(r["pitch_std_60"] != "" and float(r["pitch_std_60"]) > 0.05 for r in new)
    assert {r["dataset_version"] for r in new} == {v03.DATASET_VERSION}
    assert session["sim_extension_version"] == P.SIM_EXTENSION_VERSION and session["true_pitch_rms_deg"] > 0


def test_jobs_keep_v02_sessions_and_test_g1():
    jobs = v03.jobs()
    trainval = [j for j in jobs if j[1] is not DatasetSplit.TEST_G1]
    assert [j[2] for j in trainval] == [v02.session_seed(i) for i in range(sum(map(sum, v02.PLAN.values())))]
    assert [(j[0], j[2]) for j in jobs if j[1] is DatasetSplit.TEST_G1] == v02.pilot_test_g1_sessions()
    assert len({j[2] for j in jobs}) == len(jobs)      # không session nào nằm ở hai split


def test_v03_features_are_causal(base_runner):
    """Đặc trưng tại t chỉ phụ thuộc IMU ≤ t: cắt tương lai không đổi các hàng trước đó."""
    result = base_runner.generate(ScenarioCode.S1, seed=v02.session_seed(4), dataset_split=DatasetSplit.TRAIN,
                                  labeling_version=LabelingVersion.V2)
    imu, _ = P.synthesize(result, v03.IMU_CONFIG, v02.session_seed(4))
    full, cut = _core_rows(imu), _core_rows(imu[:len(imu) * 2 // 3])
    assert len(cut) > 10 and all(a == b or (math.isnan(a) and math.isnan(b)) for x, y in zip(full, cut) for a, b in zip(x, y))


def test_small_build_reproducible_with_provenance(tmp_path):
    first = v03.build_dataset(tmp_path / "a", SMALL, report=None, include_test=False, v02_csv=tmp_path / "none.csv")
    second = v03.build_dataset(tmp_path / "b", SMALL, report=None, include_test=False, v02_csv=tmp_path / "none.csv")
    assert first["dataset_sha256"] == second["dataset_sha256"]
    assert first["dataset_sha256"] == hashlib.sha256((tmp_path / "a/windows.csv").read_bytes()).hexdigest()
    gates = first["quality_gates"]
    assert gates["no_nan_in_eligible_features"] and gates["feature_columns_match_contract_order"]
    assert gates["pitch_features_not_identically_zero"] and gates["labels_match_v02"] is None
    assert first["sim_extension_version"] == P.SIM_EXTENSION_VERSION and first["imu_config"]["accel_noise_std_m_s2"] == 0.02
    assert "simulation/generator/pitch_imu.py" in first["sources_sha256"]
    with (tmp_path / "a/windows.csv").open() as f:
        header = next(csv.reader(f))
    assert [h for h in header if h in _features()] == list(_features())
    assert {"dataset_source", "sim_extension_version", "seed", "split", "scenario", "label_source"} <= set(header)
