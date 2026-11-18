/* mai.c - M1-04: Motion Anomaly Index (0-100).
 * MAI = 100 * min(1, max(r_amp, r_off, r_trend)); r_amp = rms_roll/A_ref, r_off = |mean_roll|/B_ref,
 * r_trend = max(0, trend_rms_slope)/G_ref. Phần tử lớn nhất cho biết thành phần chi phối. Không phải xác suất rủi ro. */
#include "svmg_decision.h"
#include "svmg_contract.h"
#include <math.h>

void svmg_mai_default(svmg_mai_params_t *p) {
  p->a_ref_deg = 8.0f;
  p->b_ref_deg = 5.0f;
  p->g_ref_deg_per_min = 2.0f;
}

void svmg_mai_compute(const svmg_mai_params_t *p, const svmg_features_t *f, svmg_mai_t *o) {
  o->r_amp = f->roll_rms_60 / p->a_ref_deg;
  o->r_off = fabsf(f->roll_mean_180) / p->b_ref_deg;
  o->r_trend = (f->roll_rms_slope_180 > 0.0f ? f->roll_rms_slope_180 : 0.0f) / p->g_ref_deg_per_min;
  float m = o->r_amp; o->dominant = 0;
  if (o->r_off > m) { m = o->r_off; o->dominant = 1; }
  if (o->r_trend > m) { m = o->r_trend; o->dominant = 2; }
  if (!(m > 0.0f)) m = 0.0f;           /* cũng bắt NaN */
  if (m > 1.0f) m = 1.0f;
  o->value = (uint8_t)(100.0f * m + 0.5f);
}

/* API của svmg_core.h: tham số mặc định. */
int computeMAI(const FeatureVector *fv) {
  svmg_mai_params_t p; svmg_mai_default(&p);
  svmg_features_t f; svmg_features_from_contract(fv, &f);
  svmg_mai_t m; svmg_mai_compute(&p, &f, &m);
  return (int)m.value;
}
