/* svmg_evbuf.h - M1-06: bộ đệm sự kiện offline 64 phần tử (đề cương 9.2).
 *  - mỗi sự kiện có seq tăng dần (do firmware cấp, dùng chung với telemetry) và đi kèm boot_id ở tầng bản tin;
 *  - khi đầy: ghi đè sự kiện CŨ NHẤT KHÔNG PHẢI cảnh báo; chỉ khi toàn là cảnh báo mới ghi đè cảnh báo cũ nhất
 *    (và đếm lại để báo trong health);
 *  - gửi theo thứ tự seq; PUBACK (QoS 1) thì giải phóng; mất kết nối thì các sự kiện đang bay quay lại hàng chờ
 *    (gửi lại bản trùng là chấp nhận được vì backend loại trùng theo (device_id, boot_id, seq)).
 */
#ifndef SVMG_EVBUF_H
#define SVMG_EVBUF_H

#include "svmg_common.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SVMG_EVBUF_CAP 64

typedef struct {
  svmg_event_t ev;
  uint8_t      state;      /* 0 trống, 1 chờ gửi, 2 đang bay (chưa PUBACK) */
} svmg_evslot_t;

typedef struct {
  svmg_evslot_t s[SVMG_EVBUF_CAP];
  uint32_t      n_pushed, n_dropped_other, n_dropped_alarm, n_acked;
} svmg_evbuf_t;

void svmg_evbuf_init(svmg_evbuf_t *b);
/* Lưu sự kiện với seq đã cấp. Trả 0 nếu còn chỗ, 1 nếu phải ghi đè một sự kiện cũ. */
int  svmg_evbuf_push(svmg_evbuf_t *b, const svmg_event_t *ev, uint32_t seq);
/* Lấy sự kiện chờ gửi có seq nhỏ nhất, đánh dấu đang bay. Trả 1 nếu có. */
int  svmg_evbuf_next(svmg_evbuf_t *b, svmg_event_t *out);
/* PUBACK: giải phóng sự kiện seq. Trả 1 nếu tìm thấy. */
int  svmg_evbuf_ack(svmg_evbuf_t *b, uint32_t seq);
/* Mất kết nối: các sự kiện đang bay quay lại hàng chờ. */
void svmg_evbuf_requeue_inflight(svmg_evbuf_t *b);
int  svmg_evbuf_depth(const svmg_evbuf_t *b);     /* tất cả sự kiện chưa được ack */
int  svmg_evbuf_pending(const svmg_evbuf_t *b);   /* chờ gửi */

#ifdef __cplusplus
}
#endif
#endif
