# Kết quả Feature Extraction — SVMG M2

Thời điểm chạy UTC: 2026-11-16T14:35:52.341997+00:00. Triển khai này đánh giá đúng 30 candidate feature; không thay đổi contract 14 feature hiện hành, không tạo nhãn và không huấn luyện Random Forest.

## 1. Mục tiêu và dữ liệu đầu vào

Extractor đọc Parquet đã tiền xử lý trong `ml/data/processed/`, mỗi file là một segment độc lập. Không nối session, sheet hoặc run. Provenance và danh tính nguồn nằm trong metadata riêng, không thuộc vector ML. Chất lượng nguồn và các giới hạn dữ liệu gốc được ghi trong [Real Dataset Audit](../../audit/real_dataset_audit_report.md); tình trạng availability ban đầu nằm trong [ma trận khả dụng](../../docs/feature_availability_matrix.md).

| Nguồn | Segment | Candidate rows (cửa sổ 60 giây) | Endpoint có đủ 180 giây | Có ít nhất một feature VALID | Đủ cả 30 feature | Hàng có INVALID_INPUT | Thời gian xử lý (s) | Peak Python memory (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Seafar | 24 | 1,384 | 1,318 | 1,384 | 0 | 0 | 59.92 | 22.31 |
| Hohai | 21 | 1,764 | 1,512 | 1,764 | 0 | 0 | 73.02 | 4.553 |
| Southampton | 47 | 277 | 34 | 277 | 0 | 0 | 2.72 | 2.623 |

## 2. Thứ tự, công thức vận hành và đơn vị

ID dưới đây là zero-based; # là thứ tự one-based. Công thức theo đúng proposal trong `ml/docs/feature_specification_30.md`; lựa chọn vận hành đang ở trạng thái `PENDING_TEAM_APPROVAL`, không thay đổi 14-feature contract.

| ID / # | Feature | Cửa sổ | Công thức vận hành | Đơn vị |
|---:|---|---:|---|---|
| 0 / 1 | `roll_rms_60` | 60 s | sqrt(mean(roll²)) — RMS góc Roll 60 giây, kể cả offset | độ |
| 1 / 2 | `roll_std_60` | 60 s | sqrt(mean((roll-mean(roll))²)) — Độ lệch chuẩn tổng thể Roll 60 giây | độ |
| 2 / 3 | `roll_mean_60` | 60 s | mean(roll) — Trung bình có dấu Roll 60 giây | độ |
| 3 / 4 | `roll_peak_to_peak_60` | 60 s | max(roll)-min(roll) — Biên độ đỉnh-đỉnh Roll | độ |
| 4 / 5 | `roll_abs_p95_60` | 60 s | Q0.95(|roll|), Type-7 — Phân vị Type-7 95% của |Roll| | độ |
| 5 / 6 | `roll_abs_max_60` | 60 s | max(|roll|) — Cực đại |Roll| | độ |
| 6 / 7 | `roll_iqr_60` | 60 s | Q0.75(roll)-Q0.25(roll), Type-7 — Khoảng tứ phân vị Roll | độ |
| 7 / 8 | `roll_diff_rms_60` | 60 s | sqrt(mean((x[i]-x[i-1])²)) trên cặp đúng chu kỳ — RMS sai phân Roll liên tiếp | độ/mẫu |
| 8 / 9 | `gyro_x_rms_60` | 60 s | sqrt(mean(gx²)) — RMS gyro trục x | rad/s |
| 9 / 10 | `gyro_x_abs_p95_60` | 60 s | Q0.95(|gx|), Type-7 — Phân vị Type-7 95% của |gyro x| | rad/s |
| 10 / 11 | `gyro_x_std_60` | 60 s | sqrt(mean((gx-mean(gx))²)) — Độ lệch chuẩn tổng thể gyro x | rad/s |
| 11 / 12 | `roll_mean_180` | 180 s | mean(roll) — Trung bình Roll 180 giây | độ |
| 12 / 13 | `roll_median_180` | 180 s | Q0.50(roll), Type-7 — Trung vị Roll Type-7 | độ |
| 13 / 14 | `roll_mean_abs_180` | 180 s | mean(|roll|) — Trung bình |Roll| | độ |
| 14 / 15 | `roll_dominant_sign_ratio_180` | 180 s | max(n_pos,n_neg)/(n_pos+n_neg); bỏ mẫu đúng 0 — Tỷ lệ dấu trội | không thứ nguyên |
| 15 / 16 | `roll_segment_mean_std_180` | 180 s | SD0(mean_1,mean_2,mean_3) — Độ lệch chuẩn population của ba mean block | độ |
| 16 / 17 | `roll_mean_shift_180` | 180 s | mean(block_muộn)-mean(block_sớm) — Dịch chuyển mean | độ |
| 17 / 18 | `roll_rms_early_60` | 180 s | sqrt(mean(roll²)) trên block đầu 60 giây — RMS block Roll sớm | độ |
| 18 / 19 | `roll_rms_late_60` | 180 s | sqrt(mean(roll²)) trên block cuối 60 giây — RMS block Roll muộn | độ |
| 19 / 20 | `roll_rms_ratio_180` | 180 s | RMS_muộn/RMS_sớm; epsilon số học 1e-9 độ — Tỷ số RMS muộn/sớm | không thứ nguyên |
| 20 / 21 | `roll_rms_slope_180` | 180 s | OLS qua tâm [30,90,150] giây; slope × 60 — Độ dốc hồi quy tuyến tính RMS | độ/phút |
| 21 / 22 | `roll_rms_trend_r2_180` | 180 s | 1-SSE/SST; undefined nếu SST dưới tolerance — R² hồi quy ba RMS block | không thứ nguyên |
| 22 / 23 | `roll_p95_trend_slope_180` | 180 s | OLS Q0.95(|roll|) ba block; slope × 60 — Độ dốc phân vị |Roll| 95% | độ/phút |
| 23 / 24 | `roll_period_est_180` | 180 s | median khoảng cách crossing lên; mean-center; nội suy tuyến tính — Chu kỳ dao động ước lượng | giây |
| 24 / 25 | `roll_zero_crossings_180` | 180 s | đếm crossing lên và xuống của roll-mean(window) — Số zero crossing | lần/180 giây |
| 25 / 26 | `roll_period_cv_180` | 180 s | SD0(periods)/mean(periods); cần ít nhất 3 period — CV chu kỳ | không thứ nguyên |
| 26 / 27 | `pitch_rms_60` | 60 s | sqrt(mean(pitch²)) — RMS Pitch | độ |
| 27 / 28 | `pitch_std_60` | 60 s | sqrt(mean((pitch-mean(pitch))²)) — Độ lệch chuẩn tổng thể Pitch | độ |
| 28 / 29 | `pitch_peak_to_peak_60` | 60 s | max(pitch)-min(pitch) — Biên độ đỉnh-đỉnh Pitch | độ |
| 29 / 30 | `gyro_y_rms_60` | 60 s | sqrt(mean(gy²)) — RMS gyro trục y | rad/s |

### Quy ước cửa sổ và validity

- Cửa sổ trailing chọn mẫu `(t-W,t]`; endpoint đầu tiên xuất hiện khi segment đã có đủ 60 giây, sau đó cách nhau 10 giây. Các feature 180 giây ở cùng endpoint có `INSUFFICIENT_WINDOW` đến khi đủ lịch sử.
- Coverage tối thiểu 95%: 570/600 mẫu trong cửa sổ 60 giây; 1.710/1.800 trong cửa sổ 180 giây. Cửa sổ có timestamp gap lớn hơn 1,5 chu kỳ danh định nhận `INVALID_INPUT`.
- Percentile/IQR dùng Type-7; độ lệch chuẩn dùng population (`ddof=0`). Sai phân không nối qua missing/gap.
- Ba block dài 60 giây lần lượt `(t-180,t-120]`, `(t-120,t-60]`, `(t-60,t]`; hồi quy dùng tâm block 30/90/150 giây và xuất slope theo độ/phút.
- Zero crossing dùng `roll-mean(window)`, crossing giữa hai mẫu được nội suy tuyến tính. Period là median chu kỳ từ crossing lên; period cần 3 crossing lên, CV cần 3 chu kỳ. Mẫu đúng 0 bị loại khỏi tỷ lệ sign; chuỗi toàn 0 làm feature sign undefined.
- Epsilon tỷ số RMS là 1e-9 độ, chỉ là guard số học cấu hình được, không suy ra từ sensor noise. R² undefined nếu SST không vượt tolerance. Hai lựa chọn này vẫn chờ nhóm duyệt.

## 3. Tổ chức bảng và metadata

Mỗi dataset có `feature_values.parquet` chứa `window_id` rồi 30 cột feature đúng thứ tự; `feature_metadata.parquet` riêng chứa nguồn/session/segment/end time, validity từng feature, provenance và version. Metadata không được đưa vào feature vector.

| Nguồn | Candidate rows | Complete 30 | Roll-only 60 (8) | Roll+Pitch 60 (11) | Offset+growth 180 (12) | Angle-only (23) |
|---|---:|---:|---:|---:|---:|---:|
| Seafar | 1,384 | 0 | 1,384 | 1,384 | 1,318 | 1,318 |
| Hohai | 1,764 | 0 | 1,764 | 1,764 | 1,512 | 1,512 |
| Southampton | 277 | 0 | 277 | 277 | 34 | 34 |

## 4. Availability và thống kê thực nghiệm

`VALID` chỉ nói phép tính có đủ dữ liệu và toán học xác định, không đồng nghĩa công thức/mapping đã được phê duyệt. Gyro Seafar và Southampton được đánh dấu `UNVERIFIED_SIGNAL_MAPPING`; Hohai gyro là `MISSING_SOURCE_SIGNAL`.

### Seafar

Đọc 24 segment processed. Có 1,384 endpoint/candidate rows 60 giây, 1,318 endpoint đủ lịch sử 180 giây; 0 row đủ 30 feature. Rows có ít nhất một feature valid: 1,384; rows chứa invalid input: 0.

| Feature | VALID | MISSING | INSUFFICIENT | INVALID | UNDEFINED | UNVERIFIED | Mean | SD population | P05 | P50 | P95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `roll_rms_60` | 1384 | 0 | 0 | 0 | 0 | 0 | 3.3145 | 0.18608 | 3.0368 | 3.303 | 3.5837 |
| `roll_std_60` | 1384 | 0 | 0 | 0 | 0 | 0 | 0.11615 | 0.082506 | 0.023673 | 0.096417 | 0.28535 |
| `roll_mean_60` | 1384 | 0 | 0 | 0 | 0 | 0 | 3.3115 | 0.18536 | 3.0321 | 3.3007 | 3.5792 |
| `roll_peak_to_peak_60` | 1384 | 0 | 0 | 0 | 0 | 0 | 0.51598 | 0.34522 | 0.11 | 0.43 | 1.23 |
| `roll_abs_p95_60` | 1384 | 0 | 0 | 0 | 0 | 0 | 3.5007 | 0.26313 | 3.18 | 3.44 | 4.03 |
| `roll_abs_max_60` | 1384 | 0 | 0 | 0 | 0 | 0 | 3.567 | 0.29555 | 3.21 | 3.48 | 4.17 |
| `roll_iqr_60` | 1384 | 0 | 0 | 0 | 0 | 0 | 0.15805 | 0.12223 | 0.03 | 0.12 | 0.39 |
| `roll_diff_rms_60` | 1384 | 0 | 0 | 0 | 0 | 0 | 0.0096871 | 0.0051487 | 0.0038546 | 0.0087537 | 0.018645 |
| `gyro_x_rms_60` | 0 | 0 | 0 | 0 | 0 | 1384 | — | — | — | — | — |
| `gyro_x_abs_p95_60` | 0 | 0 | 0 | 0 | 0 | 1384 | — | — | — | — | — |
| `gyro_x_std_60` | 0 | 0 | 0 | 0 | 0 | 1384 | — | — | — | — | — |
| `roll_mean_180` | 1318 | 0 | 66 | 0 | 0 | 0 | 3.3098 | 0.16592 | 3.0672 | 3.2907 | 3.5431 |
| `roll_median_180` | 1318 | 0 | 66 | 0 | 0 | 0 | 3.3084 | 0.1636 | 3.07 | 3.29 | 3.54 |
| `roll_mean_abs_180` | 1318 | 0 | 66 | 0 | 0 | 0 | 3.3098 | 0.16592 | 3.0672 | 3.2907 | 3.5431 |
| `roll_dominant_sign_ratio_180` | 1318 | 0 | 66 | 0 | 0 | 0 | 1 | 0 | 1 | 1 | 1 |
| `roll_segment_mean_std_180` | 1318 | 0 | 66 | 0 | 0 | 0 | 0.055312 | 0.059353 | 0.0078824 | 0.038052 | 0.18056 |
| `roll_mean_shift_180` | 1318 | 0 | 66 | 0 | 0 | 0 | 0.0042585 | 0.1642 | -0.23248 | 0.0015583 | 0.2063 |
| `roll_rms_early_60` | 1318 | 0 | 66 | 0 | 0 | 0 | 3.3108 | 0.18659 | 3.035 | 3.2945 | 3.5839 |
| `roll_rms_late_60` | 1318 | 0 | 66 | 0 | 0 | 0 | 3.3151 | 0.18483 | 3.0436 | 3.299 | 3.5839 |
| `roll_rms_ratio_180` | 1318 | 0 | 66 | 0 | 0 | 0 | 1.0025 | 0.050286 | 0.93065 | 1.0004 | 1.066 |
| `roll_rms_slope_180` | 1318 | 0 | 66 | 0 | 0 | 0 | 0.00213 | 0.08245 | -0.11755 | 0.00074861 | 0.10566 |
| `roll_rms_trend_r2_180` | 1318 | 0 | 66 | 0 | 0 | 0 | 0.56694 | 0.35341 | 0.013604 | 0.63585 | 0.99611 |
| `roll_p95_trend_slope_180` | 1318 | 0 | 66 | 0 | 0 | 0 | 0.0026927 | 0.12196 | -0.175 | 0 | 0.19 |
| `roll_period_est_180` | 1285 | 0 | 66 | 0 | 33 | 0 | 6.3552 | 5.0401 | 3.9553 | 4.6 | 12.558 |
| `roll_zero_crossings_180` | 1318 | 0 | 66 | 0 | 0 | 0 | 37.275 | 15.647 | 11 | 36.5 | 62.15 |
| `roll_period_cv_180` | 1271 | 0 | 66 | 0 | 47 | 0 | 0.87982 | 0.24683 | 0.54234 | 0.85028 | 1.3245 |
| `pitch_rms_60` | 1384 | 0 | 0 | 0 | 0 | 0 | 0.83987 | 0.099627 | 0.66435 | 0.85791 | 0.98216 |
| `pitch_std_60` | 1384 | 0 | 0 | 0 | 0 | 0 | 0.036224 | 0.025178 | 0.011149 | 0.028636 | 0.086437 |
| `pitch_peak_to_peak_60` | 1384 | 0 | 0 | 0 | 0 | 0 | 0.14523 | 0.092611 | 0.05 | 0.12 | 0.33 |
| `gyro_y_rms_60` | 0 | 0 | 0 | 0 | 0 | 1384 | — | — | — | — | — |

### Hohai

Đọc 21 segment processed. Có 1,764 endpoint/candidate rows 60 giây, 1,512 endpoint đủ lịch sử 180 giây; 0 row đủ 30 feature. Rows có ít nhất một feature valid: 1,764; rows chứa invalid input: 0.

| Feature | VALID | MISSING | INSUFFICIENT | INVALID | UNDEFINED | UNVERIFIED | Mean | SD population | P05 | P50 | P95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `roll_rms_60` | 1764 | 0 | 0 | 0 | 0 | 0 | 0.35352 | 0.098552 | 0.22043 | 0.3404 | 0.53086 |
| `roll_std_60` | 1764 | 0 | 0 | 0 | 0 | 0 | 0.34769 | 0.098645 | 0.21718 | 0.33046 | 0.52859 |
| `roll_mean_60` | 1764 | 0 | 0 | 0 | 0 | 0 | 0.014745 | 0.062019 | -0.066465 | -9.6624e-05 | 0.11276 |
| `roll_peak_to_peak_60` | 1764 | 0 | 0 | 0 | 0 | 0 | 1.9469 | 0.58777 | 1.165 | 1.8587 | 3.0278 |
| `roll_abs_p95_60` | 1764 | 0 | 0 | 0 | 0 | 0 | 0.69766 | 0.19774 | 0.43172 | 0.66669 | 1.0692 |
| `roll_abs_max_60` | 1764 | 0 | 0 | 0 | 0 | 0 | 1.0416 | 0.31281 | 0.62295 | 0.99125 | 1.6683 |
| `roll_iqr_60` | 1764 | 0 | 0 | 0 | 0 | 0 | 0.46516 | 0.14342 | 0.28104 | 0.43456 | 0.73349 |
| `roll_diff_rms_60` | 1764 | 0 | 0 | 0 | 0 | 0 | 0.11826 | 0.033867 | 0.072699 | 0.11253 | 0.18122 |
| `gyro_x_rms_60` | 0 | 1764 | 0 | 0 | 0 | 0 | — | — | — | — | — |
| `gyro_x_abs_p95_60` | 0 | 1764 | 0 | 0 | 0 | 0 | — | — | — | — | — |
| `gyro_x_std_60` | 0 | 1764 | 0 | 0 | 0 | 0 | — | — | — | — | — |
| `roll_mean_180` | 1512 | 0 | 252 | 0 | 0 | 0 | 0.015181 | 0.061011 | -0.063894 | -0.0020993 | 0.10513 |
| `roll_median_180` | 1512 | 0 | 252 | 0 | 0 | 0 | 0.011619 | 0.05762 | -0.073741 | -0.0016102 | 0.099605 |
| `roll_mean_abs_180` | 1512 | 0 | 252 | 0 | 0 | 0 | 0.28458 | 0.066781 | 0.20053 | 0.26832 | 0.40618 |
| `roll_dominant_sign_ratio_180` | 1512 | 0 | 252 | 0 | 0 | 0 | 0.54991 | 0.053851 | 0.50333 | 0.53556 | 0.62656 |
| `roll_segment_mean_std_180` | 1512 | 0 | 252 | 0 | 0 | 0 | 0.010545 | 0.0072507 | 0.0021239 | 0.0089227 | 0.024659 |
| `roll_mean_shift_180` | 1512 | 0 | 252 | 0 | 0 | 0 | -0.0020978 | 0.02347 | -0.040002 | -0.0018815 | 0.034726 |
| `roll_rms_early_60` | 1512 | 0 | 252 | 0 | 0 | 0 | 0.35021 | 0.099985 | 0.21617 | 0.33709 | 0.53063 |
| `roll_rms_late_60` | 1512 | 0 | 252 | 0 | 0 | 0 | 0.36276 | 0.097238 | 0.23531 | 0.3472 | 0.53763 |
| `roll_rms_ratio_180` | 1512 | 0 | 252 | 0 | 0 | 0 | 1.0752 | 0.27783 | 0.68833 | 1.0317 | 1.582 |
| `roll_rms_slope_180` | 1512 | 0 | 252 | 0 | 0 | 0 | 0.006275 | 0.046401 | -0.068823 | 0.0049245 | 0.084083 |
| `roll_rms_trend_r2_180` | 1512 | 0 | 252 | 0 | 0 | 0 | 0.50815 | 0.35859 | 0.0087321 | 0.52737 | 0.9931 |
| `roll_p95_trend_slope_180` | 1512 | 0 | 252 | 0 | 0 | 0 | 0.012099 | 0.094249 | -0.14602 | 0.010339 | 0.16836 |
| `roll_period_est_180` | 1512 | 0 | 252 | 0 | 0 | 0 | 1.7981 | 0.064473 | 1.6995 | 1.8054 | 1.8726 |
| `roll_zero_crossings_180` | 1512 | 0 | 252 | 0 | 0 | 0 | 194.84 | 7.835 | 181.55 | 195 | 206 |
| `roll_period_cv_180` | 1512 | 0 | 252 | 0 | 0 | 0 | 0.21586 | 0.083404 | 0.14258 | 0.20141 | 0.33866 |
| `pitch_rms_60` | 1764 | 0 | 0 | 0 | 0 | 0 | 0.086348 | 0.022673 | 0.056008 | 0.082144 | 0.12675 |
| `pitch_std_60` | 1764 | 0 | 0 | 0 | 0 | 0 | 0.085208 | 0.022344 | 0.055487 | 0.08136 | 0.12538 |
| `pitch_peak_to_peak_60` | 1764 | 0 | 0 | 0 | 0 | 0 | 0.4704 | 0.12984 | 0.29467 | 0.45258 | 0.7114 |
| `gyro_y_rms_60` | 0 | 1764 | 0 | 0 | 0 | 0 | — | — | — | — | — |

### Southampton

Đọc 47 segment processed. Có 277 endpoint/candidate rows 60 giây, 34 endpoint đủ lịch sử 180 giây; 0 row đủ 30 feature. Rows có ít nhất một feature valid: 277; rows chứa invalid input: 0.

| Feature | VALID | MISSING | INSUFFICIENT | INVALID | UNDEFINED | UNVERIFIED | Mean | SD population | P05 | P50 | P95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `roll_rms_60` | 277 | 0 | 0 | 0 | 0 | 0 | 0.43875 | 0.21434 | 0.11817 | 0.3793 | 0.76925 |
| `roll_std_60` | 277 | 0 | 0 | 0 | 0 | 0 | 0.10977 | 0.099443 | 0.016602 | 0.072235 | 0.35346 |
| `roll_mean_60` | 277 | 0 | 0 | 0 | 0 | 0 | 0.39952 | 0.23851 | 0.065499 | 0.33523 | 0.76441 |
| `roll_peak_to_peak_60` | 277 | 0 | 0 | 0 | 0 | 0 | 0.58831 | 0.49722 | 0.08481 | 0.41217 | 1.7253 |
| `roll_abs_p95_60` | 277 | 0 | 0 | 0 | 0 | 0 | 0.57521 | 0.22579 | 0.20067 | 0.60673 | 0.94083 |
| `roll_abs_max_60` | 277 | 0 | 0 | 0 | 0 | 0 | 0.68324 | 0.25545 | 0.27619 | 0.73117 | 1.133 |
| `roll_iqr_60` | 277 | 0 | 0 | 0 | 0 | 0 | 0.14826 | 0.14178 | 0.024962 | 0.091694 | 0.45872 |
| `roll_diff_rms_60` | 277 | 0 | 0 | 0 | 0 | 0 | 0.092248 | 0.082966 | 0.0046705 | 0.051222 | 0.26702 |
| `gyro_x_rms_60` | 0 | 0 | 0 | 0 | 0 | 277 | — | — | — | — | — |
| `gyro_x_abs_p95_60` | 0 | 0 | 0 | 0 | 0 | 277 | — | — | — | — | — |
| `gyro_x_std_60` | 0 | 0 | 0 | 0 | 0 | 277 | — | — | — | — | — |
| `roll_mean_180` | 34 | 0 | 243 | 0 | 0 | 0 | 0.6936 | 0.0075082 | 0.682 | 0.69209 | 0.70584 |
| `roll_median_180` | 34 | 0 | 243 | 0 | 0 | 0 | 0.69276 | 0.0075158 | 0.68092 | 0.69117 | 0.70467 |
| `roll_mean_abs_180` | 34 | 0 | 243 | 0 | 0 | 0 | 0.6936 | 0.0075082 | 0.682 | 0.69209 | 0.70584 |
| `roll_dominant_sign_ratio_180` | 34 | 0 | 243 | 0 | 0 | 0 | 1 | 0 | 1 | 1 | 1 |
| `roll_segment_mean_std_180` | 34 | 0 | 243 | 0 | 0 | 0 | 0.011056 | 0.0075386 | 0.0042092 | 0.0082166 | 0.027949 |
| `roll_mean_shift_180` | 34 | 0 | 243 | 0 | 0 | 0 | 0.0084396 | 0.017291 | -0.025586 | 0.013311 | 0.029474 |
| `roll_rms_early_60` | 34 | 0 | 243 | 0 | 0 | 0 | 0.68905 | 0.018639 | 0.64969 | 0.69212 | 0.72102 |
| `roll_rms_late_60` | 34 | 0 | 243 | 0 | 0 | 0 | 0.69826 | 0.013201 | 0.67737 | 0.69523 | 0.71826 |
| `roll_rms_ratio_180` | 34 | 0 | 243 | 0 | 0 | 0 | 1.0139 | 0.026069 | 0.96377 | 1.0206 | 1.0439 |
| `roll_rms_slope_180` | 34 | 0 | 243 | 0 | 0 | 0 | 0.0046063 | 0.009037 | -0.012918 | 0.0070825 | 0.014584 |
| `roll_rms_trend_r2_180` | 34 | 0 | 243 | 0 | 0 | 0 | 0.61143 | 0.34259 | 0.094015 | 0.76716 | 0.98216 |
| `roll_p95_trend_slope_180` | 34 | 0 | 243 | 0 | 0 | 0 | 0.011134 | 0.032844 | -0.021207 | 0.0063299 | 0.084118 |
| `roll_period_est_180` | 34 | 0 | 243 | 0 | 0 | 0 | 1.0162 | 0.32753 | 0.70362 | 0.92529 | 1.6231 |
| `roll_zero_crossings_180` | 34 | 0 | 243 | 0 | 0 | 0 | 133.21 | 73.662 | 40.65 | 136.5 | 286.6 |
| `roll_period_cv_180` | 34 | 0 | 243 | 0 | 0 | 0 | 1.9464 | 0.38227 | 1.5144 | 1.811 | 2.6214 |
| `pitch_rms_60` | 277 | 0 | 0 | 0 | 0 | 0 | 1.1589 | 0.72928 | 0.28784 | 1.1195 | 1.8122 |
| `pitch_std_60` | 277 | 0 | 0 | 0 | 0 | 0 | 0.41543 | 0.56167 | 0.013244 | 0.12476 | 1.5544 |
| `pitch_peak_to_peak_60` | 277 | 0 | 0 | 0 | 0 | 0 | 1.5404 | 1.8579 | 0.054521 | 0.60916 | 5.1795 |
| `gyro_y_rms_60` | 0 | 0 | 0 | 0 | 0 | 277 | — | — | — | — | — |

## 5. Rà soát chu kỳ và tập angle-only

Kết quả ban đầu ghi nhận 24 feature có cửa sổ VALID: 23 feature angle-only cộng với `roll_zero_crossings_180`. Tập angle-only loại toàn bộ Group E theo thiết kế. Rà soát cuối tìm thấy và sửa lỗi đảo thứ tự tín hiệu/timestamp; sau tái trích xuất có 26 feature đạt VALID trên ít nhất một cửa sổ. Chi tiết 23 tên theo thứ tự, kiểm tra từng hàng, cửa sổ thực đại diện và phép đối chiếu độc lập nằm trong [báo cáo rà soát chu kỳ và tập angle-only](feature_period_subset_review.md).

Period dùng Roll trừ trung bình của cùng cửa sổ, không detrend; đây là proposal trong đặc tả còn chờ phê duyệt. Các giá trị period nay tính được ở phần lớn cửa sổ đủ 180 giây, nhưng CV cao ở một số nguồn cần đánh giá ổn định trước khi labeling.

## 6. Độ ổn định theo preprocessing/filter

Baseline production vẫn là 10 Hz / Butterworth bậc 4 cutoff 4 Hz. So sánh bên dưới tái xử lý một segment raw đại diện với cutoff thay thế cấu hình 3 Hz, không ghi đè baseline; chỉ ghép endpoint trùng nhau và feature `VALID` ở cả hai cấu hình.

### Seafar

Tần số nguồn không cao hơn tần số đích; không có bước giảm mẫu 50 xuống 10 Hz để so sánh cutoff.

### Hohai

Phiên/segment đại diện: `Berth_B_T7_Type_A` / `segment_000`; endpoint căn thời gian chung: 84.

| Feature | Cửa sổ chung VALID | Mean |Δ| | Max |Δ| | Mean relative diff (%) | Tương quan | Mean normalized |
|---|---:|---:|---:|---:|---:|---:|
| `roll_rms_60` | 84 | 0.0001458 | 0.0015307 | 0.038529 | 0.99999 | 0.00042573 |
| `roll_std_60` | 84 | 0.00014975 | 0.0014474 | 0.041326 | 0.99999 | 0.0004521 |
| `roll_mean_60` | 84 | 0.00021019 | 0.00068407 | 0.23776 | 0.99983 | 0.002355 |
| `roll_peak_to_peak_60` | 84 | 0.010113 | 0.11607 | 0.46604 | 0.99938 | 0.0054203 |
| `roll_abs_p95_60` | 84 | 0.0092498 | 0.035732 | 1.2942 | 0.99658 | 0.013553 |
| `roll_abs_max_60` | 84 | 0.008164 | 0.11972 | 0.70549 | 0.99834 | 0.0082127 |
| `roll_iqr_60` | 84 | 0.008391 | 0.024514 | 1.8333 | 0.99615 | 0.018788 |
| `roll_diff_rms_60` | 84 | 8.2854e-05 | 0.00026016 | 0.072717 | 1 | 0.00071249 |
| `gyro_x_rms_60` | 0 | — | — | — | — | — |
| `gyro_x_abs_p95_60` | 0 | — | — | — | — | — |
| `gyro_x_std_60` | 0 | — | — | — | — | — |
| `roll_mean_180` | 72 | 8.588e-05 | 0.00031021 | 0.095754 | 0.99995 | 0.00091788 |
| `roll_median_180` | 72 | 0.0021102 | 0.0067234 | 2.5899 | 0.96578 | 0.023544 |
| `roll_mean_abs_180` | 72 | 0.00014441 | 0.00041465 | 0.05086 | 0.99998 | 0.00051047 |
| `roll_dominant_sign_ratio_180` | 72 | 0.0028241 | 0.0072222 | 0.46936 | 0.97147 | 0.0046938 |
| `roll_segment_mean_std_180` | 72 | 0.00013499 | 0.00036682 | 3.2981 | 0.99918 | 0.01897 |
| `roll_mean_shift_180` | 72 | 0.00034235 | 0.0011623 | 24.684 | 0.9995 | 0.036958 |
| `roll_rms_early_60` | 72 | 0.00016529 | 0.0015307 | 0.043583 | 0.99999 | 0.00047477 |
| `roll_rms_late_60` | 72 | 0.00015009 | 0.0015307 | 0.039074 | 0.99999 | 0.00043393 |
| `roll_rms_ratio_180` | 72 | 0.00078581 | 0.0059049 | 0.074031 | 0.99999 | 0.00076477 |
| `roll_rms_slope_180` | 72 | 0.00014408 | 0.0011805 | 0.65241 | 0.99999 | 0.0044684 |
| `roll_rms_trend_r2_180` | 72 | 0.0019544 | 0.034795 | 1.0275 | 0.99991 | 0.0038784 |
| `roll_p95_trend_slope_180` | 72 | 0.0062504 | 0.028269 | 943.34 | 0.99721 | 0.081996 |
| `roll_period_est_180` | 72 | 0.001761 | 0.01804 | 0.098655 | 0.98735 | 0.00099065 |
| `roll_zero_crossings_180` | 72 | 0.38889 | 3 | 0.19374 | 0.93122 | 0.0019348 |
| `roll_period_cv_180` | 72 | 0.0014205 | 0.015216 | 0.89433 | 0.96612 | 0.0085286 |
| `pitch_rms_60` | 84 | 4.3581e-05 | 0.00020271 | 0.073231 | 0.99999 | 0.00069985 |
| `pitch_std_60` | 84 | 4.3214e-05 | 0.00020016 | 0.073148 | 0.99999 | 0.00070016 |
| `pitch_peak_to_peak_60` | 84 | 0.0028286 | 0.010906 | 0.76449 | 0.99905 | 0.0076184 |
| `gyro_y_rms_60` | 0 | — | — | — | — | — |

### Southampton

Phiên/segment đại diện: `southampton_run_14` / `segment_000`; endpoint căn thời gian chung: 46.

| Feature | Cửa sổ chung VALID | Mean |Δ| | Max |Δ| | Mean relative diff (%) | Tương quan | Mean normalized |
|---|---:|---:|---:|---:|---:|---:|
| `roll_rms_60` | 46 | 5.2756e-05 | 0.00041883 | 0.0074844 | 0.99999 | 7.5911e-05 |
| `roll_std_60` | 46 | 0.00027176 | 0.0015674 | 0.66713 | 0.99997 | 0.012814 |
| `roll_mean_60` | 46 | 3.7849e-05 | 0.00017137 | 0.0054291 | 1 | 5.4477e-05 |
| `roll_peak_to_peak_60` | 46 | 0.0079626 | 0.06557 | 2.5888 | 0.99812 | 0.065339 |
| `roll_abs_p95_60` | 46 | 0.00073855 | 0.0062302 | 0.092536 | 0.99974 | 0.0010092 |
| `roll_abs_max_60` | 46 | 0.0054586 | 0.042243 | 0.56719 | 0.996 | 0.0072487 |
| `roll_iqr_60` | 46 | 0.00073653 | 0.0063559 | 1.4818 | 0.99956 | 0.025155 |
| `roll_diff_rms_60` | 46 | 0.001399 | 0.0043463 | 14.385 | 0.99991 | 0.23752 |
| `gyro_x_rms_60` | 0 | — | — | — | — | — |
| `gyro_x_abs_p95_60` | 0 | — | — | — | — | — |
| `gyro_x_std_60` | 0 | — | — | — | — | — |
| `roll_mean_180` | 34 | 1.242e-05 | 4.8341e-05 | 0.0017831 | 1 | 1.7946e-05 |
| `roll_median_180` | 34 | 0.00015087 | 0.00056702 | 0.021736 | 0.99969 | 0.00021828 |
| `roll_mean_abs_180` | 34 | 1.242e-05 | 4.8341e-05 | 0.0017831 | 1 | 1.7946e-05 |
| `roll_dominant_sign_ratio_180` | 34 | 0 | 0 | 0 | — | 0 |
| `roll_segment_mean_std_180` | 34 | 1.9183e-05 | 7.7812e-05 | 0.20125 | 0.99999 | 0.0023347 |
| `roll_mean_shift_180` | 34 | 4.3201e-05 | 0.00015926 | 0.37906 | 0.99999 | 0.0025702 |
| `roll_rms_early_60` | 34 | 2.9351e-05 | 9.9285e-05 | 0.0042691 | 1 | 4.2408e-05 |
| `roll_rms_late_60` | 34 | 5.1429e-05 | 0.00041883 | 0.007217 | 0.99998 | 7.3974e-05 |
| `roll_rms_ratio_180` | 34 | 9.1639e-05 | 0.0005777 | 0.0089627 | 0.99998 | 8.9791e-05 |
| `roll_rms_slope_180` | 34 | 3.1673e-05 | 0.00020079 | 0.46797 | 0.99998 | 0.0032291 |
| `roll_rms_trend_r2_180` | 34 | 0.0013347 | 0.0091313 | 0.60741 | 0.99998 | 0.0017398 |
| `roll_p95_trend_slope_180` | 34 | 0.00054861 | 0.0031913 | 4.0992 | 0.99972 | 0.039775 |
| `roll_period_est_180` | 34 | 0.2497 | 1.9156 | 23.714 | 0.67744 | 0.26987 |
| `roll_zero_crossings_180` | 34 | 17.088 | 31 | 14.659 | 0.99441 | 0.12519 |
| `roll_period_cv_180` | 34 | 0.13297 | 0.53775 | 6.8744 | 0.96134 | 0.073425 |
| `pitch_rms_60` | 46 | 3.1571e-05 | 0.00043133 | 0.0017994 | 1 | 1.7856e-05 |
| `pitch_std_60` | 46 | 2.8429e-05 | 0.00053357 | 0.082215 | 1 | 0.0016582 |
| `pitch_peak_to_peak_60` | 46 | 0.0020246 | 0.013824 | 0.75114 | 0.99992 | 0.029576 |
| `gyro_y_rms_60` | 0 | — | — | — | — | — |

Đây là sensitivity analysis trên segment đại diện, không phải bằng chứng cutoff nào tối ưu. Giai đoạn kế tiếp nên thử filter mạnh hơn/alternative Sampling Rate và so độ ổn định feature trên nhiều session, đồng thời cân nhắc attenuation gần Nyquist của baseline hiện hành.

## 7. Kiểm thử và tính tái lập

Lệnh: `python -m ml.features.run --config ml/features/config.yaml --dataset all`; tests: `18 passed in 0.52s`. Python `3.14.6`; NumPy `2.4.6`, pandas `3.0.3`, PyArrow `23.0.1`, SciPy `1.18.0`.
Raw/processed data phải có sẵn tại các đường dẫn trong README preprocessing; `ml/data/features/` bị gitignore. Các bảng feature có thể tái tạo từ CLI, notebook chỉ đọc feature outputs/summary.

## 8. Hạn chế và sẵn sàng labeling

Không có row đầy đủ 30 feature vì gyro canonical không được xác nhận hoặc không có ở ba nguồn. Hohai không đo gyro; Southampton Delta Angle không được xem là gyro; Seafar rate mapping còn cần xác nhận. Sau khi sửa lỗi gán đảo tín hiệu/timestamp, các feature chu kỳ có giá trị VALID trên phần lớn cửa sổ 180 giây; Seafar vẫn có một số cửa sổ thiếu crossing/period. Xem [rà soát chu kỳ và tập angle-only](feature_period_subset_review.md).
Bảng feature có validity riêng từng feature nên có thể bắt đầu chuẩn bị quy trình labeling có kiểm soát, nhưng chưa nên labeling tự động/huấn luyện cho đến khi nhóm duyệt công thức, mapping gyro và tiêu chí filter. Không chia các cửa sổ của cùng session qua train/test ngẫu nhiên.

## 9. Giải thích kỹ thuật phục vụ vấn đáp

**Em đã làm gì?** Trích xuất mỗi endpoint causal 10 giây từ Parquet theo segment. **Vì sao?** Tạo đặc trưng có timestamp và giữ ranh giới thử nghiệm. **Phương pháp?** Thống kê population, quantile Type-7, ba block 60 giây, hồi quy OLS và crossing nội suy. **Kết quả?** Xem bảng counts/availability/statistics thực ở trên. **Nếu bỏ qua validity?** Missing gyro hoặc cửa sổ thiếu dài có thể bị nhầm thành số 0/hợp lệ. **Giới hạn?** Các định nghĩa đang là proposal vận hành, period nhạy với noise/filter và gyro mapping chưa xác nhận.
