/* filter.c - M1-02. Xem svmg_filter.h. C99, float, không malloc. */
#include "svmg_filter.h"
#include <math.h>

/* ---------------- 1. IMU thô -> SI ---------------- */
static int is_sat(int16_t v) { return v == INT16_MIN || v == INT16_MAX; }

uint8_t svmg_imu_raw_to_si(const svmg_imu_raw_t *r, svmg_motion_sample_t *o) {
  const float ka = SVMG_G / SVMG_IMU_ACCEL_LSB_PER_G;
  const float kg = SVMG_DEG2RAD / SVMG_IMU_GYRO_LSB_PER_DPS;
  uint8_t f = 0;
  o->ax = (float)r->ax * ka;  o->ay = (float)r->ay * ka;  o->az = (float)r->az * ka;
  o->gx = (float)r->gx * kg;  o->gy = (float)r->gy * kg;  o->gz = (float)r->gz * kg;
  if (is_sat(r->ax) || is_sat(r->ay) || is_sat(r->az) ||
      is_sat(r->gx) || is_sat(r->gy) || is_sat(r->gz)) f |= SVMG_IMU_F_SATURATED;
  o->valid = 1;
  return f;
}

/* ---------------- 2. Góc từ gia tốc ---------------- */
void svmg_accel_to_angles(float ax, float ay, float az, float *roll, float *pitch) {
  *roll  = atan2f(ay, az);
  *pitch = atan2f(-ax, sqrtf(ay * ay + az * az));
}

uint8_t svmg_accel_gate_ok(float ax, float ay, float az) {
  float n = sqrtf(ax * ax + ay * ay + az * az);
  return (n >= 0.5f * SVMG_G && n <= 1.5f * SVMG_G) ? 1 : 0;
}

/* ---------------- 3. Bộ lọc bù ---------------- */
void svmg_cf_reset(svmg_cf_t *cf) { cf->roll = 0.0f; cf->pitch = 0.0f; cf->initialized = 0; }

void svmg_cf_init(svmg_cf_t *cf, float tau_s) { cf->tau_s = tau_s; svmg_cf_reset(cf); }

uint8_t svmg_cf_update(svmg_cf_t *cf, float ax, float ay, float az, float gx, float gy, float dt) {
  uint8_t gate = svmg_accel_gate_ok(ax, ay, az);
  if (!cf->initialized) {
    if (!gate) return SVMG_CF_NOT_INIT;
    svmg_accel_to_angles(ax, ay, az, &cf->roll, &cf->pitch);
    cf->initialized = 1;
    return 0;
  }
  float r_g = cf->roll  + gx * dt;
  float p_g = cf->pitch + gy * dt;
  if (!gate) { cf->roll = r_g; cf->pitch = p_g; return SVMG_CF_GATED; }
  float alpha = cf->tau_s / (cf->tau_s + dt);
  float ra, pa;
  svmg_accel_to_angles(ax, ay, az, &ra, &pa);
  cf->roll  = alpha * r_g + (1.0f - alpha) * ra;
  cf->pitch = alpha * p_g + (1.0f - alpha) * pa;
  return 0;
}

/* ---------------- 4. Biquad Butterworth thông thấp ---------------- */
void svmg_biquad_butter2_lp(svmg_biquad_coef_t *c, float fc, float fs) {
  float k = tanf(SVMG_PI * fc / fs);
  float k2 = k * k;
  float s2k = 1.41421356f * k;
  float norm = 1.0f / (1.0f + s2k + k2);
  c->a1 = 2.0f * (k2 - 1.0f) * norm;
  c->a2 = (1.0f - s2k + k2) * norm;
  /* Mẫu số 1+a1+a2 ~ 0.022 bị triệt tiêu mạnh nên làm tròn float ở a1,a2 làm lệch độ lợi DC ~5e-6.
   * Ép độ lợi DC = 1 chính xác theo a1,a2 đã làm tròn: b0 = b2 = (1+a1+a2)/4, b1 = 2 b0.
   * (Chỉ chạy một lần lúc thiết kế nên dùng double có chủ ý.) */
  double dc = 1.0 + (double)c->a1 + (double)c->a2;
  c->b0 = (float)(dc * 0.25);
  c->b1 = 2.0f * c->b0;
  c->b2 = c->b0;
}

void svmg_biquad_init(svmg_biquad_t *f, const svmg_biquad_coef_t *c, float x0) {
  f->c = *c;
  /* Độ lợi DC = 1: y = x0, z1 = (1-b0) x0, z2 = (b2-a2) x0. */
  f->z1 = (1.0f - c->b0) * x0;
  f->z2 = (c->b2 - c->a2) * x0;
}

float svmg_biquad_step(svmg_biquad_t *f, float x) {
  float y = f->c.b0 * x + f->z1;
  f->z1 = f->c.b1 * x - f->c.a1 * y + f->z2;
  f->z2 = f->c.b2 * x - f->c.a2 * y;
  return y;
}

/* ---------------- 5. Pipeline ---------------- */
void svmg_pipeline_default_cfg(svmg_pipeline_cfg_t *cfg) {
  cfg->tau_s = 7.5f;
  cfg->fc_hz = 0.5f;
  cfg->fs_hz = 20.0f;
  cfg->max_gap_s = 0.5f;
  cfg->decim = 10;
}

static void pipe_clear(svmg_pipeline_t *p) {
  svmg_cf_reset(&p->cf);
  p->lp_init = 0;
  p->phase = 0; p->n_valid = 0; p->blk_flags = 0;
  for (int i = 0; i < 4; i++) p->y[i] = 0.0f;
}

void svmg_pipeline_reset(svmg_pipeline_t *p) {
  pipe_clear(p);
  p->pending_restart = 0;
  p->have_t = 0;
}

void svmg_pipeline_init(svmg_pipeline_t *p, const svmg_pipeline_cfg_t *cfg) {
  p->cfg = *cfg;
  if (p->cfg.decim == 0) p->cfg.decim = 1;
  svmg_cf_init(&p->cf, cfg->tau_s);
  svmg_biquad_butter2_lp(&p->coef, cfg->fc_hz, cfg->fs_hz);
  p->cnt_in = p->cnt_invalid = p->cnt_gap = p->cnt_out = 0;
  p->last_t = 0.0f;
  svmg_pipeline_reset(p);
}

static int all_finite(const svmg_motion_sample_t *s) {
  return isfinite(s->ax) && isfinite(s->ay) && isfinite(s->az) &&
         isfinite(s->gx) && isfinite(s->gy) && isfinite(s->gz);
}

int svmg_pipeline_push(svmg_pipeline_t *p, const svmg_motion_sample_t *s, svmg_sample2hz_t *out) {
  const float nominal_dt = 1.0f / p->cfg.fs_hz;
  float dt = nominal_dt;
  p->cnt_in++;

  if (isfinite(s->t)) {
    if (p->have_t) {
      dt = s->t - p->last_t;
      if (dt < -SVMG_PIPE_WRAP_S) dt = nominal_dt;   /* đồng hồ float quấn vòng (firmware giữ t < 8192 s để không mất độ phân giải) */
      if (!(dt > 0.0f) || dt > p->cfg.max_gap_s) {   /* khoảng trống/đi lùi -> khởi động lại */
        pipe_clear(p);
        p->cnt_gap++;
        p->pending_restart = 1;
        dt = nominal_dt;
      }
    }
    p->last_t = s->t;
    p->have_t = 1;
  }

  if (s->valid && all_finite(s)) {
    uint8_t f = svmg_cf_update(&p->cf, s->ax, s->ay, s->az, s->gx, s->gy, dt);
    if (f & SVMG_CF_NOT_INIT) {
      p->cnt_invalid++;
    } else {
      float in[4] = { p->cf.roll, p->cf.pitch, s->gx, s->gy };
      int gated = (f & SVMG_CF_GATED) != 0;
      if (gated) p->blk_flags |= SVMG_PIPE_F_GATED;
      if (!p->lp_init) {
        for (int i = 0; i < 4; i++) { svmg_biquad_init(&p->lp[i], &p->coef, in[i]); p->y[i] = in[i]; }
        p->lp_init = 1;
      } else {
        for (int i = 0; i < 4; i++) p->y[i] = svmg_biquad_step(&p->lp[i], in[i]);
      }
      /* Bước bị cổng (|a| ngoài [0.5 g, 1.5 g]) vẫn cho bộ lọc đi tiếp bằng gyro nhưng KHÔNG tính là phép đo hợp lệ:
       * bus I2C chết (trả toàn 0) hay cảm biến rơi tự do kéo dài phải dẫn tới FAULT, không được "giữ nguyên" mãi. */
      if (gated) p->cnt_invalid++; else p->n_valid++;
    }
  } else {
    p->cnt_invalid++;
  }

  if (++p->phase < p->cfg.decim) return 0;

  out->t_s = p->last_t;
  out->roll_rad = p->y[0];  out->pitch_rad = p->y[1];
  out->gx_rads = p->y[2];   out->gy_rads = p->y[3];
  out->n_valid = p->n_valid;
  out->flags = p->blk_flags;
  if (p->n_valid < p->cfg.decim) out->flags |= SVMG_PIPE_F_PARTIAL;
  if (p->pending_restart) out->flags |= SVMG_PIPE_F_RESTARTED;
  p->phase = 0; p->n_valid = 0; p->blk_flags = 0; p->pending_restart = 0;
  p->cnt_out++;
  return 1;
}
