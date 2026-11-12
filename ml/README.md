# SVMG Machine Learning — Phân loại chuyển động tàu

Pipeline học máy cho phân loại chuyển động tàu thuyền, từ huấn luyện đến triển khai trên ESP32.

## 4 lớp phân loại

| Lớp | Mã | Mô tả |
|-----|----|-------|
| **NORMAL** | 0 | Chuyển động bình thường, biên độ thấp |
| **HIGH_ROLL** | 1 | Lắc mạnh, RMS roll vượt ngưỡng |
| **PERSISTENT_OFFSET** | 2 | Nghiêng lệch bền (heel), mean roll ≠ 0 kéo dài |
| **AMPLITUDE_GROWTH** | 3 | Biên độ tăng dần (cộng hưởng tham số) |

## Pipeline

```
Dataset (CSV/Parquet)
    → Feature Engineering (14 đặc trưng)
    → Train/Val Split (GroupKFold theo session)
    → Random Forest Training
    → Evaluation (macro-F1, false alarm, latency)
    → Export C code (emlearn)
    → Tích hợp ESP32
```

## Huấn luyện

```bash
cd ml

# Cài đặt
pip install -r requirements.txt

# Huấn luyện với GroupKFold
python train.py --data ../data/raw/ --output models/

# Đánh giá
python evaluate.py --model models/rf_best.pkl --data ../data/raw/
```

## Cross-validation

- **GroupKFold (k=5)** theo `session_id` — đảm bảo không có data leakage
- Mỗi session là một lần chạy mô phỏng độc lập (600s)

## Xuất mô hình sang C (emlearn)

```bash
python export_emlearn.py --model models/rf_best.pkl \
    --output ../core/src/rf_model.h
```

File `rf_model.h` chứa cây quyết định dạng mảng C, tích hợp trực tiếp vào firmware.

## Chỉ số đánh giá

| Metric | Mục tiêu | Mô tả |
|--------|----------|-------|
| **Macro-F1** | ≥ 0.90 | Trung bình F1 trên 4 lớp |
| **False Alarm Rate** | ≤ 2% | Tỉ lệ NORMAL bị phân loại sai |
| **Detection Latency** | ≤ 120s | Thời gian phát hiện sự kiện bất thường |

## Model Registry & Monitoring

- Mô hình được lưu tại `models/` với metadata (version, metrics, timestamp)
- File `model_registry.json` theo dõi lịch sử các phiên bản
- Monitoring: so sánh hiệu suất RF vs Baseline B trên cùng test set
