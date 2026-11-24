# HV01 target protocol v1

Firmware này chỉ kiểm tra phép tính feature C trên ESP32. Nó không đọc IMU, timestamp, RF, Baseline B, MQTT hoặc alarm. C04 không được xác nhận ở đây.

## Frame

Mọi số nguyên và bit pattern float32 dùng little-endian. Frame gồm `sync[2]=53 56`, `version:u8=1`, `type:u8`, `seq:u32`, `length:u16`, `payload[length]`, `crc32:u32`. `length` tối đa 384 byte. CRC là CRC-32/ISO-HDLC (poly reflected `0xEDB88320`, init/xorout `0xffffffff`) trên `version..payload`, không gồm sync và trường CRC. Mỗi chiều có sequence riêng, bắt đầu từ 0 và tăng đúng 1.

Frame dở dang quá 5 giây, sai CRC/version/sequence/độ dài/trạng thái, payload sai hoặc lỗi endpoint làm run thất bại. Firmware gửi `ACK`/`NACK` và `ERROR`; nó không bỏ frame để tiếp tục. Mọi endpoint trước `CASE_DONE` là provisional; host phải bỏ toàn bộ case thiếu `CASE_DONE(status=0)` và run thiếu `RUN_DONE(status=0)`. `HELLO` có thể lặp mỗi 2 giây khi chờ host.

## Host → target

| Type | Payload |
|---|---|
| `01 RUN_BEGIN` | `run_id_len:u8`, ID ASCII 1–32 (`A-Z a-z 0-9 _-.`), `case_count:u16` (1–64), `manifest_sha256[32]` |
| `02 CASE_BEGIN` | `case_id_len:u8`, ID ASCII 1–48, `sample_count:u32` (1–4096), `endpoint_count:u8` (1–32), `endpoint_index:u32[]` tăng nghiêm ngặt và `< sample_count`, `input_csv_sha256[32]`, `samples_crc32:u32` |
| `03 SAMPLES` | `first_sample_index:u32`, `count:u8` (1–32), rồi `count` record: `roll_bits:u32`, `pitch_bits:u32`, `nraw:u8` (0–2), `valid:u8` (0–1). Mỗi record 10 byte; index ngầm định liên tiếp từ `first_sample_index`. |
| `04 CASE_END` | Rỗng; chỉ hoàn tất khi đủ mẫu/endpoints và CRC sample khớp. |
| `05 RUN_END` | Rỗng; chỉ hoàn tất khi đủ số case đã khai báo. |

`samples_crc32` là CRC-32/ISO-HDLC của chuỗi 10-byte sample record theo đúng thứ tự, không gồm batch index/count. CSV SHA-256 nhận diện fixture nguồn; CRC kiểm tra payload nhị phân nhận được. Với golden hiện tại, sender dùng đúng float32 round-trip, `nraw=2`, `valid=1`; NaN/Inf được truyền nguyên bit float32 để production API áp dụng validity của nó. Không có timestamp trong protocol.

## Target → host

| Type | Payload |
|---|---|
| `80 HELLO` | `protocol_version:u8`, `feature_count:u8`, `feature_order_crc32:u32` (CRC32 tên feature nối bằng NUL), rồi các chuỗi `len:u8 + UTF-8 bytes`: C feature schema, semantic contract, validity policy, historical parity schema, harness/target ID, C++ build flags, compiler `__VERSION__`, ESP-IDF/Arduino SDK, chip model; cuối là `chip_revision:u16`, `cpu_mhz:u16`. Các semantic/schema version là metadata cấu hình của test harness, không phải xác nhận rằng feature-only C kiểm timestamp hay C04. |
| `81 ACK` | `acknowledged_host_seq:u32`, `code:u8` (0=ACK, khác 0=NACK/error), `samples_received:u32`. |
| `82 RESULT` | `case_id_len:u8`, ID, `endpoint_index:u32`, `input_csv_sha256[32]`, `elapsed_us:u32`, `valid_mask:u32`, `ready_flags:u8` (bit0 short, bit1 long), `n_valid_60:u16`, `n_valid_180:u16`, `consec_invalid:u16`, `data_quality_pct:f32`, `quality_status:u8`, `quality_reason_bits:u8`, `feature_count:u8=23`, `values:f32[23]`. |
| `83 CASE_DONE` | `case_id_len:u8`, ID, `samples_received:u32`, `endpoints_emitted:u8`, `samples_crc32:u32`, `status:u8` (0=COMPLETE). |
| `84 RUN_DONE` | `run_id_len:u8`, ID, `cases_completed:u16`, `manifest_sha256[32]`, `status:u8` (0=COMPLETE). |
| `8f ERROR` | `code:u8`, `fatal:u8=1`; run không thể được coi là hoàn tất. |

`RESULT` luôn có 23 vị trí theo `feature_order_crc32`/`SVMG_FEATURE_SCHEMA_VERSION`. Khi bit valid tương ứng bằng 0, giá trị truyền là canonical quiet NaN `0x7fc00000`, không phải 0. Khi bit bật, giá trị phải hữu hạn. `quality_status/reason_bits` là mã C cấp vector; firmware không phát M2 per-feature reason code. Thời gian chỉ đo quanh `svmg_features_compute()`; serialize/send không tính vào `elapsed_us`.

`ACK/NACK` có mã: 0 ACK, 1 frame, 2 CRC, 3 version, 4 sequence, 5 length, 6 state, 7 payload, 8 sample index, 9 sample CRC, 10 incomplete case, 11 timeout. Cần reset target để bắt đầu lại sau fatal error.

Host tính và ghi SHA-256 của firmware image sau build; target không tự khai báo hoặc xác minh SHA của binary đang chạy.
