# SVMG Backend — FastAPI

Backend server cho hệ thống Smart Vessel Motion Guard, xử lý dữ liệu telemetry, quản lý cảnh báo và cung cấp REST API.

## Tech Stack

- **FastAPI** — Web framework
- **SQLAlchemy** — ORM & database
- **Paho MQTT** — Kết nối MQTT broker
- **JWT (PyJWT)** — Xác thực người dùng
- **Uvicorn** — ASGI server
- **SQLite / PostgreSQL** — Database

## Modules

| Module | Mô tả |
|--------|-------|
| `ingest` | Nhận và lưu trữ telemetry từ MQTT |
| `alarms` | Quản lý cảnh báo (CRUD, acknowledge, escalate) |
| `commands` | Gửi lệnh đến thiết bị qua MQTT (reset, config, OTA) |
| `auth` | Đăng ký, đăng nhập, JWT token |
| `reports` | Báo cáo tổng hợp theo ngày/tuần/tháng |
| `replay` | Phát lại dữ liệu lịch sử (time-series replay) |
| `health` | Kiểm tra sức khỏe hệ thống (DB, MQTT, uptime) |
| `monitor` | Dashboard data: thống kê realtime |
| `notify` | Gửi thông báo qua Telegram / Email webhook |

## Cài đặt & Chạy

```bash
cd backend

# Tạo virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Cài đặt dependencies
pip install -r requirements.txt

# Cấu hình biến môi trường
cp ../infra/.env.example .env
# Chỉnh sửa .env theo nhu cầu

# Chạy server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Biến môi trường (.env)

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `DATABASE_URL` | `sqlite:///./svmg.db` | Connection string database |
| `MQTT_BROKER` | `localhost` | Địa chỉ MQTT broker |
| `MQTT_PORT` | `1883` | Port MQTT |
| `MQTT_USER` | `backend` | Username MQTT |
| `MQTT_PASS` | — | Password MQTT |
| `JWT_SECRET` | — | Secret key cho JWT |
| `JWT_ALGORITHM` | `HS256` | Thuật toán JWT |
| `JWT_EXPIRE_MINUTES` | `60` | Thời gian hết hạn token |
| `TELEGRAM_BOT_TOKEN` | — | Token bot Telegram |
| `TELEGRAM_CHAT_ID` | — | Chat ID Telegram |

## API Documentation

Sau khi chạy server, truy cập:

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)
