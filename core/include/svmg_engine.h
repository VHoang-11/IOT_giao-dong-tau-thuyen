/* svmg_engine.h - ghép chuỗi xử lý của thiết bị (C thuần, chạy được trên máy chủ để kiểm thử hàng loạt):
 *   mẫu 20 Hz -> lọc/giảm mẫu 2 Hz -> (trừ hiệu chuẩn) -> cửa sổ -> đặc trưng -> RF + Baseline B + MAI
 *   -> lớp ngưỡng cứng -> máy trạng thái cảnh báo -> sự kiện.
 * Không phụ thuộc mạng: cảnh báo cục bộ hoạt động như nhau khi MQTT mất (đề cương FR06, T05).
 * Không malloc; không Arduino. Tầng firmware chỉ nối phần cứng, MQTT và lưu cấu hình.
 */
#ifndef SVMG_ENGINE_H
#define SVMG_ENGINE_H

#include "svmg_common.h"
#include "svmg_filter.h"
#include "svmg_features.h"
#include "svmg_decision.h"
#include "svmg_alarm.h"
#include "svmg_config.h"
#include "svmg_calib.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SVMG_ENGINE_MAX_EV 8
#define SVMG_BLOCK_MIN_VALID 5     /* khối 0.5 s cần >= 5/10 mẫu hợp lệ mới tính là mẫu 2 Hz hợp lệ */

/* Mô hình RF do M2 xuất (qua infer.c ở firmware). Trả SVMG_UNKNOWN nếu độ tin cậy thấp/ngoài miền huấn luyện. */
typedef svmg_class_t (*svmg_rf_fn)(void *ctx, const float *features, int n_features);

typedef struct {
  svmg_class_t   cls_rf, cls_b, cls_primary;
  svmg_status_t  status;           /* chất lượng dữ liệu hiệu lực (đã tính cả việc mô hình trả UNKNOWN) */
  uint8_t        status_reason;    /* SVMG_Q_* */
  svmg_mai_t     mai;
  uint8_t        hard;
  uint8_t        model_fallback;   /* 1 nếu chọn RF nhưng chưa có mô hình -> đang dùng Baseline B */
  svmg_features_t feat;
  float          roll_deg, pitch_deg;   /* mẫu 2 Hz mới nhất đã trừ hiệu chuẩn */
  float          t_sim_s;
} svmg_decision_state_t;

typedef struct {
  svmg_pipeline_t pipe;
  svmg_window_t   win;
  svmg_safety_t   safety;
  svmg_alarm_t    alarm;
  svmg_calib_t    calib;
  svmg_config_t   cfg;
  svmg_baseline_params_t bp;
  svmg_mai_params_t      mp;
  svmg_quality_cfg_t     qc;
  svmg_rf_fn      rf;
  void           *rf_ctx;
  svmg_decision_state_t dec;
  svmg_status_t   prev_status;
  uint32_t        n_updates, n_compared, n_agree;
} svmg_engine_t;

typedef struct {
  uint8_t      got_2hz;        /* có mẫu 2 Hz mới (e->dec.roll_deg/pitch_deg) */
  uint8_t      got_update;     /* có quyết định mới (mỗi 5 s mô phỏng) */
  uint8_t      calib_done;     /* hiệu chuẩn vừa xong: firmware phải lưu cấu hình + trả ack */
  svmg_reason_t calib_result;
  uint8_t      n_ev;
  svmg_event_t ev[SVMG_ENGINE_MAX_EV];
} svmg_engine_out_t;

void svmg_engine_init(svmg_engine_t *e, const svmg_config_t *cfg);
void svmg_engine_set_rf(svmg_engine_t *e, svmg_rf_fn fn, void *ctx);
/* Áp cấu hình đã được svmg_config_validate chấp nhận. Giữ nguyên trạng thái cảnh báo. */
void svmg_engine_apply_config(svmg_engine_t *e, const svmg_config_t *cfg);
/* Đổi chế độ/kịch bản: xóa pipeline + cửa sổ + ngưỡng cứng, KHÔNG xóa trạng thái cảnh báo. */
void svmg_engine_restart_signal(svmg_engine_t *e);

/* Các hàm dưới đây ghi đè *out. Trả out->n_ev. */
int  svmg_engine_push(svmg_engine_t *e, const svmg_motion_sample_t *s, uint32_t now_ms, svmg_engine_out_t *out);
int  svmg_engine_tick(svmg_engine_t *e, uint32_t now_ms, svmg_engine_out_t *out);
int  svmg_engine_ack(svmg_engine_t *e, uint8_t by, uint32_t now_ms, svmg_engine_out_t *out);
int  svmg_engine_mute(svmg_engine_t *e, uint16_t duration_s, uint32_t now_ms, svmg_engine_out_t *out, svmg_reason_t *res);
svmg_reason_t svmg_engine_calibrate_start(svmg_engine_t *e);
float svmg_engine_agreement(const svmg_engine_t *e);   /* tỉ lệ đồng thuận RF/Baseline B, 1.0 nếu chưa có phép so */

#ifdef __cplusplus
}
#endif
#endif
