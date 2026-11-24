// M2-R2: target ESP32 CÔ LẬP chạy RF proxy nhị phân M2-R1 trên vector 23 feature nhận qua Serial (protocol: README.md).
// Không phải firmware production: không dùng svmg_engine/svmg_class_t/Baseline B/alarm.
#include <Arduino.h>
#include <esp_timer.h>
#include <string.h>
extern "C" {
#include "svmg_rf_proxy_demo.h"
}
static_assert(sizeof(float) == 4 && SVMG_RF_PROXY_DEMO_N_FEATURES == 23, "RF demo needs float32 and 23 features");

namespace {
constexpr uint8_t SYNC0 = 0x52, SYNC1 = 0x46, VERSION = 1, MAX_VALUES = 32;
constexpr uint16_t MAX_RX = 5 + 4 * MAX_VALUES, MAX_TX = 240;
constexpr uint32_t BYTE_TIMEOUT_MS = 1000;
enum Type : uint8_t { PREDICT = 0x01, HELLO_REQ = 0x02, HELLO = 0x80, RESULT = 0x81, ERROR_FRAME = 0x8f };
enum Error : uint8_t { BAD_SYNC = 1, BAD_CRC, BAD_VERSION, BAD_LENGTH, BAD_PAYLOAD, TIMEOUT, BAD_TYPE };
uint8_t rx[MAX_RX], tx[MAX_TX];  // bộ đệm tĩnh, không cấp phát động
float values[MAX_VALUES];

void put32(uint8_t *p, uint32_t v) { for (int i = 0; i < 4; ++i) p[i] = (uint8_t)(v >> (8 * i)); }
uint32_t get32(const uint8_t *p) { return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24); }
uint32_t crc32(uint32_t c, const uint8_t *p, size_t n) {  // CRC-32/ISO-HDLC (= zlib.crc32), nối tiếp được
  c = ~c;
  while (n--) { c ^= *p++; for (int k = 0; k < 8; ++k) c = (c >> 1) ^ ((c & 1u) ? 0xedb88320u : 0u); }
  return ~c;
}
void send_frame(uint8_t type, const uint8_t *p, uint16_t n) {
  uint8_t h[4] = {VERSION, type, (uint8_t)n, (uint8_t)(n >> 8)}, c[4];
  put32(c, crc32(crc32(0, h, 4), p, n));
  Serial.write(SYNC0); Serial.write(SYNC1); Serial.write(h, 4); Serial.write(p, n); Serial.write(c, 4);
}
void send_error(uint8_t code) {  // bỏ byte còn lại tới khi line im 50 ms (tối đa 2 s) rồi báo đúng một ERROR
  uint32_t start = millis(), idle = start;
  while ((uint32_t)(millis() - idle) < 50 && (uint32_t)(millis() - start) < 2000) {
    if (Serial.available()) { Serial.read(); idle = millis(); } else delay(1);
  }
  send_frame(ERROR_FRAME, &code, 1);
}
uint16_t put_str(uint8_t *p, const char *s) { size_t n = strnlen(s, 64); p[0] = (uint8_t)n; memcpy(p + 1, s, n); return (uint16_t)(n + 1); }
void send_hello() {
  uint16_t n = 0, nodes = SVMG_RF_PROXY_DEMO_N_NODES, mhz = (uint16_t)ESP.getCpuFreqMHz();
  tx[n++] = VERSION; tx[n++] = SVMG_RF_PROXY_DEMO_N_FEATURES; tx[n++] = SVMG_RF_PROXY_DEMO_N_TREES;
  memcpy(tx + n, &nodes, 2); n += 2;
  const char *fields[] = {RF_DEMO_MODEL_VERSION, RF_DEMO_MODEL_SHA256, SVMG_RF_PROXY_DEMO_FEATURE_ORDER_SHA256,
                          "m2r2-rf-demo/esp32dev/arduino", ESP.getChipModel()};
  for (const char *f : fields) n += put_str(tx + n, f);
  memcpy(tx + n, &mhz, 2); n += 2;
  send_frame(HELLO, tx, n);
}
bool read_n(uint8_t *p, uint16_t n) {
  for (uint16_t i = 0; i < n; ++i) {
    uint32_t start = millis();
    while (!Serial.available()) { if ((uint32_t)(millis() - start) >= BYTE_TIMEOUT_MS) return false; delay(0); }
    p[i] = (uint8_t)Serial.read();
  }
  return true;
}
void predict(uint16_t len) {
  uint8_t count = rx[4];
  if (len < 5 || count > MAX_VALUES || len != 5 + 4 * count) { send_error(BAD_PAYLOAD); return; }
  memcpy(values, rx + 5, 4u * count);  // float32 little-endian, đúng bit host gửi
  svmg_rf_proxy_demo_output_t out = {SVMG_RF_PROXY_DEMO_PRED_INVALID, -1.0f};
  int64_t t0 = esp_timer_get_time();  // chỉ đo thời gian gọi model, không gồm serial
  int status = svmg_rf_proxy_demo_predict(values, count, &out);
  uint32_t elapsed = (uint32_t)(esp_timer_get_time() - t0);
  if (status != SVMG_RF_PROXY_DEMO_OK) out.pred = SVMG_RF_PROXY_DEMO_PRED_INVALID;  // lỗi không bao giờ thành NEG
  memcpy(tx, rx, 4);  // sample_id
  tx[4] = (uint8_t)(int8_t)status; tx[5] = (uint8_t)(int8_t)out.pred;
  memcpy(tx + 6, &out.score, 4); put32(tx + 10, elapsed);
  send_frame(RESULT, tx, 14);
}
void handle_frame() {
  uint8_t s[2], h[4], c[4];
  if (!read_n(s, 1) || s[0] != SYNC0) { send_error(BAD_SYNC); return; }
  if (!read_n(s + 1, 1)) { send_error(TIMEOUT); return; }
  if (s[1] != SYNC1) { send_error(BAD_SYNC); return; }
  if (!read_n(h, 4)) { send_error(TIMEOUT); return; }
  uint16_t len = (uint16_t)(h[2] | (h[3] << 8));
  if (len > MAX_RX) { send_error(BAD_LENGTH); return; }  // không đọc payload vượt giới hạn
  if (!read_n(rx, len) || !read_n(c, 4)) { send_error(TIMEOUT); return; }
  if (crc32(crc32(0, h, 4), rx, len) != get32(c)) { send_error(BAD_CRC); return; }
  if (h[0] != VERSION) { send_error(BAD_VERSION); return; }
  if (h[1] == PREDICT) predict(len);
  else if (h[1] == HELLO_REQ && len == 0) send_hello();
  else send_error(BAD_TYPE);
}
}  // namespace

void setup() { Serial.setRxBufferSize(512); Serial.begin(115200); delay(50); send_hello(); }
void loop() { if (Serial.available()) handle_frame(); else delay(1); }
