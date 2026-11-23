#include "svmg_features.h"
#include "svmg_filter.h"
#include <stddef.h>

#define ROW_WIDTH (7 + SVMG_N_FEATURES)
static svmg_pipeline_t pipeline;
static svmg_window_t window_state;

/* Input is the existing simulator's FRD IMU stream. Output rows are
 * endpoint_s, mask, ready flags, valid counts, quality pct, then 23 C values. */
int svmg_g1_extract(const svmg_motion_sample_t *samples, size_t count,
                    float *rows, size_t row_capacity) {
  if (!samples || !rows) return -1;
  svmg_pipeline_cfg_t cfg;
  svmg_pipeline_default_cfg(&cfg);
  svmg_pipeline_init(&pipeline, &cfg);
  svmg_window_clear(&window_state);
  size_t used = 0;
  for (size_t i = 0; i < count; ++i) {
    svmg_motion_sample_t input = samples[i];
    svmg_sample_frd_to_sensor(&input);
    svmg_sample10hz_t out;
    if (!svmg_pipeline_push(&pipeline, &input, &out)) continue;
    if (out.flags & SVMG_PIPE_F_WARMUP) continue;
    uint8_t valid = out.n_valid >= 2 && !(out.flags & SVMG_PIPE_F_PARTIAL);
    int due = svmg_window_push(&window_state, out.roll_rad * SVMG_RAD2DEG,
                               out.pitch_rad * SVMG_RAD2DEG, out.n_valid, valid);
    if (!due) continue;
    if (used >= row_capacity) return -2;
    svmg_features_t features;
    float *row = rows + used * ROW_WIDTH;
    svmg_features_compute(&window_state, &features);
    row[0] = out.t_s;
    row[1] = (float)features.valid_mask;
    row[2] = (float)features.ready_short;
    row[3] = (float)features.ready_long;
    row[4] = (float)features.n_valid_60;
    row[5] = (float)features.n_valid_180;
    row[6] = features.data_quality_pct;
    svmg_features_to_vector(&features, row + 7);
    ++used;
  }
  return (int)used;
}
