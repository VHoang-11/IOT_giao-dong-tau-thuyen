/* msg.cpp - xem msg.h. */
#include "msg.h"
#include "svmg_evbuf.h"
#include <ArduinoJson.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <stdlib.h>

#ifndef SVMG_TELEMETRY_EXTRAS
#define SVMG_TELEMETRY_EXTRAS 0
#endif

/* ---------------- bộ ghi có chặn tràn ---------------- */
namespace {
struct W {
  char *b; size_t cap, n; bool ok;
  W(char *buf, size_t c) : b(buf), cap(c), n(0), ok(c > 0) { if (ok) b[0] = 0; }
  void raw(const char *s) {
    size_t l = strlen(s);
    if (!ok || n + l + 1 > cap) { ok = false; return; }
    memcpy(b + n, s, l + 1); n += l;
  }
  void fmt(const char *f, ...) __attribute__((format(printf, 2, 3)));
  void str(const char *s) {          /* chuỗi JSON có thoát ký tự */
    raw("\"");
    for (; s && *s && ok; s++) {
      unsigned char c = (unsigned char)*s;
      char t[8];
      if (c == '"' || c == '\\') { t[0] = '\\'; t[1] = (char)c; t[2] = 0; }
      else if (c < 0x20) snprintf(t, sizeof t, "\\u%04x", c);
      else { t[0] = (char)c; t[1] = 0; }
      raw(t);
    }
    raw("\"");
  }
  void num(float v, int dec) {
    if (!isfinite(v)) { raw("null"); return; }
    char t[24]; snprintf(t, sizeof t, "%.*f", dec, (double)v); raw(t);
  }
  size_t done() const { return ok ? n : 0; }
};
void W::fmt(const char *f, ...) {
  if (!ok) return;
  va_list ap; va_start(ap, f);
  int r = vsnprintf(b + n, cap - n, f, ap);
  va_end(ap);
  if (r < 0 || (size_t)r >= cap - n) { ok = false; return; }
  n += (size_t)r;
}

const char *src_name(uint8_t m) { return m == SVMG_SRC_SIMULATION ? "SIMULATION" : "SENSOR"; }

void head(W &w, const MsgIdent &id, uint32_t seq) {
  w.raw("{\"device_id\":"); w.str(id.device_id);
  w.raw(",\"boot_id\":"); w.str(id.boot_id);
  w.fmt(",\"seq\":%lu", (unsigned long)seq);
}
}  // namespace

const char *const MSG_PUBLISH_TOPICS[] = { "telemetry", "event", "status", "health", "cmd/ack"
#ifdef SVMG_EXT_TRACE
  , "trace"
#endif
};
const int MSG_PUBLISH_TOPIC_COUNT = (int)(sizeof MSG_PUBLISH_TOPICS / sizeof MSG_PUBLISH_TOPICS[0]);
const char *const MSG_SUBSCRIBE_TOPICS[] = { "cmd", "config" };
const int MSG_SUBSCRIBE_TOPIC_COUNT = 2;

size_t msg_alarm_id_str(char *buf, size_t cap, uint32_t id) {
  int r = snprintf(buf, cap, "A-%04lu", (unsigned long)id);
  return (r < 0 || (size_t)r >= cap) ? 0 : (size_t)r;
}

void msg_fill_telemetry(MsgTelemetry *t, const svmg_engine_t *e, uint64_t uptime_ms, double t_abs_s, uint8_t timewarp,
                        uint8_t source_mode, int scenario, bool sensor_ok, uint8_t sea_state) {
  const svmg_decision_state_t &d = e->dec;
  memset(t, 0, sizeof *t);
  t->t_sim_s = (float)t_abs_s; t->uptime_ms = uptime_ms; t->timewarp = timewarp; t->source_mode = source_mode;
  t->scenario = source_mode == SVMG_SRC_SIMULATION ? scenario : -1;
  t->roll_deg = d.roll_deg; t->pitch_deg = d.pitch_deg; t->rms_roll_deg = d.feat.rms_roll;
  t->heel_offset_deg = d.feat.mean_roll; t->trend_rms_deg_per_min = d.feat.trend_rms_slope;
  t->cls_rf = d.cls_rf; t->cls_b = d.cls_b; t->mai = d.mai.value; t->alarm_level = e->alarm.level;
  t->config_version = e->cfg.config_version; t->sensor_ok = sensor_ok;
  t->acked = e->alarm.acked; t->data_status = d.status; t->sea_state = sea_state;
}

/* ---------------- build ---------------- */
size_t msg_build_telemetry(char *buf, size_t cap, const MsgIdent &id, uint32_t seq, const MsgTelemetry &t) {
  W w(buf, cap);
  head(w, id, seq);
  w.raw(",\"t_sim_s\":"); w.num(t.t_sim_s, 1);
  w.fmt(",\"uptime_ms\":%llu,\"timewarp\":%u", (unsigned long long)t.uptime_ms, (unsigned)t.timewarp);
  w.raw(",\"source_mode\":"); w.str(src_name(t.source_mode));
  w.fmt(",\"synthetic\":%s", t.source_mode == SVMG_SRC_SIMULATION ? "true" : "false");
  w.raw(",\"scenario_id\":");
  if (t.scenario >= 0) w.str(svmg_scenario_name((uint8_t)t.scenario)); else w.raw("null");
  w.raw(",\"roll_deg\":"); w.num(t.roll_deg, 2);
  w.raw(",\"pitch_deg\":"); w.num(t.pitch_deg, 2);
  if(isfinite(t.rms_roll_deg)) { w.raw(",\"rms_roll_deg\":"); w.num(t.rms_roll_deg, 2); }
  if(isfinite(t.heel_offset_deg)) { w.raw(",\"heel_offset_deg\":"); w.num(t.heel_offset_deg, 2); }
  if(isfinite(t.trend_rms_deg_per_min)) { w.raw(",\"trend_rms_deg_per_min\":"); w.num(t.trend_rms_deg_per_min, 2); }
  w.raw(",\"class_rf\":"); w.str(svmg_class_name((svmg_class_t)t.cls_rf));
  /* schema: class_baseline_b không có FAULT (trường tùy chọn) -> bỏ khi lỗi cảm biến thay vì phát giá trị làm bản tin bị loại */
  if (t.cls_b != SVMG_FAULT) { w.raw(",\"class_baseline_b\":"); w.str(svmg_class_name((svmg_class_t)t.cls_b)); }
  /* MAI là phép đo tổng hợp có nguồn gốc feature; khi data UNKNOWN/FAULT thì
   * bỏ trường tùy chọn thay vì phát số cache cũ hoặc giả vờ là MAI=0. */
  if (t.data_status == SVMG_ST_OK)
    w.fmt(",\"mai\":%u", (unsigned)t.mai);
  w.raw(",\"alarm_level\":"); w.str(svmg_level_name((svmg_level_t)t.alarm_level));
  w.raw(",\"model_version\":"); w.str(id.model_version);
  w.fmt(",\"config_version\":%lu,\"sensor_ok\":%s", (unsigned long)t.config_version, t.sensor_ok ? "true" : "false");
#if SVMG_TELEMETRY_EXTRAS
  w.fmt(",\"acked\":%s,\"data_status\":%u,\"sea_state\":%u", t.acked ? "true" : "false", (unsigned)t.data_status, (unsigned)t.sea_state);
#endif
  w.raw("}");
  return w.done();
}

bool msg_event_publishable(uint8_t type) {
  if (type == SVMG_EV_ALARM_STATE || type == SVMG_EV_ALARM_ACK) return true;
#ifdef SVMG_EXT_EVENTS
  return type >= SVMG_EV_ALARM_MUTE && type <= SVMG_EV_BOOT;
#else
  return false;
#endif
}

size_t msg_build_event(char *buf, size_t cap, const MsgIdent &id, const svmg_event_t &e) {
  if (!msg_event_publishable(e.type)) return 0;
  W w(buf, cap);
  head(w, id, e.seq);
  char aid[16]; msg_alarm_id_str(aid, sizeof aid, e.alarm_id);
  switch (e.type) {
    case SVMG_EV_ALARM_STATE:
    case SVMG_EV_ALARM_ACK: {
      if (e.alarm_id == 0) return 0;                      /* schema bắt buộc alarm_id kiểu chuỗi: không phát bản tin sai */
      bool ack = (e.type == SVMG_EV_ALARM_ACK);
      svmg_class_t c = (e.cls <= SVMG_AMPLITUDE_GROWTH) ? (svmg_class_t)e.cls : SVMG_NORMAL;   /* schema chỉ cho 4 lớp */
      w.raw(",\"type\":\"ALARM_STATE\",\"alarm_id\":"); w.str(aid);
      w.raw(",\"level\":"); w.str(svmg_level_name((svmg_level_t)e.level));
      w.raw(",\"prev_level\":"); w.str(svmg_level_name((svmg_level_t)(ack ? e.level : e.prev_level)));
      w.raw(",\"class\":"); w.str(svmg_class_name(c));
      w.raw(",\"t_sim_s\":"); w.num(e.t_sim_s, 1);
      w.raw(",\"acked_by\":");
      if (ack) w.str(e.acked_by == SVMG_ACKBY_BUTTON ? "device_button" : "remote"); else w.raw("null");
      break;
    }
#ifdef SVMG_EXT_EVENTS
    case SVMG_EV_ALARM_MUTE:
      w.raw(",\"type\":\"ALARM_MUTE\",\"alarm_id\":"); w.str(aid);
      w.fmt(",\"duration_s\":%u", (unsigned)e.val);
      w.raw(",\"t_sim_s\":"); w.num(e.t_sim_s, 1);
      break;
    case SVMG_EV_MODE_CHANGE:
      w.raw(",\"type\":\"MODE_CHANGE\",\"mode\":"); w.str(src_name(e.aux));
      w.raw(",\"t_sim_s\":"); w.num(e.t_sim_s, 1);
      break;
    case SVMG_EV_SCENARIO_CHANGE:
      w.raw(",\"type\":\"SCENARIO_CHANGE\",\"scenario_id\":"); w.str(svmg_scenario_name(e.aux));
      w.fmt(",\"sea_state\":%u", (unsigned)e.val);
      w.raw(",\"t_sim_s\":"); w.num(e.t_sim_s, 1);
      break;
    case SVMG_EV_FAULT:
      w.fmt(",\"type\":\"FAULT\",\"reason_bits\":%u", (unsigned)e.val);
      w.raw(",\"t_sim_s\":"); w.num(e.t_sim_s, 1);
      break;
    case SVMG_EV_FAULT_CLEARED:
      w.raw(",\"type\":\"FAULT_CLEARED\",\"t_sim_s\":"); w.num(e.t_sim_s, 1);
      break;
    case SVMG_EV_CONFIG_APPLIED:
      w.fmt(",\"type\":\"CONFIG_APPLIED\",\"config_version\":%lu", (unsigned long)e.alarm_id);   /* alarm_id mang config_version */
      break;
    case SVMG_EV_CALIBRATION:
      w.raw(",\"type\":\"CALIBRATION\",\"result\":"); w.str(e.val == SVMG_R_OK ? "OK" : svmg_reason_name((svmg_reason_t)e.val));
      w.raw(",\"t_sim_s\":"); w.num(e.t_sim_s, 1);
      break;
    case SVMG_EV_BOOT:
      w.fmt(",\"type\":\"BOOT\",\"reset_reason\":%u", (unsigned)e.val);
      break;
#endif
    default:
      return 0;
  }
  w.raw("}");
  return w.done();
}

size_t msg_build_status_online(char *buf, size_t cap, const MsgIdent &id, uint32_t config_version) {
  W w(buf, cap);
  w.raw("{\"state\":\"online\",\"fw\":"); w.str(id.fw);
  w.raw(",\"model_version\":"); w.str(id.model_version);
  w.raw(",\"feature_schema_version\":");w.str(SVMG_FEATURE_SCHEMA_VERSION);
  w.raw(",\"preprocessing_version\":");w.str(SVMG_PREPROCESSING_VERSION);
  w.fmt(",\"feature_count\":%d",SVMG_N_FEATURES);
  w.fmt(",\"config_version\":%lu,\"boot_id\":", (unsigned long)config_version); w.str(id.boot_id);
  w.raw("}");
  return w.done();
}

size_t msg_build_status_offline(char *buf, size_t cap) {
  W w(buf, cap); w.raw("{\"state\":\"offline\"}"); return w.done();
}

size_t msg_build_health(char *buf, size_t cap, const MsgIdent &id, uint32_t seq, const MsgHealth &h) {
  /* Tên trường theo contracts/schemas/health.json; schema không có boot_id/seq nên không phát (device_id đủ định danh). */
  (void)seq;
  W w(buf, cap);
  w.raw("{\"device_id\":"); w.str(id.device_id);
  w.raw(",\"feature_schema_version\":");w.str(SVMG_FEATURE_SCHEMA_VERSION);
  w.raw(",\"preprocessing_version\":");w.str(SVMG_PREPROCESSING_VERSION);
  w.fmt(",\"feature_count\":%d",SVMG_N_FEATURES);
  w.fmt(",\"feature_valid_mask\":%lu,\"data_status\":%u",(unsigned long)h.feature_valid_mask,(unsigned)h.data_status);
  w.fmt(",\"feature_update_us_last\":%lu,\"feature_update_us_max\":%lu",(unsigned long)h.feature_update_us_last,(unsigned long)h.feature_update_us_max);
  w.fmt(",\"free_heap_bytes\":%lu,\"min_free_heap_bytes\":%lu,\"uptime_ms\":%llu", (unsigned long)h.heap_free,
        (unsigned long)h.heap_min, (unsigned long long)h.uptime_ms);
  w.fmt(",\"sensor_ok\":%s,\"i2c_errors\":%lu", h.sensor_ok ? "true" : "false", (unsigned long)h.i2c_errors);
  w.raw(",\"inference_ms\":"); w.num((float)h.infer_us_avg / 1000.0f, 3);
  w.fmt(",\"mqtt_reconnects\":%lu,\"buffer_used\":%lu,\"buffer_capacity\":%d", (unsigned long)h.reconnects, (unsigned long)h.evbuf_depth, SVMG_EVBUF_CAP);
  /* trường phụ (schema cho phép) */
  w.fmt(",\"rssi\":%d,\"samples_invalid\":%lu,\"gaps\":%lu,\"loop_overruns\":%lu,\"inference_ms_max\":", h.rssi,
        (unsigned long)h.samples_invalid, (unsigned long)h.gaps, (unsigned long)h.loop_overruns);
  w.num((float)h.infer_us_max / 1000.0f, 3);
  w.fmt(",\"buffer_dropped\":%lu,\"cmd_exec\":%lu,\"cmd_rejected\":%lu,\"rx_dropped\":%lu}", (unsigned long)h.evbuf_dropped,
        (unsigned long)h.cmd_exec, (unsigned long)h.cmd_rejected, (unsigned long)h.rx_dropped);
  return w.done();
}

size_t msg_build_cmd_ack(char *buf, size_t cap, const svmg_cmd_ack_t &a, const float *zr, const float *zp) {
  W w(buf, cap);
  w.raw("{\"cmd_id\":"); w.str(a.cmd_id);
  w.raw(",\"result\":"); w.str(a.applied ? "APPLIED" : "REJECTED");
  w.fmt(",\"config_version\":%lu,\"reason\":", (unsigned long)a.config_version);
  if (a.applied) w.raw("null"); else w.str(svmg_reason_name(a.reason));
  if (a.applied && zr && zp) { w.raw(",\"zero_roll_deg\":"); w.num(*zr, 2); w.raw(",\"zero_pitch_deg\":"); w.num(*zp, 2); }
  w.raw("}");
  return w.done();
}

#ifdef SVMG_EXT_TRACE
size_t msg_build_trace(char *buf, size_t cap, const MsgIdent &id, uint32_t seq, float t_end_s, uint16_t window_s,
                       int chunk, int chunks, const int16_t *r, const int16_t *p, int n) {
  W w(buf, cap);
  head(w, id, seq);
  w.raw(",\"t_end_s\":"); w.num(t_end_s, 1);
  w.fmt(",\"window_s\":%u,\"fs_hz\":10,\"chunk\":%d,\"chunks\":%d,\"roll_cdeg\":[", (unsigned)window_s, chunk, chunks);
  for (int i = 0; i < n; i++) w.fmt(i ? ",%d" : "%d", (int)r[i]);
  w.raw("],\"pitch_cdeg\":[");
  for (int i = 0; i < n; i++) w.fmt(i ? ",%d" : "%d", (int)p[i]);
  w.raw("]}");
  return w.done();
}
#endif  // SVMG_EXT_TRACE

/* ---------------- parse ---------------- */
#ifndef SVMG_MSG_NO_PARSE   /* chỉ để đo chi phí flash của ArduinoJson (xem docs/M1-06_mqtt_json_decision.md) */
namespace {
const uint32_t BAD = 0xFFFFFFFFu;

/* -1: vắng; 0: có nhưng sai kiểu/âm/không nguyên (*out = BAD); 1: hợp lệ */
int get_uint(JsonVariantConst v, uint32_t *out) {
  if (v.isNull()) return -1;
  if (v.is<float>() || v.is<int>()) {
    double d = v.as<double>();
    if (d >= 0 && d <= 4294967000.0 && d == (double)(uint32_t)d) { *out = (uint32_t)d; return 1; }
  }
  *out = BAD; return 0;
}
/* số thực: NaN nếu có mặt nhưng sai kiểu (svmg_cmd_exec sẽ trả BAD_PARAM) */
int get_float(JsonVariantConst v, float *out) {
  if (v.isNull()) return -1;
  if (v.is<float>() || v.is<int>()) { *out = v.as<float>(); return 1; }
  *out = NAN; return 0;
}
/* chuỗi enum -> chỉ số, hoặc 0xFF nếu sai */
template <typename F> uint8_t get_enum(JsonVariantConst v, F from_str) {
  if (!v.is<const char *>()) return 0xFF;
  int r = from_str(v.as<const char *>());
  return r < 0 ? 0xFF : (uint8_t)r;
}
uint8_t clamp8(uint32_t v) { return v > 254 ? 0xFE : (uint8_t)v; }   /* 0xFE: ngoài miền mọi tham số của lệnh -> BAD_PARAM */
uint16_t clamp16(uint32_t v) { return v > 65534 ? 0xFFFE : (uint16_t)v; }
#ifdef SVMG_EXT_COMMANDS
int mode_from_str(const char *s) { return !s ? -1 : !strcmp(s, "SENSOR") ? 0 : !strcmp(s, "SIMULATION") ? 1 : -1; }
#endif

struct CmdName { const char *n; svmg_cmd_type_t t; };
const CmdName CMD_NAMES[] = {
  {"set_profile", SVMG_CMD_SET_PROFILE}, {"set_threshold", SVMG_CMD_SET_THRESHOLD}, {"calibrate_zero", SVMG_CMD_CALIBRATE_ZERO},
  {"mute_alarm", SVMG_CMD_MUTE_ALARM}, {"start_voyage", SVMG_CMD_START_VOYAGE}, {"stop_voyage", SVMG_CMD_STOP_VOYAGE},
  {"restart_device", SVMG_CMD_RESTART_DEVICE}, {"ack_alarm", SVMG_CMD_ACK_ALARM},
#ifdef SVMG_EXT_COMMANDS
  {"set_mode", SVMG_CMD_SET_MODE}, {"set_scenario", SVMG_CMD_SET_SCENARIO}, {"set_timewarp", SVMG_CMD_SET_TIMEWARP},
  {"request_snapshot", SVMG_CMD_REQUEST_SNAPSHOT}, {"set_model", SVMG_CMD_SET_MODEL},
#endif
};
}  // namespace

bool msg_parse_cmd(const char *payload, size_t len, svmg_cmd_t *o) {
  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, payload, len) != DeserializationError::Ok) return false;
  memset(o, 0, sizeof *o);
  o->phi_hard_deg = NAN;
  const char *id = doc["cmd_id"] | (const char *)nullptr;
  if (!id || !id[0] || strlen(id) >= SVMG_CMD_ID_LEN) return false;
  strncpy(o->cmd_id, id, SVMG_CMD_ID_LEN - 1);
  const char *by = doc["issued_by"] | "";
  strncpy(o->issued_by, by, SVMG_CMD_ISSUER_LEN - 1);

  uint32_t u;
  /* ttl_s bắt buộc, 1..65534 (schema backend giới hạn 300). Thiếu/sai kiểu -> ttl 0 -> BAD_PARAM; age_s có mặt mà sai -> cũng BAD_PARAM. */
  o->ttl_s = (get_uint(doc["ttl_s"], &u) == 1) ? clamp16(u) : 0;
  int ra = get_uint(doc["age_s"], &u);
  if (ra == 1) o->age_s = clamp16(u);
  else if (ra == 0) o->ttl_s = 0;

  const char *name = doc["cmd"] | "";
  JsonVariantConst p = doc["params"];
  o->type = SVMG_CMD_NONE;
  for (const CmdName &m : CMD_NAMES) if (!strcmp(name, m.n)) o->type = (uint8_t)m.t;

  if (get_uint(p["duration_s"], &u) >= 0)         { o->has |= SVMG_CP_DURATION; o->duration_s = clamp16(u); }
  if (get_uint(p["mai_caution"], &u) >= 0)        { o->has |= SVMG_CP_MAI; o->mai_caution = clamp8(u); }
  if (get_uint(p["debounce_n"], &u) >= 0)         { o->has |= SVMG_CP_DEBOUNCE; o->debounce_n = clamp8(u); }
  if (get_uint(p["report_interval_s"], &u) >= 0)  { o->has |= SVMG_CP_REPORT; o->report_interval_s = clamp16(u); }
  if (get_float(p["phi_hard_deg"], &o->phi_hard_deg) >= 0) o->has |= SVMG_CP_PHI;
  if (!p["profile"].isNull())  { o->has |= SVMG_CP_PROFILE; o->profile = get_enum(p["profile"], svmg_profile_from_str); }
  if (!p["alarm_id"].isNull()) {
    o->has |= SVMG_CP_ALARM;
    if (p["alarm_id"].is<const char *>()) {
      const char *s = p["alarm_id"].as<const char *>();
      o->alarm_id = (s && s[0] == 'A' && s[1] == '-') ? (uint32_t)strtoul(s + 2, nullptr, 10) : 0;
    } else if (get_uint(p["alarm_id"], &u) == 1) o->alarm_id = u;
  }
#ifdef SVMG_EXT_COMMANDS
  if (get_uint(p["window_s"], &u) >= 0)   { o->has |= SVMG_CP_WINDOW; o->window_s = clamp16(u); }
  if (get_uint(p["sea_state"], &u) >= 0)  { o->has |= SVMG_CP_SEA; o->sea_state = clamp8(u); }
  if (get_uint(p["timewarp"], &u) >= 0)   { o->has |= SVMG_CP_TIMEWARP; o->timewarp = clamp8(u); }
  if (!p["scenario"].isNull()) { o->has |= SVMG_CP_SCENARIO; o->scenario = get_enum(p["scenario"], svmg_scenario_from_str); }
  if (!p["mode"].isNull())     { o->has |= SVMG_CP_MODE;     o->mode = get_enum(p["mode"], mode_from_str); }
  if (!p["model"].isNull())    { o->has |= SVMG_CP_MODEL;    o->model = get_enum(p["model"], svmg_model_from_str); }
#endif
  return true;
}

/* ============ CRC của config: CRC-16/CCITT-FALSE trên JSON chuẩn tắc như backend (config_service.compute_crc) ============
 * Python: json.dumps({k: v for k != "crc"}, sort_keys=True, separators=(",", ":")) -> mã hóa utf-8 (ensure_ascii nên toàn ASCII).
 * Số nguyên in nguyên; số thực in theo repr của Python (ngắn nhất khứ hồi, có ".0" nếu nguyên); chuỗi thoát kiểu ensure_ascii. */
namespace {
struct Cat {
  char buf[640]; size_t n; bool ok;
  Cat() : n(0), ok(true) { buf[0] = 0; }
  void put(const char *s) { size_t l = strlen(s); if (n + l + 1 > sizeof buf) { ok = false; return; } memcpy(buf + n, s, l + 1); n += l; }
  void putc_(char c) { char t[2] = { c, 0 }; put(t); }
};

void py_float(double v, Cat &c) {
  if (!isfinite(v)) { c.ok = false; return; }
  char e[40]; int prec = 0;
  for (; prec <= 16; prec++) { snprintf(e, sizeof e, "%.*e", prec, v); if (strtod(e, nullptr) == v) break; }
  if (prec > 16) snprintf(e, sizeof e, "%.16e", v);
  bool neg = (e[0] == '-'); const char *q = e + (neg ? 1 : 0);
  char digits[24]; int nd = 0;
  for (; *q && *q != 'e'; q++) if (*q != '.') digits[nd++] = *q;
  digits[nd] = 0;
  int ex = atoi(q + 1);
  while (nd > 1 && digits[nd - 1] == '0') digits[--nd] = 0;       /* rút gọn số 0 cuối (giữ chữ số đầu) */
  char out[64]; size_t k = 0;
  if (neg) out[k++] = '-';
  if (ex >= -4 && ex < 16) {                                       /* ký hiệu thập phân như Python */
    if (ex >= 0) {
      for (int i = 0; i <= ex; i++) out[k++] = (i < nd) ? digits[i] : '0';
      out[k++] = '.';
      if (nd > ex + 1) for (int i = ex + 1; i < nd; i++) out[k++] = digits[i]; else out[k++] = '0';
    } else {
      out[k++] = '0'; out[k++] = '.';
      for (int i = 0; i < -ex - 1; i++) out[k++] = '0';
      for (int i = 0; i < nd; i++) out[k++] = digits[i];
    }
    out[k] = 0;
  } else {                                                          /* dạng mũ: d[.ddd]e±XX */
    out[k++] = digits[0];
    if (nd > 1) { out[k++] = '.'; for (int i = 1; i < nd; i++) out[k++] = digits[i]; }
    k += (size_t)snprintf(out + k, sizeof out - k, "e%c%02d", ex < 0 ? '-' : '+', ex < 0 ? -ex : ex);
  }
  c.put(out);
}

void py_string(const char *s, Cat &c) {                            /* json.dumps(ensure_ascii=True) */
  c.putc_('"');
  const unsigned char *p = (const unsigned char *)s;
  while (*p && c.ok) {
    unsigned ch = *p;
    char t[16];
    if (ch == '"') c.put("\\\"");
    else if (ch == '\\') c.put("\\\\");
    else if (ch == '\n') c.put("\\n");
    else if (ch == '\r') c.put("\\r");
    else if (ch == '\t') c.put("\\t");
    else if (ch == '\b') c.put("\\b");
    else if (ch == '\f') c.put("\\f");
    else if (ch < 0x20) { snprintf(t, sizeof t, "\\u%04x", ch); c.put(t); }
    else if (ch < 0x80) c.putc_((char)ch);
    else {                                                          /* UTF-8 -> \uXXXX (cặp thay thế cho > U+FFFF) */
      unsigned cp = 0; int extra = 0;
      if ((ch & 0xE0) == 0xC0) { cp = ch & 0x1F; extra = 1; }
      else if ((ch & 0xF0) == 0xE0) { cp = ch & 0x0F; extra = 2; }
      else if ((ch & 0xF8) == 0xF0) { cp = ch & 0x07; extra = 3; }
      else { c.ok = false; break; }
      for (int i = 0; i < extra; i++) { p++; if ((*p & 0xC0) != 0x80) { c.ok = false; break; } cp = (cp << 6) | (*p & 0x3F); }
      if (!c.ok) break;
      if (cp > 0xFFFF) { cp -= 0x10000; snprintf(t, sizeof t, "\\u%04x\\u%04x", 0xD800 + (cp >> 10), 0xDC00 + (cp & 0x3FF)); }
      else snprintf(t, sizeof t, "\\u%04x", cp);
      c.put(t);
    }
    p++;
  }
  c.putc_('"');
}

/* Bộ quét JSON PHẲNG chỉ để dựng chuỗi chuẩn tắc: lấy nguyên token số rồi strtod (chính xác tuyệt đối). Không dùng số thực của
 * ArduinoJson vì nó nhân với lũy thừa nhị phân của 0,1 nên có thể lệch 1 ulp ngay cả với "0.3" (khác repr của Python). JSON đã được
 * ArduinoJson kiểm cú pháp trước đó nên bộ quét này chỉ cần hiểu phần cú pháp phẳng; gặp mảng/đối tượng lồng -> từ chối. */
struct Entry { char key[40]; char kind; char str[96]; double num; long long ival; };   /* kind: s i f b n */

const char *skip_ws(const char *p, const char *e) { while (p < e && (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r')) p++; return p; }

/* Giải mã chuỗi JSON thành UTF-8 vào out (có NUL). Trả con trỏ sau dấu nháy đóng, hoặc nullptr. */
const char *scan_string(const char *p, const char *e, char *out, size_t cap) {
  if (p >= e || *p != '"') return nullptr;
  p++; size_t n = 0;
  auto put = [&](unsigned c) -> bool {
    char tmp[4]; size_t k;
    if (c < 0x80) { tmp[0] = (char)c; k = 1; }
    else if (c < 0x800) { tmp[0] = (char)(0xC0 | (c >> 6)); tmp[1] = (char)(0x80 | (c & 0x3F)); k = 2; }
    else if (c < 0x10000) { tmp[0] = (char)(0xE0 | (c >> 12)); tmp[1] = (char)(0x80 | ((c >> 6) & 0x3F)); tmp[2] = (char)(0x80 | (c & 0x3F)); k = 3; }
    else { tmp[0] = (char)(0xF0 | (c >> 18)); tmp[1] = (char)(0x80 | ((c >> 12) & 0x3F)); tmp[2] = (char)(0x80 | ((c >> 6) & 0x3F)); tmp[3] = (char)(0x80 | (c & 0x3F)); k = 4; }
    if (n + k + 1 > cap) return false;
    memcpy(out + n, tmp, k); n += k; return true;
  };
  while (p < e && *p != '"') {
    unsigned c = (unsigned char)*p++;
    bool esc = (c == '\\');
    if (esc) {
      if (p >= e) return nullptr;
      char x = *p++;
      if (x == 'n') c = '\n'; else if (x == 'r') c = '\r'; else if (x == 't') c = '\t'; else if (x == 'b') c = '\b'; else if (x == 'f') c = '\f';
      else if (x == '"' || x == '\\' || x == '/') c = (unsigned char)x;
      else if (x == 'u') {
        if (e - p < 4) return nullptr;
        unsigned cp = 0;
        for (int i = 0; i < 4; i++) { char h = *p++; cp <<= 4; if (h >= '0' && h <= '9') cp |= (unsigned)(h - '0'); else if (h >= 'a' && h <= 'f') cp |= (unsigned)(h - 'a' + 10); else if (h >= 'A' && h <= 'F') cp |= (unsigned)(h - 'A' + 10); else return nullptr; }
        if (cp >= 0xD800 && cp < 0xDC00) {                              /* cặp thay thế */
          if (e - p < 6 || p[0] != '\\' || p[1] != 'u') return nullptr;
          p += 2; unsigned lo = 0;
          for (int i = 0; i < 4; i++) { char h = *p++; lo <<= 4; if (h >= '0' && h <= '9') lo |= (unsigned)(h - '0'); else if (h >= 'a' && h <= 'f') lo |= (unsigned)(h - 'a' + 10); else if (h >= 'A' && h <= 'F') lo |= (unsigned)(h - 'A' + 10); else return nullptr; }
          cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
        }
        c = cp;
      } else return nullptr;
    }
    if (esc) { if (!put(c)) return nullptr; }                              /* escape -> code point -> UTF-8 */
    else { if (n + 2 > cap) return nullptr; out[n++] = (char)c; }          /* byte thô (kể cả UTF-8 nhiều byte): chép nguyên, KHÔNG mã hóa lại */
  }
  if (p >= e) return nullptr;
  out[n] = 0;
  return p + 1;
}

bool scan_flat_object(const char *text, size_t len, Entry *ent, int *count) {
  const char *p = text, *e = text + len;
  p = skip_ws(p, e);
  if (p >= e || *p != '{') return false;
  p = skip_ws(p + 1, e);
  int n = 0;
  if (p < e && *p == '}') { *count = 0; return true; }
  while (p < e) {
    if (n >= 24) return false;
    Entry &en = ent[n];
    memset(&en, 0, sizeof en);
    p = scan_string(skip_ws(p, e), e, en.key, sizeof en.key);
    if (!p) return false;
    p = skip_ws(p, e);
    if (p >= e || *p != ':') return false;
    p = skip_ws(p + 1, e);
    if (p >= e) return false;
    if (*p == '"') { en.kind = 's'; p = scan_string(p, e, en.str, sizeof en.str); if (!p) return false; }
    else if (!strncmp(p, "true", 4) && (size_t)(e - p) >= 4) { en.kind = 'b'; en.ival = 1; p += 4; }
    else if (!strncmp(p, "false", 5) && (size_t)(e - p) >= 5) { en.kind = 'b'; en.ival = 0; p += 5; }
    else if (!strncmp(p, "null", 4) && (size_t)(e - p) >= 4) { en.kind = 'n'; p += 4; }
    else if (*p == '-' || (*p >= '0' && *p <= '9')) {
      const char *q = p; bool isf = false;
      while (q < e && (*q == '-' || *q == '+' || *q == '.' || *q == 'e' || *q == 'E' || (*q >= '0' && *q <= '9'))) { if (*q == '.' || *q == 'e' || *q == 'E') isf = true; q++; }
      char tok[48]; size_t tl = (size_t)(q - p);
      if (tl == 0 || tl >= sizeof tok) return false;
      memcpy(tok, p, tl); tok[tl] = 0;
      if (isf) { en.kind = 'f'; en.num = strtod(tok, nullptr); }
      else {
        if (tl > 18) return false;                                     /* ngoài phạm vi int64 an toàn: không hỗ trợ */
        en.kind = 'i'; en.ival = strtoll(tok, nullptr, 10);
      }
      p = q;
    } else return false;                                                /* mảng/đối tượng lồng */
    n++;
    p = skip_ws(p, e);
    if (p < e && *p == ',') { p++; continue; }
    if (p < e && *p == '}') { *count = n; return true; }
    return false;
  }
  return false;
}

bool canonical_crc_text(const char *payload, size_t len, uint16_t *crc) {
  Entry ent[24]; int n = 0;
  if (!scan_flat_object(payload, len, ent, &n)) return false;
  int idx[24]; int m = 0;
  for (int i = 0; i < n; i++) if (strcmp(ent[i].key, "crc") != 0) idx[m++] = i;
  for (int i = 1; i < m; i++) { int k = idx[i], j = i - 1; while (j >= 0 && strcmp(ent[idx[j]].key, ent[k].key) > 0) { idx[j + 1] = idx[j]; j--; } idx[j + 1] = k; }
  Cat c; c.putc_('{');
  for (int i = 0; i < m; i++) {
    const Entry &en = ent[idx[i]];
    if (i) c.putc_(',');
    py_string(en.key, c); c.putc_(':');
    if (en.kind == 's') py_string(en.str, c);
    else if (en.kind == 'b') c.put(en.ival ? "true" : "false");
    else if (en.kind == 'n') c.put("null");
    else if (en.kind == 'i') { char t[24]; snprintf(t, sizeof t, "%lld", en.ival); c.put(t); }
    else py_float(en.num, c);
    if (!c.ok) return false;
  }
  c.putc_('}');
  if (!c.ok) return false;
  *crc = svmg_crc16_ccitt(c.buf, c.n);
  return true;
}
}  // namespace

bool msg_config_canonical_crc(const char *payload, size_t len, uint16_t *crc) {
  return canonical_crc_text(payload, len, crc);
}

bool msg_parse_config(const char *payload, size_t len, svmg_config_patch_t *o) {
  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, payload, len) != DeserializationError::Ok) return false;
  if (!doc.is<JsonObject>()) return false;
  memset(o, 0, sizeof *o);
  uint32_t u; float f;
  if (get_uint(doc["config_version"], &u) != 1) return false;
  o->config_version = u;
  /* Trường có mặt mà sai kiểu/ngoài miền kiểu dữ liệu -> bản tin hỏng (REJECTED/BAD_PARAM); ngoài BIÊN an toàn do svmg_config_validate xét. */
  if (!doc["profile"].isNull()) {
    int p = svmg_profile_from_str(doc["profile"] | (const char *)nullptr);
    if (p < 0) return false;
    o->has |= SVMG_CFGP_PROFILE; o->profile = (uint8_t)p;
  }
  if (!doc["debounce_n"].isNull()) { if (get_uint(doc["debounce_n"], &u) != 1) return false; o->has |= SVMG_CFGP_DEBOUNCE; o->debounce_n = clamp8(u); }
  if (!doc["mai_caution"].isNull()) { if (get_uint(doc["mai_caution"], &u) != 1) return false; o->has |= SVMG_CFGP_MAI; o->mai_caution = clamp8(u); }
  if (!doc["report_interval_s"].isNull()) { if (get_uint(doc["report_interval_s"], &u) != 1) return false; o->has |= SVMG_CFGP_REPORT; o->report_interval_s = clamp16(u); }
  if (!doc["phi_hard_deg"].isNull()) { if (get_float(doc["phi_hard_deg"], &f) != 1) return false; o->has |= SVMG_CFGP_PHI; o->phi_hard_deg = f; }
  if (!doc["primary_model"].isNull()) {
    int m = svmg_model_from_str(doc["primary_model"] | (const char *)nullptr);
    if (m < 0) return false;
    o->has |= SVMG_CFGP_MODEL; o->primary_model = (uint8_t)m;
  }
  o->crc_state = SVMG_CRC_ABSENT;
  if (!doc["crc"].isNull()) {
    const char *c = doc["crc"] | (const char *)nullptr;
    char *end = nullptr; unsigned long cv = 0;
    bool fmt = c && strlen(c) == 4;
    if (fmt) { cv = strtoul(c, &end, 16); fmt = end && !*end; }
    uint16_t calc = 0;
    o->crc_state = (fmt && canonical_crc_text(payload, len, &calc) && calc == (uint16_t)cv) ? SVMG_CRC_OK : SVMG_CRC_BAD;
  }
  return true;
}
#endif  // SVMG_MSG_NO_PARSE
