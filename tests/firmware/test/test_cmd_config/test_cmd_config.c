/* Test M1-07: cấu hình (bản vá, biên theo schema), kênh lệnh theo contracts/schemas/command.json, hiệu chuẩn. */
#include <unity.h>
#include <string.h>
#include <stdio.h>
#include <math.h>
#include "svmg_cmd.h"
#include "svmg_config.h"
#include "svmg_calib.h"
#include "svmg_testutil.h"

void setUp(void) {}
void tearDown(void) {}

/* ================= CRC-16 ================= */
void test_crc16_check_value(void) {
  TEST_ASSERT_EQUAL_HEX16(0x29B1, svmg_crc16_ccitt("123456789", 9));      /* giá trị chuẩn CRC-16/CCITT-FALSE */
}

/* ================= Cấu hình ================= */
static svmg_config_patch_t patch(uint32_t ver) { svmg_config_patch_t p; memset(&p, 0, sizeof p); p.config_version = ver; p.crc_state = SVMG_CRC_OK; return p; }
static void with_profile(svmg_config_patch_t *p, int prof) { p->has |= SVMG_CFGP_PROFILE; p->profile = (uint8_t)prof; }

void test_profiles(void) {
  svmg_config_t c; svmg_config_default(&c, SVMG_MODEL_RF);
  TEST_ASSERT_EQUAL_UINT8(3, c.debounce_n); TEST_ASSERT_EQUAL_UINT8(80, c.mai_caution);
  svmg_config_apply_profile(&c, SVMG_PROFILE_SENSITIVE); TEST_ASSERT_EQUAL_UINT8(2, c.debounce_n); TEST_ASSERT_EQUAL_UINT8(70, c.mai_caution);
  svmg_config_apply_profile(&c, SVMG_PROFILE_CONSERVATIVE); TEST_ASSERT_EQUAL_UINT8(4, c.debounce_n); TEST_ASSERT_EQUAL_UINT8(85, c.mai_caution);
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, svmg_config_validate(&c));
  TEST_ASSERT_EQUAL_FLOAT(20.0f, c.phi_hard_deg);
}
void test_validate_bounds_follow_schema(void) {
  svmg_config_t g; svmg_config_default(&g, SVMG_MODEL_RF); svmg_config_t c;
#define BAD(stmt) do { c = g; stmt; TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_R_BAD_PARAM, svmg_config_validate(&c), #stmt); } while (0)
#define GOOD(stmt) do { c = g; stmt; TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_R_OK, svmg_config_validate(&c), #stmt); } while (0)
  BAD(c.phi_hard_deg = 14.9f); BAD(c.phi_hard_deg = 25.1f); BAD(c.phi_hard_deg = 40.0f); BAD(c.phi_hard_deg = 0.0f); BAD(c.phi_hard_deg = NAN);
  GOOD(c.phi_hard_deg = 15.0f); GOOD(c.phi_hard_deg = 25.0f); GOOD(c.phi_hard_deg = 17.5f);
  BAD(c.debounce_n = 0); BAD(c.debounce_n = 11); GOOD(c.debounce_n = 1); GOOD(c.debounce_n = 10);
  BAD(c.mai_caution = 29); BAD(c.mai_caution = 91); GOOD(c.mai_caution = 30); GOOD(c.mai_caution = 90);
  BAD(c.report_interval_s = 0); BAD(c.report_interval_s = 3601); GOOD(c.report_interval_s = 1); GOOD(c.report_interval_s = 3600); GOOD(c.report_interval_s = 7);
  BAD(c.primary_model = 2); BAD(c.profile = 3);
  BAD(c.zero_roll_deg = 10.5f); BAD(c.zero_pitch_deg = NAN);
#undef BAD
#undef GOOD
}
void test_patch_keeps_absent_fields_and_local_calibration(void) {
  svmg_config_t cur; svmg_config_default(&cur, SVMG_MODEL_RF);
  cur.config_version = 5; cur.report_interval_s = 20; cur.phi_hard_deg = 18.0f; cur.zero_roll_deg = 1.5f; cur.zero_pitch_deg = -0.5f;
  svmg_config_patch_t p = patch(6); with_profile(&p, SVMG_PROFILE_STANDARD);                  /* chỉ có profile */
  svmg_config_t out; svmg_reason_t r;
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_APPLY, svmg_config_check_patch(&cur, &p, &out, &r));
  TEST_ASSERT_EQUAL_UINT32(6, out.config_version); TEST_ASSERT_EQUAL_UINT16(20, out.report_interval_s);   /* giữ */
  TEST_ASSERT_EQUAL_FLOAT(18.0f, out.phi_hard_deg); TEST_ASSERT_EQUAL_FLOAT(1.5f, out.zero_roll_deg); TEST_ASSERT_EQUAL_FLOAT(-0.5f, out.zero_pitch_deg);
}
void test_patch_profile_defaults_then_explicit_fields_override(void) {
  svmg_config_t cur; svmg_config_default(&cur, SVMG_MODEL_RF); cur.config_version = 1; svmg_config_t out; svmg_reason_t r;
  svmg_config_patch_t p = patch(2); with_profile(&p, SVMG_PROFILE_SENSITIVE);
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_APPLY, svmg_config_check_patch(&cur, &p, &out, &r));
  TEST_ASSERT_EQUAL_UINT8(2, out.debounce_n); TEST_ASSERT_EQUAL_UINT8(70, out.mai_caution);     /* mặc định hồ sơ SENSITIVE */
  p = patch(3); with_profile(&p, SVMG_PROFILE_SENSITIVE); p.has |= SVMG_CFGP_DEBOUNCE | SVMG_CFGP_MAI; p.debounce_n = 5; p.mai_caution = 55;
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_APPLY, svmg_config_check_patch(&cur, &p, &out, &r));
  TEST_ASSERT_EQUAL_UINT8(5, out.debounce_n); TEST_ASSERT_EQUAL_UINT8(55, out.mai_caution);     /* trường tường minh thắng */
}
void test_patch_verdicts(void) {
  svmg_config_t cur; svmg_config_default(&cur, SVMG_MODEL_RF); cur.config_version = 8; svmg_config_t out; svmg_reason_t r;
  svmg_config_patch_t p = patch(9); with_profile(&p, SVMG_PROFILE_STANDARD);
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_APPLY, svmg_config_check_patch(&cur, &p, &out, &r)); TEST_ASSERT_EQUAL_INT(SVMG_R_OK, r);
  p.crc_state = SVMG_CRC_BAD;                                                                   /* sai CRC */
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_REJECT, svmg_config_check_patch(&cur, &p, &out, &r)); TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, r);
  p.crc_state = SVMG_CRC_ABSENT;                                                                /* crc tùy chọn theo schema */
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_APPLY, svmg_config_check_patch(&cur, &p, &out, &r));
  p = patch(10); with_profile(&p, SVMG_PROFILE_STANDARD); p.has |= SVMG_CFGP_PHI; p.phi_hard_deg = 40.0f;   /* T10: phi_hard = 40, CRC đúng */
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_REJECT, svmg_config_check_patch(&cur, &p, &out, &r)); TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, r);
  p = patch(9); p.has |= SVMG_CFGP_DEBOUNCE; p.debounce_n = 3;                                  /* thiếu profile (schema bắt buộc) */
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_REJECT, svmg_config_check_patch(&cur, &p, &out, &r));
  p = patch(3); with_profile(&p, SVMG_PROFILE_STANDARD);                                        /* phiên bản cũ */
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_REJECT, svmg_config_check_patch(&cur, &p, &out, &r));
  svmg_config_t same = cur; same.profile = SVMG_PROFILE_STANDARD;
  p = patch(8); with_profile(&p, SVMG_PROFILE_STANDARD);                                        /* cùng phiên bản, cùng nội dung: retained gửi lại */
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_DUPLICATE, svmg_config_check_patch(&same, &p, &out, &r));
  p = patch(8); with_profile(&p, SVMG_PROFILE_SENSITIVE);                                       /* cùng phiên bản, khác nội dung */
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_REJECT, svmg_config_check_patch(&same, &p, &out, &r));
  TEST_ASSERT_EQUAL_UINT32_MESSAGE(8, same.config_version, "bản vá bị từ chối không đổi cấu hình hiện tại");
}
void test_rollback_is_a_newer_version_with_old_content(void) {
  svmg_config_t cur; svmg_config_default(&cur, SVMG_MODEL_RF); svmg_config_t out; svmg_reason_t r;
  cur.config_version = 7; cur.phi_hard_deg = 22.0f;
  svmg_config_patch_t p = patch(8); with_profile(&p, SVMG_PROFILE_STANDARD); p.has |= SVMG_CFGP_PHI; p.phi_hard_deg = 20.0f;   /* backend rollback = phiên bản MỚI */
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_APPLY, svmg_config_check_patch(&cur, &p, &out, &r));
  TEST_ASSERT_EQUAL_FLOAT(20.0f, out.phi_hard_deg);
}
void test_string_helpers(void) {
  TEST_ASSERT_EQUAL_INT(2, svmg_profile_from_str("SENSITIVE")); TEST_ASSERT_EQUAL_INT(-1, svmg_profile_from_str("sensitive"));
  TEST_ASSERT_EQUAL_INT(1, svmg_model_from_str("BASELINE_B")); TEST_ASSERT_EQUAL_INT(-1, svmg_model_from_str(NULL));
  TEST_ASSERT_EQUAL_INT(1, svmg_scenario_from_str("S0b")); TEST_ASSERT_EQUAL_INT(5, svmg_scenario_from_str("H1")); TEST_ASSERT_EQUAL_INT(-1, svmg_scenario_from_str("S9"));
  TEST_ASSERT_EQUAL_STRING("S3", svmg_scenario_name(4));
}

/* ================= Kênh lệnh ================= */
typedef struct {
  int n_ack, n_mute, n_profile, n_thr, n_calib, n_restart, n_scn, n_mode, n_tw, n_snap, n_model;
  svmg_reason_t ret;
  uint32_t ver;
  int last_dur; uint8_t last_profile; uint16_t last_has; float last_phi;
} mock_t;
static mock_t M;
static svmg_reason_t h_ack(void *c, uint32_t id, int has) { (void)c; (void)id; (void)has; M.n_ack++; return M.ret; }
static svmg_reason_t h_mute(void *c, uint16_t d) { (void)c; M.n_mute++; M.last_dur = d; return M.ret; }
static svmg_reason_t h_prof(void *c, uint8_t p) { (void)c; M.n_profile++; M.last_profile = p; return M.ret; }
static svmg_reason_t h_thr(void *c, const svmg_cmd_t *m) { (void)c; M.n_thr++; M.last_has = m->has; M.last_phi = m->phi_hard_deg; return M.ret; }
static svmg_reason_t h_cal(void *c) { (void)c; M.n_calib++; return M.ret; }
static svmg_reason_t h_restart(void *c) { (void)c; M.n_restart++; return M.ret; }
static svmg_reason_t h_scn(void *c, uint8_t s, int sea) { (void)c; (void)s; (void)sea; M.n_scn++; return M.ret; }
static svmg_reason_t h_mode(void *c, uint8_t m) { (void)c; (void)m; M.n_mode++; return M.ret; }
static svmg_reason_t h_tw(void *c, uint8_t t) { (void)c; (void)t; M.n_tw++; return M.ret; }
static svmg_reason_t h_snap(void *c, uint16_t w) { (void)c; (void)w; M.n_snap++; return M.ret; }
static svmg_reason_t h_model(void *c, uint8_t m) { (void)c; (void)m; M.n_model++; return M.ret; }
static uint32_t h_ver(void *c) { (void)c; return M.ver; }
/* start_voyage/stop_voyage cố ý để NULL: backend không gửi xuống thiết bị. */
static svmg_cmd_hooks_t H = { NULL, h_ack, h_mute, h_prof, h_thr, h_cal, h_restart, NULL, NULL, h_scn, h_mode, h_tw, h_snap, h_model, h_ver };
static svmg_cmd_ctx_t C;
static svmg_cmd_ack_t A;

static void fresh(void) { memset(&M, 0, sizeof M); M.ret = SVMG_R_OK; M.ver = 8; svmg_cmd_init(&C); }
static svmg_cmd_t mk(const char *id, svmg_cmd_type_t t) {
  svmg_cmd_t m; memset(&m, 0, sizeof m); strncpy(m.cmd_id, id, SVMG_CMD_ID_LEN - 1); m.type = (uint8_t)t; m.ttl_s = 30; m.phi_hard_deg = NAN; return m;
}
static svmg_reason_t run(svmg_cmd_t *m) { svmg_cmd_exec(&C, &H, m, 0, &A); return A.applied ? SVMG_R_OK : A.reason; }

void test_cmd_set_profile_applied(void) {
  fresh(); svmg_cmd_t m = mk("c-1", SVMG_CMD_SET_PROFILE); m.has = SVMG_CP_PROFILE; m.profile = SVMG_PROFILE_SENSITIVE;
  TEST_ASSERT_EQUAL_INT(1, svmg_cmd_exec(&C, &H, &m, 0, &A));
  TEST_ASSERT_EQUAL_UINT8(1, A.applied); TEST_ASSERT_EQUAL_STRING("c-1", A.cmd_id); TEST_ASSERT_EQUAL_UINT32(8, A.config_version);
  TEST_ASSERT_EQUAL_INT(1, M.n_profile); TEST_ASSERT_EQUAL_UINT8(SVMG_PROFILE_SENSITIVE, M.last_profile);
  m = mk("c-1b", SVMG_CMD_SET_PROFILE); m.has = SVMG_CP_PROFILE; m.profile = 0xFF; TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run(&m));
  m = mk("c-1c", SVMG_CMD_SET_PROFILE); TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run(&m));
}
void test_cmd_set_threshold_validation_and_atomicity(void) {
  fresh(); svmg_cmd_t m;
  m = mk("t0", SVMG_CMD_SET_THRESHOLD); TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_R_BAD_PARAM, run(&m), "không tham số nào");
  m = mk("t1", SVMG_CMD_SET_THRESHOLD); m.has = SVMG_CP_PHI; m.phi_hard_deg = 40.0f; TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_R_BAD_PARAM, run(&m), "T10: phi_hard = 40");
  m = mk("t2", SVMG_CMD_SET_THRESHOLD); m.has = SVMG_CP_PHI; m.phi_hard_deg = 14.9f; TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run(&m));
  m = mk("t3", SVMG_CMD_SET_THRESHOLD); m.has = SVMG_CP_PHI; m.phi_hard_deg = NAN; TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_R_BAD_PARAM, run(&m), "sai kiểu -> NaN -> từ chối");
  m = mk("t4", SVMG_CMD_SET_THRESHOLD); m.has = SVMG_CP_MAI; m.mai_caution = 91; TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run(&m));
  m = mk("t5", SVMG_CMD_SET_THRESHOLD); m.has = SVMG_CP_DEBOUNCE; m.debounce_n = 0; TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run(&m));
  m = mk("t6", SVMG_CMD_SET_THRESHOLD); m.has = SVMG_CP_REPORT; m.report_interval_s = 3601; TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run(&m));
  m = mk("t7", SVMG_CMD_SET_THRESHOLD); m.has = SVMG_CP_PHI | SVMG_CP_MAI; m.phi_hard_deg = 18.0f; m.mai_caution = 99;   /* một hợp lệ + một sai */
  TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_R_BAD_PARAM, run(&m), "một tham số sai thì cả lệnh bị từ chối");
  TEST_ASSERT_EQUAL_INT_MESSAGE(0, M.n_thr, "tham số sai không được chạm tới hook (áp nguyên tử)");
  m = mk("t8", SVMG_CMD_SET_THRESHOLD); m.has = SVMG_CP_PHI | SVMG_CP_MAI | SVMG_CP_DEBOUNCE | SVMG_CP_REPORT;
  m.phi_hard_deg = 17.5f; m.mai_caution = 75; m.debounce_n = 4; m.report_interval_s = 10;
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run(&m)); TEST_ASSERT_EQUAL_INT(1, M.n_thr); TEST_ASSERT_EQUAL_FLOAT(17.5f, M.last_phi);
  m = mk("t9", SVMG_CMD_SET_THRESHOLD); m.has = SVMG_CP_PHI; m.phi_hard_deg = 15.0f; TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run(&m));
  m = mk("t10", SVMG_CMD_SET_THRESHOLD); m.has = SVMG_CP_PHI; m.phi_hard_deg = 25.0f; TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run(&m));
}
void test_cmd_mute_alarm_rules(void) {
  fresh(); svmg_cmd_t m = mk("m0", SVMG_CMD_MUTE_ALARM);
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run(&m)); TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_MUTE_DEFAULT_S, M.last_dur, "duration_s vắng -> mặc định 60 s");
  m = mk("m1", SVMG_CMD_MUTE_ALARM); m.has = SVMG_CP_DURATION; m.duration_s = 0;   TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run(&m));
  m = mk("m2", SVMG_CMD_MUTE_ALARM); m.has = SVMG_CP_DURATION; m.duration_s = 301; TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_R_BAD_PARAM, run(&m), "trần 300 s dù backend cho phép 600");
  m = mk("m3", SVMG_CMD_MUTE_ALARM); m.has = SVMG_CP_DURATION; m.duration_s = 300; TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run(&m)); TEST_ASSERT_EQUAL_INT(300, M.last_dur);
  M.ret = SVMG_R_FORBIDDEN_STATE;                                                                /* máy trạng thái từ chối khi CRITICAL */
  m = mk("m4", SVMG_CMD_MUTE_ALARM); TEST_ASSERT_EQUAL_INT(SVMG_R_FORBIDDEN_STATE, run(&m));
}
void test_cmd_ack_alarm_and_restart_and_voyage(void) {
  fresh(); svmg_cmd_t m = mk("a0", SVMG_CMD_ACK_ALARM); TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run(&m)); TEST_ASSERT_EQUAL_INT(1, M.n_ack);
  m = mk("r0", SVMG_CMD_RESTART_DEVICE); TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run(&m)); TEST_ASSERT_EQUAL_INT(1, M.n_restart);
  M.ret = SVMG_R_FORBIDDEN_STATE; m = mk("r1", SVMG_CMD_RESTART_DEVICE); TEST_ASSERT_EQUAL_INT(SVMG_R_FORBIDDEN_STATE, run(&m));
  M.ret = SVMG_R_OK;
  m = mk("v0", SVMG_CMD_START_VOYAGE); TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_R_UNSUPPORTED, run(&m), "backend không gửi start_voyage xuống thiết bị");
  m = mk("v1", SVMG_CMD_STOP_VOYAGE);  TEST_ASSERT_EQUAL_INT(SVMG_R_UNSUPPORTED, run(&m));
  m = mk("x0", SVMG_CMD_NONE);         TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_R_UNSUPPORTED, run(&m), "lệnh lạ (vd. tắt cảnh báo) -> UNSUPPORTED");
}
void test_cmd_idempotent_applied_and_rejected(void) {
  fresh(); svmg_cmd_t m = mk("c-2", SVMG_CMD_MUTE_ALARM); m.has = SVMG_CP_DURATION; m.duration_s = 60;
  svmg_cmd_exec(&C, &H, &m, 0, &A); TEST_ASSERT_EQUAL_INT(1, M.n_mute);
  M.ver = 99;
  TEST_ASSERT_EQUAL_INT(1, svmg_cmd_exec(&C, &H, &m, 0, &A));
  TEST_ASSERT_EQUAL_INT_MESSAGE(1, M.n_mute, "lệnh lặp không được thực thi lại");
  TEST_ASSERT_EQUAL_UINT8(1, A.applied); TEST_ASSERT_EQUAL_UINT32_MESSAGE(8, A.config_version, "trả lại kết quả cũ");
  fresh(); M.ret = SVMG_R_FORBIDDEN_STATE; m = mk("c-3", SVMG_CMD_MUTE_ALARM); m.has = SVMG_CP_DURATION; m.duration_s = 60;
  svmg_cmd_exec(&C, &H, &m, 0, &A);
  TEST_ASSERT_EQUAL_UINT8(0, A.applied); TEST_ASSERT_EQUAL_INT(SVMG_R_FORBIDDEN_STATE, A.reason);
  M.ret = SVMG_R_OK; svmg_cmd_exec(&C, &H, &m, 0, &A);
  TEST_ASSERT_EQUAL_INT(1, M.n_mute); TEST_ASSERT_EQUAL_INT(SVMG_R_FORBIDDEN_STATE, A.reason);
}
void test_cmd_calibrate_duration_param(void) {
  fresh(); svmg_cmd_t m = mk("k0", SVMG_CMD_CALIBRATE_ZERO); m.has = SVMG_CP_DURATION; m.duration_s = 10; TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run(&m));
  m = mk("k1", SVMG_CMD_CALIBRATE_ZERO); m.has = SVMG_CP_DURATION; m.duration_s = 30; TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run(&m));
  m = mk("k2", SVMG_CMD_CALIBRATE_ZERO); TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_R_OK, run(&m), "backend gửi calibrate_zero không kèm tham số");
}
void test_cmd_extension_commands_param_validation(void) {
  fresh(); svmg_cmd_t m;
  m = mk("e0", SVMG_CMD_SET_SCENARIO); m.has = SVMG_CP_SCENARIO; m.scenario = 6; TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run(&m));
  m = mk("e1", SVMG_CMD_SET_SCENARIO); m.has = SVMG_CP_SCENARIO | SVMG_CP_SEA; m.scenario = 2; m.sea_state = 6; TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run(&m));
  m = mk("e2", SVMG_CMD_SET_SCENARIO); m.has = SVMG_CP_SCENARIO | SVMG_CP_SEA; m.scenario = 2; m.sea_state = 5; TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run(&m));
  m = mk("e3", SVMG_CMD_SET_MODE); m.has = SVMG_CP_MODE; m.mode = 2; TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run(&m));
  m = mk("e4", SVMG_CMD_SET_TIMEWARP); m.has = SVMG_CP_TIMEWARP; m.timewarp = 2; TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run(&m));
  m = mk("e5", SVMG_CMD_SET_TIMEWARP); m.has = SVMG_CP_TIMEWARP; m.timewarp = 10; TEST_ASSERT_EQUAL_INT(SVMG_R_OK, run(&m));
  m = mk("e6", SVMG_CMD_REQUEST_SNAPSHOT); m.has = SVMG_CP_WINDOW; m.window_s = 181; TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run(&m));
  m = mk("e7", SVMG_CMD_SET_MODEL); m.has = SVMG_CP_MODEL; m.model = 7; TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, run(&m));
}
void test_cmd_ttl(void) {
  fresh(); svmg_cmd_t m = mk("t1", SVMG_CMD_ACK_ALARM);
  m.ttl_s = 30; m.age_s = 30;                                      /* tuổi >= TTL */
  TEST_ASSERT_EQUAL_INT(1, svmg_cmd_exec(&C, &H, &m, 0, &A)); TEST_ASSERT_EQUAL_INT(SVMG_R_EXPIRED, A.reason);
  TEST_ASSERT_EQUAL_INT_MESSAGE(0, M.n_ack, "lệnh hết hạn KHÔNG được thực thi muộn");
  m.age_s = 0; m.ttl_s = 60;                                       /* gửi lại cùng cmd_id với TTL mới -> phải xử lý */
  svmg_cmd_exec(&C, &H, &m, 0, &A); TEST_ASSERT_EQUAL_UINT8(1, A.applied); TEST_ASSERT_EQUAL_INT(1, M.n_ack);
  fresh(); m = mk("t2", SVMG_CMD_ACK_ALARM); m.ttl_s = 30;
  svmg_cmd_exec(&C, &H, &m, 29999, &A); TEST_ASSERT_EQUAL_UINT8(1, A.applied);                    /* vừa kịp */
  m = mk("t3", SVMG_CMD_ACK_ALARM); m.ttl_s = 30;
  svmg_cmd_exec(&C, &H, &m, 30000, &A); TEST_ASSERT_EQUAL_INT(SVMG_R_EXPIRED, A.reason);          /* ở trong hàng đợi quá lâu */
  m = mk("t4", SVMG_CMD_ACK_ALARM); m.ttl_s = 0;
  svmg_cmd_exec(&C, &H, &m, 0, &A); TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, A.reason);
}
void test_cmd_no_id_is_dropped(void) {
  fresh(); svmg_cmd_t m = mk("", SVMG_CMD_ACK_ALARM);
  TEST_ASSERT_EQUAL_INT(0, svmg_cmd_exec(&C, &H, &m, 0, &A)); TEST_ASSERT_EQUAL_INT(0, M.n_ack);
}
void test_cmd_cache_holds_16(void) {
  fresh(); char id[16]; svmg_cmd_t m;
  for (int i = 0; i < 16; i++) { snprintf(id, sizeof id, "k%d", i); m = mk(id, SVMG_CMD_ACK_ALARM); svmg_cmd_exec(&C, &H, &m, 0, &A); }
  TEST_ASSERT_EQUAL_INT(16, M.n_ack);
  m = mk("k0", SVMG_CMD_ACK_ALARM); svmg_cmd_exec(&C, &H, &m, 0, &A);
  TEST_ASSERT_EQUAL_INT_MESSAGE(16, M.n_ack, "16 lệnh gần nhất vẫn được nhớ");
  m = mk("k16", SVMG_CMD_ACK_ALARM); svmg_cmd_exec(&C, &H, &m, 0, &A);
  TEST_ASSERT_EQUAL_INT(17, M.n_ack);
}
void test_cmd_async_calibrate(void) {
  fresh(); M.ret = SVMG_R_PENDING;
  svmg_cmd_t m = mk("cal-1", SVMG_CMD_CALIBRATE_ZERO);
  TEST_ASSERT_EQUAL_INT(0, svmg_cmd_exec(&C, &H, &m, 0, &A));                 /* chưa có ack */
  TEST_ASSERT_EQUAL_INT(0, svmg_cmd_exec(&C, &H, &m, 0, &A));                 /* backend gửi lại: im lặng, không chạy lần 2 */
  TEST_ASSERT_EQUAL_INT(1, M.n_calib);
  M.ver = 9;
  TEST_ASSERT_EQUAL_INT(1, svmg_cmd_complete(&C, "cal-1", SVMG_R_OK, 9, &A));
  TEST_ASSERT_EQUAL_UINT8(1, A.applied); TEST_ASSERT_EQUAL_UINT32(9, A.config_version);
  TEST_ASSERT_EQUAL_INT(1, svmg_cmd_exec(&C, &H, &m, 0, &A));                 /* gửi lại sau khi xong: trả kết quả đã có */
  TEST_ASSERT_EQUAL_UINT8(1, A.applied); TEST_ASSERT_EQUAL_INT(1, M.n_calib);
  TEST_ASSERT_EQUAL_INT(0, svmg_cmd_complete(&C, "cal-1", SVMG_R_OK, 9, &A)); /* không hoàn tất hai lần */
  fresh(); M.ret = SVMG_R_PENDING; m = mk("cal-2", SVMG_CMD_CALIBRATE_ZERO); svmg_cmd_exec(&C, &H, &m, 0, &A);
  svmg_cmd_complete(&C, "cal-2", SVMG_R_NOT_STATIC, 8, &A);
  TEST_ASSERT_EQUAL_UINT8(0, A.applied); TEST_ASSERT_EQUAL_INT(SVMG_R_NOT_STATIC, A.reason);
}
void test_cmd_missing_hook_is_unsupported(void) {
  fresh(); svmg_cmd_hooks_t h2 = H; h2.set_threshold = NULL;
  svmg_cmd_t m = mk("u1", SVMG_CMD_SET_THRESHOLD); m.has = SVMG_CP_PHI; m.phi_hard_deg = 20.0f;
  svmg_cmd_exec(&C, &h2, &m, 0, &A); TEST_ASSERT_EQUAL_INT(SVMG_R_UNSUPPORTED, A.reason);
}
void test_reason_names_match_spec(void) {
  TEST_ASSERT_EQUAL_STRING("BAD_PARAM", svmg_reason_name(SVMG_R_BAD_PARAM));
  TEST_ASSERT_EQUAL_STRING("FORBIDDEN_STATE", svmg_reason_name(SVMG_R_FORBIDDEN_STATE));
  TEST_ASSERT_EQUAL_STRING("NOT_STATIC", svmg_reason_name(SVMG_R_NOT_STATIC));
  TEST_ASSERT_EQUAL_STRING("EXPIRED", svmg_reason_name(SVMG_R_EXPIRED));
  TEST_ASSERT_EQUAL_STRING("UNSUPPORTED", svmg_reason_name(SVMG_R_UNSUPPORTED));
}

/* ================= Hiệu chuẩn ================= */
static svmg_calib_t K;
static int feed_calib(float base_r, float base_p, float noise_r, int invalid_count) {
  svmg_calib_start(&K); int done = 0;
  for (int i = 0; i < SVMG_CALIB_SAMPLES; i++) {
    float r = base_r + ((i % 2) ? noise_r : -noise_r), p = base_p;
    done = svmg_calib_push(&K, r, p, i >= invalid_count);          /* invalid_count mẫu đầu thiếu */
    if (i < SVMG_CALIB_SAMPLES - 1) TEST_ASSERT_EQUAL_INT(0, done);
  }
  return done;
}
void test_calib_static_ok(void) {
  TEST_ASSERT_EQUAL_INT(1, feed_calib(2.0f, -1.0f, 0.1f, 0));
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, K.result);
  TEST_ASSERT_FLOAT_WITHIN(1e-3f, 2.0f, K.result_roll_deg); TEST_ASSERT_FLOAT_WITHIN(1e-3f, -1.0f, K.result_pitch_deg);
  TEST_ASSERT_FALSE(K.active);
}
void test_calib_not_static(void) { TEST_ASSERT_EQUAL_INT(1, feed_calib(2.0f, 0.0f, 0.8f, 0)); TEST_ASSERT_EQUAL_INT(SVMG_R_NOT_STATIC, K.result); }
void test_calib_missing_data(void) {
  feed_calib(2.0f, 0.0f, 0.05f, 30);  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, K.result);               /* 6/60 = 10%: còn chấp nhận */
  feed_calib(2.0f, 0.0f, 0.05f, 31);  TEST_ASSERT_EQUAL_INT(SVMG_R_FORBIDDEN_STATE, K.result);  /* 7/60 > 10% */
}
void test_calib_large_offset_refused(void) {
  feed_calib(12.0f, 0.0f, 0.05f, 0); TEST_ASSERT_EQUAL_INT(SVMG_R_FORBIDDEN_STATE, K.result);  /* không dùng để che nghiêng thật */
  feed_calib(10.0f, 0.0f, 0.05f, 0); TEST_ASSERT_EQUAL_INT(SVMG_R_OK, K.result);
}
void test_calib_inactive_ignores_samples_and_abort(void) {
  svmg_calib_init(&K); TEST_ASSERT_EQUAL_INT(0, svmg_calib_push(&K, 1, 1, 1));
  svmg_calib_start(&K); svmg_calib_push(&K, 1, 1, 1); svmg_calib_abort(&K);
  for (int i = 0; i < 100; i++) TEST_ASSERT_EQUAL_INT(0, svmg_calib_push(&K, 1, 1, 1));
}

int main(void) {
  UNITY_BEGIN();
  RUN_TEST(test_crc16_check_value);
  RUN_TEST(test_profiles); RUN_TEST(test_validate_bounds_follow_schema); RUN_TEST(test_patch_keeps_absent_fields_and_local_calibration);
  RUN_TEST(test_patch_profile_defaults_then_explicit_fields_override); RUN_TEST(test_patch_verdicts);
  RUN_TEST(test_rollback_is_a_newer_version_with_old_content); RUN_TEST(test_string_helpers);
  RUN_TEST(test_cmd_set_profile_applied); RUN_TEST(test_cmd_set_threshold_validation_and_atomicity); RUN_TEST(test_cmd_mute_alarm_rules);
  RUN_TEST(test_cmd_ack_alarm_and_restart_and_voyage); RUN_TEST(test_cmd_idempotent_applied_and_rejected); RUN_TEST(test_cmd_calibrate_duration_param);
  RUN_TEST(test_cmd_extension_commands_param_validation); RUN_TEST(test_cmd_ttl); RUN_TEST(test_cmd_no_id_is_dropped);
  RUN_TEST(test_cmd_cache_holds_16); RUN_TEST(test_cmd_async_calibrate); RUN_TEST(test_cmd_missing_hook_is_unsupported); RUN_TEST(test_reason_names_match_spec);
  RUN_TEST(test_calib_static_ok); RUN_TEST(test_calib_not_static); RUN_TEST(test_calib_missing_data);
  RUN_TEST(test_calib_large_offset_refused); RUN_TEST(test_calib_inactive_ignores_samples_and_abort);
  return UNITY_END();
}
