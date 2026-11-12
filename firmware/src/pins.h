// Sơ đồ chân (M1-01) - khớp wokwi/diagram.json và đề cương mục 5.2.
#pragma once

constexpr int PIN_SDA = 21, PIN_SCL = 22;
constexpr int PIN_BTN_MODE = 14, PIN_BTN_SCN = 27, PIN_BTN_ACK = 13;   // INPUT_PULLUP, nhấn = LOW
constexpr int PIN_LED_G = 33, PIN_LED_Y = 26, PIN_LED_R = 25;
constexpr int PIN_BUZZER = 32;
constexpr int PIN_POT = 34;                                            // ADC1, dùng được khi WiFi bật

constexpr uint8_t I2C_ADDR_MPU = 0x68;
constexpr uint8_t I2C_ADDR_LCD = 0x27;
