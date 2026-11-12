# SVMG Simulation — Bộ sinh tín hiệu Python

Bộ sinh tín hiệu mô phỏng chuyển động tàu thuyền dựa trên mô hình dao động tử roll bậc 2, dùng để tạo dataset huấn luyện và kiểm thử.

## Mô hình vật lý

Phương trình dao động tử roll:

```
d²φ/dt² + 2ζω₀·dφ/dt + ω₀²·[1 + h·cos(Ωt)]·φ + ω₀²·κ·φ³ = ω₀²·[b + w(t)]
```

Trong đó:
- `φ` — góc roll (rad)
- `ζ` — hệ số tắt dần
- `ω₀ = 2π/T₀` — tần số tự nhiên
- `h` — biên độ kích thích tham số (Mathieu)
- `κ` — hệ số phi tuyến bậc 3
- `b` — heel offset (nghiêng tĩnh)
- `w(t)` — kích động sóng ngẫu nhiên

## Kịch bản (Scenarios)

| Mã | Tên | Mô tả |
|----|-----|-------|
| **S0** | Biển lặng | σ_w nhỏ, không offset, không tham số |
| **S0b** | Neo cảng | σ_w rất nhỏ, có offset nhẹ |
| **S1** | Sóng vừa, lắc mạnh | σ_w tăng → HIGH_ROLL |
| **S2** | Nghiêng lệch bền | b > 0, heel kéo dài → PERSISTENT_OFFSET |
| **S3** | Cộng hưởng tham số | h > 0, biên độ tăng dần → AMPLITUDE_GROWTH |
| **H1** | Cảm biến lỗi | NaN / spike / stuck-at → FAULT |

## Bộ sinh (Generators)

### G1 — Correlated Noise (mặc định)
- Nhiễu trắng Gaussian lọc qua bộ lọc thông thấp bậc 1
- Phù hợp cho mô phỏng nhanh

### G2 — JONSWAP Sum-of-Sines
- Phổ JONSWAP → tổng hợp sóng sin với pha ngẫu nhiên
- Chính xác hơn về mặt vật lý

## Scripts chính

| File | Mô tả |
|------|-------|
| `generator.py` | Bộ sinh tín hiệu cốt lõi (lớp `RollOscillator`) |
| `scenarios.py` | Định nghĩa tham số cho các kịch bản S0–H1 |
| `mock_device.py` | Mô phỏng 1 thiết bị ESP32: sinh tín hiệu → publish MQTT |
| `fleet_sim.py` | Mô phỏng đội tàu (nhiều thiết bị đồng thời) |
| `gen_dataset.py` | Sinh dataset CSV/Parquet cho huấn luyện ML |

## Sinh dataset

```bash
cd simulation

# Cài đặt dependencies
pip install -r requirements.txt

# Sinh dataset cho tất cả kịch bản
python gen_dataset.py --scenarios S0,S0b,S1,S2,S3,H1 \
    --sessions 50 --duration 600 --output ../data/raw/

# Chạy mock device (gửi MQTT)
python mock_device.py --scenario S1 --broker localhost

# Chạy fleet simulation (5 tàu)
python fleet_sim.py --num-vessels 5 --broker localhost
```
