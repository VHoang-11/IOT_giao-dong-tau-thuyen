/* alarm_fsm.c - M1-05. Xem svmg_alarm.h. */
#include "svmg_alarm.h"
#include <string.h>

const char *svmg_level_name(svmg_level_t l) {
  switch (l) {
    case SVMG_LVL_NORMAL: return "NORMAL";
    case SVMG_LVL_CAUTION: return "CAUTION";
    case SVMG_LVL_WARNING: return "WARNING";
    case SVMG_LVL_CRITICAL: return "CRITICAL";
  }
  return "?";
}

const char *svmg_class_name(svmg_class_t c) {
  switch (c) {
    case SVMG_NORMAL: return "NORMAL";
    case SVMG_HIGH_ROLL: return "HIGH_ROLL";
    case SVMG_PERSISTENT_OFFSET: return "PERSISTENT_OFFSET";
    case SVMG_AMPLITUDE_GROWTH: return "AMPLITUDE_GROWTH";
    case SVMG_UNKNOWN: return "UNKNOWN";
    case SVMG_FAULT: return "FAULT";
  }
  return "?";
}

void svmg_alarm_default_cfg(svmg_alarm_cfg_t *c) {
  c->debounce_n = 3;
  c->mai_caution = 80;
  c->clear_updates = 6;
  c->max_mute_s = 300;
  c->t_ack_ms = 60000u;
}

void svmg_alarm_set_cfg(svmg_alarm_t *a, const svmg_alarm_cfg_t *c) {
  a->cfg = *c;
  if (a->cfg.debounce_n < 1) a->cfg.debounce_n = 1;
  if (a->cfg.clear_updates < 1) a->cfg.clear_updates = 1;
  if (a->cfg.max_mute_s > 300) a->cfg.max_mute_s = 300;       /* trần cứng theo đặc tả */
}

void svmg_alarm_init(svmg_alarm_t *a, const svmg_alarm_cfg_t *c) {
  memset(a, 0, sizeof *a);
  svmg_alarm_set_cfg(a, c);
  a->level = SVMG_LVL_NORMAL;
  a->cls = SVMG_NORMAL;
  a->streak_cls = SVMG_NORMAL;
  a->status = SVMG_ST_UNKNOWN;     /* chưa có dữ liệu: không hiển thị như bình thường */
  a->next_id = 1;
}

/* ---- tiện ích sự kiện ---- */
typedef struct { svmg_event_t *ev; int n; } evw_t;

static void emit(evw_t *w, svmg_event_type_t type, const svmg_alarm_t *a, svmg_level_t prev, uint8_t acked_by, uint16_t val, uint32_t alarm_id) {
  if (w->n >= SVMG_ALARM_MAX_EVENTS) return;
  svmg_event_t *e = &w->ev[w->n++];
  memset(e, 0, sizeof *e);
  e->type = (uint8_t)type;
  e->level = (uint8_t)a->level;
  e->prev_level = (uint8_t)prev;
  e->cls = (uint8_t)a->cls;
  e->alarm_id = alarm_id;
  e->t_sim_s = a->t_sim_s;
  e->acked_by = acked_by;
  e->val = val;
}

static int is_anomaly(svmg_class_t c) {
  return c == SVMG_HIGH_ROLL || c == SVMG_PERSISTENT_OFFSET || c == SVMG_AMPLITUDE_GROWTH;
}

/* Chuyển sang mức mới (mức mới khác mức hiện tại). */
static void go(svmg_alarm_t *a, evw_t *w, svmg_level_t to, uint32_t now_ms) {
  svmg_level_t prev = a->level;
  uint32_t id = a->alarm_id;
  if (to == SVMG_LVL_NORMAL) {
    a->level = to;
    emit(w, SVMG_EV_ALARM_STATE, a, prev, SVMG_ACKBY_NONE, 0, id);     /* CLEARED */
    if (id) a->n_cleared++;
    a->alarm_id = 0; a->acked = 0; a->muted = 0; a->cls = SVMG_NORMAL; a->clear_count = 0;
    return;
  }
  if (to >= SVMG_LVL_WARNING) {
    if (a->alarm_id == 0) { a->alarm_id = a->next_id++; a->n_raised++; a->raised_ms = now_ms; }
    if (to == SVMG_LVL_CRITICAL && prev != SVMG_LVL_CRITICAL) {
      a->acked = 0; a->muted = 0;                    /* mức mới cao hơn -> phải được xác nhận lại */
    }
    if (prev < SVMG_LVL_WARNING) { a->acked = 0; a->muted = 0; }
  }
  a->level = to;
  emit(w, SVMG_EV_ALARM_STATE, a, prev, SVMG_ACKBY_NONE, 0, a->alarm_id);
}

int svmg_alarm_update(svmg_alarm_t *a, const svmg_alarm_in_t *in, svmg_event_t *ev) {
  evw_t w = { ev, 0 };
  a->t_sim_s = in->t_sim_s;
  a->status = in->status;

  int ok = (in->status == SVMG_ST_OK);
  int anomaly = ok && is_anomaly(in->cls);
  int mai_high = ok && in->mai_valid && in->mai >= a->cfg.mai_caution;
  int cond = anomaly || mai_high || in->hard;

  if (ok) {
    if (anomaly) {
      if (in->cls == a->streak_cls && a->streak > 0) { if (a->streak < 255) a->streak++; }
      else { a->streak_cls = in->cls; a->streak = 1; }
      a->cls = in->cls;
    } else { a->streak = 0; a->streak_cls = SVMG_NORMAL; }
  }                                 /* UNKNOWN/FAULT: giữ nguyên chuỗi đếm, không tiến tới giải tỏa */

  svmg_level_t target = SVMG_LVL_NORMAL;
  if (in->hard) target = SVMG_LVL_CRITICAL;
  else if (anomaly && a->streak >= a->cfg.debounce_n) target = SVMG_LVL_WARNING;
  else if (anomaly || mai_high) target = SVMG_LVL_CAUTION;

  if (cond) a->clear_count = 0;
  else if (ok && a->clear_count < 255) a->clear_count++;

  if (target > a->level) {
    if (in->hard && a->cls == SVMG_NORMAL) a->cls = in->cls;
    if (target == SVMG_LVL_CRITICAL && a->level == SVMG_LVL_WARNING) a->n_escalated++;
    go(a, &w, target, in->now_ms);
  } else if (a->level != SVMG_LVL_NORMAL && !cond && a->clear_count >= a->cfg.clear_updates) {
    go(a, &w, SVMG_LVL_NORMAL, in->now_ms);
  }
  return w.n;
}

int svmg_alarm_force_critical(svmg_alarm_t *a, float t_sim_s, uint32_t now_ms, svmg_event_t *ev) {
  evw_t w = { ev, 0 };
  a->t_sim_s = t_sim_s;
  a->clear_count = 0;
  if (a->level < SVMG_LVL_CRITICAL) {
    if (a->level == SVMG_LVL_WARNING) a->n_escalated++;
    go(a, &w, SVMG_LVL_CRITICAL, now_ms);
  }
  return w.n;
}

int svmg_alarm_tick(svmg_alarm_t *a, uint32_t now_ms, svmg_event_t *ev) {
  evw_t w = { ev, 0 };
  if (a->muted && (int32_t)(now_ms - a->mute_until_ms) >= 0) a->muted = 0;
  if (a->level == SVMG_LVL_WARNING && !a->acked && (uint32_t)(now_ms - a->raised_ms) >= a->cfg.t_ack_ms) {
    a->n_escalated++;
    go(a, &w, SVMG_LVL_CRITICAL, now_ms);
  }
  return w.n;
}

int svmg_alarm_ack(svmg_alarm_t *a, uint8_t by, uint32_t now_ms, svmg_event_t *ev, svmg_reason_t *res) {
  evw_t w = { ev, 0 };
  if (res) *res = SVMG_R_OK;
  if (a->level >= SVMG_LVL_WARNING && !a->acked) {
    a->acked = 1; a->muted = 0; a->ack_ms = now_ms;
    a->n_acked++;
    a->sum_ack_ms += (uint32_t)(now_ms - a->raised_ms);
    emit(&w, SVMG_EV_ALARM_ACK, a, a->level, by, 0, a->alarm_id);
  }
  return w.n;
}

int svmg_alarm_mute(svmg_alarm_t *a, uint16_t duration_s, uint32_t now_ms, svmg_event_t *ev, svmg_reason_t *res) {
  evw_t w = { ev, 0 };
  if (duration_s < 1 || duration_s > a->cfg.max_mute_s) { if (res) *res = SVMG_R_BAD_PARAM; return 0; }
  if (a->level != SVMG_LVL_WARNING || a->acked) { if (res) *res = SVMG_R_FORBIDDEN_STATE; return 0; }
  a->muted = 1;
  a->mute_until_ms = now_ms + (uint32_t)duration_s * 1000u;
  if (res) *res = SVMG_R_OK;
  emit(&w, SVMG_EV_ALARM_MUTE, a, a->level, SVMG_ACKBY_NONE, duration_s, a->alarm_id);
  return w.n;
}

void svmg_alarm_outputs(const svmg_alarm_t *a, uint32_t now_ms, svmg_alarm_out_t *o) {
  o->led_g = o->led_y = o->led_r = SVMG_OUT_OFF;
  o->buzzer = SVMG_BUZ_OFF;
  switch (a->level) {
    case SVMG_LVL_NORMAL:
      if (a->status == SVMG_ST_OK) o->led_g = SVMG_OUT_ON;                    /* bình thường */
      else if (a->status == SVMG_ST_UNKNOWN) o->led_y = SVMG_OUT_BLINK_SLOW;  /* chưa biết: không được báo xanh */
      else { o->led_y = SVMG_OUT_BLINK_FAST; o->led_r = SVMG_OUT_BLINK_FAST; }/* lỗi cảm biến */
      break;
    case SVMG_LVL_CAUTION: o->led_y = SVMG_OUT_ON; break;
    case SVMG_LVL_WARNING:
    case SVMG_LVL_CRITICAL: o->led_r = SVMG_OUT_ON; break;                    /* ACK vẫn giữ đèn */
  }
  int muted = a->muted && (int32_t)(now_ms - a->mute_until_ms) < 0;
  if (!a->acked) {
    if (a->level == SVMG_LVL_CRITICAL) o->buzzer = SVMG_BUZ_CONTINUOUS;       /* không thể mute */
    else if (a->level == SVMG_LVL_WARNING && !muted) o->buzzer = SVMG_BUZ_INTERMITTENT;
  }
}
