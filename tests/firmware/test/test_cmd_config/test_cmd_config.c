/* Test M1-07: cấu hình có phiên bản + CRC, kênh lệnh idempotent/TTL/mã từ chối, hiệu chuẩn. */
#include <unity.h>
#include <string.h>
#include <stdio.h>
#include "svmg_cmd.h"
#include "svmg_config.h"
#include "svmg_calib.h"
#include "svmg_testutil.h"

void setUp(void) {}
void tearDown(void) {}

/* ================= CRC & cấu hình ================= */
void test_crc16_check_value(void) {
  TEST_ASSERT_EQUAL_HEX16(0x29B1, svmg_crc16_ccitt("123456789", 9));      /* giá trị chuẩn CRC-16/CCITT-FALSE */
}
static svmg_config_t cfg_of(uint32_t ver, int profile, int n, int phi, int mai, int rep, int model) {
  svmg_config_t c; memset(&c, 0, sizeof c);
  c.config_version = ver; c.profile = (uint8_t)profile; c.debounce_n = (uint8_t)n; c.phi_hard_deg = (uint8_t)phi;
  c.mai_caution = (uint8_t)mai; c.report_interval_s = (uint8_t)rep; c.primary_model = (uint8_t)model;
  return c;
}
void test_canonical_string_and_crc(void) {
  svmg_config_t c = cfg_of(8, SVMG_PROFILE_SENSITIVE, 2, 20, 70, 5, SVMG_MODEL_RF);
  char buf[96]; svmg_config_canonical(&c, buf, sizeof buf);
  TEST_ASSERT_EQUAL_STRING("v=8;p=SENSITIVE;n=2;phi=20;mai=70;rep=5;m=RF", buf);
  TEST_ASSERT_EQUAL_HEX16(0x498B, svmg_config_crc(&c));                  /* tính độc lập bằng binascii.crc_hqx */
  c = cfg_of(2, SVMG_PROFILE_CONSERVATIVE, 4, 18, 85, 10, SVMG_MODEL_BASELINE_B);
  TEST_ASSERT_EQUAL_HEX16(0xCA04, svmg_config_crc(&c));
}
void test_profiles(void) {
  svmg_config_t c; svmg_config_default(&c, SVMG_MODEL_RF);
  TEST_ASSERT_EQUAL_UINT8(3, c.debounce_n); TEST_ASSERT_EQUAL_UINT8(80, c.mai_caution);
  svmg_config_apply_profile(&c, SVMG_PROFILE_SENSITIVE); TEST_ASSERT_EQUAL_UINT8(2, c.debounce_n); TEST_ASSERT_EQUAL_UINT8(70, c.mai_caution);
  svmg_config_apply_profile(&c, SVMG_PROFILE_CONSERVATIVE); TEST_ASSERT_EQUAL_UINT8(4, c.debounce_n); TEST_ASSERT_EQUAL_UINT8(85, c.mai_caution);
  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, svmg_config_validate(&c));
  TEST_ASSERT_EQUAL_UINT8(20, c.phi_hard_deg);
}
void test_validate_bounds(void) {
  svmg_config_t g; svmg_config_default(&g, SVMG_MODEL_RF);
  struct { int field; int val; } bad[] = { {0,14},{0,26},{0,40},{0,0},{1,0},{1,7},{2,29},{2,96},{3,4},{3,7},{3,65},{3,0},{4,2},{5,3} };
  for (unsigned i = 0; i < sizeof bad / sizeof bad[0]; i++) {
    svmg_config_t c = g;
    switch (bad[i].field) {
      case 0: c.phi_hard_deg = (uint8_t)bad[i].val; break; case 1: c.debounce_n = (uint8_t)bad[i].val; break;
      case 2: c.mai_caution = (uint8_t)bad[i].val; break; case 3: c.report_interval_s = (uint8_t)bad[i].val; break;
      case 4: c.primary_model = (uint8_t)bad[i].val; break; case 5: c.profile = (uint8_t)bad[i].val; break;
    }
    TEST_ASSERT_EQUAL_INT_MESSAGE(SVMG_R_BAD_PARAM, svmg_config_validate(&c), "ngoài biên phải bị từ chối");
  }
  svmg_config_t c = g; c.phi_hard_deg = 15; TEST_ASSERT_EQUAL_INT(SVMG_R_OK, svmg_config_validate(&c));
  c.phi_hard_deg = 25; TEST_ASSERT_EQUAL_INT(SVMG_R_OK, svmg_config_validate(&c));
  c = g; c.zero_roll_deg = 10.5f; TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, svmg_config_validate(&c));
  c = g; c.zero_pitch_deg = NAN; TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, svmg_config_validate(&c));
}
void test_config_update_verdicts(void) {
  svmg_config_t cur = cfg_of(8, SVMG_PROFILE_SENSITIVE, 2, 20, 70, 5, SVMG_MODEL_RF);
  cur.zero_roll_deg = 1.5f; cur.zero_pitch_deg = -0.5f;
  svmg_reason_t r;
  svmg_config_t nx = cfg_of(9, SVMG_PROFILE_STANDARD, 3, 20, 80, 5, SVMG_MODEL_RF);
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_APPLY, svmg_config_check_update(&cur, &nx, 0x76DA, &r)); TEST_ASSERT_EQUAL_INT(SVMG_R_OK, r);
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_REJECT, svmg_config_check_update(&cur, &nx, 0x76DB, &r));    /* sai CRC */
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, r);
  svmg_config_t evil = cfg_of(10, SVMG_PROFILE_STANDARD, 3, 40, 80, 5, SVMG_MODEL_RF);         /* T10: phi_hard = 40, CRC đúng */
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_REJECT, svmg_config_check_update(&cur, &evil, 0x8DEA, &r));
  TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, r);
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_DUPLICATE, svmg_config_check_update(&cur, &cur, 0x498B, &r));  /* retained gửi lại */
  svmg_config_t stale = cfg_of(3, SVMG_PROFILE_STANDARD, 3, 20, 80, 5, SVMG_MODEL_RF);
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_REJECT, svmg_config_check_update(&cur, &stale, 0x809E, &r));   /* phiên bản cũ */
  svmg_config_t same_ver_diff = cfg_of(8, SVMG_PROFILE_STANDARD, 3, 20, 80, 5, SVMG_MODEL_RF);
  uint16_t crc = svmg_config_crc(&same_ver_diff);
  TEST_ASSERT_EQUAL_INT(SVMG_CFG_REJECT, svmg_config_check_update(&cur, &same_ver_diff, crc, &r)); /* cùng phiên bản khác nội dung */
}

/* ================= Kênh lệnh ================= */
typedef struct {
  int n_ack, n_mute, n_profile, n_calib, n_scn, n_mode, n_tw, n_snap, n_model;
  svmg_reason_t ret;            /* mã trả về của mọi hook */
  uint32_t ver;
  int last_sea, last_dur; uint8_t last_profile;
} mock_t;
static mock_t M;
static svmg_reason_t h_ack(void *c, uint32_t id, int has) { (void)c; (void)id; (void)has; M.n_ack++; return M.ret; }
static svmg_reason_t h_mute(void *c, uint16_t d) { (void)c; M.n_mute++; M.last_dur = d; return M.ret; }
static svmg_reason_t h_prof(void *c, uint8_t p) { (void)c; M.n_profile++; M.last_profile = p; return M.ret; }
static svmg_reason_t h_cal(void *c) { (void)c; M.n_calib++; return M.ret; }
static svmg_reason_t h_scn(void *c, uint8_t s, int sea) { (void)c; (void)s; M.n_scn++; M.last_sea = sea; return M.ret; }
static svmg_reason_t h_mode(void *c, uint8_t m) { (void)c; (void)m; M.n_mode++; return M.ret; }
static svmg_reason_t h_tw(void *c, uint8_t t) { (void)c; (void)t; M.n_tw++; return M.ret; }
static svmg_reason_t h_snap(void *c, uint16_t w) { (void)c; (void)w; M.n_snap++; return M.ret; }
static svmg_reason_t h_model(void *c, uint8_t m) { (void)c; (void)m; M.n_model++; return M.ret; }
static uint32_t h_ver(void *c) { (void)c; return M.ver; }
static svmg_cmd_hooks_t H = { NULL, h_ack, h_mute, h_prof, h_cal, h_scn, h_mode, h_tw, h_snap, h_model, h_ver };
static svmg_cmd_ctx_t C;
static svmg_cmd_ack_t A;

static void fresh(void) { memset(&M, 0, sizeof M); M.ret = SVMG_R_OK; M.ver = 8; svmg_cmd_init(&C); }
static svmg_cmd_t mk(const char *id, svmg_cmd_type_t t) {
  svmg_cmd_t m; memset(&m, 0, sizeof m); strncpy(m.cmd_id, id, SVMG_CMD_ID_LEN - 1); m.type = (uint8_t)t; m.ttl_s = 30; return m;
}

void test_cmd_basic_applied(void) {
  fresh(); svmg_cmd_t m = mk("c-1", SVMG_CMD_SET_PROFILE); m.has = SVMG_CP_PROFILE; m.profile = SVMG_PROFILE_SENSITIVE;
  TEST_ASSERT_EQUAL_INT(1, svmg_cmd_exec(&C, &H, &m, 0, &A));
  TEST_ASSERT_EQUAL_UINT8(1, A.applied); TEST_ASSERT_EQUAL_STRING("c-1", A.cmd_id); TEST_ASSERT_EQUAL_UINT32(8, A.config_version);
  TEST_ASSERT_EQUAL_INT(1, M.n_profile); TEST_ASSERT_EQUAL_UINT8(SVMG_PROFILE_SENSITIVE, M.last_profile);
}
void test_cmd_idempotent_applied_and_rejected(void) {
  fresh(); svmg_cmd_t m = mk("c-2", SVMG_CMD_MUTE); m.has = SVMG_CP_DURATION; m.duration_s = 60;
  svmg_cmd_exec(&C, &H, &m, 0, &A); TEST_ASSERT_EQUAL_INT(1, M.n_mute);
  M.ver = 99;                                                         /* thay đổi trạng thái sau đó */
  TEST_ASSERT_EQUAL_INT(1, svmg_cmd_exec(&C, &H, &m, 0, &A));
  TEST_ASSERT_EQUAL_INT_MESSAGE(1, M.n_mute, "lệnh lặp không được thực thi lại");
  TEST_ASSERT_EQUAL_UINT8(1, A.applied); TEST_ASSERT_EQUAL_UINT32_MESSAGE(8, A.config_version, "trả lại kết quả cũ");
  /* bị từ chối cũng được nhớ */
  fresh(); M.ret = SVMG_R_FORBIDDEN_STATE; m = mk("c-3", SVMG_CMD_MUTE); m.has = SVMG_CP_DURATION; m.duration_s = 60;
  svmg_cmd_exec(&C, &H, &m, 0, &A);
  TEST_ASSERT_EQUAL_UINT8(0, A.applied); TEST_ASSERT_EQUAL_INT(SVMG_R_FORBIDDEN_STATE, A.reason);
  M.ret = SVMG_R_OK;
  svmg_cmd_exec(&C, &H, &m, 0, &A);
  TEST_ASSERT_EQUAL_INT(1, M.n_mute); TEST_ASSERT_EQUAL_INT(SVMG_R_FORBIDDEN_STATE, A.reason);
}
void test_cmd_mute_param_validation(void) {
  fresh(); svmg_cmd_t m = mk("m0", SVMG_CMD_MUTE); m.has = SVMG_CP_DURATION;
  m.duration_s = 0;   svmg_cmd_exec(&C, &H, &m, 0, &A); TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, A.reason);
  strcpy(m.cmd_id, "m1"); m.duration_s = 301; svmg_cmd_exec(&C, &H, &m, 0, &A); TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, A.reason);
  strcpy(m.cmd_id, "m2"); m.has = 0;          svmg_cmd_exec(&C, &H, &m, 0, &A); TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, A.reason);
  TEST_ASSERT_EQUAL_INT_MESSAGE(0, M.n_mute, "tham số sai không được chạm tới hook");
  strcpy(m.cmd_id, "m3"); m.has = SVMG_CP_DURATION; m.duration_s = 300; svmg_cmd_exec(&C, &H, &m, 0, &A); TEST_ASSERT_EQUAL_UINT8(1, A.applied);
}
void test_cmd_param_validation_all(void) {
  fresh(); svmg_cmd_t m; int k = 0; char id[16];
#define EXP(reason_expected, init) do { m = mk((snprintf(id, sizeof id, "x%d", k++), id), SVMG_CMD_NONE); init; svmg_cmd_exec(&C, &H, &m, 0, &A); TEST_ASSERT_EQUAL_INT(reason_expected, A.reason); } while (0)
  EXP(SVMG_R_BAD_PARAM, (m.type = SVMG_CMD_SET_PROFILE, m.has = SVMG_CP_PROFILE, m.profile = 0xFF));      /* chuỗi lạ -> 0xFF */
  EXP(SVMG_R_BAD_PARAM, (m.type = SVMG_CMD_SET_PROFILE, m.has = 0));
  EXP(SVMG_R_BAD_PARAM, (m.type = SVMG_CMD_CALIBRATE_ZERO, m.has = SVMG_CP_DURATION, m.duration_s = 10));
  EXP(SVMG_R_OK,        (m.type = SVMG_CMD_CALIBRATE_ZERO, m.has = SVMG_CP_DURATION, m.duration_s = 30));
  EXP(SVMG_R_BAD_PARAM, (m.type = SVMG_CMD_SET_SCENARIO, m.has = SVMG_CP_SCENARIO, m.scenario = 6));
  EXP(SVMG_R_BAD_PARAM, (m.type = SVMG_CMD_SET_SCENARIO, m.has = SVMG_CP_SCENARIO | SVMG_CP_SEA, m.scenario = 2, m.sea_state = 6));
  EXP(SVMG_R_OK,        (m.type = SVMG_CMD_SET_SCENARIO, m.has = SVMG_CP_SCENARIO | SVMG_CP_SEA, m.scenario = 2, m.sea_state = 5));
  EXP(SVMG_R_BAD_PARAM, (m.type = SVMG_CMD_SET_MODE, m.has = SVMG_CP_MODE, m.mode = 2));
  EXP(SVMG_R_BAD_PARAM, (m.type = SVMG_CMD_SET_TIMEWARP, m.has = SVMG_CP_TIMEWARP, m.timewarp = 2));
  EXP(SVMG_R_OK,        (m.type = SVMG_CMD_SET_TIMEWARP, m.has = SVMG_CP_TIMEWARP, m.timewarp = 10));
  EXP(SVMG_R_BAD_PARAM, (m.type = SVMG_CMD_REQUEST_SNAPSHOT, m.has = SVMG_CP_WINDOW, m.window_s = 0));
  EXP(SVMG_R_BAD_PARAM, (m.type = SVMG_CMD_REQUEST_SNAPSHOT, m.has = SVMG_CP_WINDOW, m.window_s = 181));
  EXP(SVMG_R_OK,        (m.type = SVMG_CMD_REQUEST_SNAPSHOT, m.has = SVMG_CP_WINDOW, m.window_s = 180));
  EXP(SVMG_R_BAD_PARAM, (m.type = SVMG_CMD_SET_MODEL, m.has = SVMG_CP_MODEL, m.model = 7));
  EXP(SVMG_R_OK,        (m.type = SVMG_CMD_SET_MODEL, m.has = SVMG_CP_MODEL, m.model = SVMG_MODEL_BASELINE_B));
  EXP(SVMG_R_UNSUPPORTED, (m.type = SVMG_CMD_NONE));
  EXP(SVMG_R_OK,        (m.type = SVMG_CMD_ACK));
#undef EXP
}
void test_cmd_scenario_sea_optional(void) {
  fresh(); svmg_cmd_t m = mk("s1", SVMG_CMD_SET_SCENARIO); m.has = SVMG_CP_SCENARIO; m.scenario = 3;
  svmg_cmd_exec(&C, &H, &m, 0, &A); TEST_ASSERT_EQUAL_INT(-1, M.last_sea);
}
void test_cmd_ttl(void) {
  fresh(); svmg_cmd_t m = mk("t1", SVMG_CMD_ACK);
  m.ttl_s = 30; m.age_s = 30;                                      /* tuổi >= TTL */
  TEST_ASSERT_EQUAL_INT(1, svmg_cmd_exec(&C, &H, &m, 0, &A)); TEST_ASSERT_EQUAL_INT(SVMG_R_EXPIRED, A.reason);
  TEST_ASSERT_EQUAL_INT(0, M.n_ack);
  m.age_s = 0; m.ttl_s = 60;                                       /* gửi lại cùng cmd_id với TTL mới -> phải xử lý */
  svmg_cmd_exec(&C, &H, &m, 0, &A); TEST_ASSERT_EQUAL_UINT8(1, A.applied); TEST_ASSERT_EQUAL_INT(1, M.n_ack);
  fresh(); m = mk("t2", SVMG_CMD_ACK); m.ttl_s = 30;
  svmg_cmd_exec(&C, &H, &m, 29999, &A); TEST_ASSERT_EQUAL_UINT8(1, A.applied);         /* vừa kịp */
  m = mk("t3", SVMG_CMD_ACK); m.ttl_s = 30;
  svmg_cmd_exec(&C, &H, &m, 30000, &A); TEST_ASSERT_EQUAL_INT(SVMG_R_EXPIRED, A.reason); /* ở trong hàng đợi quá lâu */
  m = mk("t4", SVMG_CMD_ACK); m.ttl_s = 0;
  svmg_cmd_exec(&C, &H, &m, 0, &A); TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, A.reason);
}
void test_cmd_no_id_is_dropped(void) {
  fresh(); svmg_cmd_t m = mk("", SVMG_CMD_ACK);
  TEST_ASSERT_EQUAL_INT(0, svmg_cmd_exec(&C, &H, &m, 0, &A)); TEST_ASSERT_EQUAL_INT(0, M.n_ack);
}
void test_cmd_cache_holds_16(void) {
  fresh(); char id[16]; svmg_cmd_t m;
  for (int i = 0; i < 16; i++) { snprintf(id, sizeof id, "k%d", i); m = mk(id, SVMG_CMD_ACK); svmg_cmd_exec(&C, &H, &m, 0, &A); }
  TEST_ASSERT_EQUAL_INT(16, M.n_ack);
  m = mk("k0", SVMG_CMD_ACK); svmg_cmd_exec(&C, &H, &m, 0, &A);
  TEST_ASSERT_EQUAL_INT_MESSAGE(16, M.n_ack, "16 lệnh gần nhất vẫn được nhớ");
  m = mk("k16", SVMG_CMD_ACK); svmg_cmd_exec(&C, &H, &m, 0, &A);        /* lệnh thứ 17 đẩy bớt một lệnh cũ */
  TEST_ASSERT_EQUAL_INT(17, M.n_ack);
  for (int i = 1; i <= 16; i++) { snprintf(id, sizeof id, "k%d", i); m = mk(id, SVMG_CMD_ACK); svmg_cmd_exec(&C, &H, &m, 0, &A); }
  TEST_ASSERT_TRUE_MESSAGE(M.n_ack <= 18, "tối đa một lệnh bị quên");
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
  TEST_ASSERT_EQUAL_INT(0, svmg_cmd_complete(&C, "nope", SVMG_R_OK, 9, &A));
  /* thất bại NOT_STATIC */
  fresh(); M.ret = SVMG_R_PENDING; m = mk("cal-2", SVMG_CMD_CALIBRATE_ZERO); svmg_cmd_exec(&C, &H, &m, 0, &A);
  svmg_cmd_complete(&C, "cal-2", SVMG_R_NOT_STATIC, 8, &A);
  TEST_ASSERT_EQUAL_UINT8(0, A.applied); TEST_ASSERT_EQUAL_INT(SVMG_R_NOT_STATIC, A.reason);
}
void test_cmd_missing_hook_is_unsupported(void) {
  fresh(); svmg_cmd_hooks_t h2 = H; h2.set_model = NULL;
  svmg_cmd_t m = mk("u1", SVMG_CMD_SET_MODEL); m.has = SVMG_CP_MODEL; m.model = 0;
  svmg_cmd_exec(&C, &h2, &m, 0, &A); TEST_ASSERT_EQUAL_INT(SVMG_R_UNSUPPORTED, A.reason);
}
void test_reason_names_match_spec(void) {
  TEST_ASSERT_EQUAL_STRING("BAD_PARAM", svmg_reason_name(SVMG_R_BAD_PARAM));
  TEST_ASSERT_EQUAL_STRING("FORBIDDEN_STATE", svmg_reason_name(SVMG_R_FORBIDDEN_STATE));
  TEST_ASSERT_EQUAL_STRING("NOT_STATIC", svmg_reason_name(SVMG_R_NOT_STATIC));
  TEST_ASSERT_EQUAL_STRING("EXPIRED", svmg_reason_name(SVMG_R_EXPIRED));
  TEST_ASSERT_EQUAL_STRING("UNSUPPORTED", svmg_reason_name(SVMG_R_UNSUPPORTED));
}
void test_enum_string_helpers(void) {
  TEST_ASSERT_EQUAL_INT(2, svmg_profile_from_str("SENSITIVE")); TEST_ASSERT_EQUAL_INT(-1, svmg_profile_from_str("sensitive"));
  TEST_ASSERT_EQUAL_INT(1, svmg_model_from_str("BASELINE_B")); TEST_ASSERT_EQUAL_INT(-1, svmg_model_from_str(NULL));
  TEST_ASSERT_EQUAL_INT(1, svmg_scenario_from_str("S0b")); TEST_ASSERT_EQUAL_INT(5, svmg_scenario_from_str("H1")); TEST_ASSERT_EQUAL_INT(-1, svmg_scenario_from_str("S9"));
  TEST_ASSERT_EQUAL_STRING("S3", svmg_scenario_name(4));
}

/* ================= Hiệu chuẩn ================= */
static svmg_calib_t K;
static int feed_calib(float base_r, float base_p, float noise_r, int invalid_count) {
  svmg_calib_start(&K); int done = 0;
  for (int i = 0; i < SVMG_CALIB_SAMPLES; i++) {
    float r = base_r + ((i % 2) ? noise_r : -noise_r), p = base_p + ((i % 2) ? 0.0f : 0.0f);
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
void test_calib_not_static(void) {
  TEST_ASSERT_EQUAL_INT(1, feed_calib(2.0f, 0.0f, 0.8f, 0));        /* std ~ 0.8 > 0.5 */
  TEST_ASSERT_EQUAL_INT(SVMG_R_NOT_STATIC, K.result);
}
void test_calib_missing_data(void) {
  feed_calib(2.0f, 0.0f, 0.05f, 6);  TEST_ASSERT_EQUAL_INT(SVMG_R_OK, K.result);               /* 6/60 = 10%: còn chấp nhận */
  feed_calib(2.0f, 0.0f, 0.05f, 7);  TEST_ASSERT_EQUAL_INT(SVMG_R_FORBIDDEN_STATE, K.result);  /* 7/60 > 10% */
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
  RUN_TEST(test_crc16_check_value); RUN_TEST(test_canonical_string_and_crc); RUN_TEST(test_profiles);
  RUN_TEST(test_validate_bounds); RUN_TEST(test_config_update_verdicts);
  RUN_TEST(test_cmd_basic_applied); RUN_TEST(test_cmd_idempotent_applied_and_rejected); RUN_TEST(test_cmd_mute_param_validation);
  RUN_TEST(test_cmd_param_validation_all); RUN_TEST(test_cmd_scenario_sea_optional); RUN_TEST(test_cmd_ttl);
  RUN_TEST(test_cmd_no_id_is_dropped); RUN_TEST(test_cmd_cache_holds_16); RUN_TEST(test_cmd_async_calibrate);
  RUN_TEST(test_cmd_missing_hook_is_unsupported); RUN_TEST(test_reason_names_match_spec); RUN_TEST(test_enum_string_helpers);
  RUN_TEST(test_calib_static_ok); RUN_TEST(test_calib_not_static); RUN_TEST(test_calib_missing_data);
  RUN_TEST(test_calib_large_offset_refused); RUN_TEST(test_calib_inactive_ignores_samples_and_abort);
  return UNITY_END();
}
