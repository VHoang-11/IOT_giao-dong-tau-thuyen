"""Baseline xác định cho proxy phenotype PoC.

- ``majority``: luôn dự đoán NEG (lớp đa số) — mức sàn tầm thường.
- ``feature_quantile_rule``: một feature trong 23 feature, ngưỡng = phân vị (trọng số đều theo session)
  fit trên TẬP TRAIN của fold. Với ``roll_std_60`` đây chính là proxy rule (giới hạn trên vòng lặp, F1 = 1
  trên cửa sổ không ABSTAIN theo cấu trúc); ``roll_rms_60`` là biến thể RMS thô; ``pitch_std_60`` kiểm tra
  mức độ proxy chỉ phản ánh trạng thái sóng chung.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml.labeling.proxy_rules import session_weighted_quantile

FEATURE_RULE_BASELINES = {
    "proxy_rule_roll_std_60": "roll_std_60",
    "raw_rms_rule_roll_rms_60": "roll_rms_60",
    "pitch_only_rule_pitch_std_60": "pitch_std_60",
}


def majority(test: pd.DataFrame) -> np.ndarray:
    return np.zeros(len(test), dtype=int)


def feature_quantile_rule(train: pd.DataFrame, test: pd.DataFrame, feature: str, quantile: float) -> tuple[np.ndarray, float]:
    """Fit ngưỡng trên mọi cửa sổ train hợp lệ (gồm cả cửa sổ ABSTAIN, giống calibration của proxy)."""
    threshold = session_weighted_quantile(train[feature].to_numpy(float), train.session_id.to_numpy(), quantile)
    return (test[feature].to_numpy(float) >= threshold).astype(int), threshold
