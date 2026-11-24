# Đề xuất cho buổi họp nhóm – contracts và phạm vi (từ M1)

> Cập nhật 18/11/2026: M1 đã triển khai contract 23 theo yêu cầu tích hợp M2.
> Bảng dưới giữ các phụ thuộc M2/M3/M4 chưa hoàn tất; không thay đổi source backend, ML hoặc bộ sinh C M2.

## 0. Kết quả đối chiếu (đã chạy thật)

| Kiểm tra | Kết quả | Lệnh |
|---|---|---|
| Bản tin thật của thiết bị (telemetry, event, health, status, LWT, cmd/ack) vs `contracts/schemas` | **46 hợp lệ, 0 vi phạm**; vòng đời cảnh báo và ACL không vấn đề | `python tests/firmware/tools/validate_messages.py` |
| CRC cấu hình thiết bị vs `backend/.../config_service.compute_crc` | **4004/4004 khớp** (gồm vector vàng `4fa6`/`0902`) | `python tests/firmware/tools/crosscheck_crc.py` |
| 23 đặc trưng C vs extractor Python M2 | **529/529 giá trị khớp**, 23 chuỗi đầu vào | `python tests/firmware/tools/check_features23.py` |
| Hệ trục FRD của M2 → trục cảm biến M1 | roll khớp ≤ 0,05° (gia tốc) / ≤ 0,2° (toàn pipeline), đúng dấu | `pio test -e native -f test_sim_frd` |

## A. Cần chốt (chặn tích hợp)

| # | Nội dung | M1 đang làm | Cần | Hậu quả nếu lệch |
|---|---|---|---|---|
| A1 | **Chuyển từ 14 sang 23 đặc trưng** | M2 đã chọn [23 mục A/C/D/F](../../ml/docs/M2_23_Features_ESP32_Integration.md), 10 Hz, cửa sổ 600/1.800 mẫu, cập nhật 10 s. Lõi đã chuyển sang 23 mục, filter Butterworth4 4 Hz, parity trực tiếp với Python đã PASS; xem [contract](../../contracts/features.md) | **M2** xác nhận contract/preprocessing khi xuất model | Sai đầu vào hoặc công thức → model/firmware không tương thích |
| A2 | **Lệnh `ack_alarm`** | Thiết bị đã xử lý `ack_alarm {alarm_id}` (ack như nút; id cũ → `APPLIED` không tác dụng) và phát `ALARM_STATE` cùng mức với `acked_by`. `command.json` **chưa có** lệnh này và `backend.ack_alarm()` chỉ ghi DB, **không publish xuống thiết bị** → ACK từ dashboard không tắt còi | **M3**: thêm `ack_alarm` vào `command.json` + `CommandName` + publish trong `ack_alarm()` | ACK từ xa vô tác dụng; còi chỉ tắt bằng nút vật lý |
| A3 | **Trần `mute_alarm`** | Thiết bị từ chối `duration_s` > **300** (`BAD_PARAM`), mặc định 60 s (Bảng 3.1 đề cương). `command.json` cho tới 600 | **M3** hạ `maximum` xuống 300 | Lệnh 301–600 s hợp lệ ở backend nhưng bị thiết bị từ chối |
| A4 | **`phi_hard_deg` gửi số nguyên** | CRC dựa trên chuỗi Python; `20` → `4fa6`, `20.0` → `0902` (**khác nhau**). Thiết bị tái dựng đúng theo cách `json.dumps` in số | **M3** gửi `20` (không `20.0`) hoặc thống nhất định dạng số | CRC lệch → cấu hình bị `REJECTED` |
| A5 | **Mẫu `config_sample.json` có `crc: "9c1e"`** | Không khớp bất kỳ định nghĩa nào (đã thử). Thiết bị từ chối CRC sai | **M3/M4** sửa mẫu bằng giá trị tính từ `compute_crc` của backend (xem `crosscheck_crc.py`) | Ví dụ gây hiểu nhầm |
| A6 | **`config` là bản vá** | Backend `update_config` chỉ gửi trường thay đổi (bắt buộc `profile`). Thiết bị: trường vắng giữ giá trị hiện tại; `profile` mà thiếu `debounce_n`/`mai_caution` ⇒ lấy mặc định hồ sơ rồi chồng trường có mặt; `crc` tùy chọn nhưng có thì phải đúng | **M3 xác nhận** là chủ ý | Nếu backend định gửi bản đầy đủ, vẫn tương thích |
| A7 | **Bộ sinh M2** | `firmware/stubs/sim_stub.cpp` (sin) vẫn là nguồn SIMULATION; `core/src/sim/generator.c` của M2 còn là bản khung (`simStep` trả 0) nên chưa nối. M1 đã làm sẵn phần đổi trục `svmg_sample_frd_to_sensor` và vector vàng FRD từ `imu_simulator.py` (test PASS). Việc còn lại khi M2 xong bản C: map `SimConfig` ↔ kịch bản S0…H1 + sea state (bảng quy đổi SS→`sigma_w` hiện **chưa có** trong repo) | **M2** | Chưa có SIMULATION thật trên thiết bị |
| A8 | **`model.h`** | adapter đã kiểm đủ 23 phần tử, schema/preprocessing/model version và NaN; từ chối metadata thiếu/sai. Vẫn chưa có model thật | **M2-06** xuất artifact tương thích | M1-08 không ghép được |
| A9 | **`baseline_params.json`** | khóa theo Baseline B mới: `hi_dyn_rms_deg, grow_slope, grow_min_rms, grow_max_heel_s, off_mean_deg, off_heel_s` + `mai{a_ref,b_ref,g_ref}` → `firmware/tools/gen_baseline_header.py` | **M2-05** hiệu chỉnh theo pipeline 23 và gắn version | Script đã kiểm version; `grow_max_heel_s` là trường cũ không dùng |
| A10 | **Hệ trục** | M1: `roll = atan2(ay, az)` (az=+g nằm ngang). M2: FRD (az=−g). Adapter đổi dấu ay, az, gy, gz (phép quay 180° quanh X); roll dương = mạn phải chìm, giữ nguyên | M2 xác nhận | Roll sai dấu |

## B. Bản tin MQTT – đã khớp schema; các điểm cần biết

| # | Nội dung | M1 đang làm | Ghi chú |
|---|---|---|---|
| B1 | `event` chỉ có `type = ALARM_STATE` | CLEARED = `ALARM_STATE level=NORMAL` cùng `alarm_id`; ACK = `ALARM_STATE` giữ mức, `prev_level = level`, kèm `acked_by` (`device_button` hoặc `issued_by` của lệnh); `alarm_id` cấp ngay khi rời NORMAL | Backend ghi MTTA từ `acked_by`. Các sự kiện hệ thống (MODE_CHANGE, FAULT, BOOT…) **không** đi qua `event`; chúng suy ra từ telemetry/status/ack, và chỉ phát khi bật `SVMG_EXT_EVENTS` |
| B2 | `class` của event chỉ có 4 giá trị | ngưỡng cứng khi lớp là UNKNOWN/FAULT → `HIGH_ROLL`; khác → lớp bất thường gần nhất | schema enum |
| B3 | `telemetry.class_baseline_b` không có `FAULT` | khi FAULT thì **bỏ trường** (tùy chọn); `class_rf` giữ UNKNOWN/FAULT | |
| B4 | `health` đúng tên schema | `free_heap_bytes, min_free_heap_bytes, uptime_ms (64-bit), sensor_ok, i2c_errors, inference_ms, mqtt_reconnects, buffer_used, buffer_capacity` + trường phụ | schema cho phép trường phụ |
| B5 | Topic `trace` / `request_snapshot` | **tắt** (sau `SVMG_EXT_COMMANDS`); broker ACL không cho thiết bị ghi `trace` và backend không đăng ký | nếu nhóm muốn dùng: M4 thêm ACL, M3 thêm schema |
| B6 | `boot_id` dài 8 hex | `esp_random()` | 4 hex dễ trùng giữa hai lần boot (≈1/65 536) |
| B7 | `seq` dùng chung cho mọi loại bản tin trong một boot | telemetry QoS0 có khe hở bình thường; chỉ event QoS1 được bù | backend không coi khe seq là mất sự kiện |
| B8 | `voyage_id` không do thiết bị phát | backend gắn theo thiết bị + thời điểm nhận | `start_voyage`/`stop_voyage` → thiết bị trả `UNSUPPORTED` (backend không gửi xuống) |
| B9 | **Bộ lệnh thiết bị = `command.json`** | `set_profile, set_threshold, calibrate_zero, mute_alarm, restart_device, ack_alarm` (+ `start/stop_voyage` → `UNSUPPORTED`); `set_mode, set_scenario, set_timewarp, set_model, request_snapshot` chỉ khi bật `SVMG_EXT_COMMANDS` (env demo/Wokwi) | |
| B10 | `restart_device` | chỉ khi mức < WARNING và không đang hiệu chuẩn; ngược lại `FORBIDDEN_STATE` (lệnh từ xa không được làm mất cảnh báo cục bộ). Lưu cấu hình → ack → chờ PUBACK ≤ 1,5 s → khởi động lại | AGENTS.md: không lệnh nào tắt cảnh báo cục bộ |
| B11 | `set_threshold` | `phi_hard_deg` 15–25, `mai_caution` 30–90, `debounce_n` 1–10, `report_interval_s` 1–3600, ≥ 1 tham số, áp nguyên tử; ngoài biên → `BAD_PARAM` (T10: φ=40) | đúng `config.json` |
| B12 | Tham số sai kiểu/âm (`age_s`, `ttl_s`…) | `BAD_PARAM` (không bỏ qua âm thầm); `ttl_s` 1–300 | |
| B13 | Phiên bản cấu hình | cùng version + cùng nội dung → im lặng; cũ hơn hoặc cùng version khác nội dung → `REJECTED`; ack `cmd_id="cfg-<ver>"`; rollback = phát version **mới cao hơn** | backend phải tăng version khi rollback |
| B14 | `calibrate_zero` | ack bất đồng bộ sau ~30 s ⇒ TTL ≥ 45 s; `NOT_STATIC` nếu không đứng yên; `FORBIDDEN_STATE` khi mức ≥ WARNING hoặc \|lệch\| > 10° | M3-04 cần timeout riêng |
| B15 | Kết nối | `client_id = device_id`, tài khoản riêng/thiết bị, clean session, keepalive 30 s, LWT `status` QoS1 retained; chỉ ghi `telemetry/event/status/health/cmd/ack`, chỉ đọc `cmd`, `config` (khớp ACL – có test) | TLS tùy chọn: `-DSVMG_MQTT_TLS` + CA trong `secrets.h` |
| B16 | Gửi **không chặn** | `esp_mqtt_client_enqueue` (task MQTT gửi) – vòng lấy mẫu 20 Hz không chờ mạng | |

## C. Ngoài phạm vi WP gốc – **NGOÀI PHẠM VI, cần nhóm quyết** (M1 không tự thêm SP)

| # | Việc | Hiện trạng |
|---|---|---|
| C1 | **Chỉ số/điểm sức khỏe và T13** (FR17, mục 8.5) | Không WP nào có SP. M1 chỉ phát bộ đếm thô (`health`) và cờ chất lượng của M1-03. Cố ý **không** có bộ phát hiện "đứng yên" (Wokwi để tĩnh có phương sai 0). Cơ chế chèn lỗi (`esp32dev_inject`) sẵn sàng cho T13 |
| C2 | **Bộ sinh SIMULATION thật** | thuộc M2-02; M1 chỉ có lớp mỏng `sim_iface.h` + stub + phần đổi trục (A7) |
| C3 | **T08** (kiểm chứng chéo A/B bằng Wokwi Automation) | stretch S1-01, cần Wokwi CLI + token – chưa làm |
| C4 | **Hiệu chuẩn bias gyro lúc khởi động tĩnh** | Phần cứng thật: bias 1 °/s → lệch ≈ τ·b ≈ 7,5° (τ=7,5 s). Wokwi không có bias. Chưa làm – cần nhóm quyết nếu dùng phần cứng thật |
| C5 | **Tách task lấy mẫu/mạng**, TLS bắt buộc | chỉ làm nếu đo thực tế thấy cần (chưa đo được vì không chạy Wokwi trong môi trường này) |

## D. Rủi ro tích hợp M1 muốn nhóm biết

1. **Độ trễ phát hiện** đo trên sóng tổng hợp của M1 (không phải bộ sinh M2): S1 42 s, S2 152 s, S3 142 s (trong bài đo này lớp báo là HIGH_ROLL, chưa phải AMPLITUDE_GROWTH), ngưỡng cứng 17,2 s (bước nghiêng chỉ từ gia tốc) / 9,1 s (có gyro nhất quán). Tham số mặc định chỉ là điểm khởi đầu; M2 chỉnh trên validation.
2. **Bộ lọc bù τ = 7,5 s** ⇒ lệch do bias gyro = τ·bias. Có thể giảm τ nếu M2 thấy cần.
3. **Chưa có RF** ⇒ firmware dùng Baseline B làm mô hình chính, `class_rf = UNKNOWN` (không để RF mù trả NORMAL).
4. **Bộ đệm sự kiện chỉ ở RAM**: khởi động lại làm mất sự kiện chưa được broker xác nhận (giới hạn mục 9.2 đề cương).
5. **Chưa chạy trên Wokwi/broker**: toàn bộ kết quả ở `TEST_LOG.md` là kiểm thử máy chủ + biên dịch ESP32; phần chạy mạch là **NOT RUN**.
