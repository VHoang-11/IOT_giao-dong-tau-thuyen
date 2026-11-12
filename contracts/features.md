# SVMG ML Feature Definitions

Định nghĩa các đặc trưng (features) được sử dụng bởi mô hình phân loại dao động tàu thuyền.
Thứ tự các feature **phải giữ nguyên** để đảm bảo tương thích giữa C (ESP32) và Python (training/backend).

## Window 60s — Short-term dynamics

Các feature được tính trên cửa sổ trượt 60 giây gần nhất.

| # | Feature              | Đơn vị  | Mô tả                                                       |
|---|----------------------|---------|--------------------------------------------------------------|
| 0 | `rms_roll`           | deg     | Root-mean-square của góc roll trong 60s                      |
| 1 | `p95_roll`           | deg     | Phân vị 95 của |roll| trong 60s                              |
| 2 | `rms_pitch`          | deg     | Root-mean-square của góc pitch trong 60s                     |
| 3 | `p95_pitch`          | deg     | Phân vị 95 của |pitch| trong 60s                             |
| 4 | `max_abs_roll`       | deg     | Giá trị tuyệt đối lớn nhất của roll trong 60s               |
| 5 | `energy_roll`        | deg²    | Năng lượng tín hiệu roll = sum(roll²) / N trong 60s         |
| 6 | `zero_crossing_rate` | 1/s     | Tần suất tín hiệu roll cắt qua 0 (đổi dấu) trong 60s      |

## Window 180s — Long-term trend

Các feature được tính trên cửa sổ trượt 180 giây.

| #  | Feature              | Đơn vị     | Mô tả                                                          |
|----|----------------------|------------|-----------------------------------------------------------------|
| 7  | `mean_roll`          | deg        | Giá trị trung bình roll trong 180s (phát hiện heel offset)     |
| 8  | `mean_pitch`         | deg        | Giá trị trung bình pitch trong 180s                            |
| 9  | `std_roll`           | deg        | Độ lệch chuẩn roll trong 180s                                  |
| 10 | `trend_rms_slope`    | deg/min    | Hệ số góc hồi quy tuyến tính rms_roll theo thời gian trong 180s |
| 11 | `heel_duration_s`    | s          | Thời gian liên tục |mean_roll| > ngưỡng heel trong 180s        |

## Quality Flags

| #  | Feature             | Đơn vị | Mô tả                                                           |
|----|---------------------|--------|------------------------------------------------------------------|
| 12 | `data_quality_pct`  | %      | Tỷ lệ mẫu hợp lệ trong window (100 = hoàn hảo, < 80 = cảnh báo) |
| 13 | `sensor_ok`         | bool   | 1 nếu cảm biến MPU6050/ICM-20948 hoạt động bình thường, 0 nếu lỗi |

## Tổng kết

- **Tổng số features**: 14
- **Index**: 0–13 (thứ tự cố định)
- **Lưu ý**: Thứ tự phải khớp giữa:
  - `firmware/main/feature_extract.c` (ESP32 inference)
  - `ml/features.py` (Python training pipeline)
  - `backend/services/feature_store.py` (backend validation)
- Khi thêm/xóa feature → cập nhật cả 3 nơi + tăng `model_version`.
