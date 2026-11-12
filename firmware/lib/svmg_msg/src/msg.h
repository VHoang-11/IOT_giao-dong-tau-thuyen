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
  uint32_t uptime_ms;
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
  uint32_t uptime_ms, heap_free, heap_min;
  int      rssi;                /* 0 nếu không có WiFi */
  uint32_t reconnects, i2c_errors, samples_invalid, gaps, loop_overruns;
  uint32_t infer_us_avg, infer_us_max;
  uint32_t evbuf_depth, evbuf_dropped, cmd_exec, cmd_rejected, rx_dropped;
  bool     sensor_ok;
};

/* Các hàm build trả số byte đã ghi (không tính NUL), 0 nếu không đủ chỗ. */
size_t msg_build_telemetry(char *buf, size_t cap, const MsgIdent &id, uint32_t seq, const MsgTelemetry &t);
size_t msg_build_event(char *buf, size_t cap, const MsgIdent &id, const svmg_event_t &e);   /* dùng e.seq */
size_t msg_build_status_online(char *buf, size_t cap, const MsgIdent &id, uint32_t config_version);
size_t msg_build_status_offline(char *buf, size_t cap);                                      /* nội dung Last Will */
size_t msg_build_health(char *buf, size_t cap, const MsgIdent &id, uint32_t seq, const MsgHealth &h);
size_t msg_build_cmd_ack(char *buf, size_t cap, const svmg_cmd_ack_t &a, const float *zero_roll_deg, const float *zero_pitch_deg);
/* trace: một đoạn (chunk) của chuỗi roll/pitch 2 Hz. cdeg = centi-độ. */
size_t msg_build_trace(char *buf, size_t cap, const MsgIdent &id, uint32_t seq, float t_end_s, uint16_t window_s,
                       int chunk, int chunks, const int16_t *roll_cdeg, const int16_t *pitch_cdeg, int n);

/* Phân tích. Trả true nếu JSON hợp lệ và có cmd_id/trường bắt buộc. Tham số sai kiểu/sai miền được đánh dấu
 * để svmg_cmd_exec trả BAD_PARAM (không loại bỏ im lặng). */
bool msg_parse_cmd(const char *payload, size_t len, svmg_cmd_t *out);
/* config: trả true nếu đủ trường; *crc là CRC khai báo trong bản tin. false -> REJECTED BAD_PARAM. */
bool msg_parse_config(const char *payload, size_t len, svmg_config_t *out, uint16_t *crc);

/* Tiện ích chuỗi (công khai để test). */
size_t msg_alarm_id_str(char *buf, size_t cap, uint32_t id);   /* "A-0042" */

#endif
