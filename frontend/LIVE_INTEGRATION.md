# Dashboard SVMG thống nhất MOCK / LIVE

Một giao diện, hai nguồn dữ liệu. Sidebar, topbar, theme, điều hướng, thành phần (`Panel`, `Metric`, `Pill`, `Button` trong `src/ui.tsx`)
và CSS dùng chung. Chọn chế độ ở màn hình đăng nhập:

- **MOCK:** giữ nguyên `mock.ts`, tài khoản demo, kịch bản S0–H1 (không gọi Backend).
- **LIVE:** đăng nhập JWT `POST /api/v1/auth/login`; dữ liệu thật ESP32/Wokwi → MQTT → FastAPI → SQLite. JWT chỉ nằm trong React state
  (không localStorage, không log). Khi API lỗi **không** thay bằng MOCK; HTTP 401 → đăng xuất kèm thông báo hết phiên.

## Kiến trúc

| Tệp | Vai trò |
|---|---|
| `src/App.tsx` | Khung chung; `renderPage()` chuyển sang `LivePage` khi LIVE (trừ trang "Thêm"). Topbar/disclaimer hiển thị trạng thái LIVE |
| `src/api.ts` | Client REST: kiểu dữ liệu đúng OpenAPI (đã đối chiếu tự động 22 lời gọi + 16 schema), `ApiError` giữ mã HTTP, tải CSV/PDF có JWT |
| `src/live/useLive.ts` | Polling GET (telemetry/cảnh báo 5 s, thống kê/health 10 s, thiết bị 30 s) và phân loại kết nối |
| `src/live/LivePages.tsx` | 8 màn hình LIVE dựng từ cùng thành phần/CSS với MOCK |
| `vite.config.ts` | Dev proxy `/api` → `SVMG_API_TARGET` (mặc định `http://localhost:8000`), giống Nginx trong Docker |

**Trạng thái kết nối** (topbar và mỗi màn hình): `MẤT KẾT NỐI BACKEND` (API lỗi) · `CHƯA CÓ TELEMETRY` · `THIẾT BỊ OFFLINE / DỮ LIỆU CŨ`
(mẫu mới nhất cũ hơn max(30 s, 3 × chu kỳ gửi quan sát được) hoặc Backend báo `stale`) · `LỖI CẢM BIẾN` (dữ liệu mới nhưng
`sensor_ok=false`) · `TRỰC TUYẾN`. Khi không trực tuyến, góc/MAI hiển thị `—` và ghi rõ thời điểm mẫu cuối, không coi là thời gian thực.

## Ma trận chức năng 8 màn hình (LIVE)

| Màn hình | API thật | Trạng thái | Chưa khả dụng / giới hạn |
|---|---|---|---|
| Tổng quan vận hành | `devices`, `devices/{id}/telemetry`, `alarms`, `alarms/stats`, `health/devices` | Hoàn thành | Chọn thiết bị khi có > 1 |
| Giám sát chuyển động | telemetry (120 mẫu, cùng boot) | Hoàn thành: góc, mô hình tàu 3D, biểu đồ Roll/Pitch, xu hướng MAI thật | Đồng thuận RF/Baseline B: RF = UNKNOWN |
| Cảnh báo và ACK | `alarms`, `alarms/stats`, `POST alarms/{pk}/ack`, `PUT alarms/{pk}/label`, lệnh `mute_alarm` | Hoàn thành, có hộp xác nhận | ACK không tắt cảnh báo cục bộ; MUTE bị khóa khi NGUY CẤP; gán nhãn chỉ Supervisor/Admin |
| Trung tâm điều khiển | `commands`, `commands/stats`, `devices/{id}/config`, `POST devices/{id}/commands` | Một phần | Chỉ lệnh firmware chính hỗ trợ: `set_profile`, `set_threshold`, `calibrate_zero` (Supervisor+), `restart_device` (Admin). `set_scenario/mode/timewarp/request_snapshot/set_model` chỉ có ở firmware kiểm thử → **Chưa khả dụng**; rollback cấu hình chưa đưa lên UI |
| Báo cáo hành trình | `voyages`, `voyages/{id}/summary`, CSV/PDF, `POST voyages`, `POST voyages/{id}/end` | Hoàn thành | Báo cáo chuyến đang chạy là tạm thời; bắt đầu/kết thúc chuyến chỉ Supervisor+ và chỉ ghi Backend |
| Phát lại và đánh giá | `voyages/{id}/replay?limit=2000` | Hoàn thành: biểu đồ, vạch sự kiện cảnh báo, thanh trượt, phát/tạm dừng | Trang đầu 2000 mẫu (chưa phân trang `next_cursor`) |
| Tình trạng thiết bị | `health/devices`, `devices/{id}/health` | Hoàn thành | Health gửi định kỳ (không theo từng telemetry); `inference_ms` có thể trống |
| Giám sát mô hình AI | `monitor/agreement`, `monitor/drift`, telemetry | Hoàn thành (chỉ Supervisor/Admin, như MOCK) | Đồng thuận chỉ tính cặp mà cả RF và Baseline B có lớp phân loại; UNKNOWN/FAULT bị loại (UNKNOWN == UNKNOWN không phải đồng thuận); SENSOR/SIMULATION không gộp. Firmware chính trả `class_rf=UNKNOWN` → hiển thị "Chưa đủ dữ liệu để đánh giá đồng thuận"; drift PSI Backend báo `available=false` |

## Multi-Node: hầm hàng (Cargo Node)

Mực nước, nhiệt độ, độ ẩm hầm hàng đến từ **Cargo Node** (ESP32 thứ 2), không còn đi cùng telemetry của tàu. LIVE gọi `GET /api/v1/devices/{tàu}/cargo` (5 s) và hiển thị trên **Tổng quan** và **Giám sát chuyển động** kèm trạng thái kết nối **riêng** của Node 2
(`CHƯA GẮN CARGO NODE` · `CHƯA CÓ DỮ LIỆU HẦM HÀNG` · `CARGO NODE OFFLINE / DỮ LIỆU CŨ` · `LỖI DHT22` · `CARGO NODE TRỰC TUYẾN`). Cargo Node không bao giờ được chọn làm "tàu chính".
Admin phải gắn Cargo Node vào tàu (`PATCH /devices/{id}` với `parent_device_id`) thì dữ liệu mới xuất hiện. Chưa có cảnh báo hầm hàng (chờ ngưỡng).

Không có trong Backend nên LIVE không hiển thị (MOCK vẫn có): đăng ký/quên mật khẩu, snapshot 180 s, chọn kịch bản/timewarp/mô hình từ xa,
thông tin tĩnh của tàu (IMO, tên tàu).

## Chạy

```bash
# Docker (Nginx proxy /api): build lại frontend để dùng mã mới
docker compose -f infra/docker-compose.yml up -d --build frontend
# hoặc dev
cd frontend && npm install && npm run dev          # /api → http://localhost:8000 (đổi bằng SVMG_API_TARGET)
```

## Kiểm thử đã chạy (2026-11-26)

- `npm run build` (tsc strict + vite): thành công. `dist/` gitignored.
- Đối chiếu tự động với `/openapi.json` của Backend đang chạy: 22/22 lời gọi (path, method, query) và 16/16 interface khớp schema.
- Dev proxy: `/api/v1/devices` không token → 401 (đúng yêu cầu xác thực), `/healthz` → 200.
- **Chưa** đăng nhập LIVE trong lần kiểm thử này (chưa có tài khoản thử; `ADMIN_PASSWORD` trong `infra/.env` trống): cần kiểm tra bằng
  trình duyệt với tài khoản thật. Không gửi lệnh, không ACK, không đổi chuyến đi, không reset SQLite khi kiểm thử.
- `LiveDashboard.tsx`, `LiveTelemetryChart.tsx` (trang LIVE đơn giản cũ) giữ nguyên nhưng không còn được `App.tsx` dùng.
