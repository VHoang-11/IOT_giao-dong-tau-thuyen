"""Metric cho proxy phenotype PoC. Khoảng tin cậy chỉ bootstrap theo NHÓM độc lập, không theo cửa sổ."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score


def binary_metrics(y_true, y_pred, y_score=None) -> dict:
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else math.nan
    recall = tp / (tp + fn) if tp + fn else math.nan
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else math.nan
    out = {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "support_positive": tp + fn, "support_negative": fp + tn,
           "precision": precision, "recall": recall, "f1": f1,
           "prevalence": (tp + fn) / len(y_true) if len(y_true) else math.nan}
    if y_score is not None and 0 < out["support_positive"] < len(y_true):
        out["pr_auc_average_precision"] = float(average_precision_score(y_true, np.asarray(y_score, float)))
    else:
        out["pr_auc_average_precision"] = math.nan
    return out


def per_group_metrics(frame: pd.DataFrame, pred_column: str, score_column: str | None = None) -> list[dict]:
    rows = []
    for group, subset in frame.groupby("experiment_group", sort=True):
        metrics = binary_metrics(subset.y_true, subset[pred_column], None if score_column is None else subset[score_column])
        rows.append({"experiment_group": group, "sessions": int(subset.session_id.nunique()), **metrics})
    return rows


def group_bootstrap_f1(frame: pd.DataFrame, pred_column: str, n_boot: int = 2000, seed: int = 20261117) -> dict:
    """Bootstrap lặp lại trên các nhóm độc lập (không phải cửa sổ chồng lấn)."""
    rng = np.random.default_rng(seed)
    groups = sorted(frame.experiment_group.unique())
    counts = {g: (int(((s.y_true == 1) & (s[pred_column] == 1)).sum()), int(((s.y_true == 0) & (s[pred_column] == 1)).sum()),
                  int(((s.y_true == 1) & (s[pred_column] == 0)).sum())) for g, s in frame.groupby("experiment_group")}
    values = []
    for _ in range(n_boot):
        sample = rng.choice(groups, size=len(groups), replace=True)
        tp = sum(counts[g][0] for g in sample)
        fp = sum(counts[g][1] for g in sample)
        fn = sum(counts[g][2] for g in sample)
        if 2 * tp + fp + fn:
            values.append(2 * tp / (2 * tp + fp + fn))
    values = np.asarray(values)
    return {"n_groups": len(groups), "n_boot": n_boot, "valid_replicates": int(len(values)), "seed": seed,
            "f1_percentile_2_5": float(np.percentile(values, 2.5)) if len(values) else math.nan,
            "f1_percentile_97_5": float(np.percentile(values, 97.5)) if len(values) else math.nan,
            "note": "Khoảng bootstrap theo nhóm điều kiện thử nghiệm; với rất ít nhóm có positive, khoảng này thô và không phải độ chính xác vận hành."}


def best_f1_threshold(y_true, y_score) -> float:
    """Ngưỡng xác suất tối đa hóa F1 trên dự đoán out-of-fold của TẬP TRAIN (không dùng test)."""
    y_true = np.asarray(y_true, dtype=int)
    y_score = np.asarray(y_score, dtype=float)
    candidates = np.unique(np.round(y_score, 6))
    best, best_threshold = -1.0, 0.5
    for threshold in candidates:
        pred = (y_score >= threshold).astype(int)
        tp = int(((y_true == 1) & (pred == 1)).sum())
        denom = 2 * tp + int(((y_true == 0) & (pred == 1)).sum()) + int(((y_true == 1) & (pred == 0)).sum())
        f1 = 2 * tp / denom if denom else 0.0
        if f1 > best + 1e-12 or (abs(f1 - best) <= 1e-12 and abs(threshold - 0.5) < abs(best_threshold - 0.5)):
            best, best_threshold = f1, float(threshold)
    return best_threshold
