# Quyết định thư viện MQTT và JSON (M1-06)

Yêu cầu của nhóm: so sánh theo RAM/flash, đối chiếu với `contracts/schemas/*.json`, rồi đề xuất. `contracts/` chưa có trong
repo nên phần đối chiếu schema dựa trên **Phụ lục A đề cương** (đã có test khớp từng trường: `tests/firmware/test/test_msg`);
sẽ đối chiếu lại khi có schema thật.

## 1. MQTT: `esp-mqtt` có sẵn trong framework (không thêm thư viện)

| Tiêu chí | `esp-mqtt` (ESP-IDF, đã nằm trong arduino-esp32 3.x) | PubSubClient |
|---|---|---|
| **QoS 1 khi xuất bản + PUBACK** (bắt buộc cho `event`, `cmd/ack`, `status`) | Có: `esp_mqtt_client_publish(qos=1)` trả `msg_id`, sự kiện `MQTT_EVENT_PUBLISHED` báo PUBACK | **Không**: chỉ publish QoS 0 |
| Last Will QoS 1 retained | Có (`session.last_will`) | Có QoS 0/1 |
| Retained / subscribe QoS 1 | Có | Subscribe QoS 0/1 |
| Tự nối lại | Có (chạy trong task riêng, không chặn `loop()`) | Phải tự viết |
| TLS / xác thực | Có sẵn (bundle chứng chỉ, mTLS) | Cần thêm `WiFiClientSecure` |
| Thêm flash | **15,5 KB** (đo sau link) | không đo (không đáp ứng QoS 1 nên không cần đo) |

PubSubClient bị loại vì **không xác nhận được QoS 1**, trong khi yêu cầu FR19/T06 là "không mất, không trùng" sau mất mạng.
Cách dùng: `msg_id` → `seq` trong bảng "đang bay" tối đa 4 phần tử; PUBACK mới giải phóng sự kiện khỏi `svmg_evbuf`; quá
8 s không PUBACK hoặc mất kết nối thì sự kiện quay lại hàng chờ (có thể gửi trùng — backend loại theo `(device_id, boot_id, seq)`).

## 2. JSON: tạo bằng `snprintf`, phân tích bằng ArduinoJson v6 `StaticJsonDocument`

Số đo flash (sau link, `tests/firmware/tools/map_sizes.py` trên `firmware.map`, `pio run`):

| Thành phần | Flash | RAM tĩnh |
|---|---|---|
| Toàn bộ `msg.cpp` (tạo JSON + phân tích) | 29,0 KB | 0 |
| — trong đó chỉ phần **tạo** bằng snprintf (đo file `.o` với `-DSVMG_MSG_NO_PARSE`) | ≈ 7,6 KB | 0 |
| — phần **phân tích** ArduinoJson (hiệu số) | ≈ 21 KB (≈ 1,8 % ảnh 1,19 MB; 0,7 % phân vùng 3 MB) | 0 (tài liệu nằm trên stack: 512 B cho lệnh, 384 B cho cấu hình) |
| WiFi + TCP/IP + TLS (để so sánh quy mô) | 645 KB | 21 KB |

Bản dùng `SVMG_NET=0` (không mạng) chiếm 437 KB flash / 31 KB RAM; bản đầy đủ 1 188 KB / 57 KB ⇒ lớp mạng ≈ 750 KB flash, 26 KB RAM.

**Vì sao không tự viết bộ phân tích JSON để tiết kiệm ~21 KB:** đầu vào lệnh/cấu hình đến từ mạng (không tin cậy) và có
hậu quả an toàn (đổi cấu hình). ArduinoJson từ chối JSON hỏng/lồng sâu, không tràn bộ đệm (đã chạy fuzz 4 000 biến thể
của một lệnh hợp lệ trong `test_parse_cmd_fuzz_does_not_crash`), và phân biệt được kiểu số/chuỗi để biến "tham số sai kiểu" thành
`BAD_PARAM` thay vì bỏ qua âm thầm. Tiết kiệm 0,7 % phân vùng không đáng đánh đổi rủi ro đó.

**Vì sao tạo bằng `snprintf`:** cấu trúc bản tin cố định, không cần heap, kích thước biết trước (telemetry xấu nhất
477 byte → bộ đệm 640 B), mọi chuỗi đều thoát ký tự (`cmd_id` do mạng gửi có thể chứa dấu nháy; có test chèn trường),
và chặn tràn (có test ghi canh vùng nhớ).

## 3. Điểm chưa xác nhận
* Chưa chạy end-to-end với broker thật (cần Wokwi hoặc Mosquitto của M4). Đường gửi/nhận/ack đã biên dịch trên ESP32 nhưng
  **chưa được chạy**; phần logic (bộ đệm, idempotent, JSON) được kiểm thử trên máy.
* `esp_mqtt_client_publish` không được gọi trong trình xử lý sự kiện (theo tài liệu) — mọi publish đều từ `loop()`.
