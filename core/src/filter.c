/**
 * Bộ lọc bù (complementary filter), thông thấp, giảm mẫu 20→2 Hz
 * TODO: M1-02 — Implement
 */
#include "svmg_core.h"

static float roll_angle = 0.0f;
static float pitch_angle = 0.0f;
static const float ALPHA = 0.993f;  // τ ≈ 7s, Δt = 0.05s

void filterUpdate(MotionSample *sample) {
    // TODO: Implement complementary filter
    // angle = α × (angle_prev + gyro_rate × Δt) + (1 − α) × accel_angle
    (void)sample;
}
