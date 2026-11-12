// Cấu hình biên dịch của firmware. Giá trị nhạy cảm đặt trong include/secrets.h (KHÔNG commit; xem secrets.example.h).
#pragma once

#define SVMG_FW_VERSION "1.0.0"

#if __has_include("secrets.h")
#include "secrets.h"
#endif

#ifndef SVMG_DEVICE_ID
#define SVMG_DEVICE_ID "vessel-demo-01"
#endif

// 1 = bật WiFi/MQTT; 0 = chỉ chạy cục bộ (dùng để chứng minh cảnh báo không phụ thuộc mạng, T05)
#ifndef SVMG_NET
#define SVMG_NET 1
#endif

#ifndef SVMG_WIFI_SSID
#define SVMG_WIFI_SSID "Wokwi-GUEST"
#endif
#ifndef SVMG_WIFI_PASS
#define SVMG_WIFI_PASS ""
#endif
#ifndef SVMG_WIFI_CHANNEL
#define SVMG_WIFI_CHANNEL 6
#endif

// Broker: mặc định là cổng riêng của Wokwi tới máy phát triển (Private Gateway). Ghi đè trong secrets.h.
#ifndef SVMG_MQTT_URI
#define SVMG_MQTT_URI "mqtt://host.wokwi.internal:1883"
#endif
#ifndef SVMG_MQTT_USER
#define SVMG_MQTT_USER ""
#endif
#ifndef SVMG_MQTT_PASS
#define SVMG_MQTT_PASS ""
#endif

// Chỉ phát các trường mở rộng (acked, data_status, sea_state) trong telemetry khi đã thống nhất schema.
#ifndef SVMG_TELEMETRY_EXTRAS
#define SVMG_TELEMETRY_EXTRAS 0
#endif

// Tần số xử lý
#define SVMG_TICK_MS 50          // 20 Hz
