// LCD 16x2 qua PCF8574 (địa chỉ 0x27), điều khiển HD44780 4-bit. Tự viết để khỏi thêm thư viện.
#pragma once
#include <Arduino.h>

bool lcd_begin();
void lcd_clear();
void lcd_line(uint8_t row, const char *text16);   // tự đệm khoảng trắng tới 16 ký tự; chỉ ghi lại khi nội dung đổi
bool lcd_present();
