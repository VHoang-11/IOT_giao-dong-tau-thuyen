/* Thí nghiệm của M1 phần chạy được trên máy chủ (cùng lõi C với ESP32):
 *   T01 - MPU6050 ở SENSOR MODE: thanh ghi thô -> SI -> roll/pitch -> đặc trưng; lỗi cảm biến hiển thị
 *   T05 - Ngắt MQTT lúc có bất thường: LED/buzzer vẫn hoạt động; đồng bộ bù không mất, không trùng
 *   T07 - Lỗi cảm biến / thiếu mẫu: FAULT/UNKNOWN, không bao giờ báo "bình thường" sai
 * Phần chạy trên Wokwi (mạch thật, Serial/LCD) là thủ tục thủ công trong tests/firmware/TEST_LOG.md.
 * Mỗi ca in một dòng "T0x-y: PASS/FAIL - mô tả" (xem bằng pio test -v). */
#include <unity.h>
#include <stdio.h>
#include <math.h>
#include <string.h>
#include "svmg_engine.h"
#include "svmg_evbuf.h"
#include "svmg_testutil.h"

void setUp(void) {}
void tearDown(void) {}

static svmg_engine_t E;
static svmg_engine_out_t OUT;
static double TS;
static svmg_evbuf_t BUF;
static uint32_t SEQ;
static int N_FAULT_EV, N_CLEARED_EV;

static void say(const char *id, int ok, const char *what) { char m[200]; snprintf(m, sizeof m, "%s: %s - %s", id, ok ? "PASS" : "FAIL", what); TEST_MESSAGE(m); }
#define CHECK(id, cond, what) do { int ok_ = (cond) ? 1 : 0; say(id, ok_, what); TEST_ASSERT_TRUE_MESSAGE(ok_, what); } while (0)

static void new_engine(void) {
  svmg_config_t c; svmg_config_default(&c, SVMG_MODEL_BASELINE_B); svmg_engine_init(&E, &c);
  svmg_evbuf_init(&BUF); SEQ = 0; TS = 0; N_FAULT_EV = N_CLEARED_EV = 0;
}
static void absorb(const svmg_engine_out_t *o, int to_buffer) {
  for (int i = 0; i < o->n_ev; i++) {
    if (o->ev[i].type == SVMG_EV_FAULT) N_FAULT_EV++;
    if (o->ev[i].type == SVMG_EV_FAULT_CLEARED) N_CLEARED_EV++;
    if (to_buffer) svmg_evbuf_push(&BUF, &o->ev[i], ++SEQ);
  }
}
static uint32_t now_ms(void) { return (uint32_t)(TS * 1000.0); }

typedef enum { INJ_NONE, INJ_I2C_LOST, INJ_ZEROS, INJ_SAT, INJ_NAN, INJ_DROP30 } inj_t;
static inj_t INJ;
static uint32_t RNG = 4242;

/* Mô phỏng đường đọc thật: tạo thanh ghi thô như MPU6050 rồi qua svmg_imu_raw_to_si (đúng mã firmware dùng). */
static void step(double roll_deg, double roll_rate_dps, double pitch_deg, int buffered) {
  double r = roll_deg * ST_D2R, p = pitch_deg * ST_D2R;
  svmg_imu_raw_t raw;
  raw.ax = (int16_t)lround(-sin(p) * 16384.0);
  raw.ay = (int16_t)lround(cos(p) * sin(r) * 16384.0);
  raw.az = (int16_t)lround(cos(p) * cos(r) * 16384.0);
  raw.gx = (int16_t)lround(roll_rate_dps * 131.0); raw.gy = 0; raw.gz = 0;
  svmg_motion_sample_t s; memset(&s, 0, sizeof s);
  uint8_t fl = svmg_imu_raw_to_si(&raw, &s); (void)fl;
  s.t = (float)TS; s.source_mode = SVMG_SRC_SENSOR; s.valid = 1;
  switch (INJ) {
    case INJ_I2C_LOST: s.valid = 0; break;
    case INJ_ZEROS: s.ax = s.ay = s.az = s.gx = s.gy = s.gz = 0; break;
    case INJ_SAT: { svmg_imu_raw_t sat = { -32768, -32768, -32768, -32768, -32768, -32768 }; svmg_imu_raw_to_si(&sat, &s); s.t = (float)TS; break; }
    case INJ_NAN: s.ay = NAN; break;
    case INJ_DROP30: if ((int)(st_rng(&RNG) % 100) < 30) s.valid = 0; break;
    default: break;
  }
  svmg_engine_push(&E, &s, now_ms(), &OUT); absorb(&OUT, buffered);
  svmg_engine_tick(&E, now_ms(), &OUT); absorb(&OUT, buffered);
  TS += 0.05;
}
static void run_static(double roll, double pitch, double seconds) { for (int i = 0; i < (int)(seconds * 20); i++) step(roll, 0, pitch, 0); }
static double sea(double t) { return 3.0 * sin(6.283185307 * t / 20.0) + 2.0 * sin(6.283185307 * t / 14.0 + 1.0); }
static void run_sea(double seconds, int buffered) {
  int n = (int)(seconds * 20);
  for (int i = 0; i < n; i++) { double h = 0.01, v = (sea(TS + h) - sea(TS - h)) / (2 * h); step(sea(TS), v, 0, buffered); }
}
static svmg_alarm_out_t outs(void) { svmg_alarm_out_t o; svmg_alarm_outputs(&E.alarm, now_ms(), &o); return o; }

/* ================= T01 ================= */
void test_T01_a_static_flat_reads_zero(void) {
  new_engine(); run_static(0, 0, 40);          /* Wokwi: accelZ = 1 g, các trục khác 0 */
  CHECK("T01-a", fabsf(E.dec.roll_deg) < 0.05f && fabsf(E.dec.pitch_deg) < 0.05f, "accel (0,0,1 g) -> roll = pitch = 0");
}
void test_T01_b_roll_30(void) {
  new_engine(); run_static(30.0, 0, 60);       /* Wokwi: accelY = 0.5 g, accelZ = 0.866 g */
  CHECK("T01-b", fabsf(E.dec.roll_deg - 30.0f) < 0.2f, "accel (0, 0.5, 0.866 g) -> roll = 30.0 +- 0.2 deg");
}
void test_T01_c_pitch_30(void) {
  new_engine(); run_static(0, 30.0, 60);       /* Wokwi: accelX = -0.5 g, accelZ = 0.866 g */
  CHECK("T01-c", fabsf(E.dec.pitch_deg - 30.0f) < 0.2f && fabsf(E.dec.roll_deg) < 0.2f, "accel (-0.5, 0, 0.866 g) -> pitch = 30.0 +- 0.2 deg");
}
void test_T01_d_gyro_units(void) {
  svmg_imu_raw_t raw = { 0, 0, 16384, (int16_t)lround(10.0 * 131.0), 0, 0 };   /* Wokwi: rotationX = 10 deg/s */
  svmg_motion_sample_t s; svmg_imu_raw_to_si(&raw, &s);
  CHECK("T01-d", fabsf(s.gx - 0.174533f) < 1e-3f && fabsf(s.az - 9.80665f) < 1e-3f, "rotationX = 10 deg/s -> gx = 0.1745 rad/s; 1 g -> 9.807 m/s^2");
}
void test_T01_e_features_shown_for_oscillation(void) {
  new_engine(); run_sea(300, 0);
  CHECK("T01-e", E.dec.status == SVMG_ST_OK && E.dec.feat.rms_roll_deg > 2.0f && E.dec.feat.rms_roll_deg < 4.0f && E.alarm.level == SVMG_LVL_NORMAL,
        "dao dong +- vai do -> du lieu OK, RMS 2..4 deg, khong bao dong");
}
void test_T01_f_sensor_error_shown(void) {
  new_engine(); run_sea(200, 0); INJ = INJ_I2C_LOST; run_static(0, 0, 15);
  CHECK("T01-f", E.dec.status == SVMG_ST_FAULT, "mat ket noi I2C 15 s -> FAULT (hien thi tren Serial/LCD)");
  INJ = INJ_NONE;
}

/* ================= T05 ================= */
static double rough(double t) { return 3.0 * sea(t); }
void test_T05_offline_alarm_local_and_sync_exactly_once(void) {
  new_engine(); INJ = INJ_NONE;
  run_sea(300, 1);                                   /* bình thường, đang online */
  svmg_event_t e; while (svmg_evbuf_next(&BUF, &e)) svmg_evbuf_ack(&BUF, e.seq);   /* mọi thứ trước đó đã được xác nhận */
  uint32_t acked_before = BUF.n_acked;
  /* ---- NGẮT MQTT: bất thường S1 bắt đầu; sự kiện chỉ vào bộ đệm ---- */
  int led_red_seen = 0, buzzer_seen = 0;
  for (int sec = 0; sec < 75; sec++) {
    for (int i = 0; i < 20; i++) { double h = 0.01, v = (rough(TS + h) - rough(TS - h)) / (2 * h); step(rough(TS), v, 0, 1); }
    svmg_alarm_out_t o = outs();
    if (o.led_r == SVMG_OUT_ON) led_red_seen = 1;
    if (o.buzzer != SVMG_BUZ_OFF) buzzer_seen = 1;
  }
  CHECK("T05-a", led_red_seen && buzzer_seen && E.alarm.level >= SVMG_LVL_WARNING, "mat mang: LED do + coi van hoat dong khi co bat thuong");
  int queued = svmg_evbuf_depth(&BUF);
  CHECK("T05-b", queued >= 2 && queued <= SVMG_EVBUF_CAP, "su kien canh bao nam trong bo dem (khong mat) trong luc offline");
  /* ---- KẾT NỐI LẠI: rớt mạng thêm một lần giữa chừng khi đang gửi ---- */
  uint8_t seen[1024]; memset(seen, 0, sizeof seen); int sent = 0, dup = 0;
  for (int k = 0; k < 3 && svmg_evbuf_next(&BUF, &e); k++) { sent++; }
  svmg_evbuf_requeue_inflight(&BUF);                 /* rớt mạng khi chưa PUBACK: gửi bù (backend loại trùng theo seq) */
  uint32_t last = 0; int ordered = 1;
  while (svmg_evbuf_next(&BUF, &e)) { if (seen[e.seq]++) dup++; if (e.seq <= last) ordered = 0; last = e.seq; svmg_evbuf_ack(&BUF, e.seq); }
  int delivered = 0; for (int i = 0; i < 1024; i++) delivered += seen[i] ? 1 : 0;
  CHECK("T05-c", delivered == queued && dup == 0 && ordered, "dong bo sau khi ket noi lai: du so su kien, moi seq 1 lan, dung thu tu");
  CHECK("T05-d", svmg_evbuf_depth(&BUF) == 0 && BUF.n_acked >= acked_before + (uint32_t)queued, "bo dem trong sau khi xac nhan het");
}

/* ================= T07 ================= */
static void settle_ok(void) { new_engine(); INJ = INJ_NONE; run_sea(300, 0); TEST_ASSERT_EQUAL_INT(SVMG_ST_OK, E.dec.status); }
static void never_green_in_fault(const char *id, const char *what, inj_t inj, int expect_status, double secs) {
  settle_ok(); INJ = inj;
  int green_while_bad = 0;
  for (int s = 0; s < (int)secs; s++) { run_sea(1, 0); if (E.dec.status != SVMG_ST_OK && outs().led_g == SVMG_OUT_ON) green_while_bad = 1; }
  int ok = (E.dec.status == (svmg_status_t)expect_status) && !green_while_bad && E.alarm.level < SVMG_LVL_WARNING;
  say(id, ok, what); TEST_ASSERT_TRUE_MESSAGE(ok, what);
  INJ = INJ_NONE;
}
void test_T07_a_i2c_lost(void)   { never_green_in_fault("T07-a", "I2C mat hoan toan -> FAULT, LED khong xanh, khong bao dong gia", INJ_I2C_LOST, SVMG_ST_FAULT, 30); }
void test_T07_b_dead_bus_zeros(void) { never_green_in_fault("T07-b", "bus tra toan 0 (valid=1) -> FAULT", INJ_ZEROS, SVMG_ST_FAULT, 40); }
void test_T07_c_saturated(void)  { never_green_in_fault("T07-c", "cam bien bao hoa +-32768 -> FAULT", INJ_SAT, SVMG_ST_FAULT, 40); }
void test_T07_d_nan(void)        { never_green_in_fault("T07-d", "NaN tren gia toc -> FAULT, khong nhiem trang thai", INJ_NAN, SVMG_ST_FAULT, 40); }
void test_T07_e_missing_samples_unknown_or_ok_never_alarm(void) {
  settle_ok(); INJ = INJ_DROP30; int bad_alarm = 0, green_bad = 0;
  for (int s = 0; s < 240; s++) { run_sea(1, 0); if (E.alarm.level >= SVMG_LVL_WARNING) bad_alarm = 1; if (E.dec.status != SVMG_ST_OK && outs().led_g == SVMG_OUT_ON) green_bad = 1; }
  int ok = !bad_alarm && !green_bad;
  say("T07-e", ok, "mat 30% mau: khong bao dong gia, trang thai khong-OK khong bao xanh"); TEST_ASSERT_TRUE(ok);
  INJ = INJ_NONE;
}
void test_T07_f_events_and_recovery(void) {
  settle_ok(); INJ = INJ_I2C_LOST; run_sea(30, 1);
  INJ = INJ_NONE; run_sea(240, 1);
  int ok = (N_FAULT_EV == 1) && (N_CLEARED_EV == 1) && E.dec.status == SVMG_ST_OK && E.alarm.level == SVMG_LVL_NORMAL;
  say("T07-f", ok, "1 su kien FAULT + 1 FAULT_CLEARED, khoi phuc ve OK/NORMAL sau khi cam bien tro lai"); TEST_ASSERT_TRUE(ok);
}
void test_T07_g_fault_does_not_hide_a_real_alarm(void) {
  settle_ok(); run_static(30.0, 0, 40);        /* nghiêng 30 độ kéo dài -> ngưỡng cứng */
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_CRITICAL, E.alarm.level);
  INJ = INJ_I2C_LOST; run_static(30.0, 0, 120);   /* rồi cảm biến chết: không được tự hạ cảnh báo */
  int ok = E.alarm.level == SVMG_LVL_CRITICAL;
  say("T07-g", ok, "mat cam bien khi dang CRITICAL: khong duoc tu ha canh bao"); TEST_ASSERT_TRUE(ok);
  INJ = INJ_NONE;
}

int main(void) {
  UNITY_BEGIN();
  RUN_TEST(test_T01_a_static_flat_reads_zero); RUN_TEST(test_T01_b_roll_30); RUN_TEST(test_T01_c_pitch_30); RUN_TEST(test_T01_d_gyro_units);
  RUN_TEST(test_T01_e_features_shown_for_oscillation); RUN_TEST(test_T01_f_sensor_error_shown);
  RUN_TEST(test_T05_offline_alarm_local_and_sync_exactly_once);
  RUN_TEST(test_T07_a_i2c_lost); RUN_TEST(test_T07_b_dead_bus_zeros); RUN_TEST(test_T07_c_saturated); RUN_TEST(test_T07_d_nan);
  RUN_TEST(test_T07_e_missing_samples_unknown_or_ok_never_alarm); RUN_TEST(test_T07_f_events_and_recovery); RUN_TEST(test_T07_g_fault_does_not_hide_a_real_alarm);
  return UNITY_END();
}
