"""Kiểm tra giải tích ĐỘC LẬP cho một số case synthetic (Level 1: tính đúng của tham chiếu Python).

Giá trị kỳ vọng được suy ra bằng công thức đóng (không gọi extractor), tại endpoint cuối t = 210 s:
cửa sổ 60 s = mẫu k ∈ [1501, 2100], cửa sổ 180 s = k ∈ [301, 2100], block = [301,900], [901,1500], [1501,2100].
Sai lệch cho phép nhỏ (abs 1e-9 + 2e-6·biên độ) chỉ để hấp thụ việc làm tròn đầu vào về float32.
"""
from __future__ import annotations

import math

import numpy as np

S2 = math.sqrt(2.0)


def _ramp_stats(lo_k: int, hi_k: int, offset: float = 0.5, step: float = 1 / 256):
    k = np.arange(lo_k, hi_k + 1, dtype=np.float64)
    n = len(k)
    mean = offset + step * (lo_k + hi_k) / 2.0
    # Σ x² cho cấp số cộng: n·mean² + step²·Σ(k - k̄)² ; Σ(k - k̄)² = n(n²-1)/12
    var = step ** 2 * (n * n - 1) / 12.0
    return {"n": n, "mean": mean, "rms": math.sqrt(mean * mean + var), "std": math.sqrt(var),
            "min": offset + step * lo_k, "max": offset + step * hi_k}


def expectations(case_id: str) -> dict:
    """{feature: ("value", số, diễn giải) | ("status", trạng thái, diễn giải)} tại endpoint 210 s."""
    e = {}
    zeros60 = ("roll_rms_60", "roll_std_60", "roll_mean_60", "roll_peak_to_peak_60", "roll_abs_p95_60",
               "roll_abs_max_60", "roll_iqr_60", "roll_diff_rms_60")
    if case_id == "SYN01_const_zero":
        for f in (*zeros60, "roll_mean_180", "roll_median_180", "roll_mean_abs_180", "roll_segment_mean_std_180",
                  "roll_mean_shift_180", "roll_rms_early_60", "roll_rms_late_60", "roll_rms_slope_180",
                  "roll_p95_trend_slope_180", "pitch_rms_60", "pitch_std_60", "pitch_peak_to_peak_60"):
            e[f] = ("value", 0.0, "tín hiệu hằng 0")
        for f in ("roll_rms_ratio_180", "roll_rms_trend_r2_180", "roll_dominant_sign_ratio_180"):
            e[f] = ("status", "UNDEFINED_MATHEMATICALLY", "mẫu số 0 / SST = 0 / không có mẫu khác 0")
    elif case_id == "SYN02_const_roll_pos":
        c = 3.0
        e.update({"roll_rms_60": ("value", c, "|c|"), "roll_std_60": ("value", 0.0, "hằng"), "roll_mean_60": ("value", c, "c"),
                  "roll_peak_to_peak_60": ("value", 0.0, "hằng"), "roll_abs_p95_60": ("value", c, "|c|"),
                  "roll_abs_max_60": ("value", c, "|c|"), "roll_iqr_60": ("value", 0.0, "hằng"), "roll_diff_rms_60": ("value", 0.0, "hằng"),
                  "roll_mean_180": ("value", c, "c"), "roll_median_180": ("value", c, "c"), "roll_mean_abs_180": ("value", c, "|c|"),
                  "roll_dominant_sign_ratio_180": ("value", 1.0, "mọi mẫu dương"), "roll_segment_mean_std_180": ("value", 0.0, "hằng"),
                  "roll_mean_shift_180": ("value", 0.0, "hằng"), "roll_rms_early_60": ("value", c, "|c|"),
                  "roll_rms_late_60": ("value", c, "|c|"), "roll_rms_ratio_180": ("value", 1.0, "c/c"),
                  "roll_rms_slope_180": ("value", 0.0, "RMS block bằng nhau"), "roll_rms_trend_r2_180": ("status", "UNDEFINED_MATHEMATICALLY", "SST = 0")})
    elif case_id == "SYN04_sine_roll":
        a, dphi = 5.0, 2 * math.pi * 0.1 * 0.1
        # Sai phân d_k = 2A·sin(Δ/2)·cos(θ(k-1/2)), θ(x) = 0.3 + Δx. Cửa sổ có 600 mẫu nhưng chỉ 599 cặp (k = 1502..2100):
        # Σ_{600 cặp} cos(2θ) = 0 (12 chu kỳ đủ) nên Σ_{599 cặp} cos(2θ) = -cos(2θ(1500.5)).
        mean_cos2 = 0.5 - math.cos(2 * (0.3 + dphi * 1500.5)) / (2 * 599)
        diff_rms = 2 * a * math.sin(dphi / 2) * math.sqrt(mean_cos2)
        e.update({"roll_rms_60": ("value", a / S2, "A/√2, số chu kỳ nguyên"), "roll_std_60": ("value", a / S2, "std quần thể = A/√2"),
                  "roll_mean_60": ("value", 0.0, "tổng sin trên chu kỳ nguyên = 0"),
                  "roll_diff_rms_60": ("value", diff_rms, "2A·sin(Δ/2)·√(1/2 - cos(2θ(1500.5))/(2·599)): 599 cặp, không phải 600"),
                  "roll_dominant_sign_ratio_180": ("value", 0.5, "50 mẫu dương / 50 mẫu âm mỗi chu kỳ"),
                  "roll_rms_early_60": ("value", a / S2, "A/√2"), "roll_rms_late_60": ("value", a / S2, "A/√2"),
                  "roll_rms_ratio_180": ("value", 1.0, "RMS block bằng nhau"), "roll_rms_slope_180": ("value", 0.0, "RMS block bằng nhau")})
    elif case_id == "SYN05_sine_pitch":
        e.update({"pitch_rms_60": ("value", 2.0 / S2, "A/√2, 12 chu kỳ"), "pitch_std_60": ("value", 2.0 / S2, "std quần thể = A/√2")})
    elif case_id in ("SYN09_block_step_linear", "SYN10_block_step_nonlinear", "SYN29_block_step_symmetric"):
        r = np.array({"SYN09": (1.0, 2.0, 3.0), "SYN10": (1.0, 3.0, 2.0), "SYN29": (1.0, 2.0, 1.0)}[case_id[:5]]) / S2
        u = np.array([30.0, 90.0, 150.0])
        slope = float(np.sum((u - u.mean()) * (r - r.mean())) / np.sum((u - u.mean()) ** 2))
        fitted = r.mean() + slope * (u - u.mean())
        r2 = 1 - float(np.sum((r - fitted) ** 2) / np.sum((r - r.mean()) ** 2))
        e.update({"roll_rms_early_60": ("value", r[0], "A1/√2"), "roll_rms_late_60": ("value", r[2], "A3/√2"),
                  "roll_rms_60": ("value", r[2], "A3/√2"), "roll_rms_ratio_180": ("value", r[2] / r[0], "A3/A1"),
                  "roll_rms_slope_180": ("value", slope * 60.0, "OLS 3 điểm × 60"),
                  "roll_rms_trend_r2_180": ("value", r2, "1 - SSE/SST (giải tích: 1, 0.25 hoặc 0; R² = 0 là VALID, khác UNDEFINED)")})
    elif case_id == "SYN13_ramp_quantiles":
        step = 1 / 256
        w60, w180 = _ramp_stats(1501, 2100), _ramp_stats(301, 2100)
        blocks = [_ramp_stats(301, 900), _ramp_stats(901, 1500), _ramp_stats(1501, 2100)]
        means = np.array([b["mean"] for b in blocks])
        e.update({"roll_mean_60": ("value", w60["mean"], "trung bình cấp số cộng"), "roll_rms_60": ("value", w60["rms"], "√(mean² + step²(n²-1)/12)"),
                  "roll_std_60": ("value", w60["std"], "step·√((n²-1)/12)"), "roll_peak_to_peak_60": ("value", step * 599, "599 bước"),
                  "roll_abs_max_60": ("value", w60["max"], "mẫu cuối"),
                  "roll_abs_p95_60": ("value", w60["min"] + 0.95 * 599 * step, "Type-7: x_min + p(n-1)·bước"),
                  "roll_iqr_60": ("value", 0.5 * 599 * step, "Type-7: (0.75-0.25)(n-1)·bước"),
                  "roll_diff_rms_60": ("value", step, "sai phân hằng"), "roll_mean_180": ("value", w180["mean"], "trung bình"),
                  "roll_median_180": ("value", w180["min"] + 0.5 * 1799 * step, "Type-7 median"),
                  "roll_mean_abs_180": ("value", w180["mean"], "toàn dương"), "roll_dominant_sign_ratio_180": ("value", 1.0, "toàn dương"),
                  "roll_segment_mean_std_180": ("value", float(np.std(means)), "std quần thể của 3 mean (bước 600·step)"),
                  "roll_mean_shift_180": ("value", 1200 * step, "mean block 3 - block 1 = 1200 bước"),
                  "roll_rms_early_60": ("value", blocks[0]["rms"], "RMS cấp số cộng"), "roll_rms_late_60": ("value", blocks[2]["rms"], "RMS cấp số cộng"),
                  "roll_p95_trend_slope_180": ("value", 600 * step, "P95 block tăng 600 bước mỗi 60 s -> deg/phút")})
    elif case_id == "SYN14_square_wave_quantile_discontinuity":
        e.update({"roll_rms_60": ("value", 1.0, "|x| = 1"), "roll_std_60": ("value", 1.0, "±1 cân bằng"), "roll_mean_60": ("value", 0.0, "300/300"),
                  "roll_abs_p95_60": ("value", 1.0, "|x| = 1"), "roll_iqr_60": ("value", 2.0, "Q25 = -1, Q75 = +1"),
                  "roll_median_180": ("value", 0.0, "Type-7 h = 899.5 nội suy giữa -1 và +1"),
                  "roll_dominant_sign_ratio_180": ("value", 0.5, "900/900"),
                  "roll_diff_rms_60": ("value", math.sqrt(60 * 4 / 599), "60 bước nhảy 2 trong 599 cặp")})
    elif case_id == "SYN16_sign_with_exact_zeros":
        e["roll_dominant_sign_ratio_180"] = ("value", 6 / 9, "6 dương, 3 âm, 1 số 0 bị loại mỗi 10 mẫu")
    elif case_id == "SYN17_zero_early_block":
        e.update({"roll_rms_ratio_180": ("status", "UNDEFINED_MATHEMATICALLY", "RMS block đầu = 0 <= epsilon"),
                  "roll_rms_early_60": ("value", 0.0, "block 0"), "roll_rms_late_60": ("value", 1 / S2, "A/√2")})
    elif case_id == "SYN18_epsilon_below":
        e["roll_rms_ratio_180"] = ("status", "UNDEFINED_MATHEMATICALLY", "RMS block đầu ≈ 7e-11 <= 1e-9")
    elif case_id == "SYN19_epsilon_above":
        e["roll_rms_ratio_180"] = ("value", 1e7, "≈ (1/√2)/(1e-7/√2); sai lệch do làm tròn float32 biên độ 1e-7")
    elif case_id == "SYN20_insufficient_history":
        e["roll_mean_180"] = ("status", "INSUFFICIENT_WINDOW", "chỉ 150 s lịch sử")
        e["roll_rms_60"] = ("status", "VALID", "150 s >= 60 s")
    elif case_id == "SYN22_nan_excess":
        e.update({"roll_rms_60": ("status", "INVALID_INPUT", "40 NaN liên tiếp: 560 < 570 mẫu hữu hạn trong (150, 210]"),
                  "roll_mean_180": ("status", "VALID", "1760 >= 1710 mẫu hữu hạn trong (30, 210]"),
                  "roll_rms_early_60": ("status", "INVALID_INPUT", "block cuối thiếu mẫu làm cả 8 feature block INVALID (C01)"),
                  "pitch_rms_60": ("status", "VALID", "NaN chỉ ở kênh Roll")})
    elif case_id in ("SYN23_timestamp_gap", "SYN24_single_dropped_sample"):
        e.update({"roll_rms_60": ("status", "INVALID_INPUT", "khoảng trống timestamp > 0,15 s nằm trong (t-60, t]"),
                  "pitch_rms_60": ("status", "INVALID_INPUT", "gap timestamp ảnh hưởng mọi kênh")})
    elif case_id == "SYN26_infinite_values":
        e.update({"roll_rms_60": ("status", "VALID", "±Inf bị loại như mẫu thiếu; 2 mẫu < 5%"),
                  "roll_diff_rms_60": ("status", "VALID", "Inf xóa 4 cặp kề nhau: 595 >= 570 cặp")})
    elif case_id == "SYN30_permuted_blocks":
        e.update({"roll_rms_ratio_180": ("value", 1.0, "block 1 và 3 cùng tập giá trị: RMS bằng nhau chính xác"),
                  "roll_rms_slope_180": ("value", 0.0, "RMS 3 block bằng nhau"),
                  "roll_mean_shift_180": ("value", 0.0, "mean bằng nhau"),
                  "roll_segment_mean_std_180": ("value", 0.0, "mean bằng nhau"),
                  "roll_p95_trend_slope_180": ("value", 0.0, "P95 của cùng tập giá trị"),
                  "roll_rms_trend_r2_180": ("status", "UNDEFINED_MATHEMATICALLY", "SST = 0 chính xác (tổng fsum không phụ thuộc thứ tự)")})
    elif case_id == "SYN27_block_coverage_rule":
        e.update({"roll_rms_60": ("status", "VALID", "NaN nằm ngoài (150, 210]"),
                  "roll_mean_180": ("status", "VALID", "1760 >= 1710"),
                  "roll_rms_late_60": ("status", "INVALID_INPUT", "block ĐẦU thiếu mẫu vẫn làm rms_late INVALID theo extractor (C01)")})
    return e


def run_checks(case_id: str, endpoint: dict, feature_order) -> list[dict]:
    exp = expectations(case_id)
    rows = []
    for feature, (kind, value, why) in exp.items():
        i = feature_order.index(feature)
        status, golden = endpoint["status"][i], endpoint["vector"][i]
        scale = endpoint["scales"]["pitch_scale_60" if feature.startswith("pitch") else "roll_scale_180"] or 0.0
        if kind == "status":
            passed = status == value
            rows.append({"case_id": case_id, "feature": feature, "expected": value, "golden": status, "passed": bool(passed), "derivation": why})
        else:
            tol = 1e-9 + 2e-6 * scale + (1e-6 * abs(value) if feature == "roll_rms_ratio_180" else 0.0)
            if case_id == "SYN19_epsilon_above":
                tol = 1e-6 * abs(value)  # làm tròn float32 của biên độ 1e-7
            diff = None if golden is None else abs(golden - value)
            rows.append({"case_id": case_id, "feature": feature, "expected": value, "golden": golden, "abs_diff": diff,
                         "tolerance": tol, "passed": bool(status == "VALID" and diff is not None and diff <= tol), "derivation": why})
    return rows
