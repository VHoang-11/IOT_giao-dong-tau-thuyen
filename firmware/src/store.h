// Lưu cấu hình bền vững bằng NVS (Preferences) - M1-07. Một blob duy nhất có CRC => áp dụng nguyên tử:
// hoặc đọc lại đúng toàn bộ cấu hình mới, hoặc đúng toàn bộ cấu hình cũ (không bao giờ nửa nọ nửa kia).
// Trong Wokwi, NVS chỉ bền trong phạm vi một phiên chạy (đề cương 8.2.1).
#pragma once
#include "svmg_config.h"

// true nếu nạp được cấu hình hợp lệ từ NVS; false -> *out là mặc định (và chưa ghi gì).
bool store_load(svmg_config_t *out, svmg_model_t default_model);
bool store_save(const svmg_config_t *cfg);
uint32_t store_next_boot_count();      // đếm số lần khởi động
