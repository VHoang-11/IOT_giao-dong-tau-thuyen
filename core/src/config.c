/* config.c - M1-07. Xem svmg_config.h. */
#include "svmg_config.h"
#include "svmg_decision.h"
#include <string.h>
#include <math.h>

void svmg_config_apply_profile(svmg_config_t *c, svmg_profile_t p) {
  c->profile = (uint8_t)p;
  switch (p) {
    case SVMG_PROFILE_CONSERVATIVE: c->debounce_n = 4; c->mai_caution = 85; break;
    case SVMG_PROFILE_SENSITIVE:    c->debounce_n = 2; c->mai_caution = 70; break;
    default:                        c->debounce_n = 3; c->mai_caution = 80; break;
  }
}

void svmg_config_default(svmg_config_t *c, svmg_model_t primary) {
  memset(c, 0, sizeof *c);
  c->config_version = 1;
  svmg_config_apply_profile(c, SVMG_PROFILE_STANDARD);
  c->phi_hard_deg = SVMG_PHI_HARD_DEFAULT_DEG;
  c->report_interval_s = 5;
  c->primary_model = (uint8_t)primary;
}

svmg_reason_t svmg_config_validate(const svmg_config_t *c) {
  if (c->profile > SVMG_PROFILE_SENSITIVE) return SVMG_R_BAD_PARAM;
  if (c->debounce_n < SVMG_CFG_N_MIN || c->debounce_n > SVMG_CFG_N_MAX) return SVMG_R_BAD_PARAM;
  if (!isfinite(c->phi_hard_deg) || c->phi_hard_deg < SVMG_PHI_HARD_MIN_DEG || c->phi_hard_deg > SVMG_PHI_HARD_MAX_DEG) return SVMG_R_BAD_PARAM;
  if (c->mai_caution < SVMG_CFG_MAI_MIN || c->mai_caution > SVMG_CFG_MAI_MAX) return SVMG_R_BAD_PARAM;
  if (c->report_interval_s < SVMG_CFG_REPORT_MIN || c->report_interval_s > SVMG_CFG_REPORT_MAX) return SVMG_R_BAD_PARAM;
  if (c->primary_model > SVMG_MODEL_BASELINE_B) return SVMG_R_BAD_PARAM;
  if (!isfinite(c->zero_roll_deg) || !isfinite(c->zero_pitch_deg) ||
      fabsf(c->zero_roll_deg) > SVMG_ZERO_LIMIT_DEG || fabsf(c->zero_pitch_deg) > SVMG_ZERO_LIMIT_DEG) return SVMG_R_BAD_PARAM;
  return SVMG_R_OK;
}

void svmg_config_to_alarm(const svmg_config_t *c, svmg_alarm_cfg_t *o) {
  svmg_alarm_default_cfg(o);
  o->debounce_n = c->debounce_n;
  o->mai_caution = c->mai_caution;
}

static const char *const PROFILES[3] = { "CONSERVATIVE", "STANDARD", "SENSITIVE" };
static const char *const SCENARIOS[6] = { "S0", "S0b", "S1", "S2", "S3", "H1" };

const char *svmg_profile_name(uint8_t p) { return p < 3 ? PROFILES[p] : "?"; }
const char *svmg_model_name(uint8_t m) { return m == SVMG_MODEL_RF ? "RF" : (m == SVMG_MODEL_BASELINE_B ? "BASELINE_B" : "?"); }
const char *svmg_scenario_name(uint8_t i) { return i < 6 ? SCENARIOS[i] : "?"; }

int svmg_profile_from_str(const char *s) {
  if (!s) return -1;
  for (int i = 0; i < 3; i++) if (strcmp(s, PROFILES[i]) == 0) return i;
  return -1;
}
int svmg_model_from_str(const char *s) {
  if (!s) return -1;
  if (strcmp(s, "RF") == 0) return SVMG_MODEL_RF;
  if (strcmp(s, "BASELINE_B") == 0) return SVMG_MODEL_BASELINE_B;
  return -1;
}
int svmg_scenario_from_str(const char *s) {
  if (!s) return -1;
  for (int i = 0; i < 6; i++) if (strcmp(s, SCENARIOS[i]) == 0) return i;
  return -1;
}

uint16_t svmg_crc16_ccitt(const void *data, size_t len) {
  const uint8_t *p = (const uint8_t *)data;
  uint16_t crc = 0xFFFF;
  while (len--) {
    crc ^= (uint16_t)(*p++) << 8;
    for (int i = 0; i < 8; i++) crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
  }
  return crc;
}

svmg_reason_t svmg_config_apply_patch(const svmg_config_t *cur, const svmg_config_patch_t *p, svmg_config_t *out) {
  *out = *cur;                                   /* giữ hiệu chuẩn cục bộ và mọi trường vắng */
  out->config_version = p->config_version;
  if (p->has & SVMG_CFGP_PROFILE) {
    if (p->profile > SVMG_PROFILE_SENSITIVE) return SVMG_R_BAD_PARAM;
    svmg_config_apply_profile(out, (svmg_profile_t)p->profile);       /* mặc định của hồ sơ trước, rồi trường tường minh chồng lên */
  }
  if (p->has & SVMG_CFGP_DEBOUNCE) out->debounce_n = p->debounce_n;
  if (p->has & SVMG_CFGP_MAI) out->mai_caution = p->mai_caution;
  if (p->has & SVMG_CFGP_PHI) out->phi_hard_deg = p->phi_hard_deg;
  if (p->has & SVMG_CFGP_REPORT) out->report_interval_s = p->report_interval_s;
  if (p->has & SVMG_CFGP_MODEL) out->primary_model = p->primary_model;
  return svmg_config_validate(out);
}

static int same_content(const svmg_config_t *a, const svmg_config_t *b) {
  return a->profile == b->profile && a->debounce_n == b->debounce_n && a->mai_caution == b->mai_caution &&
         a->primary_model == b->primary_model && a->report_interval_s == b->report_interval_s && a->phi_hard_deg == b->phi_hard_deg;
}

svmg_cfg_verdict_t svmg_config_check_patch(const svmg_config_t *cur, const svmg_config_patch_t *p, svmg_config_t *out, svmg_reason_t *reason) {
  svmg_reason_t dummy; if (!reason) reason = &dummy;
  *reason = SVMG_R_OK;
  if (p->crc_state == SVMG_CRC_BAD) { *reason = SVMG_R_BAD_PARAM; return SVMG_CFG_REJECT; }
  if (!(p->has & SVMG_CFGP_PROFILE)) { *reason = SVMG_R_BAD_PARAM; return SVMG_CFG_REJECT; }      /* schema: profile bắt buộc */
  svmg_config_t cand;
  svmg_reason_t v = svmg_config_apply_patch(cur, p, &cand);
  if (v != SVMG_R_OK) { *reason = v; return SVMG_CFG_REJECT; }
  if (p->config_version < cur->config_version) { *reason = SVMG_R_BAD_PARAM; return SVMG_CFG_REJECT; }   /* chỉ áp version lớn hơn */
  if (p->config_version == cur->config_version) {
    if (same_content(&cand, cur)) return SVMG_CFG_DUPLICATE;                 /* retained gửi lại sau khi nối lại */
    *reason = SVMG_R_BAD_PARAM; return SVMG_CFG_REJECT;                      /* cùng phiên bản nhưng khác nội dung */
  }
  if (out) *out = cand;
  return SVMG_CFG_APPLY;
}
