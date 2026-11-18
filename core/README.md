# SVMG Core — lõi C M1

C99 dùng chung cho ESP32 và kiểm thử máy chủ. Lưu tín hiệu float32; tích lũy thống kê bằng double để giảm sai số.
Không Arduino, không malloc; sắp xếp heapsort tại chỗ trên workspace cố định. `core/src/sim/` vẫn thuộc M2 và chưa được nối vào firmware.

## Pipeline hiện hành

`IMU 20 Hz → quy đổi SI → lọc bù τ=7,5 s → Butterworth4 4 Hz → 10 Hz → cửa sổ 600/1.800 mẫu → 23 features mỗi 10 s → RF/Baseline B/MAI → FSM`

Ngưỡng cứng chạy theo mẫu 10 Hz, không đợi RF hoặc đủ cửa sổ. Bỏ 2 s đầu của filter khỏi lịch sử feature;
vector đầy đủ sớm nhất khoảng 182 s. Hiệu chuẩn vẫn 30 s (300 mẫu); giải tỏa theo 3 cập nhật feature, tương ứng 30 s danh nghĩa.
`debounce_n` vẫn là số lần phân loại liên tiếp, nay mỗi lần cách 10 s. ACK/mute/leo thang dùng đồng hồ thực như trước.

## Giao diện và contract

- [Contract chính thức của bản triển khai](../contracts/features.md), [manifest](../contracts/features23.json).
- `svmg_feature_schema.h`: version, nhịp và thứ tự duy nhất của 23 phần tử; `FeatureVector` gồm đúng 23 float.
- `svmg_features.h`: ring, workspace, giá trị 23 feature và metadata riêng (`valid_mask`, chất lượng, sensor_ok).
- `svmg_features_from_series`: đầu vào fixed-grid 10 Hz, cũ → mới; API máy chủ/ctypes, không dùng trên task ESP32 do có ring cục bộ lớn.
- `svmg_features_compute`: dùng workspace đi cùng ring nên không cần đặt mảng 1.800 float trên stack ESP32.
- `svmg_contract.h`: bridge C giữa `FeatureVector` và kiểu nội bộ. Các enum được kiểm bằng static assertion.

Không thay NaN thành 0 cho RF. R² của RMS không đổi, ratio có mẫu số gần 0 và sign ratio toàn zero có thể không xác định dù cảm biến tốt.
Khi chọn RF, vector thiếu → UNKNOWN, không gọi model. Khi chọn Baseline B, có thể dùng phần feature mà baseline cần nếu dữ liệu đủ chất lượng.
Chưa có model thật thì dùng Baseline B và RF=UNKNOWN; model sai schema/preprocessing không được đăng ký.

## Các module

| Module | Trách nhiệm |
|---|---|
| `filter.c` | SI, ước lượng Roll/Pitch, lọc bù và Butterworth4, giảm mẫu, phát hiện gap |
| `features.c` | 23 đặc trưng, mask, coverage, ring và API parity |
| `baseline.c`, `mai.c` | Baseline B/MAI trên feature mới; tham số demo chờ M2 hiệu chỉnh |
| `safety.c`, `alarm_fsm.c` | Ngưỡng cứng, cảnh báo, ACK/mute, leo thang, giải tỏa |
| `cmd.c`, `config.c`, `calib.c` | TTL/idempotency, bản vá cấu hình/CRC, hiệu chuẩn |
| `evbuf.c` | Bộ đệm RAM 64 sự kiện; firmware cung cấp boot_id và seq |
| `engine.c` | Điều phối, giữ cảnh báo cục bộ độc lập mạng |

MPU6050 Z lên: Roll `atan2(ay,az)`; Pitch `atan2(-ax,sqrt(ay²+az²))`. Mẫu mô phỏng FRD phải qua `svmg_sample_frd_to_sensor`.
Mất mẫu → UNKNOWN ngay; mất liên tục 10 s → FAULT. Mọi dữ liệu có SENSOR/SIMULATION; ngưỡng chỉ phục vụ demo.

## Kiểm chứng

Từ gốc repo:

```bash
python tests/firmware/tools/run_native.py
python tests/firmware/tools/check_features23.py
python tests/firmware/tools/check_filter23.py
python tests/firmware/tools/check_model_adapter.py
```

Chi tiết kết quả và giới hạn: [nhật ký](../tests/firmware/TEST_LOG.md). Kiểm thử máy chủ không thay cho chạy Wokwi/ESP32.
