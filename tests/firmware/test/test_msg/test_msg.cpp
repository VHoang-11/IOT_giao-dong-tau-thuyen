// Test bản tin MQTT: khớp Phụ lục A đề cương v2.0, chặn tràn, thoát ký tự, phân tích lệnh/cấu hình, chống dữ liệu hỏng.
#include <unity.h>
#include <ArduinoJson.h>
#include <string.h>
#include <stdio.h>
#include <math.h>
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
static StaticJsonDocument<2048> D;
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
  MsgTelemetry t = TEL(); t.cls_rf = SVMG_UNKNOWN; t.cls_b = SVMG_UNKNOWN; char b[512]; msg_build_telemetry(b, sizeof b, ID(), 1, t); parse(b);
  TEST_ASSERT_EQUAL_STRING("UNKNOWN", D["class_rf"]); TEST_ASSERT_EQUAL_STRING("UNKNOWN", D["class_baseline_b"]);
  t.cls_rf = SVMG_FAULT; t.cls_b = SVMG_FAULT; msg_build_telemetry(b, sizeof b, ID(), 2, t); parse(b);
  TEST_ASSERT_EQUAL_STRING("FAULT", D["class_rf"]);
  TEST_ASSERT_TRUE_MESSAGE(D["class_baseline_b"].isNull(), "schema không cho class_baseline_b = FAULT: phải bỏ trường, không phát giá trị sai");
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
}
void test_event_without_alarm_id_is_never_published(void) {
  svmg_event_t e; memset(&e, 0, sizeof e); e.seq = 5; e.type = SVMG_EV_ALARM_STATE; e.level = SVMG_LVL_CAUTION;
  char b[400]; TEST_ASSERT_EQUAL_UINT_MESSAGE(0, msg_build_event(b, sizeof b, ID(), e), "alarm_id bắt buộc kiểu chuỗi theo schema: thà không phát còn hơn phát sai");
}
void test_ack_is_published_as_alarm_state_with_acked_by(void) {
  svmg_event_t e; memset(&e, 0, sizeof e); char b[400];
  e.seq = 30; e.type = SVMG_EV_ALARM_ACK; e.alarm_id = 7; e.level = SVMG_LVL_WARNING; e.prev_level = SVMG_LVL_NORMAL; e.cls = SVMG_HIGH_ROLL; e.acked_by = SVMG_ACKBY_BUTTON;
  TEST_ASSERT_TRUE(msg_build_event(b, sizeof b, ID(), e) > 0); parse(b);
  TEST_ASSERT_EQUAL_STRING("ALARM_STATE", D["type"]);                         // schema: type const ALARM_STATE
  TEST_ASSERT_EQUAL_STRING("WARNING", D["level"]); TEST_ASSERT_EQUAL_STRING("WARNING", D["prev_level"]);   // giữ nguyên mức
  TEST_ASSERT_EQUAL_STRING("device_button", D["acked_by"]); TEST_ASSERT_EQUAL_STRING("A-0007", D["alarm_id"]);
  e.acked_by = SVMG_ACKBY_REMOTE; msg_build_event(b, sizeof b, ID(), e); parse(b);
  TEST_ASSERT_EQUAL_STRING("remote", D["acked_by"]);
}
void test_event_class_outside_schema_enum_is_clamped(void) {
  svmg_event_t e; memset(&e, 0, sizeof e); char b[400];
  e.seq = 9; e.type = SVMG_EV_ALARM_STATE; e.alarm_id = 3; e.level = SVMG_LVL_CRITICAL; e.prev_level = SVMG_LVL_NORMAL; e.cls = SVMG_UNKNOWN;
  TEST_ASSERT_TRUE(msg_build_event(b, sizeof b, ID(), e) > 0); parse(b);
  TEST_ASSERT_EQUAL_STRING("NORMAL", D["class"]);                             // UNKNOWN/FAULT không có trong enum class của event.json
}
void test_system_events_are_not_published_on_event_topic(void) {
  const uint8_t types[] = { SVMG_EV_ALARM_MUTE, SVMG_EV_MODE_CHANGE, SVMG_EV_SCENARIO_CHANGE, SVMG_EV_FAULT, SVMG_EV_FAULT_CLEARED,
                            SVMG_EV_CONFIG_APPLIED, SVMG_EV_CALIBRATION, SVMG_EV_BOOT, 99 };
  for (uint8_t t : types) {
    svmg_event_t e; memset(&e, 0, sizeof e); e.seq = 1; e.type = t; e.alarm_id = 9; char b[400];
    TEST_ASSERT_FALSE_MESSAGE(msg_event_publishable(t), "loại ngoài schema không được đưa vào bộ đệm phát");
    TEST_ASSERT_EQUAL_UINT(0, msg_build_event(b, sizeof b, ID(), e));
  }
  TEST_ASSERT_TRUE(msg_event_publishable(SVMG_EV_ALARM_STATE)); TEST_ASSERT_TRUE(msg_event_publishable(SVMG_EV_ALARM_ACK));
}
void test_status_and_last_will_exact(void){
 MsgIdent id=ID();strcpy(id.boot_id,"a3f9");char b[400];
 TEST_ASSERT_TRUE(msg_build_status_online(b,sizeof b,id,8)>0);parse(b);
 TEST_ASSERT_EQUAL_STRING("online",D["state"]);TEST_ASSERT_EQUAL_STRING("1.0.0",D["fw"]);
 TEST_ASSERT_EQUAL_STRING("rf_v1",D["model_version"]);TEST_ASSERT_EQUAL_STRING("a3f9",D["boot_id"]);
 TEST_ASSERT_EQUAL_INT(8,D["config_version"]);TEST_ASSERT_EQUAL_INT(23,D["feature_count"]);
 msg_build_status_offline(b,sizeof b);TEST_ASSERT_EQUAL_STRING("{\"state\":\"offline\"}",b);
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
void test_health_uses_contract_field_names(void) {
  MsgHealth h; memset(&h, 0, sizeof h); h.uptime_ms = 5000ull + (1ull << 33); h.heap_free = 200000; h.heap_min = 180000; h.rssi = -60; h.sensor_ok = true;
  h.evbuf_depth = 3; h.reconnects = 2; h.i2c_errors = 4; h.infer_us_avg = 1500; h.infer_us_max = 2500;
  char b[700]; TEST_ASSERT_TRUE(msg_build_health(b, sizeof b, ID(), 9, h) > 0); parse(b);
  TEST_ASSERT_EQUAL_STRING("vessel-demo-01", D["device_id"]);
  TEST_ASSERT_EQUAL_INT(200000, D["free_heap_bytes"]); TEST_ASSERT_EQUAL_INT(180000, D["min_free_heap_bytes"]);
  TEST_ASSERT_TRUE(D["sensor_ok"].as<bool>()); TEST_ASSERT_EQUAL_INT(4, D["i2c_errors"]);
  TEST_ASSERT_EQUAL_FLOAT(1.5f, D["inference_ms"]); TEST_ASSERT_EQUAL_INT(2, D["mqtt_reconnects"]);
  TEST_ASSERT_EQUAL_INT(3, D["buffer_used"]); TEST_ASSERT_EQUAL_INT(64, D["buffer_capacity"]);
  TEST_ASSERT_EQUAL_UINT64(5000ull + (1ull << 33), D["uptime_ms"].as<uint64_t>());            // 64 bit, không quấn
  TEST_ASSERT_TRUE_MESSAGE(D["heap_free"].isNull(), "tên cũ heap_free không còn");
}
#ifdef SVMG_EXT_TRACE
void test_trace_is_valid_json_when_enabled(void) {
  int16_t r[60], p[60]; for (int i = 0; i < 60; i++) { r[i] = (int16_t)(i * 10 - 300); p[i] = (int16_t)(-i); }
  static char big[1400]; TEST_ASSERT_TRUE(msg_build_trace(big, sizeof big, ID(), 10, 100.0f, 60, 1, 3, r, p, 60) > 0);
  static StaticJsonDocument<16384> T; DeserializationError er = deserializeJson(T, big); TEST_ASSERT_TRUE_MESSAGE(er == DeserializationError::Ok, er.c_str());
  TEST_ASSERT_EQUAL_UINT(60, T["roll_cdeg"].size());
}
#endif

/* Topic thiết bị dùng phải nằm trong ACL Mosquitto của người dùng thiết bị (infra/mosquitto/acl). */
void test_topics_match_broker_acl(void) {
  FILE *f = fopen("../../infra/mosquitto/acl", "r");
  if (!f) TEST_IGNORE_MESSAGE("không thấy infra/mosquitto/acl (chạy từ tests/firmware trong repo đầy đủ)");
  char line[200]; bool in_dev = false; int w = 0, r = 0; bool wr_ok[16] = {false}, rd_ok[8] = {false};
  while (fgets(line, sizeof line, f)) {
    if (strncmp(line, "user ", 5) == 0) in_dev = (strncmp(line + 5, "vessel-demo-01", 14) == 0);
    if (!in_dev) continue;
    char dir[16], topic[128];
    if (sscanf(line, "topic %15s %127s", dir, topic) != 2) continue;
    const char *pre = "svmg/vessel-demo-01/";
    if (strncmp(topic, pre, strlen(pre)) != 0) continue;
    const char *sub = topic + strlen(pre);
    if (!strcmp(dir, "write")) { w++; for (int i = 0; i < MSG_PUBLISH_TOPIC_COUNT; i++) if (!strcmp(sub, MSG_PUBLISH_TOPICS[i])) wr_ok[i] = true; }
    if (!strcmp(dir, "read")) { r++; for (int i = 0; i < MSG_SUBSCRIBE_TOPIC_COUNT; i++) if (!strcmp(sub, MSG_SUBSCRIBE_TOPICS[i])) rd_ok[i] = true; }
  }
  fclose(f);
  TEST_ASSERT_TRUE_MESSAGE(w > 0 && r > 0, "không đọc được ACL của vessel-demo-01");
  for (int i = 0; i < MSG_PUBLISH_TOPIC_COUNT; i++) { char m[80]; snprintf(m, sizeof m, "ACL không cho thiết bị ghi topic '%s'", MSG_PUBLISH_TOPICS[i]); TEST_ASSERT_TRUE_MESSAGE(wr_ok[i], m); }
  for (int i = 0; i < MSG_SUBSCRIBE_TOPIC_COUNT; i++) { char m[80]; snprintf(m, sizeof m, "ACL không cho thiết bị đọc topic '%s'", MSG_SUBSCRIBE_TOPICS[i]); TEST_ASSERT_TRUE_MESSAGE(rd_ok[i], m); }
}

// ---------------- Phân tích lệnh (bộ lệnh = contracts/schemas/command.json) ----------------
static svmg_reason_t ok_hook_ret;
static svmg_reason_t hk_ack(void *, uint32_t, int) { return ok_hook_ret; }
static svmg_reason_t hk_mute(void *, uint16_t) { return ok_hook_ret; }
static svmg_reason_t hk_prof(void *, uint8_t) { return ok_hook_ret; }
static svmg_reason_t hk_thr(void *, const svmg_cmd_t *) { return ok_hook_ret; }
static svmg_reason_t hk_void(void *) { return ok_hook_ret; }
static uint32_t hkv(void *) { return 5; }
/* start_voyage/stop_voyage và các lệnh mở rộng không có hook (backend không gửi / ngoài contract) -> UNSUPPORTED */
static svmg_cmd_hooks_t HK = { nullptr, hk_ack, hk_mute, hk_prof, hk_thr, hk_void, hk_void, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, hkv };
static svmg_reason_t run(const char *json) {
  svmg_cmd_t c; if (!msg_parse_cmd(json, strlen(json), &c)) return (svmg_reason_t)99;
  svmg_cmd_ctx_t ctx; svmg_cmd_init(&ctx); svmg_cmd_ack_t a; ok_hook_ret = SVMG_R_OK;
  if (!svmg_cmd_exec(&ctx, &HK, &c, 0, &a)) return (svmg_reason_t)98;
  return a.applied ? SVMG_R_OK : a.reason;
}
void test_parse_cmd_contract_example(void) {
  const char *j = "{ \"cmd_id\": \"c-7f21\", \"cmd\": \"set_profile\", \"params\": { \"profile\": \"SENSITIVE\" }, \"ttl_s\": 30, \"issued_by\": \"sup01\" }";
  svmg_cmd_t c; TEST_ASSERT_TRUE(msg_parse_cmd(j, strlen(j), &c));
  TEST_ASSERT_EQUAL_STRING("c-7f21", c.cmd_id); TEST_ASSERT_EQUAL_UINT8(SVMG_CMD_SET_PROFILE, c.type); TEST_ASSERT_EQUAL_UINT8(SVMG_PROFILE_SENSITIVE, c.profile);
  TEST_ASSERT_EQUAL_UINT16(30, c.ttl_s); TEST_ASSERT_EQUAL_STRING("sup01", c.issued_by);
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run(j));
}
void test_parse_cmd_all_contract_commands(void) {
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run("{\"cmd_id\":\"a\",\"cmd\":\"set_threshold\",\"params\":{\"phi_hard_deg\":18.5,\"mai_caution\":75,\"debounce_n\":4,\"report_interval_s\":10},\"ttl_s\":30,\"issued_by\":\"sup01\"}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run("{\"cmd_id\":\"b\",\"cmd\":\"calibrate_zero\",\"params\":{},\"ttl_s\":60,\"issued_by\":\"sup01\"}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run("{\"cmd_id\":\"c\",\"cmd\":\"calibrate_zero\",\"ttl_s\":60,\"issued_by\":\"sup01\"}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run("{\"cmd_id\":\"d\",\"cmd\":\"mute_alarm\",\"params\":{\"duration_s\":120},\"ttl_s\":30,\"issued_by\":\"op\"}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run("{\"cmd_id\":\"e\",\"cmd\":\"mute_alarm\",\"params\":{},\"ttl_s\":30,\"issued_by\":\"op\"}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run("{\"cmd_id\":\"f\",\"cmd\":\"restart_device\",\"params\":{},\"ttl_s\":30,\"issued_by\":\"admin\"}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run("{\"cmd_id\":\"g\",\"cmd\":\"ack_alarm\",\"params\":{\"alarm_id\":\"A-0042\"},\"ttl_s\":30,\"issued_by\":\"op\"}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_UNSUPPORTED, run("{\"cmd_id\":\"h\",\"cmd\":\"start_voyage\",\"params\":{},\"ttl_s\":30,\"issued_by\":\"sup\"}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_UNSUPPORTED, run("{\"cmd_id\":\"i\",\"cmd\":\"stop_voyage\",\"params\":{},\"ttl_s\":30,\"issued_by\":\"sup\"}"));
}
void test_parse_cmd_ack_alarm_id_forms(void) {
  svmg_cmd_t c; const char *a = "{\"cmd_id\":\"g\",\"cmd\":\"ack_alarm\",\"params\":{\"alarm_id\":\"A-0042\"},\"ttl_s\":30}";
  TEST_ASSERT_TRUE(msg_parse_cmd(a, strlen(a), &c)); TEST_ASSERT_TRUE(c.has & SVMG_CP_ALARM); TEST_ASSERT_EQUAL_UINT32(42, c.alarm_id);
  const char *b = "{\"cmd_id\":\"g\",\"cmd\":\"ack_alarm\",\"ttl_s\":30}";
  TEST_ASSERT_TRUE(msg_parse_cmd(b, strlen(b), &c)); TEST_ASSERT_FALSE(c.has & SVMG_CP_ALARM);
}
void test_parse_cmd_bad_params_become_bad_param_not_silent(void) {
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"a\",\"cmd\":\"mute_alarm\",\"params\":{\"duration_s\":\"abc\"},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"b\",\"cmd\":\"mute_alarm\",\"params\":{\"duration_s\":-5},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"c\",\"cmd\":\"mute_alarm\",\"params\":{\"duration_s\":999999},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"d\",\"cmd\":\"mute_alarm\",\"params\":{\"duration_s\":1.5},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"d2\",\"cmd\":\"mute_alarm\",\"params\":{\"duration_s\":600},\"ttl_s\":30}"), "backend cho 600 s nhưng thiết bị trần 300 s");
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"e\",\"cmd\":\"set_profile\",\"params\":{\"profile\":\"WILD\"},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"f\",\"cmd\":\"set_profile\",\"params\":{\"profile\":7},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"g\",\"cmd\":\"set_profile\",\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"h\",\"cmd\":\"set_threshold\",\"params\":{\"phi_hard_deg\":40},\"ttl_s\":30}"), "T10: phi_hard = 40");
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"h2\",\"cmd\":\"set_threshold\",\"params\":{\"phi_hard_deg\":\"20\"},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"h3\",\"cmd\":\"set_threshold\",\"params\":{\"mai_caution\":95},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"h4\",\"cmd\":\"set_threshold\",\"params\":{\"debounce_n\":11},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"h5\",\"cmd\":\"set_threshold\",\"params\":{},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"j\",\"cmd\":\"calibrate_zero\",\"params\":{\"duration_s\":5},\"ttl_s\":60}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"k\",\"cmd\":\"mute_alarm\",\"params\":{\"duration_s\":60}}"));                       // thiếu ttl_s
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"l\",\"cmd\":\"mute_alarm\",\"params\":{\"duration_s\":60},\"ttl_s\":0}"));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"l2\",\"cmd\":\"mute_alarm\",\"params\":{},\"ttl_s\":\"30\"}"));
  TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_R_BAD_PARAM, run("{\"cmd_id\":\"age-invalid\",\"cmd\":\"set_profile\",\"ttl_s\":30,\"age_s\":-1,\"params\":{\"profile\":\"SENSITIVE\"}}"), "age_s âm không được bỏ qua âm thầm");
  TEST_ASSERT_EQUAL_INT(SVMG_R_UNSUPPORTED, run("{\"cmd_id\":\"m\",\"cmd\":\"disable_alarm\",\"params\":{},\"ttl_s\":30}"));       // không có lệnh tắt cảnh báo
  TEST_ASSERT_EQUAL_INT(SVMG_R_UNSUPPORTED, run("{\"cmd_id\":\"n\",\"cmd\":\"set_phi_hard\",\"params\":{\"phi\":90},\"ttl_s\":30}"));
  TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_R_UNSUPPORTED, run("{\"cmd_id\":\"o\",\"cmd\":\"set_mode\",\"params\":{\"mode\":\"SIMULATION\"},\"ttl_s\":30}"), "lệnh ngoài contract bị tắt (SVMG_EXT_COMMANDS)");
  TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_R_UNSUPPORTED, run("{\"cmd_id\":\"p\",\"cmd\":\"mute\",\"params\":{\"duration_s\":60},\"ttl_s\":30}"), "tên cũ 'mute' không còn: contract là mute_alarm");
}
void test_parse_cmd_rejects_garbage(void) {
  svmg_cmd_t c;
  const char *bad[] = { "", "{", "null", "[]", "42", "{\"cmd\":\"ack_alarm\",\"ttl_s\":30}", "{\"cmd_id\":\"\",\"cmd\":\"ack_alarm\"}", "{\"cmd_id\":5}",
                        "{\"cmd_id\":\"this-cmd-id-is-way-too-long-for-the-fixed-buffer\",\"cmd\":\"ack_alarm\",\"ttl_s\":30}" };
  for (auto s : bad) TEST_ASSERT_FALSE_MESSAGE(msg_parse_cmd(s, strlen(s), &c), s);
}
void test_parse_cmd_fuzz_does_not_crash(void) {
  const char *seed = "{\"cmd_id\":\"c-7f21\",\"cmd\":\"set_threshold\",\"params\":{\"phi_hard_deg\":18.5,\"mai_caution\":75},\"ttl_s\":30,\"issued_by\":\"sup01\"}";
  uint32_t r = 12345; int accepted = 0;
  for (int i = 0; i < 4000; i++) {
    char m[200]; size_t n = strlen(seed); memcpy(m, seed, n + 1);
    int k = 1 + (int)(r % 4);
    for (int j = 0; j < k; j++) { r = r * 1664525u + 1013904223u; size_t pos = (r >> 8) % n; r = r * 1664525u + 1013904223u; m[pos] = (char)(r >> 16); }
    r = r * 1664525u + 1013904223u; if ((r >> 20) % 7 == 0) m[(r >> 8) % n] = 0;
    svmg_cmd_t c; if (msg_parse_cmd(m, strlen(m), &c)) { accepted++; svmg_cmd_ctx_t ctx; svmg_cmd_init(&ctx); svmg_cmd_ack_t a; ok_hook_ret = SVMG_R_OK; svmg_cmd_exec(&ctx, &HK, &c, 0, &a); }
  }
  TEST_ASSERT_TRUE(accepted > 0);
}

// ---------------- Phân tích cấu hình (bản vá; CRC như backend) ----------------
/* Các payload dưới đây có CRC tính bằng ĐÚNG hàm của backend (json.dumps sort_keys, separators (',',':'), binascii.crc_hqx 0xFFFF). */
static svmg_cfg_verdict_t verdict(const char *json, svmg_config_patch_t *p, svmg_reason_t *r) {
  svmg_config_t cur; svmg_config_default(&cur, SVMG_MODEL_RF); cur.config_version = 1; svmg_config_t out;
  if (!msg_parse_config(json, strlen(json), p)) { *r = SVMG_R_BAD_PARAM; return SVMG_CFG_REJECT; }
  return svmg_config_check_patch(&cur, p, &out, r);
}
void test_config_crc_matches_backend_for_int_and_float(void) {
  svmg_config_patch_t p; svmg_reason_t r;
  /* cùng nội dung nhưng 20 (số nguyên) và 20.0 (số thực) cho CRC khác nhau: 4fa6 / 0902 */
  const char *i20 = "{\"config_version\": 8, \"profile\": \"SENSITIVE\", \"debounce_n\": 2, \"phi_hard_deg\": 20, \"mai_caution\": 70, \"report_interval_s\": 5, \"primary_model\": \"RF\", \"crc\": \"4fa6\"}";
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_APPLY, verdict(i20, &p, &r)); TEST_ASSERT_EQUAL_UINT8(SVMG_CRC_OK, p.crc_state);
  const char *f20 = "{\"config_version\": 8, \"profile\": \"SENSITIVE\", \"debounce_n\": 2, \"phi_hard_deg\": 20.0, \"mai_caution\": 70, \"report_interval_s\": 5, \"primary_model\": \"RF\", \"crc\": \"0902\"}";
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_APPLY, verdict(f20, &p, &r)); TEST_ASSERT_EQUAL_UINT8(SVMG_CRC_OK, p.crc_state);
  const char *mix = "{\"config_version\": 8, \"profile\": \"SENSITIVE\", \"debounce_n\": 2, \"phi_hard_deg\": 20.0, \"mai_caution\": 70, \"report_interval_s\": 5, \"primary_model\": \"RF\", \"crc\": \"4fa6\"}";
  TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_CFG_REJECT, verdict(mix, &p, &r), "20.0 với CRC của 20 phải bị từ chối"); TEST_ASSERT_EQUAL_UINT8(SVMG_CRC_BAD, p.crc_state);
  const char *p173 = "{\"config_version\": 4, \"profile\": \"STANDARD\", \"phi_hard_deg\": 17.3, \"crc\": \"2937\"}";
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_APPLY, verdict(p173, &p, &r)); TEST_ASSERT_EQUAL_UINT8(SVMG_CRC_OK, p.crc_state);
  TEST_ASSERT_EQUAL_FLOAT(17.3f, p.phi_hard_deg);
}
void test_config_partial_patch_and_key_order_independent(void) {
  svmg_config_patch_t p; svmg_reason_t r;
  const char *a = "{\"config_version\": 2, \"profile\": \"STANDARD\", \"crc\": \"d0ef\"}";
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_APPLY, verdict(a, &p, &r)); TEST_ASSERT_TRUE(p.has == SVMG_CFGP_PROFILE);
  const char *b = "{\"crc\":\"d0ef\",\"profile\":\"STANDARD\",\"config_version\":2}";                      // thứ tự khóa/khoảng trắng khác
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_APPLY, verdict(b, &p, &r)); TEST_ASSERT_EQUAL_UINT8(SVMG_CRC_OK, p.crc_state);
  const char *c = "{\"config_version\": 2, \"profile\": \"STANDARD\"}";                                   // không có crc: schema cho phép
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_APPLY, verdict(c, &p, &r)); TEST_ASSERT_EQUAL_UINT8(SVMG_CRC_ABSENT, p.crc_state);
}
void test_config_crc_covers_unknown_fields_and_unicode(void) {
  svmg_config_patch_t p; svmg_reason_t r;
  const char *j = "{\"config_version\": 5, \"profile\": \"STANDARD\", \"note\": \"ti\\u1ebfng Vi\\u1ec7t \\\"x\\\"\", \"crc\": \"3871\"}";
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_APPLY, verdict(j, &p, &r)); TEST_ASSERT_EQUAL_UINT8(SVMG_CRC_OK, p.crc_state);
  const char *raw_utf8 = "{\"config_version\": 5, \"profile\": \"STANDARD\", \"note\": \"tiếng Việt \\\"x\\\"\", \"crc\": \"3871\"}";   // UTF-8 thô cũng cho cùng CRC
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_APPLY, verdict(raw_utf8, &p, &r)); TEST_ASSERT_EQUAL_UINT8(SVMG_CRC_OK, p.crc_state);
}
void test_config_contract_sample_is_rejected_because_its_crc_is_not_computable(void) {
  /* contracts/examples/config_sample.json mang crc "9c1e" không khớp thuật toán của backend -> thiết bị từ chối (đưa vào đề xuất sửa mẫu) */
  const char *j = "{ \"config_version\": 8, \"profile\": \"SENSITIVE\", \"debounce_n\": 2, \"phi_hard_deg\": 20, \"mai_caution\": 70, \"report_interval_s\": 5, \"primary_model\": \"RF\", \"crc\": \"9c1e\" }";
  svmg_config_patch_t p; svmg_reason_t r;
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_REJECT, verdict(j, &p, &r)); TEST_ASSERT_EQUAL_UINT8(SVMG_CRC_BAD, p.crc_state);
}
void test_config_phi_hard_40_rejected_even_with_valid_crc(void) {                       // T10
  const char *j = "{\"config_version\": 10, \"profile\": \"STANDARD\", \"phi_hard_deg\": 40, \"crc\": \"f4d2\"}";
  svmg_config_patch_t p; svmg_reason_t r;
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_REJECT, verdict(j, &p, &r)); TEST_ASSERT_EQUAL_UINT8(SVMG_CRC_OK, p.crc_state); TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, r);
}
void test_config_without_profile_parses_but_is_rejected_by_policy(void) {
  svmg_config_patch_t p; svmg_reason_t r;
  TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_CFG_REJECT, verdict("{\"config_version\":8}", &p, &r), "schema bắt buộc profile");
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, r);
}
void test_parse_config_rejects_malformed(void) {
  svmg_config_patch_t p;
  const char *bad[] = { "", "{}", "[]", "{\"profile\":\"STANDARD\"}",
    "{\"config_version\":8,\"profile\":\"XYZ\"}", "{\"config_version\":-1,\"profile\":\"STANDARD\"}", "{\"config_version\":8,\"profile\":5}",
    "{\"config_version\":8,\"profile\":\"STANDARD\",\"phi_hard_deg\":\"20\"}", "{\"config_version\":8,\"profile\":\"STANDARD\",\"debounce_n\":2.5}",
    "{\"config_version\":8,\"profile\":\"STANDARD\",\"primary_model\":\"GPT\"}", "{\"config_version\":8,\"profile\":\"STANDARD\",\"mai_caution\":-3}" };
  for (auto s : bad) TEST_ASSERT_FALSE_MESSAGE(msg_parse_config(s, strlen(s), &p), s);
  const char *badcrc = "{\"config_version\":8,\"profile\":\"STANDARD\",\"crc\":\"zzzz\"}";
  TEST_ASSERT_TRUE(msg_parse_config(badcrc, strlen(badcrc), &p)); TEST_ASSERT_EQUAL_UINT8(SVMG_CRC_BAD, p.crc_state);
  const char *nested = "{\"config_version\":8,\"profile\":\"STANDARD\",\"x\":{\"a\":1},\"crc\":\"d0ef\"}";            // cấu hình phẳng: lồng nhau -> CRC không tính được -> BAD
  TEST_ASSERT_TRUE(msg_parse_config(nested, strlen(nested), &p)); TEST_ASSERT_EQUAL_UINT8(SVMG_CRC_BAD, p.crc_state);
}
void test_config_out_of_range_values_rejected_by_validate_not_clamped(void) {
  svmg_config_patch_t p; svmg_reason_t r;
  const char *cases[] = {
    "{\"config_version\":9,\"profile\":\"STANDARD\",\"phi_hard_deg\":14}", "{\"config_version\":9,\"profile\":\"STANDARD\",\"phi_hard_deg\":26.5}",
    "{\"config_version\":9,\"profile\":\"STANDARD\",\"debounce_n\":11}", "{\"config_version\":9,\"profile\":\"STANDARD\",\"mai_caution\":91}",
    "{\"config_version\":9,\"profile\":\"STANDARD\",\"report_interval_s\":0}", "{\"config_version\":9,\"profile\":\"STANDARD\",\"report_interval_s\":3601}" };
  for (auto s : cases) { TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_CFG_REJECT, verdict(s, &p, &r), s); TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, r); }
}

void test_alarm_id_format(void) {
  char b[16]; msg_alarm_id_str(b, sizeof b, 42); TEST_ASSERT_EQUAL_STRING("A-0042", b);
  msg_alarm_id_str(b, sizeof b, 12345); TEST_ASSERT_EQUAL_STRING("A-12345", b);
}

void test_undefined_diagnostics_are_omitted_and_schema_is_versioned(){
 MsgTelemetry t=TEL();t.rms_roll_deg=NAN;t.heel_offset_deg=NAN;t.trend_rms_deg_per_min=NAN;
 char b[800];TEST_ASSERT_TRUE(msg_build_telemetry(b,sizeof b,ID(),1,t)>0);parse(b);
 TEST_ASSERT_FALSE(D.containsKey("rms_roll_deg"));TEST_ASSERT_FALSE(D.containsKey("heel_offset_deg"));TEST_ASSERT_FALSE(D.containsKey("trend_rms_deg_per_min"));
 TEST_ASSERT_TRUE(msg_build_status_online(b,sizeof b,ID(),1)>0);parse(b);
 TEST_ASSERT_EQUAL_STRING(SVMG_FEATURE_SCHEMA_VERSION,D["feature_schema_version"].as<const char*>());
 TEST_ASSERT_EQUAL_INT(23,D["feature_count"].as<int>());
}
int main(void) {
  UNITY_BEGIN();
  RUN_TEST(test_undefined_diagnostics_are_omitted_and_schema_is_versioned);
  RUN_TEST(test_telemetry_matches_appendix_A1); RUN_TEST(test_telemetry_sensor_mode_and_nan); RUN_TEST(test_telemetry_unknown_and_fault_classes_are_explicit);
  RUN_TEST(test_worst_case_telemetry_size_budget);
  RUN_TEST(test_event_alarm_state_matches_appendix_A2); RUN_TEST(test_event_without_alarm_id_is_never_published);
  RUN_TEST(test_ack_is_published_as_alarm_state_with_acked_by); RUN_TEST(test_event_class_outside_schema_enum_is_clamped);
  RUN_TEST(test_system_events_are_not_published_on_event_topic);
  RUN_TEST(test_status_and_last_will_exact); RUN_TEST(test_cmd_ack_matches_appendix_A3); RUN_TEST(test_json_escaping_of_hostile_cmd_id);
  RUN_TEST(test_buffer_overflow_is_refused_not_corrupting); RUN_TEST(test_health_uses_contract_field_names); RUN_TEST(test_topics_match_broker_acl);
#ifdef SVMG_EXT_TRACE
  RUN_TEST(test_trace_is_valid_json_when_enabled);
#endif
  RUN_TEST(test_parse_cmd_contract_example); RUN_TEST(test_parse_cmd_all_contract_commands); RUN_TEST(test_parse_cmd_ack_alarm_id_forms);
  RUN_TEST(test_parse_cmd_bad_params_become_bad_param_not_silent); RUN_TEST(test_parse_cmd_rejects_garbage); RUN_TEST(test_parse_cmd_fuzz_does_not_crash);
  RUN_TEST(test_config_crc_matches_backend_for_int_and_float); RUN_TEST(test_config_partial_patch_and_key_order_independent);
  RUN_TEST(test_config_crc_covers_unknown_fields_and_unicode); RUN_TEST(test_config_contract_sample_is_rejected_because_its_crc_is_not_computable);
  RUN_TEST(test_config_phi_hard_40_rejected_even_with_valid_crc); RUN_TEST(test_config_without_profile_parses_but_is_rejected_by_policy); RUN_TEST(test_parse_config_rejects_malformed);
  RUN_TEST(test_config_out_of_range_values_rejected_by_validate_not_clamped); RUN_TEST(test_alarm_id_format);
  return UNITY_END();
}
