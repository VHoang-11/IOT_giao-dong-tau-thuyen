# Kết nối Backend (LIVE)

Ứng dụng có hai chế độ, chọn ở màn hình đăng nhập:

- **LIVE (Backend thật):** đăng nhập JWT `POST /api/v1/auth/login`, dữ liệu từ FastAPI (ESP32/Wokwi → MQTT → Backend → SQLite/PostgreSQL).
- **MOCK (demo):** tài khoản demo và dữ liệu sinh sẵn, không gọi mạng.

LIVE **không bao giờ** thay dữ liệu lỗi bằng MOCK. Mất kết nối/dữ liệu cũ được báo rõ trên thanh trạng thái; góc roll/pitch/MAI
hiển thị `—` khi dữ liệu cũ hoặc cảm biến lỗi. JWT chỉ nằm trong bộ nhớ (không ghi đĩa, không log); HTTP 401 → đăng xuất kèm thông báo.

## Cấu trúc

| Tệp | Vai trò |
|---|---|
| `src/data/liveApi.ts` | Client REST (kiểu bám `contracts/openapi.yaml`, timeout 12s, `ApiError` giữ mã HTTP) |
| `src/data/liveMapper.ts` | Chuyển phản hồi Backend → kiểu giao diện; trường Backend không có thì `null`/`—`, không điền số giả |
| `src/data/useLiveBackend.ts` | Polling GET: telemetry/cảnh báo 5s, health/lệnh 10s, thiết bị/cấu hình/chuyến 30s; báo cáo/replay chỉ khi mở màn hình tương ứng |
| `App.tsx` | Chọn nguồn dữ liệu, hành động (ACK, nhãn, lệnh, cấu hình) |

## Chạy

Backend: xem `../backend/README.md` (`uvicorn main:app --port 8000`, tạo tài khoản bằng `scripts/create_user.py`).
Ứng dụng nhập địa chỉ Backend ở màn hình đăng nhập (mặc định `EXPO_PUBLIC_API_URL`, hoặc `http://10.0.2.2:8000` trên emulator Android):

- Emulator Android: `http://10.0.2.2:8000`
- Điện thoại thật (Expo Go): `http://<IP LAN máy chạy Backend>:8000`, cùng Wi‑Fi; Backend chạy `--host 0.0.0.0`.
- Bản build phát hành Android chặn HTTP thường; dùng HTTPS (proxy) hoặc bật `usesCleartextTraffic` khi build thử nghiệm.

## Ánh xạ chức năng

| Màn hình | API thật | Ghi chú / giới hạn |
|---|---|---|
| Đăng nhập | `POST /auth/login` | Vai trò OPERATOR/SUPERVISOR/ADMIN lấy từ token. Không có đăng ký/quên mật khẩu (Admin tạo tài khoản trên Backend) |
| Overview, Live Motion | `GET /devices`, `/devices/{id}/telemetry` | Biểu đồ = telemetry thật (cùng lần khởi động); chọn thiết bị mới nhất trên Backend |
| Alarms, Alarm Detail | `GET /alarms`, `POST /alarms/{id}/ack`, `PUT /alarms/{id}/label`, lệnh `mute_alarm` | ACK ≠ tắt cảnh báo cục bộ; MUTE bị khóa khi CRITICAL; **ghi chú cảnh báo chưa có API** nên không lưu; không có dạng sóng riêng theo cảnh báo |
| Control Center | `GET /commands`, `/devices/{id}/config`, `POST /devices/{id}/commands`, `PUT /config`, `POST /config/rollback` | Lệnh thật: `set_profile`, `calibrate_zero` (Supervisor+), `restart_device` (Admin), đổi mô hình chính qua cấu hình. **Không có** snapshot/timewarp/set_mode/set_scenario/test_timeout (chỉ MOCK) |
| Voyage Reports | `GET /voyages`, `/voyages/{id}/summary` | Chuyến đang chạy là số liệu tạm thời. RMS pitch, MAI max/avg, phút MAI>70 Backend không tổng hợp → `—`. **Tải CSV/PDF chưa hỗ trợ trên mobile** (cần header JWT) → dùng dashboard web |
| Replay | `GET /voyages/{id}/replay` | Trang đầu 2000 mẫu |
| Device Health | `GET /health/devices` | Không có RSSI, điểm sức khỏe, độ trễ hàng đợi → `—` |
| Model Monitor | `GET /monitor/agreement`, `/monitor/drift` | Đồng thuận bỏ UNKNOWN/FAULT; PSI Backend báo chưa khả dụng (chờ M2) |

Thông số kỹ thuật chưa có trong Backend (đóng kín, không bịa): ngưỡng cảnh báo roll "warning" riêng, tên/IMO tàu, snapshot 180s.
