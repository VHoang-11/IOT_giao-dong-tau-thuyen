# Nhật ký kiểm thử – M1 (firmware / lõi C)

Ngày lập: 12/11/2026. Môi trường: Windows 11, PlatformIO Core 6.2.0, gcc 13.2 (MinGW-W64 UCRT), Python 3.13, Arduino-ESP32 3.3.x.
Quy ước trạng thái: **PASS** (đã chạy, đạt) · **FAIL** · **NOT RUN** (chưa chạy, có lý do – không được hiểu là đạt).

## 1. Kiểm thử tự động trên máy chủ (cùng lõi C với ESP32)

Lệnh: `cd tests/firmware && pio test -e native` → **178 ca, 178 PASS** (≈ 12 s).

| Bộ | Ca | Kết quả |
|---|---|---|
| test_filter (M1-02) | 29 | PASS |
| test_features (M1-03) | 17 | PASS |
| test_decision (M1-04) | 17 | PASS |
| test_alarm (M1-05) | 23 | PASS |
| test_cmd_config (M1-07) | 22 | PASS |
| test_evbuf (M1-06) | 8 | PASS |
| test_msg (M1-06) | 21 | PASS |
| test_engine (tích hợp) | 27 | PASS |
| test_t01_t05_t07 (M1-09) | 14 | PASS |

Lỗi thật tìm thấy và đã sửa nhờ kiểm thử (không phải chỉnh test cho qua):
1. Độ lợi DC của biquad float lệch ~5e-6 (cực gần 1 ở 0,5 Hz/20 Hz) → ép hệ số `b` theo `a1,a2` đã làm tròn (`filter.c`).
2. `rms_ratio` của tín hiệu im lặng trả 0 thay vì 1 (sàn 0,5° chỉ áp cho mẫu số) → áp cho cả hai vế.
3. **Bus I2C chết trả toàn 0 nhưng `valid=1` không bị phát hiện** (cổng gia tốc bỏ qua rồi vẫn tính là mẫu hợp lệ) → bước bị cổng không còn tính là phép đo hợp lệ; cảm biến chết giờ dẫn tới FAULT sau 10 s.
4. **`calibrate_zero` được chấp nhận khi đang có cảnh báo OFFSET** (có thể xóa bằng chứng nghiêng thật) → từ chối `FORBIDDEN_STATE` khi mức ≥ WARNING.
5. Lệnh `calibrate_zero` bị hủy giữa chừng (đổi chế độ) làm lệnh treo mãi ở trạng thái chờ → trả `FORBIDDEN_STATE`.
6. Độ phân giải thời gian `float` mất dần theo giờ chạy → đồng hồ lõi quấn vòng ở 8 192 s, pipeline hiểu bước lùi lớn là quấn vòng.

Kiểm tra độc lập khả năng bắt lỗi: đã thử đột biến `alarm_fsm.c` (cho phép mute khi CRITICAL) → `test_mute_does_not_stop_escalation…` FAIL đúng; đã hoàn nguyên.

### Số đo hành vi trên sóng tổng hợp của M1 (`pio test -e native -f test_engine -v`)
*Không phải bộ sinh của M2; chỉ chứng minh lõi hoạt động và cho M2 biết điểm khởi đầu của tham số.*

| Đại lượng | Đo được | Mục tiêu tham khảo (Bảng 10.2) |
|---|---|---|
| Độ trễ phát hiện S1-like (warm start) | 30 s | ≤ 60 s |
| Độ trễ phát hiện S2-like | **160 s** | ≤ 180 s (sát giới hạn) |
| Độ trễ phát hiện S3-like | 130 s | ≤ 240 s |
| Cảnh báo WARNING+ trong 1 giờ sóng bình thường (sum 3 sin, RMS ≈ 2,9°) | 0 | ≤ 1 / 10 giờ |
| Nghiêng tạm thời 5° trong 60 s (S0b-like) | 0 WARNING | 0 |
| Ngưỡng cứng 25°: bước chỉ từ gia tốc kế → CRITICAL | 17,9 s | (không đặt) |
| Ngưỡng cứng 25°: nghiêng dần có gyro nhất quán → CRITICAL | 9,4 s | (không đặt) |
| Leo thang WARNING→CRITICAL khi không ACK | 60,0 s ± 0,2 | 60 s |
| `calibrate_zero` hoàn tất | 30 s | 30 s |

## 2. Kích thước / tài nguyên: xem `firmware/docs/M1-08_resource_table.md` (ảnh 1 188 119 B flash, 57 036 B RAM tĩnh; lõi `engine` 3 336 B).

## 3. Thí nghiệm của M1 – T01, T05, T07

Phần "Trên máy chủ" đã PASS (mục 1). Phần "Trên Wokwi" là thủ tục thủ công; **chưa chạy** vì môi trường phát triển không chạy được
Wokwi. Điền cột "Kết quả Wokwi" khi chạy.

### T01 – MPU6050 ở SENSOR MODE (M1)
Chuẩn bị: `cd firmware && pio run`; Wokwi: `wokwi/wokwi.toml`. Mở Serial Monitor 115200. Khởi động ở SENSOR.

| Bước | Thao tác trong Wokwi (click MPU6050, chỉnh thanh trượt) | Kỳ vọng | Trên máy chủ | Kết quả Wokwi |
|---|---|---|---|---|
| 0 | Khởi động | Serial: `[HW] LCD:ok MPU6050:ok selftest |a|=1.0xx g (thang do OK)`. Nếu in `THANG DO LECH` → dùng Adafruit getEvent() (xem README) | – | NOT RUN |
| a | accelX=0, accelY=0, accelZ=1 g | dòng `R,…` roll ≈ 0,0 ± 0,1°, pitch ≈ 0,0 ± 0,1°; LCD `SEN R:+00.0°` | PASS (T01-a) | NOT RUN |
| b | accelY=0,5 ; accelZ=0,866 | roll = 30,0 ± 0,2° (sau ≈ 60 s do bộ lọc bù) | PASS (T01-b) | NOT RUN |
| c | accelX=−0,5 ; accelZ=0,866 | pitch = 30,0 ± 0,2° | PASS (T01-c) | NOT RUN |
| d | rotationX = 10 °/s trong **2–3 s rồi đưa về 0** (accel giữ 1 g) | trong những giây đầu, roll trong dòng `R,…` tăng với độ dốc ≈ **10 °/s** (kiểm tra thang gyro 131 LSB/(°/s)); sau đó bộ lọc bù kéo về 0 với hằng số 7,5 s. **Không để rotationX khác 0 lâu**: gyro không nhất quán với gia tốc kế làm roll trôi tới τ·ω (≈ 75°) và kích hoạt ngưỡng cứng (đúng thiết kế) | PASS (T01-d: chỉ kiểm tra quy đổi đơn vị) | NOT RUN |
| e | Sau ≥ 180 s mọi thứ ổn định | `T,…` có `NORMAL` (hết UNKNOWN), LED xanh | PASS (T01-e) | NOT RUN |
| f | Giữ nguyên giá trị MPU6050 không đổi (phương sai 0) | **không** báo lỗi (cố ý không có bộ phát hiện "đứng yên"); `i2c_err=0` | – | NOT RUN |
| g | Rút dây SDA của MPU6050 (hoặc bản `esp32dev_inject` gõ `i`) | sau ≈ 10 s: LCD `FAULT`, LED vàng+đỏ nháy nhanh, `[EV]` FAULT | PASS (T01-f, T07-a) | NOT RUN |

Ghi nhận Serial/LCD kèm ảnh chụp vào `docs/` khi chạy.

### T05 – Ngắt MQTT lúc có bất thường (M1 chủ trì, M4 demo)
Có broker: chạy Mosquitto (M4 `infra/`), `secrets.h` trỏ tới broker (Private Gateway: `host.wokwi.internal`).
Không có broker: dùng `pio run -e esp32dev_inject` + `wokwi/wokwi.inject.toml`, gõ `m` để ngắt/nối đường lên.

| Bước | Thao tác | Kỳ vọng | Trên máy chủ | Kết quả Wokwi |
|---|---|---|---|---|
| 1 | Chuyển MODE→SIMULATION, ×10 (`set_timewarp`) hoặc để ×1, chờ khởi động nguội 180 s | LED vàng nháy chậm rồi xanh | PASS (test_engine) | NOT RUN |
| 2 | SCENARIO → S1 (hoặc đẩy sea state bằng chiết áp lên 5) | CAUTION → WARNING (LED đỏ, còi ngắt quãng) | PASS (T05-a) | NOT RUN |
| 3 | **Ngắt MQTT** (dừng broker hoặc gõ `m`) khi đang WARNING | LED đỏ/còi **vẫn hoạt động**; Serial tiếp tục `[EV]`; dashboard báo offline (Last Will) | PASS (T05-a, T05-b) | NOT RUN |
| 4 | Để leo thang 60 s không ACK | LED đỏ, còi liên tục (CRITICAL) dù mất mạng | PASS (test_engine) | NOT RUN |
| 5 | **Nối lại** | `[HEALTH] evbuf=N` giảm về 0; backend nhận đủ sự kiện, đúng thứ tự `seq`, không trùng | PASS (T05-c, T05-d) | NOT RUN |
| 6 | Reset thiết bị (giữa lúc offline) | `boot_id` mới; **sự kiện chưa được xác nhận trong RAM bị mất** (giới hạn đã nêu, mục 9.2) | – | NOT RUN |

### T07 – Lỗi cảm biến / thiếu mẫu (M1)
Dùng `esp32dev_inject`; gõ ký tự vào Serial Monitor: `i` mất I2C · `z` bus trả 0 · `n` NaN · `d` mất 30 % mẫu · `s` bão hòa · `x` hết lỗi.

| Ca | Kỳ vọng | Trên máy chủ | Kết quả Wokwi |
|---|---|---|---|
| `i` (30 s) | FAULT sau 10 s; LED không xanh; không WARNING giả | PASS (T07-a) | NOT RUN |
| `z` | FAULT; không xanh | PASS (T07-b) | NOT RUN |
| `s` | FAULT | PASS (T07-c) | NOT RUN |
| `n` | FAULT, trạng thái không nhiễm NaN | PASS (T07-d) | NOT RUN |
| `d` | không bao giờ báo xanh khi dữ liệu không-OK; không WARNING giả | PASS (T07-e) | NOT RUN |
| `x` sau `i` | 1 `FAULT` + 1 `FAULT_CLEARED`; về NORMAL sau khi cửa sổ đầy lại | PASS (T07-f) | NOT RUN |
| Lỗi khi đang CRITICAL | không tự hạ cảnh báo | PASS (T07-g) | NOT RUN |

### Ghi chú về T13 (M1 chủ trì)
Cơ chế chèn lỗi (`esp32dev_inject`) sẵn sàng cho T13. **Phần tính chỉ số/điểm sức khỏe chưa có WP** – xem `firmware/docs/CONTRACT_PROPOSALS.md` mục C1.

## 4. Chưa thực hiện / phụ thuộc người khác
| Hạng mục | Lý do |
|---|---|
| Chạy thủ tục Wokwi (T01/T05/T07) | cần mở Wokwi (môi trường phát triển không chạy được) |
| Chạy với broker thật, cmd/config round-trip | cần Mosquitto/backend (M3, M4) |
| Đo thời gian suy luận RF và `stack_hwm` | cần `model.h` (M2-06) và chạy trên thiết bị |
| T03 (Python ↔ lõi C ↔ ESP32), T09, T10 phía đầy đủ | thuộc M2/M3; lõi C đã sẵn cho M2 gọi qua ctypes |
| T08 | stretch, cần Wokwi CLI + token |
