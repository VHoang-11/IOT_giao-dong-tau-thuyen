// Chạy ENGINE THẬT qua các kịch bản và in ra đúng những bản tin MQTT mà firmware sẽ phát (cùng msg.cpp, cùng bộ lọc loại sự kiện).
// validate_messages.py kiểm từng dòng bằng JSON Schema trong contracts/schemas (Draft 7, giống validator của backend).
// Định dạng dòng:  <loại schema>\t<mô tả>\t<json>
#include <cstdio>
#include <cstring>
#include <cmath>
#include <cstdint>
#include "msg.h"
#include "svmg_engine.h"
#include "svmg_testutil.h"

static MsgIdent ID;
static svmg_engine_t E;
static svmg_engine_out_t OUT;
static double TS;
static uint32_t SEQ;
static int mode_fault = 0;     // 1: mất I2C, 2: bus trả 0

static double sea(double t) { return 3.0 * sin(6.283185307179586 * t / 20.0) + 2.0 * sin(6.283185307179586 * t / 14.0 + 1.0) + 2.0 * sin(6.283185307179586 * t / 26.0 + 2.0); }
static double amp = 1.0, hard = 0.0, off = 0.0;
static double roll_at(double t) { return hard > 0 ? hard : amp * sea(t) + off; }

static void emit(const char *kind, const char *name, const char *js) { std::printf("%s\t%s\t%s\n", kind, name, js); }

static void emit_events(const svmg_engine_out_t &o, const char *tag) {
  for (int i = 0; i < o.n_ev; i++) {
    svmg_event_t ev = o.ev[i];
    ev.t_sim_s = (float)TS;
    if (!msg_event_publishable(ev.type)) continue;           // đúng bộ lọc của app.cpp::push_event
    ev.seq = ++SEQ;
    char b[512];
    size_t n = msg_build_event(b, sizeof b, ID, ev);
    if (n) { char nm[96]; std::snprintf(nm, sizeof nm, "%s: %s->%s", tag, svmg_level_name((svmg_level_t)ev.prev_level), svmg_level_name((svmg_level_t)ev.level)); emit("event", nm, b); }
    else   { std::printf("INVALID_EVENT\t%s\ttype=%u alarm_id=%lu\t\n", tag, ev.type, (unsigned long)ev.alarm_id); }
  }
}

static void run(double seconds, const char *tag, bool ack_when_warning = false) {
  long n = (long)(seconds * 20);
  int tele_div = 0;
  for (long i = 0; i < n; i++) {
    double h = 0.01, r = roll_at(TS) * ST_D2R, rate = (roll_at(TS + h) - roll_at(TS - h)) / (2 * h) * ST_D2R;
    svmg_motion_sample_t s = st_sample(TS, r, rate, 0, 0);
    if (mode_fault == 1) s.valid = 0;
    if (mode_fault == 2) { s.ax = s.ay = s.az = s.gx = s.gy = s.gz = 0; }
    uint32_t now = (uint32_t)(TS * 1000.0);
    svmg_engine_push(&E, &s, now, &OUT);
    emit_events(OUT, tag);
    if (OUT.got_update && (++tele_div % 6) == 0) {            // telemetry mỗi 30 s mô phỏng để đủ mọi trạng thái mà không quá dài
      MsgTelemetry t;
      msg_fill_telemetry(&t, &E, (uint64_t)(TS * 1000.0), TS, 1, SVMG_SRC_SIMULATION, 2, mode_fault == 0, 3);
      char b[640]; size_t len = msg_build_telemetry(b, sizeof b, ID, ++SEQ, t);
      char nm[96]; std::snprintf(nm, sizeof nm, "%s: level=%d status=%d rf=%d b=%d", tag, E.alarm.level, E.dec.status, E.dec.cls_rf, E.dec.cls_b);
      if (len) emit("telemetry", nm, b); else std::printf("INVALID_TELEMETRY\t%s\t\t\n", tag);
    }
    svmg_engine_tick(&E, now, &OUT);
    emit_events(OUT, tag);
    if (ack_when_warning && E.alarm.level >= SVMG_LVL_WARNING && !E.alarm.acked) {
      svmg_engine_ack(&E, SVMG_ACKBY_BUTTON, now, &OUT);
      emit_events(OUT, "ack-button");
    }
    TS += 0.05;
  }
}

static int boots = 0;
static void new_engine(svmg_model_t primary) {
  std::snprintf(ID.boot_id, sizeof ID.boot_id, "b%07x", ++boots);   // mỗi lần khởi động có boot_id mới, seq về 0 (đúng thiết bị thật)
  SEQ = 0;
  svmg_config_t c; svmg_config_default(&c, primary);
  svmg_engine_init(&E, &c); TS = 0; mode_fault = 0; amp = 1.0; hard = 0.0; off = 0.0;
}

int main() {
  std::memset(&ID, 0, sizeof ID);
  ID.device_id = "vessel-demo-01"; ID.fw = "1.0.0"; ID.model_version = "none"; std::strcpy(ID.boot_id, "a3f9c0de");
  char b[700];

  // 1) khởi động nguội + ngưỡng cứng: lớp UNKNOWN, alarm_id phải có, class phải hợp lệ
  new_engine(SVMG_MODEL_BASELINE_B); hard = 25.0; run(30, "cold-hard");
  // 2) vòng đời đầy đủ: bình thường -> S1 (CAUTION -> WARNING -> ACK) -> trở lại bình thường (CLEARED)
  new_engine(SVMG_MODEL_BASELINE_B); run(300, "normal"); amp = 3.0; run(75, "s1", true); amp = 1.0; run(300, "recover");
  // 3) leo thang CRITICAL do không ACK
  new_engine(SVMG_MODEL_BASELINE_B); run(300, "normal"); amp = 3.0; run(150, "escalate");
  // 4) lỗi cảm biến: telemetry class_rf/b = FAULT
  new_engine(SVMG_MODEL_BASELINE_B); run(300, "normal"); mode_fault = 1; run(40, "i2c-lost"); mode_fault = 2; run(40, "dead-bus"); mode_fault = 0; run(120, "recovered");
  // 5) nghiêng lệch kéo dài (S2) và RF chưa có -> class_rf UNKNOWN
  new_engine(SVMG_MODEL_RF); run(300, "normal-rf-missing"); off = 5.0; run(200, "s2");

  // 6) bản tin cố định
  MsgHealth h; std::memset(&h, 0, sizeof h); h.uptime_ms = 123456789012ull; h.heap_free = 200000; h.heap_min = 180000; h.rssi = -61; h.sensor_ok = true;
  h.evbuf_depth = 3; h.reconnects = 2; h.i2c_errors = 1; h.infer_us_avg = 1500; h.infer_us_max = 2500;
  msg_build_health(b, sizeof b, ID, 9, h); emit("health", "health", b);
  h.sensor_ok = false; msg_build_health(b, sizeof b, ID, 10, h); emit("health", "health sensor_ok=false", b);
  msg_build_status_online(b, sizeof b, ID, 8); emit("status", "status online", b);
  msg_build_status_offline(b, sizeof b); emit("status", "LWT offline", b);
  svmg_cmd_ack_t a; std::memset(&a, 0, sizeof a); std::strcpy(a.cmd_id, "c-7f21"); a.applied = 1; a.config_version = 8;
  msg_build_cmd_ack(b, sizeof b, a, nullptr, nullptr); emit("command_ack", "ack APPLIED", b);
  a.applied = 0; a.reason = SVMG_R_FORBIDDEN_STATE; msg_build_cmd_ack(b, sizeof b, a, nullptr, nullptr); emit("command_ack", "ack REJECTED", b);
  float zr = 3.0f, zp = -0.5f; a.applied = 1; a.reason = SVMG_R_OK; msg_build_cmd_ack(b, sizeof b, a, &zr, &zp); emit("command_ack", "ack calibrate_zero", b);

  // 7) topic thiết bị dùng (để kiểm với ACL)
  for (int i = 0; i < MSG_PUBLISH_TOPIC_COUNT; i++) std::printf("TOPIC_PUB\t%s\t\t\n", MSG_PUBLISH_TOPICS[i]);
  for (int i = 0; i < MSG_SUBSCRIBE_TOPIC_COUNT; i++) std::printf("TOPIC_SUB\t%s\t\t\n", MSG_SUBSCRIBE_TOPICS[i]);
  return 0;
}
