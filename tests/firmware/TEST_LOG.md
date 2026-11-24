# Nhật ký kiểm thử M1 — bản 23 đặc trưng

Cập nhật **18/11/2026**. Chỉ PASS khi có chạy thật; build/kiểm thử máy chủ không phải chạy mạch.
Môi trường: Windows, GCC 13.2, Python 3.13.9; ESP32 dùng espressif32 8.0.0 / Arduino-ESP32 3.3.12.

## 1. Kiểm thử tự động trên máy chủ

`python tests/firmware/tools/run_native.py`: **208 ca PASS, 0 FAIL**. Gồm alarm 29, cmd/config 26,
decision 22, engine 31, evbuf 8, features 13, filter 30, message 31, FRD 4, T01/T05/T07 host 14.
Test 14 đặc trưng cũ được thay bằng kiểm tra giải tích 23 đặc trưng và parity trực tiếp với extractor M2.

| Công cụ | Kết quả |
|---|---|
| `check_features23.py` | 23 chuỗi × 23 = **529 giá trị khớp**, đúng thứ tự, không đọc tương lai; cùng float32 đầu vào với Python M2 |
| `check_filter23.py` | **8.000 giá trị** khớp CF + SciPy Butterworth4 4 Hz; sai số lớn nhất **1,681e-7 rad** |
| `check_model_adapter.py` | **6 artifact cases PASS**: đúng metadata, 14 mục cũ, sai schema, sai preprocessing, thiếu metadata, không có model |
| `validate_messages.py` | **46 bản tin hợp lệ, 0 vi phạm**; 10 event gồm 4 alarm, 1 CLEARED, 1 ACK; không lỗi vòng đời/ACL |
| `crosscheck_crc.py` | **4.004/4.004** + **300/300** số thực chính xác cao khớp CRC tham chiếu backend |

Kiểm tra an toàn: mute CRITICAL bị chặn; TTL/idempotency; cảnh báo độc lập mạng; thiếu mẫu không hiển thị xanh;
FAULT sau mất mẫu liên tục 10 s; model không nhận vector thiếu/NaN; nhãn model lỗi → UNKNOWN.
API host `svmg_features_from_series` dùng frame stack khoảng 25,5 KB vì chứa ring cục bộ, **không gọi trên ESP32**.
ESP32 dùng engine/ring/workspace tĩnh; stack thực tế còn phải đo khi chạy thiết bị.

Độ trễ trên **sóng tổng hợp của M1**, không thay T04/dataset M2:

| Hành vi | Đo được |
|---|---|
| S1-like | 42 s |
| S2-like | 152 s |
| S3-like | 142 s; lớp bắt được HIGH_ROLL, chưa chứng minh AMPLITUDE_GROWTH đúng |
| Ngưỡng cứng, bước nghiêng chỉ gia tốc | 17,2 s |
| Ngưỡng cứng, nghiêng dần có gyro nhất quán | 9,1 s |
| Hiệu chuẩn | 30 s |

## 2. Build và tài nguyên

Bảng đo và trạng thái build: [M1-08_resource_table.md](../../firmware/docs/M1-08_resource_table.md).
Bản RF vẫn là stub; các test adapter không phải kết quả suy luận RF thật.

## 3. Thí nghiệm của M1 – T01, T05, T07

Phần "Trên máy chủ" đã PASS (mục 1). Phần "Trên Wokwi" là thủ tục thủ công; **chưa chạy** trong đợt cập nhật này. Điền cột "Kết quả Wokwi" khi chạy.

### T01 – MPU6050 ở SENSOR MODE (M1)
Chuẩn bị: `cd firmware && pio run`; Wokwi: `wokwi/wokwi.toml`. Mở Serial Monitor 115200. Khởi động ở SENSOR.

| Bước | Thao tác trong Wokwi (click MPU6050, chỉnh thanh trượt) | Kỳ vọng | Trên máy chủ | Kết quả Wokwi |
|---|---|---|---|---|
| 0 | Khởi động | Serial: `[HW] LCD:ok MPU6050:ok selftest |a|=1.0xx g (thang do OK)`. Nếu in `THANG DO LECH` → dùng Adafruit getEvent() (xem README) | – | NOT RUN |
| a | accelX=0, accelY=0, accelZ=1 g | dòng `R,…` roll ≈ 0,0 ± 0,1°, pitch ≈ 0,0 ± 0,1°; LCD `SEN R:+00.0°` | PASS (T01-a) | NOT RUN |
| b | accelY=0,5 ; accelZ=0,866 | roll = 30,0 ± 0,2° (sau ≈ 60 s do bộ lọc bù) | PASS (T01-b) | NOT RUN |
| c | accelX=−0,5 ; accelZ=0,866 | pitch = 30,0 ± 0,2° | PASS (T01-c) | NOT RUN |
| d | rotationX = 10 °/s trong **2–3 s rồi đưa về 0** (accel giữ 1 g) | trong những giây đầu, roll trong dòng `R,…` tăng với độ dốc ≈ **10 °/s** (kiểm tra thang gyro 131 LSB/(°/s)); sau đó bộ lọc bù kéo về 0 với hằng số 7,5 s. **Không để rotationX khác 0 lâu**: gyro không nhất quán với gia tốc kế làm roll trôi tới τ·ω (≈ 75°) và kích hoạt ngưỡng cứng (đúng thiết kế) | PASS (T01-d: chỉ kiểm tra quy đổi đơn vị) | NOT RUN |
| e | Sau ≥ 182 s mọi thứ ổn định | `T,…` có `NORMAL` (hết UNKNOWN), LED xanh | PASS (T01-e) | NOT RUN |
| f | Giữ nguyên giá trị MPU6050 không đổi (phương sai 0) | **không** báo lỗi (cố ý không có bộ phát hiện "đứng yên"); `i2c_err=0` | – | NOT RUN |
| g | Rút dây SDA của MPU6050 (hoặc bản `esp32dev_inject` gõ `i`) | sau ≈ 10 s: LCD `FAULT`, LED vàng+đỏ nháy nhanh, `[EV]` FAULT | PASS (T01-f, T07-a) | NOT RUN |

Ghi nhận Serial/LCD kèm ảnh chụp vào `docs/` khi chạy.

### T05 – Ngắt MQTT lúc có bất thường (M1 chủ trì, M4 demo)
Có broker: chạy Mosquitto (M4 `infra/`), `secrets.h` trỏ tới broker (Private Gateway: `host.wokwi.internal`).
Không có broker: dùng `pio run -e esp32dev_inject` + `wokwi/wokwi.inject.toml`, gõ `m` để ngắt/nối đường lên.

| Bước | Thao tác | Kỳ vọng | Trên máy chủ | Kết quả Wokwi |
|---|---|---|---|---|
| 1 | Chuyển MODE→SIMULATION, ×10 (`set_timewarp`) hoặc để ×1, chờ khởi động nguội khoảng 182 s | LED vàng nháy chậm rồi xanh | PASS (test_engine) | NOT RUN |
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
| Chạy thủ tục Wokwi (T01/T05/T07) | cần thực hiện mô phỏng/thiết bị và lưu kết quả |
| Chạy với broker thật, cmd/config round-trip | cần Mosquitto/backend (M3, M4) |
| Đo thời gian suy luận RF và `stack_hwm` | cần `model.h` (M2-06) và chạy trên thiết bị |
| T03 (Python ↔ lõi C ↔ ESP32), T09, T10 phía đầy đủ | thuộc M2/M3; lõi C đã sẵn cho M2 gọi qua ctypes |
| T08 | stretch, cần Wokwi CLI + token |
