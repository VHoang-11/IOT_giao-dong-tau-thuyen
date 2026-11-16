"""Thứ tự và ánh xạ tín hiệu của 30 candidate features."""

FEATURE_NAMES = (
    "roll_rms_60", "roll_std_60", "roll_mean_60", "roll_peak_to_peak_60",
    "roll_abs_p95_60", "roll_abs_max_60", "roll_iqr_60", "roll_diff_rms_60",
    "gyro_x_rms_60", "gyro_x_abs_p95_60", "gyro_x_std_60",
    "roll_mean_180", "roll_median_180", "roll_mean_abs_180",
    "roll_dominant_sign_ratio_180", "roll_segment_mean_std_180",
    "roll_mean_shift_180", "roll_rms_early_60", "roll_rms_late_60",
    "roll_rms_ratio_180", "roll_rms_slope_180", "roll_rms_trend_r2_180",
    "roll_p95_trend_slope_180", "roll_period_est_180",
    "roll_zero_crossings_180", "roll_period_cv_180", "pitch_rms_60",
    "pitch_std_60", "pitch_peak_to_peak_60", "gyro_y_rms_60",
)

WINDOW_SECONDS = {name: 60 for name in FEATURE_NAMES[:11]}
WINDOW_SECONDS.update({name: 180 for name in FEATURE_NAMES[11:26]})
WINDOW_SECONDS.update({name: 60 for name in FEATURE_NAMES[26:]})

FEATURE_GROUPS = {
    "A_roll_amplitude_60": FEATURE_NAMES[0:8],
    "B_roll_angular_velocity_60": FEATURE_NAMES[8:11],
    "C_persistent_offset_180": FEATURE_NAMES[11:17],
    "D_amplitude_growth_180": FEATURE_NAMES[17:23],
    "E_oscillation_period_180": FEATURE_NAMES[23:26],
    "F_pitch_60": FEATURE_NAMES[26:30],
}

PRACTICAL_SUBSETS = {
    "roll_only_60": FEATURE_NAMES[0:8],
    "roll_pitch_angle_60": (*FEATURE_NAMES[0:8], *FEATURE_NAMES[26:29]),
    "offset_and_growth_180": FEATURE_NAMES[11:23],
    "angle_only_23_without_gyro_or_period": (
        *FEATURE_NAMES[0:8], *FEATURE_NAMES[11:23], *FEATURE_NAMES[26:29]),
}

VALIDITY_STATUSES = (
    "VALID", "MISSING_SOURCE_SIGNAL", "INSUFFICIENT_WINDOW", "INVALID_INPUT",
    "UNDEFINED_MATHEMATICALLY", "UNVERIFIED_SIGNAL_MAPPING",
)
