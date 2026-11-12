/* svmg_alarm.h - M1-05: máy trạng thái vòng đời cảnh báo (đề cương mục 8.1, hình 8.1, bảng 8.1).
 *
 * Mức: NORMAL -> CAUTION -> WARNING -> CRITICAL. ACK/MUTE là cờ chồng lên mức (không phải mức).
 * Hai đồng hồ tách biệt (đề cương 5.3/8.1):
 *   - đồng hồ MÔ PHỎNG: số lần svmg_alarm_update() (mỗi 5 s mô phỏng) -> chống nhấp nháy N, trễ giải tỏa;
 *   - đồng hồ THỰC (now_ms, millis()): T_ack = 60 s leo thang, hạn mute.
 * Bất biến an toàn: không có API nào hạ thấp mức đang có hoặc tắt lớp ngưỡng cứng; chỉ ACK (tắt còi, giữ LED)
 * và mute (<= 300 s, chỉ khi WARNING) là được phép; điều kiện hard luôn đưa lên CRITICAL.
 */
#ifndef SVMG_ALARM_H
#define SVMG_ALARM_H

#include "svmg_common.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SVMG_ALARM_MAX_EVENTS 4

typedef struct {
  uint8_t  debounce_n;      /* N lần cập nhật liên tiếp cùng lớp để lên WARNING (CONSERVATIVE 4 / STANDARD 3 / SENSITIVE 2) */
  uint8_t  mai_caution;     /* ngưỡng MAI cho CAUTION */
  uint8_t  clear_updates;   /* số lần cập nhật hết điều kiện để giải tỏa (6 = 30 s) */
  uint16_t max_mute_s;      /* 300 */
  uint32_t t_ack_ms;        /* 60000 (thời gian thực) */
} svmg_alarm_cfg_t;

typedef struct {
  svmg_class_t  cls;        /* lớp của mô hình chính */
  svmg_status_t status;     /* chất lượng dữ liệu */
  uint8_t       mai;
  uint8_t       mai_valid;
  uint8_t       hard;       /* lớp ngưỡng cứng đang active */
  float         t_sim_s;
  uint32_t      now_ms;
} svmg_alarm_in_t;

typedef struct {
  svmg_alarm_cfg_t cfg;
  svmg_level_t  level;
  uint8_t       acked, muted;
  svmg_class_t  cls;               /* lớp đang gây cảnh báo */
  svmg_class_t  streak_cls;
  uint8_t       streak, clear_count;
  svmg_status_t status;            /* chất lượng dữ liệu lần cập nhật gần nhất (để hiển thị) */
  uint32_t      alarm_id, next_id;
  uint32_t      raised_ms, ack_ms, mute_until_ms;
  float         t_sim_s;
  /* thống kê vận hành */
  uint32_t      n_raised, n_escalated, n_acked, n_cleared, sum_ack_ms;
} svmg_alarm_t;

void svmg_alarm_default_cfg(svmg_alarm_cfg_t *c);
void svmg_alarm_init(svmg_alarm_t *a, const svmg_alarm_cfg_t *c);
void svmg_alarm_set_cfg(svmg_alarm_t *a, const svmg_alarm_cfg_t *c);   /* giữ nguyên trạng thái */

/* Mỗi 5 s mô phỏng. Trả số sự kiện ghi vào ev[] (tối đa SVMG_ALARM_MAX_EVENTS). */
int svmg_alarm_update(svmg_alarm_t *a, const svmg_alarm_in_t *in, svmg_event_t *ev);
/* Gọi ngay khi lớp ngưỡng cứng vừa kích hoạt (không chờ chu kỳ 5 s). */
int svmg_alarm_force_critical(svmg_alarm_t *a, float t_sim_s, uint32_t now_ms, svmg_event_t *ev);
/* Gọi thường xuyên theo thời gian thực: leo thang T_ack, hết hạn mute. */
int svmg_alarm_tick(svmg_alarm_t *a, uint32_t now_ms, svmg_event_t *ev);
/* ACK luôn được chấp nhận (SVMG_R_OK); chỉ có tác dụng khi level >= WARNING. */
int svmg_alarm_ack(svmg_alarm_t *a, uint8_t by, uint32_t now_ms, svmg_event_t *ev, svmg_reason_t *res);
/* mute: BAD_PARAM nếu duration ngoài 1..300; FORBIDDEN_STATE nếu level != WARNING hoặc đã ACK (kể cả CRITICAL). */
int svmg_alarm_mute(svmg_alarm_t *a, uint16_t duration_s, uint32_t now_ms, svmg_event_t *ev, svmg_reason_t *res);

/* ---- Đầu ra cục bộ (LED/buzzer) suy ra từ trạng thái ---- */
typedef enum { SVMG_OUT_OFF = 0, SVMG_OUT_ON = 1, SVMG_OUT_BLINK_SLOW = 2, SVMG_OUT_BLINK_FAST = 3 } svmg_out_t;
typedef enum { SVMG_BUZ_OFF = 0, SVMG_BUZ_INTERMITTENT = 1, SVMG_BUZ_CONTINUOUS = 2 } svmg_buz_t;
typedef struct { uint8_t led_g, led_y, led_r, buzzer; } svmg_alarm_out_t;
void svmg_alarm_outputs(const svmg_alarm_t *a, uint32_t now_ms, svmg_alarm_out_t *out);

const char *svmg_level_name(svmg_level_t l);
const char *svmg_class_name(svmg_class_t c);

#ifdef __cplusplus
}
#endif
#endif
