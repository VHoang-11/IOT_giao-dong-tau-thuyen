"""Test M2-R6c (không mở Test-G1): UNKNOWN là bỏ sót, kiểm tra toàn vẹn chặn trước khi đọc dữ liệu, khóa chạy một lần."""
from __future__ import annotations

import numpy as np
import pytest

from ml.eval import final_test_g1_m2r6c as T
from ml.export import rf4_freeze_m2r6b as F


def test_unknown_counts_as_miss_and_never_normal():
    proba = np.array([[0.9, 0.1, 0, 0], [0.45, 0.4, 0.15, 0], [0, 0, 0.3, 0.7], [0.2, 0.3, 0.1, 0.4]])
    pred = T.apply_tau(proba, 0.5)
    assert pred.tolist() == [0, T.UNKNOWN, 3, T.UNKNOWN]
    m = T.with_tau(np.array([0, 0, 3, 3]), pred)
    assert m["coverage"] == 0.5 and m["unknown"] == 2 and m["accuracy"] == 0.5 and m["selective_accuracy"] == 1.0
    assert m["per_class"]["NORMAL"]["recall"] == 0.5 and m["per_class"]["AMPLITUDE_GROWTH"]["recall"] == 0.5
    assert m["unknown_per_class"] == {"NORMAL": 1, "HIGH_ROLL": 0, "PERSISTENT_OFFSET": 0, "AMPLITUDE_GROWTH": 1}


def test_integrity_failure_stops_before_reading_test_g1(monkeypatch):
    if not (F.MODEL_DIR / "model.joblib").exists():
        pytest.skip("Artifact M2-R6a/R6b cục bộ chưa có.")
    monkeypatch.setattr(T.pd, "read_csv", lambda *a, **k: pytest.fail("Test-G1 bị đọc dù kiểm tra toàn vẹn thất bại"))
    monkeypatch.setattr(F, "FROZEN_MODEL_SHA256", "0" * 64)
    with pytest.raises(RuntimeError):
        T.evaluate()


def test_locked_results_refuse_second_evaluation(tmp_path, monkeypatch):
    (tmp_path / "results.json").write_text("{}\n")
    monkeypatch.setattr(T, "evaluate", lambda *a, **k: pytest.fail("không được đánh giá lại"))
    with pytest.raises(RuntimeError):
        T.run(out=tmp_path, report=None)
    with pytest.raises(RuntimeError):
        T.run(verify=True, out=tmp_path / "missing", report=None)
