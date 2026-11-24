/* Test M1-04: lớp ngưỡng cứng (safety.c), MAI (mai.c), Baseline B (baseline.c) trên 23 đặc trưng + hàm theo svmg_core.h. */
#include <unity.h>
#include <math.h>
#include <string.h>
#include "svmg_decision.h"
#include "svmg_contract.h"
#include "svmg_testutil.h"

void setUp(void) {}
void tearDown(void) {}
#define PI_ 3.141592653589793

/* ---------- Ngưỡng cứng (lấy mẫu 2 Hz: t = 0.5 i) ---------- */
void test_safety_clamps_phi(void) {
  TEST_ASSERT_EQUAL_FLOAT(25.0f, svmg_safety_clamp_phi(40.0f));    /* T10: đặt phi_hard = 40 */
  TEST_ASSERT_EQUAL_FLOAT(15.0f, svmg_safety_clamp_phi(5.0f));
  TEST_ASSERT_EQUAL_FLOAT(20.0f, svmg_safety_clamp_phi(NAN));
  TEST_ASSERT_EQUAL_FLOAT(18.0f, svmg_safety_clamp_phi(18.0f));
}
void test_safety_trips_after_5s_not_before(void) {
  svmg_safety_t s; svmg_safety_init(&s, 20.0f);
  int edges = 0, first_active_i = -1;
  for (int i = 0; i < 30; i++) {
    int e = svmg_safety_push(&s, 0.5f * i, 21.0f, 1);
    edges += e;
    if (s.active && first_active_i < 0) first_active_i = i;
  }
  TEST_ASSERT_EQUAL_INT(1, edges);                  /* cạnh lên đúng một lần */
  TEST_ASSERT_EQUAL_INT(10, first_active_i);        /* mẫu thứ 11 (t = 5.0 s), mẫu t = 4.5 s chưa */
}
void test_safety_below_threshold_never_trips(void) {
  svmg_safety_t s; svmg_safety_init(&s, 20.0f);
  for (int i = 0; i < 200; i++) TEST_ASSERT_EQUAL_INT(0, svmg_safety_push(&s, 0.5f * i, 19.9f, 1));
  TEST_ASSERT_FALSE(s.active);
}
void test_safety_negative_roll_and_exact_threshold(void) {
  svmg_safety_t s; svmg_safety_init(&s, 20.0f);
  for (int i = 0; i < 12; i++) svmg_safety_push(&s, 0.5f * i, -20.0f, 1);   /* |roll| >= 20 (bằng) */
  TEST_ASSERT_TRUE(s.active);
}
void test_safety_dip_resets_counter(void) {
  svmg_safety_t s; svmg_safety_init(&s, 20.0f);
  for (int i = 0; i < 9; i++) svmg_safety_push(&s, 0.5f * i, 25.0f, 1);     /* 4 s */
  svmg_safety_push(&s, 4.5f, 5.0f, 1);                                      /* tụt xuống */
  for (int i = 10; i < 19; i++) svmg_safety_push(&s, 0.5f * i, 25.0f, 1);   /* 4 s nữa */
  TEST_ASSERT_FALSE(s.active);
}
void test_safety_invalid_sample_holds_state(void) {
  svmg_safety_t s; svmg_safety_init(&s, 20.0f);
  for (int i = 0; i < 6; i++) svmg_safety_push(&s, 0.5f * i, 25.0f, 1);
  svmg_safety_push(&s, 3.0f, 0.0f, 0);              /* mẫu thiếu với roll = 0: không được coi là hạ xuống */
  for (int i = 7; i < 12; i++) svmg_safety_push(&s, 0.5f * i, 25.0f, 1);
  TEST_ASSERT_TRUE(s.active);
}
void test_safety_active_clears_when_roll_drops(void) {
  svmg_safety_t s; svmg_safety_init(&s, 20.0f);
  for (int i = 0; i < 12; i++) svmg_safety_push(&s, 0.5f * i, 25.0f, 1);
  TEST_ASSERT_TRUE(s.active);
  svmg_safety_push(&s, 6.0f, 10.0f, 1);
  TEST_ASSERT_FALSE(s.active);
}
void test_safety_set_phi_clamped_runtime(void) {
  svmg_safety_t s; svmg_safety_init(&s, 20.0f);
  svmg_safety_set_phi(&s, 90.0f);
  TEST_ASSERT_EQUAL_FLOAT(25.0f, s.phi_hard_deg);
}
void test_checkSafetyEnvelope_contract_api(void) {
  int first = -1;
  for (int i = 1; i <= 30; i++) if (checkSafetyEnvelope(24.0f, 0.5f) && first < 0) first = i;
  TEST_ASSERT_EQUAL_INT(11, first);                 /* t = 0.5 i: lần gọi thứ 11 ứng với dwell đúng 5,0 s */
  TEST_ASSERT_FALSE(checkSafetyEnvelope(0.0f, 0.5f));
}

/* ---------- MAI ---------- */
static svmg_features_t feat(float rms, float mean, float trend) {
  svmg_features_t f; memset(&f, 0, sizeof f);
  f.roll_rms_60=rms; f.roll_mean_180=mean; f.roll_rms_slope_180=trend; f.rms_roll = rms; f.energy_roll = rms * rms; f.mean_roll = mean; f.trend_rms_slope = trend; f.sensor_ok = 1.0f;
  return f;
}
void test_mai_components(void) {
  svmg_mai_params_t p = {8.0f, 5.0f, 2.0f}; svmg_mai_t m;
  svmg_features_t f = feat(4.0f, 0, 0);  svmg_mai_compute(&p, &f, &m);         /* 4/8 = 0.5 */
  TEST_ASSERT_EQUAL_UINT8(50, m.value); TEST_ASSERT_EQUAL_UINT8(0, m.dominant);
  f = feat(1.0f, -4.0f, 0);              svmg_mai_compute(&p, &f, &m);         /* |-4|/5 = 0.8 */
  TEST_ASSERT_EQUAL_UINT8(80, m.value); TEST_ASSERT_EQUAL_UINT8(1, m.dominant);
  f = feat(1.0f, 0, 1.0f);               svmg_mai_compute(&p, &f, &m);         /* 1/2 = 0.5 */
  TEST_ASSERT_EQUAL_UINT8(50, m.value); TEST_ASSERT_EQUAL_UINT8(2, m.dominant);
  f = feat(1.0f, 0, 3.0f);               svmg_mai_compute(&p, &f, &m);         /* 1.5 -> kẹp 100 */
  TEST_ASSERT_EQUAL_UINT8(100, m.value);
  f = feat(0, 0, -5.0f);                 svmg_mai_compute(&p, &f, &m);         /* xu hướng giảm không tính */
  TEST_ASSERT_EQUAL_UINT8(0, m.value);
}
void test_mai_nan_is_zero_not_crash(void) {
  svmg_mai_params_t p = {8.0f, 5.0f, 2.0f}; svmg_mai_t m; svmg_features_t f = feat(NAN, NAN, NAN);
  svmg_mai_compute(&p, &f, &m);
  TEST_ASSERT_TRUE(m.value <= 100);
}

/* ---------- Baseline B trên tín hiệu thật qua cửa sổ 23 đặc trưng ---------- */
static svmg_window_t W; static svmg_features_t F; static svmg_baseline_params_t BP;
typedef double (*sigfn)(int i);
static void run(sigfn fn) {
  svmg_window_clear(&W);
  for (int i = 0; i < 1800; i++) svmg_window_push(&W, (float)fn(i/5), 0.0f, 2, 1);
  svmg_features_compute(&W, &F); svmg_baseline_default(&BP);
}
static double s_normal(int i) { return 4.0 * sin(2 * PI_ * i / 40.0); }             /* rms 2.8 */
static double s_high(int i) { return 12.0 * sin(2 * PI_ * i / 40.0); }              /* rms 8.5 */
static double s_off(int i) { return 4.0 + 1.0 * sin(2 * PI_ * i / 40.0); }          /* S2: lệch 4, dao động nhỏ -> không cắt 0 */
static double s_off_big(int i) { return 8.0 + 0.5 * sin(2 * PI_ * i / 40.0); }      /* S2 lệch lớn: rms 8 >= 6 nhưng không dao động quanh 0 */
static double s_s0b(int i) { return (i >= 150 && i < 330) ? 5.0 : 0.0; }            /* nghiêng tạm 90 s rồi về 0 (đã kết thúc) */
static double s_s0b_live(int i) { return (i >= 180) ? 5.0 : 0.0; }                  /* đang nghiêng tạm 90 s (chưa kết thúc) */
static double s_heel_waves(int i) { return 4.0 * sin(2 * PI_ * i / 40.0) + (i >= 240 ? 5.0 : 0.0); }
static double s_grow(int i) { return (2.0 + 6.0 * (i / 2.0) / 180.0) * sin(2 * PI_ * i / 30.0); }
static double s_h1(int i) { return 4.0 + 10.0 * sin(2 * PI_ * i / 40.0); }          /* lệch + sóng lớn */

void test_baseline_normal(void) { run(s_normal); TEST_ASSERT_EQUAL_INT(SVMG_NORMAL, svmg_baseline_b(&BP, &F)); }
void test_baseline_high_roll(void) { run(s_high); TEST_ASSERT_EQUAL_INT(SVMG_HIGH_ROLL, svmg_baseline_b(&BP, &F)); }
void test_baseline_offset(void) { run(s_off); TEST_ASSERT_EQUAL_INT(SVMG_PERSISTENT_OFFSET, svmg_baseline_b(&BP, &F)); }
void test_baseline_large_offset_is_not_high_roll(void) {
  run(s_off_big);
  TEST_ASSERT_TRUE_MESSAGE(F.rms_roll >= 6.0f, "tiền điều kiện: RMS quanh 0 (>= 6) sẽ làm S2 bị nhầm thành HIGH_ROLL");
  TEST_ASSERT_TRUE(svmg_baseline_dyn_rms(&F) < 1.0f);                                  /* biên độ dao động thật chỉ ~0,35 deg */
  TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_PERSISTENT_OFFSET, svmg_baseline_b(&BP, &F), "lệch lớn ít dao động là OFFSET, không phải HIGH_ROLL");
}
void test_baseline_heel_plus_moderate_waves_is_not_high_roll(void) {
  run(s_heel_waves);                                    /* nghiêng 5 deg trong 60 s cuối + sóng 4 deg: rms quanh 0 ~ 6 */
  TEST_ASSERT_TRUE_MESSAGE(F.rms_roll >= 5.5f, "tiền điều kiện: rms quanh 0 sát/lớn hơn 6");
  TEST_ASSERT_TRUE_MESSAGE(svmg_baseline_dyn_rms(&F) < 4.5f, "biên độ dao động ước lượng phải gần 4/sqrt2 ~ 2,8 deg");
  TEST_ASSERT_EQUAL_INT(SVMG_NORMAL, svmg_baseline_b(&BP, &F));
}
void test_baseline_temporary_heel_S0b_is_normal(void) {
  run(s_s0b);      TEST_ASSERT_EQUAL_INT(SVMG_NORMAL, svmg_baseline_b(&BP, &F));
  run(s_s0b_live); TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_NORMAL, svmg_baseline_b(&BP, &F), "đang nghiêng tạm 90 s (< T_off = 120 s) chưa phải OFFSET");
}
void test_baseline_growth(void) { run(s_grow); TEST_ASSERT_EQUAL_INT(SVMG_AMPLITUDE_GROWTH, svmg_baseline_b(&BP, &F)); }
void test_baseline_combined_case_prefers_high_roll(void) { run(s_h1); TEST_ASSERT_EQUAL_INT(SVMG_HIGH_ROLL, svmg_baseline_b(&BP, &F)); }
void test_baseline_priority_with_manual_features(void){
  svmg_baseline_params_t p;svmg_baseline_default(&p);
  svmg_features_t f={0};
  f.roll_std_60=9;f.roll_mean_60=4;f.roll_mean_180=4;f.roll_rms_slope_180=3;f.roll_dominant_sign_ratio_180=1;
  TEST_ASSERT_EQUAL_INT(SVMG_HIGH_ROLL,svmg_baseline_b(&p,&f));
  f.roll_std_60=4.5f;f.roll_mean_60=0;f.roll_mean_180=0;
  TEST_ASSERT_EQUAL_INT(SVMG_AMPLITUDE_GROWTH,svmg_baseline_b(&p,&f));
  f.roll_mean_60=4;f.roll_mean_180=4;
  TEST_ASSERT_EQUAL_INT(SVMG_PERSISTENT_OFFSET,svmg_baseline_b(&p,&f));
  f.roll_mean_180=1; /* only 45 s equivalent offset: not persistent */
  TEST_ASSERT_EQUAL_INT(SVMG_NORMAL,svmg_baseline_b(&p,&f));
}

void test_contract_wrappers_match_internal_functions(void) {
  const sigfn sigs[] = { s_normal, s_high, s_off, s_s0b, s_grow, s_h1 };
  for (unsigned k = 0; k < sizeof sigs / sizeof sigs[0]; k++) {
    run(sigs[k]);
    FeatureVector fv; svmg_features_to_contract(&F, &fv);
    TEST_ASSERT_EQUAL_INT((int)svmg_baseline_b(&BP, &F), (int)classifyBaselineB(&fv));
    svmg_mai_params_t mp; svmg_mai_default(&mp); svmg_mai_t m; svmg_mai_compute(&mp, &F, &m);
    TEST_ASSERT_EQUAL_INT((int)m.value, computeMAI(&fv));
  }
}
void test_contract_conversions_roundtrip_and_enum_order(void) {
  run(s_h1);
  FeatureVector fv; svmg_features_to_contract(&F, &fv);
  svmg_features_t g; svmg_features_from_contract(&fv, &g);
  float a[SVMG_N_FEATURES], b[SVMG_N_FEATURES]; svmg_features_to_vector(&F, a); svmg_features_to_vector(&g, b);
  for (int i = 0; i < SVMG_N_FEATURES; i++) TEST_ASSERT_EQUAL_FLOAT(a[i], b[i]);
  MotionSample ms = { 1, 2, 3, .1f, .2f, .3f, 4.5f, 1, true };
  svmg_motion_sample_t s = svmg_sample_from_contract(&ms); MotionSample back = svmg_sample_to_contract(&s);
  TEST_ASSERT_EQUAL_FLOAT(3.0f, s.az); TEST_ASSERT_EQUAL_UINT8(1, s.valid); TEST_ASSERT_EQUAL_FLOAT(4.5f, back.t); TEST_ASSERT_TRUE(back.valid);
}

int main(void) {
  UNITY_BEGIN();
  RUN_TEST(test_safety_clamps_phi); RUN_TEST(test_safety_trips_after_5s_not_before); RUN_TEST(test_safety_below_threshold_never_trips);
  RUN_TEST(test_safety_negative_roll_and_exact_threshold); RUN_TEST(test_safety_dip_resets_counter);
  RUN_TEST(test_safety_invalid_sample_holds_state); RUN_TEST(test_safety_active_clears_when_roll_drops); RUN_TEST(test_safety_set_phi_clamped_runtime);
  RUN_TEST(test_checkSafetyEnvelope_contract_api);
  RUN_TEST(test_mai_components); RUN_TEST(test_mai_nan_is_zero_not_crash);
  RUN_TEST(test_baseline_normal); RUN_TEST(test_baseline_high_roll); RUN_TEST(test_baseline_offset); RUN_TEST(test_baseline_large_offset_is_not_high_roll); RUN_TEST(test_baseline_heel_plus_moderate_waves_is_not_high_roll);
  RUN_TEST(test_baseline_temporary_heel_S0b_is_normal); RUN_TEST(test_baseline_growth); RUN_TEST(test_baseline_combined_case_prefers_high_roll);
  RUN_TEST(test_baseline_priority_with_manual_features);
  RUN_TEST(test_contract_wrappers_match_internal_functions); RUN_TEST(test_contract_conversions_roundtrip_and_enum_order);
  return UNITY_END();
}
