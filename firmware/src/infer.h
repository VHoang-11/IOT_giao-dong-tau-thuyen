// Tích hợp mô hình RF của M2 (model.h) + đo thời gian suy luận - M1-08.
//   Ghép nối: nếu tìm thấy ml/export/model.h (đường dẫn -I ../ml/export) thì dùng nó, nếu không dùng stubs/model_stub.h.
//   Giả định về model.h (cần M2 xác nhận trong contracts): hàm `int model_predict(const float *f, int n)` trả chỉ số lớp
//   theo thứ tự svmg_class_t 0..3 (NORMAL, HIGH_ROLL, PERSISTENT_OFFSET, AMPLITUDE_GROWTH), và macro SVMG_MODEL_VERSION.
//   Tùy chọn (nếu M2 cung cấp): SVMG_MODEL_HAS_RANGE (+ SVMG_MODEL_FEAT_MIN/MAX[10]) -> UNKNOWN khi đặc trưng ngoài miền
//   huấn luyện (biên 1 %); SVMG_MODEL_HAS_PROBA (+ model_predict_conf) -> UNKNOWN khi tỉ lệ phiếu < τ_conf.
#pragma once
#include <Arduino.h>
#include "svmg_engine.h"

void infer_begin(svmg_engine_t *e);          // đăng ký RF vào engine nếu không phải stub
bool infer_available();                      // có mô hình RF thật hay không
const char *infer_model_version();           // "rf_v1" hoặc "none"
svmg_class_t infer_predict(void *ctx, const float *features, int n);   // dùng làm svmg_rf_fn
struct InferStats { uint32_t calls, last_us, max_us; uint64_t sum_us; uint32_t avg_us() const { return calls ? (uint32_t)(sum_us / calls) : 0; } };
const InferStats &infer_stats();
