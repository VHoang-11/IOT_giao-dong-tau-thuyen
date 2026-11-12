# SVMG MQTT Topic Registry

Tất cả MQTT topics sử dụng prefix chung: `svmg/{device_id}/`

Trong đó `{device_id}` là mã định danh duy nhất của thiết bị (ví dụ: `vessel-demo-01`).

## Topic Map

| Topic                              | QoS | Retained | Direction | Mô tả                                                                                     |
|------------------------------------|-----|----------|-----------|--------------------------------------------------------------------------------------------|
| `svmg/{device_id}/telemetry`       | 0   | No       | Uplink    | Bản tin telemetry định kỳ chứa dữ liệu cảm biến, kết quả phân loại, và mức cảnh báo      |
| `svmg/{device_id}/event`           | 1   | No       | Uplink    | Sự kiện cảnh báo khi alarm level thay đổi (ALARM_STATE)                                   |
| `svmg/{device_id}/status`          | 1   | Yes      | Uplink    | Trạng thái online/offline của thiết bị. LWT message tự động gửi `{"state":"offline"}` khi mất kết nối |
| `svmg/{device_id}/health`          | 0   | No       | Uplink    | Thông tin sức khỏe thiết bị: heap, sensor, I²C errors, buffer usage                       |
| `svmg/{device_id}/cmd`             | 1   | No       | Downlink  | Lệnh điều khiển từ backend/supervisor gửi xuống thiết bị                                  |
| `svmg/{device_id}/cmd/ack`         | 1   | No       | Uplink    | Xác nhận (ACK) từ thiết bị cho lệnh đã nhận: APPLIED hoặc REJECTED                       |
| `svmg/{device_id}/config`          | 1   | Yes      | Downlink  | Cấu hình thiết bị (profile, thresholds, model). Retained để thiết bị nhận khi reconnect   |

## Chi tiết

### Telemetry (`svmg/{device_id}/telemetry`)
- **QoS 0**: Chấp nhận mất gói, ưu tiên throughput cho dữ liệu liên tục
- **Tần suất**: Mỗi `report_interval_s` giây (mặc định 5s, cấu hình qua config)
- **Schema**: [telemetry.json](schemas/telemetry.json)
- **Sample**: [telemetry_sample.json](examples/telemetry_sample.json)

### Event (`svmg/{device_id}/event`)
- **QoS 1**: Đảm bảo gửi ít nhất 1 lần — sự kiện quan trọng không được mất
- **Trigger**: Chỉ phát khi `alarm_level` thay đổi so với trạng thái trước đó
- **Schema**: [event.json](schemas/event.json)
- **Sample**: [event_sample.json](examples/event_sample.json)

### Status (`svmg/{device_id}/status`)
- **QoS 1 + Retained**: Giữ lại trên broker để client mới biết ngay trạng thái thiết bị
- **LWT (Last Will and Testament)**: Broker tự publish `{"state":"offline"}` khi thiết bị disconnect bất thường
- **Schema**: [status.json](schemas/status.json)
- **Samples**: [status_online.json](examples/status_online.json), [status_offline_lwt.json](examples/status_offline_lwt.json)

### Health (`svmg/{device_id}/health`)
- **QoS 0**: Thông tin giám sát, mất gói chấp nhận được
- **Tần suất**: Mỗi 30s (cố định)
- **Schema**: [health.json](schemas/health.json)

### Command (`svmg/{device_id}/cmd`)
- **QoS 1**: Lệnh phải được gửi đến thiết bị ít nhất 1 lần
- **TTL**: Thiết bị bỏ qua lệnh nếu quá `ttl_s` giây kể từ khi publish
- **Schema**: [command.json](schemas/command.json)
- **Sample**: [command_sample.json](examples/command_sample.json)

### Command ACK (`svmg/{device_id}/cmd/ack`)
- **QoS 1**: Xác nhận phải được gửi lại backend
- **Schema**: [command_ack.json](schemas/command_ack.json)
- **Samples**: [command_ack_applied.json](examples/command_ack_applied.json), [command_ack_rejected.json](examples/command_ack_rejected.json)

### Config (`svmg/{device_id}/config`)
- **QoS 1 + Retained**: Thiết bị nhận cấu hình mới nhất khi reconnect
- **Versioning**: `config_version` tăng dần, thiết bị chỉ áp dụng version > hiện tại
- **CRC**: Trường `crc` dùng để verify tính toàn vẹn payload
- **Schema**: [config.json](schemas/config.json)
- **Sample**: [config_sample.json](examples/config_sample.json)
