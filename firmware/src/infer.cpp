#include "infer.h"

#if __has_include("model.h")
#include "model.h"
#else
#include "model_stub.h"
#endif

#ifndef SVMG_MODEL_IS_STUB
#define SVMG_MODEL_IS_STUB 0
#endif
#ifndef SVMG_MODEL_VERSION
#define SVMG_MODEL_VERSION "rf_unversioned"
#endif
#ifndef SVMG_TAU_CONF
#define SVMG_TAU_CONF 0.5f
#endif

static InferStats s_stats = {0, 0, 0, 0};

bool infer_available() { return !SVMG_MODEL_IS_STUB; }
const char *infer_model_version() { return SVMG_MODEL_VERSION; }
const InferStats &infer_stats() { return s_stats; }

void infer_begin(svmg_engine_t *e) {
  if (infer_available()) svmg_engine_set_rf(e, infer_predict, nullptr);
  // stub -> không đăng ký: engine dùng Baseline B và báo model_fallback (không để "RF mù" im lặng bảo là NORMAL)
}

svmg_class_t infer_predict(void *, const float *f, int n) {
#ifdef SVMG_MODEL_HAS_RANGE
  for (int i = 0; i < n && i < (int)(sizeof(SVMG_MODEL_FEAT_MIN) / sizeof(float)); i++) {
    float lo = SVMG_MODEL_FEAT_MIN[i], hi = SVMG_MODEL_FEAT_MAX[i];
    float m = 0.01f * (hi - lo);
    if (f[i] < lo - m || f[i] > hi + m) return SVMG_UNKNOWN;       // ngoài miền đã thấy lúc huấn luyện
  }
#endif
  uint32_t t0 = micros();
#ifdef SVMG_MODEL_HAS_PROBA
  float conf = 1.0f;
  int c = model_predict_conf(f, n, &conf);
  if (conf < SVMG_TAU_CONF) c = SVMG_UNKNOWN;                      // tỉ lệ phiếu (chưa hiệu chuẩn, không phải xác suất)
#else
  int c = model_predict(f, n);
#endif
  uint32_t dt = micros() - t0;
  s_stats.calls++; s_stats.last_us = dt; s_stats.sum_us += dt;
  if (dt > s_stats.max_us) s_stats.max_us = dt;
  if (c < 0 || c > SVMG_AMPLITUDE_GROWTH) return SVMG_UNKNOWN;     // nhãn lạ -> không tin
  return (svmg_class_t)c;
}
