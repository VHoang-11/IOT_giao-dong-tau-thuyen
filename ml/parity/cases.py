"""Định nghĩa case golden: tín hiệu kiểm thử SỐ HỌC tất định (không phải dữ liệu huấn luyện hàng hải)
và quy tắc chọn đoạn dữ liệu thật đã xử lý.

Mọi giá trị đầu vào được làm tròn về float32 trước khi tính expected, để C đọc lại đúng cùng một chuỗi số.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

FS = 10.0
DEFAULT_DURATION_S = 210.0  # đủ 180 s + 3 endpoint; endpoint cuối 210 s có block (30,90], (90,150], (150,210]


@dataclass(frozen=True)
class SyntheticCase:
    case_id: str
    title: str
    detects: tuple[str, ...]
    duration_s: float = DEFAULT_DURATION_S
    params: dict = field(default_factory=dict)


def _sine(t, amplitude, freq, phase=0.3):
    return amplitude * np.sin(2 * np.pi * freq * t + phase)


SYNTHETIC_CASES = (
    SyntheticCase("SYN01_const_zero", "Roll/Pitch hằng 0", ("division_by_zero", "undefined_status", "sign_zero")),
    SyntheticCase("SYN02_const_roll_pos", "Roll hằng +3°", ("offset_sign", "zero_variance", "r2_undefined")),
    SyntheticCase("SYN03_const_roll_neg_pitch_pos", "Roll hằng -2.5°, Pitch hằng +1.25°", ("sign_handling", "mean_abs")),
    SyntheticCase("SYN04_sine_roll", "Roll sin 5°, 0.1 Hz, số chu kỳ nguyên", ("variance_convention", "diff_rms", "sign_ratio_half")),
    SyntheticCase("SYN05_sine_pitch", "Pitch sin 2°, 0.2 Hz", ("pitch_channel", "feature_order")),
    SyntheticCase("SYN06_mixed_order_detector", "Roll/Pitch hỗn hợp: 23 giá trị đôi một khác nhau", ("feature_order", "units", "channel_swap")),
    SyntheticCase("SYN07_growing_amplitude", "Biên độ Roll tăng tuyến tính", ("trend_slope", "ratio")),
    SyntheticCase("SYN08_decreasing_amplitude", "Biên độ Roll giảm tuyến tính", ("negative_slope", "ratio_below_one")),
    SyntheticCase("SYN09_block_step_linear", "Biên độ theo block 1, 2, 3 (R² = 1)", ("block_boundaries", "trend_units", "r2_one")),
    SyntheticCase("SYN10_block_step_nonlinear", "Biên độ theo block 1, 3, 2 (R² = 0.25)", ("r2_formula", "block_order")),
    SyntheticCase("SYN11_offset_constant_amplitude", "Offset 2° + sin 1° biên độ không đổi", ("cancellation", "r2_ill_conditioned")),
    SyntheticCase("SYN12_spike_window_boundaries", "Gai +10° tại t=150 s, -8° tại t=90 s", ("half_open_window", "block_boundary", "extrema")),
    SyntheticCase("SYN13_ramp_quantiles", "Ramp 0.5 + k/256 (chính xác float32)", ("quantile_interpolation", "median", "iqr", "mean_shift")),
    SyntheticCase("SYN14_square_wave_quantile_discontinuity", "Sóng vuông ±1 (10 mẫu)", ("quantile_interpolation_at_tie", "diff_pairs")),
    SyntheticCase("SYN15_low_amplitude", "Biến thiên rất nhỏ quanh 0 (1e-4°)", ("relative_tolerance", "near_zero")),
    SyntheticCase("SYN16_sign_with_exact_zeros", "Mẫu +1/-1/0 chính xác", ("exact_zero_sign_semantics",)),
    SyntheticCase("SYN17_zero_early_block", "Block đầu bằng 0, sau đó sin", ("ratio_division_by_zero", "slope_valid")),
    SyntheticCase("SYN18_epsilon_below", "Block đầu biên độ 1e-10° (< epsilon)", ("epsilon_rule",)),
    SyntheticCase("SYN19_epsilon_above", "Block đầu biên độ 1e-7° (> epsilon)", ("epsilon_rule", "large_ratio")),
    SyntheticCase("SYN20_insufficient_history", "Chỉ 150 s lịch sử", ("warmup", "insufficient_window"), duration_s=150.0),
    SyntheticCase("SYN21_isolated_nan", "20 NaN rời rạc trong 60 s cuối", ("missing_values", "diff_pair_coverage")),
    SyntheticCase("SYN22_nan_excess", "40 NaN liên tiếp (> 5% của 60 s)", ("signal_coverage", "block_coverage")),
    SyntheticCase("SYN23_timestamp_gap", "Bỏ 4 timestamp t=195.2..195.5 s (gap 0.5 s nằm trong cửa sổ cuối)", ("timestamp_gap", "endpoint_anchor")),
    SyntheticCase("SYN24_single_dropped_sample", "Bỏ 1 timestamp tại t=200 s", ("timestamp_gap", "nan_vs_dropped_semantics")),
    SyntheticCase("SYN25_large_amplitude_units", "Roll 20°, Pitch 8° (phát hiện nhầm rad/deg)", ("units",)),
    SyntheticCase("SYN26_infinite_values", "+Inf và -Inf trong Roll", ("non_finite_handling",)),
    SyntheticCase("SYN27_block_coverage_rule", "40 NaN chỉ trong block đầu (issue C01)", ("block_validity_rule",)),
    SyntheticCase("SYN28_negative_offset_sine", "-1.5° + sin 0.5° (luôn âm)", ("sign_handling", "negative_mean")),
    SyntheticCase("SYN29_block_step_symmetric", "Biên độ theo block 1, 2, 1 (slope 0, R² = 0 VALID)", ("r2_zero_vs_undefined", "slope_zero")),
    SyntheticCase("SYN30_permuted_blocks", "3 block 60 s là hoán vị của cùng 600 giá trị (SST đúng = 0)",
                  ("r2_threshold_float32", "accumulation_order", "ratio_exactly_one")),
    SyntheticCase("SYN31_large_offset_small_variation", "Roll 10° + sin 0.01°, Pitch -5° + sin 0.005° (nghiêng tĩnh)",
                  ("variance_cancellation", "one_pass_variance", "near_zero_relative")),
)


def synthetic_signal(case: SyntheticCase) -> pd.DataFrame:
    """Trả DataFrame sample_index/time_seconds/roll_deg/pitch_deg (float32 làm tròn, NaN/Inf/gap nếu có)."""
    n = int(round(case.duration_s * FS)) + 1
    k = np.arange(n)
    t = k / FS
    roll = np.zeros(n)
    pitch = np.zeros(n)
    cid = case.case_id
    if cid == "SYN02_const_roll_pos":
        roll[:] = 3.0
    elif cid == "SYN03_const_roll_neg_pitch_pos":
        roll[:], pitch[:] = -2.5, 1.25
    elif cid == "SYN04_sine_roll":
        roll = _sine(t, 5.0, 0.1)
    elif cid == "SYN05_sine_pitch":
        pitch = _sine(t, 2.0, 0.2, 0.7)
    elif cid == "SYN06_mixed_order_detector":
        roll = 1.2 + 3.0 * np.sin(2 * np.pi * 0.08 * t) + 0.7 * np.sin(2 * np.pi * 0.23 * t + 1.0) + 0.004 * t * np.sin(2 * np.pi * 0.31 * t)
        pitch = -0.4 + 1.5 * np.cos(2 * np.pi * 0.11 * t) + 0.2 * np.sin(2 * np.pi * 0.37 * t)
    elif cid == "SYN07_growing_amplitude":
        roll, pitch = (1.0 + 0.02 * t) * np.sin(2 * np.pi * 0.1 * t + 0.3), np.full(n, 0.5)
    elif cid == "SYN08_decreasing_amplitude":
        roll, pitch = (6.0 - 0.02 * t) * np.sin(2 * np.pi * 0.1 * t + 0.3), np.full(n, -0.5)
    elif cid in ("SYN09_block_step_linear", "SYN10_block_step_nonlinear", "SYN29_block_step_symmetric"):
        amps = {"SYN09": (1.0, 2.0, 3.0), "SYN10": (1.0, 3.0, 2.0), "SYN29": (1.0, 2.0, 1.0)}[cid[:5]]
        amplitude = np.where(k <= 900, amps[0], np.where(k <= 1500, amps[1], amps[2]))
        roll = amplitude * np.sin(2 * np.pi * 0.1 * t + 0.3)
    elif cid == "SYN11_offset_constant_amplitude":
        roll = 2.0 + _sine(t, 1.0, 0.1)
    elif cid == "SYN12_spike_window_boundaries":
        roll = _sine(t, 0.5, 0.1)
        roll[1500], roll[900] = 10.0, -8.0
    elif cid == "SYN13_ramp_quantiles":
        roll, pitch = 0.5 + k / 256.0, 1.0 - k / 512.0
    elif cid == "SYN14_square_wave_quantile_discontinuity":
        roll = np.where((k // 10) % 2 == 0, 1.0, -1.0)
        pitch = np.where((k // 25) % 2 == 0, 0.5, -0.25)
    elif cid == "SYN15_low_amplitude":
        roll, pitch = 5e-5 + _sine(t, 1e-4, 0.1), _sine(t, 2e-5, 0.2)
    elif cid == "SYN16_sign_with_exact_zeros":
        pattern = np.array([1, 1, 1, 1, 1, 1, -1, -1, -1, 0], dtype=float)
        roll = pattern[k % 10]
    elif cid == "SYN17_zero_early_block":
        roll = np.where(k <= 900, 0.0, _sine(t, 1.0, 0.1))
    elif cid in ("SYN18_epsilon_below", "SYN19_epsilon_above"):
        early = 1e-10 if cid.startswith("SYN18") else 1e-7
        roll = np.where(k <= 900, _sine(t, early, 0.1), _sine(t, 1.0, 0.1))
    elif cid in ("SYN20_insufficient_history", "SYN21_isolated_nan", "SYN22_nan_excess", "SYN23_timestamp_gap",
                 "SYN24_single_dropped_sample", "SYN26_infinite_values", "SYN27_block_coverage_rule"):
        roll, pitch = _sine(t, 2.0, 0.1), _sine(t, 1.0, 0.2, 0.9)
    elif cid == "SYN25_large_amplitude_units":
        roll, pitch = _sine(t, 20.0, 0.1), 3.0 + _sine(t, 8.0, 0.125, 1.1)
    elif cid == "SYN30_permuted_blocks":
        i = np.arange(600)
        base = 0.3 + 2.0 * np.sin(2 * np.pi * 3.7 * i / 600 + 0.2) + 0.45 * np.cos(2 * np.pi * 11.3 * i / 600)
        pos = (k - 301) % 600
        block = np.clip((k - 301) // 600, 0, 2)
        order = np.where(block == 1, 599 - pos, np.where(block == 2, (pos * 7) % 600, pos))
        roll = base[order]
        pitch = 0.2 * np.sin(2 * np.pi * 0.2 * t)
    elif cid == "SYN31_large_offset_small_variation":
        roll, pitch = 10.0 + _sine(t, 0.01, 0.1), -5.0 + _sine(t, 0.005, 0.2, 0.9)
    elif cid == "SYN28_negative_offset_sine":
        roll, pitch = -1.5 + _sine(t, 0.5, 0.1), _sine(t, 0.3, 0.2)
    roll = roll.astype(np.float32).astype(np.float64)
    pitch = pitch.astype(np.float32).astype(np.float64)
    keep = np.ones(n, dtype=bool)
    if cid == "SYN21_isolated_nan":
        roll[np.arange(1520, 2100, 29)[:20]] = np.nan
    elif cid == "SYN22_nan_excess":
        roll[1700:1740] = np.nan
    elif cid == "SYN23_timestamp_gap":
        keep[1952:1956] = False  # t = 195.2..195.5 bị bỏ: khoảng 195.1 -> 195.6 = 0.5 s
    elif cid == "SYN24_single_dropped_sample":
        keep[2000] = False
    elif cid == "SYN26_infinite_values":
        roll[1800], roll[1900] = np.inf, -np.inf
    elif cid == "SYN27_block_coverage_rule":
        roll[500:540] = np.nan
    frame = pd.DataFrame({"time_seconds": t[keep], "roll_deg": roll[keep], "pitch_deg": pitch[keep],
                          "source_sample_index": k[keep]})
    frame.insert(0, "sample_index", np.arange(int(keep.sum())))
    return frame


# --------------------------------------------------------------------------- dữ liệu thật


@dataclass(frozen=True)
class RealCase:
    case_id: str
    dataset_source: str
    session_id: str
    segment_id: str
    start_index: int
    n_samples: int
    selection_rule: str


def select_real_cases(repo_root: Path, excerpt_samples: int = 2401) -> list[RealCase]:
    """Chọn đoạn tất định; start_index là bội số của 100 để lưới endpoint trùng lưới feature của segment."""
    cases = []
    stride = 100
    meta = pd.read_parquet(repo_root / "ml/data/features/hohai/feature_metadata.parquet", columns=["session_id", "window_id", "validity_json"])
    values = pd.read_parquet(repo_root / "ml/data/features/hohai/feature_values.parquet", columns=["window_id", "roll_std_60"])
    hohai = meta.merge(values, on="window_id")
    median = hohai.groupby("session_id").roll_std_60.median().sort_index()
    for label, session in (("max", median.idxmax()), ("min", median.idxmin())):
        cases.append(RealCase(f"REAL_hohai_{label}_roll_std", "hohai", session, "segment_000", 3000, excerpt_samples,
                              f"Session Hohai có median roll_std_60 {label} trong feature table; đoạn bắt đầu tại mẫu 3000."))
    seafar_root = repo_root / "ml/data/processed/seafar/seafar_session_001"
    lengths = {p.name: len(pd.read_parquet(p / "timeseries.parquet", columns=["time_seconds"])) for p in sorted(seafar_root.iterdir()) if p.is_dir()}
    longest = max(sorted(lengths), key=lambda s: lengths[s])
    middle = (lengths[longest] // 2 // stride) * stride
    cases.append(RealCase("REAL_seafar_longest_segment_middle", "seafar", "seafar_session_001", longest, middle, excerpt_samples,
                          f"Segment Seafar dài nhất ({longest}); đoạn giữa, start = bội số 100 gần nhất."))
    smeta = pd.read_parquet(repo_root / "ml/data/features/seafar/feature_metadata.parquet", columns=["segment_id", "window_id", "window_end_seconds"])
    svals = pd.read_parquet(repo_root / "ml/data/features/seafar/feature_values.parquet", columns=["window_id", "roll_std_60"])
    seafar = smeta.merge(svals, on="window_id").dropna()
    top = seafar.sort_values(["roll_std_60", "window_id"], ascending=[False, True]).iloc[0]
    t = pd.read_parquet(seafar_root / top.segment_id / "timeseries.parquet", columns=["time_seconds"]).time_seconds.to_numpy()
    end_index = int(np.argmin(np.abs(t - top.window_end_seconds)))
    # endpoint segment nằm trên lưới (chỉ số 600 + 100m) nên start = end - 2400 cũng là bội số 100.
    start = max(0, end_index - (excerpt_samples - 1))
    cases.append(RealCase("REAL_seafar_max_roll_std", "seafar", "seafar_session_001", str(top.segment_id), int(start),
                          min(excerpt_samples, len(t) - start),
                          "Cửa sổ Seafar có roll_std_60 lớn nhất; đoạn kết thúc gần endpoint đó, start = bội số 100."))
    s_path = repo_root / "ml/data/processed/southampton/southampton_run_14/segment_000/timeseries.parquet"
    n = len(pd.read_parquet(s_path, columns=["time_seconds"]))
    last_grid = 600 + stride * ((n - 1 - 600) // stride)
    cases.append(RealCase("REAL_southampton_run14_end", "southampton", "southampton_run_14", "segment_000",
                          last_grid - (excerpt_samples - 1), excerpt_samples,
                          "Southampton Run 14 (run duy nhất đủ 180 s): đoạn kết thúc tại endpoint lưới cuối, gồm pha tăng biên độ cuối run."))
    return cases


def real_signal(repo_root: Path, case: RealCase) -> tuple[pd.DataFrame, dict]:
    base = repo_root / "ml/data/processed" / case.dataset_source / case.session_id / case.segment_id
    frame = pd.read_parquet(base / "timeseries.parquet", columns=["dataset_source", "session_id", "segment_id", "time_seconds", "roll_deg", "pitch_deg"])
    if {frame.dataset_source.iloc[0], frame.session_id.iloc[0], frame.segment_id.iloc[0]} != {case.dataset_source, case.session_id, case.segment_id}:
        raise ValueError(f"Định danh processed không khớp: {base}")
    stop = case.start_index + case.n_samples
    if case.start_index < 0 or stop > len(frame):
        raise ValueError(f"Đoạn {case.case_id} vượt ranh giới segment.")
    part = frame.iloc[case.start_index:stop]
    out = pd.DataFrame({"sample_index": np.arange(len(part)), "time_seconds": part.time_seconds.to_numpy(float),
                        "roll_deg": part.roll_deg.to_numpy(np.float32).astype(float),
                        "pitch_deg": part.pitch_deg.to_numpy(np.float32).astype(float),
                        "source_sample_index": np.arange(case.start_index, stop)})
    provenance = json.loads((base / "provenance.json").read_text(encoding="utf-8"))
    keep = ("raw_reference", "source_class", "timestamp_source", "original_sampling_hz", "preprocessing_version",
            "configuration_sha256", "filter")
    return out, {k: provenance.get(k) for k in keep}
