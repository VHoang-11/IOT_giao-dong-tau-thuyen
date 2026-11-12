# Bảng đo tài nguyên (M1-08)

Nguồn số liệu: `pio run` (ESP32 DevKit, Arduino-ESP32 3.3.x / ESP-IDF 5.x, partition `huge_app`), file map sau link
(`python tests/firmware/tools/map_sizes.py firmware/.pio/build/esp32dev/firmware.map`) và `sizeof` trên lõi C.
Đo ngày 12/11/2026 với **stub** thay cho `model.h` và `sim` của M2.

## 1. Ảnh firmware

| Cấu hình | Flash | RAM tĩnh (.data+.bss) | Ghi chú |
|---|---|---|---|
| Đầy đủ (WiFi + MQTT + JSON) | **1 188 119 B** (37,8 % của 3 MB) | **57 036 B** (17,4 % của 320 KB) | `pio run` |
| `-DSVMG_NET=0` (chỉ cục bộ) | 437 475 B (13,9 %) | 31 040 B (9,5 %) | chứng minh cảnh báo không cần mạng |

Phân bổ flash sau link (cấu hình đầy đủ):

| Thành phần | Flash | RAM tĩnh |
|---|---|---|
| WiFi + TCP/IP + TLS (IDF) | 645 075 B | 21 209 B |
| Framework Arduino/IDF khác | 498 975 B | 20 671 B |
| `msg.cpp` (JSON tạo + ArduinoJson phân tích) | 29 038 B | 0 |
| **Lõi C `core/` (M1)** | **23 818 B** | 9 B |
| `firmware/src` (app, net, io, lcd, mpu, store, infer, trace) | 18 674 B | 7 887 B |
| `esp-mqtt` | 15 456 B | – |
| Stub mô phỏng | 1 597 B | 10 B |

Phần mã của M1 (lõi + firmware + JSON) ≈ **71 KB flash** (≈ 6 % ảnh). Ngân sách còn lại cho `model.h` của M2:
**≈ 1,9 MB flash** (partition 3 MB) — dư rất lớn; RAM trống còn ≈ 270 KB trước khi tính heap WiFi.

## 2. RAM động của lõi C (`sizeof`)

| Cấu trúc | Byte | Ghi chú |
|---|---|---|
| `svmg_engine_t` (cả chuỗi xử lý) | **3 336** | |
| — `svmg_window_t` (roll 360 + gyro 2×120 mẫu 2 Hz) | 2 768 | Ước tính đề cương 7.2.1: 2 880 B cho roll+pitch dài 180 s; lõi giữ 1 chuỗi dài + 2 gyro ngắn |
| — `svmg_pipeline_t` (CF + 4 biquad) | 212 | |
| — `svmg_alarm_t` | 80 | |
| — `svmg_features_t` | 64 | |
| `svmg_evbuf_t` (64 sự kiện) | 1 552 | khớp "vài KiB" ở đề cương 9.2 |
| `svmg_cmd_ctx_t` (nhớ 16 `cmd_id`) | 592 | |
| `trace` (180 s × 2 Hz × 2 kênh int16) | 1 440 | |
| Kèm: đối chứng không giảm mẫu (180 s × 20 Hz) | 28 800 | chỉ để so sánh — nhỏ hơn **~10×** nhờ giảm mẫu |

Stack: `loop()` dùng tối đa vài KB (bộ đệm JSON 640 B + 900 B cho trace + mảng trace 1,4 KB); giá trị `stack_hwm` thật được in ở
dòng `[HEALTH]` trên Serial mỗi 30 s — **chưa đo** (cần chạy thiết bị).

## 3. Thời gian suy luận

| Hạng mục | Kết quả |
|---|---|
| Random Forest (`infer_predict`) | **CHƯA ĐO** – chưa có `model.h` của M2 (M2-06). Mã đo đã có (`infer_stats()`: số lần, lần cuối, trung bình, lớn nhất, µs) và được phát trong `health` (`inference_us_avg/max`) cũng như dòng `[HEALTH]`. |
| Baseline B (shadow) | chưa đo trên ESP32; chạy cùng chu kỳ 5 s với đặc trưng. |
| Chu kỳ xử lý | nhịp 50 ms; `loop_overruns` đếm lần trễ > 150 ms (trong `health`). **Chưa đo trên thiết bị.** |

Cách đo khi có `model.h`: chép vào `ml/export/`, `pio run`, chạy ≥ 10 phút mô phỏng, đọc `inference_us_avg/max` và
`stack_hwm`, điền bảng này.

## 4. Chạy shadow
Khi có RF: cả RF và Baseline B chạy mỗi 5 s mô phỏng; telemetry mang cả hai nhãn (`class_rf`, `class_baseline_b`);
`svmg_engine_agreement()` cho tỉ lệ đồng thuận. Hiện chưa có RF nên `class_rf = UNKNOWN`.
