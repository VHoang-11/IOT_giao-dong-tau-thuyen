# Bảng đo tài nguyên M1-08 — bản 23 đặc trưng

Đo lại **18/11/2026** bằng PlatformIO, espressif32 8.0.0 / Arduino-ESP32 3.3.12, ESP32 240 MHz,
partition `huge_app` (3.145.728 byte), RAM 327.680 byte. RF và sim vẫn là stub, không phải model M2 thật.
Số Flash là dung lượng chương trình PlatformIO báo; không đồng nhất với kích thước file `.bin` có padding/header.

## Kích thước sau link

| Cấu hình | Flash chương trình | RAM tĩnh | Build |
|---|---:|---:|---|
| `esp32dev` | 1.087.247 B (34,6%) | 85.100 B (26,0%) | PASS |
| `esp32dev_inject` | 1.089.298 B (34,6%) | 85.216 B (26,0%) | PASS |

Các giá trị trên được cập nhật theo lần build cuối nếu source thay đổi. Không dùng số đo firmware 14 đặc trưng cũ.

## Bộ nhớ của lõi

| Thành phần | Byte | Nguồn |
|---|---:|---|
| Engine ESP32 | 25.984 | symbol `_ZN12_GLOBAL__N_11EE` trong ELF, `nm -S` |
| Engine máy chủ | 26.000 | `sizeof`, test_engine; khác ABI/pointer với ESP32 |
| Ring + workspace | 25.208 | `sizeof(svmg_window_t)` |
| Roll/Pitch 1.800 mẫu/kênh | 14.400 | 2 × 1.800 × float32 |
| Workspace quantile dùng lại | 7.200 | 1.800 × float32; nằm trong ring, không trên stack ESP32 |
| Cờ mẫu và số mẫu thô | 3.600 | 2 × 1.800 byte |
| Pipeline | 344 | `sizeof`, gồm hai biquad/kênh |
| Bộ đệm 64 sự kiện | 1.552 | symbol BUF trong ELF |
| Command context | 592 | symbol CMDC trong ELF |
| Trace Roll/Pitch | 7.200 | hai symbol R/P, mỗi symbol 3.600 B |

GCC máy chủ `-O1 -fstack-usage`: frame `svmg_features_compute` 768 B, `stats` 224 B, sort 64 B;
không phải stack high-water mark trên ESP32. API tiện ích máy chủ `svmg_features_from_series` có frame 25.520 B
và **không được gọi trong task ESP32**; ELF thiết bị loại bỏ API không dùng này.

## Thời gian xử lý

- Chưa có model RF thật nên chưa đo inference latency trên thiết bị.
- `infer_stats()` có calls/last/avg/max (µs); health có inference_ms và inference_ms_max.
- Đã thêm `feature_update_us_last/max` vào health: đo toàn lần cập nhật engine gồm feature + baseline/MAI + RF nếu có.
- Serial `[HEALTH]` in heap/min heap/stack_hwm; `loop_overruns` đếm nhịp trễ. **Chưa có số đo runtime ESP32**.
- Model thiếu/sai schema không đăng ký; RF=UNKNOWN. Đồng thuận shadow chưa có phép so là NaN, không báo 100% giả.

Khi M2 bàn giao model: dùng đúng contract/preprocessing version, build lại, chạy ≥10 phút và điền thời gian, heap tối thiểu,
stack_hwm, loop_overruns. Flash còn chỗ chưa chứng minh model/stack/latency sẽ đạt; cần đo artifact thật.
