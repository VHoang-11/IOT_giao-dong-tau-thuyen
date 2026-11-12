/* Test chuỗi sự kiện của máy trạng thái cảnh báo (M1-05) - nền của T09 phía thiết bị. */
#include <unity.h>
#include "svmg_alarm.h"
#include "svmg_testutil.h"

void setUp(void) {}
void tearDown(void) {}

static svmg_alarm_t A;
static svmg_event_t EV[SVMG_ALARM_MAX_EVENTS];
static float T;                       /* đồng hồ mô phỏng, +5 s mỗi lần cập nhật */

static void fresh(int n) {
  svmg_alarm_cfg_t c; svmg_alarm_default_cfg(&c); c.debounce_n = (uint8_t)n;   /* mai_caution 80, clear 6, T_ack 60 s */
  svmg_alarm_init(&A, &c); T = 0;
}
static int upd(svmg_class_t cls, svmg_status_t st, int mai, int hard, uint32_t now) {
  svmg_alarm_in_t in = { cls, st, (uint8_t)mai, 1, (uint8_t)hard, 0, now };
  T += 5.0f; in.t_sim_s = T;
  return svmg_alarm_update(&A, &in, EV);
}
#define OKU(cls, now) upd((cls), SVMG_ST_OK, 0, 0, (now))
static svmg_alarm_out_t outs(uint32_t now) { svmg_alarm_out_t o; svmg_alarm_outputs(&A, now, &o); return o; }
static void to_warning(uint32_t now) { for (int i = 0; i < 3; i++) OKU(SVMG_HIGH_ROLL, now); }

void test_normal_stays_normal(void) {
  fresh(3);
  for (int i = 0; i < 50; i++) TEST_ASSERT_EQUAL_INT(0, OKU(SVMG_NORMAL, 1000));
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_NORMAL, A.level);
  svmg_alarm_out_t o = outs(0); TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_ON, o.led_g); TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_OFF, o.buzzer);
}
void test_caution_then_warning_after_N(void) {
  fresh(3);
  int n = OKU(SVMG_HIGH_ROLL, 100);                       /* lần 1 -> CAUTION */
  TEST_ASSERT_EQUAL_INT(1, n); TEST_ASSERT_EQUAL_INT(SVMG_LVL_CAUTION, A.level);
  TEST_ASSERT_EQUAL_UINT32(0, EV[0].alarm_id);            /* CAUTION chưa có alarm_id */
  svmg_alarm_out_t o = outs(0); TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_ON, o.led_y); TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_OFF, o.buzzer);
  TEST_ASSERT_EQUAL_INT(0, OKU(SVMG_HIGH_ROLL, 200));     /* lần 2: vẫn CAUTION, không sự kiện */
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_CAUTION, A.level);
  n = OKU(SVMG_HIGH_ROLL, 300);                           /* lần 3 -> WARNING (15 s mô phỏng) */
  TEST_ASSERT_EQUAL_INT(1, n); TEST_ASSERT_EQUAL_INT(SVMG_LVL_WARNING, A.level);
  TEST_ASSERT_EQUAL_UINT8(SVMG_EV_ALARM_STATE, EV[0].type);
  TEST_ASSERT_EQUAL_UINT8(SVMG_LVL_WARNING, EV[0].level); TEST_ASSERT_EQUAL_UINT8(SVMG_LVL_CAUTION, EV[0].prev_level);
  TEST_ASSERT_EQUAL_UINT32(1, EV[0].alarm_id); TEST_ASSERT_EQUAL_UINT8(SVMG_HIGH_ROLL, EV[0].cls);
  o = outs(0); TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_ON, o.led_r); TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_INTERMITTENT, o.buzzer);
}
void test_debounce_N_profiles(void) {
  for (int n = 1; n <= 4; n++) {
    fresh(n);
    for (int i = 0; i < n - 1; i++) OKU(SVMG_HIGH_ROLL, 0);
    if (n > 1) TEST_ASSERT_EQUAL_INT(SVMG_LVL_CAUTION, A.level);
    OKU(SVMG_HIGH_ROLL, 0);
    TEST_ASSERT_EQUAL_INT(SVMG_LVL_WARNING, A.level);
  }
}
void test_streak_broken_by_other_class_or_normal(void) {
  fresh(3);
  OKU(SVMG_HIGH_ROLL, 0); OKU(SVMG_AMPLITUDE_GROWTH, 0); OKU(SVMG_HIGH_ROLL, 0);
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_CAUTION, A.level);      /* khác lớp -> chuỗi đếm về 1 */
  fresh(3);
  OKU(SVMG_HIGH_ROLL, 0); OKU(SVMG_HIGH_ROLL, 0); OKU(SVMG_NORMAL, 0); OKU(SVMG_HIGH_ROLL, 0);
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_CAUTION, A.level);
}
void test_mai_alone_gives_caution_only_and_clears(void) {
  fresh(3);
  for (int i = 0; i < 20; i++) upd(SVMG_NORMAL, SVMG_ST_OK, 85, 0, 0);
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_CAUTION, A.level);       /* không bao giờ lên WARNING chỉ vì MAI */
  for (int i = 0; i < 5; i++) upd(SVMG_NORMAL, SVMG_ST_OK, 10, 0, 0);
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_CAUTION, A.level);
  upd(SVMG_NORMAL, SVMG_ST_OK, 10, 0, 0);
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_NORMAL, A.level);
}
void test_ack_silences_but_keeps_led_and_no_escalation(void) {
  fresh(3); to_warning(1000);
  int n = svmg_alarm_ack(&A, SVMG_ACKBY_BUTTON, 9000, EV, NULL);
  TEST_ASSERT_EQUAL_INT(1, n); TEST_ASSERT_EQUAL_UINT8(SVMG_EV_ALARM_ACK, EV[0].type);
  TEST_ASSERT_EQUAL_UINT8(SVMG_ACKBY_BUTTON, EV[0].acked_by); TEST_ASSERT_EQUAL_UINT32(1, EV[0].alarm_id);
  svmg_alarm_out_t o = outs(9000); TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_ON, o.led_r); TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_OFF, o.buzzer);
  TEST_ASSERT_EQUAL_INT(0, svmg_alarm_tick(&A, 1000 + 600000u, EV));      /* đã ACK: không leo thang */
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_WARNING, A.level);
  TEST_ASSERT_EQUAL_INT(0, svmg_alarm_ack(&A, SVMG_ACKBY_BUTTON, 9500, EV, NULL));   /* ACK lần 2: không sự kiện */
  TEST_ASSERT_EQUAL_UINT32(1, A.n_acked);
}
void test_ack_when_nothing_to_ack_is_ok(void) {
  fresh(3); svmg_reason_t r = SVMG_R_BAD_PARAM;
  TEST_ASSERT_EQUAL_INT(0, svmg_alarm_ack(&A, SVMG_ACKBY_REMOTE, 10, EV, &r)); TEST_ASSERT_EQUAL_INT(SVMG_R_OK, r);
  OKU(SVMG_HIGH_ROLL, 0);   /* CAUTION */
  TEST_ASSERT_EQUAL_INT(0, svmg_alarm_ack(&A, SVMG_ACKBY_REMOTE, 10, EV, &r)); TEST_ASSERT_EQUAL_INT(SVMG_R_OK, r);
}
void test_escalation_exactly_at_60s_real_time(void) {
  fresh(3); to_warning(1000);
  TEST_ASSERT_EQUAL_INT(0, svmg_alarm_tick(&A, 1000 + 59999u, EV));
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_WARNING, A.level);
  int n = svmg_alarm_tick(&A, 1000 + 60000u, EV);
  TEST_ASSERT_EQUAL_INT(1, n); TEST_ASSERT_EQUAL_INT(SVMG_LVL_CRITICAL, A.level);
  TEST_ASSERT_EQUAL_UINT8(SVMG_LVL_CRITICAL, EV[0].level); TEST_ASSERT_EQUAL_UINT8(SVMG_LVL_WARNING, EV[0].prev_level);
  TEST_ASSERT_EQUAL_UINT32(1, EV[0].alarm_id);              /* cùng alarm_id, không tạo cảnh báo mới */
  svmg_alarm_out_t o = outs(61000); TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_CONTINUOUS, o.buzzer);
  TEST_ASSERT_EQUAL_UINT32(1, A.n_escalated);
  /* sau ACK: còi tắt, mức vẫn CRITICAL */
  svmg_alarm_ack(&A, SVMG_ACKBY_REMOTE, 70000, EV, NULL);
  o = outs(70000); TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_OFF, o.buzzer); TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_ON, o.led_r);
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_CRITICAL, A.level);
}
void test_escalation_survives_millis_rollover(void) {
  fresh(3); uint32_t t0 = 0xFFFFFF00u; to_warning(t0);
  TEST_ASSERT_EQUAL_INT(0, svmg_alarm_tick(&A, t0 + 59999u, EV));
  TEST_ASSERT_EQUAL_INT(1, svmg_alarm_tick(&A, t0 + 60000u, EV));       /* tràn uint32 */
}
void test_mute_rules(void) {
  svmg_reason_t r;
  fresh(3);
  TEST_ASSERT_EQUAL_INT(0, svmg_alarm_mute(&A, 30, 0, EV, &r)); TEST_ASSERT_EQUAL_INT(SVMG_R_FORBIDDEN_STATE, r);   /* NORMAL */
  to_warning(0);
  TEST_ASSERT_EQUAL_INT(0, svmg_alarm_mute(&A, 0, 0, EV, &r));   TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, r);
  TEST_ASSERT_EQUAL_INT(0, svmg_alarm_mute(&A, 301, 0, EV, &r)); TEST_ASSERT_EQUAL_INT(SVMG_R_BAD_PARAM, r);
  TEST_ASSERT_EQUAL_INT(1, svmg_alarm_mute(&A, 300, 1000, EV, &r)); TEST_ASSERT_EQUAL_INT(SVMG_R_OK, r);
  TEST_ASSERT_EQUAL_UINT8(SVMG_EV_ALARM_MUTE, EV[0].type); TEST_ASSERT_EQUAL_UINT16(300, EV[0].val);
  TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_OFF, outs(2000).buzzer);
  TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_OFF, outs(1000 + 299999u).buzzer);
  TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_INTERMITTENT, outs(1000 + 300000u).buzzer);          /* hết hạn mute */
}
void test_mute_does_not_stop_escalation_and_critical_cannot_be_muted(void) {
  svmg_reason_t r;
  fresh(3); to_warning(0);
  svmg_alarm_mute(&A, 300, 100, EV, &r);
  TEST_ASSERT_EQUAL_INT(1, svmg_alarm_tick(&A, 60000, EV));               /* vẫn leo thang lúc 60 s */
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_CRITICAL, A.level);
  TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_CONTINUOUS, outs(60001).buzzer);       /* mute bị hủy khi lên CRITICAL */
  TEST_ASSERT_EQUAL_INT(0, svmg_alarm_mute(&A, 30, 60002, EV, &r));
  TEST_ASSERT_EQUAL_INT(SVMG_R_FORBIDDEN_STATE, r);                       /* T10: mute khi CRITICAL bị từ chối */
}
void test_mute_after_ack_rejected(void) {
  svmg_reason_t r; fresh(3); to_warning(0); svmg_alarm_ack(&A, SVMG_ACKBY_BUTTON, 5, EV, NULL);
  TEST_ASSERT_EQUAL_INT(0, svmg_alarm_mute(&A, 30, 6, EV, &r)); TEST_ASSERT_EQUAL_INT(SVMG_R_FORBIDDEN_STATE, r);
}
void test_hard_threshold_immediate_critical_even_if_model_says_normal(void) {
  fresh(3);
  int n = upd(SVMG_NORMAL, SVMG_ST_OK, 0, 1, 500);
  TEST_ASSERT_EQUAL_INT(1, n); TEST_ASSERT_EQUAL_INT(SVMG_LVL_CRITICAL, A.level);
  TEST_ASSERT_EQUAL_UINT8(SVMG_LVL_NORMAL, EV[0].prev_level); TEST_ASSERT_EQUAL_UINT32(1, EV[0].alarm_id);
  TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_CONTINUOUS, outs(500).buzzer);
}
void test_hard_threshold_works_even_when_data_unknown_or_fault(void) {
  fresh(3); upd(SVMG_UNKNOWN, SVMG_ST_UNKNOWN, 0, 1, 0);
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_CRITICAL, A.level);
  fresh(3); upd(SVMG_FAULT, SVMG_ST_FAULT, 0, 1, 0);
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_CRITICAL, A.level);
}
void test_force_critical_between_updates(void) {
  fresh(3); int n = svmg_alarm_force_critical(&A, 12.5f, 777, EV);
  TEST_ASSERT_EQUAL_INT(1, n); TEST_ASSERT_EQUAL_INT(SVMG_LVL_CRITICAL, A.level);
  TEST_ASSERT_EQUAL_INT(0, svmg_alarm_force_critical(&A, 13.0f, 778, EV));       /* idempotent */
}
void test_reescalation_unacks(void) {
  fresh(3); to_warning(0); svmg_alarm_ack(&A, SVMG_ACKBY_BUTTON, 5, EV, NULL);
  TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_OFF, outs(6).buzzer);
  upd(SVMG_HIGH_ROLL, SVMG_ST_OK, 0, 1, 10);                                     /* hard bật sau khi đã ACK ở WARNING */
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_CRITICAL, A.level); TEST_ASSERT_FALSE(A.acked);
  TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_CONTINUOUS, outs(11).buzzer);
}
void test_clear_needs_6_updates_and_new_alarm_gets_new_id(void) {
  fresh(3); to_warning(0); svmg_alarm_ack(&A, SVMG_ACKBY_BUTTON, 5, EV, NULL);
  for (int i = 0; i < 5; i++) TEST_ASSERT_EQUAL_INT(0, OKU(SVMG_NORMAL, 0));
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_WARNING, A.level);                              /* 25 s: chưa giải tỏa */
  int n = OKU(SVMG_NORMAL, 0);                                                    /* lần 6 = 30 s */
  TEST_ASSERT_EQUAL_INT(1, n); TEST_ASSERT_EQUAL_INT(SVMG_LVL_NORMAL, A.level);
  TEST_ASSERT_EQUAL_UINT8(SVMG_LVL_NORMAL, EV[0].level); TEST_ASSERT_EQUAL_UINT8(SVMG_LVL_WARNING, EV[0].prev_level);
  TEST_ASSERT_EQUAL_UINT32(1, EV[0].alarm_id); TEST_ASSERT_EQUAL_UINT32(1, A.n_cleared);
  TEST_ASSERT_FALSE(A.acked);
  to_warning(100000);
  TEST_ASSERT_EQUAL_UINT32(2, A.alarm_id);                                        /* cảnh báo mới -> id mới */
  TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_INTERMITTENT, outs(100001).buzzer);            /* và phải được ACK lại */
}
void test_flapping_same_alarm_continues(void) {
  /* T09 "cảnh báo ngắt rồi quay lại": bình thường 15 s (< 30 s) rồi tái phát -> cùng alarm_id, không sự kiện mới */
  fresh(3); to_warning(0);
  for (int i = 0; i < 3; i++) OKU(SVMG_NORMAL, 0);
  int n = OKU(SVMG_HIGH_ROLL, 0);
  TEST_ASSERT_EQUAL_INT(0, n); TEST_ASSERT_EQUAL_INT(SVMG_LVL_WARNING, A.level); TEST_ASSERT_EQUAL_UINT32(1, A.alarm_id);
  for (int i = 0; i < 5; i++) OKU(SVMG_NORMAL, 0);                                // bộ đếm giải tỏa phải bắt đầu lại từ 0
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_WARNING, A.level);
}
void test_unknown_and_fault_never_clear_nor_raise(void) {
  fresh(3);
  for (int i = 0; i < 10; i++) upd(SVMG_UNKNOWN, SVMG_ST_UNKNOWN, 0, 0, 0);
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_NORMAL, A.level);
  svmg_alarm_out_t o = outs(0);
  TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_OFF, o.led_g); TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_BLINK_SLOW, o.led_y);   /* không phải xanh */
  for (int i = 0; i < 10; i++) upd(SVMG_FAULT, SVMG_ST_FAULT, 0, 0, 0);
  o = outs(0); TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_OFF, o.led_g); TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_BLINK_FAST, o.led_r);
  fresh(3); to_warning(0);
  for (int i = 0; i < 20; i++) upd(SVMG_UNKNOWN, SVMG_ST_UNKNOWN, 0, 0, 0);
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_WARNING, A.level);                               /* mù dữ liệu không được coi là hết nguy hiểm */
  for (int i = 0; i < 20; i++) upd(SVMG_FAULT, SVMG_ST_FAULT, 0, 0, 0);
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_WARNING, A.level);
}
void test_mtta_statistics(void) {
  fresh(3); to_warning(1000);
  svmg_alarm_ack(&A, SVMG_ACKBY_BUTTON, 8000, EV, NULL);
  TEST_ASSERT_EQUAL_UINT32(7000, A.sum_ack_ms); TEST_ASSERT_EQUAL_UINT32(1, A.n_acked); TEST_ASSERT_EQUAL_UINT32(1, A.n_raised);
}
void test_time_in_event_matches_sim_clock(void) {
  fresh(3); to_warning(0);
  TEST_ASSERT_EQUAL_FLOAT(15.0f, EV[0].t_sim_s);
}
void test_cfg_update_keeps_state(void) {
  fresh(3); to_warning(0);
  svmg_alarm_cfg_t c = A.cfg; c.debounce_n = 2; c.max_mute_s = 9999;
  svmg_alarm_set_cfg(&A, &c);
  TEST_ASSERT_EQUAL_INT(SVMG_LVL_WARNING, A.level); TEST_ASSERT_EQUAL_UINT32(1, A.alarm_id);
  TEST_ASSERT_EQUAL_UINT16(300, A.cfg.max_mute_s);                                 /* trần mute 300 s không thể nới */
}

/* ---- Thuộc tính an toàn bằng thao tác ngẫu nhiên (không thể "tắt" cảnh báo cục bộ) ---- */
void test_property_no_operation_sequence_disables_local_alarm(void) {
  uint32_t rng = 0xC0FFEEu;
  for (int trial = 0; trial < 200; trial++) {
    fresh(1 + (int)(st_rng(&rng) % 4));
    uint32_t now = st_rng(&rng) % 100000u;
    for (int step = 0; step < 60; step++) {
      svmg_level_t before = A.level; int cond_false = 0;
      switch (st_rng(&rng) % 5) {
        case 0: { svmg_class_t c = (svmg_class_t)(st_rng(&rng) % 6); svmg_status_t s = (svmg_status_t)(st_rng(&rng) % 3);
                  int hard = (st_rng(&rng) % 8) == 0; int mai = (int)(st_rng(&rng) % 101);
                  cond_false = !(hard || (s == SVMG_ST_OK && (c == SVMG_HIGH_ROLL || c == SVMG_PERSISTENT_OFFSET || c == SVMG_AMPLITUDE_GROWTH || mai >= A.cfg.mai_caution)));
                  upd(c, s, mai, hard, now); break; }
        case 1: svmg_alarm_ack(&A, SVMG_ACKBY_REMOTE, now, EV, NULL); break;
        case 2: svmg_alarm_mute(&A, (uint16_t)(st_rng(&rng) % 400), now, EV, NULL); break;
        case 3: now += st_rng(&rng) % 30000u; svmg_alarm_tick(&A, now, EV); break;
        case 4: { svmg_alarm_cfg_t c = A.cfg; c.max_mute_s = (uint16_t)st_rng(&rng); c.debounce_n = (uint8_t)(1 + st_rng(&rng) % 6); svmg_alarm_set_cfg(&A, &c); break; }
      }
      /* (a) mức chỉ giảm khi một lần cập nhật hết điều kiện */
      if (A.level < before) TEST_ASSERT_TRUE(cond_false);
      /* (b) CRITICAL chưa ACK luôn kêu liên tục, mute không ảnh hưởng */
      if (A.level == SVMG_LVL_CRITICAL && !A.acked) TEST_ASSERT_EQUAL_UINT8(SVMG_BUZ_CONTINUOUS, outs(now).buzzer);
      /* (c) WARNING+ luôn sáng đỏ, kể cả khi ACK */
      if (A.level >= SVMG_LVL_WARNING) TEST_ASSERT_EQUAL_UINT8(SVMG_OUT_ON, outs(now).led_r);
      TEST_ASSERT_TRUE(A.cfg.max_mute_s <= 300);
    }
    /* (d) dù đã làm gì, điều kiện ngưỡng cứng vẫn đưa lên CRITICAL ngay */
    upd(SVMG_NORMAL, SVMG_ST_OK, 0, 1, now);
    TEST_ASSERT_EQUAL_INT(SVMG_LVL_CRITICAL, A.level);
  }
}

int main(void) {
  UNITY_BEGIN();
  RUN_TEST(test_normal_stays_normal); RUN_TEST(test_caution_then_warning_after_N); RUN_TEST(test_debounce_N_profiles);
  RUN_TEST(test_streak_broken_by_other_class_or_normal); RUN_TEST(test_mai_alone_gives_caution_only_and_clears);
  RUN_TEST(test_ack_silences_but_keeps_led_and_no_escalation); RUN_TEST(test_ack_when_nothing_to_ack_is_ok);
  RUN_TEST(test_escalation_exactly_at_60s_real_time); RUN_TEST(test_escalation_survives_millis_rollover);
  RUN_TEST(test_mute_rules); RUN_TEST(test_mute_does_not_stop_escalation_and_critical_cannot_be_muted); RUN_TEST(test_mute_after_ack_rejected);
  RUN_TEST(test_hard_threshold_immediate_critical_even_if_model_says_normal);
  RUN_TEST(test_hard_threshold_works_even_when_data_unknown_or_fault); RUN_TEST(test_force_critical_between_updates);
  RUN_TEST(test_reescalation_unacks); RUN_TEST(test_clear_needs_6_updates_and_new_alarm_gets_new_id);
  RUN_TEST(test_flapping_same_alarm_continues); RUN_TEST(test_unknown_and_fault_never_clear_nor_raise);
  RUN_TEST(test_mtta_statistics); RUN_TEST(test_time_in_event_matches_sim_clock); RUN_TEST(test_cfg_update_keeps_state);
  RUN_TEST(test_property_no_operation_sequence_disables_local_alarm);
  return UNITY_END();
}
