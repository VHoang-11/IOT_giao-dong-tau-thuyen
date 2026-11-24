"""Test M2-R6a: 23 đặc trưng đúng thứ tự, mã hóa 4 lớp = svmg_class_t, không rò nhãn/độ phủ, tách session, tất định, Test-G1 không nạp."""
from __future__ import annotations

import json

import numpy as np
import pytest

from ml.train import four_class_v03_dataset as v03
from ml.train import rf_four_class_m2r6 as R
from ml.train.g1_simulation_dataset import _sha
from simulation.generator.config import ScenarioCode

# S3 đứng đầu: seed v0.2 chỉ số 3, 4 (Train) và 5 (Validation) có cửa sổ growth -> đủ 4 lớp ở cả hai split.
SMALL = {ScenarioCode.S3: (5, 1), ScenarioCode.S0: (1, 1), ScenarioCode.S1: (1, 1), ScenarioCode.S2: (1, 1)}


@pytest.fixture(scope="module")
def small(tmp_path_factory):
    out = tmp_path_factory.mktemp("v03")
    v03.build_dataset(out, SMALL, report=None, include_test=True, v02_csv=out / "none.csv")
    return out / "windows.csv"


def test_loader_drops_test_g1_and_abstain(small):
    frame = R.load(small)
    assert set(frame.split) == {R.TRAIN, R.VAL} and frame.label.ne("ABSTAIN").all()
    assert sorted(frame.y.unique()) == [0, 1, 2, 3] and all(R.CLASSES[y] == lbl for y, lbl in zip(frame.y, frame.label))


def test_matrix_uses_only_contract_features(small):
    frame = R.load(small)
    X = R.matrix(frame)
    assert X.shape == (len(frame), 23) and X.dtype == np.float32
    leaked = frame.assign(target_coverage_180=0.0, session_id="x", label="NORMAL", y=0, scenario="S0", split=R.TRAIN, seed=1)
    assert np.array_equal(R.matrix(leaked), X)
    with pytest.raises(ValueError):
        R.matrix(frame.assign(pitch_rms_60=np.nan))      # NaN không bị thay bằng 0


def test_train_is_deterministic_grouped_and_c_compatible(small, tmp_path):
    first = R.train_dataset("small", small, None, tmp_path / "a")
    second = R.train_dataset("small", small, None, tmp_path / "b")
    assert first["model_sha256"] == second["model_sha256"] and first["trials"] == second["trials"]
    assert first["deterministic_refit"] and all(first["c_contract"].values())
    assert len(first["trials"]) == len(R.GRID) and first["selected"] in first["trials"]
    meta = json.loads((tmp_path / "a/metadata.json").read_text())
    assert meta["feature_names"] == R.FEATURES and meta["class_mapping"] == dict(zip(R.CLASSES, range(4)))
    assert meta["test_g1"].startswith("NOT_EVALUATED")
    frame = R.load(small)
    assert not set(frame.loc[frame.split.eq(R.TRAIN), "session_id"]) & set(frame.loc[frame.split.eq(R.VAL), "session_id"])
    baseline = first["baseline_b_validation"]
    assert baseline["n"] == first["validation"]["n"] and set(baseline["pred_counts"]) <= set(R.CLASSES + ["UNKNOWN"])


def test_historical_datasets_unchanged():
    for path, sha in R.DATASETS.values():
        if not path.exists():
            pytest.skip("Dataset cục bộ chưa được sinh.")
        assert _sha(path) == sha
