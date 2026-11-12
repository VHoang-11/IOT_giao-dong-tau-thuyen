#include "motion_source.h"
#include "mpu6050.h"
#include "sim_iface.h"
#include "svmg_filter.h"

static double s_sim_abs = 0.0;       // giây mô phỏng tuyệt đối
static bool s_present = false;
static uint32_t s_sat = 0;
#ifdef SVMG_FAULT_INJECT
static char s_inj = 0;
void motion_inject(char c) { s_inj = (c == 'x') ? 0 : c; }
#endif
static const double WRAP_S = 8192.0; // giữ t của lõi nhỏ để float không mất độ phân giải (lõi xử lý quấn vòng)

void motion_init() {
  s_present = mpu_begin();
  sim_init(0xC0FFEE);
}

bool motion_sensor_present() { return s_present; }
uint32_t motion_saturation_count() { return s_sat; }
double motion_sim_time_abs() { return s_sim_abs; }
void motion_sim_clock_reset() { s_sim_abs = 0.0; sim_restart(); }

svmg_motion_sample_t acquireMotionSample(svmg_source_t mode) {
  svmg_motion_sample_t s;
  memset(&s, 0, sizeof s);
  s.source_mode = (uint8_t)mode;
  if (mode == SVMG_SRC_SIMULATION) {
    s_sim_abs += 1.0 / 20.0;
    sim_next(1.0f / 20.0f, &s);
    s.t = (float)fmod(s_sim_abs, WRAP_S);
    s.valid = 1;
  } else {
    svmg_imu_raw_t raw;
    // Thời gian thực từ millis() (đã quấn vòng); khi loop bị đứng > 0.5 s lõi sẽ phát hiện khoảng trống và khởi động lại cửa sổ.
    s.t = (float)fmod((double)millis() / 1000.0, WRAP_S);
    if (mpu_read(&raw)) {
      if (svmg_imu_raw_to_si(&raw, &s) & SVMG_IMU_F_SATURATED) s_sat++;
      s.t = (float)fmod((double)millis() / 1000.0, WRAP_S);
      s.valid = 1;
    } else {
      s.valid = 0;                    // lỗi I2C: vẫn đẩy mẫu thiếu vào lõi để đếm tỉ lệ thiếu
    }
    s.source_mode = SVMG_SRC_SENSOR;
  }
#ifdef SVMG_FAULT_INJECT      // T07/T13: chèn lỗi cảm biến khi đang chạy (chỉ có trong env esp32dev_inject)
  switch (s_inj) {
    case 'i': s.valid = 0; break;                                                   // mất I2C
    case 'z': s.ax = s.ay = s.az = s.gx = s.gy = s.gz = 0; break;                   // bus chết trả 0
    case 'n': s.ay = NAN; break;                                                    // giá trị hỏng
    case 'd': if (random(100) < 30) s.valid = 0; break;                             // mất 30 % mẫu
    case 's': s.ax = s.ay = s.az = -19.6133f; s.gx = s.gy = s.gz = -4.3633f; break; // bão hòa ±2 g / ±250 °/s
    default: break;
  }
#endif
  return s;
}
