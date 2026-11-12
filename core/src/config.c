/* config.c - M1-07. Xem svmg_config.h. */
#include "svmg_config.h"
#include "svmg_decision.h"
#include <stdio.h>
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
  c->phi_hard_deg = (uint8_t)SVMG_PHI_HARD_DEFAULT_DEG;
  c->report_interval_s = 5;
  c->primary_model = (uint8_t)primary;
}

svmg_reason_t svmg_config_validate(const svmg_config_t *c) {
  if (c->profile > SVMG_PROFILE_SENSITIVE) return SVMG_R_BAD_PARAM;
  if (c->debounce_n < 1 || c->debounce_n > 6) return SVMG_R_BAD_PARAM;
  if (c->phi_hard_deg < (uint8_t)SVMG_PHI_HARD_MIN_DEG || c->phi_hard_deg > (uint8_t)SVMG_PHI_HARD_MAX_DEG) return SVMG_R_BAD_PARAM;
  if (c->mai_caution < 30 || c->mai_caution > 95) return SVMG_R_BAD_PARAM;
  if (c->report_interval_s < 5 || c->report_interval_s > 60 || (c->report_interval_s % 5) != 0) return SVMG_R_BAD_PARAM;
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

size_t svmg_config_canonical(const svmg_config_t *c, char *buf, size_t cap) {
  int n = snprintf(buf, cap, "v=%lu;p=%s;n=%u;phi=%u;mai=%u;rep=%u;m=%s",
                   (unsigned long)c->config_version, svmg_profile_name(c->profile), (unsigned)c->debounce_n,
                   (unsigned)c->phi_hard_deg, (unsigned)c->mai_caution, (unsigned)c->report_interval_s,
                   svmg_model_name(c->primary_model));
  return n < 0 ? 0 : (size_t)n;
}

uint16_t svmg_config_crc(const svmg_config_t *c) {
  char buf[96];
  size_t n = svmg_config_canonical(c, buf, sizeof buf);
  if (n >= sizeof buf) n = sizeof buf - 1;
  return svmg_crc16_ccitt(buf, n);
}

svmg_cfg_verdict_t svmg_config_check_update(const svmg_config_t *cur, const svmg_config_t *in, uint16_t crc_in, svmg_reason_t *reason) {
  svmg_config_t cand = *in;
  cand.zero_roll_deg = cur->zero_roll_deg;      /* hiệu chuẩn là dữ liệu cục bộ, không bị bản tin ghi đè */
  cand.zero_pitch_deg = cur->zero_pitch_deg;
  if (reason) *reason = SVMG_R_OK;
  if (svmg_config_crc(&cand) != crc_in) { if (reason) *reason = SVMG_R_BAD_PARAM; return SVMG_CFG_REJECT; }
  svmg_reason_t v = svmg_config_validate(&cand);
  if (v != SVMG_R_OK) { if (reason) *reason = v; return SVMG_CFG_REJECT; }
  if (cand.config_version == cur->config_version) {
    if (svmg_config_crc(cur) == crc_in) return SVMG_CFG_DUPLICATE;     /* retained gửi lại sau khi nối lại */
    if (reason) *reason = SVMG_R_BAD_PARAM;                              /* cùng phiên bản nhưng khác nội dung */
    return SVMG_CFG_REJECT;
  }
  if (cand.config_version < cur->config_version) { if (reason) *reason = SVMG_R_BAD_PARAM; return SVMG_CFG_REJECT; }
  return SVMG_CFG_APPLY;
}
