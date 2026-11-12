// app.cpp - điều phối thiết bị: nối phần cứng, lõi C (engine), MQTT và xử lý lệnh/cấu hình.
// Nguyên tắc: cảnh báo cục bộ (LED/buzzer/LCD) chỉ phụ thuộc engine; mạng chỉ là kênh phụ.
#include <Arduino.h>
#include <Wire.h>
#include <esp_system.h>
#include <esp_heap_caps.h>
#include "app.h"
#include "svmg_build.h"
#include "pins.h"
#include "svmg_engine.h"
#include "svmg_evbuf.h"
#include "svmg_cmd.h"
#include "msg.h"
#include "mpu6050.h"
#include "motion_source.h"
#include "sim_iface.h"
#include "io.h"
#include "lcd.h"
#include "store.h"
#include "infer.h"
#include "net.h"
#include "trace.h"
#if __has_include("baseline_params.h")
#include "baseline_params.h"      // sinh bởi tools/gen_baseline_header.py từ baseline_params.json của M2
#define SVMG_HAVE_BASELINE_PARAMS 1
#endif

namespace {

svmg_engine_t   E;
svmg_evbuf_t    BUF;
svmg_cmd_ctx_t  CMDC;
MsgIdent        ID;

svmg_source_t   MODE = SVMG_SRC_SENSOR;
uint8_t         TIMEWARP = 1;
uint32_t        SEQ = 0;                 // dùng chung cho telemetry/event/health/trace (đề cương Phụ lục A: telemetry và event cùng chuỗi seq)
uint32_t        UPDATES = 0;
uint32_t        loop_overruns = 0;
uint32_t        next_tick_ms = 0;
bool            pot_override = false;
uint32_t        diag_until_ms = 0;
uint32_t        boot_count = 0;

char            CUR_CMD_ID[SVMG_CMD_ID_LEN];
bool            cal_pending = false;
char            cal_cmd_id[SVMG_CMD_ID_LEN];
uint16_t        snap_window = 0;
uint32_t        snap_deadline_ms = 0;

// ---------------------------------------------------------------- tiện ích
double t_now_abs() { return MODE == SVMG_SRC_SIMULATION ? motion_sim_time_abs() : (double)millis() / 1000.0; }

void make_boot_id(char *dst) {
  uint32_t r = esp_random();
  snprintf(dst, SVMG_BOOT_ID_LEN + 1, "%08lx", (unsigned long)r);
}

const char *class_short(svmg_class_t c) {
  switch (c) {
    case SVMG_NORMAL: return "NORMAL";
    case SVMG_HIGH_ROLL: return "HIGH ROLL";
    case SVMG_PERSISTENT_OFFSET: return "OFFSET";
    case SVMG_AMPLITUDE_GROWTH: return "GROWTH";
    case SVMG_UNKNOWN: return "UNKNOWN";
    default: return "FAULT";
  }
}
const char *level_short(svmg_level_t l) {
  switch (l) { case SVMG_LVL_NORMAL: return "NORM"; case SVMG_LVL_CAUTION: return "CAUT"; case SVMG_LVL_WARNING: return "WARN"; default: return "CRIT"; }
}

void push_event(svmg_event_t ev) {
  ev.t_sim_s = (float)t_now_abs();                       // nhãn thời gian tuyệt đối (lõi dùng t đã quấn vòng)
  svmg_evbuf_push(&BUF, &ev, ++SEQ);
  Serial.printf("[EV] seq=%lu type=%u level=%s prev=%s alarm=%lu val=%u\n", (unsigned long)SEQ, ev.type,
                svmg_level_name((svmg_level_t)ev.level), svmg_level_name((svmg_level_t)ev.prev_level), (unsigned long)ev.alarm_id, ev.val);
}

void push_sys_event(svmg_event_type_t type, uint8_t aux, uint16_t val, uint32_t arg = 0) {
  svmg_event_t e; memset(&e, 0, sizeof e);
  e.type = (uint8_t)type; e.aux = aux; e.val = val; e.alarm_id = arg;
  push_event(e);
}

int publish_json(const char *sub, size_t n, const char *js, int qos, bool retain) {
  if (!n) return -1;
  return net_publish(sub, js, (int)n, qos, retain);
}

void publish_ack(const svmg_cmd_ack_t &a, bool with_zero) {
  char js[240];
  float zr = E.cfg.zero_roll_deg, zp = E.cfg.zero_pitch_deg;
  size_t n = msg_build_cmd_ack(js, sizeof js, a, with_zero ? &zr : nullptr, with_zero ? &zp : nullptr);
  publish_json("cmd/ack", n, js, 1, false);
  Serial.printf("[ACK] %s\n", js);
}

void publish_status() {
  char js[200];
  size_t n = msg_build_status_online(js, sizeof js, ID, E.cfg.config_version);
  publish_json("status", n, js, 1, true);
}

bool sensor_ok() {
  if (MODE == SVMG_SRC_SIMULATION) return true;
  return E.dec.status != SVMG_ST_FAULT && mpu_consecutive_errors() < 20;
}

void send_telemetry() {
  if (!net_connected()) return;
  MsgTelemetry t; memset(&t, 0, sizeof t);
  const svmg_decision_state_t &d = E.dec;
  t.t_sim_s = (float)t_now_abs(); t.uptime_ms = millis(); t.timewarp = TIMEWARP; t.source_mode = MODE;
  t.scenario = MODE == SVMG_SRC_SIMULATION ? (int)sim_scenario() : -1;
  t.roll_deg = d.roll_deg; t.pitch_deg = d.pitch_deg; t.rms_roll_deg = d.feat.rms_roll_deg;
  t.heel_offset_deg = d.feat.mean_roll_deg; t.trend_rms_deg_per_min = d.feat.trend_rms_deg_per_min;
  t.cls_rf = d.cls_rf; t.cls_b = d.cls_b; t.mai = d.mai.value; t.alarm_level = E.alarm.level;
  t.config_version = E.cfg.config_version; t.sensor_ok = sensor_ok();
  t.acked = E.alarm.acked; t.data_status = d.status; t.sea_state = sim_sea_state();
  char js[640];
  size_t n = msg_build_telemetry(js, sizeof js, ID, SEQ + 1, t);
  if (n && net_publish("telemetry", js, (int)n, 0, false) >= 0) SEQ++;   // seq chỉ tiêu thụ khi thật sự giao cho MQTT
}

void send_health() {
  MsgHealth h; memset(&h, 0, sizeof h);
  h.uptime_ms = millis(); h.heap_free = ESP.getFreeHeap(); h.heap_min = ESP.getMinFreeHeap(); h.rssi = net_rssi();
  h.reconnects = net_reconnects(); h.i2c_errors = mpu_error_count(); h.samples_invalid = E.pipe.cnt_invalid; h.gaps = E.pipe.cnt_gap;
  h.loop_overruns = loop_overruns; h.infer_us_avg = infer_stats().avg_us(); h.infer_us_max = infer_stats().max_us;
  h.evbuf_depth = svmg_evbuf_depth(&BUF); h.evbuf_dropped = BUF.n_dropped_other + BUF.n_dropped_alarm;
  Serial.printf("[HEALTH] heap=%lu min=%lu stack_hwm=%u evbuf=%d\n", (unsigned long)h.heap_free, (unsigned long)h.heap_min, (unsigned)uxTaskGetStackHighWaterMark(nullptr), svmg_evbuf_depth(&BUF));
  h.cmd_exec = CMDC.n_exec; h.cmd_rejected = CMDC.n_rejected; h.rx_dropped = net_rx_dropped(); h.sensor_ok = sensor_ok();
  if (!net_connected()) return;                                   // vẫn in Serial ở trên khi mất mạng
  char js[620];
  size_t n = msg_build_health(js, sizeof js, ID, SEQ + 1, h);
  if (n && net_publish("health", js, (int)n, 0, false) >= 0) SEQ++;
}

void send_snapshot(uint16_t window_s) {
  int16_t r[TRACE_CAP], p[TRACE_CAP];
  int n = trace_copy(window_s, r, p, TRACE_CAP);
  const int CH = 40;
  int chunks = (n + CH - 1) / CH;
  for (int c = 0; c < chunks; c++) {
    int off = c * CH, m = (n - off < CH) ? (n - off) : CH;
    char js[900];
    size_t len = msg_build_trace(js, sizeof js, ID, SEQ + 1, (float)t_now_abs(), window_s, c, chunks, r + off, p + off, m);
    if (len && net_publish("trace", js, (int)len, 0, false) >= 0) SEQ++;
  }
  send_telemetry();                                               // kèm đặc trưng hiện tại (đề cương 8.2: request_snapshot)
}

// ---------------------------------------------------------------- xử lý đầu ra của engine
void commit_config(const svmg_config_t &c) {
  svmg_engine_apply_config(&E, &c);
  store_save(&E.cfg);
  push_sys_event(SVMG_EV_CONFIG_APPLIED, 0, 0, E.cfg.config_version);
  publish_status();
}

void finish_calibration(svmg_reason_t result) {
  if (!cal_pending) return;
  cal_pending = false;
  if (result == SVMG_R_OK) { svmg_config_t c = E.cfg; c.config_version++; commit_config(c); }   // E.cfg đã mang độ lệch mới
  svmg_cmd_ack_t ack;
  if (svmg_cmd_complete(&CMDC, cal_cmd_id, result, E.cfg.config_version, &ack)) publish_ack(ack, result == SVMG_R_OK);
}

void log_update(uint32_t now) {
  const svmg_decision_state_t &d = E.dec;
  Serial.printf("T,%.1f,%s,%.2f,%.2f,%.2f,%.2f,%.2f,%s,%s,%s,%u,%s,%u,%lu\n", t_now_abs(), MODE == SVMG_SRC_SIMULATION ? "SIM" : "SENSOR",
                d.roll_deg, d.pitch_deg, d.feat.rms_roll_deg, d.feat.mean_roll_deg, d.feat.trend_rms_deg_per_min,
                class_short(d.cls_rf), class_short(d.cls_b), class_short(d.cls_primary), d.mai.value,
                svmg_level_name(E.alarm.level), E.alarm.acked, (unsigned long)now);
}

void handle_out(const svmg_engine_out_t &o, uint32_t now) {
  for (int i = 0; i < o.n_ev; i++) push_event(o.ev[i]);
  if (o.calib_done) finish_calibration(o.calib_result);
  else if (cal_pending && !E.calib.active) finish_calibration(SVMG_R_FORBIDDEN_STATE);   // bị hủy giữa chừng (đổi chế độ/khoảng trống): đừng để lệnh treo
  if (o.got_2hz) {
    trace_push(E.dec.roll_deg, E.dec.pitch_deg);
    if (MODE == SVMG_SRC_SENSOR)                            // T01: giá trị thật đọc từ MPU6050 (2 Hz) và tình trạng cảm biến
      Serial.printf("R,%.1f,%.2f,%.2f,i2c_err=%lu,sat=%lu,valid=%u\n", t_now_abs(), E.dec.roll_deg, E.dec.pitch_deg,
                    (unsigned long)mpu_error_count(), (unsigned long)motion_saturation_count(), (unsigned)(E.pipe.cnt_invalid == 0));
  }
  if (o.got_update) {
    UPDATES++;
    log_update(now);
    if (((UPDATES * 5u) % E.cfg.report_interval_s) == 0) send_telemetry();
  }
}

// ---------------------------------------------------------------- đổi chế độ
void change_mode(svmg_source_t m) {
  if (m == MODE) return;
  MODE = m;
  if (m == SVMG_SRC_SENSOR) TIMEWARP = 1;
  if (m == SVMG_SRC_SIMULATION) motion_sim_clock_reset();
  svmg_engine_restart_signal(&E);       // đổi chế độ xóa bộ đệm cửa sổ (đề cương 8.2); KHÔNG xóa trạng thái cảnh báo
  trace_clear();
  push_sys_event(SVMG_EV_MODE_CHANGE, (uint8_t)m, 0);
  Serial.printf("[MODE] %s\n", m == SVMG_SRC_SIMULATION ? "SIMULATION" : "SENSOR");
}

void change_scenario(uint8_t scn, int sea /*-1: giữ*/) {
  uint8_t s = sea >= 0 ? (uint8_t)sea : sim_sea_state();
  sim_set_scenario(scn, s);
  if (sea >= 0) pot_override = true;
  push_sys_event(SVMG_EV_SCENARIO_CHANGE, scn, s);   // giữ cửa sổ: t0 của kịch bản mới rơi vào lịch sử đã có (warm start)
  Serial.printf("[SCN] %s sea=%u\n", svmg_scenario_name(scn), s);
}

// ---------------------------------------------------------------- hook của kênh lệnh
svmg_reason_t hk_ack(void *, uint32_t alarm_id, int has) {
  if (has && E.alarm.alarm_id != 0 && E.alarm.alarm_id != alarm_id) return SVMG_R_OK;   // ack của cảnh báo cũ: vô hại, không ack nhầm cảnh báo mới
  svmg_engine_out_t o; svmg_engine_ack(&E, SVMG_ACKBY_REMOTE, millis(), &o); handle_out(o, millis());
  return SVMG_R_OK;
}
svmg_reason_t hk_mute(void *, uint16_t d) {
  svmg_engine_out_t o; svmg_reason_t r = SVMG_R_OK; svmg_engine_mute(&E, d, millis(), &o, &r); handle_out(o, millis());
  return r;
}
svmg_reason_t hk_profile(void *, uint8_t p) {
  svmg_config_t c = E.cfg; svmg_config_apply_profile(&c, (svmg_profile_t)p); c.config_version++;
  if (svmg_config_validate(&c) != SVMG_R_OK) return SVMG_R_BAD_PARAM;
  commit_config(c);
  return SVMG_R_OK;
}
svmg_reason_t hk_calibrate(void *) {
  svmg_reason_t r = svmg_engine_calibrate_start(&E);
  if (r == SVMG_R_PENDING) { cal_pending = true; strncpy(cal_cmd_id, CUR_CMD_ID, sizeof cal_cmd_id - 1); }
  return r;
}
svmg_reason_t hk_scenario(void *, uint8_t scn, int sea) {
  if (MODE != SVMG_SRC_SIMULATION) return SVMG_R_FORBIDDEN_STATE;
  change_scenario(scn, sea);
  return SVMG_R_OK;
}
svmg_reason_t hk_mode(void *, uint8_t m) { change_mode((svmg_source_t)m); return SVMG_R_OK; }
svmg_reason_t hk_timewarp(void *, uint8_t tw) {
  if (MODE != SVMG_SRC_SIMULATION) return SVMG_R_FORBIDDEN_STATE;
  TIMEWARP = tw;                          // chỉ đổi đồng hồ ảo; hẹn giờ ACK 60 s dùng millis() nên không bị ảnh hưởng
  return SVMG_R_OK;
}
svmg_reason_t hk_snapshot(void *, uint16_t w) { snap_window = w; snap_deadline_ms = millis() + 10000; return SVMG_R_OK; }
svmg_reason_t hk_model(void *, uint8_t m) {
  if (m == SVMG_MODEL_RF && !infer_available()) return SVMG_R_UNSUPPORTED;   // chưa có model.h thật
  svmg_config_t c = E.cfg; c.primary_model = m; c.config_version++;
  commit_config(c);
  return SVMG_R_OK;
}
uint32_t hk_version(void *) { return E.cfg.config_version; }

const svmg_cmd_hooks_t HOOKS = { nullptr, hk_ack, hk_mute, hk_profile, hk_calibrate, hk_scenario, hk_mode, hk_timewarp, hk_snapshot, hk_model, hk_version };

void handle_cmd(const RxItem &it, uint32_t now) {
  svmg_cmd_t c;
  if (!msg_parse_cmd(it.payload, it.len, &c)) { Serial.println("[CMD] bo qua: JSON khong hop le"); return; }
  strncpy(CUR_CMD_ID, c.cmd_id, sizeof CUR_CMD_ID - 1); CUR_CMD_ID[sizeof CUR_CMD_ID - 1] = 0;
  svmg_cmd_ack_t ack;
  if (svmg_cmd_exec(&CMDC, &HOOKS, &c, now - it.rx_ms, &ack)) publish_ack(ack, false);
}

void handle_config(const RxItem &it) {
  svmg_config_t in; uint16_t crc; svmg_cmd_ack_t ack; memset(&ack, 0, sizeof ack);
  if (!msg_parse_config(it.payload, it.len, &in, &crc)) {
    strcpy(ack.cmd_id, "cfg-invalid"); ack.applied = 0; ack.reason = SVMG_R_BAD_PARAM; ack.config_version = E.cfg.config_version;
    publish_ack(ack, false); return;
  }
  snprintf(ack.cmd_id, sizeof ack.cmd_id, "cfg-%lu", (unsigned long)in.config_version);
  svmg_reason_t why = SVMG_R_OK;
  svmg_cfg_verdict_t v = svmg_config_check_update(&E.cfg, &in, crc, &why);
  if (v == SVMG_CFG_DUPLICATE) return;                              // retained gửi lại sau khi nối lại: im lặng
  if (v == SVMG_CFG_REJECT) {                                       // giữ cấu hình cũ
    ack.applied = 0; ack.reason = why; ack.config_version = E.cfg.config_version;
    publish_ack(ack, false); return;
  }
  svmg_config_t c = in; c.zero_roll_deg = E.cfg.zero_roll_deg; c.zero_pitch_deg = E.cfg.zero_pitch_deg;
  commit_config(c);
  ack.applied = 1; ack.reason = SVMG_R_OK; ack.config_version = E.cfg.config_version;
  publish_ack(ack, false);
}

// ---------------------------------------------------------------- LCD
void update_lcd(uint32_t now) {
  char l0[24], l1[24];
  if (now < diag_until_ms) {
    snprintf(l0, sizeof l0, "I2C:%s E:%lu H:%luk", motion_sensor_present() ? "ok" : "--", (unsigned long)mpu_error_count(), (unsigned long)(ESP.getFreeHeap() / 1024));
    snprintf(l1, sizeof l1, "m:%s c:%lu net:%d", infer_model_version(), (unsigned long)E.cfg.config_version, net_connected() ? 1 : 0);
  } else {
    const svmg_decision_state_t &d = E.dec;
    char r[10];
    if (E.dec.status == SVMG_ST_FAULT) snprintf(r, sizeof r, " --.-");
    else snprintf(r, sizeof r, "%+05.1f", d.roll_deg);
    if (MODE == SVMG_SRC_SIMULATION) snprintf(l0, sizeof l0, "SIM R:%s\xDF %s", r, svmg_scenario_name(sim_scenario()));
    else snprintf(l0, sizeof l0, "SEN R:%s\xDF", r);
    svmg_class_t shown = d.status == SVMG_ST_FAULT ? SVMG_FAULT : (d.status == SVMG_ST_UNKNOWN ? SVMG_UNKNOWN : d.cls_primary);
    if (E.alarm.level >= SVMG_LVL_WARNING && shown == SVMG_NORMAL) shown = E.alarm.cls;
    snprintf(l1, sizeof l1, "%-10s %s%s", class_short(shown), level_short(E.alarm.level), E.alarm.acked ? "*" : "");
  }
  lcd_line(0, l0); lcd_line(1, l1);
}

#ifdef SVMG_FAULT_INJECT
// Gõ vào Serial Monitor: i z n d s x (lỗi cảm biến) | m (bật/tắt ngắt MQTT)
void handle_serial_inject() {
  static bool blackout = false;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r' || c == ' ') continue;
    if (c == 'm') { blackout = !blackout; net_inject_blackout(blackout); Serial.printf("[INJECT] mqtt blackout=%d\n", blackout ? 1 : 0); }
    else { motion_inject(c); Serial.printf("[INJECT] sensor fault '%c'\n", c); }
  }
}
#endif

}  // namespace

// ================================================================ setup / loop
void app_setup() {
  Serial.begin(115200);
  delay(100);
  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(400000);
  io_init();
  io_all_leds(true); io_beep(120); delay(250); io_all_leds(false);        // thử đèn/còi lúc khởi động

  bool lcd_ok = lcd_begin();
  lcd_line(0, "SVMG " SVMG_FW_VERSION); lcd_line(1, "khoi dong...");

  motion_init();
  float gnorm = 0; bool st_ok = mpu_selftest(&gnorm);
  Serial.printf("\n=== Smart Vessel Motion Guard fw %s | device %s ===\n", SVMG_FW_VERSION, SVMG_DEVICE_ID);
  Serial.printf("[HW] LCD:%s MPU6050:%s selftest |a|=%.3f g %s\n", lcd_ok ? "ok" : "ABSENT", motion_sensor_present() ? "ok" : "ABSENT", gnorm,
                !st_ok ? "(KHONG DOC DUOC)" : (gnorm > 0.8f && gnorm < 1.2f ? "(thang do OK)" : "(THANG DO LECH - kiem tra +-2g)"));

  svmg_config_t cfg;
  bool loaded = store_load(&cfg, infer_available() ? SVMG_MODEL_RF : SVMG_MODEL_BASELINE_B);
  boot_count = store_next_boot_count();
  Serial.printf("[CFG] %s version=%lu profile=%s n=%u phi=%u mai=%u rep=%u model=%s zero=(%.2f,%.2f) boots=%lu\n", loaded ? "NVS" : "mac dinh",
                (unsigned long)cfg.config_version, svmg_profile_name(cfg.profile), cfg.debounce_n, cfg.phi_hard_deg, cfg.mai_caution,
                cfg.report_interval_s, svmg_model_name(cfg.primary_model), cfg.zero_roll_deg, cfg.zero_pitch_deg, (unsigned long)boot_count);

  svmg_engine_init(&E, &cfg);
#ifdef SVMG_HAVE_BASELINE_PARAMS
  E.bp = SVMG_BASELINE_B_PARAMS;
  E.mp = SVMG_MAI_PARAMS;
  Serial.println("[CFG] tham so Baseline B / MAI: tu M2 (baseline_params.h)");
#else
  Serial.println("[CFG] tham so Baseline B / MAI: MAC DINH cua M1 (chua co baseline_params.json cua M2)");
#endif
  infer_begin(&E);
  svmg_evbuf_init(&BUF);
  svmg_cmd_init(&CMDC);

  memset(&ID, 0, sizeof ID);
  ID.device_id = SVMG_DEVICE_ID; ID.fw = SVMG_FW_VERSION; ID.model_version = infer_model_version();
  make_boot_id(ID.boot_id);
  Serial.printf("[ID] boot_id=%s model=%s RF=%s sim=%s\n", ID.boot_id, ID.model_version, infer_available() ? "that" : "STUB->Baseline B", sim_is_stub() ? "STUB" : "M2");

  push_sys_event(SVMG_EV_BOOT, 0, (uint16_t)esp_reset_reason());
  net_begin(ID);
  next_tick_ms = millis();
}

void app_loop() {
  uint32_t now = millis();
#ifdef SVMG_FAULT_INJECT
  handle_serial_inject();
#endif

  // ---- nút bấm
  switch (io_poll_buttons(now)) {
    case BTN_MODE_SHORT: change_mode(MODE == SVMG_SRC_SENSOR ? SVMG_SRC_SIMULATION : SVMG_SRC_SENSOR); break;
    case BTN_SCN_SHORT:
      if (MODE == SVMG_SRC_SIMULATION) change_scenario((uint8_t)((sim_scenario() + 1) % 6), -1);
      break;
    case BTN_ACK_SHORT: { svmg_engine_out_t o; svmg_engine_ack(&E, SVMG_ACKBY_BUTTON, now, &o); handle_out(o, now); break; }
    case BTN_ACK_LONG: diag_until_ms = now + 10000; break;
    default: break;
  }

  // ---- lấy mẫu 20 Hz (SIMULATION: nhân timewarp số mẫu mỗi nhịp, hẹn giờ ACK vẫn theo thời gian thực)
  if ((int32_t)(now - next_tick_ms) >= 0) {
    if (now - next_tick_ms > 3 * SVMG_TICK_MS) { loop_overruns++; next_tick_ms = now; }
    next_tick_ms += SVMG_TICK_MS;
    int n = (MODE == SVMG_SRC_SIMULATION) ? TIMEWARP : 1;
    for (int i = 0; i < n; i++) {
      svmg_motion_sample_t s = acquireMotionSample(MODE);
      svmg_engine_out_t o;
      svmg_engine_push(&E, &s, now, &o);
      handle_out(o, now);
    }
    { svmg_engine_out_t o; svmg_engine_tick(&E, now, &o); handle_out(o, now); }

    static uint32_t last_pot = 0;
    if (MODE == SVMG_SRC_SIMULATION && now - last_pot > 200) {
      last_pot = now;
      int sea = io_read_sea_state();
      static int prev_sea = -1;
      if (prev_sea >= 0 && sea != prev_sea) pot_override = false;           // người dùng vặn chiết áp: chiết áp lại có quyền
      prev_sea = sea;
      if (!pot_override && sea != sim_sea_state()) { sim_set_sea_state((uint8_t)sea); Serial.printf("[SEA] pot -> %d\n", sea); }
    }
  }

  // ---- đầu ra cục bộ: chỉ phụ thuộc engine
  { svmg_alarm_out_t ao; svmg_alarm_outputs(&E.alarm, now, &ao); io_apply_outputs(ao, now); }

  static uint32_t last_lcd = 0, last_health = 0;
  if (now - last_lcd >= 250) { last_lcd = now; update_lcd(now); }
  if (now - last_health >= 30000) { last_health = now; send_health(); }

  // ---- mạng
  net_service(now, &BUF, E.cfg.config_version);
  RxItem it;
  for (int k = 0; k < 2 && net_pop_rx(&it); k++) {
    if (it.kind == RX_CMD) handle_cmd(it, now); else handle_config(it);
  }
  if (snap_window) {
    if (net_connected()) { send_snapshot(snap_window); snap_window = 0; }
    else if ((int32_t)(now - snap_deadline_ms) > 0) snap_window = 0;       // hết hạn: bỏ
  }
  delay(1);
}
