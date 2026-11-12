/* cmd.c - M1-07. Xem svmg_cmd.h. */
#include "svmg_cmd.h"
#include <string.h>

const char *svmg_reason_name(svmg_reason_t r) {
  switch (r) {
    case SVMG_R_OK: return "OK";
    case SVMG_R_BAD_PARAM: return "BAD_PARAM";
    case SVMG_R_FORBIDDEN_STATE: return "FORBIDDEN_STATE";
    case SVMG_R_NOT_STATIC: return "NOT_STATIC";
    case SVMG_R_EXPIRED: return "EXPIRED";
    case SVMG_R_UNSUPPORTED: return "UNSUPPORTED";
    default: return "?";
  }
}

void svmg_cmd_init(svmg_cmd_ctx_t *c) { memset(c, 0, sizeof *c); }

static svmg_cmd_slot_t *find(svmg_cmd_ctx_t *c, const char *id) {
  for (int i = 0; i < SVMG_CMD_CACHE; i++)
    if (c->slot[i].state && strncmp(c->slot[i].id, id, SVMG_CMD_ID_LEN) == 0) return &c->slot[i];
  return NULL;
}

static svmg_cmd_slot_t *alloc_slot(svmg_cmd_ctx_t *c, const char *id) {
  /* Ưu tiên ô trống; nếu không, ghi đè ô đã xong cũ nhất theo vòng; không bao giờ ghi đè lệnh đang chờ nếu còn ô khác. */
  svmg_cmd_slot_t *s = NULL;
  for (int i = 0; i < SVMG_CMD_CACHE; i++) if (!c->slot[i].state) { s = &c->slot[i]; break; }
  if (!s) {
    for (int k = 0; k < SVMG_CMD_CACHE; k++) {
      uint8_t idx = (uint8_t)((c->next + k) % SVMG_CMD_CACHE);
      if (c->slot[idx].state == 2) { s = &c->slot[idx]; c->next = (uint8_t)((idx + 1) % SVMG_CMD_CACHE); break; }
    }
  }
  if (!s) { s = &c->slot[c->next]; c->next = (uint8_t)((c->next + 1) % SVMG_CMD_CACHE); }
  memset(s, 0, sizeof *s);
  strncpy(s->id, id, SVMG_CMD_ID_LEN - 1);
  return s;
}

static uint32_t cfg_ver(const svmg_cmd_hooks_t *h) { return (h && h->config_version) ? h->config_version(h->ctx) : 0; }

static void fill_ack(svmg_cmd_ack_t *a, const char *id, uint8_t applied, svmg_reason_t r, uint32_t ver) {
  memset(a, 0, sizeof *a);
  strncpy(a->cmd_id, id, SVMG_CMD_ID_LEN - 1);
  a->applied = applied; a->reason = r; a->config_version = ver;
}

/* Kiểm tra tham số thuần túy (không phụ thuộc trạng thái thiết bị). */
static svmg_reason_t validate(const svmg_cmd_t *m) {
  switch (m->type) {
    case SVMG_CMD_ACK: return SVMG_R_OK;
    case SVMG_CMD_MUTE:
      if (!(m->has & SVMG_CP_DURATION) || m->duration_s < 1 || m->duration_s > 300) return SVMG_R_BAD_PARAM;
      return SVMG_R_OK;
    case SVMG_CMD_SET_PROFILE:
      if (!(m->has & SVMG_CP_PROFILE) || m->profile > SVMG_PROFILE_SENSITIVE) return SVMG_R_BAD_PARAM;
      return SVMG_R_OK;
    case SVMG_CMD_CALIBRATE_ZERO:
      if ((m->has & SVMG_CP_DURATION) && m->duration_s != 30) return SVMG_R_BAD_PARAM;
      return SVMG_R_OK;
    case SVMG_CMD_SET_SCENARIO:
      if (!(m->has & SVMG_CP_SCENARIO) || m->scenario > 5) return SVMG_R_BAD_PARAM;
      if ((m->has & SVMG_CP_SEA) && m->sea_state > 5) return SVMG_R_BAD_PARAM;
      return SVMG_R_OK;
    case SVMG_CMD_SET_MODE:
      if (!(m->has & SVMG_CP_MODE) || m->mode > SVMG_SRC_SIMULATION) return SVMG_R_BAD_PARAM;
      return SVMG_R_OK;
    case SVMG_CMD_SET_TIMEWARP:
      if (!(m->has & SVMG_CP_TIMEWARP) || !(m->timewarp == 1 || m->timewarp == 5 || m->timewarp == 10)) return SVMG_R_BAD_PARAM;
      return SVMG_R_OK;
    case SVMG_CMD_REQUEST_SNAPSHOT:
      if (!(m->has & SVMG_CP_WINDOW) || m->window_s < 1 || m->window_s > 180) return SVMG_R_BAD_PARAM;
      return SVMG_R_OK;
    case SVMG_CMD_SET_MODEL:
      if (!(m->has & SVMG_CP_MODEL) || m->model > SVMG_MODEL_BASELINE_B) return SVMG_R_BAD_PARAM;
      return SVMG_R_OK;
    default: return SVMG_R_UNSUPPORTED;
  }
}

static svmg_reason_t dispatch(const svmg_cmd_hooks_t *h, const svmg_cmd_t *m) {
  switch (m->type) {
    case SVMG_CMD_ACK:        return h->ack ? h->ack(h->ctx, m->alarm_id, (m->has & SVMG_CP_ALARM) != 0) : SVMG_R_UNSUPPORTED;
    case SVMG_CMD_MUTE:       return h->mute ? h->mute(h->ctx, m->duration_s) : SVMG_R_UNSUPPORTED;
    case SVMG_CMD_SET_PROFILE:return h->set_profile ? h->set_profile(h->ctx, m->profile) : SVMG_R_UNSUPPORTED;
    case SVMG_CMD_CALIBRATE_ZERO: return h->calibrate_zero ? h->calibrate_zero(h->ctx) : SVMG_R_UNSUPPORTED;
    case SVMG_CMD_SET_SCENARIO:
      return h->set_scenario ? h->set_scenario(h->ctx, m->scenario, (m->has & SVMG_CP_SEA) ? (int)m->sea_state : -1) : SVMG_R_UNSUPPORTED;
    case SVMG_CMD_SET_MODE:   return h->set_mode ? h->set_mode(h->ctx, m->mode) : SVMG_R_UNSUPPORTED;
    case SVMG_CMD_SET_TIMEWARP: return h->set_timewarp ? h->set_timewarp(h->ctx, m->timewarp) : SVMG_R_UNSUPPORTED;
    case SVMG_CMD_REQUEST_SNAPSHOT: return h->request_snapshot ? h->request_snapshot(h->ctx, m->window_s) : SVMG_R_UNSUPPORTED;
    case SVMG_CMD_SET_MODEL:  return h->set_model ? h->set_model(h->ctx, m->model) : SVMG_R_UNSUPPORTED;
    default: return SVMG_R_UNSUPPORTED;
  }
}

int svmg_cmd_exec(svmg_cmd_ctx_t *c, const svmg_cmd_hooks_t *h, const svmg_cmd_t *m, uint32_t queue_age_ms, svmg_cmd_ack_t *ack) {
  if (m->cmd_id[0] == '\0') return 0;                       /* không có cmd_id thì không thể ack: bỏ qua */

  svmg_cmd_slot_t *s = find(c, m->cmd_id);
  if (s) {                                                  /* idempotent */
    c->n_dup++;
    if (s->state == 1) return 0;                            /* đang chờ: không thực thi lại, không ack lại */
    fill_ack(ack, m->cmd_id, s->applied, s->reason, s->config_version);
    return 1;
  }

  if (m->ttl_s == 0) { c->n_rejected++; fill_ack(ack, m->cmd_id, 0, SVMG_R_BAD_PARAM, cfg_ver(h)); return 1; }
  uint64_t age_ms = (uint64_t)m->age_s * 1000u + queue_age_ms;
  if (age_ms >= (uint64_t)m->ttl_s * 1000u) {               /* hết hạn: KHÔNG nhớ, để lần gửi lại (TTL mới) còn được xử lý */
    c->n_rejected++; fill_ack(ack, m->cmd_id, 0, SVMG_R_EXPIRED, cfg_ver(h)); return 1;
  }

  svmg_reason_t r = validate(m);
  if (r == SVMG_R_OK) r = dispatch(h, m);

  s = alloc_slot(c, m->cmd_id);
  if (r == SVMG_R_PENDING) { s->state = 1; c->n_exec++; return 0; }
  s->state = 2; s->applied = (r == SVMG_R_OK); s->reason = r; s->config_version = cfg_ver(h);
  if (r == SVMG_R_OK) c->n_exec++; else c->n_rejected++;
  fill_ack(ack, m->cmd_id, s->applied, r, s->config_version);
  return 1;
}

int svmg_cmd_complete(svmg_cmd_ctx_t *c, const char *cmd_id, svmg_reason_t result, uint32_t config_version, svmg_cmd_ack_t *ack) {
  svmg_cmd_slot_t *s = find(c, cmd_id);
  if (!s || s->state != 1) return 0;
  s->state = 2; s->applied = (result == SVMG_R_OK); s->reason = result; s->config_version = config_version;
  if (result != SVMG_R_OK) c->n_rejected++;
  fill_ack(ack, cmd_id, s->applied, result, config_version);
  return 1;
}
