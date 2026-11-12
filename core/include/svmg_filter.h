/* svmg_filter.h - M1-02: chuẩn hóa IMU, góc từ gia tốc, bộ lọc bù, lọc thông thấp, giảm mẫu 20 -> 2 Hz.
 * Quy ước trục (chuẩn hàng không, xem NXP AN3461):
 *   roll  = atan2(ay, az),  tốc độ roll  = gx
 *   pitch = atan2(-ax, sqrt(ay^2 + az^2)), tốc độ pitch = gy
 * Đơn vị: m/s^2, rad/s, rad, s. Chỉ dùng float (ESP32 chỉ có FPU đơn).
 */
#ifndef SVMG_FILTER_H
#define SVMG_FILTER_H

#include "svmg_common.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ---- 1. Quy đổi thanh ghi thô MPU6050 (±2 g, ±250 °/s) sang SI ---- */
#define SVMG_IMU_ACCEL_LSB_PER_G   16384.0f
#define SVMG_IMU_GYRO_LSB_PER_DPS  131.0f
#define SVMG_IMU_F_SATURATED       0x01

typedef struct { int16_t ax, ay, az, gx, gy, gz; } svmg_imu_raw_t;

/* Trả về cờ SVMG_IMU_F_*; out->valid = 1, out->t và source_mode do người gọi đặt. */
uint8_t svmg_imu_raw_to_si(const svmg_imu_raw_t *raw, svmg_motion_sample_t *out);

/* ---- 2. Góc từ gia tốc ---- */
void    svmg_accel_to_angles(float ax, float ay, float az, float *roll_rad, float *pitch_rad);
/* 1 nếu |a| nằm trong [0.5 g, 1.5 g] (gia tốc kế đáng tin để hiệu chỉnh góc). */
uint8_t svmg_accel_gate_ok(float ax, float ay, float az);

/* ---- 3. Bộ lọc bù ---- */
#define SVMG_CF_GATED    0x01   /* bước này chỉ tích phân gyro */
#define SVMG_CF_NOT_INIT 0x02   /* chưa khởi tạo (mẫu đầu bị cổng chặn) - chưa có góc */

typedef struct { float tau_s; float roll, pitch; uint8_t initialized; } svmg_cf_t;

void    svmg_cf_init(svmg_cf_t *cf, float tau_s);
void    svmg_cf_reset(svmg_cf_t *cf);
/* alpha = tau/(tau+dt), tính lại theo dt thực. Mẫu đầu lấy góc từ gia tốc. */
uint8_t svmg_cf_update(svmg_cf_t *cf, float ax, float ay, float az, float gx, float gy, float dt);

/* ---- 4. Biquad Butterworth bậc 2 thông thấp (dạng chuyển vị II) ---- */
typedef struct { float b0, b1, b2, a1, a2; } svmg_biquad_coef_t;
typedef struct { svmg_biquad_coef_t c; float z1, z2; } svmg_biquad_t;

void  svmg_biquad_butter2_lp(svmg_biquad_coef_t *c, float fc_hz, float fs_hz);
/* Khởi tạo ở trạng thái xác lập cho đầu vào hằng x0 -> không có quá độ. */
void  svmg_biquad_init(svmg_biquad_t *f, const svmg_biquad_coef_t *c, float x0);
float svmg_biquad_step(svmg_biquad_t *f, float x);

/* ---- 5. Pipeline 20 Hz -> 2 Hz ---- */
#define SVMG_PIPE_F_RESTARTED 0x01  /* có khoảng trống dữ liệu -> đã reset */
#define SVMG_PIPE_F_GATED     0x02  /* trong khối có bước bị cổng gia tốc */
#define SVMG_PIPE_F_PARTIAL   0x04  /* khối thiếu mẫu hợp lệ */
/* Bước lùi thời gian lớn hơn ngưỡng này (s) được hiểu là đồng hồ quấn vòng chứ không phải lỗi: dt = 1/fs. */
#define SVMG_PIPE_WRAP_S      1000.0f

typedef struct {
  float   tau_s;        /* hằng số thời gian bộ lọc bù (mặc định 7.5 s) */
  float   fc_hz;        /* tần số cắt (0.5 Hz) */
  float   fs_hz;        /* tần số lấy mẫu vào (20 Hz) */
  float   max_gap_s;    /* dt lớn hơn thì reset (0.5 s) */
  uint8_t decim;        /* hệ số giảm mẫu (10) */
} svmg_pipeline_cfg_t;

typedef struct {
  float   t_s;
  float   roll_rad, pitch_rad;
  float   gx_rads, gy_rads;
  uint8_t n_valid;      /* số mẫu hợp lệ trong khối (0..decim) */
  uint8_t flags;        /* SVMG_PIPE_F_* */
} svmg_sample2hz_t;

typedef struct {
  svmg_pipeline_cfg_t cfg;
  svmg_cf_t           cf;
  svmg_biquad_coef_t  coef;
  svmg_biquad_t       lp[4];       /* roll, pitch, gx, gy */
  float               y[4];        /* giá trị lọc gần nhất */
  uint8_t             lp_init;
  uint8_t             phase, n_valid, blk_flags;
  uint8_t             pending_restart;
  uint8_t             have_t;
  float               last_t;
  uint32_t            cnt_in, cnt_invalid, cnt_gap, cnt_out;
} svmg_pipeline_t;

void svmg_pipeline_default_cfg(svmg_pipeline_cfg_t *cfg);
void svmg_pipeline_init(svmg_pipeline_t *p, const svmg_pipeline_cfg_t *cfg);
/* Xóa trạng thái lọc (giữ bộ đếm thống kê). */
void svmg_pipeline_reset(svmg_pipeline_t *p);
/* Đẩy một mẫu 20 Hz. Trả 1 nếu *out được ghi (mỗi `decim` mẫu). Mẫu valid=0 vẫn phải được đẩy vào. */
int  svmg_pipeline_push(svmg_pipeline_t *p, const svmg_motion_sample_t *s, svmg_sample2hz_t *out);

#ifdef __cplusplus
}
#endif
#endif
