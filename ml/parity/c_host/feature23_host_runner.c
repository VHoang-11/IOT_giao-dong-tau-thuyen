/*
 * Host-side integration runner: drives the UNMODIFIED M1 feature code
 * (core/src/features.c, core/include/svmg_features.h) with M2 golden inputs.
 *
 * It does not reimplement any of the 23 formulas. It only:
 *   1. parses a golden input CSV (roll/pitch with strtof -> float32),
 *   2. streams samples through svmg_window_push() exactly like the firmware
 *      engine does (one push per 10 Hz sample),
 *   3. calls svmg_features_compute() at the requested endpoint rows,
 *   4. cross-checks the vector against svmg_features_from_series(),
 *   5. prints the C values plus C window state (ready flags, valid_mask,
 *      finite-sample counts read from the C ring buffer) as raw CSV.
 *
 * Usage:
 *   feature23_host_runner --info
 *   feature23_host_runner <input.csv> <endpoint_rows_comma_separated> [native|gridfill]
 *
 * native   : one input row = one svmg_window_push() (C has no timestamp input).
 * gridfill : DIAGNOSTIC ONLY. When time_seconds jumps by k nominal periods,
 *            k-1 invalid placeholder samples (valid=0, nraw=0) are pushed first,
 *            mimicking a firmware tick that produced no valid sample.
 */
#include <float.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "svmg_features.h"

#ifndef __VERSION__
#define __VERSION__ "unknown"
#endif

#define MAX_ROWS 200000
#define MAX_ENDPOINTS 4096
#define NOMINAL_DT 0.1

static double g_time[MAX_ROWS];
static float g_roll[MAX_ROWS], g_pitch[MAX_ROWS];
static long g_rows;
static svmg_window_t g_win;

static void print_info(void) {
  printf("{\"c_feature_schema_version\":\"%s\",", SVMG_FEATURE_SCHEMA_VERSION);
  printf("\"c_preprocessing_version\":\"%s\",", SVMG_PREPROCESSING_VERSION);
  printf("\"n_features\":%d,\"feature_hz\":%d,\"update_s\":%d,", SVMG_N_FEATURES,
         SVMG_FEATURE_HZ, SVMG_FEATURE_UPDATE_S);
  printf("\"win_short\":%d,\"win_long\":%d,\"seg_samples\":%d,", SVMG_WIN_SHORT,
         SVMG_WIN_LONG, SVMG_SEG_SAMPLES);
  printf("\"rms_epsilon_deg\":%.17g,\"r2_zero_tolerance\":%.17g,",
         SVMG_RMS_EPSILON_DEG, SVMG_R2_ZERO_TOLERANCE);
  printf("\"compiler_version_macro\":\"%s\",", __VERSION__);
  printf("\"flt_eval_method\":%d,\"sizeof_float\":%d,\"sizeof_double\":%d,",
         (int)FLT_EVAL_METHOD, (int)sizeof(float), (int)sizeof(double));
  printf("\"feature_names\":[");
  for (int i = 0; i < SVMG_N_FEATURES; i++)
    printf("%s\"%s\"", i ? "," : "", SVMG_FEATURE_NAMES[i]);
  printf("]}\n");
}

static int load_csv(const char *path) {
  FILE *fp = fopen(path, "r");
  if (!fp) {
    fprintf(stderr, "cannot open %s\n", path);
    return 0;
  }
  char line[512];
  if (!fgets(line, sizeof line, fp) ||
      strncmp(line,
              "sample_index,time_seconds,roll_deg,pitch_deg,source_sample_index",
              64) != 0) {
    fprintf(stderr, "unexpected header in %s\n", path);
    fclose(fp);
    return 0;
  }
  g_rows = 0;
  while (fgets(line, sizeof line, fp)) {
    if (line[0] == '\n' || line[0] == '\0')
      continue;
    if (g_rows >= MAX_ROWS) {
      fprintf(stderr, "too many rows\n");
      fclose(fp);
      return 0;
    }
    char *p = line, *end;
    long idx = strtol(p, &end, 10);
    if (end == p || *end != ',' || idx != g_rows) {
      fprintf(stderr, "bad sample_index at row %ld\n", g_rows);
      fclose(fp);
      return 0;
    }
    p = end + 1;
    g_time[g_rows] = strtod(p, &end);
    if (end == p || *end != ',')
      goto bad;
    p = end + 1;
    g_roll[g_rows] = strtof(p, &end); /* float32 round-trip of golden text */
    if (end == p || *end != ',')
      goto bad;
    p = end + 1;
    g_pitch[g_rows] = strtof(p, &end);
    if (end == p || *end != ',')
      goto bad;
    g_rows++;
    continue;
  bad:
    fprintf(stderr, "parse error at row %ld\n", g_rows);
    fclose(fp);
    return 0;
  }
  fclose(fp);
  return 1;
}

/* Age -> ring slot; same index arithmetic as features.c (oldest-first ring). */
static unsigned ring_slot(const svmg_window_t *w, unsigned age) {
  return (w->total - 1u - age) % SVMG_WIN_LONG;
}

static int count_finite(const svmg_window_t *w, int pitch, int oldest_age,
                        int count) {
  int n = 0;
  for (int k = oldest_age - count + 1; k <= oldest_age; k++) {
    unsigned i = ring_slot(w, (unsigned)k);
    n += isfinite(pitch ? w->pitch_deg[i] : w->roll_deg[i]) != 0;
  }
  return n;
}

static int count_roll_pairs(const svmg_window_t *w, int n60) {
  int pairs = 0;
  for (int k = 1; k < n60; k++)
    pairs += isfinite(w->roll_deg[ring_slot(w, (unsigned)k)]) &&
             isfinite(w->roll_deg[ring_slot(w, (unsigned)(k - 1))]);
  return pairs;
}

static int same_bits(float a, float b) {
  if (isnan(a) && isnan(b))
    return 1;
  return memcmp(&a, &b, sizeof a) == 0;
}

static int cmp_long(const void *a, const void *b) {
  long x = *(const long *)a, y = *(const long *)b;
  return (x > y) - (x < y);
}

int main(int argc, char **argv) {
  if (argc == 2 && strcmp(argv[1], "--info") == 0) {
    print_info();
    return 0;
  }
  if (argc < 3 || argc > 4) {
    fprintf(stderr, "usage: %s --info | <input.csv> <e1,e2,...> [native|gridfill]\n",
            argv[0]);
    return 2;
  }
  int gridfill = argc == 4 && strcmp(argv[3], "gridfill") == 0;
  if (argc == 4 && !gridfill && strcmp(argv[3], "native") != 0) {
    fprintf(stderr, "unknown mode %s\n", argv[3]);
    return 2;
  }
  if (!load_csv(argv[1]))
    return 3;

  static long endpoints[MAX_ENDPOINTS];
  int n_ep = 0;
  for (char *tok = strtok(argv[2], ","); tok; tok = strtok(NULL, ",")) {
    if (n_ep >= MAX_ENDPOINTS)
      return 4;
    char *end;
    endpoints[n_ep] = strtol(tok, &end, 10);
    if (*end || endpoints[n_ep] < 0 || endpoints[n_ep] >= g_rows) {
      fprintf(stderr, "endpoint %s outside input rows\n", tok);
      return 4;
    }
    n_ep++;
  }
  qsort(endpoints, (size_t)n_ep, sizeof endpoints[0], cmp_long);

  printf("endpoint_index,endpoint_time_seconds,mode,stream_total,ready_short,"
         "ready_long,valid_mask,n_valid_60,n_valid_180,roll_finite_60,"
         "pitch_finite_60,roll_pairs_60,roll_finite_180,block0_finite,"
         "block1_finite,block2_finite,placeholders_pushed,from_series_status,"
         "from_series_match");
  for (int i = 0; i < SVMG_N_FEATURES; i++)
    printf(",v%02d", i);
  printf("\n");

  svmg_window_clear(&g_win);
  long placeholders = 0;
  int next = 0;
  for (long row = 0; row < g_rows && next < n_ep; row++) {
    if (gridfill && row > 0) {
      long k = lround((g_time[row] - g_time[row - 1]) / NOMINAL_DT);
      for (long j = 1; j < k; j++, placeholders++)
        svmg_window_push(&g_win, NAN, NAN, 0, 0);
    }
    svmg_window_push(&g_win, g_roll[row], g_pitch[row], SVMG_RAW_PER_SAMPLE, 1);
    while (next < n_ep && endpoints[next] == row) {
      svmg_features_t f;
      svmg_features_compute(&g_win, &f);
      float vec[SVMG_N_FEATURES];
      svmg_features_to_vector(&f, vec);
      int n60 = g_win.total < SVMG_WIN_SHORT ? (int)g_win.total : SVMG_WIN_SHORT;
      int n180 = g_win.total < SVMG_WIN_LONG ? (int)g_win.total : SVMG_WIN_LONG;
      int b[3] = {-1, -1, -1};
      if (g_win.total >= SVMG_WIN_LONG)
        for (int j = 0; j < 3; j++)
          b[j] = count_finite(&g_win, 0, SVMG_WIN_LONG - j * SVMG_SEG_SAMPLES - 1,
                              SVMG_SEG_SAMPLES);
      int fs_status = -1, fs_match = -1;
      if (!gridfill) {
        long lo = row + 1 > SVMG_WIN_LONG ? row + 1 - SVMG_WIN_LONG : 0;
        float alt[SVMG_N_FEATURES];
        fs_status = svmg_features_from_series(g_roll + lo, g_pitch + lo, NULL,
                                              (int)(row + 1 - lo), alt);
        fs_match = 1;
        for (int i = 0; i < SVMG_N_FEATURES; i++)
          fs_match &= same_bits(vec[i], alt[i]);
      }
      printf("%ld,%.17g,%s,%u,%u,%u,%lu,%u,%u,%d,%d,%d,%d,%d,%d,%d,%ld,%d,%d",
             row, g_time[row], gridfill ? "gridfill" : "native",
             (unsigned)g_win.total, (unsigned)f.ready_short,
             (unsigned)f.ready_long, (unsigned long)f.valid_mask,
             (unsigned)f.n_valid_60, (unsigned)f.n_valid_180,
             count_finite(&g_win, 0, n60 - 1, n60),
             count_finite(&g_win, 1, n60 - 1, n60), count_roll_pairs(&g_win, n60),
             count_finite(&g_win, 0, n180 - 1, n180), b[0], b[1], b[2],
             placeholders, fs_status, fs_match);
      for (int i = 0; i < SVMG_N_FEATURES; i++)
        printf(",%.9g", (double)vec[i]);
      printf("\n");
      next++;
    }
  }
  if (next != n_ep) {
    fprintf(stderr, "not all endpoints evaluated\n");
    return 5;
  }
  return 0;
}
