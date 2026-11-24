"""Test exporter RF -> C demo cô lập trên dữ liệu tổng hợp (không cần dữ liệu gitignored); cần cc/clang."""
from __future__ import annotations

import shutil

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier

from ml.export import rf_c_export
from ml.train.rf_poc import FEATURE_ORDER

NAME = "svmg_rf_test_demo"
pytestmark = pytest.mark.skipif(shutil.which("cc") is None and shutil.which("clang") is None, reason="không có C compiler")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    rng = np.random.default_rng(7)
    X = rng.normal(size=(600, 23)).astype(np.float32)
    y = (X[:, 1] + 0.3 * X[:, 20] > 0.4).astype(int)
    model = RandomForestClassifier(n_estimators=25, max_depth=6, min_samples_leaf=10, class_weight="balanced_subsample",
                                   random_state=3).fit(X, y)
    out = tmp_path_factory.mktemp("rf_export")
    export = rf_c_export.write_c(model, list(FEATURE_ORDER), {"model_version": "test"}, out, NAME)
    return model, export, rf_c_export.build_runner(export, NAME, out), rng


def test_c_matches_sklearn_including_boundary_vectors(built):
    model, export, binary, rng = built
    X = rng.normal(size=(400, 23)).astype(np.float32)
    flat = rf_c_export.flatten_forest(model, 23)
    internal = [i for i, f in enumerate(flat["feature"]) if f >= 0][:40]
    for i, (row, node) in enumerate(zip(X, internal)):  # đặt feature đúng ngưỡng float32 hoặc float32 kế tiếp
        t = flat["value"][node]
        row[flat["feature"][node]] = t if i % 2 == 0 else np.nextafter(t, np.float32(np.inf))
    py = model.predict_proba(X)[:, 1]
    result = rf_c_export.run_vectors(binary, X.tolist())
    assert all(s == 0 for s, _, _ in result)
    assert [p for _, p, _ in result] == (py >= 0.5).astype(int).tolist()
    assert max(abs(v - s) for (_, _, v), s in zip(result, py)) <= 1e-6
    assert export["max_depth"] <= 6 and export["model_array_bytes"] <= 25 * (2 ** 7 - 1) * 9 + 25 * 2


@pytest.mark.parametrize("vector,status", [(np.zeros(22), "ERR_LENGTH"), (np.zeros(24), "ERR_LENGTH"),
                                           (np.r_[np.zeros(22), np.nan], "ERR_NONFINITE"),
                                           (np.r_[np.inf, np.zeros(22)], "ERR_NONFINITE")])
def test_invalid_inputs_are_rejected_not_negative(built, vector, status):
    (code, pred, score), = rf_c_export.run_vectors(built[2], [vector.tolist()])
    assert code == rf_c_export.STATUS[status] and pred == -1 and score == -1.0


def test_generated_artifact_is_isolated_and_deterministic(built):
    model, export, _, _ = built
    header, source, _ = rf_c_export.generate_c(model, list(FEATURE_ORDER), {"model_version": "test"}, NAME)
    assert export["paths"]["header"].read_text() == header and export["paths"]["source"].read_text() == source
    assert "svmg_engine_set_rf(" not in source and "svmg_class_t" not in source and export["paths"]["header"].name != "model.h"
    with pytest.raises(ValueError):
        rf_c_export.flatten_forest(model, 22)
