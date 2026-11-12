/* Test đơn vị M1-02 (filter.c). Đáp án tính tay / bằng tests/firmware/tools/ref_filter.py (độc lập, double). */
#include <unity.h>
#include <math.h>
#include <stdio.h>
#include "svmg_filter.h"
#include "svmg_testutil.h"

void setUp(void) {}
void tearDown(void) {}

#define G SVMG_G

/* ===== Nhóm I: quy đổi đơn vị ===== */
void test_I1_accel_1g(void) {
  svmg_imu_raw_t r = {0, 0, 16384, 0, 0, 0};
  svmg_motion_sample_t s;
  uint8_t f = svmg_imu_raw_to_si(&r, &s);
  TEST_ASSERT_FLOAT_WITHIN(1e-4f, 9.80665f, s.az);
  TEST_ASSERT_EQUAL_UINT8(0, f);
  TEST_ASSERT_EQUAL_UINT8(1, s.valid);
}
void test_I2_gyro_1dps(void) {
  svmg_imu_raw_t r = {0, 0, 0, 131, -131, 0};
  svmg_motion_sample_t s;
  svmg_imu_raw_to_si(&r, &s);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0.0174533f, s.gx);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, -0.0174533f, s.gy);
}
void test_I3_saturation(void) {
  svmg_imu_raw_t r = {0, 0, -32768, 0, 0, 0};
  svmg_motion_sample_t s;
  uint8_t f = svmg_imu_raw_to_si(&r, &s);
  TEST_ASSERT_FLOAT_WITHIN(1e-3f, -19.6133f, s.az);
  TEST_ASSERT_BITS_HIGH(SVMG_IMU_F_SATURATED, f);
}

/* ===== Nhóm A: gia tốc -> góc ===== */
void test_A_angles(void) {
  float r, p;
  svmg_accel_to_angles(0, 0, G, &r, &p);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0.0f, r); TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0.0f, p);
  svmg_accel_to_angles(0, 7, 7, &r, &p);            /* A2 */
  TEST_ASSERT_FLOAT_WITHIN(1e-5f, 0.785398f, r);
  svmg_accel_to_angles(-7, 0, 7, &r, &p);           /* A3 */
  TEST_ASSERT_FLOAT_WITHIN(1e-5f, 0.785398f, p);
  svmg_accel_to_angles(0, -4.903325f, 8.492809f, &r, &p);   /* A4: -30 deg */
  TEST_ASSERT_FLOAT_WITHIN(1e-5f, -0.523599f, r);
  svmg_accel_to_angles(0, G, 0, &r, &p);            /* A5 */
  TEST_ASSERT_FLOAT_WITHIN(1e-5f, 1.570796f, r);
}
void test_A6_gate(void) {
  TEST_ASSERT_EQUAL_UINT8(1, svmg_accel_gate_ok(0, 0, 1.0f * G));
  TEST_ASSERT_EQUAL_UINT8(0, svmg_accel_gate_ok(0, 0, 0.3f * G));
  TEST_ASSERT_EQUAL_UINT8(0, svmg_accel_gate_ok(0, 0, 0.0f));
  TEST_ASSERT_EQUAL_UINT8(0, svmg_accel_gate_ok(0, 0, 1.8f * G));
}

/* ===== Nhóm B: bộ lọc bù (tau = 0.95 s, dt = 0.05 s -> alpha = 0.95) ===== */
static void cf95(svmg_cf_t *cf) { svmg_cf_init(cf, 0.95f); }

void test_B1_first_sample_from_accel(void) {
  svmg_cf_t cf; cf95(&cf);
  uint8_t f = svmg_cf_update(&cf, 0, 7, 7, 5.0f /*gyro bị bỏ qua*/, 0, 0.05f);
  TEST_ASSERT_EQUAL_UINT8(0, f);
  TEST_ASSERT_FLOAT_WITHIN(1e-5f, 0.785398f, cf.roll);
}
void test_B2_step_response(void) {
  svmg_cf_t cf; cf95(&cf);
  svmg_cf_update(&cf, 0, 0, G, 0, 0, 0.05f);        /* khởi tạo 0 deg */
  const float exp_[3] = {0.03926991f, 0.07657632f, 0.50384398f};   /* pi/4 (1 - 0.95^n) */
  int checks[3] = {1, 2, 20}, ci = 0;
  for (int n = 1; n <= 20; n++) {
    svmg_cf_update(&cf, 0, 7, 7, 0, 0, 0.05f);
    if (n == checks[ci]) { TEST_ASSERT_FLOAT_WITHIN(1e-5f, exp_[ci], cf.roll); ci++; }
  }
  TEST_ASSERT_EQUAL_INT(3, ci);
}
void test_B3_tracking_constant_rate(void) {
  svmg_cf_t cf; cf95(&cf);
  const double rate = 0.1;
  double th = 0.0;
  svmg_cf_update(&cf, 0, 0, G, (float)rate, 0, 0.05f);
  for (int i = 1; i <= 200; i++) {
    th = rate * 0.05 * i;
    svmg_motion_sample_t s = st_sample(0, th, rate, 0, 0);
    svmg_cf_update(&cf, s.ax, s.ay, s.az, s.gx, s.gy, 0.05f);
    TEST_ASSERT_FLOAT_WITHIN(1e-5f, (float)th, cf.roll);
  }
}
void test_B4_gyro_bias_equilibrium(void) {
  svmg_cf_t cf; cf95(&cf);
  for (int i = 0; i < 400; i++) svmg_cf_update(&cf, 0, 0, G, 0.01f /*bias*/, 0, 0.05f);
  TEST_ASSERT_FLOAT_WITHIN(2e-4f, 0.0095f, cf.roll);      /* tau * bias = 0.95 * 0.01 */
}
void test_B5_gated_integrates_gyro_only(void) {
  svmg_cf_t cf; cf95(&cf);
  svmg_cf_update(&cf, 0, 0, G, 0, 0, 0.05f);              /* khởi tạo */
  uint8_t f = 0;
  for (int i = 0; i < 10; i++) f = svmg_cf_update(&cf, 0, 0, 0 /*|a| = 0 -> cổng chặn*/, 0.2f, 0, 0.05f);
  TEST_ASSERT_BITS_HIGH(SVMG_CF_GATED, f);
  TEST_ASSERT_FLOAT_WITHIN(1e-5f, 0.1f, cf.roll);         /* 10 * 0.2 * 0.05 */
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0.0f, cf.pitch);
}
void test_B6_alpha_follows_dt(void) {
  svmg_cf_t cf; svmg_cf_init(&cf, 0.9f);
  svmg_cf_update(&cf, 0, 0, G, 0, 0, 0.1f);
  svmg_cf_update(&cf, 0, 7, 7, 0, 0, 0.1f);               /* alpha = 0.9/(0.9+0.1) = 0.9 */
  TEST_ASSERT_FLOAT_WITHIN(1e-5f, 0.07853982f, cf.roll);
}
void test_B7_gated_first_sample_not_initialised(void) {
  svmg_cf_t cf; cf95(&cf);
  uint8_t f = svmg_cf_update(&cf, 0, 0, 0, 0, 0, 0.05f);
  TEST_ASSERT_BITS_HIGH(SVMG_CF_NOT_INIT, f);
  TEST_ASSERT_EQUAL_UINT8(0, cf.initialized);
}

/* ===== Nhóm C: biquad Butterworth fc = 0.5 Hz, fs = 20 Hz ===== */
void test_C1_coefficients(void) {
  svmg_biquad_coef_t c; svmg_biquad_butter2_lp(&c, 0.5f, 20.0f);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0.00554272f, c.b0);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0.01108543f, c.b1);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0.00554272f, c.b2);
  TEST_ASSERT_FLOAT_WITHIN(1e-5f, -1.77863178f, c.a1);
  TEST_ASSERT_FLOAT_WITHIN(1e-5f, 0.80080265f, c.a2);
}
void test_C2_steady_state_init_has_no_transient(void) {
  svmg_biquad_coef_t c; svmg_biquad_butter2_lp(&c, 0.5f, 20.0f);
  svmg_biquad_t f; svmg_biquad_init(&f, &c, 1.0f);
  /* b0 được ép để độ lợi DC = 1 theo a1,a2 đã làm tròn; sai số còn lại chỉ là làm tròn tích lũy (<2e-6). */
  for (int i = 0; i < 400; i++) TEST_ASSERT_FLOAT_WITHIN(2e-6f, 1.0f, svmg_biquad_step(&f, 1.0f));
  svmg_biquad_init(&f, &c, -3.5f);
  for (int i = 0; i < 400; i++) TEST_ASSERT_FLOAT_WITHIN(2.5e-5f, -3.5f, svmg_biquad_step(&f, -3.5f)); /* sai số tương đối <= 7e-6 */
}
void test_C3_step_from_zero_state(void) {
  svmg_biquad_coef_t c; svmg_biquad_butter2_lp(&c, 0.5f, 20.0f);
  svmg_biquad_t f; svmg_biquad_init(&f, &c, 0.0f);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0.00554272f, svmg_biquad_step(&f, 1.0f));
  TEST_ASSERT_FLOAT_WITHIN(1e-5f, 0.02648660f, svmg_biquad_step(&f, 1.0f));
  TEST_ASSERT_FLOAT_WITHIN(1e-5f, 0.06484216f, svmg_biquad_step(&f, 1.0f));
}

/* Biên độ (= sqrt2 * RMS) của tín hiệu sin f_hz sau biquad, đo trên số nguyên chu kỳ, bỏ 200 s đầu. */
static double tone_amp(double f_hz, int decimate_to_2hz, int use_filter) {
  svmg_biquad_coef_t c; svmg_biquad_butter2_lp(&c, 0.5f, 20.0f);
  svmg_biquad_t bq; svmg_biquad_init(&bq, &c, 0.0f);
  const int settle = 20 * 200;
  const int n_meas = 20 * 200;                      /* 200 s: số nguyên chu kỳ cho các tần số thử */
  double acc = 0; int cnt = 0;
  for (int n = 0; n < settle + n_meas; n++) {
    float x = (float)sin(2.0 * 3.141592653589793 * f_hz * n / 20.0);
    float y = use_filter ? svmg_biquad_step(&bq, x) : x;
    if (n >= settle && (!decimate_to_2hz || (n % 10) == 9)) { acc += (double)y * y; cnt++; }
  }
  return sqrt(2.0 * acc / cnt);
}
void test_C4_frequency_response(void) {
  TEST_ASSERT_FLOAT_WITHIN(0.002f, 0.99995f, (float)tone_amp(0.05, 0, 1));
  TEST_ASSERT_FLOAT_WITHIN(0.003f, 0.707107f, (float)tone_amp(0.5, 0, 1));
  TEST_ASSERT_FLOAT_WITHIN(0.003f, 0.106848f, (float)tone_amp(1.5, 0, 1));
  TEST_ASSERT_FLOAT_WITHIN(0.002f, 0.006194f, (float)tone_amp(5.0, 0, 1));
}

/* ===== Nhóm D: giảm mẫu ===== */
void test_D3_antialias_attenuates_1p5hz(void) {
  double with = tone_amp(1.5, 1, 1);      /* lọc + giảm mẫu 20->2 Hz */
  double without = tone_amp(1.5, 1, 0);   /* đối chứng: bỏ lọc phải bị alias nguyên biên độ */
  TEST_ASSERT_FLOAT_WITHIN(0.005f, 0.106848f, (float)with);
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 1.0f, (float)without);   /* test này sẽ FAIL nếu lỡ bỏ lọc */
}
void test_D4_slow_signal_preserved(void) {
  TEST_ASSERT_TRUE(tone_amp(0.05, 1, 1) > 0.99);
}

/* ===== Pipeline ===== */
static svmg_pipeline_t pp;
static void pipe_new(void) { svmg_pipeline_cfg_t c; svmg_pipeline_default_cfg(&c); svmg_pipeline_init(&pp, &c); }

void test_D1_D2_output_count_and_timestamps(void) {
  pipe_new();
  int outs = 0; float t_first = -1, t_second = -1;
  for (int i = 0; i < 200; i++) {
    svmg_motion_sample_t s = st_sample(0.05 * i, 0, 0, 0, 0);
    svmg_sample2hz_t o;
    if (svmg_pipeline_push(&pp, &s, &o)) { if (outs == 0) t_first = o.t_s; if (outs == 1) t_second = o.t_s; outs++; TEST_ASSERT_EQUAL_UINT8(10, o.n_valid); TEST_ASSERT_EQUAL_UINT8(0, o.flags); }
  }
  TEST_ASSERT_EQUAL_INT(20, outs);
  TEST_ASSERT_FLOAT_WITHIN(1e-4f, 0.45f, t_first);
  TEST_ASSERT_FLOAT_WITHIN(1e-4f, 0.95f, t_second);
  pipe_new(); outs = 0;
  for (int i = 0; i < 1000; i++) { svmg_motion_sample_t s = st_sample(0.05 * i, 0, 0, 0, 0); svmg_sample2hz_t o; outs += svmg_pipeline_push(&pp, &s, &o); }
  TEST_ASSERT_EQUAL_INT(100, outs);
}

/* Chạy tín hiệu roll xác định; trả về RMS roll [deg] của ngõ ra trong [t_from, t_to). */
static double run_roll(double amp_deg, double period_s, double bias_dps, double dur_s, double t_from, double t_to, double *pitch_max_deg, double *last_roll_deg, double *first_roll_deg) {
  pipe_new();
  double acc = 0; int cnt = 0; double pmax = 0; int first = 1;
  int n = (int)(dur_s * 20);
  for (int i = 0; i < n; i++) {
    double t = 0.05 * i, w = 2 * 3.141592653589793 / period_s;
    double roll = amp_deg * ST_D2R * sin(w * t), rate = amp_deg * ST_D2R * w * cos(w * t) + bias_dps * ST_D2R;
    svmg_motion_sample_t s = st_sample(t, roll, rate, 0, 0);
    svmg_sample2hz_t o;
    if (svmg_pipeline_push(&pp, &s, &o)) {
      double r = o.roll_rad * ST_R2D;
      if (first) { if (first_roll_deg) *first_roll_deg = r; first = 0; }
      if (last_roll_deg) *last_roll_deg = r;
      if (fabs(o.pitch_rad * ST_R2D) > pmax) pmax = fabs(o.pitch_rad * ST_R2D);
      if (o.t_s >= t_from && o.t_s < t_to) { acc += r * r; cnt++; }
    }
  }
  if (pitch_max_deg) *pitch_max_deg = pmax;
  return cnt ? sqrt(acc / cnt) : 0.0;
}

void test_E1_E3_ship_like_roll(void) {
  double pmax;
  double rms = run_roll(10.0, 20.0, 0.0, 200.0, 60.0, 180.0, &pmax, NULL, NULL);
  TEST_ASSERT_FLOAT_WITHIN(0.05f, 7.0707f, (float)rms);          /* 10/sqrt2 * |H(0.05 Hz)| */
  TEST_ASSERT_TRUE(pmax < 0.05);                                  /* E3 */
}
void test_E2_static_tilt_from_first_output(void) {
  /* amp=0 + tư thế tĩnh 5 deg: dùng run riêng. */
  pipe_new();
  svmg_sample2hz_t o; int got = 0;
  for (int i = 0; i < 10 && !got; i++) { svmg_motion_sample_t s = st_sample(0.05 * i, 5.0 * ST_D2R, 0, 0, 0); got = svmg_pipeline_push(&pp, &s, &o); }
  TEST_ASSERT_TRUE(got);
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 5.0f, (float)(o.roll_rad * ST_R2D));
}
void test_E4_gyro_bias_limit_documented(void) {
  double last;
  run_roll(0.0, 20.0, 0.1 /*deg/s*/, 200.0, 0, 0, NULL, &last, NULL);
  TEST_ASSERT_FLOAT_WITHIN(0.02f, 0.75f, (float)last);            /* tau*bias = 7.5 * 0.1: giới hạn đã biết */
}

void test_B8_invalid_and_nan_do_not_change_state(void) {
  pipe_new();
  svmg_sample2hz_t o; int got = 0;
  for (int i = 0; i < 10; i++) { svmg_motion_sample_t s = st_sample(0.05 * i, 0.1, 0, 0, 0); got = svmg_pipeline_push(&pp, &s, &o); }
  TEST_ASSERT_TRUE(got);
  float roll_before = o.roll_rad;
  for (int i = 10; i < 20; i++) {
    svmg_motion_sample_t s = st_sample(0.05 * i, 0.5, 0, 0, 0);
    if (i % 2 == 0) s.valid = 0; else s.ax = NAN;
    got = svmg_pipeline_push(&pp, &s, &o);
  }
  TEST_ASSERT_TRUE(got);
  TEST_ASSERT_EQUAL_UINT8(0, o.n_valid);
  TEST_ASSERT_BITS_HIGH(SVMG_PIPE_F_PARTIAL, o.flags);
  TEST_ASSERT_FLOAT_WITHIN(1e-6f, roll_before, o.roll_rad);        /* giữ giá trị cũ, không nhiễm NaN */
  TEST_ASSERT_EQUAL_UINT32(10, pp.cnt_invalid);
}
void test_dead_bus_zero_accel_is_not_valid_measurement(void) {
  pipe_new();
  svmg_sample2hz_t o; int got = 0;
  for (int i = 0; i < 10; i++) { svmg_motion_sample_t s = st_sample(0.05 * i, 0.1, 0, 0, 0); got = svmg_pipeline_push(&pp, &s, &o); }
  TEST_ASSERT_TRUE(got); TEST_ASSERT_EQUAL_UINT8(10, o.n_valid);
  for (int i = 10; i < 20; i++) { svmg_motion_sample_t s; memset(&s, 0, sizeof s); s.t = (float)(0.05 * i); s.valid = 1; got = svmg_pipeline_push(&pp, &s, &o); }
  TEST_ASSERT_TRUE(got);
  TEST_ASSERT_EQUAL_UINT8_MESSAGE(0, o.n_valid, "toàn 0 (valid=1) phải không được tính là phép đo hợp lệ");
  TEST_ASSERT_BITS_HIGH(SVMG_PIPE_F_GATED, o.flags);
  /* một cú xóc ngắn (3/10 mẫu bị cổng) vẫn là khối hợp lệ */
  for (int i = 20; i < 30; i++) { svmg_motion_sample_t s = st_sample(0.05 * i, 0.1, 0, 0, 0); if (i < 23) { s.ax = s.ay = s.az = 0; } got = svmg_pipeline_push(&pp, &s, &o); }
  TEST_ASSERT_TRUE(got); TEST_ASSERT_EQUAL_UINT8(7, o.n_valid);
}
void test_pipeline_partial_block(void) {
  pipe_new();
  svmg_sample2hz_t o; int got = 0;
  for (int i = 0; i < 10; i++) { svmg_motion_sample_t s = st_sample(0.05 * i, 0.1, 0, 0, 0); if (i < 3) s.valid = 0; got = svmg_pipeline_push(&pp, &s, &o); }
  TEST_ASSERT_TRUE(got);
  TEST_ASSERT_EQUAL_UINT8(7, o.n_valid);
  TEST_ASSERT_BITS_HIGH(SVMG_PIPE_F_PARTIAL, o.flags);
}
void test_B9_gap_restarts_filter(void) {
  pipe_new();
  svmg_sample2hz_t o; int got;
  for (int i = 0; i < 10; i++) { svmg_motion_sample_t s = st_sample(0.05 * i, 0.1, 0, 0, 0); svmg_pipeline_push(&pp, &s, &o); }
  /* khoảng trống 2 s, tư thế mới 0.3 rad */
  got = 0;
  for (int i = 0; i < 10; i++) { svmg_motion_sample_t s = st_sample(2.5 + 0.05 * i, 0.3, 0, 0, 0); got = svmg_pipeline_push(&pp, &s, &o); }
  TEST_ASSERT_TRUE(got);
  TEST_ASSERT_BITS_HIGH(SVMG_PIPE_F_RESTARTED, o.flags);
  TEST_ASSERT_EQUAL_UINT32(1, pp.cnt_gap);
  TEST_ASSERT_FLOAT_WITHIN(1e-4f, 0.3f, o.roll_rad);              /* khởi tạo lại từ gia tốc, không trôi từ giá trị cũ */
}
void test_time_going_backwards_restarts(void) {
  pipe_new();
  svmg_sample2hz_t o;
  for (int i = 0; i < 5; i++) { svmg_motion_sample_t s = st_sample(1.0 + 0.05 * i, 0.1, 0, 0, 0); svmg_pipeline_push(&pp, &s, &o); }
  svmg_motion_sample_t s = st_sample(0.0, 0.1, 0, 0, 0);
  svmg_pipeline_push(&pp, &s, &o);
  TEST_ASSERT_EQUAL_UINT32(1, pp.cnt_gap);
}
void test_clock_wrap_is_not_a_gap(void) {
  pipe_new();
  svmg_sample2hz_t o; int outs = 0;
  for (int i = 0; i < 20; i++) { svmg_motion_sample_t s = st_sample(8191.0 + 0.05 * i, 0.1, 0, 0, 0); outs += svmg_pipeline_push(&pp, &s, &o); }
  /* t quấn từ ~8192 về 0 giữa chừng */
  for (int i = 0; i < 20; i++) { svmg_motion_sample_t s = st_sample(0.05 * i, 0.1, 0, 0, 0); outs += svmg_pipeline_push(&pp, &s, &o); }
  TEST_ASSERT_EQUAL_UINT32_MESSAGE(0, pp.cnt_gap, "quấn vòng đồng hồ không được tính là khoảng trống");
  TEST_ASSERT_EQUAL_INT(4, outs);
}
void test_sizeof_pipeline_reported(void) {
  /* Ghi lại dung lượng RAM cho nhật ký; chặn phình to ngoài ý muốn. */
  TEST_MESSAGE("sizeof(svmg_pipeline_t) is reported below");
  char msg[64]; snprintf(msg, sizeof msg, "sizeof(svmg_pipeline_t)=%u", (unsigned)sizeof(svmg_pipeline_t)); TEST_MESSAGE(msg);
  TEST_ASSERT_TRUE(sizeof(svmg_pipeline_t) < 256);
}

int main(void) {
  UNITY_BEGIN();
  RUN_TEST(test_I1_accel_1g); RUN_TEST(test_I2_gyro_1dps); RUN_TEST(test_I3_saturation);
  RUN_TEST(test_A_angles); RUN_TEST(test_A6_gate);
  RUN_TEST(test_B1_first_sample_from_accel); RUN_TEST(test_B2_step_response); RUN_TEST(test_B3_tracking_constant_rate);
  RUN_TEST(test_B4_gyro_bias_equilibrium); RUN_TEST(test_B5_gated_integrates_gyro_only); RUN_TEST(test_B6_alpha_follows_dt);
  RUN_TEST(test_B7_gated_first_sample_not_initialised);
  RUN_TEST(test_C1_coefficients); RUN_TEST(test_C2_steady_state_init_has_no_transient); RUN_TEST(test_C3_step_from_zero_state);
  RUN_TEST(test_C4_frequency_response);
  RUN_TEST(test_D3_antialias_attenuates_1p5hz); RUN_TEST(test_D4_slow_signal_preserved);
  RUN_TEST(test_D1_D2_output_count_and_timestamps);
  RUN_TEST(test_E1_E3_ship_like_roll); RUN_TEST(test_E2_static_tilt_from_first_output); RUN_TEST(test_E4_gyro_bias_limit_documented);
  RUN_TEST(test_B8_invalid_and_nan_do_not_change_state); RUN_TEST(test_dead_bus_zero_accel_is_not_valid_measurement); RUN_TEST(test_pipeline_partial_block); RUN_TEST(test_B9_gap_restarts_filter);
  RUN_TEST(test_time_going_backwards_restarts); RUN_TEST(test_clock_wrap_is_not_a_gap); RUN_TEST(test_sizeof_pipeline_reported);
  return UNITY_END();
}
