// STUB - KHÔNG phải bộ sinh của M2. Sóng sin tổng hợp để M1 thử chuỗi cảnh báo trên Wokwi trước khi M2 bàn giao.
// Không dùng kết quả từ stub này làm dữ liệu đánh giá hay huấn luyện.
#include <math.h>
#include "sim_iface.h"

static uint8_t g_scn = 0, g_sea = 1;
static double g_t = 0.0;

void sim_init(uint32_t seed) { (void)seed; g_t = 0; }
void sim_set_scenario(uint8_t scn, uint8_t sea) { g_scn = scn > 5 ? 0 : scn; g_sea = sea > 5 ? 5 : sea; g_t = 0; }
void sim_set_sea_state(uint8_t sea) { g_sea = sea > 5 ? 5 : sea; }
uint8_t sim_scenario() { return g_scn; }
uint8_t sim_sea_state() { return g_sea; }
void sim_restart() { g_t = 0; }
bool sim_is_stub() { return true; }

// roll [deg] và đạo hàm [deg/s] tại thời điểm t
static void roll_at(double t, double *r, double *rate) {
  const double w1 = 2 * M_PI / 18.0, w2 = 2 * M_PI / 11.0;
  double a = 1.2 * (1 + g_sea);                       // biên độ nền theo sea state: SS0 1.2 deg ... SS5 7.2 deg
  double base = a * sin(w1 * t) + 0.5 * a * sin(w2 * t + 1.0);
  double drate = a * w1 * cos(w1 * t) + 0.5 * a * w2 * cos(w2 * t + 1.0);
  double k = 1.0, off = 0.0;
  switch (g_scn) {
    case 1: if (t >= 30 && t < 100) off = 5.0; break;                         // S0b: nghiêng tạm thời
    case 2: k = 3.0; break;                                                   // S1: biên độ lớn
    case 3: off = 5.0; break;                                                 // S2: nghiêng lệch kéo dài
    case 4: { double g = 1.0 + 3.0 * fmin(t / 240.0, 1.0); k = g; break; }    // S3: biên độ tăng dần
    case 5: k = 3.0; off = 4.0; break;                                        // H1: kết hợp
    default: break;
  }
  *r = k * base + off;
  *rate = k * drate;
}

void sim_next(float dt, svmg_motion_sample_t *s) {
  g_t += dt;
  double r, rate; roll_at(g_t, &r, &rate);
  const double d2r = M_PI / 180.0, g = 9.80665;
  s->ax = 0.0f; s->ay = (float)(g * sin(r * d2r)); s->az = (float)(g * cos(r * d2r));
  s->gx = (float)(rate * d2r); s->gy = 0.0f; s->gz = 0.0f;
}
