# 🚢 Smart Vessel Motion Guard (SVMG)

> **Hệ thống IoT giám sát, cảnh báo và quản lý sự kiện dao động tàu thuyền chở container**
>

## 🎯 Tổng quan

**Smart Vessel Motion Guard** là nguyên mẫu IoT + TinyML mô phỏng việc giám sát chuyển động của tàu container khi hành trình.

ESP32 thu nhận dữ liệu từ cảm biến **MPU6050** (hoặc bộ phát tín hiệu mô phỏng), lọc nhiễu, trích xuất đặc trưng theo cửa sổ thời gian và dùng mô hình **Random Forest** chạy trực tiếp trên thiết bị để nhận biết **4 mẫu chuyển động**:

| Mẫu | Mô tả |
|------|--------|
| `NORMAL` | Dao động bình thường |
| `HIGH_ROLL` | Dao động biên độ lớn |
| `PERSISTENT_OFFSET` | Nghiêng lệch kéo dài |
| `AMPLITUDE_GROWTH` | Dao động tăng biên độ dần (lắc tham số) |

### Vòng vận hành khép kín 6+1 nhóm chức năng:

1. **Giám sát thời gian thực** — Live Motion, đồ thị roll/pitch, MAI
2. **Cảnh báo có vòng đời** — ACK → leo thang → giải tỏa
3. **Điều khiển & cấu hình từ xa** — MQTT hai chiều, xác nhận lệnh
4. **Quản lý chuyến đi** — Báo cáo tự động PDF/CSV, phát lại (replay)
5. **Giám sát sức khỏe thiết bị** — RAM, nhiệt độ, I2C, hiệu chuẩn
6. **Giám sát mô hình ML** — Shadow mode, phát hiện lệch phân phối (drift)
7. **Mở rộng** — Bối cảnh biển (sea state), đội tàu ảo (fleet)

---

## 🏗 Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────────────┐
│                         KIẾN TRÚC 3 LỚP                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    MQTT     ┌──────────────┐   REST/WS   ┌──────┐│
│  │  ESP32       │◄──────────►│   Backend    │◄───────────►│ Web  ││
│  │  (Edge/IoT)  │   Broker   │  (FastAPI)   │             │ Dash ││
│  └─────────────┘             └──────┬───────┘             └──────┘│
│        │                            │                              │
│  MPU6050/Sim                  SQLite/PostgreSQL                     │
│  Lọc → Đặc trưng                                                  │
│  RF + Baseline B                                                   │
│  Cảnh báo cục bộ                                                   │
│  Bộ đệm offline                                                   │
│                                                                     │
│  ◄── Uplink: telemetry, event, status, health ──────────────────►  │
│  ◄── Downlink: cmd, cmd/ack, config ────────────────────────────►  │
└─────────────────────────────────────────────────────────────────────┘
```

### Luồng xử lý

- **Uplink**: `SENSOR/SIMULATION MODE` → `acquireMotionSample()` → lọc bù → giảm mẫu 20→2 Hz → cửa sổ (60s/180s) → RF + Baseline B + ngưỡng cứng → máy trạng thái cảnh báo → LCD/LED/buzzer + MQTT → Backend → DB → Dashboard
- **Downlink**: Dashboard → Backend (kiểm quyền) → MQTT cmd → ESP32 (kiểm an toàn) → APPLIED/REJECTED → cmd/ack → Backend cập nhật

---

## 🔧 Nhóm chức năng

### G1 – Giám sát thời gian thực (Must)
- Đọc MPU6050 hoặc bộ sinh mô phỏng
- Lọc bù, trích đặc trưng cửa sổ 60s/180s
- Suy luận RF trên ESP32, chỉ số MAI (0–100)
- Dashboard: đồ thị roll/pitch, nhãn phân loại

### G2 – Cảnh báo có vòng đời (Must)
- Máy trạng thái: `NORMAL → CAUTION → WARNING → CRITICAL`
- ACK, mute, leo thang tự động, giải tỏa
- Lớp ngưỡng cứng (|roll| ≥ 20° liên tục ≥ 5s → CRITICAL)
- MTTA, thống kê cảnh báo

### G3 – Điều khiển & cấu hình từ xa (Must)
- Lệnh: `set_profile`, `set_threshold`, `calibrate_zero`, `mute_alarm`, `start/stop_voyage`, `restart_device`
- ACK/NACK, idempotent (cmd_id), TTL, nhật ký kiểm toán
- Cấu hình có phiên bản, rollback

### G4 – Chuyến đi & báo cáo (Must/Should)
- Voyage: start → end → báo cáo tự động
- Xuất PDF/CSV, tính lại độc lập được
- Replay: phát lại với thanh thời gian ×1–×60
- Gắn nhãn cảnh báo (đúng/sai/chưa rõ)

### G5 – Sức khỏe thiết bị (Must)
- Free heap, uptime, sensor_ok, I2C status
- Hiệu chuẩn (calibrate_zero)

### G6 – Giám sát mô hình ML (Should/Could)
- Shadow mode: RF vs Baseline B chạy song song
- Model registry, PSI drift detection, Isolation Forest

### G7 – Bối cảnh biển & đội tàu (Could)
- Sea state từ Open-Meteo Marine API
- Fleet simulation: 3–5 tàu ảo, bản đồ Leaflet

---

## 💻 Công nghệ sử dụng

| Lớp | Công nghệ |
|-----|-----------|
| **Hardware/Simulation** | Wokwi, ESP32, MPU6050, LCD I2C 16×2, LED, Buzzer, 3 nút, chiết áp |
| **Firmware** | Arduino/ESP-IDF, C (lõi dùng chung), emlearn (Random Forest → C) |
| **Giao thức** | MQTT (QoS 1), WiFi, WebSocket |
| **Backend** | Python, FastAPI, SQLAlchemy, Paho MQTT |
| **Cơ sở dữ liệu** | SQLite (dev) → PostgreSQL (production) |
| **Frontend** | React, Vite, Recharts/Lightweight Charts, Leaflet |
| **ML** | scikit-learn (RandomForest), emlearn, Python |
| **Mô phỏng** | Python (bộ sinh dao động roll), xorshift32 |
| **Hạ tầng** | Docker Compose, Mosquitto (auth/ACL), GitHub Actions CI |
| **Báo cáo** | ReportLab/WeasyPrint (PDF), Telegram Bot API |

---

## 📁 Cấu trúc thư mục

```
smart-vessel-motion-guard/
├── contracts/              # Hợp đồng giao diện (MQTT schema, OpenAPI, header C)
│   ├── schemas/            # JSON Schema cho bản tin MQTT
│   ├── examples/           # Bản tin mẫu
│   ├── openapi.yaml        # API spec cho backend ↔ frontend
│   └── features.md         # Thứ tự & định nghĩa đặc trưng ML
│
├── core/                   # Lõi C dùng chung (ESP32 + máy chủ)
│   └── src/
│       ├── filter.c        # Bộ lọc bù, thông thấp, giảm mẫu
│       ├── features.c      # Trích đặc trưng cửa sổ
│       ├── baseline.c      # Baseline B
│       ├── safety.c        # Ngưỡng cứng (safety envelope)
│       ├── mai.c           # Motion Anomaly Index
│       ├── alarm_fsm.c     # Máy trạng thái cảnh báo
│       └── sim/            # Bộ sinh tín hiệu (C port)
│
├── firmware/               # Firmware ESP32 (Wokwi)
│   ├── wokwi/              # diagram.json, wokwi.toml
│   └── src/                # net.c, buffer.c, cmd.c, config.c, infer.c
│
├── simulation/             # Bộ sinh tín hiệu Python
│   ├── generator/          # Dao động tử roll, kịch bản S0–H1, G2
│   ├── mock_device.py      # Thiết bị giả phát MQTT
│   └── fleet_sim.py        # Đội tàu ảo (3–5 tàu)
│
├── ml/                     # Machine Learning
│   ├── data/               # Dataset 605 phiên, CSV + metadata
│   ├── train/              # Huấn luyện, GroupKFold
│   ├── eval/               # Đánh giá, confusion matrix, bootstrap
│   ├── export/             # model.h (emlearn)
│   ├── baselines/          # Baseline A/B params
│   ├── registry/           # Model registry (JSON)
│   ├── monitor/            # PSI, Isolation Forest, đồng thuận
│   └── features_c.py       # Python wrapper quanh lõi C (ctypes)
│
├── backend/                # Backend FastAPI
│   ├── ingest/             # MQTT consumer, JSON Schema validation, dedup
│   ├── alarms/             # Alarm service, FSM, MTTA, escalation
│   ├── commands/           # Command service, ACK lifecycle, audit log
│   ├── auth/               # JWT, RBAC (Operator/Supervisor/Admin)
│   ├── reports/            # Voyage, PDF/CSV generation
│   ├── replay/             # Replay API, annotation labels
│   ├── health/             # Device health API
│   ├── monitor/            # Model monitor integration
│   └── notify/             # Telegram/email webhook
│
├── frontend/               # Web Dashboard (React + Vite)
│   └── src/pages/
│       ├── Overview        # Tổng quan
│       ├── LiveMotion      # Đồ thị thời gian thực
│       ├── Alarms          # Quản lý cảnh báo
│       ├── Control         # Trung tâm điều khiển
│       ├── Reports         # Báo cáo chuyến đi
│       ├── Replay          # Phát lại & đánh giá
│       ├── Health          # Sức khỏe thiết bị
│       ├── Monitor         # Giám sát mô hình
│       └── Fleet           # Đội tàu (mở rộng)
│
├── tests/                  # T01–T16, kiểm thử
│   ├── firmware/
│   ├── backend/
│   └── e2e/
│
├── infra/                  # Docker, CI/CD
│   ├── docker-compose.yml
│   ├── mosquitto/          # Config, ACL, passwd
│   └── .env.example
│
├── docs/                   # Tài liệu
│   ├── report/             # Báo cáo cuối kỳ
│   └── demo.md             # Kịch bản demo
│
└── README.md               # File này
```

---

## 🚀 Hướng dẫn cài đặt & chạy

### Yêu cầu

- Python ≥ 3.10
- Node.js ≥ 18
- Docker & Docker Compose
- Wokwi CLI (tuỳ chọn, cho kiểm chứng chéo)

### 1. Clone & cài đặt

```bash
git clone https://github.com/<org>/smart-vessel-motion-guard.git
cd smart-vessel-motion-guard
cp infra/.env.example infra/.env
# Chỉnh sửa biến môi trường trong .env
```

### 2. Khởi chạy hạ tầng

```bash
cd infra
docker-compose up -d   # Mosquitto + PostgreSQL
```

### 3. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

### 5. Thiết bị mô phỏng

- Mở project trên [Wokwi](https://wokwi.com) hoặc dùng mock device:
```bash
cd simulation
python mock_device.py   # Phát bản tin MQTT giả lập
```

---

## 📡 Giao thức MQTT

Tiền tố topic: `svmg/{device_id}/`

| Topic | Hướng | QoS | Mô tả |
|-------|-------|-----|--------|
| `svmg/{id}/telemetry` | Uplink | 0 | Dữ liệu roll, pitch, MAI, nhãn phân loại |
| `svmg/{id}/event` | Uplink | 1 | Sự kiện cảnh báo (alarm_id, level, class) |
| `svmg/{id}/status` | Uplink | 1 | Trạng thái online/offline (retained + LWT) |
| `svmg/{id}/health` | Uplink | 0 | Sức khỏe thiết bị |
| `svmg/{id}/cmd` | Downlink | 1 | Lệnh điều khiển |
| `svmg/{id}/cmd/ack` | Uplink | 1 | Xác nhận lệnh (APPLIED/REJECTED) |
| `svmg/{id}/config` | Downlink | 1 | Cấu hình (retained, có phiên bản) |

### Mẫu bản tin Telemetry

```json
{
  "device_id": "vessel-demo-01", "boot_id": "a3f9", "seq": 125,
  "t_sim_s": 625.0, "uptime_ms": 62500, "timewarp": 10,
  "source_mode": "SIMULATION", "synthetic": true,
  "scenario_id": "S3", "voyage_id": "V-2026-001",
  "roll_deg": 8.4, "pitch_deg": 1.2,
  "rms_roll_deg": 5.6, "heel_offset_deg": 0.4, "trend_rms_deg_per_min": 1.1,
  "class_rf": "AMPLITUDE_GROWTH", "class_baseline_b": "AMPLITUDE_GROWTH",
  "mai": 64, "alarm_level": "WARNING",
  "model_version": "rf_v1", "config_version": 7, "sensor_ok": true
}
```

---

## 👥 Phân công nhóm

| Vai trò | Thư mục sở hữu | SP | Trách nhiệm chính |
|---------|----------------|----|--------------------|
| **M1** – Embedded / Lõi C | `core/`, `firmware/` | 40 | Mạch Wokwi, lọc/đặc trưng, ngưỡng cứng, MAI, FSM cảnh báo, MQTT, lệnh/cấu hình, bộ đệm offline |
| **M2** – Mô phỏng / ML | `simulation/`, `ml/`, `core/src/sim/` | 40 | Bộ sinh tín hiệu, 605 phiên dữ liệu, Random Forest, baseline, đánh giá, giám sát mô hình, fleet_sim |
| **M3** – Backend / Dữ liệu | `backend/` | 40 | MQTT ingest, CSDL, vòng đời cảnh báo, kênh lệnh, phân quyền, chuyến đi & báo cáo, replay, thông báo |
| **M4** – Frontend / Hạ tầng / QA | `frontend/`, `infra/`, `tests/e2e/`, `docs/` | 40 | Dashboard 9 trang, Docker/CI, kiểm thử E2E, tích hợp, demo, ghép báo cáo |

---

## 🧪 Thí nghiệm & Đánh giá

| Mã | Thí nghiệm | Chủ trì |
|----|------------|---------|
| T01 | MPU6050 ở SENSOR MODE | M1 |
| T02 | Chạy kịch bản S0–S3, S0b, H1 | M2 |
| T03 | Python ↔ C ↔ ESP32 cross-check | M2 |
| T04 | ML vs Baseline A/B trên Test-G1/G2 | M2 |
| T05 | Ngắt MQTT lúc có bất thường | M1 |
| T06 | Phục hồi mạng, đồng bộ | M3 |
| T09 | Vòng đời cảnh báo | M3 |
| T10 | Kênh lệnh: RTT, mất gói, an toàn | M3 |
| T11 | Độ chính xác báo cáo (tính lại độc lập) | M4 |
| T14 | Đội tàu, chịu tải | M3 |
| T15 | Replay khớp dữ liệu gốc | M4 |

### Chỉ số đánh giá chính

- **ML**: macro-F1, precision/recall theo lớp, cảnh báo giả/giờ, độ trễ phát hiện, bootstrap CI
- **Vận hành**: MTTA, tỉ lệ leo thang, RTT lệnh, tỉ lệ bản tin nhận, tỉ lệ trùng khớp báo cáo

---

## ⚠️ Giới hạn & Lưu ý

> **Đây là nguyên mẫu nghiên cứu/đào tạo, KHÔNG phải sản phẩm an toàn hàng hải.**

- Dữ liệu hoàn toàn là **mô phỏng** (synthetic), dựa trên mô hình dao động roll đơn giản hóa
- Kết quả tốt trên dữ liệu tổng hợp **không tự động suy rộng** sang tàu container thực tế
- Các ngưỡng (φ_hard = 20°, MAI thresholds...) chỉ là **tham số demo**
- Không gọi kết quả là "dự báo lật tàu" hay "đánh giá GM/GZ"
- Không tự nhận giảm CO₂ hay ngăn container rơi từ kết quả mô phỏng
- Mọi dữ liệu và đồ thị phải gắn cờ `SENSOR` hoặc `SIMULATION`

---



## 📄 Giấy phép

Đồ án cuối kỳ – Môn Internet of Things (IoT). Chỉ dùng cho mục đích học thuật.

[![Môn học](https://img.shields.io/badge/Môn%20học-Internet%20of%20Things-blue)]()
[![Phiên bản](https://img.shields.io/badge/Đề%20cương-v2.0-green)]()
[![ESP32](https://img.shields.io/badge/MCU-ESP32-orange)]()
[![License](https://img.shields.io/badge/License-Academic-lightgrey)]()

---

## 📋 Mục lục

- [Tổng quan](#-tổng-quan)
- [Kiến trúc hệ thống](#-kiến-trúc-hệ-thống)
- [Nhóm chức năng](#-nhóm-chức-năng)
- [Công nghệ sử dụng](#-công-nghệ-sử-dụng)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [Hướng dẫn cài đặt & chạy](#-hướng-dẫn-cài-đặt--chạy)
- [Giao thức MQTT](#-giao-thức-mqtt)
- [Phân công nhóm](#-phân-công-nhóm)
- [Thí nghiệm & Đánh giá](#-thí-nghiệm--đánh-giá)
- [Giới hạn & Lưu ý](#-giới-hạn--lưu-ý)
- [Tài liệu tham khảo](#-tài-liệu-tham-khảo)

---

## 🎯 Tổng quan

**Smart Vessel Motion Guard** là nguyên mẫu IoT + TinyML mô phỏng việc giám sát chuyển động của tàu container khi hành trình.

ESP32 thu nhận dữ liệu từ cảm biến **MPU6050** (hoặc bộ phát tín hiệu mô phỏng), lọc nhiễu, trích xuất đặc trưng theo cửa sổ thời gian và dùng mô hình **Random Forest** chạy trực tiếp trên thiết bị để nhận biết **4 mẫu chuyển động**:

| Mẫu | Mô tả |
|------|--------|
| `NORMAL` | Dao động bình thường |
| `HIGH_ROLL` | Dao động biên độ lớn |
| `PERSISTENT_OFFSET` | Nghiêng lệch kéo dài |
| `AMPLITUDE_GROWTH` | Dao động tăng biên độ dần (lắc tham số) |

### Vòng vận hành khép kín 6+1 nhóm chức năng:

1. **Giám sát thời gian thực** — Live Motion, đồ thị roll/pitch, MAI
2. **Cảnh báo có vòng đời** — ACK → leo thang → giải tỏa
3. **Điều khiển & cấu hình từ xa** — MQTT hai chiều, xác nhận lệnh
4. **Quản lý chuyến đi** — Báo cáo tự động PDF/CSV, phát lại (replay)
5. **Giám sát sức khỏe thiết bị** — RAM, nhiệt độ, I2C, hiệu chuẩn
6. **Giám sát mô hình ML** — Shadow mode, phát hiện lệch phân phối (drift)
7. **Mở rộng** — Bối cảnh biển (sea state), đội tàu ảo (fleet)

---

## 🏗 Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────────────┐
│                         KIẾN TRÚC 3 LỚP                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    MQTT     ┌──────────────┐   REST/WS   ┌──────┐│
│  │  ESP32       │◄──────────►│   Backend    │◄───────────►│ Web  ││
│  │  (Edge/IoT)  │   Broker   │  (FastAPI)   │             │ Dash ││
│  └─────────────┘             └──────┬───────┘             └──────┘│
│        │                            │                              │
│  MPU6050/Sim                  SQLite/PostgreSQL                     │
│  Lọc → Đặc trưng                                                  │
│  RF + Baseline B                                                   │
│  Cảnh báo cục bộ                                                   │
│  Bộ đệm offline                                                   │
│                                                                     │
│  ◄── Uplink: telemetry, event, status, health ──────────────────►  │
│  ◄── Downlink: cmd, cmd/ack, config ────────────────────────────►  │
└─────────────────────────────────────────────────────────────────────┘
```

### Luồng xử lý

- **Uplink**: `SENSOR/SIMULATION MODE` → `acquireMotionSample()` → lọc bù → giảm mẫu 20→2 Hz → cửa sổ (60s/180s) → RF + Baseline B + ngưỡng cứng → máy trạng thái cảnh báo → LCD/LED/buzzer + MQTT → Backend → DB → Dashboard
- **Downlink**: Dashboard → Backend (kiểm quyền) → MQTT cmd → ESP32 (kiểm an toàn) → APPLIED/REJECTED → cmd/ack → Backend cập nhật

---

## 🔧 Nhóm chức năng

### G1 – Giám sát thời gian thực (Must)
- Đọc MPU6050 hoặc bộ sinh mô phỏng
- Lọc bù, trích đặc trưng cửa sổ 60s/180s
- Suy luận RF trên ESP32, chỉ số MAI (0–100)
- Dashboard: đồ thị roll/pitch, nhãn phân loại

### G2 – Cảnh báo có vòng đời (Must)
- Máy trạng thái: `NORMAL → CAUTION → WARNING → CRITICAL`
- ACK, mute, leo thang tự động, giải tỏa
- Lớp ngưỡng cứng (|roll| ≥ 20° liên tục ≥ 5s → CRITICAL)
- MTTA, thống kê cảnh báo

### G3 – Điều khiển & cấu hình từ xa (Must)
- Lệnh: `set_profile`, `set_threshold`, `calibrate_zero`, `mute_alarm`, `start/stop_voyage`, `restart_device`
- ACK/NACK, idempotent (cmd_id), TTL, nhật ký kiểm toán
- Cấu hình có phiên bản, rollback

### G4 – Chuyến đi & báo cáo (Must/Should)
- Voyage: start → end → báo cáo tự động
- Xuất PDF/CSV, tính lại độc lập được
- Replay: phát lại với thanh thời gian ×1–×60
- Gắn nhãn cảnh báo (đúng/sai/chưa rõ)

### G5 – Sức khỏe thiết bị (Must)
- Free heap, uptime, sensor_ok, I2C status
- Hiệu chuẩn (calibrate_zero)

### G6 – Giám sát mô hình ML (Should/Could)
- Shadow mode: RF vs Baseline B chạy song song
- Model registry, PSI drift detection, Isolation Forest

### G7 – Bối cảnh biển & đội tàu (Could)
- Sea state từ Open-Meteo Marine API
- Fleet simulation: 3–5 tàu ảo, bản đồ Leaflet

---

## 💻 Công nghệ sử dụng

| Lớp | Công nghệ |
|-----|-----------|
| **Hardware/Simulation** | Wokwi, ESP32, MPU6050, LCD I2C 16×2, LED, Buzzer, 3 nút, chiết áp |
| **Firmware** | Arduino/ESP-IDF, C (lõi dùng chung), emlearn (Random Forest → C) |
| **Giao thức** | MQTT (QoS 1), WiFi, WebSocket |
| **Backend** | Python, FastAPI, SQLAlchemy, Paho MQTT |
| **Cơ sở dữ liệu** | SQLite (dev) → PostgreSQL (production) |
| **Frontend** | React, Vite, Recharts/Lightweight Charts, Leaflet |
| **ML** | scikit-learn (RandomForest), emlearn, Python |
| **Mô phỏng** | Python (bộ sinh dao động roll), xorshift32 |
| **Hạ tầng** | Docker Compose, Mosquitto (auth/ACL), GitHub Actions CI |
| **Báo cáo** | ReportLab/WeasyPrint (PDF), Telegram Bot API |

---

## 📁 Cấu trúc thư mục

```
smart-vessel-motion-guard/
├── contracts/              # Hợp đồng giao diện (MQTT schema, OpenAPI, header C)
│   ├── schemas/            # JSON Schema cho bản tin MQTT
│   ├── examples/           # Bản tin mẫu
│   ├── openapi.yaml        # API spec cho backend ↔ frontend
│   └── features.md         # Thứ tự & định nghĩa đặc trưng ML
│
├── core/                   # Lõi C dùng chung (ESP32 + máy chủ)
│   └── src/
│       ├── filter.c        # Bộ lọc bù, thông thấp, giảm mẫu
│       ├── features.c      # Trích đặc trưng cửa sổ
│       ├── baseline.c      # Baseline B
│       ├── safety.c        # Ngưỡng cứng (safety envelope)
│       ├── mai.c           # Motion Anomaly Index
│       ├── alarm_fsm.c     # Máy trạng thái cảnh báo
│       └── sim/            # Bộ sinh tín hiệu (C port)
│
├── firmware/               # Firmware ESP32 (Wokwi)
│   ├── wokwi/              # diagram.json, wokwi.toml
│   └── src/                # net.c, buffer.c, cmd.c, config.c, infer.c
│
├── simulation/             # Bộ sinh tín hiệu Python
│   ├── generator/          # Dao động tử roll, kịch bản S0–H1, G2
│   ├── mock_device.py      # Thiết bị giả phát MQTT
│   └── fleet_sim.py        # Đội tàu ảo (3–5 tàu)
│
├── ml/                     # Machine Learning
│   ├── data/               # Dataset 605 phiên, CSV + metadata
│   ├── train/              # Huấn luyện, GroupKFold
│   ├── eval/               # Đánh giá, confusion matrix, bootstrap
│   ├── export/             # model.h (emlearn)
│   ├── baselines/          # Baseline A/B params
│   ├── registry/           # Model registry (JSON)
│   ├── monitor/            # PSI, Isolation Forest, đồng thuận
│   └── features_c.py       # Python wrapper quanh lõi C (ctypes)
│
├── backend/                # Backend FastAPI
│   ├── ingest/             # MQTT consumer, JSON Schema validation, dedup
│   ├── alarms/             # Alarm service, FSM, MTTA, escalation
│   ├── commands/           # Command service, ACK lifecycle, audit log
│   ├── auth/               # JWT, RBAC (Operator/Supervisor/Admin)
│   ├── reports/            # Voyage, PDF/CSV generation
│   ├── replay/             # Replay API, annotation labels
│   ├── health/             # Device health API
│   ├── monitor/            # Model monitor integration
│   └── notify/             # Telegram/email webhook
│
├── frontend/               # Web Dashboard (React + Vite)
│   └── src/pages/
│       ├── Overview        # Tổng quan
│       ├── LiveMotion      # Đồ thị thời gian thực
│       ├── Alarms          # Quản lý cảnh báo
│       ├── Control         # Trung tâm điều khiển
│       ├── Reports         # Báo cáo chuyến đi
│       ├── Replay          # Phát lại & đánh giá
│       ├── Health          # Sức khỏe thiết bị
│       ├── Monitor         # Giám sát mô hình
│       └── Fleet           # Đội tàu (mở rộng)
│
├── tests/                  # T01–T16, kiểm thử
│   ├── firmware/
│   ├── backend/
│   └── e2e/
│
├── infra/                  # Docker, CI/CD
│   ├── docker-compose.yml
│   ├── mosquitto/          # Config, ACL, passwd
│   └── .env.example
│
├── docs/                   # Tài liệu
│   ├── report/             # Báo cáo cuối kỳ
│   └── demo.md             # Kịch bản demo
│
└── README.md               # File này
```

---

## 🚀 Hướng dẫn cài đặt & chạy

### Yêu cầu

- Python ≥ 3.10
- Node.js ≥ 18
- Docker & Docker Compose
- Wokwi CLI (tuỳ chọn, cho kiểm chứng chéo)

### 1. Clone & cài đặt

```bash
git clone https://github.com/<org>/smart-vessel-motion-guard.git
cd smart-vessel-motion-guard
cp infra/.env.example infra/.env
# Chỉnh sửa biến môi trường trong .env
```

### 2. Khởi chạy hạ tầng

```bash
cd infra
docker-compose up -d   # Mosquitto + PostgreSQL
```

### 3. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

### 5. Thiết bị mô phỏng

- Mở project trên [Wokwi](https://wokwi.com) hoặc dùng mock device:
```bash
cd simulation
python mock_device.py   # Phát bản tin MQTT giả lập
```

---

## 📡 Giao thức MQTT

Tiền tố topic: `svmg/{device_id}/`

| Topic | Hướng | QoS | Mô tả |
|-------|-------|-----|--------|
| `svmg/{id}/telemetry` | Uplink | 0 | Dữ liệu roll, pitch, MAI, nhãn phân loại |
| `svmg/{id}/event` | Uplink | 1 | Sự kiện cảnh báo (alarm_id, level, class) |
| `svmg/{id}/status` | Uplink | 1 | Trạng thái online/offline (retained + LWT) |
| `svmg/{id}/health` | Uplink | 0 | Sức khỏe thiết bị |
| `svmg/{id}/cmd` | Downlink | 1 | Lệnh điều khiển |
| `svmg/{id}/cmd/ack` | Uplink | 1 | Xác nhận lệnh (APPLIED/REJECTED) |
| `svmg/{id}/config` | Downlink | 1 | Cấu hình (retained, có phiên bản) |

### Mẫu bản tin Telemetry

```json
{
  "device_id": "vessel-demo-01", "boot_id": "a3f9", "seq": 125,
  "t_sim_s": 625.0, "uptime_ms": 62500, "timewarp": 10,
  "source_mode": "SIMULATION", "synthetic": true,
  "scenario_id": "S3", "voyage_id": "V-2026-001",
  "roll_deg": 8.4, "pitch_deg": 1.2,
  "rms_roll_deg": 5.6, "heel_offset_deg": 0.4, "trend_rms_deg_per_min": 1.1,
  "class_rf": "AMPLITUDE_GROWTH", "class_baseline_b": "AMPLITUDE_GROWTH",
  "mai": 64, "alarm_level": "WARNING",
  "model_version": "rf_v1", "config_version": 7, "sensor_ok": true
}
```

---

## 👥 Phân công nhóm

| Vai trò | Thư mục sở hữu | SP | Trách nhiệm chính |
|---------|----------------|----|--------------------|
| **M1** – Embedded / Lõi C | `core/`, `firmware/` | 40 | Mạch Wokwi, lọc/đặc trưng, ngưỡng cứng, MAI, FSM cảnh báo, MQTT, lệnh/cấu hình, bộ đệm offline |
| **M2** – Mô phỏng / ML | `simulation/`, `ml/`, `core/src/sim/` | 40 | Bộ sinh tín hiệu, 605 phiên dữ liệu, Random Forest, baseline, đánh giá, giám sát mô hình, fleet_sim |
| **M3** – Backend / Dữ liệu | `backend/` | 40 | MQTT ingest, CSDL, vòng đời cảnh báo, kênh lệnh, phân quyền, chuyến đi & báo cáo, replay, thông báo |
| **M4** – Frontend / Hạ tầng / QA | `frontend/`, `infra/`, `tests/e2e/`, `docs/` | 40 | Dashboard 9 trang, Docker/CI, kiểm thử E2E, tích hợp, demo, ghép báo cáo |

---

## 🧪 Thí nghiệm & Đánh giá

| Mã | Thí nghiệm | Chủ trì |
|----|------------|---------|
| T01 | MPU6050 ở SENSOR MODE | M1 |
| T02 | Chạy kịch bản S0–S3, S0b, H1 | M2 |
| T03 | Python ↔ C ↔ ESP32 cross-check | M2 |
| T04 | ML vs Baseline A/B trên Test-G1/G2 | M2 |
| T05 | Ngắt MQTT lúc có bất thường | M1 |
| T06 | Phục hồi mạng, đồng bộ | M3 |
| T09 | Vòng đời cảnh báo | M3 |
| T10 | Kênh lệnh: RTT, mất gói, an toàn | M3 |
| T11 | Độ chính xác báo cáo (tính lại độc lập) | M4 |
| T14 | Đội tàu, chịu tải | M3 |
| T15 | Replay khớp dữ liệu gốc | M4 |

### Chỉ số đánh giá chính

- **ML**: macro-F1, precision/recall theo lớp, cảnh báo giả/giờ, độ trễ phát hiện, bootstrap CI
- **Vận hành**: MTTA, tỉ lệ leo thang, RTT lệnh, tỉ lệ bản tin nhận, tỉ lệ trùng khớp báo cáo

---

## ⚠️ Giới hạn & Lưu ý

> **Đây là nguyên mẫu nghiên cứu/đào tạo, KHÔNG phải sản phẩm an toàn hàng hải.**

- Dữ liệu hoàn toàn là **mô phỏng** (synthetic), dựa trên mô hình dao động roll đơn giản hóa
- Kết quả tốt trên dữ liệu tổng hợp **không tự động suy rộng** sang tàu container thực tế
- Các ngưỡng (φ_hard = 20°, MAI thresholds...) chỉ là **tham số demo**
- Không gọi kết quả là "dự báo lật tàu" hay "đánh giá GM/GZ"
- Không tự nhận giảm CO₂ hay ngăn container rơi từ kết quả mô phỏng
- Mọi dữ liệu và đồ thị phải gắn cờ `SENSOR` hoặc `SIMULATION`

---

## 📚 Tài liệu tham khảo

1. World Shipping Council, "Containers Lost at Sea – 2026 Update"
2. IMO, "Marine litter" (báo cáo bắt buộc container thất lạc, hiệu lực 01/01/2026)
3. Wokwi Docs, "wokwi-mpu6050"
4. Wokwi Docs, "ESP32 WiFi Networking"
5. emlearn Documentation
6. IMO, "Ship Design and Stability"
7. Wokwi Docs, "Automation Scenarios"
8-9. Wokwi Docs, "Wokwi for CI" & "CLI Usage"
10. Adafruit MPU6050 Library
11-13. Tài liệu về lắc tham số và sự cố container
14. Open-Meteo Marine Weather API
15. IIMS/WSC report 2025

---

## 📄 Giấy phép

Đồ án cuối kỳ – Môn Internet of Things (IoT). Chỉ dùng cho mục đích học thuật.
