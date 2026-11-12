/* features.c - M1-03. Xem svmg_features.h. */
#include "svmg_features.h"
#include <math.h>
#include <string.h>

const char *const SVMG_FEATURE_NAMES[SVMG_N_FEATURES] = {
  "rms_roll", "p2p", "p95_abs", "rms_gyro_x", "rms_gyro_y",
  "mean_roll", "same_sign_ratio", "trend", "rms_ratio", "zero_cross_period"
};

void svmg_window_clear(svmg_window_t *w) { memset(w, 0, sizeof *w); }

int svmg_window_push(svmg_window_t *w, float roll_deg, float gx_dps, float gy_dps, uint8_t valid) {
  uint32_t i = w->total % SVMG_WIN_LONG;
  uint32_t j = w->total % SVMG_WIN_SHORT;
  valid = (valid && isfinite(roll_deg) && isfinite(gx_dps) && isfinite(gy_dps)) ? 1 : 0;
  w->roll_deg[i] = valid ? roll_deg : 0.0f;
  w->valid[i] = valid;
  w->gx_dps[j] = valid ? gx_dps : 0.0f;
  w->gy_dps[j] = valid ? gy_dps : 0.0f;
  w->total++;
  if (valid) w->consec_invalid = 0;
  else if (w->consec_invalid < 0xFFFF) w->consec_invalid++;
  if (++w->since_update >= SVMG_UPDATE_SAMPLES) { w->since_update = 0; return 1; }
  return 0;
}

void svmg_window_shift_roll(svmg_window_t *w, float delta_deg) {
  for (int i = 0; i < SVMG_WIN_LONG; i++) if (w->valid[i]) w->roll_deg[i] += delta_deg;
}

/* k = 0 là mẫu mới nhất. */
static inline uint32_t slot_long(const svmg_window_t *w, uint32_t k) { return (w->total - 1u - k) % SVMG_WIN_LONG; }
static inline uint32_t slot_short(const svmg_window_t *w, uint32_t k) { return (w->total - 1u - k) % SVMG_WIN_SHORT; }

/* Thống kê roll trên các mẫu k = k0 .. k0+n-1 (chỉ mẫu hợp lệ). */
typedef struct { uint16_t nv; float mean, rms_abs, rms_dyn; } roll_stat_t;

static roll_stat_t roll_stat(const svmg_window_t *w, uint32_t k0, uint32_t n) {
  roll_stat_t r = {0, 0, 0, 0};
  float s = 0, s2 = 0;
  for (uint32_t k = k0; k < k0 + n; k++) {
    uint32_t i = slot_long(w, k);
    if (!w->valid[i]) continue;
    float x = w->roll_deg[i];
    s += x; s2 += x * x; r.nv++;
  }
  if (r.nv == 0) return r;
  r.mean = s / r.nv;
  r.rms_abs = sqrtf(s2 / r.nv);
  float v = 0;
  for (uint32_t k = k0; k < k0 + n; k++) {
    uint32_t i = slot_long(w, k);
    if (!w->valid[i]) continue;
    float d = w->roll_deg[i] - r.mean;
    v += d * d;
  }
  r.rms_dyn = sqrtf(v / r.nv);
  return r;
}

static inline float pick_rms(const roll_stat_t *r) { return SVMG_FEAT_RMS_ABOUT_MEAN ? r->rms_dyn : r->rms_abs; }

static float gyro_rms(const float *buf, const svmg_window_t *w, uint32_t n) {
  float s2 = 0; int nv = 0;
  for (uint32_t k = 0; k < n; k++) {
    if (!w->valid[slot_long(w, k)]) continue;
    float x = buf[slot_short(w, k)];
    s2 += x * x; nv++;
  }
  return nv ? sqrtf(s2 / nv) : 0.0f;
}

void svmg_features_compute(const svmg_window_t *w, svmg_features_t *f) {
  memset(f, 0, sizeof *f);
  f->rms_ratio = 1.0f;
  f->consec_invalid = w->consec_invalid;
  f->ready_short = (w->total >= SVMG_WIN_SHORT);
  f->ready_long = (w->total >= SVMG_WIN_LONG);

  uint32_t n60 = w->total < SVMG_WIN_SHORT ? w->total : SVMG_WIN_SHORT;
  uint32_t n180 = w->total < SVMG_WIN_LONG ? w->total : SVMG_WIN_LONG;
  if (n60 == 0) { f->missing_ratio_60 = f->missing_ratio_180 = 1.0f; return; }

  /* --- 60 s --- */
  roll_stat_t s60 = roll_stat(w, 0, n60);
  f->n_valid_60 = s60.nv;
  f->missing_ratio_60 = 1.0f - (float)s60.nv / (float)n60;
  f->rms_roll_abs_deg = s60.rms_abs;
  f->rms_roll_deg = pick_rms(&s60);
  f->rms_gyro_x_dps = gyro_rms(w->gx_dps, w, n60);
  f->rms_gyro_y_dps = gyro_rms(w->gy_dps, w, n60);

  float tmp[SVMG_WIN_SHORT];     /* |roll| của mẫu hợp lệ, dùng cho P95 */
  float mn = 0, mx = 0; int m = 0;
  for (uint32_t k = 0; k < n60; k++) {
    uint32_t i = slot_long(w, k);
    if (!w->valid[i]) continue;
    float x = w->roll_deg[i];
    if (m == 0 || x < mn) mn = x;
    if (m == 0 || x > mx) mx = x;
    float a = fabsf(x);
    int p = m++;                       /* chèn có thứ tự (insertion sort) */
    while (p > 0 && tmp[p - 1] > a) { tmp[p] = tmp[p - 1]; p--; }
    tmp[p] = a;
  }
  if (m > 0) {
    f->p2p_deg = mx - mn;
    int idx = (int)ceilf(0.95f * (float)m) - 1;
    if (idx < 0) idx = 0;
    if (idx >= m) idx = m - 1;
    f->p95_abs_deg = tmp[idx];
  }

  /* Nhịp: số lần cắt không có trễ (hysteresis 0.15 deg), trên 60 s đã trừ trung bình. */
  {
    const float hyst = 0.15f;
    int last_sign = 0, ncross = 0;
    long first_k = -1, last_k = -1;
    for (int k = (int)n60 - 1; k >= 0; k--) {          /* từ cũ đến mới */
      uint32_t i = slot_long(w, (uint32_t)k);
      if (!w->valid[i]) continue;
      float x = w->roll_deg[i] - s60.mean;
      int sg = (x > hyst) ? 1 : (x < -hyst) ? -1 : 0;
      if (sg == 0) continue;
      if (last_sign != 0 && sg != last_sign) {
        if (first_k < 0) first_k = k;
        last_k = k;
        ncross++;
      }
      last_sign = sg;
    }
    if (ncross >= 2) {
      float half = (float)(first_k - last_k) / (float)(ncross - 1) / 2.0f;   /* nửa chu kỳ [s] (2 mẫu/s) */
      f->zero_cross_period_s = 2.0f * half;
    }
  }

  /* Nhiễu nền: sai phân bậc 2 trên ba mẫu hợp lệ liên tiếp (var = 6 sigma^2 với nhiễu trắng). */
  {
    float acc = 0; int cnt = 0;
    for (uint32_t k = 0; k + 2 < n60; k++) {
      uint32_t i0 = slot_long(w, k), i1 = slot_long(w, k + 1), i2 = slot_long(w, k + 2);
      if (!(w->valid[i0] && w->valid[i1] && w->valid[i2])) continue;
      float d2 = w->roll_deg[i0] - 2.0f * w->roll_deg[i1] + w->roll_deg[i2];
      acc += d2 * d2; cnt++;
    }
    f->noise_floor_deg = cnt ? sqrtf(acc / (6.0f * cnt)) : 0.0f;
  }

  /* --- 180 s --- */
  roll_stat_t s180 = roll_stat(w, 0, n180);
  f->n_valid_180 = s180.nv;
  f->missing_ratio_180 = 1.0f - (float)s180.nv / (float)n180;
  f->mean_roll_deg = s180.mean;
  {
    int npos = 0, nneg = 0;
    for (uint32_t k = 0; k < n180; k++) {
      uint32_t i = slot_long(w, k);
      if (!w->valid[i]) continue;
      if (w->roll_deg[i] > 0.01f) npos++; else if (w->roll_deg[i] < -0.01f) nneg++;   /* vùng chết 0.01 deg */
    }
    int nv = npos + nneg;
    f->same_sign_ratio = nv ? (float)(npos > nneg ? npos : nneg) / (float)nv : 0.5f;
  }

  if (f->ready_long) {
    /* 6 đoạn 30 s (60 mẫu), từ cũ (s = 0) đến mới (s = 5). */
    float xs[6], ys[6]; int ns = 0;
    for (int s = 0; s < 6; s++) {
      uint32_t k0 = (uint32_t)(SVMG_WIN_LONG - 60 * (s + 1));
      roll_stat_t sg = roll_stat(w, k0, 60);
      if (sg.nv < 20) continue;
      xs[ns] = (float)s; ys[ns] = pick_rms(&sg); ns++;
    }
    if (ns >= 3) {
      float mx_ = 0, my_ = 0;
      for (int i = 0; i < ns; i++) { mx_ += xs[i]; my_ += ys[i]; }
      mx_ /= ns; my_ /= ns;
      float num = 0, den = 0;
      for (int i = 0; i < ns; i++) { num += (xs[i] - mx_) * (ys[i] - my_); den += (xs[i] - mx_) * (xs[i] - mx_); }
      f->trend_rms_deg_per_min = (den > 0 ? num / den : 0.0f) * 2.0f;     /* deg / 30 s -> deg / min */
    }
    roll_stat_t first = roll_stat(w, SVMG_WIN_LONG - SVMG_WIN_SHORT, SVMG_WIN_SHORT);
    if (first.nv >= 20 && s60.nv >= 20) {
      float den = pick_rms(&first), num = f->rms_roll_deg;
      if (den < 0.5f) den = 0.5f;          /* sàn 0.5 deg cho cả hai vế: tín hiệu im lặng cho tỉ số 1 */
      if (num < 0.5f) num = 0.5f;
      f->rms_ratio = num / den;
    }
  }
}

void svmg_features_to_vector(const svmg_features_t *f, float out[SVMG_N_FEATURES]) {
  out[0] = f->rms_roll_deg;   out[1] = f->p2p_deg;           out[2] = f->p95_abs_deg;
  out[3] = f->rms_gyro_x_dps; out[4] = f->rms_gyro_y_dps;    out[5] = f->mean_roll_deg;
  out[6] = f->same_sign_ratio; out[7] = f->trend_rms_deg_per_min; out[8] = f->rms_ratio;
  out[9] = f->zero_cross_period_s;
}

void svmg_quality_default(svmg_quality_cfg_t *q) {
  q->unknown_missing_ratio = 0.20f;
  q->fault_missing_ratio = 0.50f;
  q->fault_consec_invalid = 20;
}

svmg_status_t svmg_features_status(const svmg_features_t *f, const svmg_quality_cfg_t *q, uint8_t *reason) {
  uint8_t r = 0;
  if (f->consec_invalid >= q->fault_consec_invalid) r |= SVMG_Q_FAULT_RUN;
  if (f->missing_ratio_60 > q->fault_missing_ratio) r |= SVMG_Q_FAULT_RATIO;
  if (!f->ready_long) r |= SVMG_Q_COLD;
  if (f->missing_ratio_60 > q->unknown_missing_ratio || f->missing_ratio_180 > q->unknown_missing_ratio) r |= SVMG_Q_MISSING;
  if (reason) *reason = r;
  if (r & (SVMG_Q_FAULT_RUN | SVMG_Q_FAULT_RATIO)) return SVMG_ST_FAULT;
  if (r & (SVMG_Q_COLD | SVMG_Q_MISSING)) return SVMG_ST_UNKNOWN;
  return SVMG_ST_OK;
}
