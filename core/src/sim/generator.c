/**
 * Bộ sinh tín hiệu (C port) — dao động tử roll bậc 2
 * TODO: M2-02 — Implement (cổng từ Python)
 */
#include "svmg_sim.h"

static SimConfig sim_cfg;
static uint32_t rng_state;
static float phi = 0.0f;     // roll angle (rad)
static float dphi = 0.0f;    // angular velocity (rad/s)

uint32_t xorshift32(uint32_t *state) {
    uint32_t x = *state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

void simInit(const SimConfig *cfg) {
    sim_cfg = *cfg;
    rng_state = cfg->seed;
    phi = 0.0f;
    dphi = 0.0f;
}

MotionSample simStep(float dt) {
    MotionSample s = {0};
    s.source_mode = 1; // SIMULATION
    s.valid = true;
    // TODO: Implement Euler semi-implicit integration
    // d²φ/dt² + 2ζω₀·dφ/dt + ω₀²·[1 + h·cos(Ωt)]·φ + ω₀²·κ·φ³ = ω₀²·[b + w(t)]
    return s;
}
