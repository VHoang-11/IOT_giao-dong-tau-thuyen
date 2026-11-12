# SVMG Backend — FastAPI

Backend của **Smart Vessel Motion Guard**: nhận bản tin MQTT từ thiết bị, lưu CSDL, quản lý vòng đời cảnh báo, gửi lệnh điều khiển xuống thiết bị và cung cấp REST API + WebSocket cho dashboard.

> **Nguyên mẫu nghiên cứu/đào tạo, KHÔNG phải hệ thống an toàn hàng hải.** Dữ liệu luôn mang cờ `SENSOR` hoặc `SIMULATION`. Các ngưỡng chỉ là tham số demo.

## Tiến độ (phần M3)

| WP | Nội dung | Trạng thái |
|----|----------|-----------|
| M3-01 | Khung FastAPI + CSDL + OpenAPI | Xong |
| M3-02 | MQTT ingest (validate, khử trùng, LWT) | Xong |
| M3-03 | Alarm service (ACK, MTTA, leo thang, WebSocket) | Xong |
| M3-04 | Command service (vòng đời lệnh, TTL, cấu hình có phiên bản, rollback) | Xong |
| M3-05 | JWT + RBAC (3 vai trò) | Xong |
| M3-06 | Voyage + báo cáo PDF/CSV | **Chưa làm** (chờ xác nhận cách M1 xử lý `voyage_id`) |
| M3-07 | Replay, Health, Model monitor | Mới có **Health**; replay và model monitor chưa làm (chờ M2) |
| M3-08 | Thông báo Telegram/email | Xong |
| M3-09 | Kiểm thử T06/T09/T10/T14 + README | Test đơn vị/tích hợp xong; **chưa chạy với broker thật** |

## Công nghệ

FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic v2 · paho-mqtt 2.x · PyJWT · httpx · jsonschema. CSDL: SQLite (dev), PostgreSQL (dự kiến cho production, **chưa chạy thử trên PostgreSQL**).

## Cấu trúc

```
backend/
├── main.py                  # entrypoint, lifespan (MQTT, quét nền, bootstrap admin)
├── app/
│   ├── core/                # config, db, logging (JSON), security (JWT/RBAC), passwords (scrypt)
│   ├── models/              # 10 bảng SQLAlchemy + enums
│   ├── schemas/             # Pydantic request/response
│   ├── routers/             # auth, devices, alarms, commands, device_health, notify, health
│   └── services/            # audit, auth
├── ingest/                  # validator (JSON Schema), service (xử lý bản tin), consumer (paho)
├── alarms/                  # service (vòng đời cảnh báo), realtime (WebSocket hub)
├── commands/                # params (an toàn), service (vòng đời lệnh), config_service, publisher
├── notify/                  # Telegram + email webhook
├── migrations/              # Alembic (0001 schema, 0002 định danh cảnh báo)
├── scripts/                 # export_openapi.py, create_user.py
└── (reports/ replay/ monitor/ — chưa làm)
```

## Cài đặt & chạy

Chạy các lệnh **từ thư mục `backend/`** (file `.env` được đọc theo thư mục hiện tại).

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows   |   source venv/bin/activate  (Linux/Mac)
pip install -r requirements.txt

cp ../infra/.env.example .env    # rồi sửa .env (xem bảng biến môi trường)
python scripts/create_user.py admin ADMIN   # tạo admin đầu tiên (hỏi mật khẩu, không hiện trên màn hình)

uvicorn main:app --reload --port 8000
```

- Swagger UI: http://localhost:8000/docs (dùng nút **Authorize**, đăng nhập bằng username/password)
- OpenAPI: `python scripts/export_openapi.py` → `contracts/openapi.yaml`
- Khi chưa có MQTT broker, backend vẫn chạy (tự kết nối lại). Tắt hẳn bằng `MQTT_ENABLED=false`.
- Tạo bảng bằng `alembic upgrade head`. Môi trường dev còn tự `create_all` khi khởi động.

## Biến môi trường

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `ENV` | `dev` | `production` → **bắt buộc** `JWT_SECRET` ≥ 32 ký tự, không dùng giá trị mẫu; nếu không thì từ chối khởi động |
| `DATABASE_URL` | `sqlite:///./svmg.db` | Chuỗi kết nối CSDL |
| `JWT_SECRET` | *(rỗng)* | Khóa ký JWT. Tạo: `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `JWT_ALGORITHM` | `HS256` | Chỉ nhận `HS256/HS384/HS512` |
| `JWT_EXPIRE_MINUTES` | `60` | Thời hạn token |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `admin` / *(rỗng)* | Đặt `ADMIN_PASSWORD` để tự tạo admin đầu tiên khi bảng `users` rỗng |
| `LOGIN_MAX_FAILURES` / `LOGIN_LOCKOUT_S` | `5` / `300` | Khóa đăng nhập sau N lần sai |
| `MQTT_ENABLED` | `true` | Bật/tắt consumer MQTT |
| `MQTT_BROKER` / `MQTT_PORT` | `localhost` / `1883` | Broker |
| `MQTT_USER` / `MQTT_PASS` | `backend` / *(rỗng)* | Tài khoản MQTT |
| `CONTRACTS_DIR` | *(rỗng → `<repo>/contracts/schemas`)* | Thư mục JSON Schema |
| `ALARM_ESCALATE_AFTER_S` | `60` | Cảnh báo chưa ACK sau N giây → leo thang |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | *(rỗng)* | Bật kênh Telegram khi cả hai được đặt |
| `EMAIL_WEBHOOK_URL` | *(rỗng)* | Bật kênh email webhook |
| `NOTIFY_COOLDOWN_S` | `30` | Không gửi lại cùng một thông báo trong N giây |
| `CORS_ORIGINS` | `http://localhost:5173` | Origin được phép, ngăn cách bằng dấu phẩy |

**Không commit `.env`.** `.gitignore` đã chặn.

## Xác thực & phân quyền

`POST /api/v1/auth/login` (form `username`, `password`) → JWT. Gửi kèm `Authorization: Bearer <token>`. WebSocket dùng `?token=<JWT>`. Vai trò và trạng thái tài khoản được đọc từ CSDL ở **mỗi request**, nên hạ quyền/khóa tài khoản có hiệu lực ngay.

| Vai trò | Quyền |
|---------|-------|
| **OPERATOR** | Xem dữ liệu, ACK cảnh báo, gửi lệnh `mute_alarm` |
| **SUPERVISOR** | + `set_profile`, `set_threshold`, `calibrate_zero`, `start/stop_voyage`, `PUT /config`, rollback, xem audit |
| **ADMIN** | + `restart_device`, quản lý người dùng, kiểm tra kênh thông báo |

Mọi lần bị từ chối (403) và mọi lệnh/cấu hình đều ghi vào `audit_log` (`GET /api/v1/audit`).

## API

| Nhóm | Endpoint |
|------|----------|
| Auth | `POST /auth/login`, `GET /auth/me`, `POST /auth/change-password` |
| Người dùng (Admin) | `GET/POST /users`, `PATCH /users/{id}` |
| Thiết bị | `GET /devices`, `/devices/{id}`, `/devices/{id}/telemetry` |
| Sức khỏe | `GET /health/devices`, `/devices/{id}/health` |
| Cảnh báo | `GET /alarms`, `/alarms/{id}`, `/alarms/stats`, `POST /alarms/{id}/ack`, WebSocket `/ws/alarms` |
| Lệnh | `POST /devices/{id}/commands`, `GET /commands`, `/commands/{cmd_id}`, `/commands/stats` |
| Cấu hình | `GET/PUT /devices/{id}/config`, `POST /devices/{id}/config/rollback` |
| Kiểm toán | `GET /audit` |
| Thông báo (Admin) | `GET /notify/status`, `POST /notify/test` |
| Hệ thống | `GET /healthz` (công khai) |

Tất cả đường dẫn trên có tiền tố `/api/v1` (trừ `/healthz` và `/ws/alarms`). Chi tiết ở Swagger hoặc `contracts/openapi.yaml`.

## Luồng dữ liệu MQTT

Topic `svmg/{device_id}/…` theo `contracts/mqtt_topics.md`.

- `telemetry`, `event`, `status` (kể cả LWT), `health`, `cmd/ack` đi vào `ingest/service.py`: kiểm tra topic → JSON → **JSON Schema** → `device_id` trong payload phải trùng topic → chống trùng theo `(device_id, boot_id, seq)` → lưu + gắn `server_rx_time`.
- `event` cập nhật vòng đời cảnh báo (`alarms/service.py`); `cmd/ack` cập nhật vòng đời lệnh.
- Lệnh và cấu hình đi xuống qua `commands/` (`cmd` QoS 1; `config` QoS 1 + retained).

## Quy tắc an toàn đã cài đặt (đều có test)

- Lệnh từ xa **không** tắt được cảnh báo cục bộ: lệnh theo danh sách trắng, tham số lạ bị từ chối.
- **Không MUTE khi CRITICAL** (kể cả lần bị chặn vẫn ghi audit).
- `phi_hard_deg` chỉ nhận 15–25.
- Lệnh quá TTL → `TIMEOUT`; ACK đến muộn **không** làm lệnh sống lại.
- Mất kết nối MQTT thì **từ chối gửi lệnh (503)** thay vì xếp hàng, vì lệnh trễ có thể bị thiết bị thực thi sau hạn TTL.
- ACK trên server chỉ ghi nhận người trực đã biết, **không** tắt cảnh báo trên thiết bị.
- Mức cảnh báo nặng hơn sau khi đã ACK → cảnh báo bật lại, yêu cầu xác nhận lại.
- Rollback cấu hình tạo phiên bản **mới** (số lớn hơn) vì thiết bị chỉ nhận `config_version` lớn hơn hiện tại.
- Thông báo luôn ghi nhãn `SENSOR`/`SIMULATION`; token Telegram không bao giờ vào log.

## Thông báo Telegram / email

1. Tạo bot qua BotFather, lấy token; lấy `chat_id` của nhóm/người nhận.
2. Đặt `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (và/hoặc `EMAIL_WEBHOOK_URL`) trong `.env`.
3. Đăng nhập Admin rồi gọi `POST /api/v1/notify/test` để kiểm tra từng kênh.

Gửi khi: cảnh báo lên **CRITICAL**, cảnh báo chưa ACK bị **leo thang**, cảnh báo **nặng hơn sau khi đã ACK**, thiết bị chuyển **online → offline**. Gửi ở luồng nền, lỗi chỉ ghi log và không làm hỏng việc xử lý cảnh báo.

## Kiểm thử

Từ thư mục gốc repo:

```bash
python -m pytest tests/backend -q
```

Test dùng SQLite trong bộ nhớ, publisher MQTT giả và mạng giả (`httpx.MockTransport`). **Không cần broker, không gửi tin nhắn thật, không dùng dữ liệu của thành viên khác** — chỉ dùng `contracts/examples/` và payload tối thiểu trong chính file test.

## Hạn chế đã biết

- **Chưa chạy với Mosquitto thật** và **chưa thử trên PostgreSQL**.
- Chưa có refresh token và đăng xuất phía server (token sống `JWT_EXPIRE_MINUTES`; muốn thu hồi sớm thì khóa tài khoản).
- Bộ đếm khóa đăng nhập nằm trong bộ nhớ tiến trình (mất khi restart, không chia sẻ giữa nhiều worker).
- Token WebSocket nằm trong URL (có thể vào log của proxy); phiên WebSocket không tự ngắt khi token hết hạn.
- MTTA tính theo giờ server nhận bản tin, nên có thể bị phóng đại khi thiết bị gửi lại dữ liệu đệm sau mất mạng.

## Điểm cần thống nhất với nhóm (chưa chốt)

1. **Thuật toán `crc` của config.** Hợp đồng chỉ có ví dụ `"9c1e"`. Backend đang dùng CRC-16/CCITT-FALSE trên JSON chuẩn hóa (khóa sắp xếp, không khoảng trắng, bỏ trường `crc`). Firmware (M1) phải tính y hệt.
2. **`set_profile` / `set_threshold` so với `PUT /config`.** Hiện là hai đường độc lập. Cần M1 xác nhận thiết bị xử lý thế nào.
3. **`DELIVERED`** nghĩa là broker đã nhận (PUBACK), không phải thiết bị đã nhận; chỉ `cmd/ack` mới xác nhận thiết bị.
4. **`voyage_id` trong lệnh `start_voyage`** (cho M3-06): thiết bị nhận từ lệnh hay tự sinh rồi báo ngược lên?
