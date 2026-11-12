# Đề xuất cho buổi họp nhóm – contracts và phạm vi (từ M1)

> M1 **không sửa `contracts/`**. Đây là danh sách các giả định M1 đã dùng khi viết code (chưa đọc được `contracts/` vì chưa có
> repo khung) và các chỗ cần nhóm chốt. Mỗi mục ghi: **M1 đang làm gì**, **cần ai xác nhận**, **hậu quả nếu lệch**.
> Mọi giả định được cô lập trong ít file để đổi nhanh (chỉ rõ ở cột "Nơi sửa").

## A. Cần chốt TRƯỚC khi tích hợp (chặn người khác)

| # | Nội dung | M1 đang dùng | Cần xác nhận | Nơi sửa | Hậu quả nếu lệch |
|---|---|---|---|---|---|
| A1 | **Thứ tự và định nghĩa vector đặc trưng** (`features.md`) | 10 phần tử: `rms_roll, p2p, p95_abs, rms_gyro_x, rms_gyro_y, mean_roll, same_sign_ratio, trend, rms_ratio, zero_cross_period` (Phụ lục B + Bảng 7.1) | M2 (huấn luyện) | `core/src/features.c`, `svmg_features_to_vector` | M2-04/M2-06 huấn luyện lệch với firmware → nhãn sai (T03 fail) |
| A2 | **`rms_roll` là độ lệch chuẩn quanh trung bình 60 s, không phải RMS quanh 0** | Chọn quanh trung bình. Lý do: S2 có \|b\| tới 8° với dao động nhỏ sẽ có RMS-quanh-0 ≥ 6° và rơi vào luật nhãn HIGH_ROLL (mục 6.2) dù là PERSISTENT_OFFSET. RMS quanh 0 vẫn có ở `rms_roll_abs_deg`. | M2 (luật nhãn 6.2) | cờ `SVMG_FEAT_RMS_ABOUT_MEAN` | Nhãn S2 bị trộn với S1 |
| A3 | **Các quy ước tính đặc trưng**: P95 theo hạng gần nhất; trễ cắt không 0,15°; `same_sign_ratio` = tỉ lệ dấu chiếm ưu thế (vùng chết 0,01°, nằm 0,5..1); `trend` = hồi quy tuyến tính RMS 6 đoạn 30 s (deg/phút); `rms_ratio` có sàn 0,5° ở cả tử và mẫu; `zero_cross_period` = 0 khi < 2 lần cắt | như trên | M2 (`features_ref.py`, `features_c.py`) | `features.c` | T03 lệch số học |
| A4 | **Pha mẫu 2 Hz và khởi động nguội** | Mẫu 2 Hz = mẫu thứ 10 của mỗi khối 0,5 s (độ trễ nhóm ≈ 0,45 s); cập nhật mỗi 10 mẫu; **UNKNOWN cho tới khi đủ 360 mẫu (180 s)**; mẫu 2 Hz hợp lệ nếu ≥ 5/10 mẫu 20 Hz hợp lệ và không bị cổng gia tốc | M2 (độ trễ cold/warm), M4 (T04) | `engine.c`, `svmg_pipeline_push` | Bảng độ trễ cold start khác nhau |
| A5 | **Quy ước dấu/trục** | `roll = atan2(ay, az)`, tốc độ roll = `gx`; `pitch = atan2(-ax, √(ay²+az²))`, tốc độ pitch = `gy` (hệ phải, NXP AN3461). Nhắc: sự khác dấu giữa bộ sinh M2 và firmware làm chuỗi lọc bù **tự triệt tiêu** | M2 (`svmg_sim.h`) | `svmg_filter.h` | Tín hiệu mô phỏng đưa vào pipeline cho roll sai dấu/biên độ |
| A6 | **Tên enum trong `svmg_core.h`** | `svmg_class_t` {NORMAL=0, HIGH_ROLL, PERSISTENT_OFFSET, AMPLITUDE_GROWTH, UNKNOWN=4, FAULT=5}; mức {NORMAL, CAUTION, WARNING, CRITICAL}; mã lý do {OK, BAD_PARAM, FORBIDDEN_STATE, NOT_STATIC, EXPIRED, UNSUPPORTED} | M2 (thứ tự nhãn của mô hình), M3 | `core/include/svmg_common.h` | Trùng định danh khi gộp `svmg_core.h`; model.h trả chỉ số lớp khác thứ tự |
| A7 | **Giao diện `model.h`** | `int model_predict(const float *f, int n)` trả chỉ số lớp 0..3; macro `SVMG_MODEL_VERSION`; tùy chọn `SVMG_MODEL_HAS_RANGE` + `SVMG_MODEL_FEAT_MIN/MAX[10]` (UNKNOWN ngoài miền, biên 1 %), `SVMG_MODEL_HAS_PROBA` + `model_predict_conf` (UNKNOWN khi tỉ lệ phiếu < τ_conf). `model.h` đặt ở `ml/export/` | M2 (M2-06) | `firmware/src/infer.cpp` | M1-08 không ghép được |
| A8 | **Giao diện bộ sinh `svmg_sim.h`** | M1 chỉ gọi 6 hàm trong `firmware/src/sim_iface.h` (`sim_init, sim_set_scenario, sim_set_sea_state, sim_restart, sim_next(dt), …`). **Đổi kịch bản KHÔNG xóa cửa sổ** (để t0 rơi vào lịch sử → warm start); M1 chạy timewarp bằng cách gọi `sim_next` nhiều lần mỗi nhịp 50 ms (×10 = 200 mẫu/s). `sim_next` trả IMU theo SI, không đặt thời gian | M2 | `firmware/stubs/sim_stub.cpp` → adapter | Warm/cold start sai; demo ×10 chậm |
| A9 | **Định dạng `baseline_params.json`** | `{"baseline_b":{hi_rms_deg, off_mean_deg, off_same_sign, grow_trend, grow_ratio, grow_min_rms}, "mai":{a_ref_deg, b_ref_deg, g_ref_deg_per_min}, generator_version, data_hash}` → `firmware/tools/gen_baseline_header.py` sinh `include/baseline_params.h` | M2 (M2-05) | `firmware/tools/` | Phải đổi script |

## B. Bản tin MQTT (đối chiếu với `contracts/schemas/*.json`)

| # | Nội dung | M1 đang làm | Ghi chú |
|---|---|---|---|
| B1 | `boot_id` dài **8 hex** (32 bit), ví dụ đề cương dùng 4 hex | `esp_random()` | Với 4 hex, xác suất trùng boot_id giữa hai lần khởi động ≈ 1/65 536 → backend loại nhầm toàn bộ sự kiện của lần boot đó. Cần schema `pattern` cho phép 8 ký tự. |
| B2 | `seq` **dùng chung** cho telemetry, event, health, trace trong một lần boot (đúng Phụ lục A: telemetry seq 125, event seq 126) | tăng khi thật sự giao cho MQTT | Telemetry QoS 0 nên seq có khe hở bình thường; chỉ event QoS 1 được bù. Backend không được coi khe hở seq là mất sự kiện. |
| B3 | **`voyage_id` không do thiết bị phát** | telemetry 21 trường = Phụ lục A.1 trừ `voyage_id` | Thiết bị không biết chuyến đi. Backend gắn theo thiết bị + thời điểm nhận (FR13). Nếu muốn thiết bị gửi, cần thêm vào `config`. |
| B4 | Trường mở rộng telemetry (`acked`, `data_status`, `sea_state`) | **tắt** (`SVMG_TELEMETRY_EXTRAS=0`) vì schema có thể cấm trường lạ | Dashboard Alarms cần `acked`; hiện suy ra từ event `ALARM_ACK`. Bật bằng 1 cờ nếu schema cho phép. |
| B5 | Loại sự kiện và trường | `ALARM_STATE` (đổi mức; `level=NORMAL` = CLEARED, có `prev_level` và `alarm_id`), `ALARM_ACK` (`acked_by`: `device_button`/`remote`), `ALARM_MUTE` (`duration_s`), `MODE_CHANGE` (`mode`), `SCENARIO_CHANGE` (`scenario_id`, `sea_state`), `FAULT` (`reason_bits`), `FAULT_CLEARED`, `CONFIG_APPLIED` (`config_version`), `CALIBRATION` (`result`), `BOOT` (`reset_reason`) | Cần M3 xác nhận enum `type` trong schema event. |
| B6 | `alarm_id` dạng `"A-0042"`, **chỉ cấp từ mức WARNING**; sự kiện CAUTION có `alarm_id: null`; bộ đếm về 1 sau mỗi lần boot | — | Khóa duy nhất ở backend phải là `(device_id, boot_id, alarm_id)`. |
| B7 | Vòng đời | RAISED=WARNING, ACKED = cờ `acked` (sự kiện `ALARM_ACK`), CLEARED = `ALARM_STATE` với `level=NORMAL`; CAUTION không phải alarm; CRITICAL có thể do leo thang 60 s hoặc ngưỡng cứng | Cần khớp máy trạng thái alarm service của M3 (M3-03, T09). |
| B8 | **CRC cấu hình** | CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF) trên chuỗi chuẩn tắc `v=<ver>;p=<PROFILE>;n=<n>;phi=<int>;mai=<int>;rep=<int>;m=<MODEL>` (số nguyên, không dấu cách) | Giá trị minh họa `"9c1e"` trong đề cương **không khớp** chuỗi nào nên M1 từ chối nó. Cần M3 dùng đúng định nghĩa này (đã có test với giá trị tính độc lập bằng `binascii.crc_hqx`: `v=8;p=SENSITIVE;n=2;phi=20;mai=70;rep=5;m=RF` → `498b`). |
| B9 | Ngữ nghĩa phiên bản cấu hình | cùng version + cùng nội dung → im lặng (retained gửi lại sau nối lại); version cũ hơn hoặc cùng version khác nội dung → `REJECTED/BAD_PARAM`; **rollback = phát phiên bản MỚI (cao hơn) mang giá trị cũ** | Backend phải tăng version khi rollback. |
| B10 | Ack của cấu hình | `cmd/ack` với `cmd_id = "cfg-<version>"`; `"cfg-invalid"` nếu không phân tích được | Cần M3 chấp nhận định danh này. |
| B11 | `cmd/ack` | thêm `config_version` cả khi `REJECTED`; `calibrate_zero` thành công kèm `zero_roll_deg`, `zero_pitch_deg`; **ack của calibrate_zero đến sau ~30 s** (bất đồng bộ) nên TTL của lệnh này phải ≥ 45 s | M3-04 cần timeout riêng cho calibrate. |
| B12 | **TTL** | thiết bị không có đồng hồ thời gian thực, nên TTL chỉ đo từ lúc nhận trên thiết bị; thêm trường tùy chọn `age_s` (tuổi lệnh khi backend gửi lại). Lệnh EXPIRED **không** được nhớ trong bộ nhớ idempotent để lần gửi lại với TTL mới vẫn xử lý | Backend là nơi cưỡng chế TTL chính. |
| B13 | Ngữ nghĩa lệnh | `ack` luôn `APPLIED` (ack `alarm_id` cũ/không khớp cảnh báo hiện tại thì không có tác dụng — tránh ack nhầm cảnh báo mới); `mute` chỉ khi **WARNING chưa ACK** (CRITICAL, đã ACK, hoặc không có cảnh báo → `FORBIDDEN_STATE`); `calibrate_zero` bị `FORBIDDEN_STATE` khi đang WARNING/CRITICAL và khi \|độ lệch\| > 10°; `set_model RF` → `UNSUPPORTED` nếu chưa có `model.h` thật | Cần M3/M4 hiển thị đúng. |
| B14 | `request_snapshot` | topic `trace` QoS 0, chia đoạn 40 mẫu: `{device_id, boot_id, seq, t_end_s, window_s, fs_hz:2, chunk, chunks, roll_cdeg[], pitch_cdeg[]}` (centi-độ, số nguyên), sau đó một telemetry kèm đặc trưng hiện tại | Đề cương mô tả nội dung nhưng chưa có schema. |
| B15 | `health` | các trường: `uptime_ms, heap_free, heap_min, rssi, reconnects, i2c_errors, samples_invalid, gaps, loop_overruns, inference_us_avg/max, evbuf_depth, evbuf_dropped, cmd_exec, cmd_rejected, rx_dropped, sensor_ok` (bộ đếm thô) | Điểm sức khỏe và các bộ phát hiện (xem mục C1). |
| B16 | Quyền broker (ACL) cho M4 | publish: `svmg/<id>/{telemetry,event,status,health,cmd/ack,trace}`; subscribe: `svmg/<id>/{cmd,config}` (QoS 1); Last Will `status` QoS 1 retained `{"state":"offline"}`; `client_id = device_id`; clean session; keepalive 30 s; broker/tài khoản đặt trong `include/secrets.h` | Mặc định `mqtt://host.wokwi.internal:1883` (Wokwi Private Gateway). |

## C. Ngoài phạm vi WP gốc – **NGOÀI PHẠM VI, cần nhóm quyết** (M1 không tự thêm SP)

| # | Việc | WP của đề cương đã bao gồm? | Hiện trạng trong code M1 |
|---|---|---|---|
| C1 | **Tính chỉ số sức khỏe và điểm sức khỏe** (FR17, mục 8.5, Bảng 8.4: đứng yên, bão hòa, nhiễu nền, jitter, điểm 0–100) và **thí nghiệm T13** (M1 chủ trì) | M1-06 chỉ nêu "health" (gửi bản tin). **Không WP nào** bao gồm phần tính chỉ số/điểm. Kế hoạch gán mục 8.5 và T13 cho M1 nhưng không có SP. | M1 chỉ phát **bộ đếm thô** (B15) và các cờ chất lượng vốn thuộc M1-03 (tỉ lệ thiếu, lỗi liên tiếp, nhiễu nền, mẫu bị cổng/bão hòa → FAULT). **Không** có phát hiện "đứng yên (phương sai ≈ 0)" vì trong Wokwi cảm biến để tĩnh có phương sai đúng 0 (T01) và sẽ bị báo lỗi oan. |
| C2 | **Nhánh SIMULATION của `acquireMotionSample`** | M1-02 ghi "(SENSOR)"; bộ sinh thuộc M2-02; lệnh `set_mode/set_scenario/set_timewarp` thuộc M1-07 (Bảng 8.2) | M1 chỉ có lớp mỏng `sim_iface.h` + stub sin (đúng mock "bộ sinh sin đơn giản" ở mục 4 của kế hoạch). Không viết bộ sinh thật. |
| C3 | **`request_snapshot` + topic `trace`** | Lệnh thuộc M1-07 (Bảng 8.2, mức Should); topic thuộc Bảng 9.1 | Đã làm (≈ 60 dòng) vì là một lệnh trong bộ lệnh của M1-07. |
| C4 | **T08** (kiểm chứng chéo A/B bằng Wokwi Automation) | Stretch S1-01 (3 SP, không tính vào 40 SP) | **Chưa làm**; cần Wokwi CLI + `WOKWI_CLI_TOKEN`. |
| C5 | **Quyết định thư viện MQTT/JSON** | M1-06 (người dùng giao: so sánh RAM/flash và đề xuất) | Xong: `M1-06_mqtt_json_decision.md`. |

## D. Rủi ro tích hợp M1 muốn nhóm biết

1. **Độ trễ phát hiện** đo trên sóng tổng hợp của M1 (không phải bộ sinh M2) với tham số mặc định: S1 ≈ 30 s, S2 ≈ 160 s (**sát giới hạn 180 s**), S3 ≈ 130 s. S2 chậm vì phải chờ trung bình 180 s vượt 2,5° — M2 nên chỉnh `off_mean_deg`/`grow_*` trên validation (M2-05) rồi xuất lại `baseline_params.json`.
2. **Bộ lọc bù τ = 7,5 s** ⇒ lệch do bias gyro = τ·bias (0,1°/s → 0,75°). Ngưỡng cứng phản ứng với bước nghiêng *chỉ từ gia tốc kế* mất ≈ 18 s (τ + dwell 5 s); với chuyển động có gyro nhất quán ≈ 9 s. Có thể giảm τ về 5 s nếu M2 thấy cần.
3. **Mô hình RF chưa có** ⇒ firmware dùng **Baseline B làm mô hình chính** và báo `class_rf = UNKNOWN` (không để "RF mù trả NORMAL"). Khi có `model.h` thật thì tự chuyển sang RF nếu cấu hình `primary_model = RF`.
4. **Bộ đệm sự kiện chỉ nằm trong RAM**: mất điện/khởi động lại là mất những sự kiện chưa được broker xác nhận (đúng giới hạn đã nêu ở mục 9.2 của đề cương).
