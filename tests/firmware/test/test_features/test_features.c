/* Independent analytic checks for the selected 23 features. Python parity is a
 * separate tool. */
#include "svmg_features.h"
#include <math.h>
#include <string.h>
#include <unity.h>
static svmg_window_t W;
static svmg_features_t F;
static svmg_quality_cfg_t Q;
void setUp(void) {
  svmg_window_clear(&W);
  svmg_quality_default(&Q);
}
void tearDown(void) {}
static void push(float r, float p) { svmg_window_push(&W, r, p, 2, 1); }
static void compute(void) { svmg_features_compute(&W, &F); }
static void constant(int n, float r, float p) {
  for (int i = 0; i < n; i++)
    push(r, p);
}
void test_schema_order_and_dimension(void) {
  const char *names[23] = {"roll_rms_60",
                           "roll_std_60",
                           "roll_mean_60",
                           "roll_peak_to_peak_60",
                           "roll_abs_p95_60",
                           "roll_abs_max_60",
                           "roll_iqr_60",
                           "roll_diff_rms_60",
                           "roll_mean_180",
                           "roll_median_180",
                           "roll_mean_abs_180",
                           "roll_dominant_sign_ratio_180",
                           "roll_segment_mean_std_180",
                           "roll_mean_shift_180",
                           "roll_rms_early_60",
                           "roll_rms_late_60",
                           "roll_rms_ratio_180",
                           "roll_rms_slope_180",
                           "roll_rms_trend_r2_180",
                           "roll_p95_trend_slope_180",
                           "pitch_rms_60",
                           "pitch_std_60",
                           "pitch_peak_to_peak_60"};
  TEST_ASSERT_EQUAL_INT(23, SVMG_N_FEATURES);
  for (int i = 0; i < 23; i++)
    TEST_ASSERT_EQUAL_STRING(names[i], SVMG_FEATURE_NAMES[i]);
}
void test_three_blocks_analytic_values(void) {
  for (int j = 0; j < 3; j++)
    for (int i = 0; i < 600; i++)
      push((i % 2 ? 1 : -1) * (float)(j + 1), i % 2 ? 2 : -2);
  compute();
  TEST_ASSERT_FLOAT_WITHIN(1e-6, 3, F.roll_rms_60);
  TEST_ASSERT_FLOAT_WITHIN(1e-6, 3, F.roll_std_60);
  TEST_ASSERT_EQUAL_FLOAT(0, F.roll_mean_60);
  TEST_ASSERT_EQUAL_FLOAT(6, F.roll_peak_to_peak_60);
  TEST_ASSERT_EQUAL_FLOAT(3, F.roll_abs_p95_60);
  TEST_ASSERT_EQUAL_FLOAT(6, F.roll_iqr_60);
  TEST_ASSERT_EQUAL_FLOAT(6, F.roll_diff_rms_60);
  TEST_ASSERT_EQUAL_FLOAT(0, F.roll_median_180);
  TEST_ASSERT_EQUAL_FLOAT(2, F.roll_mean_abs_180);
  TEST_ASSERT_EQUAL_FLOAT(.5f, F.roll_dominant_sign_ratio_180);
  TEST_ASSERT_EQUAL_FLOAT(0, F.roll_segment_mean_std_180);
  TEST_ASSERT_EQUAL_FLOAT(0, F.roll_mean_shift_180);
  TEST_ASSERT_EQUAL_FLOAT(1, F.roll_rms_early_60);
  TEST_ASSERT_EQUAL_FLOAT(3, F.roll_rms_late_60);
  TEST_ASSERT_EQUAL_FLOAT(3, F.roll_rms_ratio_180);
  TEST_ASSERT_EQUAL_FLOAT(1, F.roll_rms_slope_180);
  TEST_ASSERT_EQUAL_FLOAT(1, F.roll_rms_trend_r2_180);
  TEST_ASSERT_EQUAL_FLOAT(1, F.roll_p95_trend_slope_180);
  TEST_ASSERT_EQUAL_FLOAT(2, F.pitch_rms_60);
  TEST_ASSERT_EQUAL_FLOAT(2, F.pitch_std_60);
  TEST_ASSERT_EQUAL_FLOAT(4, F.pitch_peak_to_peak_60);
  TEST_ASSERT_TRUE(svmg_features_vector_valid(&F));
  svmg_window_clear(&W);
  for (int block = 0; block < 3; block++) {
    float amplitude = block == 1 ? 2.0f : 1.0f;
    for (int i = 0; i < 600; i++)
      push((i % 2 ? 1.0f : -1.0f) * amplitude, 0);
  }
  compute();
  TEST_ASSERT_EQUAL_FLOAT(0.0f, F.roll_rms_trend_r2_180);
}
void test_ramp_quantiles_population_and_difference(void) {
  for (int i = 0; i < 1800; i++)
    push((float)i, 0);
  compute();
  TEST_ASSERT_FLOAT_WITHIN(.001, 1769.05, F.roll_abs_p95_60);
  TEST_ASSERT_FLOAT_WITHIN(.001, 299.5, F.roll_iqr_60);
  TEST_ASSERT_FLOAT_WITHIN(.001, 899.5, F.roll_median_180);
  TEST_ASSERT_FLOAT_WITHIN(.001, sqrt((600.0 * 600 - 1) / 12), F.roll_std_60);
  TEST_ASSERT_EQUAL_FLOAT(1, F.roll_diff_rms_60);
  TEST_ASSERT_EQUAL_FLOAT(1200, F.roll_mean_shift_180);
}
void test_raw_rms_offset_growth_is_not_centered(void) {
  constant(600, 1, 0);
  constant(600, 2, 0);
  constant(600, 3, 0);
  compute();
  TEST_ASSERT_EQUAL_FLOAT(0, F.roll_std_60);
  TEST_ASSERT_EQUAL_FLOAT(1, F.roll_rms_slope_180);
  TEST_ASSERT_EQUAL_FLOAT(1, F.roll_rms_trend_r2_180);
  TEST_ASSERT_EQUAL_FLOAT(2, F.roll_mean_shift_180);
  TEST_ASSERT_FLOAT_WITHIN(1e-6, sqrt(2.0 / 3), F.roll_segment_mean_std_180);
}
void test_c02_ratio_epsilon_and_large_finite_ratio(void) {
  svmg_window_clear(&W);
  for (int i = 0; i < 600; i++)
    push(1e-9f, 0); /* float representation is at or below the double threshold. */
  constant(600, 0.5f, 0);
  constant(600, 1.0f, 0);
  compute();
  TEST_ASSERT_TRUE(isnan(F.roll_rms_ratio_180));

  svmg_window_clear(&W);
  float above = nextafterf(1e-9f, INFINITY);
  for (int i = 0; i < 600; i++)
    push(above, 0);
  constant(600, 0.5f, 0);
  constant(600, 1.0f, 0);
  compute();
  TEST_ASSERT_TRUE(isfinite(F.roll_rms_ratio_180));
  TEST_ASSERT_TRUE(F.roll_rms_ratio_180 > 1e8f);
}
void test_undefined_zero_and_flat_trend_are_nan(void) {
  constant(1800, 0, 0);
  compute();
  TEST_ASSERT_TRUE(isnan(F.roll_rms_ratio_180));
  TEST_ASSERT_TRUE(isnan(F.roll_dominant_sign_ratio_180));
  TEST_ASSERT_TRUE(isnan(F.roll_rms_trend_r2_180));
  TEST_ASSERT_FALSE(svmg_features_vector_valid(&F));
  TEST_ASSERT_EQUAL_INT(
      SVMG_ST_OK,
      svmg_features_status(&F, &Q, 0)); /* valid sensor, invalid RF vector */
  constant(1800, 5, 2);
  compute();
  TEST_ASSERT_EQUAL_FLOAT(1, F.roll_rms_ratio_180);
  TEST_ASSERT_TRUE(isnan(F.roll_rms_trend_r2_180));
}
void test_cold_start_and_update_cadence(void) {
  int due = 0;
  for (int i = 0; i < 1799; i++)
    due += svmg_window_push(&W, 1, 1, 2, 1);
  compute();
  TEST_ASSERT_EQUAL_INT(17, due);
  TEST_ASSERT_FALSE(F.ready_long);
  TEST_ASSERT_TRUE(isnan(F.roll_mean_180));
  TEST_ASSERT_EQUAL_INT(SVMG_ST_UNKNOWN, svmg_features_status(&F, &Q, 0));
  TEST_ASSERT_EQUAL_INT(1, svmg_window_push(&W, 2, 1, 2, 1));
  compute();
  TEST_ASSERT_TRUE(F.ready_long);
}
void test_missing_does_not_bridge_differences(void) {
  for (int i = 0; i < 1800; i++)
    push((float)(i % 7), 0);
  /* Last 600: remove 15 isolated points, leaving 569 adjacent pairs => invalid
   * diff but valid moments. */
  for (int j = 0; j < 15; j++) {
    int i = 1201 + j * 30;
    W.roll_deg[i] = NAN;
  }
  compute();
  TEST_ASSERT_TRUE(isfinite(F.roll_rms_60));
  TEST_ASSERT_TRUE(isnan(F.roll_diff_rms_60));
}
void test_coverage_threshold_per_block(void) {
  for (int block = 0; block < 3; block++) {
    svmg_window_clear(&W);
    constant(1800, 2, 0);
    for (int i = block * 600; i < block * 600 + 31; i++)
      W.roll_deg[i] = NAN; /* 569/600 in one block; 1769/1800 overall. */
    compute();
    TEST_ASSERT_TRUE(isfinite(F.roll_mean_180));
    const float block_features[] = {F.roll_segment_mean_std_180, F.roll_mean_shift_180,
      F.roll_rms_early_60, F.roll_rms_late_60, F.roll_rms_ratio_180, F.roll_rms_slope_180,
      F.roll_rms_trend_r2_180, F.roll_p95_trend_slope_180};
    for (int i = 0; i < 8; i++) TEST_ASSERT_TRUE(isnan(block_features[i]));
    TEST_ASSERT_FALSE(svmg_features_vector_valid(&F));
  }
}
void test_quality_and_fault_wall_time(void) {
  constant(1700, 1, 1);
  for (int i = 0; i < 99; i++)
    svmg_window_push(&W, NAN, NAN, 0, 0);
  push(1, 1);
  compute();
  TEST_ASSERT_EQUAL_INT(SVMG_ST_UNKNOWN, svmg_features_status(&F, &Q, 0));
  for (int i = 0; i < 100; i++)
    svmg_window_push(&W, NAN, NAN, 0, 0);
  compute();
  TEST_ASSERT_EQUAL_INT(SVMG_ST_FAULT, svmg_features_status(&F, &Q, 0));
}
void test_quality_95_boundary_and_raw_loss(void) {
  for (int i = 0; i < 1800; i++)
    svmg_window_push(&W, 1, 1, (i % 20 == 0) ? 1 : 2, 1);
  compute();
  TEST_ASSERT_FLOAT_WITHIN(.01, 97.5, F.data_quality_pct);
  TEST_ASSERT_EQUAL_INT(SVMG_ST_OK, svmg_features_status(&F, &Q, 0));
  for (int i = 0; i < 1800; i++)
    svmg_window_push(&W, 1, 1, (i % 5 == 0) ? 1 : 2, 1);
  compute();
  TEST_ASSERT_EQUAL_INT(SVMG_ST_UNKNOWN, svmg_features_status(&F, &Q, 0));
}
void test_ring_wrap_shift_and_flat_api(void) {
  for (int i = 0; i < 5400; i++)
    push((float)(i % 1800), 2);
  compute();
  float before = F.roll_mean_180;
  svmg_window_shift(&W, -3, -2);
  compute();
  TEST_ASSERT_FLOAT_WITHIN(.001, before - 3, F.roll_mean_180);
  TEST_ASSERT_EQUAL_FLOAT(0, F.mean_pitch);
  static float r[1800], p[1800], v[23];
  for (int i = 0; i < 1800; i++) {
    r[i] = (float)(i / 600 + 1) * (i % 2 ? 1 : -1);
    p[i] = 0;
  }
  TEST_ASSERT_EQUAL_INT(SVMG_ST_OK,
                        svmg_features_from_series(r, p, 0, 1800, v));
  TEST_ASSERT_EQUAL_FLOAT(3, v[0]);
  TEST_ASSERT_EQUAL_FLOAT(1, v[17]);
}
void test_nan_inf_and_empty_arguments(void) {
  static float r[1800], p[1800], v[23];
  for (int i = 0; i < 1800; i++) {
    r[i] = (float)(i % 13);
    p[i] = 0;
  }
  r[1799] = INFINITY;
  svmg_features_from_series(r, p, 0, 1800, v);
  TEST_ASSERT_TRUE(isfinite(v[0]));
  TEST_ASSERT_EQUAL_INT(SVMG_ST_UNKNOWN,
                        svmg_features_from_series(0, p, 0, 0, v));
  for (int i = 0; i < 23; i++)
    TEST_ASSERT_TRUE(isnan(v[i]));
}
void test_workspace_is_bounded_and_ring_preserved(void) {
  TEST_ASSERT_TRUE(sizeof W < 26000);
  constant(1800, 3, 2);
  compute();
  for (int i = 0; i < 1800; i++) {
    TEST_ASSERT_EQUAL_FLOAT(3, W.roll_deg[i]);
    TEST_ASSERT_EQUAL_FLOAT(2, W.pitch_deg[i]);
  }
}
int main(void) {
  UNITY_BEGIN();
  RUN_TEST(test_schema_order_and_dimension);
  RUN_TEST(test_three_blocks_analytic_values);
  RUN_TEST(test_ramp_quantiles_population_and_difference);
  RUN_TEST(test_raw_rms_offset_growth_is_not_centered);
  RUN_TEST(test_c02_ratio_epsilon_and_large_finite_ratio);
  RUN_TEST(test_undefined_zero_and_flat_trend_are_nan);
  RUN_TEST(test_cold_start_and_update_cadence);
  RUN_TEST(test_missing_does_not_bridge_differences);
  RUN_TEST(test_coverage_threshold_per_block);
  RUN_TEST(test_quality_and_fault_wall_time);
  RUN_TEST(test_quality_95_boundary_and_raw_loss);
  RUN_TEST(test_ring_wrap_shift_and_flat_api);
  RUN_TEST(test_nan_inf_and_empty_arguments);
  RUN_TEST(test_workspace_is_bounded_and_ring_preserved);
  return UNITY_END();
}
