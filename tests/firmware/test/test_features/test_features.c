/* Test đơn vị M1-03 (features.c). Đáp án tính tay, ghi chú cạnh từng ca. */
#include <unity.h>
#include <math.h>
#include <stdio.h>
#include "svmg_features.h"
#include "svmg_testutil.h"

void setUp(void) {}
void tearDown(void) {}

static svmg_window_t W;
static svmg_features_t F;
#define PI_ 3.141592653589793

typedef double (*sigfn)(int i);
static void feed(int n, sigfn roll, sigfn gx) {
  for (int i = 0; i < n; i++) svmg_window_push(&W, (float)roll(i), gx ? (float)gx(i) : 0.0f, 0.0f, 1);
}
static double sig_zero(int i) { (void)i; return 0.0; }
static double sig_five(int i) { (void)i; return 5.0; }
static double sig_sin10(int i) { return 10.0 * sin(2 * PI_ * i / 40.0); }          /* T = 20 s */
static double sig_off_sin4(int i) { return 5.0 + 4.0 * sin(2 * PI_ * i / 40.0); }
/* T = 15 s: mỗi đoạn 30 s chứa đúng 2 chu kỳ nên RMS đoạn không phụ thuộc pha */
static double sig_ramp(int i) { double t = i / 2.0; return (2.0 + 6.0 * t / 180.0) * sin(2 * PI_ * i / 30.0); }
static double sig_gx3(int i) { (void)i; return 3.0; }

static void fresh(void) { svmg_window_clear(&W); }

void test_cold_start_boundaries(void) {
  fresh(); svmg_quality_cfg_t q; svmg_quality_default(&q); uint8_t why;
  feed(119, sig_zero, NULL); svmg_features_compute(&W, &F);
  TEST_ASSERT_FALSE(F.ready_short); TEST_ASSERT_FALSE(F.ready_long);
  TEST_ASSERT_EQUAL_INT(SVMG_ST_UNKNOWN, svmg_features_status(&F, &q, &why)); TEST_ASSERT_BITS_HIGH(SVMG_Q_COLD, why);
  feed(1, sig_zero, NULL); svmg_features_compute(&W, &F);
  TEST_ASSERT_TRUE(F.ready_short); TEST_ASSERT_FALSE(F.ready_long);
  feed(239, sig_zero, NULL); svmg_features_compute(&W, &F);
  TEST_ASSERT_FALSE(F.ready_long);
  TEST_ASSERT_EQUAL_INT(SVMG_ST_UNKNOWN, svmg_features_status(&F, &q, &why));
  feed(1, sig_zero, NULL); svmg_features_compute(&W, &F);
  TEST_ASSERT_TRUE(F.ready_long);
  TEST_ASSERT_EQUAL_INT(SVMG_ST_OK, svmg_features_status(&F, &q, &why)); TEST_ASSERT_EQUAL_UINT8(0, why);
}
void test_update_cadence_every_10_samples(void) {
  fresh(); int due = 0;
  for (int i = 0; i < 100; i++) due += svmg_window_push(&W, 0, 0, 0, 1);
  TEST_ASSERT_EQUAL_INT(10, due);
}
void test_constant_zero(void) {
  fresh(); feed(360, sig_zero, NULL); svmg_features_compute(&W, &F);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0, F.rms_roll_deg); TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0, F.p2p_deg);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0, F.mean_roll_deg); TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0, F.trend_rms_deg_per_min);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0, F.zero_cross_period_s); TEST_ASSERT_FLOAT_WITHIN(1e-6f, 1.0f, F.rms_ratio);
}
void test_constant_offset_5deg(void) {
  fresh(); feed(360, sig_five, NULL); svmg_features_compute(&W, &F);
  TEST_ASSERT_FLOAT_WITHIN(1e-4f, 5.0f, F.mean_roll_deg);
  TEST_ASSERT_FLOAT_WITHIN(1e-4f, 0.0f, F.rms_roll_deg);        /* dao động = 0 */
  TEST_ASSERT_FLOAT_WITHIN(1e-4f, 5.0f, F.rms_roll_abs_deg);    /* RMS quanh 0 = 5 */
  TEST_ASSERT_FLOAT_WITHIN(1e-4f, 5.0f, F.p95_abs_deg);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 1.0f, F.same_sign_ratio);
  TEST_ASSERT_FLOAT_WITHIN(1e-4f, 0.0f, F.p2p_deg);
}
void test_sine_10deg_T20(void) {
  fresh(); feed(360, sig_sin10, NULL); svmg_features_compute(&W, &F);
  TEST_ASSERT_FLOAT_WITHIN(0.005f, 7.0711f, F.rms_roll_deg);        /* A / sqrt2 */
  TEST_ASSERT_FLOAT_WITHIN(0.005f, 7.0711f, F.rms_roll_abs_deg);
  TEST_ASSERT_FLOAT_WITHIN(0.005f, 20.0f, F.p2p_deg);               /* mẫu rơi đúng đỉnh (k = 10) */
  TEST_ASSERT_FLOAT_WITHIN(0.005f, 9.8769f, F.p95_abs_deg);         /* hạng 114/120 của |sin|: 10 sin(9 pi / 20) */
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.0f, F.mean_roll_deg);
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.5f, F.same_sign_ratio);
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 20.0f, F.zero_cross_period_s);    /* 2 x khoảng cách giữa các lần cắt không */
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.0f, F.trend_rms_deg_per_min);
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 1.0f, F.rms_ratio);
  /* nhiễu nền đo bằng sai phân bậc 2 rò rỉ từ tín hiệu: 10 (2 pi / 40)^2 / sqrt2 / sqrt6 = 0.0712 */
  TEST_ASSERT_FLOAT_WITHIN(0.004f, 0.0712f, F.noise_floor_deg);
}
void test_offset_plus_oscillation_separated(void) {
  fresh(); feed(360, sig_off_sin4, NULL); svmg_features_compute(&W, &F);
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 5.0f, F.mean_roll_deg);
  TEST_ASSERT_FLOAT_WITHIN(0.005f, 2.8284f, F.rms_roll_deg);        /* 4/sqrt2: tách khỏi độ lệch */
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 20.0f, F.zero_cross_period_s);    /* cắt quanh trung bình */
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 1.0f, F.same_sign_ratio);         /* luôn dương */
}
void test_growing_amplitude_trend_and_ratio(void) {
  fresh(); feed(360, sig_ramp, NULL); svmg_features_compute(&W, &F);
  /* A(t) = 2 + t/30: RMS đoạn s ~ (2.5 + s)/sqrt2 -> dốc 0.7071 deg/đoạn 30 s = 1.4142 deg/phút */
  TEST_ASSERT_FLOAT_WITHIN(0.06f, 1.4142f, F.trend_rms_deg_per_min);
  /* RMS(60 s cuối) = sqrt(49.33/2) = 4.967; RMS(60 s đầu) = sqrt(9.33/2) = 2.160 -> 2.299 */
  TEST_ASSERT_FLOAT_WITHIN(0.06f, 2.299f, F.rms_ratio);
}
void test_gyro_rms(void) {
  fresh(); feed(120, sig_zero, sig_gx3); svmg_features_compute(&W, &F);
  TEST_ASSERT_FLOAT_WITHIN(1e-4f, 3.0f, F.rms_gyro_x_dps); TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0.0f, F.rms_gyro_y_dps);
}
void test_white_noise_floor(void) {
  fresh(); uint32_t seed = 12345;
  for (int i = 0; i < 360; i++) svmg_window_push(&W, (float)(0.05 * st_gauss(&seed)), 0, 0, 1);
  svmg_features_compute(&W, &F);
  TEST_ASSERT_FLOAT_WITHIN(0.012f, 0.05f, F.noise_floor_deg);
  TEST_ASSERT_FLOAT_WITHIN(0.015f, 0.05f, F.rms_roll_deg);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0.0f, F.zero_cross_period_s);     /* sigma = 3x nhỏ hơn trễ 0.15 deg: không coi là dao động */
}
void test_missing_quarter_is_unknown(void) {
  fresh(); svmg_quality_cfg_t q; svmg_quality_default(&q); uint8_t why;
  for (int i = 0; i < 360; i++) svmg_window_push(&W, 1.0f, 0, 0, (i % 4) != 3);
  svmg_features_compute(&W, &F);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0.25f, F.missing_ratio_180); TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0.25f, F.missing_ratio_60);
  TEST_ASSERT_EQUAL_INT(SVMG_ST_UNKNOWN, svmg_features_status(&F, &q, &why)); TEST_ASSERT_BITS_HIGH(SVMG_Q_MISSING, why);
  TEST_ASSERT_FLOAT_WITHIN(1e-5f, 1.0f, F.mean_roll_deg);           /* thống kê chỉ trên mẫu hợp lệ */
}
void test_consecutive_invalid_fault_threshold(void) {
  svmg_quality_cfg_t q; svmg_quality_default(&q); uint8_t why;
  fresh(); feed(340, sig_zero, NULL);
  for (int i = 0; i < 19; i++) svmg_window_push(&W, 0, 0, 0, 0);
  svmg_window_push(&W, 0, 0, 0, 1);                                  /* 19 thiếu rồi hợp lệ trở lại */
  svmg_features_compute(&W, &F);
  TEST_ASSERT_EQUAL_INT(SVMG_ST_OK, svmg_features_status(&F, &q, &why));
  fresh(); feed(340, sig_zero, NULL);
  for (int i = 0; i < 20; i++) svmg_window_push(&W, 0, 0, 0, 0);     /* đúng 20 liên tiếp = 10 s */
  svmg_features_compute(&W, &F);
  TEST_ASSERT_EQUAL_INT(SVMG_ST_FAULT, svmg_features_status(&F, &q, &why)); TEST_ASSERT_BITS_HIGH(SVMG_Q_FAULT_RUN, why);
}
void test_fault_by_ratio_without_long_run(void) {
  svmg_quality_cfg_t q; svmg_quality_default(&q); uint8_t why;
  fresh(); feed(240, sig_zero, NULL);
  for (int i = 0; i < 120; i++) svmg_window_push(&W, 0, 0, 0, (i % 10) < 4);   /* 60% thiếu, chuỗi dài nhất 6 */
  svmg_features_compute(&W, &F);
  TEST_ASSERT_EQUAL_INT(SVMG_ST_FAULT, svmg_features_status(&F, &q, &why)); TEST_ASSERT_BITS_HIGH(SVMG_Q_FAULT_RATIO, why);
}
void test_all_invalid_never_ok(void) {
  svmg_quality_cfg_t q; svmg_quality_default(&q);
  fresh();
  for (int i = 0; i < 400; i++) svmg_window_push(&W, 0, 0, 0, 0);
  svmg_features_compute(&W, &F);
  TEST_ASSERT_EQUAL_INT(SVMG_ST_FAULT, svmg_features_status(&F, &q, NULL));
  TEST_ASSERT_EQUAL_UINT16(0, F.n_valid_180);
}
void test_nan_input_is_missing(void) {
  fresh(); svmg_window_push(&W, NAN, 0, 0, 1); svmg_window_push(&W, 1, INFINITY, 0, 1);
  svmg_features_compute(&W, &F);
  TEST_ASSERT_EQUAL_UINT16(0, F.n_valid_60); TEST_ASSERT_EQUAL_UINT16(2, F.consec_invalid);
}
void test_shift_roll_for_calibration(void) {
  fresh(); feed(360, sig_five, NULL);
  svmg_window_shift_roll(&W, -5.0f); svmg_features_compute(&W, &F);
  TEST_ASSERT_FLOAT_WITHIN(1e-4f, 0.0f, F.mean_roll_deg);
}
void test_feature_vector_order(void) {
  fresh(); feed(360, sig_off_sin4, sig_gx3); svmg_features_compute(&W, &F);
  float v[SVMG_N_FEATURES]; svmg_features_to_vector(&F, v);
  TEST_ASSERT_EQUAL_FLOAT(F.rms_roll_deg, v[0]); TEST_ASSERT_EQUAL_FLOAT(F.p2p_deg, v[1]);
  TEST_ASSERT_EQUAL_FLOAT(F.p95_abs_deg, v[2]); TEST_ASSERT_EQUAL_FLOAT(F.rms_gyro_x_dps, v[3]);
  TEST_ASSERT_EQUAL_FLOAT(F.rms_gyro_y_dps, v[4]); TEST_ASSERT_EQUAL_FLOAT(F.mean_roll_deg, v[5]);
  TEST_ASSERT_EQUAL_FLOAT(F.same_sign_ratio, v[6]); TEST_ASSERT_EQUAL_FLOAT(F.trend_rms_deg_per_min, v[7]);
  TEST_ASSERT_EQUAL_FLOAT(F.rms_ratio, v[8]); TEST_ASSERT_EQUAL_FLOAT(F.zero_cross_period_s, v[9]);
  TEST_ASSERT_EQUAL_STRING("zero_cross_period", SVMG_FEATURE_NAMES[9]);
}
void test_ring_wraparound_consistency(void) {
  /* Cùng tín hiệu nhưng đẩy qua nhiều vòng đệm: đặc trưng phải như nhau. */
  fresh(); feed(360, sig_sin10, NULL); svmg_features_compute(&W, &F); svmg_features_t a = F;
  fresh(); feed(360 * 7, sig_sin10, NULL); svmg_features_compute(&W, &F);
  TEST_ASSERT_FLOAT_WITHIN(1e-3f, a.rms_roll_deg, F.rms_roll_deg);
  TEST_ASSERT_FLOAT_WITHIN(1e-3f, a.p95_abs_deg, F.p95_abs_deg);
  TEST_ASSERT_FLOAT_WITHIN(1e-2f, a.zero_cross_period_s, F.zero_cross_period_s);
}
void test_sizeof_window(void) {
  char m[96]; snprintf(m, sizeof m, "sizeof(svmg_window_t)=%u sizeof(svmg_features_t)=%u", (unsigned)sizeof(svmg_window_t), (unsigned)sizeof(svmg_features_t)); TEST_MESSAGE(m);
  TEST_ASSERT_TRUE(sizeof(svmg_window_t) < 3200);
}

int main(void) {
  UNITY_BEGIN();
  RUN_TEST(test_cold_start_boundaries); RUN_TEST(test_update_cadence_every_10_samples);
  RUN_TEST(test_constant_zero); RUN_TEST(test_constant_offset_5deg); RUN_TEST(test_sine_10deg_T20);
  RUN_TEST(test_offset_plus_oscillation_separated); RUN_TEST(test_growing_amplitude_trend_and_ratio);
  RUN_TEST(test_gyro_rms); RUN_TEST(test_white_noise_floor);
  RUN_TEST(test_missing_quarter_is_unknown); RUN_TEST(test_consecutive_invalid_fault_threshold);
  RUN_TEST(test_fault_by_ratio_without_long_run); RUN_TEST(test_all_invalid_never_ok); RUN_TEST(test_nan_input_is_missing);
  RUN_TEST(test_shift_roll_for_calibration); RUN_TEST(test_feature_vector_order); RUN_TEST(test_ring_wraparound_consistency);
  RUN_TEST(test_sizeof_window);
  return UNITY_END();
}
