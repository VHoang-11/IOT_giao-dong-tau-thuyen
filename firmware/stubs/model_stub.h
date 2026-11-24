// STUB mô hình RF - dùng cho tới khi M2 bàn giao ml/export/model.h. TRẢ UNKNOWN nếu bị gọi trực tiếp; không giả làm RF thật.
// infer.cpp nhận biết SVMG_MODEL_IS_STUB và KHÔNG đăng ký RF vào engine (để engine dùng Baseline B thay vì "RF mù").
#pragma once
#include "svmg_common.h"
#define SVMG_MODEL_IS_STUB 1
#define SVMG_MODEL_VERSION "none"
static inline int model_predict(const float *features, int n) { (void)features; (void)n; return SVMG_UNKNOWN; }
