/* Test M1-06: bộ đệm offline boot_id+seq (nền của T05/T06 phía thiết bị). */
#include <unity.h>
#include <string.h>
#include "svmg_evbuf.h"
#include "svmg_testutil.h"

void setUp(void) {}
void tearDown(void) {}

static svmg_evbuf_t B;
static uint32_t SEQ;

static svmg_event_t mk(svmg_event_type_t t) { svmg_event_t e; memset(&e, 0, sizeof e); e.type = (uint8_t)t; return e; }
static int push(svmg_event_type_t t) { svmg_event_t e = mk(t); return svmg_evbuf_push(&B, &e, ++SEQ); }
static void fresh(void) { svmg_evbuf_init(&B); SEQ = 0; }

void test_in_order_delivery_and_ack(void) {
  fresh(); for (int i = 0; i < 10; i++) push(SVMG_EV_ALARM_STATE);
  TEST_ASSERT_EQUAL_INT(10, svmg_evbuf_pending(&B));
  svmg_event_t e;
  for (uint32_t want = 1; want <= 10; want++) {
    TEST_ASSERT_EQUAL_INT(1, svmg_evbuf_next(&B, &e)); TEST_ASSERT_EQUAL_UINT32(want, e.seq);
  }
  TEST_ASSERT_EQUAL_INT(0, svmg_evbuf_next(&B, &e));               /* đang bay: chưa gửi lại */
  TEST_ASSERT_EQUAL_INT(10, svmg_evbuf_depth(&B));
  for (uint32_t s = 1; s <= 10; s++) TEST_ASSERT_EQUAL_INT(1, svmg_evbuf_ack(&B, s));
  TEST_ASSERT_EQUAL_INT(0, svmg_evbuf_depth(&B));
  TEST_ASSERT_EQUAL_INT(0, svmg_evbuf_ack(&B, 3));                 /* ack trùng/không tồn tại */
}
void test_disconnect_requeues_inflight_without_loss(void) {
  fresh(); for (int i = 0; i < 5; i++) push(SVMG_EV_ALARM_STATE);
  svmg_event_t e; svmg_evbuf_next(&B, &e); svmg_evbuf_next(&B, &e);   /* seq 1,2 đang bay */
  svmg_evbuf_ack(&B, 1);                                             /* chỉ seq 1 được PUBACK trước khi mất mạng */
  svmg_evbuf_requeue_inflight(&B);
  uint32_t got[8]; int n = 0;
  while (svmg_evbuf_next(&B, &e)) got[n++] = e.seq;
  TEST_ASSERT_EQUAL_INT(4, n);
  TEST_ASSERT_EQUAL_UINT32(2, got[0]); TEST_ASSERT_EQUAL_UINT32(3, got[1]); TEST_ASSERT_EQUAL_UINT32(5, got[3]);   /* 2..5, đúng thứ tự, 1 không gửi lại */
}
void test_full_buffer_drops_oldest_non_alarm_first(void) {
  fresh();
  for (int i = 0; i < 32; i++) { push(SVMG_EV_ALARM_STATE); push(SVMG_EV_MODE_CHANGE); }   /* 64: xen kẽ cảnh báo/hệ thống */
  TEST_ASSERT_EQUAL_INT(64, svmg_evbuf_depth(&B));
  TEST_ASSERT_EQUAL_INT(1, push(SVMG_EV_ALARM_STATE));              /* phải ghi đè: nạn nhân là MODE_CHANGE cũ nhất (seq 2) */
  TEST_ASSERT_EQUAL_UINT32(1, B.n_dropped_other); TEST_ASSERT_EQUAL_UINT32(0, B.n_dropped_alarm);
  svmg_event_t e; int has_seq2 = 0, has_seq1 = 0;
  while (svmg_evbuf_next(&B, &e)) { if (e.seq == 2) has_seq2 = 1; if (e.seq == 1) has_seq1 = 1; }
  TEST_ASSERT_FALSE(has_seq2); TEST_ASSERT_TRUE(has_seq1);
}
void test_all_alarm_overwrites_oldest_alarm_and_counts(void) {
  fresh(); for (int i = 0; i < 64; i++) push(SVMG_EV_ALARM_STATE);
  push(SVMG_EV_ALARM_ACK);
  TEST_ASSERT_EQUAL_UINT32(0, B.n_dropped_other); TEST_ASSERT_EQUAL_UINT32(1, B.n_dropped_alarm);
  svmg_event_t e; svmg_evbuf_next(&B, &e); TEST_ASSERT_EQUAL_UINT32(2, e.seq);          /* seq 1 đã bị ghi đè */
}
void test_capacity_64_no_loss_below_limit(void) {
  fresh(); for (int i = 0; i < 64; i++) TEST_ASSERT_EQUAL_INT(0, push(SVMG_EV_ALARM_STATE));
  svmg_event_t e; uint32_t expect = 1;
  while (svmg_evbuf_next(&B, &e)) { TEST_ASSERT_EQUAL_UINT32(expect, e.seq); expect++; }
  TEST_ASSERT_EQUAL_UINT32(65, expect);
}
void test_offline_burst_then_reconnect_exactly_once(void) {
  /* T06 phía thiết bị: ngắt mạng, 40 sự kiện, kết nối lại, gửi - có lúc rớt mạng giữa chừng - rồi gửi tiếp. */
  fresh(); for (int i = 0; i < 40; i++) push(i % 3 ? SVMG_EV_ALARM_STATE : SVMG_EV_FAULT);
  uint8_t acked[128]; memset(acked, 0, sizeof acked); svmg_event_t e; int sent = 0;
  for (int i = 0; i < 15 && svmg_evbuf_next(&B, &e); i++) { sent++; if (i < 10) { svmg_evbuf_ack(&B, e.seq); acked[e.seq]++; } }
  svmg_evbuf_requeue_inflight(&B);                                  /* rớt mạng lần 2 */
  while (svmg_evbuf_next(&B, &e)) { svmg_evbuf_ack(&B, e.seq); acked[e.seq]++; }
  for (uint32_t s = 1; s <= 40; s++) TEST_ASSERT_EQUAL_UINT8_MESSAGE(1, acked[s], "mỗi sự kiện được xác nhận đúng 1 lần");
  TEST_ASSERT_EQUAL_INT(0, svmg_evbuf_depth(&B));
}
void test_property_random_ops_keep_invariants(void) {
  uint32_t rng = 777; fresh(); svmg_event_t e; uint8_t acked[4096]; memset(acked, 0, sizeof acked);
  for (int step = 0; step < 5000; step++) {
    switch (st_rng(&rng) % 4) {
      case 0: push((svmg_event_type_t)(1 + st_rng(&rng) % 10)); break;
      case 1: if (svmg_evbuf_next(&B, &e)) { TEST_ASSERT_EQUAL_UINT8(0, acked[e.seq % 4096]); } break;
      case 2: if (svmg_evbuf_next(&B, &e)) { if (svmg_evbuf_ack(&B, e.seq)) acked[e.seq % 4096] = 1; } break;
      case 3: svmg_evbuf_requeue_inflight(&B); break;
    }
    TEST_ASSERT_TRUE(svmg_evbuf_depth(&B) <= SVMG_EVBUF_CAP);
    TEST_ASSERT_TRUE(svmg_evbuf_pending(&B) <= svmg_evbuf_depth(&B));
    if (step % 700 == 699) memset(acked, 0, sizeof acked);          /* seq không quay vòng trong cửa sổ kiểm tra */
  }
}
void test_sizeof_evbuf(void) { TEST_ASSERT_TRUE(sizeof(svmg_evbuf_t) <= 2048); }

int main(void) {
  UNITY_BEGIN();
  RUN_TEST(test_in_order_delivery_and_ack); RUN_TEST(test_disconnect_requeues_inflight_without_loss);
  RUN_TEST(test_full_buffer_drops_oldest_non_alarm_first); RUN_TEST(test_all_alarm_overwrites_oldest_alarm_and_counts);
  RUN_TEST(test_capacity_64_no_loss_below_limit); RUN_TEST(test_offline_burst_then_reconnect_exactly_once);
  RUN_TEST(test_property_random_ops_keep_invariants); RUN_TEST(test_sizeof_evbuf);
  return UNITY_END();
}
