/* svmg_decision.h - M1-04: lớp ngưỡng cứng (safety envelope), chỉ số MAI, Baseline B.
 * Mọi ngưỡng ở đây là tham số DEMO, không phải ngưỡng an toàn hàng hải (đề cương mục 5.3, 7.4).
 */
#ifndef SVMG_DECISION_H
#define SVMG_DECISION_H

#include "svmg_common.h"
#include "svmg_features.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ---------------- Lớp ngưỡng cứng ----------------
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
 * MAI = 100 * min(1, max(r_amp, r_off, r_trend)); không phải xác suất rủi ro. */
typedef struct { float a_ref_deg, b_ref_deg, g_ref_deg_per_min; } svmg_mai_params_t;
typedef struct {
  uint8_t value;       /* 0..100 */
  uint8_t dominant;    /* 0 = biên độ, 1 = độ lệch, 2 = xu hướng */
  float   r_amp, r_off, r_trend;
} svmg_mai_t;

void svmg_mai_default(svmg_mai_params_t *p);
void svmg_mai_compute(const svmg_mai_params_t *p, const svmg_features_t *f, svmg_mai_t *out);

/* ---------------- Baseline B (luật nhiều đặc trưng) ----------------
 * Ưu tiên như quy tắc nhãn: HIGH_ROLL > AMPLITUDE_GROWTH > PERSISTENT_OFFSET > NORMAL.
 * Giá trị mặc định chỉ là điểm khởi đầu; M2 xuất baseline_params.json sau khi chỉnh trên validation. */
typedef struct {
  float hi_rms_deg;        /* HIGH_ROLL nếu rms_roll >= */
  float off_mean_deg;      /* PERSISTENT_OFFSET nếu |mean_roll| >= ... */
  float off_same_sign;     /* ... và same_sign_ratio >= */
  float grow_trend;        /* AMPLITUDE_GROWTH nếu trend >= (deg/phút) ... */
  float grow_ratio;        /* ... và rms_ratio >= ... */
  float grow_min_rms;      /* ... và rms_roll >= (loại nhiễu nhỏ) */
} svmg_baseline_params_t;

void         svmg_baseline_default(svmg_baseline_params_t *p);
/* Chỉ gọi khi dữ liệu đạt chất lượng (status OK). */
svmg_class_t svmg_baseline_b(const svmg_baseline_params_t *p, const svmg_features_t *f);

#ifdef __cplusplus
}
#endif
#endif
