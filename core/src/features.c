#include "svmg_features.h"
#include <math.h>
#include <string.h>
#define NAME(name) #name,
const char *const SVMG_FEATURE_NAMES[SVMG_N_FEATURES] = {
    SVMG_FEATURE_FIELDS(NAME)};
#undef NAME
void svmg_window_clear(svmg_window_t *w) { memset(w, 0, sizeof *w); }
int svmg_window_push(svmg_window_t *w, float r, float p, uint8_t nr,
                     uint8_t valid) {
  uint32_t i = w->total % SVMG_WIN_LONG;
  w->valid[i] = valid && nr == SVMG_RAW_PER_SAMPLE;
  w->roll_deg[i] = w->valid[i] && isfinite(r) ? r : NAN;
  w->pitch_deg[i] = w->valid[i] && isfinite(p) ? p : NAN;
  w->nraw[i] = nr > SVMG_RAW_PER_SAMPLE ? SVMG_RAW_PER_SAMPLE : nr;
  if (!valid || !isfinite(r) || !isfinite(p))
    w->nraw[i] = 0;
  w->total++;
  if (isfinite(w->roll_deg[i]) && isfinite(w->pitch_deg[i]))
    w->consec_invalid = 0;
  else if (w->consec_invalid < UINT16_MAX)
    w->consec_invalid++;
  if (++w->since_update == SVMG_UPDATE_SAMPLES) {
    w->since_update = 0;
    return 1;
  }
  return 0;
}
void svmg_window_shift(svmg_window_t *w, float dr, float dp) {
  for (int i = 0; i < SVMG_WIN_LONG; i++) {
    if (isfinite(w->roll_deg[i]))
      w->roll_deg[i] += dr;
    if (isfinite(w->pitch_deg[i]))
      w->pitch_deg[i] += dp;
  }
}
static uint32_t slot(const svmg_window_t *w, uint32_t age) {
  return (w->total - 1u - age) % SVMG_WIN_LONG;
}
/* In-place heapsort: bounded O(N log N), no allocator or recursive sort stack.
 */
static void sift(float *a, int root, int n) {
  for (;;) {
    int child = root * 2 + 1;
    if (child >= n)
      return;
    if (child + 1 < n && a[child] < a[child + 1])
      child++;
    if (a[root] >= a[child])
      return;
    float t = a[root];
    a[root] = a[child];
    a[child] = t;
    root = child;
  }
}
static void sort(float *a, int n) {
  for (int i = n / 2; i > 0; i--)
    sift(a, i - 1, n);
  for (int end = n - 1; end > 0; end--) {
    float t = a[0];
    a[0] = a[end];
    a[end] = t;
    sift(a, 0, end);
  }
}
static float quantile(const float *z, int n, double p) {
  if (!n)
    return NAN;
  double h = (n - 1) * p;
  int j = (int)h;
  return (float)((double)z[j] +
                 (h - j) * ((double)z[j + (j + 1 < n)] - (double)z[j]));
}
typedef struct {
  int n, pos, neg;
  double mean, rms, sd, mean_abs;
  float min, max, median, iqr, p95;
} stats_t;
static stats_t stats(svmg_window_t *w, int pitch, int oldest_age, int count) {
  stats_t s = {0};
  double sum = 0, sq = 0, abs_sum = 0, var = 0;
  s.min = INFINITY;
  s.max = -INFINITY;
  for (int k = oldest_age - count + 1; k <= oldest_age; k++) {
    uint32_t i = slot(w, (uint32_t)k);
    float v = pitch ? w->pitch_deg[i] : w->roll_deg[i];
    if (!isfinite(v))
      continue;
    w->scratch[s.n++] = v;
    sum += (double)v;
    sq += (double)v * (double)v;
    abs_sum += fabs((double)v);
    if (v < s.min)
      s.min = v;
    if (v > s.max)
      s.max = v;
    s.pos += v > 0;
    s.neg += v < 0;
  }
  if (!s.n) {
    s.mean = s.rms = s.sd = s.mean_abs = NAN;
    s.median = s.iqr = s.p95 = NAN;
    return s;
  }
  s.mean = sum / s.n;
  s.rms = sqrt(sq / s.n);
  s.mean_abs = abs_sum / s.n;
  for (int j = 0; j < s.n; j++) {
    double d = (double)w->scratch[j] - s.mean;
    var += d * d;
  }
  s.sd = sqrt(var / s.n);
  sort(w->scratch, s.n);
  s.median = quantile(w->scratch, s.n, .5);
  s.iqr = quantile(w->scratch, s.n, .75) - quantile(w->scratch, s.n, .25);
  for (int j = 0; j < s.n; j++)
    w->scratch[j] = fabsf(w->scratch[j]);
  sort(w->scratch, s.n);
  s.p95 = quantile(w->scratch, s.n, .95);
  return s;
}
static void assign(svmg_features_t *f, int id, float *dst, double value,
                   int valid) {
  *dst = valid && isfinite(value) ? (float)value : NAN;
  if (isfinite(*dst))
    f->valid_mask |= 1u << id;
}
#define SET(name, value, ok) assign(f, SVMG_F_##name, &f->name, (value), (ok))
void svmg_features_compute(svmg_window_t *w, svmg_features_t *f) {
  memset(f, 0, sizeof *f);
#define INIT(name) f->name = NAN;
  SVMG_FEATURE_FIELDS(INIT)
#undef INIT
  f->sensor_ok = 1;
  f->consec_invalid = w->consec_invalid;
  f->ready_short = w->total >= SVMG_WIN_SHORT;
  f->ready_long = w->total >= SVMG_WIN_LONG;
  int n60 = w->total < SVMG_WIN_SHORT ? (int)w->total : SVMG_WIN_SHORT;
  int n180 = w->total < SVMG_WIN_LONG ? (int)w->total : SVMG_WIN_LONG;
  if (!n180)
    return;
  stats_t r = stats(w, 0, n60 - 1, n60), p = stats(w, 1, n60 - 1, n60),
          l = stats(w, 0, n180 - 1, n180);
  f->n_valid_60 = (uint16_t)(r.n < p.n ? r.n : p.n);
  int both = 0;
  unsigned nr = 0;
  for (int k = 0; k < n180; k++) {
    uint32_t i = slot(w, (uint32_t)k);
    nr += w->nraw[i];
    both += isfinite(w->roll_deg[i]) && isfinite(w->pitch_deg[i]);
  }
  f->n_valid_180 = (uint16_t)both;
  f->data_quality_pct =
      100.0f * (float)nr / (float)(n180 * SVMG_RAW_PER_SAMPLE);
  int rok = f->ready_short && r.n >= 570, pok = f->ready_short && p.n >= 570,
      lok = f->ready_long && l.n >= 1710;
  SET(roll_rms_60, r.rms, rok);
  SET(roll_std_60, r.sd, rok);
  SET(roll_mean_60, r.mean, rok);
  SET(roll_peak_to_peak_60, (double)r.max - (double)r.min, rok);
  SET(roll_abs_p95_60, r.p95, rok);
  SET(roll_abs_max_60, fmax(fabs(r.min), fabs(r.max)), rok);
  SET(roll_iqr_60, r.iqr, rok);
  double dsq = 0;
  int pairs = 0;
  for (int k = 1; k < n60; k++) {
    float a = w->roll_deg[slot(w, (uint32_t)k)],
          b = w->roll_deg[slot(w, (uint32_t)(k - 1))];
    if (isfinite(a) && isfinite(b)) {
      double d = (double)b - (double)a;
      dsq += d * d;
      pairs++;
    }
  }
  SET(roll_diff_rms_60, pairs ? sqrt(dsq / pairs) : (double)NAN,
      f->ready_short && pairs >= 570);
  SET(roll_mean_180, l.mean, lok);
  SET(roll_median_180, l.median, lok);
  SET(roll_mean_abs_180, l.mean_abs, lok);
  SET(roll_dominant_sign_ratio_180,
      l.pos + l.neg ? (double)(l.pos > l.neg ? l.pos : l.neg) / (l.pos + l.neg)
                    : (double)NAN,
      lok);
  SET(pitch_rms_60, p.rms, pok);
  SET(pitch_std_60, p.sd, pok);
  SET(pitch_peak_to_peak_60, (double)p.max - (double)p.min, pok);
  if (f->ready_long) {
    stats_t b[3];
    int bok = 1;
    for (int j = 0; j < 3; j++) {
      b[j] = stats(w, 0, SVMG_WIN_LONG - j * SVMG_SEG_SAMPLES - 1,
                   SVMG_SEG_SAMPLES);
      bok &= b[j].n >= 570;
    }
    double mean = (b[0].mean + b[1].mean + b[2].mean) / 3, var = 0;
    for (int j = 0; j < 3; j++) {
      double d = b[j].mean - mean;
      var += d * d;
    }
    SET(roll_segment_mean_std_180, sqrt(var / 3), bok);
    SET(roll_mean_shift_180, b[2].mean - b[0].mean, bok);
    SET(roll_rms_early_60, b[0].rms, bok);
    SET(roll_rms_late_60, b[2].rms, bok);
    SET(roll_rms_ratio_180,
        b[0].rms > SVMG_RMS_EPSILON_DEG ? b[2].rms / b[0].rms : (double)NAN,
        bok);
    /* OLS at centers [30,90,150] seconds, converted to degrees/minute. */
    double slope = (b[2].rms - b[0].rms) / 2;
    SET(roll_rms_slope_180, slope, bok);
    SET(roll_p95_trend_slope_180, ((double)b[2].p95 - (double)b[0].p95) / 2,
        bok);
    double rm = (b[0].rms + b[1].rms + b[2].rms) / 3, sst = 0, sse = 0;
    for (int j = 0; j < 3; j++) {
      double d = b[j].rms - rm, e = b[j].rms - (rm + slope * (j - 1));
      sst += d * d;
      sse += e * e;
    }
    SET(roll_rms_trend_r2_180,
        sst > SVMG_R2_ZERO_TOLERANCE ? fmax(0, fmin(1, 1 - sse / sst))
                                     : (double)NAN,
        bok);
  }
  f->rms_roll = f->roll_rms_60;
  f->p95_roll = f->roll_abs_p95_60;
  f->rms_pitch = f->pitch_rms_60;
  f->p95_pitch = p.p95;
  f->max_abs_roll = f->roll_abs_max_60;
  f->energy_roll = (float)(r.rms * r.rms);
  f->mean_roll = f->roll_mean_180;
  stats_t lp = stats(w, 1, n180 - 1, n180);
  f->mean_pitch = (float)lp.mean;
  f->std_roll = (float)l.sd;
  f->trend_rms_slope = f->roll_rms_slope_180;
}
#undef SET
void svmg_features_to_vector(const svmg_features_t *f,
                             float out[SVMG_N_FEATURES]) {
  int i = 0;
#define COPY(name) out[i++] = f->name;
  SVMG_FEATURE_FIELDS(COPY)
#undef COPY
}
int svmg_features_vector_valid(const svmg_features_t *f) {
  return f->valid_mask == SVMG_FEATURE_ALL_VALID;
}
void svmg_quality_default(svmg_quality_cfg_t *q) {
  q->unknown_quality_pct = 95;
  q->fault_quality_pct = 50;
  q->fault_consec_invalid = 100;
}
svmg_status_t svmg_features_status(const svmg_features_t *f,
                                   const svmg_quality_cfg_t *q,
                                   uint8_t *reason) {
  uint8_t r = 0;
  if (f->consec_invalid >= q->fault_consec_invalid)
    r |= SVMG_Q_FAULT_RUN;
  if (f->data_quality_pct < q->fault_quality_pct)
    r |= SVMG_Q_FAULT_PCT;
  if (!f->ready_long)
    r |= SVMG_Q_COLD;
  if (f->data_quality_pct < q->unknown_quality_pct ||
      (f->ready_long && f->n_valid_180 < 1710) ||
      (f->ready_short && f->n_valid_60 < 570))
    r |= SVMG_Q_LOWQUALITY;
  if (reason)
    *reason = r;
  return r & (SVMG_Q_FAULT_RUN | SVMG_Q_FAULT_PCT) ? SVMG_ST_FAULT
         : r                                       ? SVMG_ST_UNKNOWN
                                                   : SVMG_ST_OK;
}
int svmg_features_from_series(const float *r, const float *p, const uint8_t *nr,
                              int n, float out[SVMG_N_FEATURES]) {
  if (!out)
    return SVMG_ST_FAULT;
  if (!r || !p || n <= 0) {
    for (int j = 0; j < SVMG_N_FEATURES; j++)
      out[j] = NAN;
    return SVMG_ST_UNKNOWN;
  }
  svmg_window_t w;
  svmg_window_clear(&w);
  if (n > SVMG_WIN_LONG) {
    int skip = n - SVMG_WIN_LONG;
    r += skip;
    p += skip;
    if (nr)
      nr += skip;
    n = SVMG_WIN_LONG;
  }
  for (int i = 0; i < n; i++) {
    uint8_t c = nr ? nr[i] : SVMG_RAW_PER_SAMPLE;
    svmg_window_push(&w, r[i], p[i], c, c == SVMG_RAW_PER_SAMPLE);
  }
  svmg_features_t f;
  svmg_features_compute(&w, &f);
  svmg_features_to_vector(&f, out);
  svmg_quality_cfg_t q;
  svmg_quality_default(&q);
  svmg_status_t st = svmg_features_status(&f, &q, NULL);
  return st == SVMG_ST_OK && !svmg_features_vector_valid(&f) ? SVMG_ST_UNKNOWN
                                                             : st;
}
