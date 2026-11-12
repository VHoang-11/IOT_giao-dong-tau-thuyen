/**
 * Smart Vessel Motion Guard — Lõi C dùng chung
 * Dùng cho cả ESP32 (firmware) và máy chủ (kiểm thử hàng loạt)
 */
#ifndef SVMG_CORE_H
#define SVMG_CORE_H

#include <stdint.h>
#include <stdbool.h>

/* ── Cấu trúc dữ liệu ── */

typedef struct {
    float ax, ay, az;   // m/s²
    float gx, gy, gz;   // rad/s
    float t;            // s (thời gian mô phỏng)
    uint8_t source_mode; // 0 = SENSOR, 1 = SIMULATION
    bool valid;
} MotionSample;

typedef enum {
    CLASS_NORMAL = 0,
    CLASS_HIGH_ROLL,
    CLASS_PERSISTENT_OFFSET,
    CLASS_AMPLITUDE_GROWTH,
    CLASS_UNKNOWN,
    CLASS_FAULT
} MotionClass;

typedef enum {
    ALARM_NORMAL = 0,
    ALARM_CAUTION,
    ALARM_WARNING,
    ALARM_CRITICAL,
    ALARM_ACKED
} AlarmLevel;

typedef struct {
    float rms_roll;
    float p95_roll;
    float rms_pitch;
    float p95_pitch;
    float max_abs_roll;
    float energy_roll;
    float zero_crossing_rate;
    float mean_roll;
    float mean_pitch;
    float std_roll;
    float trend_rms_slope;
    float heel_duration_s;
    float data_quality_pct;
    bool sensor_ok;
} FeatureVector;

/* ── API ── */

MotionSample acquireMotionSample(uint8_t mode);
void filterUpdate(MotionSample *sample);
FeatureVector extractFeatures(void);
MotionClass classifyRF(const FeatureVector *fv);
MotionClass classifyBaselineB(const FeatureVector *fv);
int computeMAI(const FeatureVector *fv);
AlarmLevel updateAlarmFSM(MotionClass cls, int mai);

#endif // SVMG_CORE_H
