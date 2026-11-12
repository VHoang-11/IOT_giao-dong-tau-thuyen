/* svmg_config.h - M1-07: cấu hình có phiên bản, kiểm tra biên an toàn, CRC (đề cương 8.2.1, Phụ lục A.3).
 * Mọi giá trị nhận từ xa đều bị kiểm tra ở đây; giá trị ngoài biên bị từ chối (không kẹp âm thầm).
 */
#ifndef SVMG_CONFIG_H
#define SVMG_CONFIG_H

#include "svmg_common.h"
#include "svmg_alarm.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum { SVMG_PROFILE_CONSERVATIVE = 0, SVMG_PROFILE_STANDARD = 1, SVMG_PROFILE_SENSITIVE = 2 } svmg_profile_t;
typedef enum { SVMG_MODEL_RF = 0, SVMG_MODEL_BASELINE_B = 1 } svmg_model_t;

#define SVMG_ZERO_LIMIT_DEG 10.0f      /* |độ lệch hiệu chuẩn| tối đa: không dùng calibrate để che nghiêng lệch thật */

typedef struct {
  uint32_t config_version;
  uint8_t  profile;
  uint8_t  debounce_n;         /* 1..6 */
  uint8_t  phi_hard_deg;       /* 15..25 (nguyên) */
  uint8_t  mai_caution;        /* 30..95 */
  uint8_t  report_interval_s;  /* 5..60, bội của 5 (giây mô phỏng) */
  uint8_t  primary_model;      /* svmg_model_t */
  float    zero_roll_deg;      /* hiệu chuẩn cục bộ, không thuộc CRC/bản tin config từ backend */
  float    zero_pitch_deg;
} svmg_config_t;

void svmg_config_default(svmg_config_t *c, svmg_model_t primary);
/* Đặt debounce_n và mai_caution theo hồ sơ: CONSERVATIVE 4/85, STANDARD 3/80, SENSITIVE 2/70. */
void svmg_config_apply_profile(svmg_config_t *c, svmg_profile_t p);
svmg_reason_t svmg_config_validate(const svmg_config_t *c);   /* SVMG_R_OK hoặc SVMG_R_BAD_PARAM */
void svmg_config_to_alarm(const svmg_config_t *c, svmg_alarm_cfg_t *out);

const char *svmg_profile_name(uint8_t p);
const char *svmg_model_name(uint8_t m);
int  svmg_profile_from_str(const char *s);   /* -1 nếu sai */
int  svmg_model_from_str(const char *s);
int  svmg_scenario_from_str(const char *s);  /* S0=0, S0b=1, S1=2, S2=3, S3=4, H1=5 ; -1 nếu sai */
const char *svmg_scenario_name(uint8_t i);

/* CRC-16/CCITT-FALSE (đa thức 0x1021, khởi tạo 0xFFFF, không đảo bit). Kiểm thử: "123456789" -> 0x29B1. */
uint16_t svmg_crc16_ccitt(const void *data, size_t len);
/* Chuỗi chuẩn tắc để tính CRC (đề xuất cho contracts): "v=8;p=SENSITIVE;n=2;phi=20;mai=70;rep=5;m=RF" */
size_t   svmg_config_canonical(const svmg_config_t *c, char *buf, size_t cap);
uint16_t svmg_config_crc(const svmg_config_t *c);

typedef enum { SVMG_CFG_APPLY = 0, SVMG_CFG_DUPLICATE = 1, SVMG_CFG_REJECT = 2 } svmg_cfg_verdict_t;
/* Xét bản tin config từ backend: sai CRC/ngoài biên/phiên bản cũ -> REJECT (giữ cấu hình cũ);
 * cùng phiên bản và cùng nội dung -> DUPLICATE (không áp lại, không ack lại). */
svmg_cfg_verdict_t svmg_config_check_update(const svmg_config_t *cur, const svmg_config_t *incoming,
                                            uint16_t crc_in, svmg_reason_t *reason);

#ifdef __cplusplus
}
#endif
#endif
