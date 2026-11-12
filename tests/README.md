# SVMG Tests — Kế hoạch kiểm thử

Danh sách 16 thí nghiệm kiểm thử (T01–T16) cho hệ thống Smart Vessel Motion Guard.

## Tổng quan

| Mã | Tên | Mô tả | Thực hiện |
|----|-----|-------|-----------|
| **T01** | Unit Test — Filter | Kiểm tra bộ lọc bù: đầu vào sin → đầu ra đúng biên độ/pha | Host (gcc) |
| **T02** | Unit Test — Features | Kiểm tra trích xuất đặc trưng: dữ liệu biết trước → giá trị đúng | Host (gcc) |
| **T03** | Unit Test — MAI | Kiểm tra tính toán MAI: các tổ hợp đầu vào → MAI đúng | Host (gcc) |
| **T04** | Unit Test — Alarm FSM | Kiểm tra máy trạng thái cảnh báo: chuỗi sự kiện → chuyển trạng thái đúng | Host (gcc) |
| **T05** | Unit Test — Safety Envelope | Kiểm tra ngưỡng cứng: roll ≥ 20° liên tục ≥ 5s → CRITICAL | Host (gcc) |
| **T06** | Sim vs C Port | So sánh output Python generator vs C generator (≤ 1e-6) | Host (gcc + Python) |
| **T07** | Wokwi HIL — Sensor Mode | Chạy firmware trên Wokwi, chế độ SENSOR, kiểm tra LCD + MQTT | Wokwi |
| **T08** | Wokwi HIL — Simulation Mode | Chạy firmware trên Wokwi, chế độ SIMULATION, kiểm tra output | Wokwi |
| **T09** | ML Cross-validation | GroupKFold (k=5) trên dataset, báo cáo macro-F1 ≥ 0.90 | Python |
| **T10** | ML vs Baseline B | So sánh RF vs Baseline B trên cùng test set | Python |
| **T11** | Detection Latency | Đo thời gian phát hiện bất thường (mục tiêu ≤ 120s) | Python |
| **T12** | False Alarm Rate | Đo tỉ lệ false alarm trên dữ liệu S0/S0b (mục tiêu ≤ 2%) | Python |
| **T13** | MQTT End-to-End | mock_device → Mosquitto → backend → database — kiểm tra toàn bộ luồng | Docker |
| **T14** | API Integration | Kiểm tra tất cả endpoint REST API (CRUD, auth, WebSocket) | pytest + httpx |
| **T15** | Frontend E2E | Kiểm tra 9 trang dashboard (render, tương tác, dữ liệu) | Playwright |
| **T16** | Full System Demo | Demo 5 phút: khởi động hệ thống → tạo sự kiện → cảnh báo → acknowledge | Manual |

## Cách chạy

```bash
# Unit tests (T01–T05)
cd tests
gcc -I ../core/include -o test_core test_core.c ../core/src/*.c -lm
./test_core

# Sim comparison (T06)
python test_sim_comparison.py

# ML tests (T09–T12)
cd ml
python -m pytest tests/

# API tests (T14)
cd backend
python -m pytest tests/

# Frontend E2E (T15)
cd frontend
npx playwright test
```
