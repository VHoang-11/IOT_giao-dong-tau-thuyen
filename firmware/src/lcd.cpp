#include "lcd.h"
#include <Wire.h>
#include "pins.h"

static const uint8_t RS = 0x01, EN = 0x04, BL = 0x08;
static bool s_ok = false;
static char s_cache[2][17];

static bool expander(uint8_t v) {
  Wire.beginTransmission(I2C_ADDR_LCD);
  Wire.write(v | BL);
  return Wire.endTransmission() == 0;
}

static void pulse(uint8_t v) { expander(v | EN); delayMicroseconds(1); expander(v & ~EN); delayMicroseconds(50); }

static void write4(uint8_t nibble, uint8_t rs) { pulse((uint8_t)((nibble << 4) | rs)); }

static void send(uint8_t b, uint8_t rs) { write4(b >> 4, rs); write4(b & 0x0F, rs); }

bool lcd_begin() {
  Wire.beginTransmission(I2C_ADDR_LCD);
  s_ok = (Wire.endTransmission() == 0);
  if (!s_ok) return false;
  delay(50);
  write4(0x03, 0); delay(5); write4(0x03, 0); delayMicroseconds(150); write4(0x03, 0); write4(0x02, 0);   // chuyển về 4-bit
  send(0x28, 0);        // 2 dòng, 5x8
  send(0x0C, 0);        // bật hiển thị, tắt con trỏ
  send(0x06, 0);        // tăng địa chỉ
  lcd_clear();
  return true;
}

void lcd_clear() {
  if (!s_ok) return;
  send(0x01, 0); delay(2);
  memset(s_cache, 0, sizeof s_cache);
}

bool lcd_present() { return s_ok; }

void lcd_line(uint8_t row, const char *text) {
  if (!s_ok || row > 1) return;
  char line[17];
  size_t i = 0;
  for (; i < 16 && text[i]; i++) line[i] = text[i];
  for (; i < 16; i++) line[i] = ' ';
  line[16] = 0;
  if (memcmp(line, s_cache[row], 17) == 0) return;      // không đổi -> khỏi tốn thời gian trên bus I2C dùng chung với MPU6050
  send((uint8_t)(0x80 | (row ? 0x40 : 0x00)), 0);
  for (int k = 0; k < 16; k++) send((uint8_t)line[k], RS);
  memcpy(s_cache[row], line, 17);
}
