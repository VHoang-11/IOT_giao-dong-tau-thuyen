/* Causal 10 Hz windows; see contracts/features.md. */
#ifndef SVMG_FEATURES_H
#define SVMG_FEATURES_H
#include "svmg_common.h"
#include "svmg_feature_schema.h"
#ifdef __cplusplus
extern "C" {
#endif
#define SVMG_WIN_SHORT 600
#define SVMG_WIN_LONG 1800
#define SVMG_UPDATE_SAMPLES (SVMG_FEATURE_HZ * SVMG_FEATURE_UPDATE_S)
#define SVMG_RAW_PER_SAMPLE 2
#define SVMG_SEG_SAMPLES 600
#define SVMG_N_SEGMENTS 3
#define SVMG_RMS_EPSILON_DEG 1e-9
#define SVMG_R2_ZERO_TOLERANCE 1e-15

typedef struct {
  float roll_deg[SVMG_WIN_LONG], pitch_deg[SVMG_WIN_LONG];
  uint8_t valid[SVMG_WIN_LONG], nraw[SVMG_WIN_LONG];
  /* Reusable sorting workspace, NOT an ESP32 stack allocation. */
  float scratch[SVMG_WIN_LONG];
  uint32_t total;
  uint16_t since_update, consec_invalid;
} svmg_window_t;
typedef struct {
#define FIELD(name) float name;
  SVMG_FEATURE_FIELDS(FIELD)
#undef FIELD
  uint32_t valid_mask;
  float data_quality_pct, sensor_ok;
  uint16_t n_valid_60, n_valid_180, consec_invalid;
  uint8_t ready_short, ready_long;
  /* Compatibility diagnostics for telemetry, outside the RF input. */
  float rms_roll, p95_roll, rms_pitch, p95_pitch, max_abs_roll, energy_roll;
  float mean_roll, mean_pitch, std_roll, trend_rms_slope;
} svmg_features_t;
void svmg_window_clear(svmg_window_t *w);
int svmg_window_push(svmg_window_t *w, float roll, float pitch, uint8_t nraw,
                     uint8_t valid);
void svmg_window_shift(svmg_window_t *w, float dr, float dp);
/* Mutates the sorting workspace only, never the historical samples. */
void svmg_features_compute(svmg_window_t *w, svmg_features_t *f);
void svmg_features_to_vector(const svmg_features_t *f,
                             float out[SVMG_N_FEATURES]);
int svmg_features_vector_valid(const svmg_features_t *f);
extern const char *const SVMG_FEATURE_NAMES[SVMG_N_FEATURES];
#define SVMG_Q_COLD 0x01
#define SVMG_Q_LOWQUALITY 0x02
#define SVMG_Q_FAULT_RUN 0x04
#define SVMG_Q_FAULT_PCT 0x08
#define SVMG_Q_VECTOR_INVALID 0x10
typedef struct {
  float unknown_quality_pct, fault_quality_pct;
  uint16_t fault_consec_invalid;
} svmg_quality_cfg_t;
void svmg_quality_default(svmg_quality_cfg_t *q);
svmg_status_t svmg_features_status(const svmg_features_t *f,
                                   const svmg_quality_cfg_t *q,
                                   uint8_t *reason);
/* Host/ctypes: oldest-first, fixed 10 Hz grid; nraw NULL means 2/2 raw samples.
 * Undefined features remain NaN; return includes vector validity. */
int svmg_features_from_series(const float *roll, const float *pitch,
                              const uint8_t *nraw, int n,
                              float out[SVMG_N_FEATURES]);
#ifdef __cplusplus
}
#endif
#endif
