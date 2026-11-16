# Kiểm định Feature Extraction — SVMG M2

## Phạm vi và kết quả kiểm thử

Lệnh kiểm thử: `python -m pytest ml/features/tests -q`. Kết quả thực tế: **18 đạt, 0 lỗi, 0 bỏ qua** (`18 passed in 0.52s`).

Unit tests dùng fixture nhỏ có nghiệm phân tích được; fixture tổng hợp không được đưa vào feature tables hoặc dùng làm dữ liệu huấn luyện.

| Nhóm kiểm thử | Nội dung đã kiểm chứng | Kết quả |
|---|---|---|
| Công thức cơ bản | RMS, population SD, mean, P2P, Type-7 percentile/IQR, max abs | Xem kết quả pytest |
| Trend | OLS slope, population R² và trường hợp SST=0 | Xem kết quả pytest |
| Chu kỳ | Zero crossing nội suy, period median, CV và thiếu chu kỳ | Xem kết quả pytest |
| Cửa sổ | `(t-W,t]`, đúng 60/180 giây, stride, thiếu duration | Xem kết quả pytest |
| Tính causal | Kết quả tại endpoint không đổi khi nối thêm dữ liệu tương lai | Xem kết quả pytest |
| Schema/validity | Thứ tự 30 cột, validity từng feature, missing gyro và mapping chưa xác nhận | Xem kết quả pytest |
| Hồi quy lỗi period | Cửa sổ sin 0,5 Hz, chu kỳ biết trước 2 giây; kiểm tra Roll và timestamp không bị đảo | Xem kết quả pytest |
| Tập angle-only 23 | Đúng tên/thứ tự; kiểm tra đủ 23 trạng thái VALID trên cửa sổ 180 giây đủ điều kiện | Xem kết quả pytest |
| Tính causal | Nối thêm quan sát tương lai không làm đổi giá trị period tại endpoint cũ | Xem kết quả pytest |

## Kiểm định dữ liệu thực

Kết quả theo nguồn và số lượng status từng feature nằm trong `feature_extraction_summary.json`. Mỗi Parquet values có metadata companion với `validity_json`; feature không hợp lệ được null, không điền 0.

## Giới hạn xác nhận

Unit test không xác nhận tính đại diện hàng hải, hiệu chuẩn cảm biến, validity của nhãn hay chất lượng phân loại. Thử nghiệm filter stability chỉ so sánh cùng cửa sổ thời gian và cùng định nghĩa feature.

Rà soát period phát hiện lỗi gán đảo mảng Roll và timestamp; extractor đã sửa, chạy lại trên dữ liệu thực và bổ sung test hồi quy. Bằng chứng cửa sổ đại diện, tính sẵn có của tập 23 feature và giới hạn dao động được ghi trong [báo cáo rà soát chu kỳ và tập angle-only](feature_period_subset_review.md).
### Seafar

Candidate rows: 1,384; complete 30-feature rows: 0; invalid-input rows: 0.

| Feature | VALID | MISSING_SOURCE_SIGNAL | INSUFFICIENT_WINDOW | INVALID_INPUT | UNDEFINED_MATHEMATICALLY | UNVERIFIED_SIGNAL_MAPPING |
|---|---:|---:|---:|---:|---:|---:|
| `roll_rms_60` | 1384 | 0 | 0 | 0 | 0 | 0 |
| `roll_std_60` | 1384 | 0 | 0 | 0 | 0 | 0 |
| `roll_mean_60` | 1384 | 0 | 0 | 0 | 0 | 0 |
| `roll_peak_to_peak_60` | 1384 | 0 | 0 | 0 | 0 | 0 |
| `roll_abs_p95_60` | 1384 | 0 | 0 | 0 | 0 | 0 |
| `roll_abs_max_60` | 1384 | 0 | 0 | 0 | 0 | 0 |
| `roll_iqr_60` | 1384 | 0 | 0 | 0 | 0 | 0 |
| `roll_diff_rms_60` | 1384 | 0 | 0 | 0 | 0 | 0 |
| `gyro_x_rms_60` | 0 | 0 | 0 | 0 | 0 | 1384 |
| `gyro_x_abs_p95_60` | 0 | 0 | 0 | 0 | 0 | 1384 |
| `gyro_x_std_60` | 0 | 0 | 0 | 0 | 0 | 1384 |
| `roll_mean_180` | 1318 | 0 | 66 | 0 | 0 | 0 |
| `roll_median_180` | 1318 | 0 | 66 | 0 | 0 | 0 |
| `roll_mean_abs_180` | 1318 | 0 | 66 | 0 | 0 | 0 |
| `roll_dominant_sign_ratio_180` | 1318 | 0 | 66 | 0 | 0 | 0 |
| `roll_segment_mean_std_180` | 1318 | 0 | 66 | 0 | 0 | 0 |
| `roll_mean_shift_180` | 1318 | 0 | 66 | 0 | 0 | 0 |
| `roll_rms_early_60` | 1318 | 0 | 66 | 0 | 0 | 0 |
| `roll_rms_late_60` | 1318 | 0 | 66 | 0 | 0 | 0 |
| `roll_rms_ratio_180` | 1318 | 0 | 66 | 0 | 0 | 0 |
| `roll_rms_slope_180` | 1318 | 0 | 66 | 0 | 0 | 0 |
| `roll_rms_trend_r2_180` | 1318 | 0 | 66 | 0 | 0 | 0 |
| `roll_p95_trend_slope_180` | 1318 | 0 | 66 | 0 | 0 | 0 |
| `roll_period_est_180` | 1285 | 0 | 66 | 0 | 33 | 0 |
| `roll_zero_crossings_180` | 1318 | 0 | 66 | 0 | 0 | 0 |
| `roll_period_cv_180` | 1271 | 0 | 66 | 0 | 47 | 0 |
| `pitch_rms_60` | 1384 | 0 | 0 | 0 | 0 | 0 |
| `pitch_std_60` | 1384 | 0 | 0 | 0 | 0 | 0 |
| `pitch_peak_to_peak_60` | 1384 | 0 | 0 | 0 | 0 | 0 |
| `gyro_y_rms_60` | 0 | 0 | 0 | 0 | 0 | 1384 |

### Hohai

Candidate rows: 1,764; complete 30-feature rows: 0; invalid-input rows: 0.

| Feature | VALID | MISSING_SOURCE_SIGNAL | INSUFFICIENT_WINDOW | INVALID_INPUT | UNDEFINED_MATHEMATICALLY | UNVERIFIED_SIGNAL_MAPPING |
|---|---:|---:|---:|---:|---:|---:|
| `roll_rms_60` | 1764 | 0 | 0 | 0 | 0 | 0 |
| `roll_std_60` | 1764 | 0 | 0 | 0 | 0 | 0 |
| `roll_mean_60` | 1764 | 0 | 0 | 0 | 0 | 0 |
| `roll_peak_to_peak_60` | 1764 | 0 | 0 | 0 | 0 | 0 |
| `roll_abs_p95_60` | 1764 | 0 | 0 | 0 | 0 | 0 |
| `roll_abs_max_60` | 1764 | 0 | 0 | 0 | 0 | 0 |
| `roll_iqr_60` | 1764 | 0 | 0 | 0 | 0 | 0 |
| `roll_diff_rms_60` | 1764 | 0 | 0 | 0 | 0 | 0 |
| `gyro_x_rms_60` | 0 | 1764 | 0 | 0 | 0 | 0 |
| `gyro_x_abs_p95_60` | 0 | 1764 | 0 | 0 | 0 | 0 |
| `gyro_x_std_60` | 0 | 1764 | 0 | 0 | 0 | 0 |
| `roll_mean_180` | 1512 | 0 | 252 | 0 | 0 | 0 |
| `roll_median_180` | 1512 | 0 | 252 | 0 | 0 | 0 |
| `roll_mean_abs_180` | 1512 | 0 | 252 | 0 | 0 | 0 |
| `roll_dominant_sign_ratio_180` | 1512 | 0 | 252 | 0 | 0 | 0 |
| `roll_segment_mean_std_180` | 1512 | 0 | 252 | 0 | 0 | 0 |
| `roll_mean_shift_180` | 1512 | 0 | 252 | 0 | 0 | 0 |
| `roll_rms_early_60` | 1512 | 0 | 252 | 0 | 0 | 0 |
| `roll_rms_late_60` | 1512 | 0 | 252 | 0 | 0 | 0 |
| `roll_rms_ratio_180` | 1512 | 0 | 252 | 0 | 0 | 0 |
| `roll_rms_slope_180` | 1512 | 0 | 252 | 0 | 0 | 0 |
| `roll_rms_trend_r2_180` | 1512 | 0 | 252 | 0 | 0 | 0 |
| `roll_p95_trend_slope_180` | 1512 | 0 | 252 | 0 | 0 | 0 |
| `roll_period_est_180` | 1512 | 0 | 252 | 0 | 0 | 0 |
| `roll_zero_crossings_180` | 1512 | 0 | 252 | 0 | 0 | 0 |
| `roll_period_cv_180` | 1512 | 0 | 252 | 0 | 0 | 0 |
| `pitch_rms_60` | 1764 | 0 | 0 | 0 | 0 | 0 |
| `pitch_std_60` | 1764 | 0 | 0 | 0 | 0 | 0 |
| `pitch_peak_to_peak_60` | 1764 | 0 | 0 | 0 | 0 | 0 |
| `gyro_y_rms_60` | 0 | 1764 | 0 | 0 | 0 | 0 |

### Southampton

Candidate rows: 277; complete 30-feature rows: 0; invalid-input rows: 0.

| Feature | VALID | MISSING_SOURCE_SIGNAL | INSUFFICIENT_WINDOW | INVALID_INPUT | UNDEFINED_MATHEMATICALLY | UNVERIFIED_SIGNAL_MAPPING |
|---|---:|---:|---:|---:|---:|---:|
| `roll_rms_60` | 277 | 0 | 0 | 0 | 0 | 0 |
| `roll_std_60` | 277 | 0 | 0 | 0 | 0 | 0 |
| `roll_mean_60` | 277 | 0 | 0 | 0 | 0 | 0 |
| `roll_peak_to_peak_60` | 277 | 0 | 0 | 0 | 0 | 0 |
| `roll_abs_p95_60` | 277 | 0 | 0 | 0 | 0 | 0 |
| `roll_abs_max_60` | 277 | 0 | 0 | 0 | 0 | 0 |
| `roll_iqr_60` | 277 | 0 | 0 | 0 | 0 | 0 |
| `roll_diff_rms_60` | 277 | 0 | 0 | 0 | 0 | 0 |
| `gyro_x_rms_60` | 0 | 0 | 0 | 0 | 0 | 277 |
| `gyro_x_abs_p95_60` | 0 | 0 | 0 | 0 | 0 | 277 |
| `gyro_x_std_60` | 0 | 0 | 0 | 0 | 0 | 277 |
| `roll_mean_180` | 34 | 0 | 243 | 0 | 0 | 0 |
| `roll_median_180` | 34 | 0 | 243 | 0 | 0 | 0 |
| `roll_mean_abs_180` | 34 | 0 | 243 | 0 | 0 | 0 |
| `roll_dominant_sign_ratio_180` | 34 | 0 | 243 | 0 | 0 | 0 |
| `roll_segment_mean_std_180` | 34 | 0 | 243 | 0 | 0 | 0 |
| `roll_mean_shift_180` | 34 | 0 | 243 | 0 | 0 | 0 |
| `roll_rms_early_60` | 34 | 0 | 243 | 0 | 0 | 0 |
| `roll_rms_late_60` | 34 | 0 | 243 | 0 | 0 | 0 |
| `roll_rms_ratio_180` | 34 | 0 | 243 | 0 | 0 | 0 |
| `roll_rms_slope_180` | 34 | 0 | 243 | 0 | 0 | 0 |
| `roll_rms_trend_r2_180` | 34 | 0 | 243 | 0 | 0 | 0 |
| `roll_p95_trend_slope_180` | 34 | 0 | 243 | 0 | 0 | 0 |
| `roll_period_est_180` | 34 | 0 | 243 | 0 | 0 | 0 |
| `roll_zero_crossings_180` | 34 | 0 | 243 | 0 | 0 | 0 |
| `roll_period_cv_180` | 34 | 0 | 243 | 0 | 0 | 0 |
| `pitch_rms_60` | 277 | 0 | 0 | 0 | 0 | 0 |
| `pitch_std_60` | 277 | 0 | 0 | 0 | 0 | 0 |
| `pitch_peak_to_peak_60` | 277 | 0 | 0 | 0 | 0 | 0 |
| `gyro_y_rms_60` | 0 | 0 | 0 | 0 | 0 | 277 |
