// SVMG Cargo Node (ESP32 thứ 2) - đo hầm hàng và publish MQTT. Độc lập với Motion Node.
//  - chiết áp mực nước GPIO 35 -> cargo_water_pct (0..100 %)
//  - DHT22 GPIO 4              -> cargo_temp_c, cargo_humidity_pct
// Topic (xem contracts/mqtt_topics.md):  svmg/{id}/cargo (QoS 0), svmg/{id}/status (QoS 1, retained, có LWT), svmg/{id}/health (QoS 0).
// KHÔNG gửi roll/pitch. Cảm biến lỗi -> sensor_ok=false và giá trị null (không bao giờ gửi số giả).
// Nguyên tắc như Motion Node: vòng lặp không chờ mạng (esp_mqtt_client_enqueue), mất mạng vẫn đo và tự nối lại.
#include <Arduino.h>
#include <DHT.h>
#include <WiFi.h>
#include <esp_system.h>
#include <esp_timer.h>
#include <math.h>
#include <mqtt_client.h>
#include "cargo_config.h"

namespace {
DHT s_dht(PIN_DHT, DHT22);
esp_mqtt_client_handle_t s_cli = nullptr;
volatile bool s_connected = false, s_flag_online = false, s_ever = false;
volatile uint32_t s_reconnects = 0;
bool s_started = false;
char s_boot[9];
char T_cargo[80], T_status[80], T_health[80], s_lwt[32];
uint32_t s_seq = 0;
float s_last_temp = NAN, s_last_hum = NAN;      // giá trị DHT hợp lệ gần nhất (chỉ dùng khi lần đọc mới lỗi < DHT_STALE_MS)
uint32_t s_last_dht_ok_ms = 0;
constexpr uint32_t DHT_PERIOD_MS = 2100;        // DHT22 không đọc nhanh hơn 0,5 Hz
constexpr uint32_t DHT_STALE_MS = 10000;        // quá 10 s không có mẫu DHT hợp lệ -> báo lỗi, không dùng giá trị cũ

void on_mqtt(void *, esp_event_base_t, int32_t id, void *) {
  switch (id) {
    case MQTT_EVENT_CONNECTED:
      if (s_ever) s_reconnects = s_reconnects + 1;
      s_ever = true; s_connected = true; s_flag_online = true;
      break;
    case MQTT_EVENT_DISCONNECTED:
      s_connected = false;
      break;
    default: break;
  }
}

float read_water_pct() {
  int raw = analogRead(PIN_POT_WATER);
  if (raw < 0) raw = 0;
  if (raw > 4095) raw = 4095;
  return (float)raw * 100.0f / 4095.0f;
}

// Trả true nếu có nhiệt độ/độ ẩm hợp lệ (tươi), ngược lại false và để NAN.
bool read_dht(float *t, float *h) {
  static uint32_t last_try = 0;
  uint32_t now = millis();
  if (last_try == 0 || now - last_try >= DHT_PERIOD_MS) {
    last_try = now;
    float hh = s_dht.readHumidity(), tt = s_dht.readTemperature();
    if (!isnan(hh) && !isnan(tt)) { s_last_hum = hh; s_last_temp = tt; s_last_dht_ok_ms = now; }
  }
  bool fresh = s_last_dht_ok_ms != 0 && (now - s_last_dht_ok_ms) < DHT_STALE_MS;
  *t = fresh ? s_last_temp : NAN;
  *h = fresh ? s_last_hum : NAN;
  return fresh;
}

// Ghi số thực hoặc null (JSON chuẩn không có NaN).
int put_num(char *dst, size_t cap, const char *key, float v) {
  return isnan(v) ? snprintf(dst, cap, ",\"%s\":null", key) : snprintf(dst, cap, ",\"%s\":%.1f", key, v);
}

void publish_cargo() {
  if (!s_connected) return;                     // seq chỉ tiêu thụ khi thật sự giao cho MQTT (như Motion Node)
  float water = read_water_pct(), temp, hum;
  bool ok = read_dht(&temp, &hum);
  char js[360];
  int n = snprintf(js, sizeof js,
                   "{\"device_id\":\"%s\",\"boot_id\":\"%s\",\"seq\":%lu,\"uptime_ms\":%llu,\"sensor_ok\":%s"
                   ",\"source_mode\":\"%s\",\"parent_device_id\":\"%s\"",
                   CARGO_DEVICE_ID, s_boot, (unsigned long)(s_seq + 1), (unsigned long long)(esp_timer_get_time() / 1000),
                   ok ? "true" : "false", CARGO_SOURCE_MODE, CARGO_PARENT_ID);
  n += put_num(js + n, sizeof js - n, "cargo_water_pct", water);
  n += put_num(js + n, sizeof js - n, "cargo_temp_c", temp);
  n += put_num(js + n, sizeof js - n, "cargo_humidity_pct", hum);
  n += snprintf(js + n, sizeof js - n, "}");
  if (n <= 0 || n >= (int)sizeof js) return;
  if (esp_mqtt_client_enqueue(s_cli, T_cargo, js, n, 0, 0, true) >= 0) {
    s_seq++;
    Serial.printf("[CARGO] %s\n", js);
  }
}

void publish_health() {
  if (!s_connected) return;
  char js[256];
  float t, h;
  bool ok = read_dht(&t, &h);
  int n = snprintf(js, sizeof js,
                   "{\"device_id\":\"%s\",\"free_heap_bytes\":%lu,\"min_free_heap_bytes\":%lu,\"uptime_ms\":%llu"
                   ",\"sensor_ok\":%s,\"mqtt_reconnects\":%lu}",
                   CARGO_DEVICE_ID, (unsigned long)ESP.getFreeHeap(), (unsigned long)ESP.getMinFreeHeap(),
                   (unsigned long long)(esp_timer_get_time() / 1000), ok ? "true" : "false", (unsigned long)s_reconnects);
  if (n > 0 && n < (int)sizeof js) esp_mqtt_client_enqueue(s_cli, T_health, js, n, 0, 0, true);
}

void publish_online() {
  char js[200];
  int n = snprintf(js, sizeof js, "{\"state\":\"online\",\"fw\":\"%s\",\"boot_id\":\"%s\"}", CARGO_FW_VERSION, s_boot);
  if (n > 0 && n < (int)sizeof js) esp_mqtt_client_enqueue(s_cli, T_status, js, n, 1, 1, true);   // retained, QoS 1
}
}  // namespace

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  s_dht.begin();
  snprintf(s_boot, sizeof s_boot, "%08lx", (unsigned long)esp_random());
  snprintf(T_cargo, sizeof T_cargo, "svmg/%s/cargo", CARGO_DEVICE_ID);
  snprintf(T_status, sizeof T_status, "svmg/%s/status", CARGO_DEVICE_ID);
  snprintf(T_health, sizeof T_health, "svmg/%s/health", CARGO_DEVICE_ID);
  snprintf(s_lwt, sizeof s_lwt, "{\"state\":\"offline\"}");
  Serial.printf("[CARGO] id=%s parent=%s boot_id=%s source=%s\n", CARGO_DEVICE_ID, CARGO_PARENT_ID, s_boot, CARGO_SOURCE_MODE);

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(SVMG_WIFI_SSID, SVMG_WIFI_PASS, SVMG_WIFI_CHANNEL);

  esp_mqtt_client_config_t c = {};
  c.broker.address.uri = SVMG_MQTT_URI;
  if (SVMG_MQTT_USER[0]) { c.credentials.username = SVMG_MQTT_USER; c.credentials.authentication.password = SVMG_MQTT_PASS; }
  c.credentials.client_id = CARGO_DEVICE_ID;
  c.session.last_will.topic = T_status;
  c.session.last_will.msg = s_lwt; c.session.last_will.msg_len = (int)strlen(s_lwt);
  c.session.last_will.qos = 1; c.session.last_will.retain = 1;
  c.session.keepalive = 30;
  c.network.reconnect_timeout_ms = 5000;
  c.network.timeout_ms = 5000;
  c.buffer.size = 1024; c.buffer.out_size = 1024;
  s_cli = esp_mqtt_client_init(&c);
  if (s_cli) esp_mqtt_client_register_event(s_cli, MQTT_EVENT_ANY, on_mqtt, nullptr);
}

void loop() {
  static uint32_t t_cargo = 0, t_health = 0;
  uint32_t now = millis();
  if (s_cli && !s_started && WiFi.status() == WL_CONNECTED) { esp_mqtt_client_start(s_cli); s_started = true; }
  if (s_flag_online && s_connected) { s_flag_online = false; publish_online(); }
  if (now - t_cargo >= CARGO_PERIOD_MS) { t_cargo = now; publish_cargo(); }
  if (now - t_health >= CARGO_HEALTH_MS) { t_health = now; publish_health(); }
  delay(20);
}
