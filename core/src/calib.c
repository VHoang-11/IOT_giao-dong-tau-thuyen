/* calib.c - M1-07. Xem svmg_calib.h. */
#include "svmg_calib.h"
#include <math.h>
#include <string.h>

void svmg_calib_init(svmg_calib_t *c) { memset(c, 0, sizeof *c); c->result = SVMG_R_OK; }

void svmg_calib_start(svmg_calib_t *c) {
  memset(c, 0, sizeof *c);
  c->active = 1;
  c->result = SVMG_R_OK;
}

void svmg_calib_abort(svmg_calib_t *c) { c->active = 0; }

int svmg_calib_push(svmg_calib_t *c, float roll, float pitch, uint8_t valid) {
  if (!c->active) return 0;
  if (valid && isfinite(roll) && isfinite(pitch)) {
    c->n++;
    float d = roll - c->mean_r;  c->mean_r += d / c->n;  c->m2_r += d * (roll - c->mean_r);
    float e = pitch - c->mean_p; c->mean_p += e / c->n;  c->m2_p += e * (pitch - c->mean_p);
  } else {
    c->n_invalid++;
  }
  if ((uint16_t)(c->n + c->n_invalid) < SVMG_CALIB_SAMPLES) return 0;

  c->active = 0;
  c->result_roll_deg = c->mean_r;
  c->result_pitch_deg = c->mean_p;
  if (c->n_invalid * 10u > SVMG_CALIB_SAMPLES || c->n < 2) { c->result = SVMG_R_FORBIDDEN_STATE; return 1; }
  float sr = sqrtf(c->m2_r / (float)(c->n - 1)), sp = sqrtf(c->m2_p / (float)(c->n - 1));
  if (sr > SVMG_CALIB_STD_MAX_DEG || sp > SVMG_CALIB_STD_MAX_DEG) { c->result = SVMG_R_NOT_STATIC; return 1; }
  if (fabsf(c->mean_r) > SVMG_ZERO_LIMIT_DEG || fabsf(c->mean_p) > SVMG_ZERO_LIMIT_DEG) { c->result = SVMG_R_FORBIDDEN_STATE; return 1; }
  c->result = SVMG_R_OK;
  return 1;
}
