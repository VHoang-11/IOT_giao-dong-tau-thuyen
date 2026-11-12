# SVMG Docs — Tài liệu dự án

Thư mục tài liệu cho hệ thống Smart Vessel Motion Guard.

## Cấu trúc thư mục

```
docs/
├── report/        # Báo cáo đồ án, báo cáo thí nghiệm
│   ├── chapters/  # Các chương báo cáo (LaTeX/Markdown)
│   └── figures/   # Hình ảnh cho báo cáo
├── diagrams/      # Sơ đồ kiến trúc, luồng dữ liệu, FSM
│   ├── architecture.drawio
│   ├── data_flow.drawio
│   └── alarm_fsm.drawio
├── api/           # Tài liệu API
│   ├── openapi.yaml     # OpenAPI 3.0 specification
│   └── mqtt_topics.md   # Mô tả các MQTT topics
└── README.md
```

## Mô tả

### `report/`
Chứa báo cáo đồ án cuối kỳ và báo cáo thí nghiệm:
- Báo cáo chính (LaTeX hoặc Markdown)
- Hình ảnh, biểu đồ, bảng kết quả
- Tài liệu tham khảo

### `diagrams/`
Sơ đồ thiết kế hệ thống:
- Kiến trúc tổng thể (ESP32 ↔ MQTT ↔ Backend ↔ Frontend)
- Luồng dữ liệu (telemetry pipeline)
- Máy trạng thái cảnh báo (Alarm FSM)
- Sơ đồ lớp và mô-đun

### `api/`
Tài liệu API:
- **openapi.yaml** — Đặc tả OpenAPI 3.0 cho REST API
- **mqtt_topics.md** — Mô tả cấu trúc topic MQTT, payload JSON, QoS
