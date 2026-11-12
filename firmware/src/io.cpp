#include "io.h"
#include "pins.h"

static const uint32_t DEBOUNCE_MS = 30, LONG_PRESS_MS = 3000;

struct Btn { int pin; bool stable; bool raw; uint32_t t_change; uint32_t t_press; bool long_fired; };
static Btn B[3] = {
  { PIN_BTN_MODE, false, false, 0, 0, false },
  { PIN_BTN_SCN,  false, false, 0, 0, false },
  { PIN_BTN_ACK,  false, false, 0, 0, false },
};

void io_init() {
  for (auto &b : B) pinMode(b.pin, INPUT_PULLUP);
  pinMode(PIN_LED_G, OUTPUT); pinMode(PIN_LED_Y, OUTPUT); pinMode(PIN_LED_R, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  analogReadResolution(12);
}

void io_all_leds(bool on) { digitalWrite(PIN_LED_G, on); digitalWrite(PIN_LED_Y, on); digitalWrite(PIN_LED_R, on); }

void io_beep(uint16_t ms) { tone(PIN_BUZZER, 1000); delay(ms); noTone(PIN_BUZZER); }

static bool blink(uint8_t mode, uint32_t now) {
  switch (mode) {
    case SVMG_OUT_ON: return true;
    case SVMG_OUT_BLINK_SLOW: return (now / 500) % 2 == 0;   // 1 Hz
    case SVMG_OUT_BLINK_FAST: return (now / 125) % 2 == 0;   // 4 Hz
    default: return false;
  }
}

void io_apply_outputs(const svmg_alarm_out_t &o, uint32_t now) {
  static int8_t last_g = -1, last_y = -1, last_r = -1, last_b = -1;
  int8_t g = blink(o.led_g, now), y = blink(o.led_y, now), r = blink(o.led_r, now);
  if (g != last_g) { digitalWrite(PIN_LED_G, g); last_g = g; }
  if (y != last_y) { digitalWrite(PIN_LED_Y, y); last_y = y; }
  if (r != last_r) { digitalWrite(PIN_LED_R, r); last_r = r; }
  int8_t buz = 0;
  if (o.buzzer == SVMG_BUZ_CONTINUOUS) buz = 1;
  else if (o.buzzer == SVMG_BUZ_INTERMITTENT) buz = ((now % 1000) < 300) ? 1 : 0;   // 300 ms kêu / 700 ms nghỉ
  if (buz != last_b) { if (buz) tone(PIN_BUZZER, 1000); else noTone(PIN_BUZZER); last_b = buz; }
}

ButtonEvent io_poll_buttons(uint32_t now) {
  ButtonEvent ev = BTN_NONE;
  for (int i = 0; i < 3; i++) {
    Btn &b = B[i];
    bool pressed = (digitalRead(b.pin) == LOW);
    if (pressed != b.raw) { b.raw = pressed; b.t_change = now; }
    if ((now - b.t_change) >= DEBOUNCE_MS && b.stable != b.raw) {
      b.stable = b.raw;
      if (b.stable) { b.t_press = now; b.long_fired = false; }
      else if (!b.long_fired) {                           // nhả nút: nhấn ngắn
        if (i == 0) ev = BTN_MODE_SHORT; else if (i == 1) ev = BTN_SCN_SHORT; else ev = BTN_ACK_SHORT;
      }
    }
    if (i == 2 && b.stable && !b.long_fired && (now - b.t_press) >= LONG_PRESS_MS) {   // ACK giữ 3 s: trang chẩn đoán
      b.long_fired = true; ev = BTN_ACK_LONG;
    }
  }
  return ev;
}

int io_read_sea_state() {
  static int last = -1;
  int raw = analogRead(PIN_POT);                           // 0..4095
  int s = raw * 6 / 4096;                                  // chia đều 6 mức 0..5 (không để mức 5 chỉ ở đúng đầu mút)
  if (s > 5) s = 5;
  if (last < 0) { last = s; return s; }
  // trễ: chỉ đổi khi vượt quá ranh giới kề với mức hiện tại hơn 40 đơn vị ADC để tránh nhấp nháy
  if (s > last && raw > (last + 1) * 4096 / 6 + 40) last = s;
  else if (s < last && raw < last * 4096 / 6 - 40) last = s;
  return last;
}
