/* safety.c - M1-04: lớp ngưỡng cứng (safety envelope). Độc lập với mô hình; lệnh từ xa không nới được ra ngoài 15-25 deg.
 * |roll| >= phi_hard (mặc định 20 deg) liên tục >= 5 s -> CRITICAL (đề cương 7.4). */
#include "svmg_decision.h"
#include "svmg_core.h"
#include <math.h>

float svmg_safety_clamp_phi(float phi) {
  if (!isfinite(phi)) return SVMG_PHI_HARD_DEFAULT_DEG;
  if (phi < SVMG_PHI_HARD_MIN_DEG) return SVMG_PHI_HARD_MIN_DEG;
  if (phi > SVMG_PHI_HARD_MAX_DEG) return SVMG_PHI_HARD_MAX_DEG;
  return phi;
}

void svmg_safety_reset(svmg_safety_t *s) { s->over = 0; s->active = 0; s->over_since_s = 0.0f; }

void svmg_safety_init(svmg_safety_t *s, float phi) {
  s->phi_hard_deg = svmg_safety_clamp_phi(phi);
  s->dwell_s = SVMG_HARD_DWELL_S;
  svmg_safety_reset(s);
}

void svmg_safety_set_phi(svmg_safety_t *s, float phi) { s->phi_hard_deg = svmg_safety_clamp_phi(phi); }

int svmg_safety_push(svmg_safety_t *s, float t, float roll, uint8_t valid) {
  if (!valid || !isfinite(roll) || !isfinite(t)) return 0;      /* giữ nguyên trạng thái, không reset, không kích hoạt */
  if (s->over && t < s->over_since_s) svmg_safety_reset(s);     /* đồng hồ đi lùi (quấn vòng) */
  int was_active = s->active;
  if (fabsf(roll) >= s->phi_hard_deg) {
    if (!s->over) { s->over = 1; s->over_since_s = t; }
    if ((t - s->over_since_s) >= s->dwell_s) s->active = 1;
  } else {
    s->over = 0; s->active = 0;
  }
  return (!was_active && s->active) ? 1 : 0;
}

/* API của svmg_core.h/stub khung: trạng thái nội bộ mặc định, dt tính bằng giây. */
bool checkSafetyEnvelope(float roll_deg, float dt) {
  static svmg_safety_t s;
  static float t = 0.0f;
  static int inited = 0;
  if (!inited) { svmg_safety_init(&s, SVMG_PHI_HARD_DEFAULT_DEG); inited = 1; }
  t += dt;
  svmg_safety_push(&s, t, roll_deg, 1);
  return s.active != 0;
}
