# firmware/ – ESP32 + Wokwi (M1)

**Chủ sở hữu:** M1. Lõi xử lý dùng chung nằm ở [`../core`](../core/README.md) (C thuần, không Arduino, không malloc);
thư mục này chỉ nối phần cứng, mạng, lưu cấu hình và điều phối.

## Trạng thái gói công việc

Cột "Trên máy chủ" = đã kiểm thử tự động (`pio test -e native`, xem `tests/firmware/TEST_LOG.md`). Cột "Trên Wokwi/ESP32" =
đã biên dịch cho ESP32 nhưng **chưa được chạy trong mô phỏng** (môi trường phát triển không chạy được Wokwi).

| WP | Nội dung | Mã nguồn | Trên máy chủ | Trên Wokwi/ESP32 |
|---|---|---|---|---|
| M1-01 | Mạch Wokwi | `wokwi/diagram.json` | – | cần mở lại để xác nhận |
| M1-02 | Lọc (bù + Butterworth) + giảm mẫu 20→2 Hz, đọc MPU6050 | `core/src/filter.c`, `src/mpu6050.cpp`, `src/motion_source.cpp` | ✅ 29 ca | chưa chạy |
| M1-03 | Đặc trưng 60/180 s, cờ chất lượng, UNKNOWN/FAULT | `core/src/features.c` | ✅ 17 ca | chưa chạy |
| M1-04 | Ngưỡng cứng, MAI, Baseline B | `core/src/decision.c` | ✅ 17 ca | chưa chạy |
| M1-05 | Máy trạng thái cảnh báo + LED/buzzer/LCD/nút | `core/src/alarm_fsm.c`, `src/io.cpp`, `src/lcd.cpp` | ✅ 23 ca (kể cả kiểm thử thuộc tính ngẫu nhiên) | chưa chạy |
| M1-06 | WiFi/MQTT, bản tin, bộ đệm offline | `src/net.cpp`, `lib/svmg_msg`, `core/src/evbuf.c` | ✅ bản tin 21 ca + bộ đệm 8 ca | chưa chạy với broker |
| M1-07 | Lệnh/cấu hình: idempotent, TTL, CRC, NVS, mã từ chối | `core/src/cmd.c`, `config.c`, `calib.c`, `src/store.cpp` | ✅ 22 ca | NVS chưa chạy |
| M1-08 | Ghép RF + shadow Baseline B + bảng tài nguyên | `src/infer.cpp`, `docs/M1-08_resource_table.md` | ✅ (RF giả) | **chờ `model.h` của M2** để đo thời gian suy luận |
| M1-09 | Kiểm thử T01/T05/T07, README, nhật ký | `tests/firmware/` | ✅ 14 ca thí nghiệm (T01 ×6, T05 ×1, T07 ×7) | **thủ tục Wokwi chưa chạy** |

Chưa làm: **T08** (stretch S1-01, cần Wokwi CLI + token). Các mục cần nhóm quyết: [`docs/CONTRACT_PROPOSALS.md`](docs/CONTRACT_PROPOSALS.md).

## Cấu trúc
```
firmware/
  platformio.ini         env esp32dev (build_src_filter nạp stubs/); env probe_noparse chỉ để đo flash
  wokwi/                 diagram.json, wokwi.toml
  src/                   app.cpp (điều phối), net, mpu6050, motion_source, io, lcd, store, infer, trace
  lib/svmg_msg/          tạo/phân tích JSON (không phụ thuộc Arduino → test trên máy)
  stubs/                 sim_stub.cpp, model_stub.h  (MOCK – M2 thay thế)
  include/               svmg_build.h, secrets.example.h  (secrets.h KHÔNG commit)
  tools/                 gen_baseline_header.py (baseline_params.json của M2 → header)
  docs/                  CONTRACT_PROPOSALS, M1-06_mqtt_json_decision, M1-08_resource_table
```

## Bảng chân (M1-01) – khớp `wokwi/diagram.json`
| Thiết bị / tín hiệu | ESP32 | Ghi chú |
|---|---|---|
| MPU6050 SDA / SCL | GPIO 21 / 22 | I2C chung với LCD; MPU6050 0x68, nguồn 3V3 |
| LCD 16×2 I2C | GPIO 21 / 22 | nguồn 5V; 0x27 |
| Nút MODE / SCENARIO / ACK | GPIO 14 / 27 / 13 | INPUT_PULLUP, nhấn = LOW, chống rung 30 ms |
| LED xanh / vàng / đỏ | GPIO 33 / 26 / 25 | qua điện trở 220 Ω |
| Buzzer | GPIO 32 | `tone()` 1 kHz |
| Chiết áp (SIG) | GPIO 34 | ADC1; sea state 0–5 chia đều 6 mức, có trễ |

Không dùng chân strapping (0, 2, 5, 12, 15) và GPIO 6–11.

## Chạy
```
cd firmware
pio run                          # build (lần đầu tải thư viện, ~2 phút)
cp include/secrets.example.h include/secrets.h   # tùy chọn: broker/tài khoản thật
```
Mô phỏng: VS Code + extension *Wokwi Simulator* → `Wokwi: Select Config File` → `firmware/wokwi/wokwi.toml` →
`Wokwi: Start Simulator` (giữ tab hiển thị). Chạy cục bộ không cần broker: `PLATFORMIO_BUILD_FLAGS=-DSVMG_NET=0 pio run`.

## Vận hành trên thiết bị
| Thao tác | Hiệu ứng |
|---|---|
| MODE (nhấn ngắn) | đổi SENSOR ↔ SIMULATION (xóa cửa sổ; **không** xóa trạng thái cảnh báo) |
| SCENARIO | kịch bản kế tiếp S0→S0b→S1→S2→S3→H1 (chỉ SIMULATION; giữ cửa sổ để t0 rơi vào lịch sử) |
| ACK (nhấn ngắn, nhả) | xác nhận: tắt còi, **giữ đèn**; không xóa cảnh báo |
| ACK (giữ 3 s) | trang chẩn đoán trên LCD 10 s (I2C, heap, phiên bản mô hình/cấu hình, mạng) |
| Chiết áp | sea state 0–5 trong SIMULATION |

LCD: dòng 1 `SIM R:+08.2° S3` / `SEN R:+08.2°`; dòng 2 `<lớp> <mức>[*]` (`*` = đã ACK), ví dụ `HIGH ROLL  WARN*`.

| Trạng thái | Đèn | Còi |
|---|---|---|
| NORMAL, dữ liệu OK | xanh | – |
| Chưa đủ dữ liệu (khởi động nguội 180 s) / mô hình không chắc | **vàng nháy chậm** (không bao giờ xanh) | – |
| Lỗi cảm biến (FAULT) | vàng + đỏ nháy nhanh | – |
| CAUTION | vàng | – |
| WARNING | đỏ | ngắt quãng (tắt được bằng ACK hoặc mute ≤ 300 s) |
| CRITICAL | đỏ | liên tục (chỉ ACK tắt được; không mute) |

Serial 115200: `T,<t>,<mode>,<roll>,<pitch>,<rms>,<mean>,<trend>,<rf>,<baseline>,<chính>,<mai>,<mức>,<acked>,<ms>` mỗi 5 s mô phỏng;
`R,<t>,<roll>,<pitch>,i2c_err=…` mỗi 0,5 s ở SENSOR; `[EV]`, `[ACK]`, `[HEALTH]`.

## Giao diện với người khác
* **MQTT** (`svmg/<device_id>/…`): `telemetry` (QoS0), `event` (QoS1, bộ đệm 64, `boot_id`+`seq`), `status` (QoS1 retained + Last Will),
  `health` (QoS0, 30 s), `cmd` ↓ / `cmd/ack` ↑ (QoS1), `config` ↓ (QoS1 retained), `trace` (QoS0). Định dạng bám Phụ lục A; các chỗ
  lệch/giả định: `docs/CONTRACT_PROPOSALS.md` (mục B).
* **Bất biến an toàn:** không có lệnh nào tắt cảnh báo cục bộ; `phi_hard` luôn trong 15–25° (cấu hình ngoài biên bị từ chối);
  mute tối đa 300 s, không áp cho CRITICAL; mất mạng không ảnh hưởng LED/còi; lỗi/mất dữ liệu hiển thị UNKNOWN/FAULT, không bao giờ NORMAL.
* **M2 → M1:** `ml/export/model.h` (tự nhận qua `-I ../ml/export`), `baseline_params.json` (`tools/gen_baseline_header.py`),
  `core/src/sim` + `svmg_sim.h` (thay `stubs/sim_stub.cpp`). Khi chưa có RF, firmware dùng **Baseline B làm mô hình chính** và
  báo `class_rf = UNKNOWN`.

## Giới hạn đã biết
* Chưa chạy được trên Wokwi trong phiên làm việc này: cần chạy thủ tục T01/T05/T07 ở `tests/firmware/TEST_LOG.md` và điền kết quả.
* Bộ đệm sự kiện chỉ ở RAM (mất khi khởi động lại; đúng giới hạn mục 9.2). NVS trong Wokwi chỉ bền trong một phiên chạy.
* Thang đo MPU6050 ±2 g / ±250 °/s: lúc khởi động firmware tự kiểm tra |a| ≈ 1 g và in cảnh báo `THANG DO LECH` nếu Wokwi
  không mô phỏng đúng các thanh ghi cấu hình; khi đó chuyển sang `Adafruit_MPU6050::getEvent()` (đã trả SI).
* Tham số Baseline B/MAI là mặc định của M1 cho tới khi M2 xuất `baseline_params.json`.
