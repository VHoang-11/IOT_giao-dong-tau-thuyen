/* svmg_decision.h - M1-04: lớp ngưỡng cứng (safety.c), chỉ số MAI (mai.c), Baseline B (baseline.c).
 * Baseline B và MAI dùng bộ 23 đặc trưng của contract (đề cương 7.4: cùng nhóm đặc trưng với RF để so sánh công bằng).
 * Mọi ngưỡng là tham số DEMO, không phải ngưỡng an toàn hàng hải (đề cương 5.3, 7.4).
 */
#ifndef SVMG_DECISION_H
#define SVMG_DECISION_H

#include "svmg_common.h"
#include "svmg_features.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ---------------- Lớp ngưỡng cứng (safety.c) ----------------
 * |roll| >= phi_hard liên tục >= dwell_s  ->  active (CRITICAL bất kể mô hình).
 * phi_hard luôn bị kẹp vào [15, 25] độ: lệnh/cấu hình từ xa không thể nới ra ngoài. */
#define SVMG_PHI_HARD_MIN_DEG     15.0f
#define SVMG_PHI_HARD_MAX_DEG     25.0f
#define SVMG_PHI_HARD_DEFAULT_DEG 20.0f
#define SVMG_HARD_DWELL_S         5.0f

typedef struct {
  float   phi_hard_deg;
  float   dwell_s;
  float   over_since_s;
  uint8_t over;       /* |roll| >= phi_hard ở mẫu gần nhất hợp lệ */
  uint8_t active;     /* đã vượt liên tục >= dwell_s */
} svmg_safety_t;

float svmg_safety_clamp_phi(float phi_deg);
void  svmg_safety_init(svmg_safety_t *s, float phi_hard_deg);
void  svmg_safety_set_phi(svmg_safety_t *s, float phi_hard_deg);   /* tự kẹp */
void  svmg_safety_reset(svmg_safety_t *s);
/* Trả 1 đúng tại thời điểm active chuyển 0 -> 1 (cạnh lên). Mẫu thiếu: giữ nguyên trạng thái. */
int   svmg_safety_push(svmg_safety_t *s, float t_s, float roll_deg, uint8_t valid);

/* ---------------- MAI (Motion Anomaly Index, 0..100) ----------------
 * MAI = 100 * min(1, max(r_amp, r_off, r_trend)); không phải xác suất rủi ro.
 * r_amp = rms_roll/A_ref ; r_off = |mean_roll|/B_ref ; r_trend = max(0, trend_rms_slope)/G_ref. */
typedef struct { float a_ref_deg, b_ref_deg, g_ref_deg_per_min; } svmg_mai_params_t;
typedef struct {
  uint8_t value;       /* 0..100 */
  uint8_t dominant;    /* 0 = biên độ, 1 = độ lệch, 2 = xu hướng */
  float   r_amp, r_off, r_trend;
} svmg_mai_t;

void svmg_mai_default(svmg_mai_params_t *p);
void svmg_mai_compute(const svmg_mai_params_t *p, const svmg_features_t *f, svmg_mai_t *out);

/* Baseline B uses angle-23 only: std60 for dynamic amplitude, raw RMS slope with
 * a short-mean gate for growth, sign ratio and a long/short mean heuristic for offset.
 * off_heel_s is an equivalent-duration demo threshold, NOT measured continuous heel.
 * grow_max_heel_s is retained for parameter-source compatibility but unused.
 * See contracts/features.md; M2 must recalibrate defaults on validation data. */
typedef struct {
  float hi_dyn_rms_deg;
  float grow_slope;        /* deg/phút */
  float grow_min_rms;
  float grow_max_heel_s;
  float off_mean_deg;
  float off_heel_s;
} svmg_baseline_params_t;

void         svmg_baseline_default(svmg_baseline_params_t *p);
/* Chỉ gọi khi dữ liệu đạt chất lượng (status OK). */
svmg_class_t svmg_baseline_b(const svmg_baseline_params_t *p, const svmg_features_t *f);
/* Biên độ động (deg): population std của Roll 60 s. */
float        svmg_baseline_dyn_rms(const svmg_features_t *f);

#ifdef __cplusplus
}
#endif
#endif
