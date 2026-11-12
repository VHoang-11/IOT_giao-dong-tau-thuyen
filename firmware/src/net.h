// WiFi + MQTT (M1-06). Dùng esp-mqtt có sẵn trong framework (QoS 1 + PUBACK, Last Will, retained, tự nối lại).
// Toàn bộ logic cảnh báo KHÔNG phụ thuộc module này: mất mạng chỉ làm sự kiện nằm lại trong bộ đệm (svmg_evbuf).
#pragma once
#include <Arduino.h>
#include "msg.h"
#include "svmg_evbuf.h"

enum RxKind : uint8_t { RX_CMD = 1, RX_CONFIG = 2 };
struct RxItem { RxKind kind; uint32_t rx_ms; uint16_t len; char payload[400]; };

void net_begin(const MsgIdent &id, const char *model_version_unused = nullptr);
// Gọi mỗi vòng loop: xử lý kết nối, PUBACK, gửi bù sự kiện từ bộ đệm. config_version dùng cho bản tin status online.
void net_service(uint32_t now_ms, svmg_evbuf_t *buf, uint32_t config_version);
bool net_connected();
// Gửi không qua bộ đệm. Trả msg_id (>=0) hoặc -1 nếu lỗi/mất kết nối.
int  net_publish(const char *subtopic, const char *payload, int len, int qos, bool retain);
bool net_pop_rx(RxItem *out);
int  net_rssi();
uint32_t net_reconnects();
uint32_t net_rx_dropped();
uint32_t net_connected_since_ms();
#ifdef SVMG_FAULT_INJECT
void net_inject_blackout(bool on);   // mô phỏng ngắt đường lên MQTT (T05) khi không có broker để tắt
#endif
