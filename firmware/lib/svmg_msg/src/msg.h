/* msg.h - tạo/phân tích bản tin MQTT (JSON) cho thiết bị. Không phụ thuộc Arduino -> kiểm thử được trên máy.
 *
 * Quyết định thư viện (M1-06): TẠO bản tin bằng snprintf vào bộ đệm tĩnh (không heap, kích thước biết trước,
 * chặn tràn); PHÂN TÍCH bản tin vào bằng ArduinoJson v6 StaticJsonDocument (không cấp phát động, từ chối JSON hỏng).
 * Lý do và số đo flash/RAM: xem firmware/docs/M1-06_mqtt_json_decision.md.
 * Mọi tên trường lấy từ Phụ lục A đề cương v2.0; chờ đối chiếu với các file schema trong contracts/schemas.
 */
#ifndef SVMG_MSG_H
#define SVMG_MSG_H

#include <stddef.h>
#include <stdint.h>
#include "svmg_common.h"
#include "svmg_cmd.h"
#include "svmg_config.h"
#include "svmg_engine.h"

#ifndef SVMG_BOOT_ID_LEN
#define SVMG_BOOT_ID_LEN 8      /* ký tự hex; 8 (32 bit) để va chạm giữa các lần khởi động gần như bằng 0 */
#endif

struct MsgIdent {
  const char *device_id;        /* "vessel-demo-01" */
  char        boot_id[SVMG_BOOT_ID_LEN + 1];
  const char *fw;               /* "1.0.0" */
  const char *model_version;    /* "rf_v1" hoặc "none" */
};

struct MsgTelemetry {
  float    t_sim_s;
  uint64_t uptime_ms;           /* 64 bit: không quấn ở 49 ngày */
  uint8_t  timewarp;
  uint8_t  source_mode;         /* svmg_source_t */
  int      scenario;            /* -1 nếu SENSOR */
  float    roll_deg, pitch_deg, rms_roll_deg, heel_offset_deg, trend_rms_deg_per_min;
  uint8_t  cls_rf, cls_b;       /* svmg_class_t */
  uint8_t  mai;
  uint8_t  alarm_level;         /* svmg_level_t */
  uint32_t config_version;
  bool     sensor_ok;
  /* trường mở rộng, chỉ phát khi SVMG_TELEMETRY_EXTRAS (mặc định tắt vì schema có thể cấm trường lạ) */
  bool     acked;
  uint8_t  data_status;         /* svmg_status_t */
  uint8_t  sea_state;
};

struct MsgHealth {
  uint64_t uptime_ms;
  uint32_t heap_free, heap_min;
  int      rssi;                /* 0 nếu không có WiFi */
  uint32_t reconnects, i2c_errors, samples_invalid, gaps, loop_overruns;
  uint32_t infer_us_avg, infer_us_max;
  uint32_t feature_valid_mask;
  uint32_t feature_update_us_last,feature_update_us_max;
  uint8_t data_status;
  uint32_t evbuf_depth, evbuf_dropped, cmd_exec, cmd_rejected, rx_dropped;
  bool     sensor_ok;
};

/* Điền MsgTelemetry từ engine (một nơi duy nhất, dùng cho cả firmware và kiểm schema trên máy). sensor_ok theo chế độ nguồn. */
void msg_fill_telemetry(MsgTelemetry *t, const svmg_engine_t *e, uint64_t uptime_ms, double t_abs_s, uint8_t timewarp,
                        uint8_t source_mode, int scenario, bool sensor_ok, uint8_t sea_state);

/* Các hàm build trả số byte đã ghi (không tính NUL), 0 nếu không đủ chỗ. */
size_t msg_build_telemetry(char *buf, size_t cap, const MsgIdent &id, uint32_t seq, const MsgTelemetry &t);
/* Theo contracts/schemas/event.json chỉ có type = ALARM_STATE. ALARM_ACK được phát dưới dạng ALARM_STATE giữ nguyên mức
 * (prev_level = level) kèm acked_by ("device_button" | "remote") để backend ghi MTTA. Các loại khác (MODE_CHANGE, FAULT, BOOT,
 * CONFIG_APPLIED, CALIBRATION, MUTE...) KHÔNG nằm trong schema nên bị từ chối (trả 0) trừ khi biên dịch với SVMG_EXT_EVENTS. */
size_t msg_build_event(char *buf, size_t cap, const MsgIdent &id, const svmg_event_t &e);   /* dùng e.seq */
bool   msg_event_publishable(uint8_t svmg_event_type);   /* true nếu loại sự kiện này được phát lên topic event */
size_t msg_build_status_online(char *buf, size_t cap, const MsgIdent &id, uint32_t config_version);
size_t msg_build_status_offline(char *buf, size_t cap);                                      /* nội dung Last Will */
size_t msg_build_health(char *buf, size_t cap, const MsgIdent &id, uint32_t seq, const MsgHealth &h);
size_t msg_build_cmd_ack(char *buf, size_t cap, const svmg_cmd_ack_t &a, const float *zero_roll_deg, const float *zero_pitch_deg);
#ifdef SVMG_EXT_TRACE
/* trace: một đoạn (chunk) của chuỗi roll/pitch 10 Hz. cdeg = centi-độ. */
size_t msg_build_trace(char *buf, size_t cap, const MsgIdent &id, uint32_t seq, float t_end_s, uint16_t window_s,
                       int chunk, int chunks, const int16_t *roll_cdeg, const int16_t *pitch_cdeg, int n);
#endif

/* Phân tích. Trả true nếu JSON hợp lệ và có cmd_id/trường bắt buộc. Tham số sai kiểu/sai miền được đánh dấu
 * để svmg_cmd_exec trả BAD_PARAM (không loại bỏ im lặng). */
bool msg_parse_cmd(const char *payload, size_t len, svmg_cmd_t *out);
/* config: phân tích thành BẢN VÁ (svmg_config_patch_t). Trả false nếu JSON hỏng/thiếu config_version/trường sai kiểu hoặc sai enum
 * (-> REJECTED BAD_PARAM). patch.crc_state: ABSENT nếu không có `crc`; OK/BAD sau khi tính lại CRC-16/CCITT-FALSE trên JSON chuẩn tắc
 * (khóa sắp xếp, nhỏ gọn, bỏ crc) đúng như backend/commands/config_service.compute_crc. */
bool msg_parse_config(const char *payload, size_t len, svmg_config_patch_t *out);
/* Chỉ để kiểm thử/đối chiếu với backend: CRC chuẩn tắc của một payload (bỏ trường crc). */
bool msg_config_canonical_crc(const char *payload, size_t len, uint16_t *crc);

/* Topic thiết bị dùng (nguồn duy nhất; test so với infra/mosquitto/acl). */
extern const char *const MSG_PUBLISH_TOPICS[];     /* telemetry, event, status, health, cmd/ack  (kèm "trace" nếu SVMG_EXT_TRACE) */
extern const int MSG_PUBLISH_TOPIC_COUNT;
extern const char *const MSG_SUBSCRIBE_TOPICS[];   /* cmd, config */
extern const int MSG_SUBSCRIBE_TOPIC_COUNT;

/* Tiện ích chuỗi (công khai để test). */
size_t msg_alarm_id_str(char *buf, size_t cap, uint32_t id);   /* "A-0042" */

#endif
