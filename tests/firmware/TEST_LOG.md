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

#### T01-diag (M2-R4) – MPU6050 mô phỏng → Core C → 23 đặc trưng
Build `pio run -e esp32dev_diag` (bản chẩn đoán; `esp32dev` mặc định không đổi), Wokwi chọn `wokwi/wokwi.diag.toml`
(cùng `diagram.json`, part `imu`, RFC2217 cổng 4000). Bản này thêm dòng `I,` 1 Hz (thanh ghi thô, WHO_AM_I, lỗi I2C),
`F,` mỗi 10 s (status, mask, ready, n60/n180, 23 giá trị, `nan` = INVALID) và `[DIAG] invalid:` khi mask đổi.
Ghi bằng chứng (chỉ đọc): `.venv/bin/python firmware/tools/wokwi_sensor_capture.py --seconds 300 --run-id imu01`
→ `ml/data/parity/wokwi_mpu6050/imu01/` (gitignored, kèm SHA-256). Nguồn là MPU6050 **mô phỏng**, không phải cảm biến thật.

| Bước (t tính từ lúc boot) | Thao tác MPU6050 | Kỳ vọng (dự đoán bằng Core C trên máy chủ) | Kết quả Wokwi |
|---|---|---|---|
| 0–182 s | giữ accel (0, 0, 1 g), gyro 0 | `F` ready 1/0 từ ~62 s (11/23), ready 1/1 ở ~182 s; phương sai 0 → 20/23: `roll_dominant_sign_ratio_180`, `roll_rms_ratio_180`, `roll_rms_trend_r2_180` INVALID do mẫu số bằng 0 (đúng contract, không phải lỗi) | NOT RUN (acq03 không giữ tĩnh tới 182 s) |
| ~100 s | accelY 0,5 g, accelZ 0,866 g (nghiêng tĩnh 30°, gyro 0) | dòng `I` đổi ay/az (8192/14189 LSB); `R` roll → 30° (τ 7,5 s); có lúc 23/23 khi cửa sổ 180 s chứa bước nghiêng | PASS (acq03, bản `esp32dev_diag_acq`) |
| sau đó | giữ nguyên | `roll_rms_trend_r2_180` lại INVALID khi chuỗi RMS hằng số (22/23) | NOT RUN |

Thanh trượt Wokwi chỉ tạo được nghiêng tĩnh; dao động liên tục nhất quán gyro–accel cần Automation Scenario (wokwi-cli + token, chưa có).

**Kết quả `imu01` (Wokwi, MPU6050 mô phỏng): PARTIAL.** I2C/thanh ghi/roll 0→30° đạt, 0 lỗi I2C, nhưng 0/23 đặc trưng: cửa sổ reset
đều mỗi 32 s (n60 100→200→300→100, 8 lần trong 300 s), đúng lúc lần cập nhật thứ 3 sau mỗi lần reset. Không mất mẫu 10 Hz,
không có đổi chế độ/khởi động lại. Giả thuyết (chưa xác nhận): thời gian tính đặc trưng chạy đồng bộ trong vòng lấy mẫu 20 Hz tăng theo n
(trên máy chủ: n=300 ≈ 2,5× n=100; n=1800 ≈ 5,6× n=300) nên mẫu kế tiếp đến trễ > `max_gap_s` 75 ms → pipeline coi là khoảng trống.
Chẩn đoán: bản diag in thêm `G,` 1 Hz (cnt_gap, overruns, mẫu trễ, max khoảng mẫu/loop/sampling/LCD/mạng, `feature_update` last/max ms)
và `[DIAG] GAP` ngay khi `cnt_gap` tăng. A/B mạng: `pio run -e esp32dev_diag_nonet` + `wokwi/wokwi.diag_nonet.toml` (SVMG_NET=0).
Không nới `max_gap_s`; nếu xác nhận, sửa đúng là tách việc lấy mẫu khỏi việc tính đặc trưng (thay đổi kiến trúc M1, cần review M1).

**`gap01` xác nhận:** `feature_update` 19,8/38,5/57,3 ms ở n60 100/200/300 (tuyến tính, ~0,19 ms/mẫu trên Wokwi); ở n60=300 khối lấy mẫu
75 ms → khoảng mẫu 76 ms > 75 ms → reset; mạng 0 ms, LCD 0,4 ms. `gap02_old_diag_not_acq` (bản diag cũ) tái hiện: 8 GAP, tối đa 94 ms.
**Sửa (cờ `SVMG_ACQ_TASK`, chỉ env `esp32dev_diag_acq`; production chưa bật, cần M1 duyệt):** task 20 Hz ưu tiên 3 cùng core đọc MPU6050
(timestamp `millis()` lúc đọc) vào hàng đợi 64 mẫu; loop xả hàng đợi rồi đưa vào engine như cũ. Hàng đợi đầy → bỏ mẫu, đếm overflow,
khoảng trống thật làm pipeline reset; mutex I2C chung với LCD; task đăng ký watchdog 8 s. Core C, công thức, `max_gap_s` không đổi.
Kiểm: `pio run -e esp32dev_diag_acq` + `wokwi/wokwi.diag_acq.toml`; đạt khi dòng `G` có `cnt_gap` không tăng sau khởi động,
`acq_ovf=0`, `F` lên n60=600/n180=1800, ready 1/1 (đứng yên: 20/23 theo thiết kế; nghiêng ~100 s → 23/23 khoảng 222 s).

**`acq03` (Wokwi, `esp32dev_diag_acq`, MPU6050 mô phỏng, 300 s từ boot): WOKWI_SENSOR_PASS.** `serial_raw.log` SHA-256
`c9a687ad70acd6e30f1f290643c1e8e3fae27e5222678f39a7da50492feae36c` (khớp `summary.json`; chạy lại bộ tóm tắt cho kết quả giống hệt).
`[I2C] scan: 0x27 0x68`, selftest |a| = 1,005 g, `[ACQ]` có; 0 lỗi I2C; 9 bộ thanh ghi accel khác nhau, roll 5,7–32,9°.
`cnt_gap` = 0 suốt 293 dòng `G`, 0 `[DIAG] GAP`, 0 reset cửa sổ; khoảng mẫu tối đa 72 ms; hàng đợi tối đa 10/64, overflow 0.
`F`: n60 100→600, n180 100→1800 liên tục; 11/23 từ khi ready ngắn, **23/23 từ t = 185,3 s** (12 lần cập nhật, mọi giá trị hữu hạn, status OK).
Một `[EV] CRITICAL` do roll > φ_hard khi nghiêng (hành vi an toàn đúng thiết kế, không phải lỗi).

**Giới hạn còn lại:** (1) `feature_update` tăng tới **493,9 ms** ở cửa sổ đầy (≈ 0,27 ms/mẫu trên Wokwi); trong lúc đó loop bị chặn:
khoảng giữa hai lần vào loop tới 539 ms, **20 loop overrun** (nhịp `svmg_engine_tick`/LED/LCD trễ tới ~0,5 s mỗi 10 s), LCD đo tới 56 ms
do bị task lấy mẫu chen ngang; (2) hàng đợi dùng tối đa **10/64** (≈ 0,5 s tồn đọng) nên mẫu được xử lý trễ tối đa ~0,5 s nhưng giữ đúng timestamp;
(3) chỉ kiểm trên **Wokwi** (thời gian mô phỏng, không phải ESP32 thật) và thanh trượt chỉ đổi accelY (|a| tới ≈ 1,19 g), nên đây là bằng chứng
cơ chế đường dữ liệu, không phải độ chính xác cảm biến; (4) `SVMG_ACQ_TASK` chưa bật cho `esp32dev` — **cần M1 review** trước khi dùng cho production;
(5) không có RF 4 lớp (engine vẫn dùng Baseline B/RF stub như cũ).

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
