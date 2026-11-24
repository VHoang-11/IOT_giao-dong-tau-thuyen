/* svmg_config.h - M1-07: cấu hình có phiên bản, kiểm tra biên an toàn (đề cương 8.2.1, contracts/schemas/config.json).
 *
 * Bản tin config từ backend là BẢN VÁ (backend chỉ gửi các trường đổi, bắt buộc có `profile`): trường vắng giữ giá trị hiện tại;
 * có `profile` mà vắng debounce_n/mai_caution -> lấy mặc định của hồ sơ rồi chồng các trường có mặt.
 * Mọi giá trị nhận từ xa đều bị kiểm tra ở đây; giá trị ngoài biên bị TỪ CHỐI (không kẹp âm thầm).
 * Biên theo schema: debounce_n 1..10, phi_hard_deg 15..25 (số thực), mai_caution 30..90, report_interval_s 1..3600.
 * CRC của bản tin tính trên JSON chuẩn tắc (khóa sắp xếp, nhỏ gọn) nên do lớp bản tin (msg.cpp) tính và đưa vào patch.crc_state.
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

#define SVMG_ZERO_LIMIT_DEG   10.0f     /* |độ lệch hiệu chuẩn| tối đa: không dùng calibrate để che nghiêng lệch thật */
#define SVMG_CFG_N_MIN        1
#define SVMG_CFG_N_MAX        10
#define SVMG_CFG_MAI_MIN      30
#define SVMG_CFG_MAI_MAX      90
#define SVMG_CFG_REPORT_MIN   1
#define SVMG_CFG_REPORT_MAX   3600

typedef struct {
  uint32_t config_version;
  uint8_t  profile;
  uint8_t  debounce_n;
  uint8_t  mai_caution;
  uint8_t  primary_model;      /* svmg_model_t */
  uint16_t report_interval_s;  /* chu kỳ telemetry theo đồng hồ mô phỏng */
  float    phi_hard_deg;       /* 15..25 */
  float    zero_roll_deg;      /* hiệu chuẩn cục bộ, không thuộc bản tin config từ backend */
  float    zero_pitch_deg;
} svmg_config_t;

#define SVMG_CFGP_PROFILE  0x01
#define SVMG_CFGP_DEBOUNCE 0x02
#define SVMG_CFGP_PHI      0x04
#define SVMG_CFGP_MAI      0x08
#define SVMG_CFGP_REPORT   0x10
#define SVMG_CFGP_MODEL    0x20
#define SVMG_CRC_ABSENT 0
#define SVMG_CRC_OK     1
#define SVMG_CRC_BAD    2

typedef struct {
  uint32_t config_version;
  uint8_t  has;                /* SVMG_CFGP_* */
  uint8_t  profile, debounce_n, mai_caution, primary_model;
  uint16_t report_interval_s;
  float    phi_hard_deg;
  uint8_t  crc_state;          /* SVMG_CRC_*: do lớp bản tin tính từ JSON chuẩn tắc */
} svmg_config_patch_t;

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

typedef enum { SVMG_CFG_APPLY = 0, SVMG_CFG_DUPLICATE = 1, SVMG_CFG_REJECT = 2 } svmg_cfg_verdict_t;
/* Áp bản vá lên cấu hình hiện tại -> *out (giữ hiệu chuẩn cục bộ). Trả kết quả kiểm biên của *out. */
svmg_reason_t svmg_config_apply_patch(const svmg_config_t *cur, const svmg_config_patch_t *p, svmg_config_t *out);
/* Xét một bản vá: sai CRC / thiếu profile / ngoài biên / phiên bản cũ / cùng phiên bản khác nội dung -> REJECT (giữ cấu hình cũ, *reason);
 * cùng phiên bản và cùng nội dung (retained gửi lại khi nối lại) -> DUPLICATE (không áp lại, không ack lại); mới hơn -> APPLY, *out = kết quả. */
svmg_cfg_verdict_t svmg_config_check_patch(const svmg_config_t *cur, const svmg_config_patch_t *p, svmg_config_t *out, svmg_reason_t *reason);

#ifdef __cplusplus
}
#endif
#endif
