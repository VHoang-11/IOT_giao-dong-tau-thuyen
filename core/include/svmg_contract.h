/* svmg_contract.h - cầu nối giữa kiểu của lõi M1 (svmg_*) và header hợp đồng
 * core/include/svmg_core.h (MotionSample, MotionClass, AlarmLevel,
 * FeatureVector). Chỉ dùng trong C (svmg_core.h không có extern "C"); không sửa
 * svmg_core.h. Thứ tự giá trị enum của MotionClass và svmg_class_t TRÙNG NHAU
 * (0..5), AlarmLevel 0..3 trùng svmg_level_t (ALARM_ACKED=4 là cờ, không phải
 * mức). */
#ifndef SVMG_CONTRACT_H
#define SVMG_CONTRACT_H

#include "svmg_common.h"
#include "svmg_core.h"
#include "svmg_features.h"

_Static_assert((int)CLASS_NORMAL == (int)SVMG_NORMAL &&
                   (int)CLASS_HIGH_ROLL == (int)SVMG_HIGH_ROLL &&
                   (int)CLASS_PERSISTENT_OFFSET ==
                       (int)SVMG_PERSISTENT_OFFSET &&
                   (int)CLASS_AMPLITUDE_GROWTH == (int)SVMG_AMPLITUDE_GROWTH &&
                   (int)CLASS_UNKNOWN == (int)SVMG_UNKNOWN &&
                   (int)CLASS_FAULT == (int)SVMG_FAULT,
               "MotionClass phai trung thu tu voi svmg_class_t");
_Static_assert((int)ALARM_NORMAL == (int)SVMG_LVL_NORMAL &&
                   (int)ALARM_CAUTION == (int)SVMG_LVL_CAUTION &&
                   (int)ALARM_WARNING == (int)SVMG_LVL_WARNING &&
                   (int)ALARM_CRITICAL == (int)SVMG_LVL_CRITICAL,
               "AlarmLevel phai trung thu tu voi svmg_level_t");

static inline svmg_motion_sample_t
svmg_sample_from_contract(const MotionSample *s) {
  svmg_motion_sample_t o;
  o.ax = s->ax;
  o.ay = s->ay;
  o.az = s->az;
  o.gx = s->gx;
  o.gy = s->gy;
  o.gz = s->gz;
  o.t = s->t;
  o.source_mode = s->source_mode;
  o.valid = s->valid ? 1 : 0;
  return o;
}

static inline MotionSample
svmg_sample_to_contract(const svmg_motion_sample_t *s) {
  MotionSample o;
  o.ax = s->ax;
  o.ay = s->ay;
  o.az = s->az;
  o.gx = s->gx;
  o.gy = s->gy;
  o.gz = s->gz;
  o.t = s->t;
  o.source_mode = s->source_mode;
  o.valid = s->valid != 0;
  return o;
}

/* Named copies; quality metadata stays outside the RF vector. */
_Static_assert(sizeof(FeatureVector) == SVMG_N_FEATURES * sizeof(float),
               "RF vector must be 23 floats");
static inline void svmg_features_from_contract(const FeatureVector *v,
                                               svmg_features_t *f) {
  *f = (svmg_features_t){0};
#define COPY(name) f->name = v->name;
  SVMG_FEATURE_FIELDS(COPY)
#undef COPY
  f->rms_roll = f->roll_rms_60;
  f->mean_roll = f->roll_mean_180;
  f->trend_rms_slope = f->roll_rms_slope_180;
}
static inline void svmg_features_to_contract(const svmg_features_t *f,
                                             FeatureVector *v) {
#define COPY(name) v->name = f->name;
  SVMG_FEATURE_FIELDS(COPY)
#undef COPY
}

bool checkSafetyEnvelope(float roll_deg,
                         float dt); /* safety.c: ngưỡng cứng 20 deg / 5 s, trạng
                                       thái nội bộ, dt tính bằng giây */
MotionClass classifyBaselineB(
    const FeatureVector *fv); /* baseline.c (đã khai báo trong svmg_core.h) */
int computeMAI(
    const FeatureVector *fv); /* mai.c (đã khai báo trong svmg_core.h) */

#endif
