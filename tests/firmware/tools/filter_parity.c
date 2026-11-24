/* Test adapter only. No hardware libraries; exercises the production C
 * pipeline. */
#include "svmg_filter.h"
#include <math.h>
int check_pipeline(const float *r, const float *p, const float *gx,
                   const float *gy, int n, float *ro, float *po) {
  svmg_pipeline_t pipe;
  svmg_pipeline_cfg_t cfg;
  svmg_pipeline_default_cfg(&cfg);
  svmg_pipeline_init(&pipe, &cfg);
  int m = 0;
  for (int i = 0; i < n; i++) {
    svmg_motion_sample_t s = {0};
    s.t = (float)i / 20;
    s.valid = 1;
    s.ax = -SVMG_G * sinf(p[i]);
    s.ay = SVMG_G * sinf(r[i]) * cosf(p[i]);
    s.az = SVMG_G * cosf(r[i]) * cosf(p[i]);
    s.gx = gx[i];
    s.gy = gy[i];
    svmg_sample10hz_t o;
    if (svmg_pipeline_push(&pipe, &s, &o)) {
      ro[m] = o.roll_rad;
      po[m] = o.pitch_rad;
      m++;
    }
  }
  return m;
}
