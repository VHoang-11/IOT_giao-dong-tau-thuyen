// Sao chép thành secrets_cargo.h (đã nằm trong .gitignore) và điền giá trị thật. KHÔNG commit secrets_cargo.h.
// Tài khoản MQTT riêng của Cargo Node, cấp trong infra/mosquitto/passwd (mosquitto_passwd) và infra/mosquitto/acl.
#pragma once

#define SVMG_MQTT_USER "vessel-demo-01-cargo"
#define SVMG_MQTT_PASS "doi-mat-khau-nay"

// Tùy chọn (mặc định xem cargo_config.h):
// #define SVMG_MQTT_URI "mqtt://host.wokwi.internal:1883"
// #define CARGO_DEVICE_ID "vessel-demo-01-cargo"
// #define CARGO_PARENT_ID "vessel-demo-01"
// #define CARGO_SOURCE_MODE "SENSOR"      // mặc định "SIMULATION" (Wokwi)
