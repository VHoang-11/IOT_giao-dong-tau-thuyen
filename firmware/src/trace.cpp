#include "trace.h"
#include <math.h>

static int16_t R[TRACE_CAP], P[TRACE_CAP];
static uint32_t total = 0;

static int16_t cdeg(float v) {
  if (!isfinite(v)) return 0;
  float c = v * 100.0f;
  if (c > 32767.0f) c = 32767.0f;
  if (c < -32768.0f) c = -32768.0f;
  return (int16_t)lroundf(c);
}

void trace_push(float roll, float pitch) { R[total % TRACE_CAP] = cdeg(roll); P[total % TRACE_CAP] = cdeg(pitch); total++; }
void trace_clear() { total = 0; }

int trace_copy(uint16_t window_s, int16_t *r, int16_t *p, int cap) {
  int want = (int)window_s * 2;
  if (want > TRACE_CAP) want = TRACE_CAP;
  if (want > (int)total) want = (int)total;
  if (want > cap) want = cap;
  for (int i = 0; i < want; i++) {
    uint32_t idx = (total - (uint32_t)want + (uint32_t)i) % TRACE_CAP;
    r[i] = R[idx]; p[i] = P[idx];
  }
  return want;
}
