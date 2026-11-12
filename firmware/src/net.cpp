#include "net.h"
#include "svmg_build.h"

#if SVMG_NET
#include <WiFi.h>
#include <mqtt_client.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>

namespace {
constexpr int MAX_INFLIGHT = 4;
constexpr uint32_t PUBACK_TIMEOUT_MS = 8000;

struct Inflight { int msg_id; uint32_t seq; uint32_t t_ms; };

esp_mqtt_client_handle_t s_cli = nullptr;
volatile bool s_connected = false, s_flag_online = false, s_flag_requeue = false, s_ever = false;
volatile uint32_t s_reconnects = 0, s_rx_dropped = 0, s_since_ms = 0;
bool s_started = false;
bool s_blackout = false;   // chỉ đặt được khi SVMG_FAULT_INJECT
QueueHandle_t q_rx = nullptr, q_ack = nullptr;
Inflight s_inf[MAX_INFLIGHT];
int s_inf_n = 0;
MsgIdent s_id;
char T_telemetry[64], T_event[64], T_status[64], T_health[64], T_cmd[64], T_ack[64], T_config[64], T_trace[64], T_base[48];
char s_lwt[32];

void topic(char *dst, size_t cap, const char *suffix) { snprintf(dst, cap, "svmg/%s/%s", SVMG_DEVICE_ID, suffix); }

bool topic_is(const esp_mqtt_event_t *e, const char *t) {
  size_t n = strlen(t);
  return (size_t)e->topic_len == n && strncmp(e->topic, t, n) == 0;     // chỉ nhận đúng topic của chính thiết bị này
}

void on_mqtt(void *, esp_event_base_t, int32_t id, void *data) {
  auto *e = (esp_mqtt_event_handle_t)data;
  switch (id) {
    case MQTT_EVENT_CONNECTED:
      if (s_ever) s_reconnects = s_reconnects + 1;
      s_ever = true; s_connected = true; s_since_ms = millis(); s_flag_online = true;
      break;
    case MQTT_EVENT_DISCONNECTED:
      s_connected = false; s_flag_requeue = true;
      break;
    case MQTT_EVENT_PUBLISHED: {
      int m = e->msg_id;
      xQueueSend(q_ack, &m, 0);
      break;
    }
    case MQTT_EVENT_DATA: {
      RxItem it;
      if (e->current_data_offset != 0 || e->data_len != e->total_data_len || e->data_len >= (int)sizeof it.payload) { s_rx_dropped = s_rx_dropped + 1; break; }
      if (topic_is(e, T_cmd)) it.kind = RX_CMD;
      else if (topic_is(e, T_config)) it.kind = RX_CONFIG;
      else break;
      it.rx_ms = millis(); it.len = (uint16_t)e->data_len;
      memcpy(it.payload, e->data, e->data_len); it.payload[e->data_len] = 0;
      if (xQueueSend(q_rx, &it, 0) != pdTRUE) s_rx_dropped = s_rx_dropped + 1;
      break;
    }
    default: break;
  }
}

void drop_inflight(svmg_evbuf_t *buf) { svmg_evbuf_requeue_inflight(buf); s_inf_n = 0; }
}  // namespace

void net_begin(const MsgIdent &id, const char *) {
  s_id = id;
  snprintf(T_base, sizeof T_base, "svmg/%s", SVMG_DEVICE_ID);
  topic(T_telemetry, sizeof T_telemetry, "telemetry"); topic(T_event, sizeof T_event, "event");
  topic(T_status, sizeof T_status, "status");          topic(T_health, sizeof T_health, "health");
  topic(T_cmd, sizeof T_cmd, "cmd");                   topic(T_ack, sizeof T_ack, "cmd/ack");
  topic(T_config, sizeof T_config, "config");          topic(T_trace, sizeof T_trace, "trace");
  q_rx = xQueueCreate(4, sizeof(RxItem));
  q_ack = xQueueCreate(16, sizeof(int));

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(SVMG_WIFI_SSID, SVMG_WIFI_PASS, SVMG_WIFI_CHANNEL);        // không chặn: thiết bị vẫn cảnh báo cục bộ khi chưa có mạng

  size_t ln = msg_build_status_offline(s_lwt, sizeof s_lwt);
  esp_mqtt_client_config_t c = {};
  c.broker.address.uri = SVMG_MQTT_URI;
  if (SVMG_MQTT_USER[0]) { c.credentials.username = SVMG_MQTT_USER; c.credentials.authentication.password = SVMG_MQTT_PASS; }
  c.credentials.client_id = SVMG_DEVICE_ID;
  c.session.last_will.topic = T_status;
  c.session.last_will.msg = s_lwt; c.session.last_will.msg_len = (int)ln;
  c.session.last_will.qos = 1; c.session.last_will.retain = 1;
  c.session.keepalive = 30;
  c.network.reconnect_timeout_ms = 5000;
  c.network.timeout_ms = 5000;
  c.buffer.size = 1024; c.buffer.out_size = 1024;
  s_cli = esp_mqtt_client_init(&c);
  if (s_cli) esp_mqtt_client_register_event(s_cli, MQTT_EVENT_ANY, on_mqtt, nullptr);
}

#ifdef SVMG_FAULT_INJECT
void net_inject_blackout(bool on) { s_blackout = on; }
#endif
bool net_connected() { return s_connected && !s_blackout; }
int net_rssi() { return WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0; }
uint32_t net_reconnects() { return s_reconnects; }
uint32_t net_rx_dropped() { return s_rx_dropped; }
uint32_t net_connected_since_ms() { return s_since_ms; }

int net_publish(const char *sub, const char *payload, int len, int qos, bool retain) {
  if (!s_cli || !s_connected || s_blackout) return -1;
  const char *t = !strcmp(sub, "telemetry") ? T_telemetry : !strcmp(sub, "event") ? T_event : !strcmp(sub, "status") ? T_status
                : !strcmp(sub, "health") ? T_health : !strcmp(sub, "cmd/ack") ? T_ack : !strcmp(sub, "trace") ? T_trace : nullptr;
  if (!t) return -1;
  return esp_mqtt_client_publish(s_cli, t, payload, len, qos, retain ? 1 : 0);
}

bool net_pop_rx(RxItem *out) { return q_rx && xQueueReceive(q_rx, out, 0) == pdTRUE; }

void net_service(uint32_t now, svmg_evbuf_t *buf, uint32_t config_version) {
  if (!s_cli) return;
  if (!s_started && WiFi.status() == WL_CONNECTED) { esp_mqtt_client_start(s_cli); s_started = true; }

  if (s_flag_requeue) { s_flag_requeue = false; drop_inflight(buf); }           // mất kết nối: sự kiện đang bay quay lại hàng chờ

  if (s_flag_online && s_connected) {
    s_flag_online = false;
    char js[200]; size_t n = msg_build_status_online(js, sizeof js, s_id, config_version);
    if (n) esp_mqtt_client_publish(s_cli, T_status, js, (int)n, 1, 1);          // retained, QoS 1
    esp_mqtt_client_subscribe(s_cli, T_cmd, 1);
    esp_mqtt_client_subscribe(s_cli, T_config, 1);
  }

  int m;
  while (q_ack && xQueueReceive(q_ack, &m, 0) == pdTRUE) {                      // PUBACK -> giải phóng khỏi bộ đệm
    for (int i = 0; i < s_inf_n; i++) if (s_inf[i].msg_id == m) {
      svmg_evbuf_ack(buf, s_inf[i].seq);
      s_inf[i] = s_inf[--s_inf_n];
      break;
    }
  }
  for (int i = 0; i < s_inf_n; i++) if (now - s_inf[i].t_ms > PUBACK_TIMEOUT_MS) { drop_inflight(buf); break; }   // gửi bù (có thể trùng, backend loại theo seq)

  while (s_connected && !s_blackout && s_inf_n < MAX_INFLIGHT) {
    svmg_event_t e;
    if (!svmg_evbuf_next(buf, &e)) break;
    char js[420];
    size_t n = msg_build_event(js, sizeof js, s_id, e);
    if (!n) { svmg_evbuf_ack(buf, e.seq); continue; }                           // không tuần tự hóa được: bỏ để khỏi kẹt hàng chờ
    int id = esp_mqtt_client_publish(s_cli, T_event, js, (int)n, 1, 0);
    if (id > 0) { s_inf[s_inf_n++] = { id, e.seq, now }; }
    else { drop_inflight(buf); break; }                                         // lỗi/đầy outbox: thử lại vòng sau
  }
}

#else  // SVMG_NET == 0: chạy cục bộ hoàn toàn
void net_begin(const MsgIdent &, const char *) {}
void net_service(uint32_t, svmg_evbuf_t *, uint32_t) {}
bool net_connected() { return false; }
int net_publish(const char *, const char *, int, int, bool) { return -1; }
bool net_pop_rx(RxItem *) { return false; }
int net_rssi() { return 0; }
uint32_t net_reconnects() { return 0; }
uint32_t net_rx_dropped() { return 0; }
uint32_t net_connected_since_ms() { return 0; }
#endif
