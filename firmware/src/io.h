// LED / buzzer / 3 nút (MODE, SCENARIO, ACK) - M1-05. Chống rung bằng phần mềm 30 ms.
#pragma once
#include <Arduino.h>
#include "svmg_alarm.h"

enum ButtonEvent : uint8_t { BTN_NONE = 0, BTN_MODE_SHORT, BTN_SCN_SHORT, BTN_ACK_SHORT, BTN_ACK_LONG };

void io_init();
void io_apply_outputs(const svmg_alarm_out_t &o, uint32_t now_ms);   // chỉ ghi chân khi trạng thái thay đổi
void io_all_leds(bool on);
void io_beep(uint16_t ms);                                           // chặn, chỉ dùng lúc khởi động
ButtonEvent io_poll_buttons(uint32_t now_ms);                        // gọi thường xuyên (mỗi vài ms)
int  io_read_sea_state();                                            // chiết áp -> 0..5, có trễ chống nhảy
