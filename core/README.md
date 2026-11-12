# SVMG Core — Thư viện C dùng chung (M1)

Thư viện lõi C dùng chung cho cả **ESP32 firmware** (chạy trên vi điều khiển) và **máy chủ** (kiểm thử native trên PC).
Đặc điểm: C99, float, không phụ thuộc Arduino, không cấp phát động (`malloc`), an toàn thời gian thực.

## Cấu trúc thư mục

```
core/
├── include/
│   ├── svmg_common.h    # Định nghĩa kiểu dữ liệu cơ sở, hằng số toán học/vật lý
│   ├── svmg_core.h      # Header tổng hợp chính — cấu trúc dữ liệu & API
│   ├── svmg_filter.h    # Bộ lọc bù (complementary filter), Butterworth, giảm mẫu 20→2 Hz
│   ├── svmg_features.h  # Trích xuất đặc trưng cửa sổ 60s / 180s, cờ chất lượng
│   ├── svmg_decision.h  # Lớp ngưỡng cứng (safety envelope), chỉ số MAI, Baseline B
│   ├── svmg_alarm.h     # Máy trạng thái cảnh báo (FSM), leo thang, giải tỏa
│   ├── svmg_cmd.h       # Xử lý kênh lệnh (idempotent, CRC, TTL, mã từ chối)
│   ├── svmg_config.h    # Cấu hình có phiên bản, kiểm tra biên an toàn
│   ├── svmg_calib.h     # Hiệu chuẩn zero lệch tĩnh và ma trận bù
│   ├── svmg_evbuf.h     # Bộ đệm sự kiện ngoại tuyến (ring buffer)
│   ├── svmg_engine.h    # Động cơ tích hợp toàn chuỗi xử lý lõi
│   └── svmg_sim.h       # Header bộ sinh tín hiệu mô phỏng (M2)
├── src/
│   ├── filter.c         # Cài đặt bộ lọc & giảm mẫu
│   ├── features.c       # Cài đặt trích xuất đặc trưng cửa sổ trượt
│   ├── decision.c       # Cài đặt logic ra quyết định, ngưỡng cứng, MAI & Baseline B
│   ├── alarm_fsm.c      # Cài đặt máy trạng thái cảnh báo
│   ├── cmd.c            # Xử lý và thẩm định lệnh
│   ├── config.c         # Quản lý cấu hình thiết bị
│   ├── calib.c          # Xử lý lệnh hiệu chuẩn zero
│   ├── evbuf.c          # Cài đặt bộ đệm sự kiện
│   ├── engine.c         # Tích hợp toàn bộ pipeline
│   └── sim/
│       └── generator.c  # Bộ sinh tín hiệu C — dao động tử roll bậc 2 (M2)
├── library.json         # PlatformIO library manifest
└── README.md
```

## Kiểm thử đơn vị

Toàn bộ lõi C được kiểm thử 100% tự động bằng Unity trên môi trường host (`native`):
```bash
cd tests/firmware
pio test -e native
```
Chi tiết nhật ký kiểm thử và kết quả đo đạc xem tại [`tests/firmware/TEST_LOG.md`](../tests/firmware/TEST_LOG.md).
