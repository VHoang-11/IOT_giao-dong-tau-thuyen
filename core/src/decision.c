/* decision.c - M1-04. Xem svmg_decision.h. */
#include "svmg_decision.h"
#include <math.h>

/* ---------------- Lớp ngưỡng cứng ---------------- */
float svmg_safety_clamp_phi(float phi) {
  if (!isfinite(phi)) return SVMG_PHI_HARD_DEFAULT_DEG;
  if (phi < SVMG_PHI_HARD_MIN_DEG) return SVMG_PHI_HARD_MIN_DEG;
  if (phi > SVMG_PHI_HARD_MAX_DEG) return SVMG_PHI_HARD_MAX_DEG;
  return phi;
}

void svmg_safety_reset(svmg_safety_t *s) { s->over = 0; s->active = 0; s->over_since_s = 0.0f; }

void svmg_safety_init(svmg_safety_t *s, float phi) {
  s->phi_hard_deg = svmg_safety_clamp_phi(phi);
  s->dwell_s = SVMG_HARD_DWELL_S;
  svmg_safety_reset(s);
}

void svmg_safety_set_phi(svmg_safety_t *s, float phi) { s->phi_hard_deg = svmg_safety_clamp_phi(phi); }

int svmg_safety_push(svmg_safety_t *s, float t, float roll, uint8_t valid) {
  if (!valid || !isfinite(roll) || !isfinite(t)) return 0;      /* giữ nguyên trạng thái, không reset, không kích hoạt */
  if (s->over && t < s->over_since_s) svmg_safety_reset(s);     /* đồng hồ đi lùi */
  int was_active = s->active;
  if (fabsf(roll) >= s->phi_hard_deg) {
    if (!s->over) { s->over = 1; s->over_since_s = t; }
    if ((t - s->over_since_s) >= s->dwell_s) s->active = 1;
  } else {
    s->over = 0; s->active = 0;
  }
  return (!was_active && s->active) ? 1 : 0;
}

/* ---------------- MAI ---------------- */
void svmg_mai_default(svmg_mai_params_t *p) {
  p->a_ref_deg = 8.0f;
  p->b_ref_deg = 5.0f;
  p->g_ref_deg_per_min = 2.0f;
}

void svmg_mai_compute(const svmg_mai_params_t *p, const svmg_features_t *f, svmg_mai_t *o) {
  o->r_amp = f->rms_roll_deg / p->a_ref_deg;
  o->r_off = fabsf(f->mean_roll_deg) / p->b_ref_deg;
  o->r_trend = (f->trend_rms_deg_per_min > 0.0f ? f->trend_rms_deg_per_min : 0.0f) / p->g_ref_deg_per_min;
  float m = o->r_amp; o->dominant = 0;
  if (o->r_off > m) { m = o->r_off; o->dominant = 1; }
  if (o->r_trend > m) { m = o->r_trend; o->dominant = 2; }
  if (!(m > 0.0f)) m = 0.0f;           /* cũng bắt NaN */
  if (m > 1.0f) m = 1.0f;
  o->value = (uint8_t)(100.0f * m + 0.5f);
}

/* ---------------- Baseline B ---------------- */
void svmg_baseline_default(svmg_baseline_params_t *p) {
  p->hi_rms_deg = 6.0f;
  p->off_mean_deg = 2.5f;
  p->off_same_sign = 0.85f;
  p->grow_trend = 1.0f;
  p->grow_ratio = 1.5f;
  p->grow_min_rms = 1.5f;
}

svmg_class_t svmg_baseline_b(const svmg_baseline_params_t *p, const svmg_features_t *f) {
  if (f->rms_roll_deg >= p->hi_rms_deg) return SVMG_HIGH_ROLL;
  if (f->trend_rms_deg_per_min >= p->grow_trend && f->rms_ratio >= p->grow_ratio &&
      f->rms_roll_deg >= p->grow_min_rms) return SVMG_AMPLITUDE_GROWTH;
  if (fabsf(f->mean_roll_deg) >= p->off_mean_deg && f->same_sign_ratio >= p->off_same_sign) return SVMG_PERSISTENT_OFFSET;
  return SVMG_NORMAL;
}
