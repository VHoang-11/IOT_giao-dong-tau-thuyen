// Sao chép thành secrets.h (đã nằm trong .gitignore) và điền giá trị thật. KHÔNG commit secrets.h.
#pragma once

// Mỗi thiết bị một tài khoản MQTT (đề cương 9.3). Mật khẩu do infra/ (M4) cấp.
#define SVMG_MQTT_URI  "mqtt://host.wokwi.internal:1883"
#define SVMG_MQTT_USER "vessel-demo-01"
#define SVMG_MQTT_PASS "doi-mat-khau-nay"
// #define SVMG_DEVICE_ID "vessel-demo-02"

// TLS (khuyến nghị khi broker hỗ trợ): đổi URI sang mqtts://..., định nghĩa CA của broker và bật cờ biên dịch -DSVMG_MQTT_TLS
// #define SVMG_MQTT_URI "mqtts://broker.example:8883"
// #define SVMG_MQTT_CA_PEM "-----BEGIN CERTIFICATE-----\n...(PEM của CA)...\n-----END CERTIFICATE-----\n"
