"""Test M2-R6b: manifest đóng băng khớp header sinh lại từ mô hình M2-R6a; Test-G1 chưa đánh giá; parity đã ghi."""
from __future__ import annotations

import json

import pytest

from ml.export import rf4_freeze_m2r6b as F
from ml.export import rf_c_export as E
from ml.train import rf_four_class_m2r6 as R


def test_frozen_manifest_matches_regenerated_header():
    manifest = json.loads(F.MANIFEST.read_text())
    assert manifest["status"] == "FROZEN_PENDING_TEST_G1" and manifest["test_g1"].startswith("NOT_EVALUATED")
    assert manifest["feature_names"] == R.FEATURES and manifest["class_mapping"] == dict(zip(R.CLASSES, range(4)))
    assert all(manifest["parity"][k]["pred_mismatches"] == 0 for k in ("validation", "s0b", "threshold_boundaries"))
    if not (F.MODEL_DIR / "model.joblib").exists():
        pytest.skip("Mô hình M2-R6a cục bộ chưa được sinh.")
    model, meta = F.load_frozen()
    text = E.generate_model_h(model, R.FEATURES, F.c_metadata(meta), manifest["unknown_policy"]["tau_conf"])[0]
    assert E.hashlib.sha256(text.encode()).hexdigest() == manifest["c_artifact"]["sha256"]
