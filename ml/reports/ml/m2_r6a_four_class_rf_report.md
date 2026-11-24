# Báo cáo đánh giá Random Forest bốn lớp M2-R6a (`svmg-rf-four-class-m2r6a-0.1.0`)

> Dữ liệu `SIMULATION` (`svmg-four-class-exp-0.2.0` roll-only và `0.3.0` có pitch + nhiễu IMU), nhãn proxy `SIMULATION_SCENARIO_V2_CANDIDATE` sinh từ roll thật bằng ngưỡng đóng băng; RF học lại các luật này nên điểm cao **không** phải độ chính xác phát hiện nguy hiểm ngoài thực tế. Fit trên CORE Train (886 cửa sổ, 30 session), chọn chỉ bằng CORE Validation (469 cửa sổ, 12 session); **Test-G1 chưa được nạp/đánh giá**. Sinh bởi `python -m ml.train.rf_four_class_m2r6`; mô hình/artifact gitignored tại `ml/data/models/rf_four_class_m2r6/`.

## Cấu hình khai báo trước (Validation macro-F1 / tổng nút), seed 20261124, `max_features=sqrt`

| # | Cây | Độ sâu | Lá tối thiểu | class_weight | v0.2 | v0.3 |
|---:|---:|---:|---:|---|---:|---:|
| 0 | 15 | 4 | 5 | None | 0.9112 / 223 | 0.9876 / 185 |
| 1 | 15 | 4 | 5 | balanced_subsample | 0.8715 / 207 | 0.9112 / 199 |
| 2 | 25 | 6 | 5 | None | 0.9052 / 543 | 0.9739 / 459 |
| 3 | 25 | 6 | 5 | balanced_subsample | 0.8756 / 529 | 0.9473 / 471 |
| 4 | 40 | 8 | 3 | None | 0.9112 / 1014 | 0.9739 / 822 |
| 5 | 40 | 8 | 3 | balanced_subsample | 0.8800 / 1054 | 0.9524 / 870 |

Quy tắc chọn: macro-F1 Validation lớn nhất (3 chữ số), hòa → cấu hình gọn hơn đứng trước. Cổng đủ dùng khai báo trước: macro-F1 ≥ 0.8 và recall mọi lớp ≥ 0.5. Chọn: v0.2 #0, v0.3 #0; qua cổng: v0.2 True, v0.3 True.

## Validation CORE (cùng cửa sổ), so với Baseline B của Core C (tham số demo mặc định, không hiệu chỉnh lại)

| Chỉ số | RF v0.2 | RF v0.3 | Baseline B v0.2 | Baseline B v0.3 |
|---|---:|---:|---:|---:|
| Accuracy | 0.9787 | 0.9979 | 0.9126 | 0.9168 |
| Macro-F1 | 0.9112 | 0.9876 | 0.6781 | 0.6793 |
| Weighted-F1 | 0.982 | 0.9979 | 0.9238 | 0.9262 |
| KTC 95% macro-F1 (bootstrap theo session) | [0.6196, 1.0] | [0.7268, 1.0] | – | – |
| Session đúng theo đa số | 12/12 | 12/12 | – | – |
| Số dự đoán theo lớp | NORMAL 222, HIGH_ROLL 44, PERSISTENT_OFFSET 183, AMPLITUDE_GROWTH 20 | NORMAL 231, HIGH_ROLL 44, PERSISTENT_OFFSET 183, AMPLITUDE_GROWTH 11 | NORMAL 206, HIGH_ROLL 68, PERSISTENT_OFFSET 178, AMPLITUDE_GROWTH 17 | NORMAL 208, HIGH_ROLL 68, PERSISTENT_OFFSET 178, AMPLITUDE_GROWTH 15 |

Ma trận nhầm lẫn (hàng = thật). RF v0.2: NORMAL: [222, 0, 0, 10]; HIGH_ROLL: [0, 44, 0, 0]; PERSISTENT_OFFSET: [0, 0, 183, 0]; AMPLITUDE_GROWTH: [0, 0, 0, 10] (cột: NORMAL, HIGH_ROLL, PERSISTENT_OFFSET, AMPLITUDE_GROWTH). RF v0.3: NORMAL: [231, 0, 0, 1]; HIGH_ROLL: [0, 44, 0, 0]; PERSISTENT_OFFSET: [0, 0, 183, 0]; AMPLITUDE_GROWTH: [0, 0, 0, 10] (cột: NORMAL, HIGH_ROLL, PERSISTENT_OFFSET, AMPLITUDE_GROWTH). Baseline B v0.3: NORMAL: [208, 9, 0, 15]; HIGH_ROLL: [0, 44, 0, 0]; PERSISTENT_OFFSET: [0, 5, 178, 0]; AMPLITUDE_GROWTH: [0, 10, 0, 0] (cột: NORMAL, HIGH_ROLL, PERSISTENT_OFFSET, AMPLITUDE_GROWTH).

| Lớp | Validation cửa sổ/session | Train session | RF v0.2 P / R / F1 | RF v0.3 P / R / F1 | Baseline B v0.3 P / R / F1 |
|---|---:|---:|---:|---:|---:|
| NORMAL | 232/3 | 6 | 1.000 / 0.957 / 0.978 | 1.000 / 0.996 / 0.998 | 1.000 / 0.897 / 0.946 |
| HIGH_ROLL | 44/3 | 6 | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 | 0.647 / 1.000 / 0.786 |
| PERSISTENT_OFFSET | 183/3 | 5 | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 | 1.000 / 0.973 / 0.986 |
| AMPLITUDE_GROWTH | 10/3 | 13 | 0.500 / 1.000 / 0.667 | 0.909 / 1.000 / 0.952 | 0.000 / 0.000 / 0.000 |

## Theo độ phủ `target_coverage_180`, S0b và lỗi chính

- Accuracy theo độ phủ, v0.2: [0.0, 0.25) 1.000 (n=19); [0.25, 0.5) 1.000 (n=14); [0.5, 0.75) 1.000 (n=22); [0.75, 1.0) 0.837 (n=49); [1.0, 1.0001) 0.995 (n=365). v0.3: [0.0, 0.25) 1.000 (n=19); [0.25, 0.5) 1.000 (n=14); [0.5, 0.75) 1.000 (n=22); [0.75, 1.0) 0.980 (n=49); [1.0, 1.0001) 1.000 (n=365).
- S0b challenge (NORMAL, không dùng để fit): v0.2 Train 1.000 (dự đoán {'NORMAL': 200, 'HIGH_ROLL': 0, 'PERSISTENT_OFFSET': 0, 'AMPLITUDE_GROWTH': 0}); Validation 0.952 (dự đoán {'NORMAL': 99, 'HIGH_ROLL': 0, 'PERSISTENT_OFFSET': 0, 'AMPLITUDE_GROWTH': 5}); v0.3 Train 1.000 (dự đoán {'NORMAL': 200, 'HIGH_ROLL': 0, 'PERSISTENT_OFFSET': 0, 'AMPLITUDE_GROWTH': 0}); Validation 0.952 (dự đoán {'NORMAL': 99, 'HIGH_ROLL': 0, 'PERSISTENT_OFFSET': 0, 'AMPLITUDE_GROWTH': 5}).
- Lỗi RF v0.2: NORMAL->AMPLITUDE_GROWTH: 10 cửa sổ/1 session, phủ trung vị 0.918. Lỗi RF v0.3: NORMAL->AMPLITUDE_GROWTH: 1 cửa sổ/1 session, phủ trung vị 0.918.

## AMPLITUDE_GROWTH: nhóm Validation rất nhỏ

- Validation chỉ 10 cửa sổ từ 3 session (Train: 13 session). Recall Wilson 95%: v0.2 [0.7225, 1.0], v0.3 [0.7225, 1.0]; precision Wilson 95%: v0.2 [0.2993, 0.7007], v0.3 [0.6226, 0.9838]. Khoảng Wilson coi cửa sổ là độc lập nên còn lạc quan; theo session chỉ có 3 quan sát.
- Chênh lệch v0.2/v0.3 ở lớp này đến từ một session NORMAL duy nhất bị đoán nhầm thành growth; KTC bootstrap theo session chồng lấn, nên chưa đủ bằng chứng nói pitch/nhiễu cải thiện mô hình.

## Kích thước, tái lập và ứng viên

- RF v0.2: 15 cây, độ sâu ≤ 4, 223 nút (119 lá), so sánh trung bình/tối đa mỗi lần suy luận 41/60, ước tính mảng C ≈ 3152 B (12 B/nút trong + 16 B/lá 4 xác suất float32). RF v0.3: 15 cây, độ sâu ≤ 4, 185 nút (100 lá), so sánh trung bình/tối đa mỗi lần suy luận 37/60, ước tính mảng C ≈ 2620 B (12 B/nút trong + 16 B/lá 4 xác suất float32). Đặc trưng quan trọng nhất (MDI) v0.3: {'roll_abs_p95_60': 0.1458, 'roll_dominant_sign_ratio_180': 0.1287, 'roll_median_180': 0.122, 'roll_mean_180': 0.1177, 'roll_std_60': 0.0783}.
- Fit lại cùng seed cho cùng xác suất và cùng ngưỡng: v0.2 True, v0.3 True. Kiểm tra contract C (`svmg_class_t`, thứ tự `SVMG_FEATURE_FIELDS`, chỉ số nút int16): v0.3 {'classes_match_svmg_class_t': True, 'feature_order_matches_core_header': True, 'nodes_fit_int16_index': True}.
- **Ứng viên: `v0.3`** (quy tắc khai báo trước: v0.3 (gần miền cảm biến hơn) nếu qua cổng Validation, nếu không thì v0.2; không dùng Test-G1). SHA mô hình: `3d7ecf315e237b00e26da4338ed0aa313d6efc9e5488dd6b227e18cc80f41f89`; SHA dataset `f3c893fcaa49…`.
- Giới hạn: 3 session mỗi lớp ở Validation; chọn trong 6 cấu hình trên chính Validation nên điểm lạc quan; chưa có Test-G1, Test-G2 hay dữ liệu MPU6050 thật; chưa export `model.h` và chưa đo trên ESP32.
