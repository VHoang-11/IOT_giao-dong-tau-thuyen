"""Phân tích AI-assisted cho pilot 29 record (chỉ gợi ý, không phải human review).

Module đọc trực tiếp chuỗi Roll/Pitch đã preprocessing của từng cửa sổ review,
tính lại chỉ số, đối chiếu với feature table hiện có và áp dụng các quy tắc quan
sát tường minh (không dùng ngưỡng an toàn tuyệt đối, không dùng phân vị dataset
làm ngưỡng). Output chỉ được ghi vào ``ml/data/labels/ai_assisted_review/`` và
báo cáo ``ml/reports/labeling/ai_assisted_pilot_analysis.md``; module không chạm
vào decision ledger, audit history hay bảng nhãn verified.

Chạy từ repository root::

    python -m ml.labeling.ai_assisted_review
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from ml.features.calculations import dominant_sign_ratio, period_values, population_std, rms

from .human_review_workflow import ANGLE_FEATURES, INITIAL_BATCH_NAME

RULE_VERSION = "ai_observation_rules_v0.1"
ANNOTATION_METHOD = "AI_SUGGESTED"
SAMPLING_HZ = 10.0
DT = 1.0 / SAMPLING_HZ
WINDOW_SECONDS = 180.0
SUB_BLOCK_SECONDS = 20.0
N_SUB_BLOCKS = 9
MIN_FRACTION = 0.95
MAX_GAP_FACTOR = 1.5
FAMILY_ALPHA = 0.05
PERIOD_FEATURES = ("roll_period_est_180", "roll_zero_crossings_180", "roll_period_cv_180")
PHENOTYPES = ("HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH")

BATCH_PATH = Path("ml/data/labels/annotation_pilot/batches/pilot_29.csv")
FORMS_PATH = Path("ml/data/labels/annotation_pilot/annotation_pilot.csv")
OUTPUT_DIR = Path("ml/data/labels/ai_assisted_review")
CSV_NAME = "pilot_29_ai_suggestions.csv"
METRICS_NAME = "pilot_29_ai_metrics.json"
REPORT_PATH = Path("ml/reports/labeling/ai_assisted_pilot_analysis.md")
PROTECTED_PATHS = (
    Path("ml/data/labels/annotation_pilot/review_decisions.csv"),
    Path("ml/data/labels/annotation_pilot/review_audit.jsonl"),
    Path("ml/data/labels/annotation_pilot/annotation_pilot.csv"),
    Path("ml/data/labels/annotation_pilot/human_annotation_quality_summary.json"),
)
PROTECTED_GLOBS = ("ml/data/labels/feasibility/*/verified_reviewed_annotations.parquet",)

CSV_COLUMNS = (
    "review_id", "dataset_source", "session_id", "segment_id", "window_start_seconds",
    "window_end_seconds", "suggested_label", "observed_phenotype_flags", "evidence_summary",
    "supporting_feature_values", "temporal_evidence", "contradictory_evidence",
    "uncertainty_reason", "evidence_reference", "annotation_method", "requires_human_review",
    "rule_version",
)
ALLOWED_SUGGESTIONS = ("HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH",
                       "REVIEW_REQUIRED", "UNLABELED")  # NORMAL cố ý không có trong danh sách


# --------------------------------------------------------------------------- thống kê


def mann_kendall_exact_increasing(values) -> tuple[int, float]:
    """Mann–Kendall S và p một phía (xu hướng tăng) theo phân phối chính xác.

    Phân phối số nghịch thế (số Mahonian) cho n phần tử không trùng; S = M - 2·inv.
    Trả p = P(S >= S_obs | H0: thứ tự ngẫu nhiên). Giá trị trùng làm S nhỏ hơn
    nên p được giữ bảo thủ.
    """
    v = np.asarray(values, dtype=float)
    n = len(v)
    if n < 3 or not np.all(np.isfinite(v)):
        raise ValueError("Mann–Kendall cần ít nhất 3 giá trị hữu hạn.")
    s = int(sum(np.sign(v[j] - v[i]) for i in range(n) for j in range(i + 1, n)))
    dist = np.array([1.0])
    for k in range(1, n + 1):
        new = np.zeros(len(dist) + k - 1)
        for d in range(k):
            new[d:d + len(dist)] += dist
        dist = new
    dist /= dist.sum()
    m = n * (n - 1) // 2
    s_values = m - 2 * np.arange(len(dist))
    return s, float(dist[s_values >= s].sum())


def _slice(t: np.ndarray, x: np.ndarray, lower: float, upper: float) -> np.ndarray:
    """Mẫu có timestamp thuộc (lower, upper], cùng quy ước với feature extractor."""
    left = int(np.searchsorted(t, lower, side="right"))
    right = int(np.searchsorted(t, upper, side="right"))
    return x[left:right]


def _linear_fit(y: np.ndarray) -> tuple[float, float]:
    u = np.array([30.0, 90.0, 150.0])
    slope = float(np.polyfit(u, y, 1)[0])
    pred = np.polyval(np.polyfit(u, y, 1), u)
    sst = float(np.sum((y - y.mean()) ** 2))
    r2 = float(1 - np.sum((y - pred) ** 2) / sst) if sst > 0 else math.nan
    return slope * 60.0, r2


def _half_cycle_amplitudes(x: np.ndarray) -> np.ndarray:
    centered = x - x.mean()
    crossings = np.where(np.diff(np.sign(centered)) != 0)[0]
    amps = [np.abs(centered[a + 1:b + 1]).max() for a, b in zip(crossings[:-1], crossings[1:]) if b > a]
    return np.asarray(amps, dtype=float)


def _round(value, digits: int = 4):
    if value is None:
        return None
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_round(v, digits) for v in value]
    value = float(value)
    return None if not math.isfinite(value) else round(value, digits)


# --------------------------------------------------------------------------- dữ liệu


def load_batch(repo_root: Path) -> pd.DataFrame:
    batch = pd.read_csv(repo_root / BATCH_PATH, keep_default_na=False)
    forms = pd.read_csv(repo_root / FORMS_PATH, keep_default_na=False)
    if len(batch) != 29 or batch.review_id.duplicated().any():
        raise ValueError(f"Batch pilot phải có 29 review_id duy nhất, nhận {len(batch)}.")
    if not batch.review_id.eq(batch.review_sample_id).all():
        raise ValueError("review_id và review_sample_id trong batch không trùng nhau.")
    if not set(batch.batch_name) == {INITIAL_BATCH_NAME}:
        raise ValueError("Batch không phải pilot_29.")
    merged = batch.merge(forms[["review_sample_id", "dataset_source", "session_id", "segment_id",
                                "window_start_seconds", "window_end_seconds"]],
                         on="review_sample_id", suffixes=("", "_form"), how="left", validate="one_to_one")
    for column in ("dataset_source", "session_id", "segment_id", "window_start_seconds", "window_end_seconds"):
        if not merged[column].astype(str).eq(merged[f"{column}_form"].astype(str)).all():
            raise ValueError(f"Batch và form pilot lệch nhau ở cột {column}.")
    return batch


def _segment_path(repo_root: Path, record) -> Path:
    return (repo_root / "ml/data/processed" / record.dataset_source / record.session_id
            / record.segment_id / "timeseries.parquet")


def load_feature_row(repo_root: Path, record, cache: dict) -> tuple[dict, dict, str]:
    ds = record.dataset_source
    if ds not in cache:
        base = repo_root / "ml/data/features" / ds
        cache[ds] = (pd.read_parquet(base / "feature_values.parquet"),
                     pd.read_parquet(base / "feature_metadata.parquet"))
    values, metadata = cache[ds]
    mask = (metadata.session_id.astype(str).eq(record.session_id)
            & metadata.segment_id.astype(str).eq(record.segment_id)
            & ((pd.to_numeric(metadata.window_end_seconds) - float(record.window_end_seconds)).abs() <= 1e-6))
    matched = metadata.loc[mask]
    if len(matched) != 1:
        raise ValueError(f"Không khớp duy nhất feature metadata cho {record.review_id}.")
    window_id = str(matched.iloc[0].window_id)
    row = values.loc[values.window_id.astype(str).eq(window_id)]
    if len(row) != 1:
        raise ValueError(f"Không khớp duy nhất feature values cho {record.review_id}.")
    return row.iloc[0].to_dict(), json.loads(matched.iloc[0].validity_json), window_id


def dataset_std_rank(repo_root: Path, dataset: str, value: float, cache: dict) -> tuple[float, int]:
    """Hạng phần trăm mô tả của roll_std_60 giữa các cửa sổ angle-only hợp lệ cùng nguồn.

    Chỉ dùng để mô tả "tương đối mạnh/yếu trong nguồn"; KHÔNG phải ngưỡng phân lớp.
    """
    key = f"rank::{dataset}"
    if key not in cache:
        values, metadata = cache[dataset]
        valid = metadata.validity_json.map(
            lambda text: all(json.loads(text)[name]["status"] == "VALID" for name in ANGLE_FEATURES))
        ids = set(metadata.loc[valid, "window_id"].astype(str))
        cache[key] = np.sort(values.loc[values.window_id.astype(str).isin(ids), "roll_std_60"].to_numpy(float))
    population = cache[key]
    return float(np.searchsorted(population, value + 1e-12, side="right") / len(population)), int(len(population))


# --------------------------------------------------------------------------- phân tích một record


def analyze_record(repo_root: Path, record, feature_cache: dict) -> dict:
    path = _segment_path(repo_root, record)
    frame = pd.read_parquet(path)
    identity = {c: frame[c].astype(str).unique().tolist() for c in ("dataset_source", "session_id", "segment_id")}
    if identity != {"dataset_source": [record.dataset_source], "session_id": [record.session_id],
                    "segment_id": [record.segment_id]}:
        raise ValueError(f"Parquet {path} không khớp định danh của {record.review_id}.")
    t = frame.time_seconds.to_numpy(float)
    roll = frame.roll_deg.to_numpy(float)
    pitch = frame.pitch_deg.to_numpy(float)
    start, end = float(record.window_start_seconds), float(record.window_end_seconds)
    seg_first, seg_last = float(t[0]), float(t[-1])

    x = _slice(t, roll, start, end)
    tw = _slice(t, t, start, end)
    p = _slice(t, pitch, start, end)
    gaps = np.diff(tw)
    boundary = {
        "segment_first_time_s": seg_first, "segment_last_time_s": seg_last,
        "window_inside_segment": bool(seg_first <= start + 1e-9 and end <= seg_last + 1e-9),
        "window_samples": int(len(x)), "expected_samples": int(round(WINDOW_SECONDS * SAMPLING_HZ)),
        "finite_roll_samples": int(np.isfinite(x).sum()), "finite_pitch_samples": int(np.isfinite(p).sum()),
        "max_dt_s": float(gaps.max()), "min_dt_s": float(gaps.min()),
        "no_gap_over_1_5_dt": bool(gaps.max() <= MAX_GAP_FACTOR * DT + 1e-8),
        "window_length_s": end - start,
        # Chỉ là provenance độ dài segment; không dùng giá trị tín hiệu sau endpoint.
        "segment_seconds_after_endpoint": seg_last - end,
    }
    boundary["passed"] = bool(boundary["window_inside_segment"] and boundary["no_gap_over_1_5_dt"]
                              and boundary["window_samples"] == boundary["expected_samples"]
                              and boundary["finite_roll_samples"] == len(x)
                              and math.isclose(end - start, WINDOW_SECONDS, abs_tol=1e-6))
    if not boundary["passed"]:
        raise ValueError(f"Cửa sổ {record.review_id} vi phạm ranh giới/coverage: {boundary}")

    # Block 3×60 s và sub-block 9×20 s (cũ -> mới), cùng quy ước (lower, upper].
    blocks = [_slice(t, roll, end - 180 + 60 * k, end - 120 + 60 * k) for k in range(3)]
    subs = [_slice(t, roll, end - 180 + 20 * k, end - 160 + 20 * k) for k in range(N_SUB_BLOCKS)]
    pitch_subs = [_slice(t, pitch, end - 180 + 20 * k, end - 160 + 20 * k) for k in range(N_SUB_BLOCKS)]
    if any(len(b) < MIN_FRACTION * 600 for b in blocks) or any(len(s) < MIN_FRACTION * 200 for s in subs):
        raise ValueError(f"Block/sub-block thiếu coverage: {record.review_id}")
    block_mean = np.array([b.mean() for b in blocks])
    block_rms = np.array([rms(b) for b in blocks])
    block_std = np.array([population_std(b) for b in blocks])
    sub_std = np.array([population_std(s) for s in subs])
    sub_mean = np.array([s.mean() for s in subs])

    # Bối cảnh lịch sử: (start-180, start], không vượt đầu segment, không dùng dữ liệu sau endpoint.
    ctx_lower = max(start - WINDOW_SECONDS, seg_first - DT)
    ctx = _slice(t, roll, ctx_lower, start)
    ctx_coverage = min(1.0, len(ctx) / (WINDOW_SECONDS * SAMPLING_HZ))
    ctx_subs = [_slice(t, roll, start - 180 + 20 * k, start - 160 + 20 * k) for k in range(N_SUB_BLOCKS)]
    ctx_sub_std = [population_std(s) if len(s) >= MIN_FRACTION * 200 else math.nan for s in ctx_subs]
    ctx_valid_sub_std = [v for v in ctx_sub_std if math.isfinite(v)]
    history = _slice(t, roll, seg_first - DT, end)

    # Chu kỳ: zero-crossing (tái sử dụng hàm của feature pipeline) và đỉnh phổ để đối chiếu.
    periods, crossing_count = period_values(tw, x, DT, MAX_GAP_FACTOR)
    periods = np.asarray(periods, dtype=float)
    centered = x - x.mean()
    power = np.abs(np.fft.rfft(centered * np.hanning(len(centered)))) ** 2
    freqs = np.fft.rfftfreq(len(centered), DT)
    peak = int(np.argmax(power[1:]) + 1)
    spectral_period = float(1.0 / freqs[peak])
    if len(periods) >= 3:
        q1, q3 = np.percentile(periods, [25, 75])
        period_cv = float(np.std(periods) / np.mean(periods))
        period_status = "ZC_AND_SPECTRUM_AGREE" if q1 <= spectral_period <= q3 else "ZC_AND_SPECTRUM_DISAGREE"
    else:
        q1 = q3 = period_cv = math.nan
        period_status = "INSUFFICIENT_CROSSINGS"
    unique_values = np.unique(np.round(x, 6))
    quant_step = float(np.diff(unique_values).min()) if len(unique_values) < len(x) / 2 else None

    amps = _half_cycle_amplitudes(x)
    amp_ac1 = float(np.corrcoef(amps[:-1], amps[1:])[0, 1]) if len(amps) > 3 else math.nan
    mk_s, mk_p = mann_kendall_exact_increasing(sub_std)
    rms_slope, rms_r2 = _linear_fit(block_rms)
    std_slope, std_r2 = _linear_fit(block_std)

    # Thời điểm khởi phát: sub-block đầu tiên mà nó và mọi sub-block sau đều vượt cực đại lịch sử trước đó.
    onset_index = None
    for k in range(1, N_SUB_BLOCKS):
        before = [*sub_std[:k], *ctx_valid_sub_std]
        if all(v > max(before) for v in sub_std[k:]):
            onset_index = k
            break
    pitch_blocks = [_slice(t, pitch, end - 180 + 60 * k, end - 120 + 60 * k) for k in range(3)]

    feature_row, validity, window_id = load_feature_row(repo_root, record, feature_cache)
    rank, rank_population = dataset_std_rank(repo_root, record.dataset_source, population_std(blocks[2]), feature_cache)

    metrics = {
        "review_id": record.review_id, "dataset_source": record.dataset_source,
        "session_id": record.session_id, "segment_id": record.segment_id,
        "window_start_seconds": start, "window_end_seconds": end,
        "processed_path": path.relative_to(repo_root).as_posix(),
        "feature_window_id": window_id, "plot_path": record.plot_path,
        "boundary_check": boundary,
        "roll": {
            "mean": float(x.mean()), "median": float(np.median(x)), "std_population": population_std(x),
            "rms": rms(x), "centered_rms": population_std(x), "peak_to_peak": float(x.max() - x.min()),
            "min": float(x.min()), "max": float(x.max()), "abs_p95": float(np.percentile(np.abs(x), 95)),
            "dominant_sign_ratio": dominant_sign_ratio(x),
            "offset_to_oscillation_ratio": float(abs(x.mean()) / population_std(x)),
            "unique_values": int(len(unique_values)), "quantization_step_deg": quant_step,
        },
        "pitch": {"std_population": population_std(p), "peak_to_peak": float(p.max() - p.min()),
                  "early60_centered_std": population_std(pitch_blocks[0]),
                  "late60_centered_std": population_std(pitch_blocks[2]),
                  "sub_block_std_20s": [population_std(s) for s in pitch_subs]},
        "growth_onset": {"sub_block_index": onset_index,
                         "time_s": None if onset_index is None else end - 180 + SUB_BLOCK_SECONDS * onset_index,
                         "definition": "first 20 s sub-block from which every later sub-block exceeds all earlier window and context sub-block std"},
        "blocks_60s": {"mean": block_mean.tolist(), "rms": block_rms.tolist(), "centered_std": block_std.tolist(),
                       "mean_std": population_std(block_mean), "mean_shift": float(block_mean[2] - block_mean[0]),
                       "rms_ratio": float(block_rms[2] / block_rms[0]), "rms_slope_deg_per_min": rms_slope,
                       "rms_trend_r2": rms_r2, "centered_std_ratio": float(block_std[2] / block_std[0]),
                       "centered_std_slope_deg_per_min": std_slope, "centered_std_trend_r2": std_r2},
        "sub_blocks_20s": {"centered_std": sub_std.tolist(), "mean": sub_mean.tolist(),
                           "mean_sign_pattern": "".join("+" if v > 0 else "-" if v < 0 else "0" for v in sub_mean),
                           "mann_kendall_S": mk_s, "mann_kendall_p_one_sided": mk_p},
        "context": {"samples": int(len(ctx)), "coverage_fraction": ctx_coverage,
                    "mean": float(ctx.mean()) if len(ctx) else None,
                    "std_population": population_std(ctx) if len(ctx) > 1 else None,
                    "dominant_sign_ratio": dominant_sign_ratio(ctx) if len(ctx) else None,
                    "all_same_sign_as_window": bool(len(ctx) and np.all(np.sign(ctx) == np.sign(x.mean()))),
                    "sub_block_std_20s": ctx_sub_std,
                    "max_valid_sub_block_std": max(ctx_valid_sub_std) if ctx_valid_sub_std else None,
                    "segment_history_seconds_to_endpoint": float(end - seg_first),
                    "segment_mean_to_endpoint": float(history.mean())},
        "period": {"zero_crossings": int(crossing_count), "upward_periods": int(len(periods)),
                   "median_period_s": float(np.median(periods)) if len(periods) else None,
                   "period_q1_s": _round(q1, 6), "period_q3_s": _round(q3, 6), "period_cv": _round(period_cv, 6),
                   "spectral_peak_period_s": spectral_period, "spectral_resolution_hz": float(freqs[1]),
                   "status": period_status},
        "half_cycle_amplitude": {"count": int(len(amps)), "lag1_autocorrelation": amp_ac1},
        "dataset_relative": {"late60_centered_std_percentile_rank_in_dataset": rank,
                             "population_windows": rank_population,
                             "note": "descriptive only; not a classification threshold"},
        "feature_table": {name: (None if feature_row.get(name) is None or pd.isna(feature_row.get(name))
                                 else float(feature_row[name])) for name in (*ANGLE_FEATURES, *PERIOD_FEATURES)},
        "feature_validity": {name: validity[name]["status"] for name in (*ANGLE_FEATURES, *PERIOD_FEATURES)},
    }
    metrics["feature_parity"] = feature_parity(metrics, x, blocks, p_last60=_slice(t, pitch, end - 60, end))
    return metrics


def feature_parity(metrics: dict, x: np.ndarray, blocks: list[np.ndarray], p_last60: np.ndarray) -> dict:
    """Tính lại độc lập bằng numpy và so với feature_values.parquet."""
    last = blocks[2]
    p95 = lambda v: float(np.percentile(v, 95))  # numpy 'linear' = Type-7
    centers = np.array([30.0, 90.0, 150.0])
    brms = np.array([np.sqrt(np.mean(b ** 2)) for b in blocks])
    bp95 = np.array([p95(np.abs(b)) for b in blocks])
    bmean = np.array([b.mean() for b in blocks])
    fit = np.polyfit(centers, brms, 1)
    pred = np.polyval(fit, centers)
    recomputed = {
        "roll_rms_60": np.sqrt(np.mean(last ** 2)), "roll_std_60": np.std(last), "roll_mean_60": last.mean(),
        "roll_peak_to_peak_60": np.ptp(last), "roll_abs_p95_60": p95(np.abs(last)),
        "roll_abs_max_60": np.abs(last).max(),
        "roll_iqr_60": np.percentile(last, 75) - np.percentile(last, 25),
        "roll_diff_rms_60": np.sqrt(np.mean(np.diff(last) ** 2)),
        "roll_mean_180": x.mean(), "roll_median_180": np.median(x), "roll_mean_abs_180": np.abs(x).mean(),
        "roll_dominant_sign_ratio_180": max((x > 0).sum(), (x < 0).sum()) / ((x > 0).sum() + (x < 0).sum()),
        "roll_segment_mean_std_180": np.std(bmean), "roll_mean_shift_180": bmean[2] - bmean[0],
        "roll_rms_early_60": brms[0], "roll_rms_late_60": brms[2], "roll_rms_ratio_180": brms[2] / brms[0],
        "roll_rms_slope_180": np.polyfit(centers, brms, 1)[0] * 60,
        "roll_rms_trend_r2_180": 1 - np.sum((brms - pred) ** 2) / np.sum((brms - brms.mean()) ** 2),
        "roll_p95_trend_slope_180": np.polyfit(centers, bp95, 1)[0] * 60,
        "pitch_rms_60": np.sqrt(np.mean(p_last60 ** 2)), "pitch_std_60": np.std(p_last60),
        "pitch_peak_to_peak_60": np.ptp(p_last60),
        "roll_zero_crossings_180": metrics["period"]["zero_crossings"],
        "roll_period_est_180": metrics["period"]["median_period_s"],
        "roll_period_cv_180": metrics["period"]["period_cv"],
    }
    differences = {}
    for name, value in recomputed.items():
        stored = metrics["feature_table"].get(name)
        if stored is None or value is None:
            differences[name] = None if stored is None and value is None else "MISMATCH_NULL"
            continue
        differences[name] = abs(float(value) - stored)
    numeric = [v for v in differences.values() if isinstance(v, float)]
    worst = max(differences, key=lambda k: differences[k] if isinstance(differences[k], float) else -1)
    tolerance = lambda name: 1e-5 * max(1.0, abs(metrics["feature_table"].get(name) or 0.0))
    passed = all(isinstance(v, float) and v <= tolerance(k) for k, v in differences.items())
    return {"features_compared": len(differences), "max_abs_difference": max(numeric) if numeric else None,
            "worst_feature": worst, "passed": bool(passed),
            "method": "numpy recomputation (np.std ddof=0, np.percentile linear=Type-7, np.polyfit) vs feature_values.parquet; tolerance 1e-5 relative"}


# --------------------------------------------------------------------------- quy tắc quan sát


def evaluate_rules(metrics: dict, n_records: int) -> dict:
    """Quy tắc quan sát v0.1 (đề xuất của AI, CHƯA được nhóm phê duyệt).

    Không có ngưỡng biên độ tuyệt đối nào; mọi tiêu chí dựa trên dấu, tính đơn điệu,
    kiểm định thứ hạng hoặc so sánh với chính lịch sử của cùng segment.
    """
    roll, blocks, subs, ctx = metrics["roll"], metrics["blocks_60s"], metrics["sub_blocks_20s"], metrics["context"]
    alpha_family = FAMILY_ALPHA / n_records

    # PERSISTENT_OFFSET
    same_sign_subs = subs["mean_sign_pattern"] in ("+" * N_SUB_BLOCKS, "-" * N_SUB_BLOCKS)
    window_never_crosses = roll["dominant_sign_ratio"] == 1.0
    has_context = ctx["samples"] > 1
    ctx_mean_same_sign = (not has_context) or (np.sign(ctx["mean"]) == np.sign(roll["mean"]))
    if window_never_crosses and same_sign_subs and ((not has_context) or ctx["all_same_sign_as_window"]):
        offset = "OBSERVED_CONSISTENT"
    elif same_sign_subs and ctx_mean_same_sign:
        offset = "OBSERVED_WEAK"
    else:
        offset = "NOT_OBSERVED"

    # AMPLITUDE_GROWTH (dùng std quanh trung bình để tách khỏi offset)
    s = blocks["centered_std"]
    monotonic = s[0] < s[1] < s[2]
    ctx_max = ctx["max_valid_sub_block_std"]
    exceeds_history = ctx_max is None or s[2] > ctx_max
    p_mk = subs["mann_kendall_p_one_sided"]
    observed_subs = [*subs["centered_std"], *[v for v in ctx["sub_block_std_20s"] if math.isfinite(v)]]
    latest_is_record = subs["centered_std"][-1] >= max(observed_subs)
    if p_mk < alpha_family and monotonic and exceeds_history:
        growth = "OBSERVED_CONSISTENT"
    elif p_mk < FAMILY_ALPHA or (monotonic and latest_is_record):
        growth = "OBSERVED_WEAK"
    else:
        growth = "NOT_OBSERVED"

    flags = {"HIGH_ROLL": "NOT_ASSESSABLE_NO_VALIDATED_ENVELOPE", "PERSISTENT_OFFSET": offset,
             "AMPLITUDE_GROWTH": growth, "NORMAL": "NOT_ASSESSABLE_NO_VALIDATED_ENVELOPE"}
    consistent = [k for k in PHENOTYPES if flags[k] == "OBSERVED_CONSISTENT"]
    weak = [k for k in PHENOTYPES if flags[k] == "OBSERVED_WEAK"]
    if len(consistent) == 1 and not weak:
        label = consistent[0]
    elif consistent or weak:
        label = "REVIEW_REQUIRED"
    else:
        label = "UNLABELED"
    return {"flags": flags, "suggested_label": label, "consistent": consistent, "weak": weak,
            "alpha_family": alpha_family, "growth_monotonic_60s": bool(monotonic),
            "growth_exceeds_history": bool(exceeds_history), "growth_latest_subblock_is_record": bool(latest_is_record),
            "offset_subblock_sign_consistent": bool(same_sign_subs),
            "offset_window_never_crosses_datum": bool(window_never_crosses)}


# --------------------------------------------------------------------------- văn bản tiếng Việt

DATASET_NOTES = {
    "hohai": ("Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không "
              "phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, "
              "cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận."),
    "seafar": ("Seafar là tàu thật nhưng chỉ có một session; timestamp epoch ms, khoảng 10 Hz gốc, không áp bộ lọc; "
               "Roll lượng tử hóa theo bước 0.01°; trường rate chưa xác minh trục/dấu nên gyro không được dùng; "
               "session bị tách segment do gap/duplicate; độ tin cậy trục/dấu được provenance ghi là thấp."),
    "southampton": ("Southampton là mô hình KCS trong bể thử (model-scale), chỉ Run 14 đủ 180 giây; timestamp lấy từ CSV; "
                    "Roll/Pitch lọc Butterworth nhân quả 4 Hz, 50→10 Hz; Delta Angle chưa map sang gyro; bốn cửa sổ "
                    "pilot cùng một run nên không phải quan sát độc lập."),
}
FLAG_VI = {
    "OBSERVED_CONSISTENT": "quan sát thấy, nhất quán",
    "OBSERVED_WEAK": "dấu hiệu yếu/chưa kết luận",
    "NOT_OBSERVED": "không quan sát thấy theo quy tắc",
    "NOT_ASSESSABLE_NO_VALIDATED_ENVELOPE": "không đánh giá được (chưa có operating envelope được xác thực)",
}
LABEL_VI = {
    "PERSISTENT_OFFSET": "PERSISTENT_OFFSET (phenotype tín hiệu đo, AI gợi ý, cần người xác nhận)",
    "AMPLITUDE_GROWTH": "AMPLITUDE_GROWTH (phenotype tín hiệu đo, AI gợi ý, cần người xác nhận)",
    "REVIEW_REQUIRED": "REVIEW_REQUIRED (có dấu hiệu nhưng chưa đủ căn cứ hoặc nhiều phenotype chồng lấn)",
    "UNLABELED": "UNLABELED (không có dấu hiệu phenotype theo quy tắc, nhưng không đủ căn cứ để gọi NORMAL)",
}


def f(value, digits: int = 3) -> str:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "không xác định"
    return f"{float(value):.{digits}f}"


def flist(values, digits: int = 3) -> str:
    return "[" + ", ".join(f(v, digits) for v in values) + "]"


def _sign_word(value: float) -> str:
    return "dương" if value > 0 else "âm"


def describe_record(m: dict, rules: dict) -> dict:
    roll, blocks, subs, ctx, per = m["roll"], m["blocks_60s"], m["sub_blocks_20s"], m["context"], m["period"]
    pitch, flags, ft = m["pitch"], rules["flags"], m["feature_table"]
    offset, growth = flags["PERSISTENT_OFFSET"], flags["AMPLITUDE_GROWTH"]
    n_same = max(subs["mean_sign_pattern"].count("+"), subs["mean_sign_pattern"].count("-"))
    rank = m["dataset_relative"]["late60_centered_std_percentile_rank_in_dataset"]

    observations = []
    if offset == "OBSERVED_CONSISTENT":
        observations.append(
            f"Roll lệch {_sign_word(roll['mean'])} ổn định: mean {f(roll['mean'])}°, median {f(roll['median'])}°, "
            f"100% mẫu cùng dấu (tín hiệu không cắt mốc 0 trong 180 s), {n_same}/9 sub-block 20 s cùng dấu.")
    elif offset == "OBSERVED_WEAK":
        observations.append(
            f"Độ lệch có dấu nhỏ: mean {f(roll['mean'])}°, {n_same}/9 sub-block 20 s cùng dấu nhưng dao động vẫn cắt "
            f"mốc 0 (sign ratio {f(roll['dominant_sign_ratio'])}, |mean|/std {f(roll['offset_to_oscillation_ratio'], 2)}).")
    else:
        observations.append(
            f"Không thấy độ lệch có dấu bền vững: mean {f(roll['mean'])}°, mẫu dấu sub-block `{subs['mean_sign_pattern']}`, "
            f"sign ratio {f(roll['dominant_sign_ratio'])}.")
    s = blocks["centered_std"]
    if growth == "OBSERVED_CONSISTENT":
        observations.append(
            f"Biên độ dao động (std quanh trung bình) tăng nhất quán: block 60 s {flist(s)}° "
            f"(tỷ lệ muộn/sớm {f(blocks['centered_std_ratio'], 2)}), Mann–Kendall p={f(subs['mann_kendall_p_one_sided'], 4)} "
            f"< α hiệu chỉnh {f(rules['alpha_family'], 4)}.")
    elif growth == "OBSERVED_WEAK":
        observations.append(
            f"Có dấu hiệu tăng biên độ nhưng chưa nhất quán: block 60 s {flist(s)}°, Mann–Kendall p={f(subs['mann_kendall_p_one_sided'], 4)} "
            f"(không đạt α hiệu chỉnh {f(rules['alpha_family'], 4)}).")
    else:
        observations.append(
            f"Không thấy tăng biên độ bền vững: std block 60 s {flist(s)}°, Mann–Kendall p={f(subs['mann_kendall_p_one_sided'], 4)}.")
    observations.append(
        f"Dao động Roll quanh trung bình: std {f(roll['std_population'])}°, peak-to-peak {f(roll['peak_to_peak'])}°; "
        f"std 60 s cuối ở hạng phần trăm {f(100 * rank, 0)} trong {m['dataset_relative']['population_windows']} cửa sổ hợp lệ "
        f"cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).")
    if per["status"] == "ZC_AND_SPECTRUM_AGREE":
        observations.append(
            f"Chu kỳ ước lượng {f(per['median_period_s'], 2)} s (zero-crossing) khớp đỉnh phổ {f(per['spectral_peak_period_s'], 2)} s; "
            f"CV chu kỳ {f(per['period_cv'], 2)}."
            + (" Tuy vậy CV > 1 (độ phân tán chu kỳ lớn hơn chính chu kỳ trung bình) nên chu kỳ chỉ đại diện cho phần "
               "dao động rõ trong cửa sổ, không ổn định trên toàn 180 s." if per["period_cv"] and per["period_cv"] > 1 else ""))
    else:
        observations.append(
            f"Chu kỳ chưa tin cậy: zero-crossing {f(per['median_period_s'], 2)} s, đỉnh phổ {f(per['spectral_peak_period_s'], 2)} s "
            f"(nằm ngoài IQR chu kỳ zero-crossing), CV {f(per['period_cv'], 2)}.")

    supporting, contradictory, uncertainty, questions = [], [], [], []
    # ---- PERSISTENT_OFFSET
    if offset in ("OBSERVED_CONSISTENT", "OBSERVED_WEAK"):
        supporting.append(
            f"Mean các block 60 s {flist(blocks['mean'])}° (độ lệch chuẩn giữa block {f(blocks['mean_std'], 4)}°, "
            f"mean shift {f(blocks['mean_shift'], 4)}°).")
        if ctx["samples"] > 1:
            supporting.append(
                f"Bối cảnh 180 s trước cửa sổ (coverage {f(100 * ctx['coverage_fraction'], 0)}%) có mean {f(ctx['mean'])}°, "
                f"sign ratio {f(ctx['dominant_sign_ratio'])}; trung bình Roll từ đầu segment đến endpoint "
                f"({f(ctx['segment_history_seconds_to_endpoint'], 0)} s) là {f(ctx['segment_mean_to_endpoint'])}°.")
        contradictory.append(
            "Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực "
            "(list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.")
        if offset == "OBSERVED_WEAK":
            contradictory.append(
                f"Dao động cắt qua mốc 0 ({f(100 * (1 - roll['dominant_sign_ratio']), 1)}% mẫu mang dấu ngược) và |mean|/std chỉ "
                f"{f(roll['offset_to_oscillation_ratio'], 2)}; tiêu chí 9/9 sub-block cùng dấu là bằng chứng thống kê, không phải "
                "bằng chứng độ lệch có ý nghĩa vật lý.")
            questions.append(
                f"Độ lệch {f(roll['mean'])}° có vượt sai số zero của cảm biến/khung thử không, và nhóm có định nghĩa biên độ "
                "tối thiểu cho PERSISTENT_OFFSET không?")
        else:
            questions.append(
                f"Mốc 0 của Roll ở nguồn {m['dataset_source']} đã được hiệu chuẩn chưa? Độ lệch {f(roll['mean'])}° là nghiêng "
                "thực của tàu/mô hình hay sai lệch lắp đặt?")
    else:
        pattern = subs["mean_sign_pattern"]
        if sum(a != b for a, b in zip(pattern, pattern[1:])) == 1:
            contradictory.append(
                f"Mean 20 s đổi dấu đúng một lần (mẫu `{pattern}`, mean shift {f(blocks['mean_shift'], 4)}°): đây là trôi "
                "trung bình qua mốc 0, không phải lệch ổn định về dấu.")
    # ---- AMPLITUDE_GROWTH
    p_mk = subs["mann_kendall_p_one_sided"]
    if growth in ("OBSERVED_CONSISTENT", "OBSERVED_WEAK"):
        supporting.append(f"Std 20 s (cũ→mới): {flist(subs['centered_std'])}°; Mann–Kendall S={subs['mann_kendall_S']:+d}.")
        supporting.append(
            f"Feature gốc: roll_rms_ratio_180 {f(ft['roll_rms_ratio_180'], 3)}, roll_rms_slope_180 "
            f"{f(ft['roll_rms_slope_180'], 4)}°/phút, roll_rms_trend_r2_180 {f(ft['roll_rms_trend_r2_180'], 3)}; "
            f"std quanh trung bình: tỷ lệ {f(blocks['centered_std_ratio'], 3)}, slope {f(blocks['centered_std_slope_deg_per_min'], 4)}°/phút, "
            f"R² {f(blocks['centered_std_trend_r2'], 3)}.")
        if rules["growth_monotonic_60s"]:
            supporting.append(f"Std ba block 60 s tăng đơn điệu {flist(s)}°.")
        if rules["growth_latest_subblock_is_record"]:
            supporting.append(
                f"Std 20 s mới nhất ({f(subs['centered_std'][-1])}°) là cực đại của toàn bộ lịch sử quan sát "
                f"(cửa sổ + bối cảnh); không có dữ liệu sau endpoint để biết nó kéo dài hay chỉ là đỉnh nhóm sóng.")
        if m["growth_onset"]["time_s"] is not None and growth == "OBSERVED_CONSISTENT":
            supporting.append(
                f"Khởi phát ước lượng tại khoảng {f(m['growth_onset']['time_s'], 0)} s (sub-block {m['growth_onset']['sub_block_index'] + 1}/9); "
                "mọi sub-block sau đó đều cao hơn mọi sub-block trước đó và bối cảnh.")
        if ctx["max_valid_sub_block_std"] is not None:
            (supporting if rules["growth_exceeds_history"] else contradictory).append(
                f"Std block 60 s cuối {f(s[2])}° {'lớn hơn' if rules['growth_exceeds_history'] else 'không vượt'} "
                f"std 20 s lớn nhất trong bối cảnh trước cửa sổ ({f(ctx['max_valid_sub_block_std'])}°).")
        if p_mk >= rules["alpha_family"]:
            contradictory.append(
                f"Mann–Kendall p={f(p_mk, 4)} không vượt hiệu chỉnh đa kiểm định (α={FAMILY_ALPHA}/29={f(rules['alpha_family'], 4)}); "
                f"với 29 kiểm định ở α=0.05, kỳ vọng khoảng {f(29 * FAMILY_ALPHA, 2)} kết quả dương tính giả.")
        if not rules["growth_monotonic_60s"]:
            contradictory.append(f"Std ba block 60 s không tăng đơn điệu ({flist(s)}°).")
        ac1 = m["half_cycle_amplitude"]["lag1_autocorrelation"]
        if math.isfinite(ac1) and ac1 >= 0.5:
            contradictory.append(
                f"Biên độ các nửa chu kỳ liên tiếp tương quan mạnh (lag-1 = {f(ac1, 2)}), có thể do nhóm sóng hoặc do chính "
                "xu hướng; các sub-block không độc lập nên p-value của Mann–Kendall có xu hướng lạc quan.")
        pe, pl = pitch["early60_centered_std"], pitch["late60_centered_std"]
        if pl > pe:
            contradictory.append(
                f"Pitch tăng đồng thời (std 60 s sớm {f(pe)}° → muộn {f(pl)}°), gợi ý thay đổi kích thích bên ngoài "
                "(sóng/pha thí nghiệm) chứ không riêng cơ chế Roll; tín hiệu không đủ để xác định nguyên nhân.")
        if m["boundary_check"]["segment_seconds_after_endpoint"] < 5.0:
            contradictory.append(
                f"Cửa sổ kết thúc sát cuối run/segment (segment chỉ còn {f(m['boundary_check']['segment_seconds_after_endpoint'], 1)} s "
                "sau endpoint), nên không thể kiểm tra tăng biên độ có duy trì hay là pha cuối thí nghiệm.")
        questions.append(
            "Sự tăng biên độ này có trùng với một pha thí nghiệm/khởi phát sóng hoặc sự kiện vận hành được ghi nhận không? "
            "Nhóm có chấp nhận tiêu chí tăng biên độ dựa trên kiểm định xu hướng và vượt lịch sử không?")
    if offset != "NOT_OBSERVED" and roll["offset_to_oscillation_ratio"] > 1.0 and blocks["centered_std_ratio"] > 1.5 * blocks["rms_ratio"]:
        contradictory.append(
            f"Feature roll_rms_ratio_180 = {f(blocks['rms_ratio'], 3)} che mất tăng biên độ vì RMS bị offset chi phối "
            f"(|mean|/std = {f(roll['offset_to_oscillation_ratio'], 1)}); tỷ lệ std quanh trung bình là {f(blocks['centered_std_ratio'], 2)}.")
    # ---- chu kỳ và chất lượng
    if per["status"] != "ZC_AND_SPECTRUM_AGREE":
        uncertainty.append(
            f"Ước lượng chu kỳ không ổn định (CV {f(per['period_cv'], 2)}; đỉnh phổ {f(per['spectral_peak_period_s'], 1)} s, "
            f"độ phân giải phổ {f(per['spectral_resolution_hz'], 4)} Hz), nên không dùng chu kỳ làm bằng chứng phân lớp.")
    if roll["quantization_step_deg"]:
        uncertainty.append(
            f"Roll lượng tử hóa {f(roll['quantization_step_deg'], 2)}°; chỉ {roll['unique_values']} giá trị khác nhau trong cửa sổ, "
            f"std {f(roll['std_population'])}° ≈ {f(roll['std_population'] / roll['quantization_step_deg'], 1)} bước lượng tử, "
            "nên zero-crossing và chu kỳ bị nhiễu lượng tử chi phối.")
    if ctx["samples"] <= 1:
        uncertainty.append("Cửa sổ bắt đầu ngay đầu segment: không có lịch sử trước cửa sổ, thời lượng quan sát chỉ 180 s.")
    elif ctx["coverage_fraction"] < MIN_FRACTION:
        uncertainty.append(f"Bối cảnh trước cửa sổ chỉ phủ {f(100 * ctx['coverage_fraction'], 0)}% của 180 s.")
    uncertainty.append(
        "HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập "
        "cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.")
    uncertainty.append(DATASET_NOTES[m["dataset_source"]])
    uncertainty.append(f"Quy tắc {RULE_VERSION} do AI đề xuất, chưa được nhóm phê duyệt.")
    if not supporting:
        supporting.append("Không có bằng chứng ủng hộ phenotype nào theo quy tắc quan sát; các chỉ số mô tả được liệt kê ở trên.")
    contradictory = [c for c in contradictory if c]
    if not contradictory:
        contradictory.append("Không ghi nhận mâu thuẫn nội tại; giới hạn chính nằm ở phần độ không chắc chắn.")
    if rules["suggested_label"] == "UNLABELED":
        questions.append(
            "Không có phenotype nổi bật theo quy tắc. Nhóm có operating envelope NORMAL độc lập cho nguồn này không? "
            "Nếu không, cửa sổ phải giữ UNLABELED.")
    questions.append("HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?")
    if len(rules["consistent"]) + len(rules["weak"]) > 1:
        questions.append("Nhiều phenotype cùng xuất hiện: nhóm muốn giữ đồng thời các cờ hay chọn lớp chính theo quy ước nào?")
    return {"observations": observations, "supporting": supporting, "contradictory": contradictory,
            "uncertainty": uncertainty, "questions": questions}


def csv_row(m: dict, rules: dict, text: dict) -> dict:
    roll, blocks, subs, ctx, per, ft = (m["roll"], m["blocks_60s"], m["sub_blocks_20s"], m["context"],
                                        m["period"], m["feature_table"])
    supporting_values = {
        "roll_mean_180": _round(roll["mean"]), "roll_median_180": _round(roll["median"]),
        "roll_std_180_population": _round(roll["std_population"]), "roll_rms_180": _round(roll["rms"]),
        "roll_centered_rms_180": _round(roll["centered_rms"]), "roll_peak_to_peak_180": _round(roll["peak_to_peak"]),
        "roll_dominant_sign_ratio_180": _round(roll["dominant_sign_ratio"]),
        "offset_to_oscillation_ratio": _round(roll["offset_to_oscillation_ratio"]),
        "roll_segment_mean_std_180": _round(blocks["mean_std"], 5), "roll_mean_shift_180": _round(blocks["mean_shift"], 5),
        "roll_rms_early_60": _round(blocks["rms"][0]), "roll_rms_late_60": _round(blocks["rms"][2]),
        "roll_rms_ratio_180": _round(blocks["rms_ratio"]), "roll_rms_slope_180": _round(blocks["rms_slope_deg_per_min"], 5),
        "roll_rms_trend_r2_180": _round(blocks["rms_trend_r2"]),
        "centered_std_60_blocks": _round(blocks["centered_std"]), "centered_std_ratio_180": _round(blocks["centered_std_ratio"]),
        "mann_kendall_p_20s_std": _round(subs["mann_kendall_p_one_sided"], 5),
        "roll_std_60": _round(ft["roll_std_60"]), "pitch_std_60": _round(ft["pitch_std_60"]),
        "roll_period_est_180": _round(per["median_period_s"]), "roll_period_cv_180": _round(per["period_cv"]),
        "spectral_peak_period_s": _round(per["spectral_peak_period_s"]), "period_status": per["status"],
        "late60_std_percentile_rank_in_dataset": _round(m["dataset_relative"]["late60_centered_std_percentile_rank_in_dataset"]),
        "feature_parity_max_abs_diff": m["feature_parity"]["max_abs_difference"],
    }
    temporal = (f"Std 20 s (cũ→mới) {flist(subs['centered_std'])}°; mean 20 s dấu `{subs['mean_sign_pattern']}`; "
                f"block 60 s mean {flist(blocks['mean'])}°, std {flist(blocks['centered_std'])}°; "
                f"bối cảnh trước cửa sổ {ctx['samples']} mẫu (coverage {f(100 * ctx['coverage_fraction'], 0)}%)"
                + (f", mean {f(ctx['mean'])}°, std {f(ctx['std_population'])}°" if ctx["samples"] > 1 else "")
                + f"; lịch sử segment đến endpoint {f(ctx['segment_history_seconds_to_endpoint'], 0)} s.")
    reference = (f"processed={m['processed_path']}::({f(m['window_start_seconds'], 1)},{f(m['window_end_seconds'], 1)}]s; "
                 f"feature_window_id={m['feature_window_id']}; plot={m['plot_path']}; "
                 f"metrics={(OUTPUT_DIR / METRICS_NAME).as_posix()}#{m['review_id']}; "
                 f"rule=ml/labeling/ai_assisted_review.py@{RULE_VERSION}")
    return {
        "review_id": m["review_id"], "dataset_source": m["dataset_source"], "session_id": m["session_id"],
        "segment_id": m["segment_id"], "window_start_seconds": m["window_start_seconds"],
        "window_end_seconds": m["window_end_seconds"], "suggested_label": rules["suggested_label"],
        "observed_phenotype_flags": json.dumps(rules["flags"], sort_keys=True),
        "evidence_summary": " ".join(text["observations"]),
        "supporting_feature_values": json.dumps(supporting_values, sort_keys=True),
        "temporal_evidence": temporal, "contradictory_evidence": " ".join(text["contradictory"]),
        "uncertainty_reason": " ".join(text["uncertainty"]), "evidence_reference": reference,
        "annotation_method": ANNOTATION_METHOD, "requires_human_review": True, "rule_version": RULE_VERSION,
    }


# --------------------------------------------------------------------------- an toàn ghi file


def protected_checksums(repo_root: Path) -> dict:
    paths = [repo_root / p for p in PROTECTED_PATHS]
    for pattern in PROTECTED_GLOBS:
        paths.extend(sorted(repo_root.glob(pattern)))
    return {p.relative_to(repo_root).as_posix(): (hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "ABSENT")
            for p in paths}


def _assert_output_path(repo_root: Path, path: Path) -> None:
    resolved = path.resolve()
    allowed = [(repo_root / OUTPUT_DIR).resolve(), (repo_root / REPORT_PATH).resolve()]
    if not (resolved == allowed[1] or allowed[0] in resolved.parents):
        raise PermissionError(f"Từ chối ghi ngoài vùng AI-assisted: {path}")
    protected = {(repo_root / p).resolve() for p in PROTECTED_PATHS}
    if resolved in protected:
        raise PermissionError(f"Từ chối ghi vào ledger/nhãn của con người: {path}")


def validate_outputs(rows: list[dict], metrics: list[dict], batch: pd.DataFrame) -> dict:
    ids = [r["review_id"] for r in rows]
    checks = {
        "record_count": len(rows),
        "ids_match_pilot_batch": sorted(ids) == sorted(batch.review_id.tolist()),
        "all_windows_inside_segment_without_gaps": all(m["boundary_check"]["passed"] for m in metrics),
        "all_feature_parity_passed": all(m["feature_parity"]["passed"] for m in metrics),
        "max_feature_abs_difference": max(m["feature_parity"]["max_abs_difference"] for m in metrics),
        "annotation_method_all_ai_suggested": all(r["annotation_method"] == ANNOTATION_METHOD for r in rows),
        "all_require_human_review": all(r["requires_human_review"] is True for r in rows),
        "no_normal_or_high_roll_suggestion": all(r["suggested_label"] not in ("NORMAL", "HIGH_ROLL") for r in rows),
        "suggestions_in_allowed_set": all(r["suggested_label"] in ALLOWED_SUGGESTIONS for r in rows),
        "no_verified_or_human_reviewed_status": all("VERIFIED" not in r["suggested_label"]
                                                    and "HUMAN_REVIEWED" not in r["suggested_label"] for r in rows),
        "every_row_has_evidence_reference": all(r["evidence_reference"].startswith("processed=ml/data/processed/") for r in rows),
    }
    failed = [k for k, v in checks.items() if v is False]
    if failed:
        raise AssertionError(f"Kiểm tra output thất bại: {failed}")
    return checks


def session_overlaps(batch: pd.DataFrame) -> list[dict]:
    overlaps = []
    for (ds, session, segment), group in batch.groupby(["dataset_source", "session_id", "segment_id"]):
        g = group.sort_values("window_start_seconds")
        starts, ends, ids = (g.window_start_seconds.astype(float).tolist(), g.window_end_seconds.astype(float).tolist(),
                             g.review_id.tolist())
        for i in range(len(g) - 1):
            ov = ends[i] - starts[i + 1]
            if ov > 0:
                overlaps.append({"dataset_source": ds, "session_id": session, "segment_id": segment,
                                 "first": ids[i], "second": ids[i + 1], "overlap_seconds": ov})
    return overlaps


# --------------------------------------------------------------------------- báo cáo Markdown


def _metric_table(m: dict) -> list[str]:
    roll, blocks, subs, ctx, per, pitch = (m["roll"], m["blocks_60s"], m["sub_blocks_20s"], m["context"],
                                           m["period"], m["pitch"])
    rows = [
        ("A. Dao động", "mean / median (°)", f"{f(roll['mean'])} / {f(roll['median'])}"),
        ("A. Dao động", "std quần thể = centered RMS (°)", f(roll["std_population"])),
        ("A. Dao động", "RMS gồm offset (°)", f(roll["rms"])),
        ("A. Dao động", "peak-to-peak; min..max (°)", f"{f(roll['peak_to_peak'])}; {f(roll['min'])}..{f(roll['max'])}"),
        ("B. Offset", "dominant sign ratio; |mean|/std", f"{f(roll['dominant_sign_ratio'])}; {f(roll['offset_to_oscillation_ratio'], 2)}"),
        ("B. Offset", "mean block 60 s (°); dấu mean 20 s", f"{flist(blocks['mean'])}; `{subs['mean_sign_pattern']}`"),
        ("B. Offset", "std mean block; mean shift (°)", f"{f(blocks['mean_std'], 4)}; {f(blocks['mean_shift'], 4)}"),
        ("C. Tăng biên độ", "RMS block 60 s (°); ratio", f"{flist(blocks['rms'])}; {f(blocks['rms_ratio'], 3)}"),
        ("C. Tăng biên độ", "RMS slope (°/phút); R²", f"{f(blocks['rms_slope_deg_per_min'], 4)}; {f(blocks['rms_trend_r2'], 3)}"),
        ("C. Tăng biên độ", "std quanh mean block 60 s (°); ratio", f"{flist(blocks['centered_std'])}; {f(blocks['centered_std_ratio'], 3)}"),
        ("C. Tăng biên độ", "std 20 s (°)", flist(subs["centered_std"])),
        ("C. Tăng biên độ", "Mann–Kendall S; p một phía", f"{subs['mann_kendall_S']:+d}; {f(subs['mann_kendall_p_one_sided'], 4)}"),
        ("D. Chu kỳ", "zero-crossings; chu kỳ median (s); CV", f"{per['zero_crossings']}; {f(per['median_period_s'], 3)}; {f(per['period_cv'], 3)}"),
        ("D. Chu kỳ", "đỉnh phổ (s); trạng thái", f"{f(per['spectral_peak_period_s'], 3)}; {per['status']}"),
        ("Bối cảnh", "mẫu; coverage; mean; std (°)",
         f"{ctx['samples']}; {f(100 * ctx['coverage_fraction'], 0)}%; {f(ctx['mean'])}; {f(ctx['std_population'])}"),
        ("Pitch", "std 180 s; std 60 s sớm→muộn (°)", f"{f(pitch['std_population'])}; {f(pitch['early60_centered_std'])}→{f(pitch['late60_centered_std'])}"),
        ("Đối chiếu", "sai lệch lớn nhất so với feature table", f"{m['feature_parity']['max_abs_difference']:.2e} ({m['feature_parity']['features_compared']} feature)"),
    ]
    out = ["| Nhóm | Chỉ số | Giá trị |", "|---|---|---|"]
    out.extend(f"| {a} | {b} | {c} |" for a, b, c in rows)
    return out


def _record_section(index: int, m: dict, rules: dict, text: dict) -> list[str]:
    b = m["boundary_check"]
    lines = [f"### {index}. `{m['review_id']}` — {m['dataset_source']} · `{m['session_id']}` · `{m['segment_id']}`", ""]
    lines.append(
        f"**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ ({f(m['window_start_seconds'], 1)}, {f(m['window_end_seconds'], 1)}] s, "
        f"{b['window_samples']}/{b['expected_samples']} mẫu 10 Hz, khoảng cách mẫu {f(b['min_dt_s'], 3)}–{f(b['max_dt_s'], 3)} s; "
        f"segment chạy từ {f(b['segment_first_time_s'], 1)} đến {f(b['segment_last_time_s'], 1)} s nên cửa sổ không vượt ranh giới "
        f"segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: "
        f"`{m['processed_path']}`; hình: `{m['plot_path']}`.")
    lines += ["", "**2. Các chỉ số quan trọng.**", "", *_metric_table(m), ""]
    lines += ["**3. Dấu hiệu chuyển động quan sát được.**", "", *[f"- {o}" for o in text["observations"]], ""]
    lines += ["**4. Bằng chứng hỗ trợ.**", "", *[f"- {o}" for o in text["supporting"]], ""]
    lines += ["**5. Bằng chứng mâu thuẫn.**", "", *[f"- {o}" for o in text["contradictory"]], ""]
    flags = rules["flags"]
    lines += [f"**6. Nhãn hoặc trạng thái đề xuất.** `{rules['suggested_label']}` — {LABEL_VI[rules['suggested_label']]}. "
              f"Cờ: HIGH_ROLL = {FLAG_VI[flags['HIGH_ROLL']]}; PERSISTENT_OFFSET = {FLAG_VI[flags['PERSISTENT_OFFSET']]}; "
              f"AMPLITUDE_GROWTH = {FLAG_VI[flags['AMPLITUDE_GROWTH']]}; NORMAL = {FLAG_VI[flags['NORMAL']]}. "
              "`requires_human_review = true`.", ""]
    lines += ["**7. Lý do chưa thể xác minh.**", "", *[f"- {o}" for o in text["uncertainty"]], ""]
    lines += ["**8. Câu hỏi cần người đánh giá xác nhận.**", "", *[f"- {o}" for o in text["questions"]], ""]
    return lines


def write_report(repo_root: Path, results: list[tuple[dict, dict, dict]], checks: dict, checksums_before: dict,
                 checksums_after: dict, overlaps: list[dict]) -> Path:
    by_id = {m["review_id"]: (m, r) for m, r, _ in results}
    labels = pd.Series([r["suggested_label"] for _, r, _ in results])
    datasets = pd.Series([m["dataset_source"] for m, _, _ in results])
    n = len(results)

    def g(review_id: str):
        return by_id[review_id][0]

    lines = [
        "# Phân tích AI-assisted cho pilot 29 record",
        "",
        "> **Cảnh báo bắt buộc.** Toàn bộ nội dung dưới đây là gợi ý do AI tạo (`annotation_method = AI_SUGGESTED`). "
        "Đây không phải quyết định human review, không phải nhãn ground truth và không phải đánh giá an toàn hàng hải. "
        "Mọi gợi ý vẫn **chưa được xác minh** cho đến khi người đánh giá thực sự xem xét. Không có dòng nào được ghi vào "
        "decision ledger, audit history hay bảng nhãn verified.",
        "",
        "## 1. Phạm vi và nguyên tắc",
        "",
        f"- Batch phân tích: `{BATCH_PATH.as_posix()}` ({n} record), đối chiếu từng khóa với `{FORMS_PATH.as_posix()}`.",
        f"- Output: `{(OUTPUT_DIR / CSV_NAME).as_posix()}` (bảng gợi ý) và `{(OUTPUT_DIR / METRICS_NAME).as_posix()}` "
        "(toàn bộ số đo để truy vết). Cả hai nằm trong `ml/data/labels/` nên bị `.gitignore` loại khỏi Git như các artifact nhãn khác.",
        f"- Mã tái lập: `ml/labeling/ai_assisted_review.py`, quy tắc `{RULE_VERSION}`; chạy `python -m ml.labeling.ai_assisted_review`.",
        "- Phenotype là mô tả hình thái tín hiệu đo được, không đồng nghĩa hazard vận hành. Không dùng ngưỡng mô phỏng, "
        "không tạo ngưỡng phân vị để ép đủ bốn lớp, không gán số confidence.",
        "- Cửa sổ review là `(t-180, t]` trong đúng session/segment; bối cảnh chỉ lấy tối đa 180 s trước cửa sổ, "
        "cùng segment, không dùng dữ liệu sau endpoint (giống hình review của pilot).",
        "",
        "## 2. Cách phân tích tín hiệu",
        "",
        "Với mỗi record, script đọc trực tiếp `timeseries.parquet` đã preprocessing, cắt đúng cửa sổ và tính lại:",
        "",
        "- **A. Dao động Roll:** mean, median, độ lệch chuẩn quần thể (mẫu số n), RMS (gồm cả offset), centered RMS "
        "(RMS sau khi trừ mean, bằng std quần thể), peak-to-peak, min/max.",
        "- **B. Offset bền vững:** mean có dấu, median, dominant sign ratio, mean của ba block 60 s và chín sub-block 20 s, "
        "mean shift, độ lệch chuẩn giữa các block mean, mean của bối cảnh trước cửa sổ và trung bình từ đầu segment đến endpoint.",
        "- **C. Tăng biên độ:** RMS sớm/muộn, RMS ratio, RMS slope, R² (đúng như feature), cộng thêm std quanh trung bình của "
        "ba block 60 s và chín sub-block 20 s, kiểm định xu hướng Mann–Kendall chính xác một phía trên chín giá trị std 20 s, "
        "so sánh với std 20 s trong bối cảnh trước cửa sổ, tương quan lag-1 giữa biên độ các nửa chu kỳ.",
        "- **D. Chu kỳ:** zero-crossing sau khi trừ mean (tái sử dụng `period_values` của feature pipeline), chu kỳ median, "
        "CV chu kỳ, đối chiếu với đỉnh phổ (periodogram cửa sổ Hann, độ phân giải 1/180 Hz). Chu kỳ chỉ được coi là ổn định "
        "khi đỉnh phổ nằm trong khoảng tứ phân vị của các chu kỳ zero-crossing.",
        "- **E. Chất lượng dữ liệu:** số mẫu, khoảng cách mẫu, ranh giới segment, coverage bối cảnh, lượng tử hóa, provenance "
        "(timestamp suy diễn, thiếu gyro, bộ lọc, model-scale).",
        "",
        "Toàn bộ 23 angle feature và 3 period feature được tính lại độc lập bằng numpy rồi so với `feature_values.parquet`.",
        "",
        "## 3. Quy tắc quan sát tường minh (`" + RULE_VERSION + "`, chưa được nhóm phê duyệt)",
        "",
        "| Phenotype | Mức | Tiêu chí (không có ngưỡng biên độ tuyệt đối) |",
        "|---|---|---|",
        "| HIGH_ROLL | luôn `NOT_ASSESSABLE_NO_VALIDATED_ENVELOPE` | Định nghĩa của dự án cần ngưỡng vận hành có căn cứ; hiện không có. Hạng phần trăm std chỉ để mô tả. |",
        "| NORMAL | luôn `NOT_ASSESSABLE_NO_VALIDATED_ENVELOPE` | Cần operating envelope NORMAL độc lập; biên độ nhỏ không đủ. |",
        "| PERSISTENT_OFFSET | `OBSERVED_CONSISTENT` | Mọi mẫu trong cửa sổ cùng dấu (tín hiệu không cắt mốc 0), 9/9 sub-block 20 s cùng dấu, và mọi mẫu bối cảnh có sẵn cùng dấu. |",
        "| PERSISTENT_OFFSET | `OBSERVED_WEAK` | 9/9 sub-block cùng dấu và mean bối cảnh cùng dấu, nhưng dao động vẫn cắt mốc 0. |",
        "| AMPLITUDE_GROWTH | `OBSERVED_CONSISTENT` | Mann–Kendall p < 0.05/29 (hiệu chỉnh Bonferroni cho cả batch), std ba block 60 s tăng đơn điệu, và std block cuối lớn hơn mọi std 20 s của bối cảnh. |",
        "| AMPLITUDE_GROWTH | `OBSERVED_WEAK` | Mann–Kendall p < 0.05 danh nghĩa, hoặc std ba block tăng đơn điệu và sub-block 20 s mới nhất là cực đại của toàn bộ lịch sử quan sát. |",
        "",
        "Nhãn gợi ý: đúng **một** phenotype `OBSERVED_CONSISTENT` và không có dấu hiệu yếu nào khác → gợi ý phenotype đó; "
        "có dấu hiệu yếu hoặc nhiều phenotype → `REVIEW_REQUIRED`; không có dấu hiệu → `UNLABELED` (không bao giờ là `NORMAL`). "
        "Mọi dòng đều `requires_human_review = true`. Mức ý nghĩa 0.05 là quy ước thống kê, không phải giới hạn an toàn.",
        "",
        "## 4. Kết quả kiểm tra",
        "",
        "| Kiểm tra | Kết quả |",
        "|---|---|",
        f"| Số record phân tích | {checks['record_count']} |",
        f"| Review ID khớp `pilot_29.csv` và form pilot | {'Đạt' if checks['ids_match_pilot_batch'] else 'Không đạt'} |",
        f"| Mọi cửa sổ nằm trong một segment, 1.800 mẫu, không gap > 1.5 chu kỳ | {'Đạt' if checks['all_windows_inside_segment_without_gaps'] else 'Không đạt'} |",
        f"| Đối chiếu 26 feature với feature table | {'Đạt' if checks['all_feature_parity_passed'] else 'Không đạt'}; sai lệch tuyệt đối lớn nhất {checks['max_feature_abs_difference']:.2e} |",
        f"| `annotation_method = AI_SUGGESTED`, `requires_human_review = true` | {'Đạt' if checks['annotation_method_all_ai_suggested'] and checks['all_require_human_review'] else 'Không đạt'} |",
        f"| Không gợi ý NORMAL/HIGH_ROLL, không có trạng thái VERIFIED/HUMAN_REVIEWED | {'Đạt' if checks['no_normal_or_high_roll_suggestion'] and checks['no_verified_or_human_reviewed_status'] else 'Không đạt'} |",
        f"| Mỗi dòng có evidence reference truy vết đến parquet/feature/plot/metrics | {'Đạt' if checks['every_row_has_evidence_reference'] else 'Không đạt'} |",
        f"| Ledger/audit/verified label không đổi (SHA-256 trước = sau) | {'Đạt' if checksums_before == checksums_after else 'KHÔNG ĐẠT'} |",
        "",
        "| Tệp được bảo vệ | SHA-256 trước và sau |",
        "|---|---|",
        *[f"| `{path}` | `{digest[:16]}…` |" if digest != "ABSENT" else f"| `{path}` | không tồn tại (không tạo mới) |"
          for path, digest in checksums_after.items()],
        "",
        "## 5. Tổng hợp pilot",
        "",
        f"Đã phân tích **{n} record thực tế** thuộc {datasets.nunique()} nguồn, "
        f"{len({(m['dataset_source'], m['session_id']) for m, _, _ in results})} session và "
        f"{len({(m['dataset_source'], m['session_id'], m['segment_id']) for m, _, _ in results})} segment.",
        "",
        "| Nguồn | Record | Session | Segment | " + " | ".join(ALLOWED_SUGGESTIONS) + " |",
        "|---|---:|---:|---:|" + "---:|" * len(ALLOWED_SUGGESTIONS),
    ]
    for ds in sorted(datasets.unique()):
        subset = [(m, r) for m, r, _ in results if m["dataset_source"] == ds]
        counts = pd.Series([r["suggested_label"] for _, r in subset]).value_counts()
        lines.append(f"| {ds} | {len(subset)} | {len({m['session_id'] for m, _ in subset})} | "
                     f"{len({(m['session_id'], m['segment_id']) for m, _ in subset})} | "
                     + " | ".join(str(int(counts.get(lbl, 0))) for lbl in ALLOWED_SUGGESTIONS) + " |")
    total = labels.value_counts()
    lines.append(f"| **Tổng** | **{n}** | | | " + " | ".join(f"**{int(total.get(lbl, 0))}**" for lbl in ALLOWED_SUGGESTIONS) + " |")
    lines += ["", "| Phenotype | OBSERVED_CONSISTENT | OBSERVED_WEAK | NOT_OBSERVED | NOT_ASSESSABLE |", "|---|---:|---:|---:|---:|"]
    for ph in (*PHENOTYPES, "NORMAL"):
        vals = pd.Series([r["flags"][ph] for _, r, _ in results]).value_counts()
        lines.append(f"| {ph} | {int(vals.get('OBSERVED_CONSISTENT', 0))} | {int(vals.get('OBSERVED_WEAK', 0))} | "
                     f"{int(vals.get('NOT_OBSERVED', 0))} | {int(vals.get('NOT_ASSESSABLE_NO_VALIDATED_ENVELOPE', 0))} |")
    combos = pd.Series([" + ".join(f"{k}:{'C' if v == 'OBSERVED_CONSISTENT' else 'W'}" for k, v in r["flags"].items()
                                   if k in PHENOTYPES and v.startswith("OBSERVED")) or "không có cờ"
                        for _, r, _ in results]).value_counts()
    insufficient = int(total.get("UNLABELED", 0))
    lines += ["", "**Mẫu hình phenotype chồng lấn** (C = nhất quán, W = yếu):", ""]
    lines += [f"- {combo}: {count} record" for combo, count in combos.items()]
    lines += [
        "",
        f"- Số record cần người đánh giá: **{n}/{n}** (mọi gợi ý AI đều cần xác nhận). Trong đó "
        f"{int(total.get('REVIEW_REQUIRED', 0))} record là `REVIEW_REQUIRED` vì bằng chứng yếu hoặc chồng lấn.",
        f"- Số record không có đủ bằng chứng cho bất kỳ phenotype nào: **{insufficient}** (`UNLABELED`). "
        "Không record nào đủ căn cứ cho `NORMAL` hoặc `HIGH_ROLL`.",
        "- Cửa sổ chồng lấn trong batch (cùng segment): "
        + ("; ".join(f"`{o['first']}`/`{o['second']}` chồng {f(o['overlap_seconds'], 0)} s" for o in overlaps) or "không có")
        + ". Các cửa sổ này không phải quan sát độc lập.",
        "",
        "**Độ mạnh bằng chứng và giới hạn.** Bằng chứng mạnh nhất là offset có dấu của Seafar và Southampton: tín hiệu không cắt mốc 0 "
        "trong toàn cửa sổ. Tuy vậy, cả bốn record Seafar thuộc một session tàu thật duy nhất và bốn record Southampton thuộc một run "
        "nên số đơn vị độc lập rất nhỏ. Dấu hiệu tăng biên độ duy nhất vượt hiệu chỉnh đa kiểm định nằm ở cửa sổ Southampton cuối run "
        "và đi kèm tăng Pitch. Ở Hohai, "
        f"{sum(g(i)['period']['status'] == 'ZC_AND_SPECTRUM_AGREE' for i in by_id if g(i)['dataset_source'] == 'hohai')}/"
        f"{sum(g(i)['dataset_source'] == 'hohai' for i in by_id)} record có chu kỳ zero-crossing khớp đỉnh phổ; "
        "tín hiệu chủ yếu là dao động tuần hoàn với chu kỳ zero-crossing khoảng "
        f"{f(min(g(i)['period']['median_period_s'] for i in by_id if g(i)['dataset_source'] == 'hohai'), 2)}–"
        f"{f(max(g(i)['period']['median_period_s'] for i in by_id if g(i)['dataset_source'] == 'hohai'), 2)} s; "
        "các offset nhỏ cùng dấu là có thật về thống kê nhưng chưa thể nói có ý nghĩa vật lý.",
        "",
        "## 6. Phân tích chi tiết từng record",
        "",
    ]
    order = sorted(results, key=lambda item: (item[0]["dataset_source"], item[0]["session_id"], item[0]["window_end_seconds"]))
    current = None
    for idx, (m, r, text) in enumerate(order, start=1):
        if m["dataset_source"] != current:
            current = m["dataset_source"]
            lines += [f"## 6.{sorted(datasets.unique()).index(current) + 1}. Nguồn `{current}`", "", DATASET_NOTES[current], ""]
        lines += _record_section(idx, m, r, text)
    lines += oral_defense_section(by_id)
    path = repo_root / REPORT_PATH
    _assert_output_path(repo_root, path)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def oral_defense_section(by_id: dict) -> list[str]:
    def m(review_id: str) -> dict:
        return by_id[review_id][0]

    sh = m("PILOT-c2643af463e2")
    sh3 = m("PILOT-db0b97396fc9")
    dt7 = m("PILOT-fb456420a73f")
    bt7 = m("PILOT-279f4ef04864")
    bt9 = m("PILOT-88aebf3cd137")
    dt9 = m("PILOT-9299db975778")
    d3c = m("PILOT-e0713611700d")
    sf4 = m("PILOT-9115297d34b5")
    sf1 = m("PILOT-5e1196364be9")
    return [
        "## 7. Giải thích kết quả phục vụ vấn đáp cá nhân",
        "",
        "### 7.1. Tín hiệu được phân tích như thế nào?",
        "",
        "Em không chỉ nhìn biểu đồ hay đọc lại feature có sẵn. Script đọc chuỗi Roll/Pitch 10 Hz đã preprocessing của từng record, "
        "cắt đúng cửa sổ `(t-180, t]`, chia thành ba block 60 s và chín sub-block 20 s, rồi tính lại thống kê. Kết quả được so với "
        "feature table: 26 feature của cả 29 record khớp đến sai số làm tròn float32, nên các con số trong báo cáo là cùng một "
        "nguồn dữ liệu với pipeline. Điểm quan trọng là em tách **mức trung bình** (offset) khỏi **dao động quanh trung bình** (std). "
        "RMS gộp cả hai nên có thể gây hiểu nhầm.",
        "",
        "### 7.2. Các phenotype khác nhau thế nào?",
        "",
        "- **PERSISTENT_OFFSET** nói về *vị trí trung bình*: Roll lệch về một phía và giữ dấu theo thời gian. Ví dụ "
        f"`{sf1['review_id']}` (Seafar) có mean {f(sf1['roll']['mean'])}°, std chỉ {f(sf1['roll']['std_population'])}°, "
        "100% mẫu dương.",
        "- **AMPLITUDE_GROWTH** nói về *độ lớn dao động thay đổi theo thời gian*. Ví dụ `" + sh["review_id"] + "` (Southampton): "
        f"std 20 s đi từ {f(sh['sub_blocks_20s']['centered_std'][0])}° lên {f(sh['sub_blocks_20s']['centered_std'][-1])}°, "
        f"Mann–Kendall p={f(sh['sub_blocks_20s']['mann_kendall_p_one_sided'], 4)}.",
        "- **HIGH_ROLL** nói về *dao động lớn so với giới hạn vận hành*. Vì chưa có giới hạn được xác thực, em chỉ mô tả "
        "\"tương đối mạnh trong nguồn\" bằng hạng phần trăm, ví dụ `" + dt7["review_id"] + "` có std 60 s cuối ở hạng "
        f"{f(100 * dt7['dataset_relative']['late60_centered_std_percentile_rank_in_dataset'], 0)} trong Hohai, nhưng không gọi đó là HIGH_ROLL.",
        "- **NORMAL** cần envelope vận hành bình thường độc lập. `" + d3c["review_id"] + "` có biên độ nhỏ nhất nhóm Hohai "
        f"(std 60 s cuối ở hạng {f(100 * d3c['dataset_relative']['late60_centered_std_percentile_rank_in_dataset'], 0)}) "
        "nhưng vẫn để `UNLABELED`, vì biên độ nhỏ không chứng minh trạng thái bình thường.",
        "",
        "### 7.3. Vì sao offset có thể che mất tăng biên độ?",
        "",
        f"Ở `{sh['review_id']}`, feature `roll_rms_ratio_180` chỉ bằng {f(sh['blocks_60s']['rms_ratio'], 3)} vì RMS bị offset "
        f"{f(sh['roll']['mean'])}° chi phối, trong khi tỷ lệ std quanh trung bình muộn/sớm là {f(sh['blocks_60s']['centered_std_ratio'], 2)}. "
        "Nếu chỉ dùng RMS ratio làm proxy, mẫu này sẽ bị bỏ sót. Đây là lý do em báo cáo cả RMS và centered RMS, và cũng là "
        "câu hỏi nên đưa cho nhóm khi chốt định nghĩa feature nhóm D.",
        "",
        "### 7.4. Vì sao một số mẫu vẫn mơ hồ?",
        "",
        f"- **Tăng ngắn hạn so với tăng bền vững.** `{dt7['review_id']}` có RMS ba block tăng (ratio {f(dt7['blocks_60s']['rms_ratio'], 2)}), "
        f"nhưng std 20 s dao động lên xuống {flist(dt7['sub_blocks_20s']['centered_std'], 2)} và Mann–Kendall p="
        f"{f(dt7['sub_blocks_20s']['mann_kendall_p_one_sided'], 2)}; bối cảnh trước đó đã có sub-block {f(dt7['context']['max_valid_sub_block_std'], 2)}°. "
        "Đây giống nhóm sóng (wave group) hơn là tăng bền vững, nhưng không có dữ liệu sau endpoint để chắc chắn.",
        f"- **Đa kiểm định.** `{bt7['review_id']}` và `{sh3['review_id']}` có p={f(bt7['sub_blocks_20s']['mann_kendall_p_one_sided'], 3)} "
        f"và p={f(sh3['sub_blocks_20s']['mann_kendall_p_one_sided'], 3)}: dưới 0.05 nhưng với 29 kiểm định thì kỳ vọng khoảng 1.45 "
        "kết quả dương tính giả, nên em chỉ xếp vào mức yếu.",
        f"- **Offset nhỏ.** `{bt9['review_id']}` có mean {f(bt9['roll']['mean'])}° và 9/9 sub-block dương, nhưng dao động vẫn cắt mốc 0 "
        f"(sign ratio {f(bt9['roll']['dominant_sign_ratio'])}). Có thật về thống kê nhưng chưa biết có lớn hơn sai số zero của cảm biến hay không.",
        f"- **Trôi trung bình.** `{dt9['review_id']}` có mean 20 s đổi dấu `{dt9['sub_blocks_20s']['mean_sign_pattern']}`; đây là trôi qua "
        "mốc 0 chứ không phải lệch ổn định, nên không gắn PERSISTENT_OFFSET.",
        f"- **Chất lượng tín hiệu.** `{sf4['review_id']}` (Seafar) chỉ có {sf4['roll']['unique_values']} giá trị Roll khác nhau do lượng tử "
        f"0.01°, std {f(sf4['roll']['std_population'])}°, nên chu kỳ zero-crossing {f(sf4['period']['median_period_s'], 1)} s "
        "chủ yếu phản ánh nhiễu lượng tử.",
        "- **Mốc 0 chưa xác nhận.** Ngay cả offset mạnh của Seafar/Southampton vẫn có thể là sai lệch lắp đặt thay vì nghiêng thật.",
        "",
        "### 7.5. Vì sao AI-assisted annotation không phải ground truth?",
        "",
        "- Quy tắc do AI đề xuất, chưa được nhóm phê duyệt; nó chỉ làm minh bạch cách đọc tín hiệu.",
        "- AI nhìn cùng tín hiệu và cùng loại thống kê mà mô hình sau này sẽ học. Nếu dùng nhãn AI để train rồi test trên feature "
        "tương tự thì chỉ đo được khả năng tái tạo quy tắc (circular labeling).",
        "- Không có nguồn độc lập như nhật ký vận hành, ghi chú thí nghiệm hoặc envelope được xác thực. Không được tính "
        "\"inter-reviewer agreement\" bằng cách chạy AI nhiều lần, vì các lần chạy đó không độc lập như hai người đánh giá.",
        "",
        "### 7.6. Cần thêm bằng chứng gì để huấn luyện đáng tin cậy?",
        "",
        "1. Ít nhất hai người đánh giá độc lập review 29 record trên giao diện Streamlit *trước khi* xem bảng gợi ý AI (tránh anchoring), "
        "sau đó so sánh với bảng AI để tìm bất đồng.",
        "2. Xác nhận mốc 0/mounting của cảm biến Roll cho từng nguồn và sai số zero.",
        "3. Envelope NORMAL và giới hạn HIGH_ROLL có tài liệu độc lập, đúng quy mô (tàu thật khác mô hình).",
        "4. Ghi chú pha thí nghiệm (thời điểm sóng tới, kết thúc run) cho Southampton/Hohai, nhật ký vận hành cho Seafar.",
        "5. Thêm session độc lập; chia train/test theo session/run, không theo cửa sổ chồng lấn.",
        "",
        "### 7.7. Có thể và không thể khẳng định gì?",
        "",
        "| Có thể khẳng định | Không thể khẳng định |",
        "|---|---|",
        "| Các số đo được tính lại trực tiếp từ dữ liệu và khớp feature table | Bất kỳ record nào là nguy hiểm hoặc an toàn |",
        "| Seafar/Southampton có Roll lệch một phía trong toàn cửa sổ | Độ lệch đó là nghiêng thật của tàu/mô hình |",
        f"| `{sh['review_id']}` có biên độ Roll và Pitch tăng rõ trong 80 s cuối | Đó là cơ chế mất ổn định Roll thay vì thay đổi kích thích/pha thí nghiệm |",
        "| Hohai chủ yếu là dao động tuần hoàn đều, offset rất nhỏ | Mẫu Hohai nào là NORMAL hay HIGH_ROLL |",
        "| Bảng gợi ý giúp người đánh giá tập trung vào chỗ mơ hồ | Bảng gợi ý là nhãn huấn luyện hay ground truth |",
        "",
    ]


# --------------------------------------------------------------------------- điểm vào


def run(repo_root: Path) -> dict:
    repo_root = repo_root.resolve()
    before = protected_checksums(repo_root)
    batch = load_batch(repo_root)
    cache: dict = {}
    results, rows, metrics_all = [], [], []
    for record in batch.itertuples(index=False):
        metrics = analyze_record(repo_root, record, cache)
        rules = evaluate_rules(metrics, len(batch))
        text = describe_record(metrics, rules)
        metrics["rule_evaluation"] = rules
        results.append((metrics, rules, text))
        rows.append(csv_row(metrics, rules, text))
        metrics_all.append(metrics)
    checks = validate_outputs(rows, metrics_all, batch)
    overlaps = session_overlaps(batch)

    out_dir = repo_root / OUTPUT_DIR
    _assert_output_path(repo_root, out_dir / CSV_NAME)
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=CSV_COLUMNS).to_csv(out_dir / CSV_NAME, index=False)
    payload = {"rule_version": RULE_VERSION, "annotation_method": ANNOTATION_METHOD,
               "disclaimer": "AI-suggested observations only; not human review, not ground truth, not a safety assessment.",
               "batch": BATCH_PATH.as_posix(), "validation": checks, "window_overlaps": overlaps,
               "records": {m["review_id"]: m for m in metrics_all}}
    _assert_output_path(repo_root, out_dir / METRICS_NAME)
    (out_dir / METRICS_NAME).write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    after_data = protected_checksums(repo_root)
    if after_data != before:
        raise RuntimeError("Tệp ledger/nhãn được bảo vệ bị thay đổi trong lúc chạy; dừng lại.")
    report = write_report(repo_root, results, checks, before, after_data, overlaps)
    if protected_checksums(repo_root) != before:
        raise RuntimeError("Tệp ledger/nhãn được bảo vệ bị thay đổi; dừng lại.")
    return {"csv": out_dir / CSV_NAME, "metrics": out_dir / METRICS_NAME, "report": report, "checks": checks,
            "labels": pd.Series([r["suggested_label"] for r in rows]).value_counts().to_dict()}


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-assisted observation analysis cho pilot_29 (không ghi human review).")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    result = run(args.repo_root)
    print(json.dumps({k: (str(v) if isinstance(v, Path) else v) for k, v in result.items()}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
