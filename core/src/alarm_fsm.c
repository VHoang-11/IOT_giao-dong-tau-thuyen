/**
 * Máy trạng thái cảnh báo
 * NORMAL → CAUTION → WARNING → CRITICAL → ACKED → NORMAL
 * TODO: M1-05 — Implement
 */
#include "svmg_core.h"

static AlarmLevel current_level = ALARM_NORMAL;

AlarmLevel updateAlarmFSM(MotionClass cls, int mai) {
    (void)cls; (void)mai;
    // TODO: Implement alarm state machine with debounce
    return current_level;
}
