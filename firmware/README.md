# SVMG Firmware — ESP32 trên Wokwi

Firmware ESP32 chạy trên môi trường mô phỏng **Wokwi**, dùng để thu thập và xử lý dữ liệu chuyển động tàu thuyền theo thời gian thực.

## Phần cứng (Wokwi Simulation)

| Linh kiện          | Kết nối          | Mô tả |
|---------------------|------------------|-------|
| **ESP32 DevKit**    | —                | Vi điều khiển chính |
| **MPU6050**         | I2C (SDA=21, SCL=22) | Cảm biến gia tốc + con quay hồi chuyển 6 trục |
| **LCD I2C 16×2**    | I2C (SDA=21, SCL=22, addr=0x27) | Hiển thị trạng thái, góc roll/pitch, MAI |
| **3 Buttons**       | GPIO 25, 26, 27  | MODE, ACK, RESET |
| **Potentiometer**   | GPIO 34 (ADC)    | Điều chỉnh tham số mô phỏng (biên độ sóng) |
| **LED**             | GPIO 2           | Chỉ báo trạng thái cảnh báo |
| **Buzzer**          | GPIO 4           | Âm thanh cảnh báo |

## Hai chế độ hoạt động

### SENSOR MODE (mode = 0)
- Đọc dữ liệu thực từ MPU6050
- Lọc bù (complementary filter) → trích xuất đặc trưng → phân loại → cảnh báo
- Gửi telemetry qua MQTT mỗi 0.5s

### SIMULATION MODE (mode = 1)
- Dùng bộ sinh tín hiệu C (`generator.c`) thay cho MPU6050
- Potentiometer điều chỉnh biên độ kích thích
- Hữu ích khi không có cảm biến thực hoặc khi demo

## Mở trong Wokwi

1. Cài đặt extension [Wokwi for VS Code](https://docs.wokwi.com/vscode/getting-started)
2. Mở thư mục `firmware/` trong VS Code
3. File `wokwi.toml` và `diagram.json` đã được cấu hình sẵn
4. Nhấn **F1 → Wokwi: Start Simulator**

## Kết nối MQTT

- **Broker:** Mosquitto (xem `infra/docker-compose.yml`)
- **Topics:**
  - `svmg/{vessel_id}/telemetry` — dữ liệu chuyển động (JSON)
  - `svmg/{vessel_id}/event` — sự kiện cảnh báo
  - `svmg/{vessel_id}/status` — trạng thái thiết bị
  - `svmg/{vessel_id}/health` — sức khỏe hệ thống
  - `svmg/{vessel_id}/cmd` — nhận lệnh từ backend
  - `svmg/{vessel_id}/config` — nhận cấu hình từ backend

## Build & Upload

```bash
# PlatformIO CLI
cd firmware
pio run              # Build
pio run -t upload    # Upload (cho board thật)
```
