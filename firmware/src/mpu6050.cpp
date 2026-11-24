#include "mpu6050.h"
#include <Wire.h>
#include "pins.h"

static uint32_t s_err = 0, s_consec = 0, s_recoveries = 0;
static bool s_ready = false;
static uint32_t s_last_reinit_ms = 0;
#ifdef SVMG_DIAG_FEATURES
static svmg_imu_raw_t s_last_raw;
static bool s_have_raw = false;
#endif

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

void i2c_begin() {
  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(400000);
  Wire.setTimeOut(20);                       // ms: một thiết bị kéo SDA/SCL treo không được chặn vòng lấy mẫu
}

// Phục hồi bus I2C bị treo (thiết bị con giữ SDA ở mức thấp giữa chừng một byte): phát tối đa 9 xung SCL cho tới khi SDA nhả,
// rồi một điều kiện STOP, rồi khởi tạo lại Wire. Chuẩn xử lý của I2C (NXP UM10204 mục 3.1.16).
void i2c_bus_recover() {
  Wire.end();
  pinMode(PIN_SCL, OUTPUT_OPEN_DRAIN); digitalWrite(PIN_SCL, HIGH);
  pinMode(PIN_SDA, INPUT_PULLUP);
  for (int i = 0; i < 9 && digitalRead(PIN_SDA) == LOW; i++) {
    digitalWrite(PIN_SCL, LOW);  delayMicroseconds(5);
    digitalWrite(PIN_SCL, HIGH); delayMicroseconds(5);
  }
  pinMode(PIN_SDA, OUTPUT_OPEN_DRAIN);
  digitalWrite(PIN_SDA, LOW);  delayMicroseconds(5);
  digitalWrite(PIN_SCL, HIGH); delayMicroseconds(5);
  digitalWrite(PIN_SDA, HIGH); delayMicroseconds(5);                // STOP
  s_recoveries++;
  i2c_begin();
}

uint32_t i2c_recovery_count() { return s_recoveries; }

// Quét I2C và in địa chỉ (giữ tiện ích của chương trình thử mạch M1-01): kỳ vọng MPU6050 0x68 và LCD 0x27.
void i2c_scan_report(bool *found_mpu, bool *found_lcd) {
  *found_mpu = *found_lcd = false;
  Serial.print("[I2C] scan:");
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.printf(" 0x%02X", a);
      if (a == I2C_ADDR_MPU) *found_mpu = true;
      if (a == I2C_ADDR_LCD) *found_lcd = true;
    }
  }
  Serial.println();
}

bool mpu_begin() {
  uint8_t who = 0;
  if (!rd(0x75, &who, 1) || who != 0x68) { s_ready = false; return false; }      // WHO_AM_I
  bool ok = wr(0x6B, 0x80);                                                      // reset
  delay(100);
  ok = wr(0x6B, 0x01) && ok;                                                     // thoát ngủ, xung nhịp PLL theo gyro X
  ok = wr(0x19, 0x09) && ok;                                                     // SMPLRT_DIV: 100 Hz (đọc 20 Hz)
  ok = wr(0x1A, 0x05) && ok;                                                     // DLPF ~10 Hz: băng thông <= Nyquist (10 Hz) của nhịp đọc 20 Hz -> không chồng phổ
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
    if (s_consec >= 20 && millis() - s_last_reinit_ms > 1000) {                  // bus có thể treo: phục hồi bus rồi khởi tạo lại MPU, tối đa 1 lần/giây
      s_last_reinit_ms = millis();
      i2c_bus_recover();
      mpu_begin();
    }
    return false;
  }
  s_consec = 0;
  raw->ax = (int16_t)((b[0] << 8) | b[1]);  raw->ay = (int16_t)((b[2] << 8) | b[3]);  raw->az = (int16_t)((b[4] << 8) | b[5]);
  raw->gx = (int16_t)((b[8] << 8) | b[9]);  raw->gy = (int16_t)((b[10] << 8) | b[11]); raw->gz = (int16_t)((b[12] << 8) | b[13]);
#ifdef SVMG_DIAG_FEATURES
  s_last_raw = *raw; s_have_raw = true;
#endif
  return true;
}

#ifdef SVMG_DIAG_FEATURES
bool mpu_last_raw(svmg_imu_raw_t *raw) { if (s_have_raw) *raw = s_last_raw; return s_have_raw; }
#endif

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
