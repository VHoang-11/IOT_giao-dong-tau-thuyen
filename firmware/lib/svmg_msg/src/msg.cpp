/* msg.cpp - xem msg.h. */
#include "msg.h"
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

size_t msg_alarm_id_str(char *buf, size_t cap, uint32_t id) {
  int r = snprintf(buf, cap, "A-%04lu", (unsigned long)id);
  return (r < 0 || (size_t)r >= cap) ? 0 : (size_t)r;
}

/* ---------------- build ---------------- */
size_t msg_build_telemetry(char *buf, size_t cap, const MsgIdent &id, uint32_t seq, const MsgTelemetry &t) {
  W w(buf, cap);
  head(w, id, seq);
  w.raw(",\"t_sim_s\":"); w.num(t.t_sim_s, 1);
  w.fmt(",\"uptime_ms\":%lu,\"timewarp\":%u", (unsigned long)t.uptime_ms, (unsigned)t.timewarp);
  w.raw(",\"source_mode\":"); w.str(src_name(t.source_mode));
  w.fmt(",\"synthetic\":%s", t.source_mode == SVMG_SRC_SIMULATION ? "true" : "false");
  w.raw(",\"scenario_id\":");
  if (t.scenario >= 0) w.str(svmg_scenario_name((uint8_t)t.scenario)); else w.raw("null");
  w.raw(",\"roll_deg\":"); w.num(t.roll_deg, 2);
  w.raw(",\"pitch_deg\":"); w.num(t.pitch_deg, 2);
  w.raw(",\"rms_roll_deg\":"); w.num(t.rms_roll_deg, 2);
  w.raw(",\"heel_offset_deg\":"); w.num(t.heel_offset_deg, 2);
  w.raw(",\"trend_rms_deg_per_min\":"); w.num(t.trend_rms_deg_per_min, 2);
  w.raw(",\"class_rf\":"); w.str(svmg_class_name((svmg_class_t)t.cls_rf));
  w.raw(",\"class_baseline_b\":"); w.str(svmg_class_name((svmg_class_t)t.cls_b));
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

size_t msg_build_event(char *buf, size_t cap, const MsgIdent &id, const svmg_event_t &e) {
  W w(buf, cap);
  head(w, id, e.seq);
  char aid[16]; msg_alarm_id_str(aid, sizeof aid, e.alarm_id);
  switch (e.type) {
    case SVMG_EV_ALARM_STATE:
      w.raw(",\"type\":\"ALARM_STATE\",\"alarm_id\":"); if (e.alarm_id) w.str(aid); else w.raw("null");
      w.raw(",\"level\":"); w.str(svmg_level_name((svmg_level_t)e.level));
      w.raw(",\"prev_level\":"); w.str(svmg_level_name((svmg_level_t)e.prev_level));
      w.raw(",\"class\":"); w.str(svmg_class_name((svmg_class_t)e.cls));
      w.raw(",\"t_sim_s\":"); w.num(e.t_sim_s, 1);
      w.raw(",\"acked_by\":null");
      break;
    case SVMG_EV_ALARM_ACK:
      w.raw(",\"type\":\"ALARM_ACK\",\"alarm_id\":"); if (e.alarm_id) w.str(aid); else w.raw("null");
      w.raw(",\"level\":"); w.str(svmg_level_name((svmg_level_t)e.level));
      w.raw(",\"t_sim_s\":"); w.num(e.t_sim_s, 1);
      w.raw(",\"acked_by\":"); w.str(e.acked_by == SVMG_ACKBY_BUTTON ? "device_button" : "remote");
      break;
    case SVMG_EV_ALARM_MUTE:
      w.raw(",\"type\":\"ALARM_MUTE\",\"alarm_id\":"); if (e.alarm_id) w.str(aid); else w.raw("null");
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
  w.fmt(",\"config_version\":%lu,\"boot_id\":", (unsigned long)config_version); w.str(id.boot_id);
  w.raw("}");
  return w.done();
}

size_t msg_build_status_offline(char *buf, size_t cap) {
  W w(buf, cap); w.raw("{\"state\":\"offline\"}"); return w.done();
}

size_t msg_build_health(char *buf, size_t cap, const MsgIdent &id, uint32_t seq, const MsgHealth &h) {
  W w(buf, cap);
  head(w, id, seq);
  w.fmt(",\"uptime_ms\":%lu,\"heap_free\":%lu,\"heap_min\":%lu,\"rssi\":%d", (unsigned long)h.uptime_ms,
        (unsigned long)h.heap_free, (unsigned long)h.heap_min, h.rssi);
  w.fmt(",\"reconnects\":%lu,\"i2c_errors\":%lu,\"samples_invalid\":%lu,\"gaps\":%lu,\"loop_overruns\":%lu",
        (unsigned long)h.reconnects, (unsigned long)h.i2c_errors, (unsigned long)h.samples_invalid,
        (unsigned long)h.gaps, (unsigned long)h.loop_overruns);
  w.fmt(",\"inference_us_avg\":%lu,\"inference_us_max\":%lu", (unsigned long)h.infer_us_avg, (unsigned long)h.infer_us_max);
  w.fmt(",\"evbuf_depth\":%lu,\"evbuf_dropped\":%lu,\"cmd_exec\":%lu,\"cmd_rejected\":%lu,\"rx_dropped\":%lu",
        (unsigned long)h.evbuf_depth, (unsigned long)h.evbuf_dropped, (unsigned long)h.cmd_exec,
        (unsigned long)h.cmd_rejected, (unsigned long)h.rx_dropped);
  w.fmt(",\"sensor_ok\":%s}", h.sensor_ok ? "true" : "false");
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

size_t msg_build_trace(char *buf, size_t cap, const MsgIdent &id, uint32_t seq, float t_end_s, uint16_t window_s,
                       int chunk, int chunks, const int16_t *r, const int16_t *p, int n) {
  W w(buf, cap);
  head(w, id, seq);
  w.raw(",\"t_end_s\":"); w.num(t_end_s, 1);
  w.fmt(",\"window_s\":%u,\"fs_hz\":2,\"chunk\":%d,\"chunks\":%d,\"roll_cdeg\":[", (unsigned)window_s, chunk, chunks);
  for (int i = 0; i < n; i++) w.fmt(i ? ",%d" : "%d", (int)r[i]);
  w.raw("],\"pitch_cdeg\":[");
  for (int i = 0; i < n; i++) w.fmt(i ? ",%d" : "%d", (int)p[i]);
  w.raw("]}");
  return w.done();
}

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
/* chuỗi enum -> chỉ số, hoặc 0xFF nếu sai */
template <typename F> uint8_t get_enum(JsonVariantConst v, F from_str) {
  if (!v.is<const char *>()) return 0xFF;
  int r = from_str(v.as<const char *>());
  return r < 0 ? 0xFF : (uint8_t)r;
}
uint8_t clamp8(uint32_t v) { return v > 254 ? 0xFE : (uint8_t)v; }   /* 0xFE: ngoài miền mọi tham số của lệnh -> BAD_PARAM */
uint16_t clamp16(uint32_t v) { return v > 65534 ? 0xFFFE : (uint16_t)v; }
int mode_from_str(const char *s) { return !s ? -1 : !strcmp(s, "SENSOR") ? 0 : !strcmp(s, "SIMULATION") ? 1 : -1; }
}  // namespace

bool msg_parse_cmd(const char *payload, size_t len, svmg_cmd_t *o) {
  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, payload, len) != DeserializationError::Ok) return false;
  memset(o, 0, sizeof *o);
  const char *id = doc["cmd_id"] | (const char *)nullptr;
  if (!id || !id[0] || strlen(id) >= SVMG_CMD_ID_LEN) return false;
  strncpy(o->cmd_id, id, SVMG_CMD_ID_LEN - 1);
  const char *by = doc["issued_by"] | "";
  strncpy(o->issued_by, by, SVMG_CMD_ISSUER_LEN - 1);

  uint32_t u;
  o->ttl_s = (get_uint(doc["ttl_s"], &u) == 1) ? clamp16(u) : 0;
  if (get_uint(doc["age_s"], &u) == 1) o->age_s = clamp16(u);

  const char *name = doc["cmd"] | "";
  JsonVariantConst p = doc["params"];
  struct { const char *n; svmg_cmd_type_t t; } map[] = {
    {"ack", SVMG_CMD_ACK}, {"mute", SVMG_CMD_MUTE}, {"set_profile", SVMG_CMD_SET_PROFILE},
    {"calibrate_zero", SVMG_CMD_CALIBRATE_ZERO}, {"set_scenario", SVMG_CMD_SET_SCENARIO}, {"set_mode", SVMG_CMD_SET_MODE},
    {"set_timewarp", SVMG_CMD_SET_TIMEWARP}, {"request_snapshot", SVMG_CMD_REQUEST_SNAPSHOT}, {"set_model", SVMG_CMD_SET_MODEL}};
  o->type = SVMG_CMD_NONE;
  for (auto &m : map) if (!strcmp(name, m.n)) o->type = (uint8_t)m.t;

  int r;
  if ((r = get_uint(p["duration_s"], &u)) >= 0) { o->has |= SVMG_CP_DURATION; o->duration_s = clamp16(u); }
  if ((r = get_uint(p["window_s"], &u)) >= 0)   { o->has |= SVMG_CP_WINDOW; o->window_s = clamp16(u); }
  if ((r = get_uint(p["sea_state"], &u)) >= 0)  { o->has |= SVMG_CP_SEA; o->sea_state = clamp8(u); }
  if ((r = get_uint(p["timewarp"], &u)) >= 0)   { o->has |= SVMG_CP_TIMEWARP; o->timewarp = clamp8(u); }
  if (!p["profile"].isNull())  { o->has |= SVMG_CP_PROFILE;  o->profile = get_enum(p["profile"], svmg_profile_from_str); }
  if (!p["scenario"].isNull()) { o->has |= SVMG_CP_SCENARIO; o->scenario = get_enum(p["scenario"], svmg_scenario_from_str); }
  if (!p["mode"].isNull())     { o->has |= SVMG_CP_MODE;     o->mode = get_enum(p["mode"], mode_from_str); }
  if (!p["model"].isNull())    { o->has |= SVMG_CP_MODEL;    o->model = get_enum(p["model"], svmg_model_from_str); }
  if (!p["alarm_id"].isNull()) {
    o->has |= SVMG_CP_ALARM;
    if (p["alarm_id"].is<const char *>()) {
      const char *s = p["alarm_id"].as<const char *>();
      o->alarm_id = (s && s[0] == 'A' && s[1] == '-') ? (uint32_t)strtoul(s + 2, nullptr, 10) : 0;
    } else if (get_uint(p["alarm_id"], &u) == 1) o->alarm_id = u;
  }
  return true;
}

bool msg_parse_config(const char *payload, size_t len, svmg_config_t *o, uint16_t *crc) {
  StaticJsonDocument<384> doc;
  if (deserializeJson(doc, payload, len) != DeserializationError::Ok) return false;
  memset(o, 0, sizeof *o);
  uint32_t u;
  if (get_uint(doc["config_version"], &u) != 1) return false;
  o->config_version = u;
  int p = svmg_profile_from_str(doc["profile"] | (const char *)nullptr);
  if (p < 0) return false;
  o->profile = (uint8_t)p;
  if (get_uint(doc["debounce_n"], &u) != 1) return false;
  o->debounce_n = clamp8(u);
  if (get_uint(doc["phi_hard_deg"], &u) != 1) return false;
  o->phi_hard_deg = clamp8(u);
  if (get_uint(doc["mai_caution"], &u) != 1) return false;
  o->mai_caution = clamp8(u);
  if (get_uint(doc["report_interval_s"], &u) != 1) return false;
  o->report_interval_s = clamp8(u);
  int m = svmg_model_from_str(doc["primary_model"] | (const char *)nullptr);
  if (m < 0) return false;
  o->primary_model = (uint8_t)m;
  const char *c = doc["crc"] | (const char *)nullptr;
  if (!c || strlen(c) != 4) return false;
  char *end = nullptr; unsigned long cv = strtoul(c, &end, 16);
  if (!end || *end) return false;
  *crc = (uint16_t)cv;
  return true;
}
#endif  // SVMG_MSG_NO_PARSE
