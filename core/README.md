# SVMG Core — Thư viện C dùng chung

Thư viện lõi C dùng chung cho cả **ESP32 firmware** (chạy trên vi điều khiển) và **máy chủ** (kiểm thử hàng loạt trên PC).

## Cấu trúc thư mục

```
core/
├── include/
│   ├── svmg_core.h      # Header chính — cấu trúc dữ liệu & API
│   └── svmg_sim.h       # Header bộ sinh tín hiệu mô phỏng
├── src/
│   ├── filter.c          # Bộ lọc bù (complementary filter), giảm mẫu 20→2 Hz
│   ├── features.c        # Trích xuất đặc trưng cửa sổ 60s/180s
│   ├── baseline.c        # Baseline B — phân loại dựa trên quy tắc
│   ├── safety.c          # Lớp ngưỡng cứng (safety envelope)
│   ├── mai.c             # Motion Anomaly Index (MAI, 0–100)
│   ├── alarm_fsm.c       # Máy trạng thái cảnh báo (FSM)
│   └── sim/
│       └── generator.c   # Bộ sinh tín hiệu C — dao động tử roll bậc 2
└── README.md
```

## Mục đích từng file

| File           | Mô tả |
|----------------|--------|
| `svmg_core.h`  | Định nghĩa `MotionSample`, `FeatureVector`, `MotionClass`, `AlarmLevel` và các API chính |
| `svmg_sim.h`   | Cấu hình và API cho bộ sinh tín hiệu mô phỏng (`SimConfig`, `simInit`, `simStep`) |
| `filter.c`     | Complementary filter kết hợp gia tốc kế + con quay hồi chuyển, giảm mẫu từ 20 Hz xuống 2 Hz |
| `features.c`   | Trích xuất 14 đặc trưng từ cửa sổ trượt (RMS, P95, zero-crossing, trend, v.v.) |
| `baseline.c`   | Phân loại Baseline B dựa trên quy tắc ngưỡng — dùng để so sánh với mô hình RF |
| `safety.c`     | Kiểm tra ngưỡng cứng: \|roll\| ≥ 20° liên tục ≥ 5s → CRITICAL |
| `mai.c`        | Tính chỉ số bất thường chuyển động MAI (0–100) |
| `alarm_fsm.c`  | Máy trạng thái: NORMAL → CAUTION → WARNING → CRITICAL → ACKED → NORMAL |
| `generator.c`  | Bộ sinh tín hiệu mô phỏng (C port từ Python), dùng dao động tử roll bậc 2 |

## Build cho máy chủ (Host)

```bash
# Dùng gcc + make
cd core
gcc -I include -c src/filter.c src/features.c src/baseline.c \
    src/safety.c src/mai.c src/alarm_fsm.c src/sim/generator.c
ar rcs libsvmg_core.a *.o
```

## Build cho ESP32 (PlatformIO)

Thư viện được tích hợp như một component trong PlatformIO project:

```ini
; platformio.ini
[env:esp32]
platform = espressif32
board = esp32dev
framework = arduino
build_flags = -I core/include
build_src_filter = +<*> +<../core/src/*>
```

## Chạy kiểm thử đơn vị (Unit Tests)

```bash
cd tests
gcc -I ../core/include -o test_core test_core.c ../core/src/*.c -lm
./test_core
```

Xem thêm chi tiết tại `tests/README.md`.
