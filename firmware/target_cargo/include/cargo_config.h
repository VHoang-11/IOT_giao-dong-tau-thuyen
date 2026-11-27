// Cấu hình biên dịch của Cargo Node. Giá trị nhạy cảm đặt trong include/secrets_cargo.h (KHÔNG commit).
#pragma once

#define CARGO_FW_VERSION "cargo-1.0.0"

#if __has_include("secrets_cargo.h")
#include "secrets_cargo.h"
#endif

#ifndef CARGO_DEVICE_ID
#define CARGO_DEVICE_ID "vessel-demo-01-cargo"
#endif
// Tàu chính mà hầm hàng này thuộc về (chỉ để đối chiếu; liên kết chính thức do Admin đặt trên Backend).
#ifndef CARGO_PARENT_ID
#define CARGO_PARENT_ID "vessel-demo-01"
#endif
// Mọi dữ liệu mang cờ nguồn: Wokwi = SIMULATION; cảm biến thật = SENSOR.
#ifndef CARGO_SOURCE_MODE
#define CARGO_SOURCE_MODE "SIMULATION"
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
#ifndef SVMG_MQTT_URI
#define SVMG_MQTT_URI "mqtt://host.wokwi.internal:1883"
#endif
#ifndef SVMG_MQTT_USER
#define SVMG_MQTT_USER ""
#endif
#ifndef SVMG_MQTT_PASS
#define SVMG_MQTT_PASS ""
#endif

// Chân (Cargo Node là mạch riêng nên dùng lại đúng số chân của sơ đồ cũ).
#define PIN_POT_WATER 35   // ADC1, mực nước hầm hàng
#define PIN_DHT 4          // DHT22 nhiệt độ & độ ẩm hầm hàng

#define CARGO_PERIOD_MS 5000      // chu kỳ publish cargo (DHT22 tối thiểu 2 s)
#define CARGO_HEALTH_MS 30000     // chu kỳ publish health (khớp contract: 30 s)
