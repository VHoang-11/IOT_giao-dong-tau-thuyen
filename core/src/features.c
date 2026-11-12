/**
 * Trích xuất đặc trưng cửa sổ 60s/180s
 * TODO: M1-03 — Implement
 */
#include "svmg_core.h"

FeatureVector extractFeatures(void) {
    FeatureVector fv = {0};
    // TODO: Implement feature extraction from sliding windows
    // Window 60s (120 samples @ 2Hz): rms_roll, p95_roll, rms_pitch, etc.
    // Window 180s (360 samples @ 2Hz): mean_roll, trend_rms_slope, etc.
    return fv;
}
