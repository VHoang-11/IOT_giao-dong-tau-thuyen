/**
 * SVMG Bộ sinh tín hiệu mô phỏng — header
 */
#ifndef SVMG_SIM_H
#define SVMG_SIM_H

#include "svmg_core.h"

typedef struct {
    float T0;           // chu kỳ lắc tự nhiên (s)
    float zeta;         // hệ số tắt dần
    float sigma_w;      // độ lệch chuẩn kích động sóng
    float h;            // biên độ kích thích tham số
    float b;            // heel offset (độ nghiêng lệch tĩnh)
    float kappa;        // hệ số phi tuyến bậc 3
    uint32_t seed;      // xorshift32 seed
} SimConfig;

void simInit(const SimConfig *cfg);
MotionSample simStep(float dt);
uint32_t xorshift32(uint32_t *state);

#endif // SVMG_SIM_H
