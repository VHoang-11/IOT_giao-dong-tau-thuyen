/* svmg_common.h - kiểu dữ liệu dùng chung của lõi M1 (C99, không malloc, không Arduino).
 *
 * LƯU Ý ĐỐI CHIẾU: tên enum/struct ở đây là bản của M1 viết theo Phụ lục A/B của đề cương v2.0.
 * Khi contracts/svmg_core.h được chốt, đối chiếu và gộp (xem firmware/docs/CONTRACT_PROPOSALS.md).
 */
#ifndef SVMG_COMMON_H
#define SVMG_COMMON_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SVMG_G          9.80665f
#define SVMG_PI         3.14159265358979f
#define SVMG_RAD2DEG    57.29577951f
#define SVMG_DEG2RAD    0.01745329252f

/* Lớp chuyển động (thứ tự = chỉ số nhãn đề xuất cho mô hình RF). */
typedef enum {
  SVMG_NORMAL = 0,
  SVMG_HIGH_ROLL = 1,
  SVMG_PERSISTENT_OFFSET = 2,
  SVMG_AMPLITUDE_GROWTH = 3,
  SVMG_UNKNOWN = 4,   /* không đủ dữ liệu/độ tin cậy - KHÔNG BAO GIỜ hiển thị như NORMAL */
  SVMG_FAULT = 5      /* lỗi cảm biến */
} svmg_class_t;

/* Chất lượng dữ liệu của một lần cập nhật. */
typedef enum { SVMG_ST_OK = 0, SVMG_ST_UNKNOWN = 1, SVMG_ST_FAULT = 2 } svmg_status_t;

/* Nguồn dữ liệu (phải hiển thị rõ trên LCD/log/MQTT). */
typedef enum { SVMG_SRC_SENSOR = 0, SVMG_SRC_SIMULATION = 1 } svmg_source_t;

/* Mức cảnh báo. ACK là cờ chồng lên mức, không phải mức. */
typedef enum {
  SVMG_LVL_NORMAL = 0,
  SVMG_LVL_CAUTION = 1,
  SVMG_LVL_WARNING = 2,
  SVMG_LVL_CRITICAL = 3
} svmg_level_t;

/* Mã lý do từ chối lệnh/cấu hình (đúng tập trong mục 8.2 của đề cương). */
typedef enum {
  SVMG_R_OK = 0,
  SVMG_R_BAD_PARAM,
  SVMG_R_FORBIDDEN_STATE,
  SVMG_R_NOT_STATIC,
  SVMG_R_EXPIRED,
  SVMG_R_UNSUPPORTED,
  SVMG_R_PENDING = 100   /* nội bộ: lệnh bất đồng bộ đã bắt đầu, ack gửi sau */
} svmg_reason_t;

/* Mẫu chuyển động chuẩn hóa theo SI (acquireMotionSample trả về). */
typedef struct {
  float ax, ay, az;     /* m/s^2 */
  float gx, gy, gz;     /* rad/s */
  float t;              /* s (đồng hồ mô phỏng hoặc thời gian thực) */
  uint8_t source_mode;  /* svmg_source_t */
  uint8_t valid;        /* 0 = đọc lỗi/thiếu mẫu */
} svmg_motion_sample_t;

/* Loại sự kiện đẩy lên MQTT topic "event" (QoS 1) và vào bộ đệm offline. */
typedef enum {
  SVMG_EV_NONE = 0,
  SVMG_EV_ALARM_STATE = 1,    /* đổi mức cảnh báo; level=NORMAL nghĩa là CLEARED */
  SVMG_EV_ALARM_ACK = 2,
  SVMG_EV_ALARM_MUTE = 3,
  SVMG_EV_MODE_CHANGE = 4,
  SVMG_EV_SCENARIO_CHANGE = 5,
  SVMG_EV_FAULT = 6,          /* sensor FAULT bắt đầu; val = bit lý do */
  SVMG_EV_FAULT_CLEARED = 7,
  SVMG_EV_CONFIG_APPLIED = 8,
  SVMG_EV_CALIBRATION = 9,    /* val = svmg_reason_t */
  SVMG_EV_BOOT = 10
} svmg_event_type_t;

/* ack: nguồn xác nhận */
#define SVMG_ACKBY_NONE   0
#define SVMG_ACKBY_BUTTON 1
#define SVMG_ACKBY_REMOTE 2

typedef struct {
  uint32_t seq;        /* gán khi vào bộ đệm (0 = chưa gán) */
  uint32_t alarm_id;   /* 0 = chưa có */
  float    t_sim_s;
  uint8_t  type;       /* svmg_event_type_t */
  uint8_t  level;      /* svmg_level_t */
  uint8_t  prev_level;
  uint8_t  cls;        /* svmg_class_t */
  uint8_t  acked_by;   /* SVMG_ACKBY_* */
  uint8_t  aux;        /* theo loại: MODE_CHANGE: mode mới; SCENARIO: chỉ số kịch bản */
  uint16_t val;        /* theo loại: MUTE: giây; FAULT: bit lý do; SCENARIO: sea state */
} svmg_event_t;

#ifdef __cplusplus
}
#endif
#endif
