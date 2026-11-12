#include "mpu6050.h"
#include <Wire.h>
#include "pins.h"

static uint32_t s_err = 0, s_consec = 0;
static bool s_ready = false;
static uint32_t s_last_reinit_ms = 0;

static bool wr(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(I2C_ADDR_MPU);
  Wire.write(reg); Wire.write(val);
  return Wire.endTransmission() == 0;
}

static bool rd(uint8_t reg, uint8_t *buf, size_t n) {
  Wire.beginTransmission(I2C_ADDR_MPU);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint8_t)I2C_ADDR_MPU, (uint8_t)n) != n) return false;
  for (size_t i = 0; i < n; i++) buf[i] = Wire.read();
  return true;
}

bool mpu_begin() {
  uint8_t who = 0;
  if (!rd(0x75, &who, 1) || who != 0x68) { s_ready = false; return false; }      // WHO_AM_I
  bool ok = wr(0x6B, 0x80);                                                      // reset
  delay(100);
  ok = wr(0x6B, 0x01) && ok;                                                     // thoát ngủ, xung nhịp PLL theo gyro X
  ok = wr(0x19, 0x09) && ok;                                                     // SMPLRT_DIV: 100 Hz (đọc 20 Hz)
  ok = wr(0x1A, 0x04) && ok;                                                     // DLPF ~20 Hz: chống chồng phổ trước khi lấy mẫu 20 Hz
  ok = wr(0x1B, 0x00) && ok;                                                     // gyro ±250 °/s  (131 LSB/(°/s))
  ok = wr(0x1C, 0x00) && ok;                                                     // accel ±2 g     (16384 LSB/g)
  s_ready = ok;
  return ok;
}

bool mpu_read(svmg_imu_raw_t *raw) {
  uint8_t b[14];
  bool ok = rd(0x3B, b, 14) || rd(0x3B, b, 14);                                  // thử lại 1 lần
  if (!ok) {
    s_err++; s_consec++;
    if (s_consec >= 20 && millis() - s_last_reinit_ms > 1000) {                  // bus có thể treo: thử khởi tạo lại mỗi 1 s
      s_last_reinit_ms = millis(); mpu_begin();
    }
    return false;
  }
  s_consec = 0;
  raw->ax = (int16_t)((b[0] << 8) | b[1]);  raw->ay = (int16_t)((b[2] << 8) | b[3]);  raw->az = (int16_t)((b[4] << 8) | b[5]);
  raw->gx = (int16_t)((b[8] << 8) | b[9]);  raw->gy = (int16_t)((b[10] << 8) | b[11]); raw->gz = (int16_t)((b[12] << 8) | b[13]);
  return true;
}

uint32_t mpu_error_count() { return s_err; }
uint32_t mpu_consecutive_errors() { return s_consec; }

bool mpu_selftest(float *norm_g) {
  double acc = 0; int n = 0;
  for (int i = 0; i < 10; i++) {
    svmg_imu_raw_t r;
    if (mpu_read(&r)) {
      double ax = r.ax / 16384.0, ay = r.ay / 16384.0, az = r.az / 16384.0;
      acc += sqrt(ax * ax + ay * ay + az * az); n++;
    }
    delay(10);
  }
  if (n == 0) return false;
  *norm_g = (float)(acc / n);
  return true;
}
