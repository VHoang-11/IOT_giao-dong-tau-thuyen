"""Proxy rules v1 cho Motion Phenotype Classification (PoC, KHÔNG phải ground truth).

Ba bước tách biệt:
1. ``compute_segment_statistics``: thống kê nhân quả trên cửa sổ (t-180, t] và lịch sử (t-360, t-180]
   cùng segment; không dùng mẫu sau endpoint.
2. ``fit_calibration``: ngưỡng tương đối fit CHỈ trên cửa sổ của các nhóm train, mỗi miền riêng.
3. ``apply_rules``: gán POS/NEG/ABSTAIN cho từng target, kèm lý do và số đo hỗ trợ.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ml.features.calculations import dominant_sign_ratio, population_std
from ml.labeling.human_review_workflow import ANGLE_FEATURES

POS, NEG, ABSTAIN = "POS", "NEG", "ABSTAIN"
TARGETS = ("RELATIVE_HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH")
CALIBRATED_TARGETS = ("RELATIVE_HIGH_ROLL", "AMPLITUDE_GROWTH")
DEFAULT_SPEC = Path("ml/labeling/proxy_spec.yaml")


def load_spec(path: Path = DEFAULT_SPEC) -> dict:
    spec = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if tuple(spec["targets"]) != TARGETS:
        raise ValueError("Danh sách target trong spec không khớp TARGETS.")
    return spec


def spec_sha256(path: Path = DEFAULT_SPEC) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --------------------------------------------------------------------------- thống kê nhân quả


def _slice(t: np.ndarray, x: np.ndarray, lower: float, upper: float) -> np.ndarray:
    return x[int(np.searchsorted(t, lower, side="right")):int(np.searchsorted(t, upper, side="right"))]


def _coverage_ok(t: np.ndarray, lower: float, upper: float, spec: dict) -> tuple[bool, float]:
    w = spec["window"]
    dt = 1.0 / w["sampling_hz"]
    tt = _slice(t, t, lower, upper)
    expected = int(round((upper - lower) * w["sampling_hz"]))
    fraction = len(tt) / expected if expected else 0.0
    gap_ok = len(tt) < 2 or float(np.max(np.diff(tt))) <= w["maximum_gap_factor"] * dt + 1e-8
    return bool(fraction >= w["minimum_valid_fraction"] and gap_ok), min(1.0, fraction)


def _half_cycle_lag1(x: np.ndarray) -> float:
    centered = x - x.mean()
    crossings = np.where(np.diff(np.sign(centered)) != 0)[0]
    amps = np.array([np.abs(centered[a + 1:b + 1]).max() for a, b in zip(crossings[:-1], crossings[1:]) if b > a])
    if len(amps) < 4 or np.std(amps[:-1]) == 0 or np.std(amps[1:]) == 0:
        return math.nan
    return float(np.corrcoef(amps[:-1], amps[1:])[0, 1])


def window_statistics(t: np.ndarray, roll: np.ndarray, end: float, segment_first: float,
                      segment_last: float, spec: dict) -> dict:
    """Thống kê của một cửa sổ, chỉ dùng mẫu có timestamp <= end."""
    w = spec["window"]
    W, B, S = w["window_seconds"], w["short_window_seconds"], w["sub_block_seconds"]
    start = end - W
    ok, fraction = _coverage_ok(t, start, end, spec)
    out = {"window_coverage_fraction": fraction, "window_coverage_ok": ok,
           "seconds_after_endpoint_in_segment": float(segment_last - end)}
    out["near_segment_end_audit"] = bool(out["seconds_after_endpoint_in_segment"] < w["near_segment_end_audit_seconds"])
    if not ok or start < segment_first - 1e-9:
        out["statistics_valid"] = False
        return out
    x = _slice(t, roll, start, end)
    x = x[np.isfinite(x)]
    n_blocks = int(round(W / B))
    n_sub = int(round(W / S))
    blocks = [_slice(t, roll, start + B * k, start + B * (k + 1)) for k in range(n_blocks)]
    subs = [_slice(t, roll, start + S * k, start + S * (k + 1)) for k in range(n_sub)]
    min_sub = math.ceil(w["minimum_valid_fraction"] * S * w["sampling_hz"])
    if any(len(s) < min_sub for s in subs):
        out["statistics_valid"] = False
        return out
    block_std = [population_std(b) for b in blocks]
    block_mean = [float(np.mean(b)) for b in blocks]
    block_rms = [float(np.sqrt(np.mean(b ** 2))) for b in blocks]
    sub_std = [population_std(s) for s in subs]
    sub_mean = [float(np.mean(s)) for s in subs]
    signs = "".join("+" if m > 0 else "-" if m < 0 else "0" for m in sub_mean)

    ctx_lower = max(start - w["context_seconds"], segment_first - 1.0 / w["sampling_hz"])
    ctx_ok, ctx_fraction = _coverage_ok(t, ctx_lower, start, spec)
    ctx_fraction = len(_slice(t, t, ctx_lower, start)) / (w["context_seconds"] * w["sampling_hz"])
    ctx = _slice(t, roll, ctx_lower, start)
    ctx_subs = [_slice(t, roll, start - w["context_seconds"] + S * k, start - w["context_seconds"] + S * (k + 1))
                for k in range(int(round(w["context_seconds"] / S)))]
    ctx_sub_std = [population_std(s) for s in ctx_subs if len(s) >= min_sub]
    mean180 = float(np.mean(x))
    std180 = population_std(x)
    s = np.asarray(sub_std)
    mk_s = int(sum(np.sign(s[j] - s[i]) for i in range(len(s)) for j in range(i + 1, len(s))))
    out.update({
        "statistics_valid": True,
        "roll_mean_180_stat": mean180, "roll_centered_std_180": std180,
        "roll_dominant_sign_ratio_180_stat": dominant_sign_ratio(x),
        "offset_to_oscillation_ratio": abs(mean180) / std180 if std180 > 0 else math.nan,
        "block_mean_json": json.dumps([round(v, 6) for v in block_mean]),
        "block_centered_std_json": json.dumps([round(v, 6) for v in block_std]),
        "block_raw_rms_json": json.dumps([round(v, 6) for v in block_rms]),
        "sub_block_std_json": json.dumps([round(v, 6) for v in sub_std]),
        "sub_block_mean_sign_pattern": signs,
        "sub_block_mean_sign_changes": int(sum(a != b for a, b in zip(signs, signs[1:]))),
        "centered_std_ratio": block_std[-1] / block_std[0] if block_std[0] > 0 else math.nan,
        "log_centered_std_ratio": math.log(block_std[-1] / block_std[0]) if block_std[0] > 0 and block_std[-1] > 0 else math.nan,
        "raw_rms_ratio": block_rms[-1] / block_rms[0] if block_rms[0] > 0 else math.nan,
        "monotonic_centered_blocks": bool(all(a < b for a, b in zip(block_std, block_std[1:]))),
        "context_fraction": float(min(1.0, ctx_fraction)),
        "context_coverage_ok": bool(ctx_ok and ctx_fraction >= w["minimum_valid_fraction"]),
        "context_all_same_sign": bool(len(ctx) > 0 and np.all(np.sign(ctx) == np.sign(mean180))),
        "context_max_sub_std": max(ctx_sub_std) if ctx_sub_std else math.nan,
        "late_block_exceeds_context": bool(ctx_sub_std and block_std[-1] > max(ctx_sub_std)),
        "mann_kendall_S_sub_std": mk_s,
        "sub_std_lag1_autocorr": float(np.corrcoef(s[:-1], s[1:])[0, 1]) if np.std(s) > 0 else math.nan,
        "half_cycle_amplitude_lag1": _half_cycle_lag1(x),
    })
    return out


# --------------------------------------------------------------------------- hiệu chuẩn


def session_weighted_quantile(values: np.ndarray, sessions: np.ndarray, q: float) -> float:
    """Phân vị có trọng số đều theo session (mỗi session tổng trọng số 1), quy ước inverted-CDF."""
    values = np.asarray(values, dtype=float)
    mask = np.isfinite(values)
    values, sessions = values[mask], np.asarray(sessions)[mask]
    if not len(values):
        raise ValueError("Không có giá trị hữu hạn để hiệu chuẩn.")
    counts = pd.Series(sessions).value_counts()
    weights = np.array([1.0 / counts[s] for s in sessions])
    order = np.argsort(values, kind="stable")
    cumulative = np.cumsum(weights[order]) / weights.sum()
    return float(values[order][int(np.searchsorted(cumulative, q - 1e-12, side="left"))])


def fit_calibration(measurements: pd.DataFrame, train_groups: list[str], spec: dict,
                    overrides: dict | None = None) -> dict:
    """Fit ngưỡng tương đối từ cửa sổ hợp lệ của các nhóm train, từng miền riêng.

    ``overrides`` cho phép nghiên cứu độ nhạy: {target: (q_pos, q_neg)}.
    """
    overrides = overrides or {}
    train = measurements.loc[measurements.experiment_group.isin(train_groups)
                             & measurements.angle23_complete & measurements.statistics_valid]
    calibration = {"rule_version": spec["rule_version"], "train_groups": sorted(train_groups), "domains": {}}
    for domain, settings in spec["calibration_domains"].items():
        subset = train.loc[train.dataset_source.eq(domain)]
        entry = {"calibrated": False, "train_windows": int(len(subset)),
                 "train_sessions": int(subset.session_id.nunique()),
                 "train_groups": sorted(subset.experiment_group.unique().tolist())}
        if not settings.get("calibrate"):
            entry["reason"] = settings.get("reason", "CALIBRATION_DISABLED")
        elif subset.experiment_group.nunique() < spec["readiness"]["minimum_domain_groups"] - 1:
            entry["reason"] = "TOO_FEW_TRAIN_GROUPS"
        else:
            entry["calibrated"] = True
            hr = spec["rules"]["RELATIVE_HIGH_ROLL"]
            q_pos, q_neg = overrides.get("RELATIVE_HIGH_ROLL", (hr["positive_quantile"], hr["negative_quantile"]))
            entry["RELATIVE_HIGH_ROLL"] = {
                "statistic": hr["statistic"], "positive_quantile": q_pos, "negative_quantile": q_neg,
                "positive_threshold": session_weighted_quantile(subset[hr["statistic"]], subset.session_id, q_pos),
                "negative_threshold": session_weighted_quantile(subset[hr["statistic"]], subset.session_id, q_neg)}
            gr = spec["rules"]["AMPLITUDE_GROWTH"]
            q_pos, q_neg = overrides.get("AMPLITUDE_GROWTH", (gr["positive_quantile"], gr["negative_quantile"]))
            entry["AMPLITUDE_GROWTH"] = {
                "statistic": "log_centered_std_ratio", "positive_quantile": q_pos, "negative_quantile": q_neg,
                "positive_threshold": session_weighted_quantile(subset.log_centered_std_ratio, subset.session_id, q_pos),
                "negative_threshold": session_weighted_quantile(subset.log_centered_std_ratio, subset.session_id, q_neg)}
        calibration["domains"][domain] = entry
    payload = json.dumps(calibration, sort_keys=True, default=float)
    calibration["calibration_id"] = "cal-" + hashlib.sha256(payload.encode()).hexdigest()[:12]
    return calibration


# --------------------------------------------------------------------------- áp dụng rule


def _high_roll(row, cal) -> tuple[str, str]:
    c = cal["RELATIVE_HIGH_ROLL"]
    value = row[c["statistic"]]
    if not math.isfinite(value):
        return ABSTAIN, "INVALID_STATISTIC"
    if value >= c["positive_threshold"]:
        return POS, "S60_AT_OR_ABOVE_TRAIN_UPPER_QUANTILE"
    if value < c["negative_threshold"]:
        return NEG, "S60_BELOW_TRAIN_LOWER_QUANTILE"
    return ABSTAIN, "BOUNDARY_BAND"


def _offset(row, spec) -> tuple[str, str]:
    if row.sub_block_mean_sign_changes > 0 or "0" in row.sub_block_mean_sign_pattern:
        return NEG, "SUB_BLOCK_MEAN_SIGN_NOT_PERSISTENT"
    if row.roll_dominant_sign_ratio_180_stat < 1.0:
        return ABSTAIN, "SIGNED_BIAS_BUT_OSCILLATION_CROSSES_DATUM"
    if spec["rules"]["PERSISTENT_OFFSET"]["require_context_same_sign"]:
        if not row.context_coverage_ok:
            return ABSTAIN, "NO_FULL_CAUSAL_CONTEXT_FOR_DURATION"
        if not row.context_all_same_sign:
            return ABSTAIN, "CONTEXT_CROSSES_DATUM_ONSET_UNCLEAR"
    return POS, "WINDOW_AND_CONTEXT_ENTIRELY_ONE_SIDE_OF_SENSOR_DATUM"


def _growth(row, cal, spec) -> tuple[str, str]:
    c = cal["AMPLITUDE_GROWTH"]
    rule = spec["rules"]["AMPLITUDE_GROWTH"]
    value = row.log_centered_std_ratio
    if not math.isfinite(value):
        return ABSTAIN, "INVALID_STATISTIC"
    if value < c["negative_threshold"]:
        return NEG, "CENTERED_RATIO_BELOW_TRAIN_LOWER_QUANTILE"
    if value < c["positive_threshold"]:
        return ABSTAIN, "BOUNDARY_BAND"
    if rule["require_monotonic_blocks"] and not row.monotonic_centered_blocks:
        return ABSTAIN, "HIGH_RATIO_NOT_MONOTONIC"
    if rule["require_exceeds_context_max"]:
        if not row.context_coverage_ok or row.context_fraction < rule["minimum_context_fraction"]:
            return ABSTAIN, "HIGH_RATIO_NO_CAUSAL_CONTEXT"
        if not row.late_block_exceeds_context:
            return ABSTAIN, "HIGH_RATIO_NOT_ABOVE_RECENT_HISTORY"
    return POS, "HIGH_RATIO_MONOTONIC_AND_ABOVE_HISTORY"


def apply_rules(measurements: pd.DataFrame, calibration: dict, spec: dict) -> pd.DataFrame:
    """Gán trạng thái proxy cho mọi cửa sổ (kể cả cửa sổ không hợp lệ -> ABSTAIN có lý do)."""
    rows = []
    for row in measurements.itertuples(index=False):
        domain = calibration["domains"].get(row.dataset_source, {"calibrated": False, "reason": "UNKNOWN_DOMAIN"})
        result = {"window_id": row.window_id}
        if not row.angle23_complete:
            for target in TARGETS:
                result[f"{target}_status"], result[f"{target}_reason"] = ABSTAIN, "INCOMPLETE_ANGLE_FEATURES"
        elif not row.statistics_valid:
            for target in TARGETS:
                result[f"{target}_status"], result[f"{target}_reason"] = ABSTAIN, "INVALID_OR_MISSING_SIGNAL"
        else:
            result["PERSISTENT_OFFSET_status"], result["PERSISTENT_OFFSET_reason"] = _offset(row, spec)
            if domain["calibrated"]:
                result["RELATIVE_HIGH_ROLL_status"], result["RELATIVE_HIGH_ROLL_reason"] = _high_roll(row._asdict(), domain)
                result["AMPLITUDE_GROWTH_status"], result["AMPLITUDE_GROWTH_reason"] = _growth(row, domain, spec)
            else:
                for target in CALIBRATED_TARGETS:
                    result[f"{target}_status"] = ABSTAIN
                    result[f"{target}_reason"] = domain.get("reason", "DOMAIN_NOT_CALIBRATED")
        positives = [t for t in TARGETS if result[f"{t}_status"] == POS]
        if positives:
            status = "PHENOTYPE_PROXY"
        elif all(result[f"{t}_status"] == NEG for t in TARGETS):
            status = "NO_PROXY_TRIGGERED"
        else:
            status = "ABSTAIN"
        result.update({"proxy_window_status": status, "proxy_phenotypes": json.dumps(positives),
                       "multi_label": len(positives) > 1, "offset_reference": "SENSOR_DATUM_UNVERIFIED",
                       "physical_heel_claim": False, "label_source": "PROXY_RULE",
                       "rule_version": calibration["rule_version"], "calibration_id": calibration["calibration_id"]})
        rows.append(result)
    return pd.DataFrame(rows)


def supporting_measurements(row: pd.Series, calibration: dict) -> str:
    """JSON số đo hỗ trợ cho một cửa sổ (dùng trong bảng proxy)."""
    keys = ("roll_std_60", "roll_mean_180_stat", "roll_centered_std_180", "roll_dominant_sign_ratio_180_stat",
            "offset_to_oscillation_ratio", "sub_block_mean_sign_pattern", "block_centered_std_json",
            "log_centered_std_ratio", "raw_rms_ratio", "monotonic_centered_blocks", "context_fraction",
            "context_max_sub_std", "late_block_exceeds_context")
    payload = {k: (row[k] if not isinstance(row[k], float) or math.isfinite(row[k]) else None) for k in keys if k in row}
    domain = calibration["domains"].get(row["dataset_source"], {})
    payload["thresholds"] = {t: {k: domain[t][k] for k in ("positive_threshold", "negative_threshold")}
                             for t in CALIBRATED_TARGETS if domain.get("calibrated")}
    return json.dumps(payload, sort_keys=True, default=lambda v: v.item() if hasattr(v, "item") else str(v))


__all__ = ["ANGLE_FEATURES", "TARGETS", "load_spec", "window_statistics", "fit_calibration", "apply_rules",
           "session_weighted_quantile", "supporting_measurements", "POS", "NEG", "ABSTAIN"]
