/* Tiện ích dùng chung cho test: tạo mẫu IMU giả từ tư thế, bộ sinh số ngẫu nhiên xác định. */
#ifndef SVMG_TESTUTIL_H
#define SVMG_TESTUTIL_H

#include <math.h>
#include <stdint.h>
#include <string.h>
#include "svmg_common.h"

#define ST_G 9.80665
#define ST_D2R 0.017453292519943295
#define ST_R2D 57.29577951308232

/* Mẫu IMU lý tưởng cho tư thế (roll, pitch) [rad] và tốc độ góc [rad/s] (trục ZYX, khớp svmg_filter.h). */
static inline svmg_motion_sample_t st_sample(double t, double roll, double roll_rate, double pitch, double pitch_rate) {
  svmg_motion_sample_t s;
  memset(&s, 0, sizeof s);
  s.ax = (float)(-ST_G * sin(pitch));
  s.ay = (float)(ST_G * cos(pitch) * sin(roll));
  s.az = (float)(ST_G * cos(pitch) * cos(roll));
  s.gx = (float)roll_rate;
  s.gy = (float)pitch_rate;
  s.gz = 0.0f;
  s.t = (float)t;
  s.source_mode = SVMG_SRC_SENSOR;
  s.valid = 1;
  return s;
}

/* xorshift32 xác định cho nhiễu trong test. */
static inline uint32_t st_rng(uint32_t *s) { uint32_t x = *s; x ^= x << 13; x ^= x >> 17; x ^= x << 5; return *s = x; }
static inline double st_uniform(uint32_t *s) { return (double)st_rng(s) / 4294967296.0; }
/* xấp xỉ Gauss(0,1): tổng 12 phân bố đều trừ 6. */
static inline double st_gauss(uint32_t *s) { double a = 0; for (int i = 0; i < 12; i++) a += st_uniform(s); return a - 6.0; }

#endif
