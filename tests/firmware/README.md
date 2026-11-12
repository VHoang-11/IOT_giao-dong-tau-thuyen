# tests/firmware/ – kiểm thử của M1

## Chạy
```
cd tests/firmware
pio test -e native                  # toàn bộ (≈ 12 s, cần gcc; lần đầu tải Unity và ArduinoJson)
pio test -e native -f test_engine -v   # một bộ, hiện cả dòng INFO (độ trễ phát hiện, sizeof…)
python tools/ref_filter.py          # đáp án tham chiếu độc lập (double, chỉ dùng math) cho test lọc
python tools/map_sizes.py ../../firmware/.pio/build/esp32dev/firmware.map   # dung lượng flash/RAM theo thành phần
```
Yêu cầu: PlatformIO Core ≥ 6.1, gcc/MinGW trong PATH (đã kiểm tra: gcc 13.2 trên Windows; không cần MSYS2/WSL).

## Bộ test
| Bộ | Ca | Nội dung |
|---|---|---|
| `test_filter` | 29 | quy đổi SI, góc, bộ lọc bù (đáp án tính tay), biquad (hệ số, đáp ứng tần số, chống chồng phổ có đối chứng), giảm mẫu, tín hiệu giống tàu, mẫu thiếu/NaN/bus chết, khoảng trống, đồng hồ quấn vòng |
| `test_features` | 17 | biên khởi động nguội, từng đặc trưng với tín hiệu có đáp án giải tích, UNKNOWN/FAULT, vòng đệm quay vòng |
| `test_decision` | 17 | ngưỡng cứng (5 s, kẹp 15–25°, mẫu thiếu), MAI, Baseline B trên tín hiệu qua cửa sổ (kể cả S0b) |
| `test_alarm` | 23 | chuỗi sự kiện T09 phía thiết bị, ACK/mute/leo thang/giải tỏa, tràn `millis()`, **kiểm thử thuộc tính ngẫu nhiên: không chuỗi thao tác nào tắt được cảnh báo cục bộ** |
| `test_cmd_config` | 22 | CRC (giá trị chuẩn 0x29B1), cấu hình ngoài biên bị từ chối, lệnh idempotent/TTL/mã từ chối, lệnh bất đồng bộ, hiệu chuẩn |
| `test_evbuf` | 8 | thứ tự, ack/gửi bù, đầy bộ đệm, đồng bộ đúng một lần, thuộc tính ngẫu nhiên |
| `test_msg` | 21 | khớp Phụ lục A, thoát ký tự, chặn tràn, phân tích lệnh/cấu hình, fuzz |
| `test_engine` | 27 | tích hợp cả chuỗi: không báo giả 1 giờ, độ trễ phát hiện, ngưỡng cứng, vòng đời, lỗi cảm biến, hiệu chuẩn, RF/shadow |
| `test_t01_t05_t07` | 14 | thí nghiệm T01/T05/T07 phần chạy trên máy (in từng dòng `T0x-y: PASS/FAIL`) |

Nguyên tắc: đáp án kỳ vọng tính tay hoặc bằng `tools/ref_filter.py`/`binascii` (độc lập với mã đang test); kiểm tra "có thể thất bại"
(ví dụ đối chứng bỏ bộ lọc phải bị alias nguyên biên độ); đã thử đột biến mã `alarm_fsm.c` (cho phép mute ở CRITICAL) và test bắt được.

**Giới hạn:** tín hiệu trong test là sóng tổng hợp xác định của M1, **không phải** bộ sinh của M2 (S0…H1); độ trễ đo được chỉ có giá trị
kiểm tra hành vi của lõi, không thay T04. Mã trong `firmware/src` (app, net, io, lcd, store) chưa kiểm thử tự động được vì phụ thuộc phần cứng/mạng.

Nhật ký kiểm thử và thủ tục Wokwi: [`TEST_LOG.md`](TEST_LOG.md).
