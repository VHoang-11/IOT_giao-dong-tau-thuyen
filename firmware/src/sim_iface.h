// Giao diện nguồn tín hiệu mô phỏng. Bộ sinh THẬT thuộc M2 (core/src/sim, svmg_sim.h) - M1 chỉ gọi qua đây.
// Cho tới khi M2 bàn giao: stubs/sim_stub.cpp (sóng sin đơn giản, đúng mock đã nêu ở mục 4 của kế hoạch chia việc).
// Khi có svmg_sim.h: thay phần thân các hàm trong sim_adapter (một file), không đổi chỗ gọi.
#pragma once
#include <stdint.h>
#include "svmg_common.h"

void sim_init(uint32_t seed);
void sim_set_scenario(uint8_t scenario /*0..5 = S0,S0b,S1,S2,S3,H1*/, uint8_t sea_state /*0..5*/);
void sim_set_sea_state(uint8_t sea_state);
uint8_t sim_scenario();
uint8_t sim_sea_state();
void sim_restart();                       // đưa đồng hồ kịch bản về 0 (t0 mới)
// Sinh một mẫu IMU theo SI cho thời điểm kế tiếp (dt giây sau mẫu trước). Không đặt s->t/valid/source_mode.
void sim_next(float dt, svmg_motion_sample_t *s);
bool sim_is_stub();
