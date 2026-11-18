from __future__ import annotations

LABELS = ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH",
          "UNLABELED", "REVIEW_REQUIRED")
LABEL_SOURCES = ("EXTERNAL_REFERENCE", "HUMAN_REVIEW", "PROXY_RULE", "UNKNOWN")
LABEL_STATUSES = ("VERIFIED", "HUMAN_REVIEWED", "PROXY", "REVIEW_REQUIRED", "UNLABELED")
REVIEW_STATUSES = ("NOT_REVIEWED", "PENDING", "ACCEPTED", "REJECTED", "NEEDS_DISCUSSION")

IDENTITY_COLUMNS = ("dataset_source", "session_id", "segment_id", "window_start_seconds",
                    "window_end_seconds")
LABEL_COLUMNS = (*IDENTITY_COLUMNS, "label", "label_status", "label_source", "labeling_method",
                 "rule_version", "evidence_reference", "review_status", "ambiguity_reason",
                 "quality_flags", "phenotype_flags_json", "suggested_label")

ANGLE_ONLY_23 = (
    "roll_rms_60", "roll_std_60", "roll_mean_60", "roll_peak_to_peak_60",
    "roll_abs_p95_60", "roll_abs_max_60", "roll_iqr_60", "roll_diff_rms_60",
    "roll_mean_180", "roll_median_180", "roll_mean_abs_180",
    "roll_dominant_sign_ratio_180", "roll_segment_mean_std_180", "roll_mean_shift_180",
    "roll_rms_early_60", "roll_rms_late_60", "roll_rms_ratio_180", "roll_rms_slope_180",
    "roll_rms_trend_r2_180", "roll_p95_trend_slope_180", "pitch_rms_60", "pitch_std_60",
    "pitch_peak_to_peak_60",
)

FEATURE_STATUS_VALUES = ("VALID", "MISSING_SOURCE_SIGNAL", "INSUFFICIENT_WINDOW",
                         "INVALID_INPUT", "UNDEFINED_MATHEMATICALLY", "UNVERIFIED_SIGNAL_MAPPING")
