/* evbuf.c - M1-06. Xem svmg_evbuf.h. */
#include "svmg_evbuf.h"
#include <string.h>

static int is_alarm_ev(uint8_t t) {
  return t == SVMG_EV_ALARM_STATE || t == SVMG_EV_ALARM_ACK || t == SVMG_EV_ALARM_MUTE;
}

void svmg_evbuf_init(svmg_evbuf_t *b) { memset(b, 0, sizeof *b); }

int svmg_evbuf_push(svmg_evbuf_t *b, const svmg_event_t *ev, uint32_t seq) {
  int slot = -1, overwrote = 0;
  for (int i = 0; i < SVMG_EVBUF_CAP; i++) if (b->s[i].state == 0) { slot = i; break; }
  if (slot < 0) {
    int old_other = -1, old_alarm = -1;
    for (int i = 0; i < SVMG_EVBUF_CAP; i++) {
      uint32_t q = b->s[i].ev.seq;
      if (is_alarm_ev(b->s[i].ev.type)) { if (old_alarm < 0 || q < b->s[old_alarm].ev.seq) old_alarm = i; }
      else { if (old_other < 0 || q < b->s[old_other].ev.seq) old_other = i; }
    }
    if (old_other >= 0) { slot = old_other; b->n_dropped_other++; }
    else { slot = old_alarm; b->n_dropped_alarm++; }
    overwrote = 1;
  }
  b->s[slot].ev = *ev;
  b->s[slot].ev.seq = seq;
  b->s[slot].state = 1;
  b->n_pushed++;
  return overwrote;
}

int svmg_evbuf_next(svmg_evbuf_t *b, svmg_event_t *out) {
  int best = -1;
  for (int i = 0; i < SVMG_EVBUF_CAP; i++)
    if (b->s[i].state == 1 && (best < 0 || b->s[i].ev.seq < b->s[best].ev.seq)) best = i;
  if (best < 0) return 0;
  b->s[best].state = 2;
  *out = b->s[best].ev;
  return 1;
}

int svmg_evbuf_ack(svmg_evbuf_t *b, uint32_t seq) {
  for (int i = 0; i < SVMG_EVBUF_CAP; i++)
    if (b->s[i].state != 0 && b->s[i].ev.seq == seq) { b->s[i].state = 0; b->n_acked++; return 1; }
  return 0;
}

void svmg_evbuf_requeue_inflight(svmg_evbuf_t *b) {
  for (int i = 0; i < SVMG_EVBUF_CAP; i++) if (b->s[i].state == 2) b->s[i].state = 1;
}

int svmg_evbuf_depth(const svmg_evbuf_t *b) {
  int n = 0; for (int i = 0; i < SVMG_EVBUF_CAP; i++) if (b->s[i].state) n++; return n;
}

int svmg_evbuf_pending(const svmg_evbuf_t *b) {
  int n = 0; for (int i = 0; i < SVMG_EVBUF_CAP; i++) if (b->s[i].state == 1) n++; return n;
}
