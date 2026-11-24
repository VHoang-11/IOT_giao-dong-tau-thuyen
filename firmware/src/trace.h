// Chuỗi roll/pitch 10 Hz (centi-độ) cho lệnh request_snapshot và topic `trace` (đề cương 8.2, 9.1) - M1-07.
#pragma once
#include <stdint.h>

void trace_push(float roll_deg, float pitch_deg);       // gọi mỗi mẫu 10 Hz hợp lệ (đã trừ hiệu chuẩn)
void trace_clear();
// Sao chép tối đa window_s*10 mẫu mới nhất theo thứ tự cũ -> mới. Trả số mẫu.
int  trace_copy(uint16_t window_s, int16_t *roll_cdeg, int16_t *pitch_cdeg, int cap);
constexpr int TRACE_CAP = 1800;                          // 180 s x 10 Hz = 7.1 KiB
