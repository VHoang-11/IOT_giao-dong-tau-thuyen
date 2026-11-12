/* svmg_calib.h - M1-07: hiệu chuẩn độ lệch 0 (calibrate_zero, FR18, đề cương 8.5).
 * Đo trung bình roll/pitch trong 30 s (60 mẫu 2 Hz) khi tín hiệu tĩnh. Không tĩnh -> NOT_STATIC (từ chối),
 * thiếu dữ liệu -> FORBIDDEN_STATE, độ lệch quá lớn (> SVMG_ZERO_LIMIT_DEG) -> FORBIDDEN_STATE
 * (để lệnh này không bị dùng để che một góc nghiêng thật).
 */
#ifndef SVMG_CALIB_H
#define SVMG_CALIB_H

#include "svmg_common.h"
#include "svmg_config.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SVMG_CALIB_SAMPLES 60            /* 30 s x 2 Hz */
#define SVMG_CALIB_STD_MAX_DEG 0.5f      /* ngưỡng "tĩnh": độ lệch chuẩn roll/pitch */

typedef struct {
  uint8_t  active;
  uint16_t n, n_invalid;
  float    mean_r, m2_r, mean_p, m2_p;      /* Welford */
  float    result_roll_deg, result_pitch_deg;
  svmg_reason_t result;
} svmg_calib_t;

void svmg_calib_init(svmg_calib_t *c);
void svmg_calib_start(svmg_calib_t *c);
void svmg_calib_abort(svmg_calib_t *c);
/* Đẩy mẫu 2 Hz (roll/pitch CHƯA trừ hiệu chuẩn, đơn vị độ). Trả 0 = đang chạy/không hoạt động, 1 = xong (xem ->result). */
int  svmg_calib_push(svmg_calib_t *c, float roll_deg, float pitch_deg, uint8_t valid);

#ifdef __cplusplus
}
#endif
#endif
