/* Versioned model input; quality/safety metadata is not part of this vector. */
#ifndef SVMG_FEATURE_SCHEMA_H
#define SVMG_FEATURE_SCHEMA_H
#define SVMG_FEATURE_SCHEMA_VERSION "svmg-angle-23-v1"
#define SVMG_PREPROCESSING_VERSION "imu-cf-bw4-20to10-v1"
#define SVMG_FEATURE_HZ 10
#define SVMG_FEATURE_UPDATE_S 10
#define SVMG_N_FEATURES 23
#define SVMG_FEATURE_FIELDS(X)                                                 \
  X(roll_rms_60)                                                               \
  X(roll_std_60) X(roll_mean_60) X(roll_peak_to_peak_60) X(roll_abs_p95_60)    \
      X(roll_abs_max_60) X(roll_iqr_60) X(roll_diff_rms_60) X(roll_mean_180)   \
          X(roll_median_180) X(roll_mean_abs_180)                              \
              X(roll_dominant_sign_ratio_180) X(roll_segment_mean_std_180)     \
                  X(roll_mean_shift_180) X(roll_rms_early_60)                  \
                      X(roll_rms_late_60) X(roll_rms_ratio_180)                \
                          X(roll_rms_slope_180) X(roll_rms_trend_r2_180)       \
                              X(roll_p95_trend_slope_180) X(pitch_rms_60)      \
                                  X(pitch_std_60) X(pitch_peak_to_peak_60)
#define SVMG_FEATURE_ENUM(name) SVMG_F_##name,
typedef enum {
  SVMG_FEATURE_FIELDS(SVMG_FEATURE_ENUM) SVMG_FEATURE_COUNT
} svmg_feature_id_t;
#undef SVMG_FEATURE_ENUM
#define SVMG_FEATURE_ALL_VALID ((1u << SVMG_N_FEATURES) - 1u)
#endif
