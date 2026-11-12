// Driver MPU6050 qua I2C bằng thanh ghi thô (±2 g, ±250 °/s) - M1-02.
// Chọn đọc thanh ghi thay vì thư viện Adafruit: ít RAM/flash, tự chủ thang đo, trả số thô để core/ quy đổi SI một lần.
#pragma once
#include <Arduino.h>
#include "svmg_filter.h"

bool     mpu_begin();                       // false nếu không thấy thiết bị/WHO_AM_I sai
bool     mpu_read(svmg_imu_raw_t *raw);     // false nếu lỗi I2C (đã thử lại 1 lần)
uint32_t mpu_error_count();
uint32_t mpu_consecutive_errors();
// Tự kiểm tra thang đo lúc khởi động: đọc N mẫu đứng yên, trả |a| theo g (kỳ vọng ~1.0 khi tĩnh).
bool     mpu_selftest(float *accel_norm_g);
