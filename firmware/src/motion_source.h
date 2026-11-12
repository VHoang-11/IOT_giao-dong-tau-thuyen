// acquireMotionSample(mode): nguồn dữ liệu chung SENSOR/SIMULATION -> MotionSample chuẩn hóa theo SI (đề cương 4.2, 7.1).
#pragma once
#include <Arduino.h>
#include "svmg_common.h"

void motion_init();
// Trả mẫu kế tiếp. SENSOR: đọc MPU6050 (valid=0 nếu lỗi I2C); SIMULATION: gọi sim_next, đồng hồ ảo tiến 1/20 s.
svmg_motion_sample_t acquireMotionSample(svmg_source_t mode);
// Thời gian mô phỏng tuyệt đối (s) - chỉ dùng để gắn nhãn bản tin; lõi nhận t đã quấn vòng < 8192 s.
double motion_sim_time_abs();
void   motion_sim_clock_reset();
bool   motion_sensor_present();
uint32_t motion_saturation_count();
#ifdef SVMG_FAULT_INJECT
void motion_inject(char c);   // 'i' mất I2C, 'z' bus trả 0, 'n' NaN, 'd' mất 30 %, 's' bão hòa, 'x' bỏ lỗi
#endif
