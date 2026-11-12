/* engine.c - xem svmg_engine.h. */
#include "svmg_engine.h"
#include <string.h>
#include <math.h>

static void out_clear(svmg_engine_out_t *o) { memset(o, 0, sizeof *o); }

static void out_add(svmg_engine_out_t *o, const svmg_event_t *ev, int n) {
  for (int i = 0; i < n && o->n_ev < SVMG_ENGINE_MAX_EV; i++) o->ev[o->n_ev++] = ev[i];
}

static void out_add_sys(svmg_engine_out_t *o, svmg_event_type_t type, float t, uint16_t val, uint8_t aux) {
  if (o->n_ev >= SVMG_ENGINE_MAX_EV) return;
  svmg_event_t *e = &o->ev[o->n_ev++];
  memset(e, 0, sizeof *e);
  e->type = (uint8_t)type; e->t_sim_s = t; e->val = val; e->aux = aux;
}

void svmg_engine_init(svmg_engine_t *e, const svmg_config_t *cfg) {
  memset(e, 0, sizeof *e);
  e->cfg = *cfg;
  svmg_pipeline_cfg_t pc; svmg_pipeline_default_cfg(&pc);
  svmg_pipeline_init(&e->pipe, &pc);
  svmg_window_clear(&e->win);
  svmg_safety_init(&e->safety, (float)cfg->phi_hard_deg);
  svmg_alarm_cfg_t ac; svmg_config_to_alarm(cfg, &ac);
  svmg_alarm_init(&e->alarm, &ac);
  svmg_calib_init(&e->calib);
  svmg_baseline_default(&e->bp);
  svmg_mai_default(&e->mp);
  svmg_quality_default(&e->qc);
  e->dec.cls_rf = e->dec.cls_b = e->dec.cls_primary = SVMG_UNKNOWN;
  e->dec.status = SVMG_ST_UNKNOWN;
  e->prev_status = SVMG_ST_UNKNOWN;
}

void svmg_engine_set_rf(svmg_engine_t *e, svmg_rf_fn fn, void *ctx) { e->rf = fn; e->rf_ctx = ctx; }

void svmg_engine_apply_config(svmg_engine_t *e, const svmg_config_t *cfg) {
  float old_zero = e->cfg.zero_roll_deg;
  e->cfg = *cfg;
  svmg_alarm_cfg_t ac; svmg_config_to_alarm(cfg, &ac);
  svmg_alarm_set_cfg(&e->alarm, &ac);
  svmg_safety_set_phi(&e->safety, (float)cfg->phi_hard_deg);
  if (cfg->zero_roll_deg != old_zero) svmg_window_shift_roll(&e->win, old_zero - cfg->zero_roll_deg);
}

void svmg_engine_restart_signal(svmg_engine_t *e) {
  svmg_pipeline_reset(&e->pipe);
  svmg_window_clear(&e->win);
  svmg_safety_reset(&e->safety);
  svmg_calib_abort(&e->calib);
  e->dec.status = SVMG_ST_UNKNOWN;
}

svmg_reason_t svmg_engine_calibrate_start(svmg_engine_t *e) {
  if (e->calib.active) return SVMG_R_FORBIDDEN_STATE;
  /* Không cho hiệu chuẩn khi đang có cảnh báo WARNING/CRITICAL: lệnh này không được dùng để "xóa" bằng chứng
   * của một nghiêng lệch thật (đề cương 8.5: chỉ để tránh nhầm lệch lắp đặt cảm biến). */
  if (e->alarm.level >= SVMG_LVL_WARNING) return SVMG_R_FORBIDDEN_STATE;
  svmg_calib_start(&e->calib);
  return SVMG_R_PENDING;
}

float svmg_engine_agreement(const svmg_engine_t *e) {
  return e->n_compared ? (float)e->n_agree / (float)e->n_compared : 1.0f;
}

static void decide(svmg_engine_t *e, uint32_t now_ms, svmg_engine_out_t *out) {
  svmg_decision_state_t *d = &e->dec;
  svmg_features_compute(&e->win, &d->feat);
  uint8_t why = 0;
  svmg_status_t st = svmg_features_status(&d->feat, &e->qc, &why);
  d->status_reason = why;
  d->model_fallback = (e->cfg.primary_model == SVMG_MODEL_RF && e->rf == NULL) ? 1 : 0;

  if (st == SVMG_ST_OK) {
    float vec[SVMG_N_FEATURES];
    svmg_features_to_vector(&d->feat, vec);
    d->cls_rf = e->rf ? e->rf(e->rf_ctx, vec, SVMG_N_FEATURES) : SVMG_UNKNOWN;
    d->cls_b = svmg_baseline_b(&e->bp, &d->feat);
    svmg_mai_compute(&e->mp, &d->feat, &d->mai);
    int use_rf = (e->cfg.primary_model == SVMG_MODEL_RF) && e->rf;
    d->cls_primary = use_rf ? d->cls_rf : d->cls_b;
    if (d->cls_primary == SVMG_UNKNOWN) st = SVMG_ST_UNKNOWN;       /* mô hình không đủ tin cậy: không được coi là NORMAL */
    if (d->cls_rf != SVMG_UNKNOWN) {
      e->n_compared++;
      if (d->cls_rf == d->cls_b) e->n_agree++;
    }
  } else {
    d->cls_rf = d->cls_b = d->cls_primary = (st == SVMG_ST_FAULT) ? SVMG_FAULT : SVMG_UNKNOWN;
    memset(&d->mai, 0, sizeof d->mai);
  }
  d->status = st;
  d->hard = e->safety.active;
  e->n_updates++;

  if (st == SVMG_ST_FAULT && e->prev_status != SVMG_ST_FAULT) out_add_sys(out, SVMG_EV_FAULT, d->t_sim_s, why, 0);
  if (st != SVMG_ST_FAULT && e->prev_status == SVMG_ST_FAULT) out_add_sys(out, SVMG_EV_FAULT_CLEARED, d->t_sim_s, why, 0);
  e->prev_status = st;

  svmg_alarm_in_t in;
  in.cls = d->cls_primary; in.status = st; in.mai = d->mai.value; in.mai_valid = (st == SVMG_ST_OK);
  in.hard = d->hard; in.t_sim_s = d->t_sim_s; in.now_ms = now_ms;
  svmg_event_t ev[SVMG_ALARM_MAX_EVENTS];
  int n = svmg_alarm_update(&e->alarm, &in, ev);
  out_add(out, ev, n);
  out->got_update = 1;
}

int svmg_engine_push(svmg_engine_t *e, const svmg_motion_sample_t *s, uint32_t now_ms, svmg_engine_out_t *out) {
  out_clear(out);
  svmg_sample2hz_t s2;
  if (!svmg_pipeline_push(&e->pipe, s, &s2)) return 0;
  out->got_2hz = 1;

  if (s2.flags & SVMG_PIPE_F_RESTARTED) {          /* khoảng trống dữ liệu: bỏ lịch sử cũ, không trộn hai đoạn */
    svmg_window_clear(&e->win);
    svmg_safety_reset(&e->safety);
    svmg_calib_abort(&e->calib);
  }

  uint8_t valid = (s2.n_valid >= SVMG_BLOCK_MIN_VALID) ? 1 : 0;
  float roll_raw = s2.roll_rad * SVMG_RAD2DEG, pitch_raw = s2.pitch_rad * SVMG_RAD2DEG;
  float roll = roll_raw - e->cfg.zero_roll_deg, pitch = pitch_raw - e->cfg.zero_pitch_deg;
  svmg_decision_state_t *d = &e->dec;
  d->t_sim_s = s2.t_s;
  if (valid) { d->roll_deg = roll; d->pitch_deg = pitch; }

  if (e->calib.active && svmg_calib_push(&e->calib, roll_raw, pitch_raw, valid)) {
    out->calib_done = 1;
    out->calib_result = e->calib.result;
    if (e->calib.result == SVMG_R_OK) {
      float old_r = e->cfg.zero_roll_deg;
      e->cfg.zero_roll_deg = e->calib.result_roll_deg;
      e->cfg.zero_pitch_deg = e->calib.result_pitch_deg;
      svmg_window_shift_roll(&e->win, old_r - e->cfg.zero_roll_deg);
    }
    out_add_sys(out, SVMG_EV_CALIBRATION, s2.t_s, (uint16_t)e->calib.result, 0);
  }

  if (svmg_safety_push(&e->safety, s2.t_s, roll, valid)) {      /* cạnh lên: không chờ chu kỳ 5 s */
    svmg_event_t ev[SVMG_ALARM_MAX_EVENTS];
    int n = svmg_alarm_force_critical(&e->alarm, s2.t_s, now_ms, ev);
    out_add(out, ev, n);
  }

  float gx_dps = s2.gx_rads * SVMG_RAD2DEG, gy_dps = s2.gy_rads * SVMG_RAD2DEG;
  if (svmg_window_push(&e->win, roll, gx_dps, gy_dps, valid)) decide(e, now_ms, out);
  return out->n_ev;
}

int svmg_engine_tick(svmg_engine_t *e, uint32_t now_ms, svmg_engine_out_t *out) {
  out_clear(out);
  svmg_event_t ev[SVMG_ALARM_MAX_EVENTS];
  int n = svmg_alarm_tick(&e->alarm, now_ms, ev);
  out_add(out, ev, n);
  return out->n_ev;
}

int svmg_engine_ack(svmg_engine_t *e, uint8_t by, uint32_t now_ms, svmg_engine_out_t *out) {
  out_clear(out);
  svmg_event_t ev[SVMG_ALARM_MAX_EVENTS];
  int n = svmg_alarm_ack(&e->alarm, by, now_ms, ev, NULL);
  out_add(out, ev, n);
  return out->n_ev;
}

int svmg_engine_mute(svmg_engine_t *e, uint16_t duration_s, uint32_t now_ms, svmg_engine_out_t *out, svmg_reason_t *res) {
  out_clear(out);
  svmg_event_t ev[SVMG_ALARM_MAX_EVENTS];
  int n = svmg_alarm_mute(&e->alarm, duration_s, now_ms, ev, res);
  out_add(out, ev, n);
  return out->n_ev;
}
