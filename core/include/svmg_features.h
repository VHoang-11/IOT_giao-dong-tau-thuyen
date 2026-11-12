/* svmg_features.h - M1-03: cửa sổ trượt trên chuỗi 2 Hz, đặc trưng 60 s / 180 s, chất lượng dữ liệu.
 *
 * Đặc trưng tính từ góc roll đã trừ độ lệch hiệu chuẩn, đơn vị ĐỘ (deg, deg/s) theo đề cương mục 7.1.
 * Cửa sổ ngắn 60 s = 120 mẫu; cửa sổ dài 180 s = 360 mẫu; cập nhật mỗi 10 mẫu (= 5 s thời gian mô phỏng).
 * Chỉ tính trên mẫu hợp lệ; mẫu thiếu được đếm vào tỉ lệ thiếu.
 */
#ifndef SVMG_FEATURES_H
#define SVMG_FEATURES_H

#include "svmg_common.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SVMG_WIN_SHORT      120
#define SVMG_WIN_LONG       360
#define SVMG_UPDATE_SAMPLES 10
#define SVMG_N_FEATURES     10

/* rms_roll_deg = độ lệch chuẩn quanh trung bình 60 s (1) hay RMS quanh 0 (0).
 * Mặc định (1): tách "dao động" khỏi "nghiêng lệch" để HIGH_ROLL không nhầm với PERSISTENT_OFFSET.
 * Đây là đề xuất cho features.md; giá trị RMS quanh 0 luôn có ở rms_roll_abs_deg. */
#ifndef SVMG_FEAT_RMS_ABOUT_MEAN
#define SVMG_FEAT_RMS_ABOUT_MEAN 1
#endif

typedef struct {
  float    roll_deg[SVMG_WIN_LONG];
  float    gx_dps[SVMG_WIN_SHORT];
  float    gy_dps[SVMG_WIN_SHORT];
  uint8_t  valid[SVMG_WIN_LONG];
  uint32_t total;            /* tổng số mẫu đã đẩy từ lần clear */
  uint16_t since_update;
  uint16_t consec_invalid;   /* số mẫu 2 Hz thiếu liên tiếp gần nhất */
} svmg_window_t;

typedef struct {
  /* Biên độ (60 s) */
  float rms_roll_deg;        /* xem SVMG_FEAT_RMS_ABOUT_MEAN */
  float rms_roll_abs_deg;    /* RMS quanh 0 */
  float p2p_deg;
  float p95_abs_deg;         /* P95 của |roll| (quanh 0), hạng gần nhất */
  float rms_gyro_x_dps, rms_gyro_y_dps;
  /* Độ lệch (180 s) */
  float mean_roll_deg;
  float same_sign_ratio;     /* tỉ lệ thời gian roll cùng dấu chiếm ưu thế, 0.5..1 */
  /* Xu hướng (180 s) */
  float trend_rms_deg_per_min;   /* độ dốc RMS qua 6 đoạn 30 s */
  float rms_ratio;           /* max(RMS(60 s cuối), 0.5) / max(RMS(60 s đầu), 0.5) [deg] */
  /* Nhịp */
  float zero_cross_period_s; /* 0 = không dao động rõ (< 2 lần cắt không) */
  /* Chất lượng */
  float noise_floor_deg;     /* nhiễu nền ước lượng từ sai phân bậc 2 */
  float missing_ratio_60, missing_ratio_180;
  uint16_t n_valid_60, n_valid_180;
  uint16_t consec_invalid;
  uint8_t ready_short, ready_long;
} svmg_features_t;

void svmg_window_clear(svmg_window_t *w);
/* Đẩy một mẫu 2 Hz. Trả 1 khi đến hạn cập nhật (mỗi 10 mẫu). valid=0: mẫu thiếu. */
int  svmg_window_push(svmg_window_t *w, float roll_deg, float gx_dps, float gy_dps, uint8_t valid);
/* Dịch toàn bộ roll đã lưu (khi đổi độ lệch hiệu chuẩn) để không phải khởi động nguội lại. */
void svmg_window_shift_roll(svmg_window_t *w, float delta_deg);
void svmg_features_compute(const svmg_window_t *w, svmg_features_t *f);

/* Thứ tự vector đặc trưng đưa vào mô hình (đề xuất cho contracts/features.md):
 * 0 rms_roll, 1 p2p, 2 p95_abs, 3 rms_gyro_x, 4 rms_gyro_y,
 * 5 mean_roll, 6 same_sign_ratio, 7 trend, 8 rms_ratio, 9 zero_cross_period */
void svmg_features_to_vector(const svmg_features_t *f, float out[SVMG_N_FEATURES]);
extern const char *const SVMG_FEATURE_NAMES[SVMG_N_FEATURES];

/* ---- Quy tắc UNKNOWN / FAULT ---- */
#define SVMG_Q_COLD        0x01   /* chưa đủ cửa sổ 180 s (khởi động nguội) */
#define SVMG_Q_MISSING     0x02   /* tỉ lệ thiếu vượt ngưỡng UNKNOWN */
#define SVMG_Q_FAULT_RUN   0x04   /* thiếu liên tiếp quá lâu */
#define SVMG_Q_FAULT_RATIO 0x08   /* tỉ lệ thiếu vượt ngưỡng FAULT */

typedef struct {
  float    unknown_missing_ratio;   /* mặc định 0.20 */
  float    fault_missing_ratio;     /* mặc định 0.50 */
  uint16_t fault_consec_invalid;    /* mặc định 20 mẫu (= 10 s) */
} svmg_quality_cfg_t;

void           svmg_quality_default(svmg_quality_cfg_t *q);
/* FAULT > UNKNOWN > OK. *reason (có thể NULL) nhận các bit SVMG_Q_*. */
svmg_status_t  svmg_features_status(const svmg_features_t *f, const svmg_quality_cfg_t *q, uint8_t *reason);

#ifdef __cplusplus
}
#endif
#endif
