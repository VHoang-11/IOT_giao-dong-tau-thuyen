/* svmg_cmd.h - M1-07: xử lý lệnh downlink (đề cương 8.2, contracts/schemas/command.json).
 *  - bộ lệnh = command.json: set_profile, set_threshold, calibrate_zero, mute_alarm, start_voyage, stop_voyage, restart_device
 *    (+ ack_alarm đề xuất cho ACK từ dashboard; + lệnh mở rộng chỉ bật khi biên dịch SVMG_EXT_COMMANDS);
 *  - idempotent: nhớ 16 cmd_id gần nhất; lệnh lặp trả lại kết quả cũ, không thực thi lại;
 *  - kiểm tra tham số ở đây (BAD_PARAM) rồi mới gọi hook; hook trả FORBIDDEN_STATE/NOT_STATIC...;
 *  - hết hạn TTL -> EXPIRED (kết quả EXPIRED không được nhớ để lần gửi lại với TTL mới vẫn xử lý);
 *  - KHÔNG có lệnh nào tắt cảnh báo cục bộ hoặc hạ ngưỡng cứng ra ngoài 15..25 deg.
 * Phần phân tích JSON thuộc firmware/lib/svmg_msg (không ở đây).
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
#define SVMG_MUTE_DEFAULT_S 60     /* mute_alarm không kèm duration_s */
#define SVMG_MUTE_MAX_S     300

typedef enum {
  SVMG_CMD_NONE = 0,
  /* --- contract (command.json) --- */
  SVMG_CMD_SET_PROFILE, SVMG_CMD_SET_THRESHOLD, SVMG_CMD_CALIBRATE_ZERO, SVMG_CMD_MUTE_ALARM,
  SVMG_CMD_START_VOYAGE, SVMG_CMD_STOP_VOYAGE, SVMG_CMD_RESTART_DEVICE,
  /* --- đề xuất thêm vào contract --- */
  SVMG_CMD_ACK_ALARM,
  /* --- mở rộng ngoài contract (SVMG_EXT_COMMANDS) --- */
  SVMG_CMD_SET_MODE, SVMG_CMD_SET_SCENARIO, SVMG_CMD_SET_TIMEWARP, SVMG_CMD_REQUEST_SNAPSHOT, SVMG_CMD_SET_MODEL
} svmg_cmd_type_t;

/* Bit "có mặt" của tham số (parser đặt). Enum sai chuỗi -> parser đặt giá trị 0xFF và vẫn bật bit. */
#define SVMG_CP_DURATION 0x0001
#define SVMG_CP_PROFILE  0x0002
#define SVMG_CP_SCENARIO 0x0004
#define SVMG_CP_SEA      0x0008
#define SVMG_CP_MODE     0x0010
#define SVMG_CP_TIMEWARP 0x0020
#define SVMG_CP_WINDOW   0x0040
#define SVMG_CP_MODEL    0x0080
#define SVMG_CP_ALARM    0x0100
#define SVMG_CP_PHI      0x0200   /* set_threshold */
#define SVMG_CP_MAI      0x0400
#define SVMG_CP_DEBOUNCE 0x0800
#define SVMG_CP_REPORT   0x1000

typedef struct {
  char     cmd_id[SVMG_CMD_ID_LEN];
  char     issued_by[SVMG_CMD_ISSUER_LEN];
  uint8_t  type;               /* svmg_cmd_type_t, 0 nếu lệnh lạ */
  uint16_t ttl_s;              /* bắt buộc > 0 (parser đặt 0 nếu thiếu/sai kiểu -> BAD_PARAM) */
  uint16_t age_s;              /* tuổi lệnh khi backend gửi (tùy chọn, mặc định 0) */
  uint16_t has;                /* SVMG_CP_* */
  uint32_t alarm_id;
  uint16_t duration_s, window_s, report_interval_s;
  float    phi_hard_deg;       /* NaN nếu sai kiểu */
  uint8_t  profile, scenario, sea_state, mode, timewarp, model, mai_caution, debounce_n;
} svmg_cmd_t;

typedef struct {
  char          cmd_id[SVMG_CMD_ID_LEN];
  uint8_t       applied;       /* 1 = APPLIED, 0 = REJECTED */
  svmg_reason_t reason;        /* SVMG_R_OK khi applied */
  uint32_t      config_version;
} svmg_cmd_ack_t;

/* Hook thực thi hiệu ứng thật. Trả SVMG_R_OK, hoặc mã từ chối; SVMG_R_PENDING nghĩa là đã bắt đầu, ack gửi sau
 * (dùng cho calibrate_zero). Hook để NULL -> UNSUPPORTED. Tham số đã được svmg_cmd_exec kiểm biên. */
typedef struct {
  void *ctx;
  svmg_reason_t (*ack_alarm)(void *ctx, uint32_t alarm_id, int has_alarm);
  svmg_reason_t (*mute_alarm)(void *ctx, uint16_t duration_s);
  svmg_reason_t (*set_profile)(void *ctx, uint8_t profile);
  svmg_reason_t (*set_threshold)(void *ctx, const svmg_cmd_t *cmd);       /* đọc cmd->has + trường tương ứng; áp nguyên tử */
  svmg_reason_t (*calibrate_zero)(void *ctx);
  svmg_reason_t (*restart_device)(void *ctx);
  svmg_reason_t (*start_voyage)(void *ctx);
  svmg_reason_t (*stop_voyage)(void *ctx);
  /* mở rộng */
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
