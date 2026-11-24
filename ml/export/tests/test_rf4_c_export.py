"""Test export C99 RF bốn lớp (M2-R6b): parity sklearn/C, hòa, đầu vào lỗi, metadata không tương thích, tất định."""
from __future__ import annotations

import shutil

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier

from ml.export import rf_c_export as E
from ml.train import rf_four_class_m2r6 as R

pytestmark = pytest.mark.skipif(shutil.which("cc") is None, reason="không có C compiler")
META = {"model_version": "test-rf4", "feature_schema_version": "svmg-angle-23-v1", "preprocessing_version": "imu-cf-bw4-20to10-v1"}


def build(model, tmp_path, tau=0.5):
    header = tmp_path / "rf4_test.h"
    header.write_text(E.generate_model_h(model, R.FEATURES, META, tau)[0], encoding="ascii")
    return E.build_runner4(header, tmp_path)


def test_parity_boundaries_and_invalid_inputs(tmp_path):
    rng = np.random.default_rng(11)
    X = rng.normal(size=(800, 23)).astype(np.float32)
    y = np.digitize(X[:, 1] + 0.5 * X[:, 20], [-0.7, 0.0, 0.7])
    model = RandomForestClassifier(n_estimators=15, max_depth=4, min_samples_leaf=5, random_state=2).fit(X, y)
    binary = build(model, tmp_path)
    vectors = np.vstack([X[:300], np.array(E.boundary_vectors4(model, X[0], limit=400), dtype=np.float32)])
    p = E.parity4(binary, model, vectors, 0.5)
    assert p["pred_mismatches"] == 0 and p["pred_conf_mismatches"] == 0 and p["proba_max_abs_diff"] < 1e-6
    assert p["unknown_mismatches_at_tau"] == 0 and all(E.invalid_inputs4(binary, X[0]).values())


@pytest.mark.parametrize("labels, expected", [([0, 1, 2, 3], 0), ([0, 1, 1, 2, 2, 3], 1)])
def test_ties_pick_lowest_class_like_sklearn(tmp_path, labels, expected):
    X = np.zeros((len(labels), 23), dtype=np.float32)       # mọi cây chỉ có một lá -> xác suất hòa chính xác
    model = RandomForestClassifier(n_estimators=3, bootstrap=False, random_state=0).fit(X, labels)
    pred, proba, _, conf = E.run_vectors4(build(model, tmp_path), [X[0].tolist()])[0]
    assert model.predict(X[:1])[0] == pred == expected and np.allclose(proba, model.predict_proba(X[:1])[0], atol=1e-7)


def test_incompatible_models_and_metadata_rejected():
    X = np.random.default_rng(0).normal(size=(40, 23)).astype(np.float32)
    binary_model = RandomForestClassifier(n_estimators=2, random_state=0).fit(X, X[:, 0] > 0)
    four = RandomForestClassifier(n_estimators=2, random_state=0).fit(X, np.arange(40) % 4)
    with pytest.raises(ValueError):
        E.generate_model_h(binary_model, R.FEATURES, META, 0.5)
    with pytest.raises(ValueError):
        E.generate_model_h(four, R.FEATURES[:22], META, 0.5)
    with pytest.raises(ValueError):
        E.generate_model_h(four, R.FEATURES, {**META, "preprocessing_version": ""}, 0.5)
    assert E.generate_model_h(four, R.FEATURES, META, 0.5) == E.generate_model_h(four, R.FEATURES, META, 0.5)
