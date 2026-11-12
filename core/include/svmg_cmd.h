/* svmg_cmd.h - M1-07: xử lý lệnh downlink (đề cương 8.2, Bảng 8.2).
 *  - idempotent: nhớ 16 cmd_id gần nhất; lệnh lặp trả lại kết quả cũ, không thực thi lại;
 *  - kiểm tra tham số ở đây (BAD_PARAM) rồi mới gọi hook; hook trả FORBIDDEN_STATE/NOT_STATIC...;
 *  - hết hạn TTL -> EXPIRED (kết quả EXPIRED không được nhớ để lần gửi lại với TTL mới vẫn xử lý);
 *  - KHÔNG có lệnh nào tắt cảnh báo cục bộ hoặc hạ ngưỡng cứng.
 * Phần phân tích JSON thuộc firmware/ (không ở đây).
 */
#ifndef SVMG_CMD_H
#define SVMG_CMD_H

#include "svmg_common.h"
#include "svmg_config.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SVMG_CMD_ID_LEN 24
#define SVMG_CMD_CACHE  16
#define SVMG_CMD_ISSUER_LEN 16

typedef enum {
  SVMG_CMD_NONE = 0, SVMG_CMD_ACK, SVMG_CMD_MUTE, SVMG_CMD_SET_PROFILE, SVMG_CMD_CALIBRATE_ZERO,
  SVMG_CMD_SET_SCENARIO, SVMG_CMD_SET_MODE, SVMG_CMD_SET_TIMEWARP, SVMG_CMD_REQUEST_SNAPSHOT, SVMG_CMD_SET_MODEL
} svmg_cmd_type_t;

/* Bit "có mặt" của tham số (parser đặt). Enum sai chuỗi -> parser đặt giá trị 0xFF và vẫn bật bit. */
#define SVMG_CP_DURATION 0x001
#define SVMG_CP_PROFILE  0x002
#define SVMG_CP_SCENARIO 0x004
#define SVMG_CP_SEA      0x008
#define SVMG_CP_MODE     0x010
#define SVMG_CP_TIMEWARP 0x020
#define SVMG_CP_WINDOW   0x040
#define SVMG_CP_MODEL    0x080
#define SVMG_CP_ALARM    0x100

typedef struct {
  char     cmd_id[SVMG_CMD_ID_LEN];
  char     issued_by[SVMG_CMD_ISSUER_LEN];
  uint8_t  type;               /* svmg_cmd_type_t, 0 nếu lệnh lạ */
  uint16_t ttl_s;              /* bắt buộc > 0 */
  uint16_t age_s;              /* tuổi lệnh khi backend gửi (tùy chọn, mặc định 0) */
  uint16_t has;                /* SVMG_CP_* */
  uint32_t alarm_id;
  uint16_t duration_s, window_s;
  uint8_t  profile, scenario, sea_state, mode, timewarp, model;
} svmg_cmd_t;

typedef struct {
  char          cmd_id[SVMG_CMD_ID_LEN];
  uint8_t       applied;       /* 1 = APPLIED, 0 = REJECTED */
  svmg_reason_t reason;        /* SVMG_R_OK khi applied */
  uint32_t      config_version;
} svmg_cmd_ack_t;

/* Hook thực thi hiệu ứng thật. Trả SVMG_R_OK, hoặc mã từ chối; SVMG_R_PENDING nghĩa là đã bắt đầu, ack gửi sau
 * (dùng cho calibrate_zero). Hook có thể để NULL -> UNSUPPORTED. */
typedef struct {
  void *ctx;
  svmg_reason_t (*ack)(void *ctx, uint32_t alarm_id, int has_alarm);
  svmg_reason_t (*mute)(void *ctx, uint16_t duration_s);
  svmg_reason_t (*set_profile)(void *ctx, uint8_t profile);
  svmg_reason_t (*calibrate_zero)(void *ctx);
  svmg_reason_t (*set_scenario)(void *ctx, uint8_t scenario, int sea_state /* -1 = giữ nguyên */);
  svmg_reason_t (*set_mode)(void *ctx, uint8_t mode);
  svmg_reason_t (*set_timewarp)(void *ctx, uint8_t timewarp);
  svmg_reason_t (*request_snapshot)(void *ctx, uint16_t window_s);
  svmg_reason_t (*set_model)(void *ctx, uint8_t model);
  uint32_t      (*config_version)(void *ctx);
} svmg_cmd_hooks_t;

typedef struct {
  char          id[SVMG_CMD_ID_LEN];
  uint8_t       state;         /* 0 trống, 1 đang chờ (bất đồng bộ), 2 đã xong */
  uint8_t       applied;
  svmg_reason_t reason;
  uint32_t      config_version;
} svmg_cmd_slot_t;

typedef struct { svmg_cmd_slot_t slot[SVMG_CMD_CACHE]; uint8_t next; uint32_t n_exec, n_dup, n_rejected; } svmg_cmd_ctx_t;

void svmg_cmd_init(svmg_cmd_ctx_t *c);

/* Kết quả: 1 = *ack sẵn sàng gửi (kể cả lệnh lặp trả lại kết quả cũ); 0 = đang chờ (chưa có ack, hoặc lệnh lặp
 * của lệnh còn đang chờ -> không gửi gì). */
int svmg_cmd_exec(svmg_cmd_ctx_t *c, const svmg_cmd_hooks_t *h, const svmg_cmd_t *cmd, uint32_t queue_age_ms, svmg_cmd_ack_t *ack);
/* Hoàn tất lệnh bất đồng bộ. Trả 1 nếu tìm thấy và *ack được điền. */
int svmg_cmd_complete(svmg_cmd_ctx_t *c, const char *cmd_id, svmg_reason_t result, uint32_t config_version, svmg_cmd_ack_t *ack);

const char *svmg_reason_name(svmg_reason_t r);

#ifdef __cplusplus
}
#endif
#endif
