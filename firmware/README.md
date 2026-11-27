# firmware/ – ESP32 + Wokwi (M1)

**Chủ sở hữu:** M1. Lõi xử lý dùng chung nằm ở [`../core`](../core/README.md) (C thuần, không Arduino, không malloc);
thư mục này chỉ nối phần cứng, mạng, lưu cấu hình và điều phối.

## Chuyển sang 23 đặc trưng theo M2

Firmware **1.1.0** đã chuyển sang [contract 23 đặc trưng](../contracts/features.md), schema `svmg-angle-23-v1`:
Roll/Pitch 10 Hz, cửa sổ 600/1.800 mẫu, cập nhật mỗi 10 giây. Filter bỏ 2 giây đầu trước khi tích lũy cửa sổ;
vector đầy đủ sớm nhất khoảng 182 giây. Danh sách M2: [đọc trước](../ml/docs/M2_23_Features_ESP32_Integration.md);
[công thức tham chiếu](../ml/docs/feature_specification_30.md).

Đã cập nhật ring/workspace, 23 công thức, parity với Python M2, lọc Butterworth4 4 Hz, chất lượng ngoài vector,
Baseline B/MAI, hiệu chuẩn 300 mẫu/30 s và giải tỏa 3 lần cập nhật/30 s danh nghĩa. `debounce_n` giữ nghĩa số lần phân loại liên tiếp.
RF chỉ chạy khi vector hữu hạn và đủ coverage; model thiếu/sai version bị từ chối. Khi chưa có RF, dùng Baseline B và báo RF=UNKNOWN.

MPU6050 và sơ đồ chân giữ nguyên. Chưa cần vẽ lại mạch cho bộ 23 đặc trưng góc. Chất lượng ước lượng góc trên phần cứng
và hiệu chuẩn vẫn phải xác nhận ở T01; không suy ra độ chính xác chỉ từ build/parity.

**Còn chờ:** model RF/metadata và tham số Baseline M2 đã hiệu chỉnh; bộ sinh C M2; chạy Wokwi/ESP32, broker/NVS và đo latency/stack thực tế.
Quy ước vận hành (epsilon/R²/slope/INVALID) đã bám Python hiện có, ghi ở contract; M2 cần xác nhận khi xuất model.

## Trạng thái gói công việc

Cột "Trên máy chủ" = đã kiểm thử tự động (`run_native.py`, có thể dùng `pio test -e native`; xem `tests/firmware/TEST_LOG.md`). Cột "Trên Wokwi/ESP32" =
đã biên dịch cho ESP32 nhưng **chưa được chạy trong mô phỏng** (chưa có kết quả chạy Wokwi trong đợt cập nhật này).

| WP | Nội dung | Mã nguồn | Trên máy chủ | Trên Wokwi/ESP32 |
|---|---|---|---|---|
| M1-01 | Mạch Wokwi | `wokwi/diagram.json` | – | cần mở lại để xác nhận |
| M1-02 | Đọc MPU6050 (DLPF 10 Hz, phục hồi bus I2C), lọc (bù + Butterworth), giảm mẫu 20→10 Hz, đổi trục FRD của M2 | `core/src/filter.c`, `src/mpu6050.cpp`, `src/motion_source.cpp` | ✅ 30 ca + 4 ca FRD; đối chiếu SciPy | build OK; chưa chạy |
| M1-03 | **23 đặc trưng đúng contract**, cờ chất lượng, UNKNOWN/FAULT | `core/src/features.c` | ✅ 13 ca + 529 giá trị parity Python | build OK; chưa chạy |
| M1-04 | Ngưỡng cứng, MAI, Baseline B (trên 23 đặc trưng) | `core/src/safety.c`, `mai.c`, `baseline.c` | ✅ 22 ca | build OK; chưa chạy |
| M1-05 | Máy trạng thái cảnh báo + LED/buzzer/LCD/nút | `core/src/alarm_fsm.c`, `src/io.cpp`, `src/lcd.cpp` | ✅ 29 ca (gồm kiểm thử thuộc tính ngẫu nhiên) | build OK; chưa chạy |
| M1-06 | WiFi/MQTT (gửi không chặn), bản tin khớp schema, bộ đệm offline | `src/net.cpp`, `lib/svmg_msg`, `core/src/evbuf.c` | ✅ bản tin 31 ca + bộ đệm 8 ca + **46 bản tin hợp lệ schema** | build OK; chưa chạy với broker |
| M1-07 | Lệnh/cấu hình theo `command.json`/`config.json`: idempotent, TTL, CRC khớp backend, NVS, mã từ chối | `core/src/cmd.c`, `config.c`, `calib.c`, `src/store.cpp` | ✅ 26 ca + CRC 4004/4004 | NVS chưa chạy |
| M1-08 | Ghép RF + shadow Baseline B + bảng tài nguyên | `src/infer.cpp`, `docs/M1-08_resource_table.md` | ✅ 6 ca kiểm metadata của adapter; chưa có RF thật | **chờ `model.h` của M2** để đo thời gian suy luận |
| M1-09 | Kiểm thử T01/T05/T07, README, nhật ký | `tests/firmware/` | ✅ 14 ca thí nghiệm | **thủ tục Wokwi chưa chạy** |

Tổng: **208 ca máy chủ PASS**; `pio run -e esp32dev` và `-e esp32dev_inject` biên dịch sạch (0 cảnh báo).

Chưa làm: **T08** (stretch S1-01, cần Wokwi CLI + token). Các mục cần nhóm quyết: [`docs/CONTRACT_PROPOSALS.md`](docs/CONTRACT_PROPOSALS.md).

## Cấu trúc
```
firmware/
  platformio.ini         env esp32dev (build_src_filter nạp stubs/); env probe_noparse chỉ để đo flash
  wokwi/                 diagram.json, wokwi.toml
  src/                   app.cpp (điều phối), net, mpu6050, motion_source, io, lcd, store, infer, trace
  lib/svmg_msg/          tạo/phân tích JSON (không phụ thuộc Arduino → test trên máy)
  stubs/                 sim_stub.cpp, model_stub.h  (MOCK – M2 thay thế; đổi trục FRD đã có sẵn ở core/include/svmg_common.h)
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
| *(không còn)* | GPIO 35, 4 | Mực nước/DHT22 hầm hàng đã chuyển sang **Cargo Node** riêng (ESP32 thứ 2, xem `target_cargo/`) |

Không dùng chân strapping (0, 2, 5, 12, 15) và GPIO 6–11.

## Bố cục mạch Wokwi

[Sơ đồ chỉnh sửa](wokwi/diagram.json) · [Ảnh bố cục](docs/wiring-layout.png).
ESP32 ở giữa; chiết áp/còi và ba nhánh LED ở bên trái; LCD/MPU6050 ở bên phải; ba nút ở hàng dưới.
Dây đi vuông góc theo tuyến riêng, có nhãn linh kiện. Đỏ là nguồn, đen là GND, xanh lá/xanh dương là SDA/SCL;
các tín hiệu LED/nút dùng màu riêng. Các chân GND của ESP32 cùng một net; các nút dùng tiếp điểm tương đương bên phải
cho tín hiệu và bên trái cho GND để dây gọn hơn. Chỉ các điểm nối tại chân mới tạo kết nối điện.

Đã kiểm tra bằng Wokwi CLI lint và so sánh toàn bộ netlist trước/sau: giữ nguyên GPIO, hai mức nguồn, I2C và điện trở 220 Ω;
không có đoạn dây khác tín hiệu nằm đè lên nhau. Ảnh là bản xem bố cục, không phải kết quả chạy mô phỏng cảm biến.

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
| Chưa đủ dữ liệu (khởi động nguội khoảng 182 s) / mô hình không chắc | **vàng nháy chậm** (không bao giờ xanh) | – |
| Lỗi cảm biến (FAULT) | vàng + đỏ nháy nhanh | – |
| CAUTION | vàng | – |
| WARNING | đỏ | ngắt quãng (tắt được bằng ACK hoặc mute ≤ 300 s) |
| CRITICAL | đỏ | liên tục (chỉ ACK tắt được; không mute) |

Serial 115200: `T,<t>,<mode>,<roll>,<pitch>,<rms>,<mean>,<trend>,<rf>,<baseline>,<chính>,<mai>,<mức>,<acked>,<ms>` mỗi 10 s mô phỏng;
`R,<t>,<roll>,<pitch>,i2c_err=…` mỗi 0,1 s ở SENSOR; `[EV]`, `[ACK]`, `[HEALTH]`.

## Giao diện với người khác
* **MQTT** (`svmg/<device_id>/…`): `telemetry` (QoS0, theo `report_interval_s`), `event` (QoS1, chỉ `ALARM_STATE`; bộ đệm 64, `boot_id`+`seq`),
  `status` (QoS1 retained + Last Will), `health` (QoS0, 30 s), `cmd` ↓ / `cmd/ack` ↑ (QoS1), `config` ↓ (QoS1 retained, xử lý như bản vá).
  Mọi bản tin được kiểm bằng `contracts/schemas` (`tests/firmware/tools/validate_messages.py`: 0 vi phạm) và topic khớp ACL Mosquitto.
  Gửi bằng `esp_mqtt_client_enqueue` (không chặn vòng 20 Hz). Topic `trace`/`request_snapshot` và các lệnh mở rộng chỉ bật bằng `SVMG_EXT_*`
  (env `esp32dev_inject`). Đề xuất cho người khác: `docs/CONTRACT_PROPOSALS.md`.
* **Bất biến an toàn:** không có lệnh nào tắt cảnh báo cục bộ; `phi_hard` luôn trong 15–25° (cấu hình ngoài biên bị từ chối);
  mute tối đa 300 s, không áp cho CRITICAL; `restart_device` bị từ chối khi mức ≥ WARNING; mất mạng không ảnh hưởng LED/còi; lỗi/mất dữ liệu hiển thị UNKNOWN/FAULT, không bao giờ NORMAL.
* **M2 → M1:** `ml/export/model.h` (tự nhận qua `-I ../ml/export`), `baseline_params.json` (`tools/gen_baseline_header.py`),
  `core/src/sim` + `svmg_sim.h` (thay `stubs/sim_stub.cpp`; bản C của M2 còn là khung nên chưa nối). Khi chưa có RF, firmware dùng **Baseline B làm mô hình chính** và
  báo `class_rf = UNKNOWN`.

## Giới hạn đã biết
* Chưa có kết quả chạy Wokwi/ESP32 trong lần cập nhật này: cần chạy thủ tục T01/T05/T07 ở `tests/firmware/TEST_LOG.md` và điền kết quả.
* Bộ đệm sự kiện chỉ ở RAM (mất khi khởi động lại; đúng giới hạn mục 9.2). NVS trong Wokwi chỉ bền trong một phiên chạy.
* Thang đo MPU6050 ±2 g / ±250 °/s: lúc khởi động firmware tự kiểm tra |a| ≈ 1 g và in cảnh báo `THANG DO LECH` nếu Wokwi
  không mô phỏng đúng các thanh ghi cấu hình; khi đó chuyển sang `Adafruit_MPU6050::getEvent()` (đã trả SI).
* Tham số Baseline B/MAI là mặc định của M1 cho tới khi M2 xuất `baseline_params.json`.
* Chưa kiểm: `loop_overruns` khi broker treo, Last Will, NVS, RF — cần chạy thiết bị/Wokwi (xem `tests/firmware/TEST_LOG.md`, mục **NOT RUN**).
