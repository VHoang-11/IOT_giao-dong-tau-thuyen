// Test bản tin MQTT: khớp Phụ lục A đề cương v2.0, chặn tràn, thoát ký tự, phân tích lệnh/cấu hình, chống dữ liệu hỏng.
#include <unity.h>
#include <ArduinoJson.h>
#include <string.h>
#include <stdio.h>
#include "msg.h"

void setUp(void) {}
void tearDown(void) {}

static MsgIdent ID() {
  MsgIdent i; memset(&i, 0, sizeof i);
  i.device_id = "vessel-demo-01"; i.fw = "1.0.0"; i.model_version = "rf_v1"; strcpy(i.boot_id, "a3f9c0de");
  return i;
}
static MsgTelemetry TEL() {
  MsgTelemetry t; memset(&t, 0, sizeof t);
  t.t_sim_s = 625.0f; t.uptime_ms = 62500; t.timewarp = 10; t.source_mode = SVMG_SRC_SIMULATION; t.scenario = 4;
  t.roll_deg = 8.4f; t.pitch_deg = 1.2f; t.rms_roll_deg = 5.6f; t.heel_offset_deg = 0.4f; t.trend_rms_deg_per_min = 1.1f;
  t.cls_rf = SVMG_AMPLITUDE_GROWTH; t.cls_b = SVMG_AMPLITUDE_GROWTH; t.mai = 64; t.alarm_level = SVMG_LVL_WARNING;
  t.config_version = 7; t.sensor_ok = true;
  return t;
}
static StaticJsonDocument<1024> D;
static void parse(const char *s) { DeserializationError e = deserializeJson(D, s); TEST_ASSERT_TRUE_MESSAGE(e == DeserializationError::Ok, s); }

void test_telemetry_matches_appendix_A1(void) {
  char b[512]; size_t n = msg_build_telemetry(b, sizeof b, ID(), 125, TEL());
  TEST_ASSERT_TRUE(n > 0); TEST_ASSERT_EQUAL_UINT(strlen(b), n);
  parse(b);
  TEST_ASSERT_EQUAL_STRING("vessel-demo-01", D["device_id"]); TEST_ASSERT_EQUAL_STRING("a3f9c0de", D["boot_id"]);
  TEST_ASSERT_EQUAL_INT(125, D["seq"]);
  TEST_ASSERT_EQUAL_FLOAT(625.0f, D["t_sim_s"]); TEST_ASSERT_EQUAL_INT(62500, D["uptime_ms"]); TEST_ASSERT_EQUAL_INT(10, D["timewarp"]);
  TEST_ASSERT_EQUAL_STRING("SIMULATION", D["source_mode"]); TEST_ASSERT_TRUE(D["synthetic"].as<bool>());
  TEST_ASSERT_EQUAL_STRING("S3", D["scenario_id"]);
  TEST_ASSERT_EQUAL_FLOAT(8.4f, D["roll_deg"]); TEST_ASSERT_EQUAL_FLOAT(1.2f, D["pitch_deg"]);
  TEST_ASSERT_EQUAL_FLOAT(5.6f, D["rms_roll_deg"]); TEST_ASSERT_EQUAL_FLOAT(0.4f, D["heel_offset_deg"]);
  TEST_ASSERT_EQUAL_FLOAT(1.1f, D["trend_rms_deg_per_min"]);
  TEST_ASSERT_EQUAL_STRING("AMPLITUDE_GROWTH", D["class_rf"]); TEST_ASSERT_EQUAL_STRING("AMPLITUDE_GROWTH", D["class_baseline_b"]);
  TEST_ASSERT_EQUAL_INT(64, D["mai"]); TEST_ASSERT_EQUAL_STRING("WARNING", D["alarm_level"]);
  TEST_ASSERT_EQUAL_STRING("rf_v1", D["model_version"]); TEST_ASSERT_EQUAL_INT(7, D["config_version"]); TEST_ASSERT_TRUE(D["sensor_ok"].as<bool>());
  TEST_ASSERT_EQUAL_UINT_MESSAGE(21, D.size(), "đúng 21 trường: Phụ lục A.1 trừ voyage_id (do backend gắn), không trường lạ");
}
void test_telemetry_sensor_mode_and_nan(void) {
  MsgTelemetry t = TEL(); t.source_mode = SVMG_SRC_SENSOR; t.scenario = -1; t.roll_deg = NAN;
  char b[512]; msg_build_telemetry(b, sizeof b, ID(), 1, t); parse(b);
  TEST_ASSERT_FALSE(D["synthetic"].as<bool>()); TEST_ASSERT_TRUE(D["scenario_id"].isNull()); TEST_ASSERT_TRUE(D["roll_deg"].isNull());
  TEST_ASSERT_EQUAL_STRING("SENSOR", D["source_mode"]);
}
void test_telemetry_unknown_and_fault_classes_are_explicit(void) {
  MsgTelemetry t = TEL(); t.cls_rf = SVMG_UNKNOWN; t.cls_b = SVMG_FAULT; char b[512]; msg_build_telemetry(b, sizeof b, ID(), 1, t); parse(b);
  TEST_ASSERT_EQUAL_STRING("UNKNOWN", D["class_rf"]); TEST_ASSERT_EQUAL_STRING("FAULT", D["class_baseline_b"]);
}
void test_worst_case_telemetry_size_budget(void) {
  MsgTelemetry t = TEL(); t.t_sim_s = 99999.9f; t.uptime_ms = 4294967295u; t.roll_deg = -179.99f; t.pitch_deg = -179.99f;
  t.rms_roll_deg = 179.99f; t.cls_rf = SVMG_PERSISTENT_OFFSET; t.cls_b = SVMG_PERSISTENT_OFFSET; t.config_version = 4294967295u;
  MsgIdent id = ID(); id.model_version = "rf_v1234567";
  char b[512]; size_t n = msg_build_telemetry(b, sizeof b, id, 4294967295u, t);
  char m[64]; snprintf(m, sizeof m, "worst-case telemetry length = %u bytes", (unsigned)n); TEST_MESSAGE(m);
  TEST_ASSERT_TRUE(n > 0 && n < 480);
}
void test_event_alarm_state_matches_appendix_A2(void) {
  svmg_event_t e; memset(&e, 0, sizeof e);
  e.seq = 126; e.type = SVMG_EV_ALARM_STATE; e.alarm_id = 42; e.level = SVMG_LVL_WARNING; e.prev_level = SVMG_LVL_CAUTION;
  e.cls = SVMG_AMPLITUDE_GROWTH; e.t_sim_s = 625.0f;
  char b[400]; size_t n = msg_build_event(b, sizeof b, ID(), e); TEST_ASSERT_TRUE(n > 0); parse(b);
  TEST_ASSERT_EQUAL_INT(126, D["seq"]); TEST_ASSERT_EQUAL_STRING("ALARM_STATE", D["type"]); TEST_ASSERT_EQUAL_STRING("A-0042", D["alarm_id"]);
  TEST_ASSERT_EQUAL_STRING("WARNING", D["level"]); TEST_ASSERT_EQUAL_STRING("CAUTION", D["prev_level"]);
  TEST_ASSERT_EQUAL_STRING("AMPLITUDE_GROWTH", D["class"]); TEST_ASSERT_EQUAL_FLOAT(625.0f, D["t_sim_s"]); TEST_ASSERT_TRUE(D["acked_by"].isNull());
  TEST_ASSERT_EQUAL_UINT(10, D.size());
  e.alarm_id = 0; msg_build_event(b, sizeof b, ID(), e); parse(b); TEST_ASSERT_TRUE(D["alarm_id"].isNull());   // CAUTION chưa có alarm_id
}
void test_event_other_types_are_valid_json(void) {
  svmg_event_t e; char b[400];
  struct { uint8_t type; uint8_t aux; uint16_t val; const char *name; } cases[] = {
    {SVMG_EV_ALARM_ACK, 0, 0, "ALARM_ACK"}, {SVMG_EV_ALARM_MUTE, 0, 120, "ALARM_MUTE"}, {SVMG_EV_MODE_CHANGE, SVMG_SRC_SIMULATION, 0, "MODE_CHANGE"},
    {SVMG_EV_SCENARIO_CHANGE, 4, 3, "SCENARIO_CHANGE"}, {SVMG_EV_FAULT, 0, 5, "FAULT"}, {SVMG_EV_FAULT_CLEARED, 0, 0, "FAULT_CLEARED"},
    {SVMG_EV_CONFIG_APPLIED, 0, 0, "CONFIG_APPLIED"}, {SVMG_EV_CALIBRATION, 0, SVMG_R_NOT_STATIC, "CALIBRATION"}, {SVMG_EV_BOOT, 0, 1, "BOOT"}};
  for (auto &c : cases) {
    memset(&e, 0, sizeof e); e.seq = 7; e.type = c.type; e.aux = c.aux; e.val = c.val; e.alarm_id = 9; e.acked_by = SVMG_ACKBY_BUTTON;
    TEST_ASSERT_TRUE_MESSAGE(msg_build_event(b, sizeof b, ID(), e) > 0, c.name); parse(b);
    TEST_ASSERT_EQUAL_STRING(c.name, D["type"]); TEST_ASSERT_EQUAL_INT(7, D["seq"]); TEST_ASSERT_EQUAL_STRING("a3f9c0de", D["boot_id"]);
  }
  memset(&e, 0, sizeof e); e.type = SVMG_EV_ALARM_ACK; e.acked_by = SVMG_ACKBY_REMOTE; e.alarm_id = 3; msg_build_event(b, sizeof b, ID(), e); parse(b);
  TEST_ASSERT_EQUAL_STRING("remote", D["acked_by"]);
  memset(&e, 0, sizeof e); e.type = SVMG_EV_CONFIG_APPLIED; e.alarm_id = 11; msg_build_event(b, sizeof b, ID(), e); parse(b);
  TEST_ASSERT_EQUAL_INT(11, D["config_version"]);
  memset(&e, 0, sizeof e); e.type = 99; TEST_ASSERT_EQUAL_UINT(0, msg_build_event(b, sizeof b, ID(), e));   // loại lạ -> không phát
}
void test_status_and_last_will_exact(void) {
  MsgIdent id = ID(); strcpy(id.boot_id, "a3f9");
  char b[200]; msg_build_status_online(b, sizeof b, id, 8);
  TEST_ASSERT_EQUAL_STRING("{\"state\":\"online\",\"fw\":\"1.0.0\",\"model_version\":\"rf_v1\",\"config_version\":8,\"boot_id\":\"a3f9\"}", b);
  msg_build_status_offline(b, sizeof b);
  TEST_ASSERT_EQUAL_STRING("{\"state\":\"offline\"}", b);
}
void test_cmd_ack_matches_appendix_A3(void) {
  svmg_cmd_ack_t a; memset(&a, 0, sizeof a); strcpy(a.cmd_id, "c-7f21"); a.applied = 1; a.config_version = 8;
  char b[200]; msg_build_cmd_ack(b, sizeof b, a, nullptr, nullptr);
  TEST_ASSERT_EQUAL_STRING("{\"cmd_id\":\"c-7f21\",\"result\":\"APPLIED\",\"config_version\":8,\"reason\":null}", b);
  memset(&a, 0, sizeof a); strcpy(a.cmd_id, "c-7f22"); a.applied = 0; a.reason = SVMG_R_FORBIDDEN_STATE; a.config_version = 8;
  msg_build_cmd_ack(b, sizeof b, a, nullptr, nullptr); parse(b);
  TEST_ASSERT_EQUAL_STRING("REJECTED", D["result"]); TEST_ASSERT_EQUAL_STRING("FORBIDDEN_STATE", D["reason"]);
  float zr = 3.0f, zp = -0.5f; a.applied = 1; a.reason = SVMG_R_OK; strcpy(a.cmd_id, "cal");
  msg_build_cmd_ack(b, sizeof b, a, &zr, &zp); parse(b);
  TEST_ASSERT_EQUAL_FLOAT(3.0f, D["zero_roll_deg"]); TEST_ASSERT_EQUAL_FLOAT(-0.5f, D["zero_pitch_deg"]);
}
void test_json_escaping_of_hostile_cmd_id(void) {
  svmg_cmd_ack_t a; memset(&a, 0, sizeof a); strcpy(a.cmd_id, "x\"},\"evil\":{\"y\\\n"); a.applied = 1;
  char b[200]; size_t n = msg_build_cmd_ack(b, sizeof b, a, nullptr, nullptr); TEST_ASSERT_TRUE(n > 0); parse(b);
  TEST_ASSERT_TRUE(D["evil"].isNull());                                         // không bị chèn trường
  TEST_ASSERT_EQUAL_STRING(a.cmd_id, D["cmd_id"]);
}
void test_buffer_overflow_is_refused_not_corrupting(void) {
  for (size_t cap = 1; cap < 330; cap += 7) {
    char guard[400]; memset(guard, 0x5A, sizeof guard);
    size_t n = msg_build_telemetry(guard, cap, ID(), 1, TEL());
    for (size_t i = cap; i < sizeof guard; i++) TEST_ASSERT_EQUAL_UINT8_MESSAGE(0x5A, (uint8_t)guard[i], "ghi vượt bộ đệm");
    if (n) TEST_ASSERT_TRUE(n < cap);
  }
  char tiny[4]; TEST_ASSERT_EQUAL_UINT(0, msg_build_status_offline(tiny, sizeof tiny));
  TEST_ASSERT_EQUAL_UINT(0, msg_build_status_offline(tiny, 0));
}
void test_health_and_trace_are_valid_json(void) {
  MsgHealth h; memset(&h, 0, sizeof h); h.uptime_ms = 5000; h.heap_free = 200000; h.heap_min = 180000; h.rssi = -60; h.sensor_ok = true; h.evbuf_depth = 3;
  char b[600]; TEST_ASSERT_TRUE(msg_build_health(b, sizeof b, ID(), 9, h) > 0); parse(b);
  TEST_ASSERT_EQUAL_INT(-60, D["rssi"]); TEST_ASSERT_EQUAL_INT(3, D["evbuf_depth"]); TEST_ASSERT_TRUE(D["sensor_ok"].as<bool>());
  int16_t r[60], p[60]; for (int i = 0; i < 60; i++) { r[i] = (int16_t)(i * 10 - 300); p[i] = (int16_t)(-i); }
  static char big[1400]; TEST_ASSERT_TRUE(msg_build_trace(big, sizeof big, ID(), 10, 100.0f, 60, 1, 3, r, p, 60) > 0);
  static StaticJsonDocument<16384> T; DeserializationError er = deserializeJson(T, big); TEST_ASSERT_TRUE_MESSAGE(er == DeserializationError::Ok, er.c_str());
  TEST_ASSERT_EQUAL_UINT(60, T["roll_cdeg"].size()); TEST_ASSERT_EQUAL_INT(-300, T["roll_cdeg"][0]); TEST_ASSERT_EQUAL_INT(-59, T["pitch_cdeg"][59]);
  TEST_ASSERT_EQUAL_INT(3, T["chunks"]);
}

// ---------------- Phân tích lệnh ----------------
static svmg_reason_t ok_hook_ret;
static svmg_reason_t hk1(void *, uint32_t, int) { return ok_hook_ret; }
static svmg_reason_t hk2(void *, uint16_t) { return ok_hook_ret; }
static svmg_reason_t hk3(void *, uint8_t) { return ok_hook_ret; }
static svmg_reason_t hk4(void *) { return ok_hook_ret; }
static svmg_reason_t hk5(void *, uint8_t, int) { return ok_hook_ret; }
static uint32_t hkv(void *) { return 5; }
static svmg_cmd_hooks_t HK = { nullptr, hk1, hk2, hk3, hk4, hk5, hk3, hk3, hk2, hk3, hkv };
static svmg_reason_t run(const char *json) {
  svmg_cmd_t c; if (!msg_parse_cmd(json, strlen(json), &c)) return (svmg_reason_t)99;
  svmg_cmd_ctx_t ctx; svmg_cmd_init(&ctx); svmg_cmd_ack_t a; ok_hook_ret = SVMG_R_OK;
  if (!svmg_cmd_exec(&ctx, &HK, &c, 0, &a)) return (svmg_reason_t)98;
  return a.applied ? SVMG_R_OK : a.reason;
}
void test_parse_cmd_appendix_example(void) {
  const char *j = "{ \"cmd_id\": \"c-7f21\", \"cmd\": \"set_profile\", \"params\": { \"profile\": \"SENSITIVE\" }, \"ttl_s\": 30, \"issued_by\": \"sup01\" }";
  svmg_cmd_t c; TEST_ASSERT_TRUE(msg_parse_cmd(j, strlen(j), &c));
  TEST_ASSERT_EQUAL_STRING("c-7f21", c.cmd_id); TEST_ASSERT_EQUAL_UINT8(SVMG_CMD_SET_PROFILE, c.type); TEST_ASSERT_EQUAL_UINT8(SVMG_PROFILE_SENSITIVE, c.profile);
  TEST_ASSERT_EQUAL_UINT16(30, c.ttl_s); TEST_ASSERT_EQUAL_STRING("sup01", c.issued_by);
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run(j));
}
void test_parse_cmd_all_types(void) {
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run("{\"cmd_id\":\"a\",\"cmd\":\"ack\",\"params\":{\"alarm_id\":\"A-0042\"},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run("{\"cmd_id\":\"b\",\"cmd\":\"mute\",\"params\":{\"duration_s\":120},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run("{\"cmd_id\":\"c\",\"cmd\":\"calibrate_zero\",\"params\":{\"duration_s\":30},\"ttl_s\":60}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run("{\"cmd_id\":\"d\",\"cmd\":\"set_scenario\",\"params\":{\"scenario\":\"S3\",\"sea_state\":2},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run("{\"cmd_id\":\"e\",\"cmd\":\"set_mode\",\"params\":{\"mode\":\"SIMULATION\"},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run("{\"cmd_id\":\"f\",\"cmd\":\"set_timewarp\",\"params\":{\"timewarp\":10},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run("{\"cmd_id\":\"g\",\"cmd\":\"request_snapshot\",\"params\":{\"window_s\":180},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run("{\"cmd_id\":\"h\",\"cmd\":\"set_model\",\"params\":{\"model\":\"BASELINE_B\"},\"ttl_s\":30}"));
}
void test_parse_cmd_bad_params_become_bad_param_not_silent(void) {
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"a\",\"cmd\":\"mute\",\"params\":{\"duration_s\":\"abc\"},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"b\",\"cmd\":\"mute\",\"params\":{\"duration_s\":-5},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"c\",\"cmd\":\"mute\",\"params\":{\"duration_s\":999999},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"d\",\"cmd\":\"mute\",\"params\":{\"duration_s\":1.5},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"e\",\"cmd\":\"set_profile\",\"params\":{\"profile\":\"WILD\"},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"f\",\"cmd\":\"set_profile\",\"params\":{\"profile\":7},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"g\",\"cmd\":\"set_profile\",\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"h\",\"cmd\":\"set_timewarp\",\"params\":{\"timewarp\":3},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"i\",\"cmd\":\"set_scenario\",\"params\":{\"scenario\":\"S3\",\"sea_state\":9},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"j\",\"cmd\":\"calibrate_zero\",\"params\":{\"duration_s\":5},\"ttl_s\":60}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"k\",\"cmd\":\"mute\",\"params\":{\"duration_s\":60}}"));          // thiếu ttl_s
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"l\",\"cmd\":\"mute\",\"params\":{\"duration_s\":60},\"ttl_s\":0}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_UNSUPPORTED, run("{\"cmd_id\":\"m\",\"cmd\":\"disable_alarm\",\"params\":{},\"ttl_s\":30}"));       // không có lệnh tắt cảnh báo
  TEST_ASSERT_EQUAL_INT(SVMG_R_UNSUPPORTED, run("{\"cmd_id\":\"n\",\"cmd\":\"set_phi_hard\",\"params\":{\"phi\":90},\"ttl_s\":30}"));
}
void test_parse_cmd_rejects_garbage(void) {
  svmg_cmd_t c;
  const char *bad[] = { "", "{", "null", "[]", "42", "{\"cmd\":\"ack\",\"ttl_s\":30}", "{\"cmd_id\":\"\",\"cmd\":\"ack\"}", "{\"cmd_id\":5}",
                        "{\"cmd_id\":\"this-cmd-id-is-way-too-long-for-the-fixed-buffer\",\"cmd\":\"ack\",\"ttl_s\":30}" };
  for (auto s : bad) TEST_ASSERT_FALSE_MESSAGE(msg_parse_cmd(s, strlen(s), &c), s);
}
void test_parse_cmd_fuzz_does_not_crash(void) {
  const char *seed = "{\"cmd_id\":\"c-7f21\",\"cmd\":\"set_scenario\",\"params\":{\"scenario\":\"S3\",\"sea_state\":2},\"ttl_s\":30,\"issued_by\":\"sup01\"}";
  uint32_t r = 12345; int accepted = 0;
  for (int i = 0; i < 4000; i++) {
    char m[160]; size_t n = strlen(seed); memcpy(m, seed, n + 1);
    int k = 1 + (int)(r % 4);
    for (int j = 0; j < k; j++) { r = r * 1664525u + 1013904223u; size_t pos = (r >> 8) % n; r = r * 1664525u + 1013904223u; m[pos] = (char)(r >> 16); }
    r = r * 1664525u + 1013904223u; if ((r >> 20) % 7 == 0) m[(r >> 8) % n] = 0;
    svmg_cmd_t c; if (msg_parse_cmd(m, strlen(m), &c)) { accepted++; svmg_cmd_ctx_t ctx; svmg_cmd_init(&ctx); svmg_cmd_ack_t a; ok_hook_ret = SVMG_R_OK; svmg_cmd_exec(&ctx, &HK, &c, 0, &a); }
  }
  TEST_ASSERT_TRUE(accepted > 0);
}

// ---------------- Phân tích cấu hình ----------------
void test_parse_config_appendix_example_and_crc_semantics(void) {
  const char *j = "{ \"config_version\": 8, \"profile\": \"SENSITIVE\", \"debounce_n\": 2, \"phi_hard_deg\": 20, \"mai_caution\": 70, \"report_interval_s\": 5, \"primary_model\": \"RF\", \"crc\": \"498b\" }";
  svmg_config_t c; uint16_t crc;
  TEST_ASSERT_TRUE(msg_parse_config(j, strlen(j), &c, &crc));
  TEST_ASSERT_EQUAL_UINT32(8, c.config_version); TEST_ASSERT_EQUAL_UINT8(2, c.debounce_n); TEST_ASSERT_EQUAL_UINT8(20, c.phi_hard_deg);
  TEST_ASSERT_EQUAL_HEX16(0x498B, crc); TEST_ASSERT_EQUAL_HEX16(0x498B, svmg_config_crc(&c));
  svmg_config_t cur; svmg_config_default(&cur, SVMG_MODEL_RF); svmg_reason_t r;
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_APPLY, svmg_config_check_update(&cur, &c, crc, &r));
  /* CRC minh họa "9c1e" trong đề cương không khớp chuỗi chuẩn tắc nào -> bị từ chối (đưa vào danh sách đề xuất) */
  const char *j2 = "{\"config_version\":8,\"profile\":\"SENSITIVE\",\"debounce_n\":2,\"phi_hard_deg\":20,\"mai_caution\":70,\"report_interval_s\":5,\"primary_model\":\"RF\",\"crc\":\"9c1e\"}";
  TEST_ASSERT_TRUE(msg_parse_config(j2, strlen(j2), &c, &crc));
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_REJECT, svmg_config_check_update(&cur, &c, crc, &r));
}
void test_parse_config_rejects_malformed(void) {
  svmg_config_t c; uint16_t crc;
  const char *bad[] = {
    "{}", "{\"config_version\":8}",
    "{\"config_version\":8,\"profile\":\"SENSITIVE\",\"debounce_n\":2,\"phi_hard_deg\":20.5,\"mai_caution\":70,\"report_interval_s\":5,\"primary_model\":\"RF\",\"crc\":\"498b\"}",
    "{\"config_version\":8,\"profile\":\"SENSITIVE\",\"debounce_n\":2,\"phi_hard_deg\":20,\"mai_caution\":70,\"report_interval_s\":5,\"primary_model\":\"RF\",\"crc\":\"zzzz\"}",
    "{\"config_version\":8,\"profile\":\"SENSITIVE\",\"debounce_n\":2,\"phi_hard_deg\":20,\"mai_caution\":70,\"report_interval_s\":5,\"primary_model\":\"RF\"}",
    "{\"config_version\":8,\"profile\":\"XYZ\",\"debounce_n\":2,\"phi_hard_deg\":20,\"mai_caution\":70,\"report_interval_s\":5,\"primary_model\":\"RF\",\"crc\":\"498b\"}",
    "{\"config_version\":-1,\"profile\":\"SENSITIVE\",\"debounce_n\":2,\"phi_hard_deg\":20,\"mai_caution\":70,\"report_interval_s\":5,\"primary_model\":\"RF\",\"crc\":\"498b\"}" };
  for (auto s : bad) TEST_ASSERT_FALSE_MESSAGE(msg_parse_config(s, strlen(s), &c, &crc), s);
}
void test_config_phi_hard_40_rejected_even_with_valid_crc(void) {                       // T10
  const char *j = "{\"config_version\":10,\"profile\":\"STANDARD\",\"debounce_n\":3,\"phi_hard_deg\":40,\"mai_caution\":80,\"report_interval_s\":5,\"primary_model\":\"RF\",\"crc\":\"8dea\"}";
  svmg_config_t c, cur; uint16_t crc; svmg_reason_t r; svmg_config_default(&cur, SVMG_MODEL_RF);
  TEST_ASSERT_TRUE(msg_parse_config(j, strlen(j), &c, &crc));
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_REJECT, svmg_config_check_update(&cur, &c, crc, &r)); TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, r);
}
void test_alarm_id_format(void) {
  char b[16]; msg_alarm_id_str(b, sizeof b, 42); TEST_ASSERT_EQUAL_STRING("A-0042", b);
  msg_alarm_id_str(b, sizeof b, 12345); TEST_ASSERT_EQUAL_STRING("A-12345", b);
}

int main(void) {
  UNITY_BEGIN();
  RUN_TEST(test_telemetry_matches_appendix_A1); RUN_TEST(test_telemetry_sensor_mode_and_nan); RUN_TEST(test_telemetry_unknown_and_fault_classes_are_explicit);
  RUN_TEST(test_worst_case_telemetry_size_budget);
  RUN_TEST(test_event_alarm_state_matches_appendix_A2); RUN_TEST(test_event_other_types_are_valid_json);
  RUN_TEST(test_status_and_last_will_exact); RUN_TEST(test_cmd_ack_matches_appendix_A3); RUN_TEST(test_json_escaping_of_hostile_cmd_id);
  RUN_TEST(test_buffer_overflow_is_refused_not_corrupting); RUN_TEST(test_health_and_trace_are_valid_json);
  RUN_TEST(test_parse_cmd_appendix_example); RUN_TEST(test_parse_cmd_all_types); RUN_TEST(test_parse_cmd_bad_params_become_bad_param_not_silent);
  RUN_TEST(test_parse_cmd_rejects_garbage); RUN_TEST(test_parse_cmd_fuzz_does_not_crash);
  RUN_TEST(test_parse_config_appendix_example_and_crc_semantics); RUN_TEST(test_parse_config_rejects_malformed);
  RUN_TEST(test_config_phi_hard_40_rejected_even_with_valid_crc); RUN_TEST(test_alarm_id_format);
  return UNITY_END();
}
