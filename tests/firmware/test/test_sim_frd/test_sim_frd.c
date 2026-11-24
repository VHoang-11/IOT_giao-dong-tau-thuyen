/* Test M1-02/WS8: hệ trục FRD của bộ mô phỏng M2 -> hệ trục cảm biến M1 (svmg_sample_frd_to_sensor).
 * Dữ liệu vào (frd_golden.h) do CHÍNH simulation/generator/imu_simulator.py của M2 sinh ra (tools/gen_frd_golden.py).
 * Kiểm: (1) mức nằm ngang cho az = -g (FRD) -> +g sau đổi; (2) roll từ gia tốc khớp roll thật <= 0.05 deg, ĐÚNG DẤU;
 * (3) toàn pipeline C cho roll khớp (<= 0.2 deg) pipeline chạy với mẫu M1 lý tưởng của cùng roll thật. */
#include <unity.h>
#include <math.h>
#include "svmg_filter.h"
#include "svmg_testutil.h"
#include "frd_golden.h"

void setUp(void) {}
void tearDown(void) {}

static svmg_motion_sample_t frd_sample(int i) {
  svmg_motion_sample_t s;
  memset(&s, 0, sizeof s);
  s.ax = FRD_AX[i]; s.ay = FRD_AY[i]; s.az = FRD_AZ[i];
  s.gx = FRD_GX[i]; s.gy = FRD_GY[i]; s.gz = FRD_GZ[i];
  s.t = (float)(i * (double)FRD_DT); s.source_mode = SVMG_SRC_SIMULATION; s.valid = 1;
  return s;
}

void test_level_frd_has_az_minus_g_and_sensor_has_plus_g(void) {
  TEST_ASSERT_TRUE_MESSAGE(FRD_AZ[0] < -9.0f, "M2 FRD: nằm ngang cho az = -g (xác nhận quy ước trong imu_simulator.py)");
  svmg_motion_sample_t s = frd_sample(0);
  svmg_sample_frd_to_sensor(&s);
  TEST_ASSERT_TRUE(s.az > 9.0f);
}

void test_accel_roll_matches_true_roll_with_correct_sign(void) {
  double worst = 0.0;
  for (int i = 0; i < FRD_N; i++) {
    svmg_motion_sample_t s = frd_sample(i);
    svmg_sample_frd_to_sensor(&s);
    float r, p; svmg_accel_to_angles(s.ax, s.ay, s.az, &r, &p);
    double e = fabs((double)r - (double)FRD_PHI[i]) * ST_R2D;
    if (e > worst) worst = e;
    if (fabs(FRD_PHI[i]) > 0.05) TEST_ASSERT_TRUE_MESSAGE(r * FRD_PHI[i] > 0, "dấu roll phải giữ nguyên (mạn phải chìm = dương)");
  }
  TEST_ASSERT_TRUE_MESSAGE(worst <= 0.05, "roll từ gia tốc sau đổi trục lệch quá 0.05 deg so với roll thật của M2");
}

/* Đối chứng: không đổi trục thì sai (kiểm chứng test này bắt được lỗi dấu). */
void test_without_conversion_roll_is_wrong(void) {
  int bad = 0;
  for (int i = 0; i < FRD_N; i += 50) {
    svmg_motion_sample_t s = frd_sample(i);
    float r, p; svmg_accel_to_angles(s.ax, s.ay, s.az, &r, &p);
    if (fabs((double)r - (double)FRD_PHI[i]) * ST_R2D > 1.0) bad++;
  }
  TEST_ASSERT_TRUE(bad > 0);
}

void test_pipeline_matches_native_frame_pipeline(void) {
  svmg_pipeline_cfg_t cfg; svmg_pipeline_default_cfg(&cfg);
  svmg_pipeline_t a, b; svmg_pipeline_init(&a, &cfg); svmg_pipeline_init(&b, &cfg);
  double worst = 0.0; int n = 0;
  for (int i = 0; i < FRD_N; i++) {
    svmg_motion_sample_t s = frd_sample(i); svmg_sample_frd_to_sensor(&s);
    svmg_motion_sample_t ref = st_sample(i * (double)FRD_DT, FRD_PHI[i], (double)FRD_GX[i], 0.0, 0.0);
    svmg_sample10hz_t oa, ob;
    int ra = svmg_pipeline_push(&a, &s, &oa), rb = svmg_pipeline_push(&b, &ref, &ob);
    TEST_ASSERT_EQUAL_INT(rb, ra);
    if (ra && rb) { double e = fabs((double)oa.roll_rad - (double)ob.roll_rad) * ST_R2D; if (e > worst) worst = e; n++; }
  }
  TEST_ASSERT_TRUE(n > 100);
  TEST_ASSERT_TRUE_MESSAGE(worst <= 0.2, "pipeline với mẫu M2 (sau đổi trục) lệch quá 0.2 deg so với mẫu M1 lý tưởng");
}

int main(void) {
  UNITY_BEGIN();
  RUN_TEST(test_level_frd_has_az_minus_g_and_sensor_has_plus_g);
  RUN_TEST(test_accel_roll_matches_true_roll_with_correct_sign);
  RUN_TEST(test_without_conversion_roll_is_wrong);
  RUN_TEST(test_pipeline_matches_native_frame_pipeline);
  return UNITY_END();
}
