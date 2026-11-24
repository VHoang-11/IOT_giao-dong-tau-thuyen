/* Baseline B uses the same 23 angle features as RF. Demo defaults need M2
 * validation. */
#include "svmg_contract.h"
#include "svmg_decision.h"
#include <math.h>
void svmg_baseline_default(svmg_baseline_params_t *p) {
  p->hi_dyn_rms_deg = 6;
  p->grow_slope = 1;
  p->grow_min_rms = 1.5f;
  p->grow_max_heel_s = 0;
  p->off_mean_deg = 1.5f;
  p->off_heel_s = 120;
}
float svmg_baseline_dyn_rms(const svmg_features_t *f) { return f->roll_std_60; }
svmg_class_t svmg_baseline_b(const svmg_baseline_params_t *p,
                             const svmg_features_t *f) {
  float dyn = f->roll_std_60, mean = f->roll_mean_60, offset = f->roll_mean_180;
  if (!isfinite(dyn) || !isfinite(mean) || !isfinite(offset))
    return SVMG_UNKNOWN;
  if (dyn >= p->hi_dyn_rms_deg)
    return SVMG_HIGH_ROLL;
  /* Raw RMS slope is NOT centered RMS. Suppress offset-driven growth using the
   * short mean. */
  if (isfinite(f->roll_rms_slope_180) &&
      f->roll_rms_slope_180 >= p->grow_slope && dyn >= p->grow_min_rms &&
      fabsf(mean) < p->off_mean_deg)
    return SVMG_AMPLITUDE_GROWTH;
  /* Equivalent-duration heuristic, not a measured continuous heel duration. */
  float duration =
      fabsf(mean) > 1e-6f ? 180.0f * fminf(1.0f, fabsf(offset / mean)) : 0;
  if (fabsf(mean) >= p->off_mean_deg && fabsf(offset) >= p->off_mean_deg &&
      mean * offset > 0 && f->roll_dominant_sign_ratio_180 >= 0.75f &&
      duration > p->off_heel_s)
    return SVMG_PERSISTENT_OFFSET;
  return SVMG_NORMAL;
}
MotionClass classifyBaselineB(const FeatureVector *fv) {
  svmg_features_t f;
  svmg_features_from_contract(fv, &f);
  svmg_baseline_params_t p;
  svmg_baseline_default(&p);
  return (MotionClass)svmg_baseline_b(&p, &f);
}
