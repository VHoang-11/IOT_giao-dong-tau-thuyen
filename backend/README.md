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
| M3-06 | Voyage + báo cáo PDF/CSV | Phần lõi xong (chuyến đi, số liệu, CSV, PDF). **Chưa nối** với lệnh `start_voyage` xuống thiết bị (chờ M1); báo cáo chưa tự sinh khi kết thúc chuyến (chờ nhóm quyết định) |
| Ngoài WP | Quản lý thiết bị (Admin), số đếm ingest, dọn dữ liệu cũ, hiệu chuẩn, gắn nhãn cảnh báo, TLS MQTT | Xong |
| M3-07 | Replay, Health, Model monitor | **Replay**, **Health** và **độ nhất quán RF/Baseline** xong. **Drift PSI chưa khả dụng** (chờ M2: vector 14 đặc trưng, `ml/monitor/`); endpoint trả `available=false`, không trả số giả |
| M3-08 | Thông báo Telegram/email | Xong (chưa gửi thử tin thật) |
| M3-09 | Kiểm thử T06/T09/T10/T14 + README | 375 test, độ phủ 97%, gồm test **qua kết nối MQTT thật** (broker thuần Python). **Chưa** chạy với Mosquitto, ESP32 hay đội tàu thật: T14 và T05 chờ M1/M2 |

## Công nghệ

FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic v2 · paho-mqtt 2.x · PyJWT · httpx · jsonschema · ReportLab. CSDL: SQLite chế độ WAL (dev), PostgreSQL (dự kiến cho production, **chưa chạy thử trên PostgreSQL**). Phiên bản thư viện được **ghim** trong `requirements.txt` (bộ đã chạy đủ test trên Python 3.13.5).

## Cấu trúc

```
backend/
├── main.py                  # entrypoint, lifespan (MQTT, quét nền, bootstrap admin)
├── app/
│   ├── core/                # config, db, logging (JSON), security (JWT/RBAC), passwords (scrypt)
│   ├── models/              # 10 bảng SQLAlchemy + enums
│   ├── schemas/             # Pydantic request/response
│   ├── routers/             # auth, devices, alarms, commands, device_health, notify, voyages, replay, monitor, ingest_stats, retention, health
│   └── services/            # audit, auth, voyages, retention
├── ingest/                  # validator (JSON Schema), service (xử lý bản tin), consumer (paho), stats (bộ đếm)
├── alarms/                  # service (vòng đời cảnh báo), realtime (WebSocket hub)
├── commands/                # params (an toàn), service (vòng đời lệnh), config_service, publisher
├── notify/                  # Telegram + email webhook
├── reports/                 # metrics (số liệu), csvexport, pdf, fonts/ (DejaVu, kèm license)
├── migrations/              # Alembic (0001 schema, 0002 định danh cảnh báo, 0003 nhãn cảnh báo, 0004 chuyến đi, 0005 bật/tắt thiết bị)
├── scripts/                 # export_openapi.py, create_user.py
├── replay/                  # Replay API (service lấy dữ liệu theo trang)
└── monitor/                 # nhất quán RF vs Baseline B; drift PSI chờ M2
```

## Cài đặt & chạy

Chạy các lệnh **từ thư mục `backend/`** (file `.env` được đọc theo thư mục hiện tại).

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows   |   source venv/bin/activate  (Linux/Mac)
pip install -r requirements.txt        # chạy backend (phiên bản đã ghim)
pip install -r requirements-dev.txt    # thêm: chạy đủ test (pdfplumber đọc PDF, amqtt = broker MQTT trong test)

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
| `MQTT_TLS` / `MQTT_CA_CERTS` | `false` / *(rỗng)* | Mã hóa kết nối tới broker (thường cổng 8883). Luôn xác minh chứng chỉ, **không có tùy chọn tắt xác minh**. `ENV=production` mà chưa bật sẽ có cảnh báo |
| `AUTO_REGISTER_DEVICES` | `true` | `false` = chỉ nhận thiết bị Admin đã đăng ký trước (`POST /devices`); nên dùng ở production |
| `DOCS_ENABLED` | *(tự động)* | Bật `/docs`, `/redoc`, `/openapi.json`. Mặc định bật ở dev, **tắt khi `ENV=production`** |
| `CONTRACTS_DIR` | *(rỗng → `<repo>/contracts/schemas`)* | Thư mục JSON Schema |
| `ALARM_ESCALATE_AFTER_S` | `60` | Cảnh báo chưa ACK sau N giây → leo thang |
| `ALARM_ESCALATION_ENABLED` / `ALARM_ESCALATION_CHECK_S` | `true` / `5` | Bật/tắt và chu kỳ quét nền (leo thang cảnh báo, TIMEOUT lệnh) |
| `HEALTH_STALE_S` | `90` | Thiết bị im quá N giây = `stale` (health gửi mỗi 30 s → 3 chu kỳ) |
| `RETENTION_HEALTH_DAYS` / `RETENTION_TELEMETRY_DAYS` | `0` / `0` | Dọn dữ liệu cũ; **0 = giữ mãi (mặc định)**. Xem mục *Dọn dữ liệu cũ* |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | *(rỗng)* | Bật kênh Telegram khi cả hai được đặt |
| `EMAIL_WEBHOOK_URL` | *(rỗng)* | Bật kênh email webhook |
| `NOTIFY_COOLDOWN_S` | `30` | Không gửi lại cùng một thông báo trong N giây |
| `NOTIFY_TIMEOUT_S` / `NOTIFY_RETRIES` / `NOTIFY_BACKOFF_S` | `5` / `2` / `1` | Thời gian chờ, số lần thử lại, giãn cách giữa các lần thử |
| `CORS_ORIGINS` | `http://localhost:5173` | Origin được phép, ngăn cách bằng dấu phẩy |

**Không commit `.env`.** `.gitignore` đã chặn.

## Xác thực & phân quyền

`POST /api/v1/auth/login` (form `username`, `password`) → JWT. Gửi kèm `Authorization: Bearer <token>`. WebSocket dùng `?token=<JWT>`. Vai trò và trạng thái tài khoản được đọc từ CSDL ở **mỗi request**, nên hạ quyền/khóa tài khoản có hiệu lực ngay.

| Vai trò | Quyền |
|---------|-------|
| **OPERATOR** | Xem dữ liệu, ACK cảnh báo, gửi lệnh `mute_alarm` |
| **SUPERVISOR** | + tạo/kết thúc chuyến đi, `set_profile`, `set_threshold`, `calibrate_zero`, `start/stop_voyage`, `PUT /config`, rollback, **gắn nhãn cảnh báo**, xem audit và số đếm ingest |
| **ADMIN** | + `restart_device`, quản lý người dùng và **thiết bị** (đăng ký, đặt tên, bật/tắt), đặt lại số đếm ingest, kiểm tra kênh thông báo, dọn dữ liệu cũ |

Mọi lần bị từ chối (403) và mọi lệnh/cấu hình đều ghi vào `audit_log` (`GET /api/v1/audit`).

## API

| Nhóm | Endpoint |
|------|----------|
| Auth | `POST /auth/login`, `GET /auth/me`, `POST /auth/change-password` |
| Người dùng (Admin) | `GET/POST /users`, `PATCH /users/{id}` |
| Thiết bị | `GET /devices`, `/devices/{id}`, `/devices/{id}/telemetry`; Admin: `POST /devices`, `PATCH /devices/{id}` |
| Sức khỏe | `GET /health/devices` (kèm trạng thái hiệu chuẩn), `/devices/{id}/health` |
| Giám sát mô hình | `GET /monitor/agreement`, `/monitor/drift` |
| Số đếm ingest | `GET /ingest/stats` (Supervisor), `POST /ingest/stats/reset` (Admin) |
| Dọn dữ liệu (Admin) | `GET /retention/status`, `POST /retention/run` |
| Cảnh báo | `GET /alarms` (lọc `state`, `label`, `unlabeled`), `/alarms/{id}`, `/alarms/stats`, `POST /alarms/{id}/ack`, `PUT /alarms/{id}/label`, WebSocket `/ws/alarms` |
| Chuyến đi (Supervisor tạo/kết thúc) | `POST /voyages`, `GET /voyages`, `/voyages/{id}`, `POST /voyages/{id}/end` |
| Báo cáo chuyến | `GET /voyages/{id}/summary`, `/telemetry.csv`, `/alarms.csv`, `/report.pdf` |
| Replay | `GET /voyages/{id}/replay` (lọc `from_time/to_time` hoặc `from_t_sim/to_t_sim`, `limit`, `cursor`) |
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
- Bản tin chứa `NaN`/`Infinity`/số tràn, hoặc chuỗi dài quá cột trong CSDL, bị từ chối ngay ở ingest (không làm hỏng API đọc).
- Backend **không tự điền giá trị cấu hình mặc định**: phiên bản config đầu tiên chỉ chứa đúng những trường người gọi gửi.
- Việc nặng (băm mật khẩu, gửi thông báo thử) chạy ngoài event loop; WebSocket gửi song song, client chậm bị loại để không chặn cảnh báo tới người khác.
- SQLite chạy chế độ WAL + `busy_timeout` để MQTT, API và tác vụ nền ghi đồng thời không gây `database is locked`.
- **Không bao giờ trả số liệu giả:** drift chưa có nguồn thì `available=false` kèm lý do (không phải PSI = 0, không phải "ổn định"); tỉ lệ chưa có mẫu thì `null` chứ không phải 0%.
- Thiết bị bị Admin vô hiệu hóa: bản tin bị từ chối (hiện trong số đếm lỗi), không nhận lệnh, cấu hình, chuyến mới. Không có chức năng xóa thiết bị để giữ lịch sử và báo cáo.
- `/docs` và `/openapi.json` tự tắt khi `ENV=production`.

## Gắn nhãn cảnh báo (đánh giá sau sự việc)

`PUT /api/v1/alarms/{id}/label` với `{"label": "TRUE_ALARM" | "FALSE_ALARM" | "UNCLEAR"}` (SUPERVISOR trở lên). Ghi lại ai gắn và lúc nào, mọi lần đổi nhãn đều có audit `ALARM_LABEL`.

- Nhãn **chỉ để đánh giá**, không bao giờ đổi trạng thái cảnh báo: gắn "sai" không tự ACK, không tắt, không chặn leo thang.
- `GET /alarms/stats` trả thêm `labeled`, `by_label`, `label_coverage` và `false_alarm_rate = FALSE / (TRUE + FALSE)`. `UNCLEAR` và cảnh báo chưa đánh giá **không** nằm trong mẫu số; chưa có kết luận nào thì giá trị là `null`, không phải 0%.
- Tên giá trị nhãn do backend đặt từ "đúng/sai/chưa rõ" trong README gốc, **cần M4 xác nhận** khi làm giao diện.

## Chuyến đi và báo cáo (G4)

**Chuyến đi** là một bản ghi trong backend: `POST /voyages` (`device_id`, tùy chọn `voyage_id`; bỏ trống thì sinh `V-YYYY-NNN`). Mỗi thiết bị chỉ có **tối đa một chuyến đang chạy** (CSDL tự chặn bằng chỉ mục duy nhất có điều kiện). Việc này **không tự gửi lệnh `start_voyage`** xuống thiết bị; bản ghi chuyến gom dữ liệu theo trường `voyage_id` mà thiết bị gắn vào telemetry. Chưa có telemetry nào mang `voyage_id` đó thì báo cáo vẫn trả về, với số liệu rỗng và ghi chú rõ.

**Báo cáo không lưu số đã tính**: mỗi lần gọi đều tính lại từ dữ liệu gốc. `summary.json` kèm `telemetry_csv_sha256`, là SHA-256 của file `telemetry.csv`, để đối chiếu rằng hai bên tính lại từ **cùng dữ liệu đầu vào**. CSV có BOM UTF-8, chuỗi bắt đầu bằng `= + - @` được chèn dấu `'` để Excel không chạy thành công thức.

Công thức (để tính lại độc lập, xem thêm đầu file `reports/metrics.py`):

| Số liệu | Cách tính |
|---|---|
| `samples` | Số dòng telemetry có `(device_id, voyage_id)` của chuyến |
| `expected_samples` | Tổng theo từng `boot_id` của `seq_max − seq_min + 1` (`seq` đếm lại sau mỗi lần khởi động) |
| `received_rate` | `samples / expected_samples` |
| Thống kê roll/pitch/heel/rms | **Chỉ** mẫu `sensor_ok = true`; mẫu `sensor_ok = false` chỉ được đếm riêng |
| `p95_abs_roll_deg` | Nearest-rank: `sorted(|roll|)[ceil(0.95·n) − 1]` |
| `mean_rms_roll_deg` | Trung bình `rms_roll_deg` do thiết bị gửi (backend không tự tính lại từ roll) |
| Phân bố lớp / mức cảnh báo | Đếm theo **số mẫu**, không phải theo thời gian |
| `rf_baseline_agreement_rate` | `#(class_rf == class_baseline_b) / #(mẫu có cả hai)` |
| `duration_s` | `last_sample_at − first_sample_at` theo `server_rx_time` |
| `false_alarms_per_hour` | `#FALSE_ALARM / (duration_s/3600)`; là `null` nếu chưa có cảnh báo nào được đánh giá |

Cảnh báo thuộc chuyến theo `voyage_id` của telemetry mới nhất lúc cảnh báo mở. Lệnh được tính nếu `created_at` nằm trong khoảng mẫu đầu → mẫu cuối. Chuyến đang chạy được đánh dấu `provisional` (số liệu tạm thời). Dữ liệu trộn `SENSOR` và `SIMULATION` ghi nhãn `MIXED`.

**PDF** dùng ReportLab và font DejaVu Sans (có đủ dấu tiếng Việt) đặt trong `reports/fonts/` kèm `LICENSE_DEJAVU`; biểu đồ roll được lấy mẫu thưa tối đa 500 điểm và **không vẽ đường ngưỡng nào** vì ngưỡng chỉ là tham số demo.

## Replay (xem lại chuyến đi)

`GET /api/v1/voyages/{voyage_id}/replay` trả dữ liệu để giao diện **phát lại** chuyến đi. Tốc độ ×1–×60 do giao diện tự xử lý (đồng hồ chạy trên trình duyệt), backend không có tham số tốc độ.

| Tham số | Ý nghĩa |
|---|---|
| `from_time`, `to_time` | Lọc theo **giờ server** (ISO 8601, thiếu múi giờ thì coi là UTC), bao gồm cả hai đầu |
| `from_t_sim`, `to_t_sim` | Lọc theo `t_sim_s` của thiết bị. **Không dùng chung** với `from_time/to_time` (chọn một trục) |
| `limit` | Số mẫu telemetry mỗi trang (1–5000, mặc định 1000) |
| `cursor` | `next_cursor` của trang trước; giữ nguyên các tham số lọc khi gọi trang tiếp |

Kết quả gồm `meta` (tổng quan thanh thời gian), `telemetry`, `alarm_events` (từng lần đổi mức do thiết bị gửi), `alarms` (trạng thái hiện tại kèm nhãn đánh giá) và `commands`.

- **Thứ tự:** tăng dần theo `(server_rx_time, id)`, **không** theo `t_sim_s`, vì hợp đồng chưa nói `t_sim_s` có đếm lại sau khi thiết bị khởi động lại hay không. `meta.t_sim_monotonic` cho biết trục `t_sim_s` có đáng tin trong chuyến đó không (`false` nếu có chỗ giảm).
- **Không cắt dữ liệu âm thầm:** `truncated=true` nghĩa là còn trang sau. Nối tất cả các trang lại cho ra đúng chuỗi như `telemetry.csv` (đã có test; phục vụ T15 "replay khớp dữ liệu gốc").
- `alarm_events` và `commands` chia theo khoảng thời gian của từng trang, nên mỗi mục xuất hiện **đúng một lần** qua các trang. `alarms` là các cảnh báo đang hoạt động trong khoảng đó, nên có thể lặp lại giữa các trang (giao diện gộp theo `id`).
- Mỗi mẫu luôn có `source_mode` và `sensor_ok` (giao diện cần hiển thị mẫu `sensor_ok=false` khác đi).
- `meta` có `duration_wall_s` (giờ server) và `timewarps`; backend **không** đoán thời lượng theo giờ mô phỏng.

## Múi giờ

Mọi mốc thời gian lưu và trả về là **UTC, có ký hiệu múi giờ** (`...Z`). SQLite không lưu múi giờ, nên backend dùng kiểu `UTCDateTime` để đọc ra luôn có múi giờ UTC (nếu không, JavaScript hiểu chuỗi thiếu `Z` là giờ địa phương và dashboard ở UTC+7 sẽ lệch 7 tiếng). Giao diện chỉ cần đổi sang giờ địa phương khi hiển thị.

## Giám sát mô hình (G6)

- `GET /monitor/agreement?device_id=…[&voyage_id=…][&limit=…]`: tỉ lệ Random Forest **trùng** Baseline B trên `limit` mẫu gần nhất (theo giờ nhận) có đủ cả hai nhãn. Đây là độ **nhất quán** giữa hai mô hình, không phải độ chính xác (không có nhãn thật) và không phải dự báo nguy hiểm. Mẫu `sensor_ok=false` bị loại và đếm riêng (`excluded_sensor_fault`); kết quả luôn có `source_label` (`SIMULATION`/`SENSOR`/`MIXED`); chia theo **lớp RF** (`by_rf_class`), không đổi tên thành mức cảnh báo. `agreement_rate = null` khi chưa có mẫu.
- `GET /monitor/drift?device_id=…[&window_hours=…]`: **hiện chưa khả dụng**. PSI cần vector 14 đặc trưng (`contracts/features.md`), trong khi telemetry chỉ lưu 3 đặc trưng tóm tắt. Endpoint trả `available=false`, `reason`, `expected_features` (14 tên đúng thứ tự hợp đồng, có test đối chiếu), và `window_samples` thật. **Không trả PSI nào.** Khi M2 giao `ml/monitor/` và nguồn đặc trưng, thay phần trả về trong `monitor/service.py`.

## Quản lý thiết bị (Admin)

Thiết bị mặc định **tự đăng ký** khi có bản tin đầu tiên. Admin có thể:

- `POST /devices` `{device_id, name?, source_mode}`: đăng ký trước. `source_mode` (`SENSOR`/`SIMULATION`) **bắt buộc**, không có mặc định ngầm; giá trị này được cập nhật theo bản tin thật khi thiết bị bắt đầu gửi.
- `PATCH /devices/{id}` `{name?, enabled?}`: đặt tên, bật/tắt. Mọi thay đổi có audit.
- Đặt `AUTO_REGISTER_DEVICES=false` để chỉ nhận thiết bị đã đăng ký (khuyến nghị cho production).

Thiết bị `enabled=false`: ingest từ chối bản tin; lệnh, cấu hình, chuyến mới trả 409. Lưu ý: tắt thiết bị nghĩa là **bỏ qua cả cảnh báo** của nó, chỉ dùng cho thiết bị đã ngừng hoạt động hoặc đáng ngờ.

## Số đếm ingest (đo T06, T14)

`GET /ingest/stats` trả số bản tin theo kết quả (`STORED`, `DUPLICATE`, `INVALID`, `REJECTED`, `IGNORED`), theo loại bản tin và theo thiết bị, kèm các tỉ lệ (`null` khi chưa có bản tin), và **50 bản tin bị từ chối gần nhất kèm lý do** để M1 tự sửa firmware mà không phải đọc log. `POST /ingest/stats/reset` (Admin, có audit) đặt lại trước mỗi lần chạy thí nghiệm. Bộ đếm nằm trong bộ nhớ tiến trình (mất khi khởi động lại; không chia sẻ giữa nhiều worker); số theo từng chuyến (dựa trên `seq`) xem trong báo cáo chuyến đi.

## Hiệu chuẩn (G5)

`GET /health/devices` có thêm `last_calibrated_at` (lần `calibrate_zero` gần nhất được thiết bị xác nhận `APPLIED`) và `last_calibration_state` (kết quả lần gửi lệnh gần nhất). **Chỉ phản ánh lệnh qua backend**; hiệu chuẩn bằng nút/chiết áp trên thiết bị không được ghi nhận. `null` nghĩa là chưa có lần nào (không phải "không cần").

## Dọn dữ liệu cũ (retention)

**Mặc định TẮT** (`0` ngày = giữ mãi). Khi bật, chỉ động vào `device_health` cũ hơn `RETENTION_HEALTH_DAYS` và telemetry **không thuộc chuyến nào** cũ hơn `RETENTION_TELEMETRY_DAYS`. **Không bao giờ xóa**: telemetry thuộc chuyến đi (nguồn của báo cáo, replay, T11/T15), cảnh báo, sự kiện cảnh báo, lệnh, cấu hình, chuyến đi, nhật ký kiểm toán. Xóa theo lô nhỏ, commit từng lô, có audit `RETENTION_PURGE`. `GET /retention/status` xem chính sách và số dòng; `POST /retention/run` chạy ngay. Thời gian giữ dữ liệu là quyết định của nhóm, chưa chốt.

## Thông báo Telegram / email

1. Tạo bot qua BotFather, lấy token; lấy `chat_id` của nhóm/người nhận.
2. Đặt `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (và/hoặc `EMAIL_WEBHOOK_URL`) trong `.env`.
3. Đăng nhập Admin rồi gọi `POST /api/v1/notify/test` để kiểm tra từng kênh.

Gửi khi: cảnh báo lên **CRITICAL**, cảnh báo chưa ACK bị **leo thang**, cảnh báo **nặng hơn sau khi đã ACK**, thiết bị chuyển **online → offline**. Gửi ở luồng nền, lỗi chỉ ghi log và không làm hỏng việc xử lý cảnh báo.

## Kiểm thử

Từ thư mục gốc repo (nên dùng venv riêng + `pip install -r backend/requirements-dev.txt`):

```bash
python -m pytest tests/backend -q
```

**375 test, độ phủ ~97%.** Thiếu `amqtt` hoặc `pdfplumber` thì test tương ứng tự bỏ qua (không lỗi). Đã chạy đủ trong một môi trường sạch dựng từ `requirements-dev.txt`.

- **Test đơn vị/API:** SQLite trong bộ nhớ, publisher MQTT giả, mạng giả (`httpx.MockTransport`). Không gửi tin nhắn thật, không dùng dữ liệu của thành viên khác: chỉ `contracts/examples/` và payload tối thiểu trong chính file test.
- **Test tích hợp MQTT thật** (`tests/backend/test_mqtt_integration.py`): `consumer.py` kết nối tới một broker `amqtt` qua **TCP thật** (không cần Docker), cùng một "thiết bị giả" dùng paho. Phủ: nhận telemetry/event/status, khử trùng khi gửi lại sau mất mạng (T06), payload xấu, thiết bị bị vô hiệu hóa, **LWT**, lệnh khứ hồi (PUBACK → `DELIVERED` → ACK → `APPLIED`), mute bị chặn khi CRITICAL không bao giờ tới thiết bị, cấu hình **retained** tới thiết bị bật sau, **broker chết rồi sống lại** (tự kết nối lại, subscribe lại, không xếp hàng lệnh hỏng). Mỗi test dùng một broker riêng để không rò rỉ tin retained.
- Bộ test tích hợp đã được kiểm chứng bằng cách **cố ý phá code thật** (bỏ `subscribe`; bỏ chốt chặn gửi lệnh khi mất kết nối) và xem test có bắt được không.
- `test_pinned_versions_match_what_is_installed` báo ngay nếu ai nâng thư viện mà quên cập nhật `requirements.txt`.

## Hạn chế đã biết

- **Đã chạy qua broker MQTT thuần Python (`amqtt`), chưa chạy với Mosquitto, ESP32/Wokwi hay đội tàu thật.** T05 và T14 vẫn chờ M1/M2. Chưa thử trên **PostgreSQL**. Chưa gửi **Telegram thật**. `Dockerfile` chưa được build thử (Docker Desktop chưa chạy khi kiểm tra).
- MQTT TLS đã có cấu hình nhưng chưa được thử với broker thật (cần chứng chỉ).
- Chưa có refresh token và đăng xuất phía server (token sống `JWT_EXPIRE_MINUTES`; muốn thu hồi sớm thì khóa tài khoản).
- Bộ đếm khóa đăng nhập và bộ đếm ingest nằm trong bộ nhớ tiến trình (mất khi khởi động lại, không chia sẻ giữa nhiều worker).
- Token WebSocket nằm trong URL (có thể vào log của proxy); phiên WebSocket không tự ngắt khi token hết hạn. WebSocket chỉ đẩy cảnh báo và lệnh, **chưa đẩy telemetry** (trang Live Motion đang cần polling hoặc cần thêm kênh, chờ M4 quyết định).
- MTTA tính theo giờ server nhận bản tin, nên có thể bị phóng đại khi thiết bị gửi lại dữ liệu đệm sau mất mạng.
- Báo cáo đọc toàn bộ telemetry của chuyến trong một lượt (bộ nhớ ~ số mẫu). Đã thử 6000 mẫu; chuyến rất dài (hàng trăm nghìn mẫu) chưa kiểm chứng.
- Retention chỉ xóa `device_health` và telemetry không thuộc chuyến; telemetry của chuyến đã kết thúc giữ mãi.
- `contracts/` không nằm trong Docker image, cần mount và đặt `CONTRACTS_DIR`.
- Nếu chạy nhiều instance backend, `client_id` MQTT cố định (`svmg-backend-ingest`) sẽ làm các instance đá nhau khỏi broker.
- `main.py` (vòng đời khởi động, các vòng quét nền) phủ test thấp nhất (~68%).

## Điểm cần thống nhất với nhóm (chưa chốt)

1. **Thuật toán `crc` của config.** Hợp đồng chỉ có ví dụ `"9c1e"`. Backend đang dùng CRC-16/CCITT-FALSE trên JSON chuẩn hóa (khóa sắp xếp, không khoảng trắng, bỏ trường `crc`). Firmware (M1) phải tính y hệt.
2. **`set_profile` / `set_threshold` so với `PUT /config`.** Hiện là hai đường độc lập. Cần M1 xác nhận thiết bị xử lý thế nào.
3. **`DELIVERED`** nghĩa là broker đã nhận (PUBACK), không phải thiết bị đã nhận; chỉ `cmd/ack` mới xác nhận thiết bị.
4. **`voyage_id` trong lệnh `start_voyage`**: thiết bị nhận từ lệnh hay tự sinh rồi báo ngược lên? Hiện `POST /voyages` cho phép truyền sẵn `voyage_id` để khớp với giá trị thiết bị đang phát.
5. **Ý nghĩa của `t_sim_s`**: có đếm lại sau mỗi lần khởi động không? Với dữ liệu thật (`SENSOR`) nó mang nghĩa gì? Replay hiện sắp xếp theo giờ server vì chưa chốt điều này.
6. **Drift PSI (G6):** cần M2 cung cấp vector 14 đặc trưng (qua topic/trường nào, tần suất) và `ml/monitor/`. Trước khi có, endpoint chỉ trả `available=false`.
7. **Thời gian giữ dữ liệu** (retention) và việc "báo cáo tự động" khi kết thúc chuyến nghĩa là gì (chỉ tải được bất kỳ lúc nào, hay tự tạo và lưu file).
8. **Tên giá trị nhãn cảnh báo** (`TRUE_ALARM`/`FALSE_ALARM`/`UNCLEAR`) và các trường `summary.json` do backend đặt, cần M4 xác nhận khi làm giao diện.
