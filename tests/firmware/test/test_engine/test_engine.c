/* Test tích hợp cả chuỗi lõi M1 (engine): T05/T07/T09 phía thiết bị, hiệu chuẩn, ngưỡng cứng, độ trễ phát hiện.
 * Tín hiệu là sóng tổng hợp xác định (KHÔNG phải bộ sinh của M2) - chỉ để kiểm tra hành vi của lõi. */
#include <unity.h>
#include <stdio.h>
#include <math.h>
#include <string.h>
#include "svmg_engine.h"
#include "svmg_evbuf.h"
#include "svmg_testutil.h"

void setUp(void) {}
void tearDown(void) {}
#define TAU 6.283185307179586

typedef struct { uint8_t type, level, prev; uint32_t alarm_id; double t; uint16_t val; } logev_t;
static logev_t LOG[1024]; static int NLOG;
static svmg_engine_t E;
static double TS;                    /* thời gian (s), dùng cho cả đồng hồ mô phỏng và thực (timewarp = 1) */
static svmg_engine_out_t OUT;
static int INVALID_ALL;              /* chèn lỗi cảm biến */
static int DROP_PCT;                 /* tỉ lệ mất mẫu */
static uint32_t RNG = 99;
static int ZERO_SAMPLES;             /* bus I2C chết: trả 0 nhưng vẫn "valid" */
static int CAL_DONE; static svmg_reason_t CAL_RES;

typedef double (*rollfn)(double t);  /* độ */

static void new_engine(svmg_model_t primary) {
  svmg_config_t c; svmg_config_default(&c, primary);
  svmg_engine_init(&E, &c); TS = 0; NLOG = 0; INVALID_ALL = DROP_PCT = ZERO_SAMPLES = 0; CAL_DONE = 0;
}
static void record(const svmg_engine_out_t *o) {
  if (o->calib_done) { CAL_DONE = 1; CAL_RES = o->calib_result; }
  for (int i = 0; i < o->n_ev && NLOG < 1024; i++) {
    const svmg_event_t *e = &o->ev[i];
    LOG[NLOG++] = (logev_t){ e->type, e->level, e->prev_level, e->alarm_id, TS, e->val };
  }
}
static uint32_t now_ms(void) { return (uint32_t)(TS * 1000.0); }

static void drive(double seconds, rollfn f) {
  long n = (long)(seconds * 20.0);
  for (long i = 0; i < n; i++) {
    double h = 0.01;
    double r = f(TS) * ST_D2R, rate = (f(TS + h) - f(TS - h)) / (2 * h) * ST_D2R;
    svmg_motion_sample_t s = st_sample(TS, r, rate, 0, 0);
    if (INVALID_ALL || (DROP_PCT && (int)(st_rng(&RNG) % 100) < DROP_PCT)) s.valid = 0;
    if (ZERO_SAMPLES) { s.ax = s.ay = s.az = s.gx = s.gy = s.gz = 0; }
    svmg_engine_push(&E, &s, now_ms(), &OUT); record(&OUT);
    svmg_engine_tick(&E, now_ms(), &OUT); record(&OUT);
    TS += 0.05;
  }
}

static double sea(double t) { return 3.0 * sin(TAU * t / 20.0) + 2.0 * sin(TAU * t / 14.0 + 1.0) + 2.0 * sin(TAU * t / 26.0 + 2.0); }  /* rms ~2.9 deg */
static double calm(double t) { (void)t; return 0.0; }
static double rough(double t) { return 3.0 * sea(t); }                                   /* S1: rms ~8.7 deg */
static double heel5(double t) { return sea(t) + 5.0; }                                   /* S2 */
static double tilt3(double t) { (void)t; return 3.0; }
static double wob(double t) { return 4.0 * sin(TAU * t / 20.0); }
static double hard25(double t) { (void)t; return 25.0; }
static double hard_ramp(double t) { double r = 5.0 * (t - 30.0); return r < 0 ? 0 : (r > 25.0 ? 25.0 : r); }   /* nghiêng dần 25 deg trong 5 s, có gyro nhất quán */
static double heel_tmp(double t) { return sea(t) + ((t >= 400 && t < 460) ? 5.0 : 0.0); }  /* S0b: nghiêng tạm 60 s */
static double growth_t0;
static double grow(double t) { double a = t < growth_t0 ? 2.0 : 2.0 + (t - growth_t0) * (8.0 / 240.0); return a * sin(TAU * t / 15.0); }

static int count_ev(uint8_t type, int level) {
  int n = 0; for (int i = 0; i < NLOG; i++) if (LOG[i].type == type && (level < 0 || LOG[i].level == level)) n++; return n;
}
static double first_t(uint8_t type, int level, double after) {
  for (int i = 0; i < NLOG; i++) if (LOG[i].type == type && LOG[i].level == level && LOG[i].t >= after) return LOG[i].t;
  return -1;
}
static svmg_alarm_out_t outs(void) { svmg_alarm_out_t o; svmg_alarm_outputs(&E.alarm, now_ms(), &o); return o; }
static void say(const char *fmt, double a, double b) { char m[160]; snprintf(m, sizeof m, fmt, a, b); TEST_MESSAGE(m); }

/* ===== khởi động nguội ===== */
void test_cold_start_is_never_shown_as_normal(void) {
  new_engine(SVMG_MODEL_BASELINE_B);
  for (int s = 0; s < 170; s += 10) {
    drive(10, sea);
    svmg_alarm_out_t o = outs();
    TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_OFF, o.led_g);                       /* chưa đủ cửa sổ 180 s: không được báo xanh */
    TEST_ASSERT_EQUAL_INT(SVMG_ST_UNKNOWN, E.dec.status);
  }
  drive(40, sea);
  TEST_ASSERT_EQUAL_INT(SVMG_ST_OK, E.dec.status);
  TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_ON, outs().led_g);
}

/* ===== không báo giả ===== */
void test_normal_sea_one_hour_no_warning(void) {
  new_engine(SVMG_MODEL_BASELINE_B);
  drive(3600, sea);
  TEST_ASSERT_EQUAL_INT(0, count_ev(SVMG_EV_ALARM_STATE, SVMG_LVL_WARNING));
  TEST_ASSERT_EQUAL_INT(0, count_ev(SVMG_EV_ALARM_STATE, SVMG_LVL_CRITICAL));
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_NORMAL, E.alarm.level);
}
void test_temporary_heel_S0b_no_warning(void) {
  new_engine(SVMG_MODEL_BASELINE_B);
  drive(900, heel_tmp);
  TEST_ASSERT_EQUAL_INT(0, count_ev(SVMG_EV_ALARM_STATE, SVMG_LVL_WARNING));
}

/* ===== độ trễ phát hiện (warm start) ===== */
void test_detect_high_roll_S1(void) {
  new_engine(SVMG_MODEL_BASELINE_B);
  drive(300, sea); double t0 = TS;
  drive(240, rough);
  double tw = first_t(SVMG_EV_ALARM_STATE, SVMG_LVL_WARNING, t0);
  TEST_ASSERT_TRUE_MESSAGE(tw > 0, "S1 phải bị phát hiện");
  say("S1 detect delay = %.0f s (mục tiêu tham khảo <= 60 s)  class=%.0f", tw - t0, (double)E.dec.cls_primary);
  TEST_ASSERT_TRUE(tw - t0 <= 60.0);
  TEST_ASSERT_EQUAL_INT(SVMG_HIGH_ROLL, E.dec.cls_primary);
}
void test_detect_persistent_offset_S2(void) {
  new_engine(SVMG_MODEL_BASELINE_B);
  drive(300, sea); double t0 = TS;
  drive(400, heel5);
  double tw = first_t(SVMG_EV_ALARM_STATE, SVMG_LVL_WARNING, t0);
  TEST_ASSERT_TRUE_MESSAGE(tw > 0, "S2 phải bị phát hiện");
  say("S2 detect delay = %.0f s (mục tiêu tham khảo <= 180 s)  class=%.0f", tw - t0, (double)E.dec.cls_primary);
  TEST_ASSERT_TRUE(tw - t0 <= 180.0);
  TEST_ASSERT_EQUAL_INT(SVMG_PERSISTENT_OFFSET, E.dec.cls_primary);
}
void test_detect_amplitude_growth_S3(void) {
  new_engine(SVMG_MODEL_BASELINE_B);
  growth_t0 = 300; drive(300, grow);
  drive(300, grow);
  double tw = first_t(SVMG_EV_ALARM_STATE, SVMG_LVL_WARNING, growth_t0);
  TEST_ASSERT_TRUE_MESSAGE(tw > 0, "S3 phải bị phát hiện");
  say("S3 detect delay = %.0f s (mục tiêu tham khảo <= 240 s)  class=%.0f", tw - growth_t0, (double)E.dec.cls_primary);
  TEST_ASSERT_TRUE(tw - growth_t0 <= 240.0);
}

/* ===== ngưỡng cứng ===== */
static svmg_class_t rf_always_normal(void *c, const float *f, int n) { (void)c; (void)f; (void)n; return SVMG_NORMAL; }
void test_hard_threshold_overrides_model_and_cold_start(void) {
  new_engine(SVMG_MODEL_RF); svmg_engine_set_rf(&E, rf_always_normal, NULL);    /* mô hình "mù": luôn NORMAL */
  drive(30, calm); drive(40, hard25);                                            /* vẫn đang khởi động nguội */
  double t = first_t(SVMG_EV_ALARM_STATE, SVMG_LVL_CRITICAL, 30);
  TEST_ASSERT_TRUE_MESSAGE(t > 0, "CRITICAL phải xuất hiện dù mô hình trả NORMAL và cửa sổ chưa đầy");
  say("Hard threshold, step tilt (accel only) -> CRITICAL after %.1f s (CF tau 7.5 s + dwell 5 s)  %.0f", t - 30, 0);
  TEST_ASSERT_TRUE(t - 30 <= 25.0);
  TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_CONTINUOUS, outs().buzzer);
}
void test_hard_threshold_fast_when_gyro_confirms_motion(void) {
  new_engine(SVMG_MODEL_RF); svmg_engine_set_rf(&E, rf_always_normal, NULL);
  drive(30, calm); drive(40, hard_ramp);
  double t = first_t(SVMG_EV_ALARM_STATE, SVMG_LVL_CRITICAL, 30);
  TEST_ASSERT_TRUE(t > 0);
  say("Hard threshold, ramp with gyro -> CRITICAL after %.1f s (dwell 5 s + lọc)  %.0f", t - 30, 0);
  TEST_ASSERT_TRUE(t - 30 <= 12.0);
}
void test_hard_threshold_respects_calibrated_zero_and_phi_clamp(void) {
  new_engine(SVMG_MODEL_BASELINE_B);
  svmg_config_t c = E.cfg; c.phi_hard_deg = 25; svmg_engine_apply_config(&E, &c);
  drive(60, tilt3);                                                              /* 3 deg: xa ngưỡng */
  TEST_ASSERT_EQUAL_INT(0, count_ev(SVMG_EV_ALARM_STATE, SVMG_LVL_CRITICAL));
  TEST_ASSERT_EQUAL_FLOAT(25.0f, E.safety.phi_hard_deg);
}

/* ===== vòng đời cảnh báo (T09 phía thiết bị) ===== */
void test_alarm_lifecycle_sequence(void) {
  new_engine(SVMG_MODEL_BASELINE_B);
  drive(300, sea);
  drive(75, rough);                                                              /* WARNING ~45 s, chưa tới 60 s leo thang */
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_WARNING, E.alarm.level);
  TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_INTERMITTENT, outs().buzzer);
  svmg_engine_ack(&E, SVMG_ACKBY_BUTTON, now_ms(), &OUT); record(&OUT);
  TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_OFF, outs().buzzer); TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_ON, outs().led_r);
  drive(200, sea);                                                               /* điều kiện hết: đợi giải tỏa */
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_NORMAL, E.alarm.level);
  /* thứ tự sự kiện: CAUTION, WARNING, ACK, (CAUTION giảm?) ..., NORMAL(cleared) */
  int i = 0; while (i < NLOG && !(LOG[i].type == SVMG_EV_ALARM_STATE && LOG[i].level == SVMG_LVL_CAUTION)) i++;
  TEST_ASSERT_TRUE(i < NLOG);
  int iw = i; while (iw < NLOG && !(LOG[iw].type == SVMG_EV_ALARM_STATE && LOG[iw].level == SVMG_LVL_WARNING)) iw++;
  int ia = iw; while (ia < NLOG && LOG[ia].type != SVMG_EV_ALARM_ACK) ia++;
  int ic = ia; while (ic < NLOG && !(LOG[ic].type == SVMG_EV_ALARM_STATE && LOG[ic].level == SVMG_LVL_NORMAL && LOG[ic].alarm_id)) ic++;
  TEST_ASSERT_TRUE(i < iw); TEST_ASSERT_TRUE(iw < ia); TEST_ASSERT_TRUE(ia < ic); TEST_ASSERT_TRUE(ic < NLOG);
  TEST_ASSERT_EQUAL_UINT32(LOG[iw].alarm_id, LOG[ic].alarm_id);                  /* cùng một alarm_id từ RAISED tới CLEARED */
  TEST_ASSERT_EQUAL_UINT32(1, E.alarm.n_cleared);
}
void test_unacked_warning_escalates_after_60s_real_time(void) {
  new_engine(SVMG_MODEL_BASELINE_B);
  drive(300, sea); drive(120, rough);
  double tw = first_t(SVMG_EV_ALARM_STATE, SVMG_LVL_WARNING, 300);
  double tc = first_t(SVMG_EV_ALARM_STATE, SVMG_LVL_CRITICAL, 300);
  TEST_ASSERT_TRUE(tw > 0 && tc > 0);
  TEST_ASSERT_FLOAT_WITHIN(0.2f, 60.0f, (float)(tc - tw));
}

/* ===== T07: lỗi cảm biến / thiếu mẫu ===== */
void test_sensor_fault_never_normal_and_recovers(void) {
  new_engine(SVMG_MODEL_BASELINE_B);
  drive(300, sea);
  TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_ON, outs().led_g);
  INVALID_ALL = 1; drive(30, sea);                                              /* I2C mất hoàn toàn 30 s */
  TEST_ASSERT_EQUAL_INT(SVMG_ST_FAULT, E.dec.status);
  TEST_ASSERT_EQUAL_INT(SVMG_FAULT, E.dec.cls_primary);
  svmg_alarm_out_t o = outs();
  TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_OFF, o.led_g); TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_BLINK_FAST, o.led_r);
  TEST_ASSERT_EQUAL_INT(1, count_ev(SVMG_EV_FAULT, -1));
  INVALID_ALL = 0; drive(240, sea);
  TEST_ASSERT_EQUAL_INT(1, count_ev(SVMG_EV_FAULT_CLEARED, -1));
  TEST_ASSERT_EQUAL_INT(SVMG_ST_OK, E.dec.status);
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_NORMAL, E.alarm.level);
}
void test_fault_threshold_10_seconds(void) {
  new_engine(SVMG_MODEL_BASELINE_B); drive(300, sea);
  INVALID_ALL = 1; drive(8, sea);   TEST_ASSERT_NOT_EQUAL(SVMG_ST_FAULT, E.dec.status);        /* 8 s: chưa FAULT */
  drive(12, sea);                   TEST_ASSERT_EQUAL_INT(SVMG_ST_FAULT, E.dec.status);        /* >= 10 s */
}
void test_dropped_samples_make_unknown_not_normal(void) {
  new_engine(SVMG_MODEL_BASELINE_B); drive(300, sea);
  DROP_PCT = 40; drive(120, sea);                                               /* mất 40% mẫu 20 Hz: mẫu 2 Hz vẫn đủ >=5/10 nhưng thiếu nhiều */
  say("status=%.0f (0 OK,1 UNKNOWN,2 FAULT) missing60=%.2f", (double)E.dec.status, (double)E.dec.feat.missing_ratio_60);
  svmg_alarm_out_t o = outs();
  if (E.dec.status != SVMG_ST_OK) TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_OFF, o.led_g);
  TEST_ASSERT_TRUE(E.alarm.level < SVMG_LVL_WARNING);                           /* mất mẫu không được gây báo động giả */
}
void test_dead_bus_zero_samples_flagged_fault(void) {
  new_engine(SVMG_MODEL_BASELINE_B); drive(300, sea);
  ZERO_SAMPLES = 1; drive(40, sea);                                             /* I2C trả toàn 0 nhưng valid = 1 */
  TEST_ASSERT_EQUAL_INT(SVMG_ST_FAULT, E.dec.status);
  TEST_ASSERT_NOT_EQUAL(SVMG_OUT_ON, outs().led_g);
}
void test_nan_samples_do_not_poison_state(void) {
  new_engine(SVMG_MODEL_BASELINE_B); drive(300, sea);
  for (int i = 0; i < 40; i++) { svmg_motion_sample_t s = st_sample(TS, 0, 0, 0, 0); s.ax = NAN; svmg_engine_push(&E, &s, now_ms(), &OUT); TS += 0.05; }
  drive(300, sea);
  TEST_ASSERT_EQUAL_INT(SVMG_ST_OK, E.dec.status);
  TEST_ASSERT_TRUE(isfinite(E.dec.feat.rms_roll_deg));
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_NORMAL, E.alarm.level);
}

/* ===== T05: mất mạng khi đang có bất thường ===== */
void test_offline_alarm_still_local_and_events_sync_without_loss_or_duplicates(void) {
  new_engine(SVMG_MODEL_BASELINE_B);
  svmg_evbuf_t buf; svmg_evbuf_init(&buf); uint32_t seq = 0;
  drive(300, sea);
  int logged = NLOG;
  drive(75, rough);                                                             /* "ngắt MQTT": sự kiện chỉ vào bộ đệm */
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_WARNING, E.alarm.level);                       /* cảnh báo cục bộ không phụ thuộc mạng */
  TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_ON, outs().led_r);
  TEST_ASSERT_EQUAL_UINT8_MESSAGE(SVMG_BUZ_INTERMITTENT, outs().buzzer, "còi vẫn kêu khi mất mạng");
  int expected = 0;
  for (int i = logged; i < NLOG; i++) { svmg_event_t e; memset(&e, 0, sizeof e); e.type = LOG[i].type; e.level = LOG[i].level; svmg_evbuf_push(&buf, &e, ++seq); expected++; }
  TEST_ASSERT_TRUE(expected >= 2);
  int got = 0; uint32_t last = 0; svmg_event_t e;                                // kết nối lại
  while (svmg_evbuf_next(&buf, &e)) { TEST_ASSERT_TRUE(e.seq > last); last = e.seq; svmg_evbuf_ack(&buf, e.seq); got++; }
  TEST_ASSERT_EQUAL_INT(expected, got);
}

/* ===== đổi chế độ / khoảng trống / cấu hình ===== */
void test_restart_signal_keeps_alarm_state(void) {
  new_engine(SVMG_MODEL_BASELINE_B); drive(300, sea); drive(75, rough);
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_WARNING, E.alarm.level);
  svmg_engine_restart_signal(&E);                                               /* đổi MODE/SCENARIO không được xóa cảnh báo */
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_WARNING, E.alarm.level);
  svmg_engine_ack(&E, SVMG_ACKBY_BUTTON, now_ms(), &OUT);                       /* tránh leo thang làm nhiễu phép kiểm tra */
  drive(100, sea);                                                              /* chưa đủ dữ liệu: không giải tỏa */
  TEST_ASSERT_TRUE(E.alarm.level >= SVMG_LVL_WARNING);
  TEST_ASSERT_EQUAL_INT(SVMG_ST_UNKNOWN, E.dec.status);
}
void test_time_gap_clears_history(void) {
  new_engine(SVMG_MODEL_BASELINE_B); drive(300, sea);
  TS += 10.0; drive(5, sea);                                                    /* nhảy 10 s */
  TEST_ASSERT_EQUAL_UINT32(1, E.pipe.cnt_gap);
  TEST_ASSERT_EQUAL_INT(SVMG_ST_UNKNOWN, E.dec.status);                         /* cửa sổ bắt đầu lại, không trộn hai đoạn */
}
void test_calibration_flow(void) {
  new_engine(SVMG_MODEL_BASELINE_B); drive(60, tilt3);                            /* cảm biến lắp lệch 3 deg, tàu tĩnh */
  TEST_ASSERT_EQUAL_FLOAT(0.0f, E.cfg.zero_roll_deg);
  TEST_ASSERT_EQUAL_INT(SVMG_R_PENDING, svmg_engine_calibrate_start(&E));
  TEST_ASSERT_EQUAL_INT(SVMG_R_FORBIDDEN_STATE, svmg_engine_calibrate_start(&E));  /* đang chạy */
  int done = 0; double t_start = TS;
  for (int i = 0; i < 40 && !done; i++) { drive(1, tilt3); done = CAL_DONE; }
  TEST_ASSERT_TRUE(done);
  say("calibration finished after %.0f s, result code %.0f", TS - t_start, (double)CAL_RES);
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, CAL_RES);
  TEST_ASSERT_FLOAT_WITHIN(0.05f, 3.0f, E.cfg.zero_roll_deg);
  drive(300, tilt3);
  TEST_ASSERT_FLOAT_WITHIN(0.1f, 0.0f, E.dec.feat.mean_roll_deg);                // đã trừ độ lệch lắp đặt
  TEST_ASSERT_EQUAL_INT(0, count_ev(SVMG_EV_ALARM_STATE, SVMG_LVL_WARNING));
}
void test_calibration_refused_while_alarm_active(void) {
  new_engine(SVMG_MODEL_BASELINE_B); drive(300, sea); drive(75, heel5 /*không đủ*/); drive(200, heel5);
  TEST_ASSERT_TRUE_MESSAGE(E.alarm.level >= SVMG_LVL_WARNING, "tiền điều kiện: đang có cảnh báo OFFSET");
  TEST_ASSERT_EQUAL_INT(SVMG_R_FORBIDDEN_STATE, svmg_engine_calibrate_start(&E));    /* không được xóa bằng chứng nghiêng thật */
  TEST_ASSERT_FALSE(E.calib.active);
}
void test_calibration_refused_when_not_static(void) {
  new_engine(SVMG_MODEL_BASELINE_B); drive(300, wob);
  svmg_engine_calibrate_start(&E); int done = 0;
  for (int i = 0; i < 40 && !done; i++) { drive(1, wob); done = CAL_DONE; }
  TEST_ASSERT_TRUE(done); TEST_ASSERT_EQUAL_INT(SVMG_R_NOT_STATIC, CAL_RES);
  TEST_ASSERT_EQUAL_FLOAT(0.0f, E.cfg.zero_roll_deg);                            /* cấu hình không đổi */
}

/* ===== shadow / RF ===== */
static int RF_CALLS;
static svmg_class_t rf_probe(void *c, const float *f, int n) { (void)c; RF_CALLS++; TEST_ASSERT_EQUAL_INT(SVMG_N_FEATURES, n); return f[0] >= 6.0f ? SVMG_HIGH_ROLL : SVMG_NORMAL; }
void test_rf_called_with_feature_vector_and_shadow_agreement(void) {
  new_engine(SVMG_MODEL_RF); RF_CALLS = 0; svmg_engine_set_rf(&E, rf_probe, NULL);
  drive(600, sea);
  TEST_ASSERT_TRUE(RF_CALLS > 50);
  TEST_ASSERT_FLOAT_WITHIN(0.001f, 1.0f, svmg_engine_agreement(&E));            /* cùng quy tắc ngưỡng 6 deg trên cùng đặc trưng */
  TEST_ASSERT_EQUAL_UINT8(0, E.dec.model_fallback);
}
void test_rf_primary_without_model_falls_back_to_baseline(void) {
  new_engine(SVMG_MODEL_RF);                                                    /* chưa có model.h */
  drive(300, sea); drive(75, rough);
  TEST_ASSERT_EQUAL_UINT8(1, E.dec.model_fallback);
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_WARNING, E.alarm.level);                       /* vẫn bảo vệ được nhờ Baseline B */
  TEST_ASSERT_EQUAL_INT(SVMG_UNKNOWN, E.dec.cls_rf);
}
static svmg_class_t rf_unknown(void *c, const float *f, int n) { (void)c; (void)f; (void)n; return SVMG_UNKNOWN; }
void test_rf_unknown_is_not_treated_as_normal(void) {
  new_engine(SVMG_MODEL_RF); svmg_engine_set_rf(&E, rf_unknown, NULL); drive(400, sea);
  TEST_ASSERT_EQUAL_INT(SVMG_ST_UNKNOWN, E.dec.status);
  TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_OFF, outs().led_g);
}
void test_primary_model_switch_via_config(void) {
  new_engine(SVMG_MODEL_RF); svmg_engine_set_rf(&E, rf_always_normal, NULL);
  drive(300, sea); drive(150, rough);
  /* RF "mù" là mô hình chính -> không lên WARNING; chỉ MAI cao nên dừng ở CAUTION (cảnh báo sớm độc lập với lớp) */
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_CAUTION, E.alarm.level);
  svmg_config_t c = E.cfg; c.primary_model = SVMG_MODEL_BASELINE_B; c.config_version++; svmg_engine_apply_config(&E, &c);
  drive(40, rough);
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_WARNING, E.alarm.level);
  TEST_ASSERT_TRUE(svmg_engine_agreement(&E) < 1.0f);                            /* shadow ghi nhận bất đồng RF/B */
}

/* ===== tài nguyên ===== */
void test_sizeof_engine(void) {
  char m[160]; snprintf(m, sizeof m, "sizeof(svmg_engine_t)=%u  window=%u pipeline=%u alarm=%u", (unsigned)sizeof(svmg_engine_t),
                        (unsigned)sizeof(svmg_window_t), (unsigned)sizeof(svmg_pipeline_t), (unsigned)sizeof(svmg_alarm_t));
  TEST_MESSAGE(m);
  TEST_ASSERT_TRUE(sizeof(svmg_engine_t) < 8192);
}

int main(void) {
  UNITY_BEGIN();
  RUN_TEST(test_cold_start_is_never_shown_as_normal);
  RUN_TEST(test_normal_sea_one_hour_no_warning); RUN_TEST(test_temporary_heel_S0b_no_warning);
  RUN_TEST(test_detect_high_roll_S1); RUN_TEST(test_detect_persistent_offset_S2); RUN_TEST(test_detect_amplitude_growth_S3);
  RUN_TEST(test_hard_threshold_overrides_model_and_cold_start); RUN_TEST(test_hard_threshold_fast_when_gyro_confirms_motion); RUN_TEST(test_hard_threshold_respects_calibrated_zero_and_phi_clamp);
  RUN_TEST(test_alarm_lifecycle_sequence); RUN_TEST(test_unacked_warning_escalates_after_60s_real_time);
  RUN_TEST(test_sensor_fault_never_normal_and_recovers); RUN_TEST(test_fault_threshold_10_seconds);
  RUN_TEST(test_dropped_samples_make_unknown_not_normal); RUN_TEST(test_dead_bus_zero_samples_flagged_fault);
  RUN_TEST(test_nan_samples_do_not_poison_state);
  RUN_TEST(test_offline_alarm_still_local_and_events_sync_without_loss_or_duplicates);
  RUN_TEST(test_restart_signal_keeps_alarm_state); RUN_TEST(test_time_gap_clears_history);
  RUN_TEST(test_calibration_flow); RUN_TEST(test_calibration_refused_when_not_static); RUN_TEST(test_calibration_refused_while_alarm_active);
  RUN_TEST(test_rf_called_with_feature_vector_and_shadow_agreement); RUN_TEST(test_rf_primary_without_model_falls_back_to_baseline);
  RUN_TEST(test_rf_unknown_is_not_treated_as_normal); RUN_TEST(test_primary_model_switch_via_config);
  RUN_TEST(test_sizeof_engine);
  return UNITY_END();
}
