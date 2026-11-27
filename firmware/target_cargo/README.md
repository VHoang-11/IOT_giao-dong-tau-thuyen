# Cargo Node (Multi-Node) – ESP32 thứ 2: hầm hàng

Tàu có **hai mạch ESP32 độc lập**:

| Node | `device_id` | Cảm biến | Topic |
|---|---|---|---|
| Motion Node (`firmware/`) | `vessel-demo-01` | MPU6050, 23 đặc trưng, Baseline B/RF, FSM cảnh báo dao động | `telemetry`, `event`, `status`, `health`, `cmd`, `config`, `cmd/ack` |
| **Cargo Node** (thư mục này) | `vessel-demo-01-cargo` | chiết áp mực nước **GPIO 35**, DHT22 **GPIO 4** | `cargo` (QoS 0), `status` (QoS 1, retained, có LWT), `health` (QoS 0) |

Cargo Node **không** gửi `roll_deg`/`pitch_deg`, không nhận `cmd`/`config` (ACL không cấp). Cảm biến lỗi → `sensor_ok=false` và giá trị `null`, không gửi số giả. Hợp đồng: [`contracts/schemas/cargo.json`](../../contracts/schemas/cargo.json), [`contracts/mqtt_topics.md`](../../contracts/mqtt_topics.md).

## Build

```powershell
cd firmware/target_cargo
pio run
```

## Cấu hình & bí mật

- Mặc định trong `include/cargo_config.h` (id, tàu chính `vessel-demo-01`, nguồn `SIMULATION`, WiFi `Wokwi-GUEST`, broker `host.wokwi.internal:1883`).
- Tài khoản MQTT riêng: sao chép `include/secrets_cargo.example.h` → `include/secrets_cargo.h` (đã nằm trong `.gitignore`, **không commit**).
- Tài khoản phải có trong `infra/mosquitto/passwd` (tạo bằng `mosquitto_passwd`, file này cũng bị `.gitignore`) và quyền ghi trong `infra/mosquitto/acl`. Sau khi sửa phải **restart mosquitto** để nạp lại.

## Chạy mô phỏng Wokwi (song song với Motion Node)

Sơ đồ: [`../wokwi/diagram_cargo.json`](../wokwi/diagram_cargo.json); cấu hình: [`../wokwi/wokwi.cargo.toml`](../wokwi/wokwi.cargo.toml) (cổng rfc2217 4002). Cần một cửa sổ Wokwi riêng cho mỗi node; xem ghi chú đầu file `wokwi.cargo.toml`.

## Liên kết với tàu chính (Backend)

Cargo Node tự đăng ký khi gửi bản tin đầu tiên (`AUTO_REGISTER_DEVICES=true`) và được Backend đánh dấu `node_type=CARGO` (không hiện như một tàu). **Admin phải gắn nó vào tàu chính** thì dashboard mới gộp dữ liệu hầm hàng:

```bash
curl -X PATCH http://localhost:8000/api/v1/devices/vessel-demo-01-cargo \
  -H "Authorization: Bearer <JWT admin>" -H "Content-Type: application/json" \
  -d '{"parent_device_id":"vessel-demo-01"}'
```

`parent_device_id` trong payload của thiết bị chỉ để đối chiếu, **không** tự liên kết.
