"""Đặc tả dung sai parity theo từng feature (ĐỀ XUẤT KỸ THUẬT, chưa phải độ chính xác đo trên thiết bị).

Quy tắc: |c - p| <= abs_floor + rel * |p| + scale_rel * S, với S = max|x| hữu hạn của tín hiệu và cửa sổ mà feature
dùng (roll 60 s, roll 180 s hoặc pitch 60 s). Lý do có hạng S: sai số làm tròn float32 tỷ lệ với độ lớn ĐẦU VÀO,
không với giá trị đầu ra (ví dụ std nhỏ của một tín hiệu offset lớn bị triệt tiêu số học).
Giả định: đầu vào là chính các giá trị float32 của golden; u32 = 2^-24 ≈ 5.96e-8.
"""
from __future__ import annotations

import math

U32 = 2.0 ** -24
R2_MIN_RELATIVE_SST = 1e-6          # dưới mức này R² bị coi là ill-conditioned (REVIEW)
EPSILON_REVIEW_FACTOR = 10.0        # rms_early trong [eps/10, eps*10] -> ratio ill-conditioned (REVIEW)

CLASSES = {
    "mean": {"abs_floor": 1e-7, "rel": 0.0, "scale_rel": 2e-5,
             "rationale": "Tổng N <= 1800 phần tử float32: sai số điển hình ~sqrt(N)·u ≈ 2.5e-6, chặn xấu N·u ≈ 1.1e-4 nếu cộng tuần tự; đề xuất C cộng dồn compensated/double."},
    "rms": {"abs_floor": 1e-7, "rel": 2e-5, "scale_rel": 2e-6,
            "rationale": "Tổng bình phương dương, không triệt tiêu; sai số tương đối theo giá trị."},
    "dispersion": {"abs_floor": 1e-7, "rel": 2e-5, "scale_rel": 5e-5,
                   "rationale": "Phương sai có triệt tiêu khi |mean| >> std; hạng tỷ lệ theo biên độ đầu vào. Vẫn đủ chặt để phân biệt std quần thể/mẫu (lệch 8.3e-4 tương đối) ở tín hiệu mean 0."},
    "difference_rms": {"abs_floor": 1e-7, "rel": 2e-5, "scale_rel": 2e-6,
                       "rationale": "Hiệu hai mẫu float32 kề nhau rồi RMS."},
    "extremum": {"abs_floor": 1e-9, "rel": 2e-7, "scale_rel": 2e-7,
                 "rationale": "Chọn đúng một giá trị float32 đầu vào (abs_max) hoặc một phép trừ (peak-to-peak): gần như chính xác."},
    "quantile": {"abs_floor": 1e-9, "rel": 1e-6, "scale_rel": 4e-6,
                 "rationale": "Sắp xếp chính xác + một phép nội suy Type-7 (IQR thêm một phép trừ). Đủ chặt để bắt sai quy ước phân vị."},
    "count_ratio": {"abs_floor": 1e-6, "rel": 0.0, "scale_rel": 0.0,
                    "rationale": "Đếm dấu trên giá trị float32 chính xác; chỉ sai số chia."},
    "mean_difference": {"abs_floor": 1e-7, "rel": 0.0, "scale_rel": 4e-5,
                        "rationale": "Hiệu hai mean block: cộng dồn sai số hai tổng."},
    "ratio": {"abs_floor": 1e-9, "rel": 5e-5, "scale_rel": 0.0,
              "rationale": "Tỷ số hai RMS: sai số tương đối cộng dồn của tử và mẫu."},
    "slope": {"abs_floor": 1e-7, "rel": 1e-5, "scale_rel": 2e-5,
              "rationale": "OLS 3 điểm cách đều = (r3 - r1)/2 deg/phút; sai số theo biên độ đầu vào."},
    "r_squared": {"abs_floor": 2e-3, "rel": 0.0, "scale_rel": 0.0,
                  "rationale": "Chỉ áp dụng khi SST/mean(r)^2 >= 1e-6; dưới mức đó R² ill-conditioned -> REVIEW."},
}

FEATURE_CLASS = {
    "roll_rms_60": "rms", "roll_std_60": "dispersion", "roll_mean_60": "mean", "roll_peak_to_peak_60": "extremum",
    "roll_abs_p95_60": "quantile", "roll_abs_max_60": "extremum", "roll_iqr_60": "quantile",
    "roll_diff_rms_60": "difference_rms", "roll_mean_180": "mean", "roll_median_180": "quantile",
    "roll_mean_abs_180": "mean", "roll_dominant_sign_ratio_180": "count_ratio",
    "roll_segment_mean_std_180": "dispersion", "roll_mean_shift_180": "mean_difference",
    "roll_rms_early_60": "rms", "roll_rms_late_60": "rms", "roll_rms_ratio_180": "ratio",
    "roll_rms_slope_180": "slope", "roll_rms_trend_r2_180": "r_squared", "roll_p95_trend_slope_180": "slope",
    "pitch_rms_60": "rms", "pitch_std_60": "dispersion", "pitch_peak_to_peak_60": "extremum",
}

FEATURE_SCALE = {name: ("pitch_scale_60" if name.startswith("pitch_") else
                        "roll_scale_60" if name in ("roll_rms_60", "roll_std_60", "roll_mean_60", "roll_peak_to_peak_60",
                                                    "roll_abs_p95_60", "roll_abs_max_60", "roll_iqr_60", "roll_diff_rms_60")
                        else "roll_scale_180") for name in FEATURE_CLASS}


def allowed_error(feature: str, expected: float, scale: float | None) -> float:
    spec = CLASSES[FEATURE_CLASS[feature]]
    s = 0.0 if scale is None or not math.isfinite(scale) else abs(scale)
    return spec["abs_floor"] + spec["rel"] * abs(expected) + spec["scale_rel"] * s


def tolerance_document() -> dict:
    return {"tolerance_version": "svmg-angle23-tolerance-0.1.0-proposal", "status": "ENGINEERING_PROPOSAL_NOT_DEVICE_MEASURED",
            "formula": "abs(actual - expected) <= abs_floor + rel*abs(expected) + scale_rel*S",
            "scale_definition": "S = max |x| trên các mẫu hữu hạn của tín hiệu/cửa sổ tương ứng (cột tolerance_scale trong golden)",
            "u32": U32, "classes": CLASSES, "feature_class": FEATURE_CLASS, "feature_scale": FEATURE_SCALE,
            "review_conditions": {
                "roll_rms_trend_r2_180": f"SST/mean(block_rms)^2 < {R2_MIN_RELATIVE_SST} -> REVIEW_ILL_CONDITIONED (giá trị và validity)",
                "roll_rms_ratio_180": f"rms block đầu trong [eps/{EPSILON_REVIEW_FACTOR:g}, eps*{EPSILON_REVIEW_FACTOR:g}] -> REVIEW_ILL_CONDITIONED"},
            "status_rule": "Trạng thái phải trùng chính xác; feature không VALID phải có value rỗng/null; VALID mà NaN là FAIL.",
            "note": "Giá trị dung sai là đề xuất kỹ thuật dựa trên phân tích làm tròn float32; cần M1/M2 xác nhận sau khi có đầu ra C thật."}
