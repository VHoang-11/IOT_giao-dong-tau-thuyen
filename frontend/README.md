# SVMG Frontend — React + Vite Dashboard

Dashboard web cho hệ thống Smart Vessel Motion Guard, hiển thị dữ liệu chuyển động tàu thuyền theo thời gian thực.

## Tech Stack

- **React 18** + **Vite** — UI framework & bundler
- **Recharts** — Biểu đồ time-series
- **Zustand** — State management
- **React Router** — Routing
- **Axios** — HTTP client
- **WebSocket** — Realtime data

## 9 Trang chính

| Trang | Route | Mô tả |
|-------|-------|-------|
| **Overview** | `/` | Tổng quan hệ thống: số tàu, trạng thái, cảnh báo mới nhất |
| **LiveMotion** | `/live` | Biểu đồ realtime roll/pitch, MAI, trạng thái cảnh báo |
| **Alarms** | `/alarms` | Danh sách cảnh báo, lọc/sắp xếp, acknowledge |
| **Control** | `/control` | Gửi lệnh đến thiết bị (reset, config, chuyển mode) |
| **Reports** | `/reports` | Báo cáo tổng hợp theo ngày/tuần/tháng |
| **Replay** | `/replay` | Phát lại dữ liệu lịch sử, chọn khoảng thời gian |
| **Health** | `/health` | Trạng thái sức khỏe hệ thống (DB, MQTT, uptime) |
| **Monitor** | `/monitor` | Giám sát mô hình ML: accuracy, drift, so sánh RF vs Baseline |
| **Fleet** | `/fleet` | Bản đồ đội tàu, trạng thái từng tàu |

## Cài đặt & Chạy

```bash
cd frontend

# Cài đặt dependencies
npm install

# Chạy development server
npm run dev
# → http://localhost:5173

# Build production
npm run build
```

## Kết nối Backend

- **REST API:** `http://localhost:8000/api/v1/`
- **WebSocket:** `ws://localhost:8000/ws/telemetry`
- Cấu hình trong `src/config.js` hoặc biến môi trường `VITE_API_URL`

## Mock API (Phát triển không cần backend)

Dùng **Prism** hoặc **MSW** để mock API từ file `openapi.yaml`:

```bash
# Prism mock server
npx @stoplight/prism-cli mock ../docs/api/openapi.yaml --port 4010

# Hoặc MSW (trong browser)
# Xem src/mocks/handlers.js
```
