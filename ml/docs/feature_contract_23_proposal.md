# Đề xuất contract `svmg-angle23` 0.1.0-proposal

**Trạng thái:** `PROPOSAL_PENDING_M1_REVIEW` — đề xuất cho M1, chưa thay thế contract hiện hành. Các file sau KHÔNG bị chỉnh sửa: `contracts/features.md`, `core/include/svmg_core.h`, `core/include/svmg_features.h`.

- Nguồn công thức: ml/docs/feature_specification_30.md + ml/features/extractor.py (feature_extractor_version 0.1.0).
- Lấy mẫu 10.0 Hz; endpoint `(t-W, t]`; cập nhật mỗi 10.0 s; 3 block 60 s không chồng lấn, cũ -> mới, (lower, upper].
- Hợp lệ: ≥ 95% mẫu, gap ≤ 1.5 chu kỳ; Không thay bằng 0; mỗi feature có cờ validity; vector thiếu -> ABSTAIN/UNKNOWN, không NORMAL.
- Kiểu dữ liệu: float32 trên ESP32; tham chiếu float64 Python. Bản máy đọc được: `ml/docs/feature_contract_23_v0.1.json`.

| Index | Feature | Spec ID | Tín hiệu | Cửa sổ (s) | Đơn vị | Định nghĩa |
|---:|---|---:|---|---:|---|---|
| 0 | `roll_rms_60` | 0 | roll | 60 | deg | sqrt(mean(x^2)) trên (t-60,t] |
| 1 | `roll_std_60` | 1 | roll | 60 | deg | độ lệch chuẩn quần thể (mẫu số n) |
| 2 | `roll_mean_60` | 2 | roll | 60 | deg | mean(x) |
| 3 | `roll_peak_to_peak_60` | 3 | roll | 60 | deg | max(x)-min(x) |
| 4 | `roll_abs_p95_60` | 4 | roll | 60 | deg | phân vị Type-7 0.95 của |x| |
| 5 | `roll_abs_max_60` | 5 | roll | 60 | deg | max(|x|) |
| 6 | `roll_iqr_60` | 6 | roll | 60 | deg | Q0.75-Q0.25 Type-7 |
| 7 | `roll_diff_rms_60` | 7 | roll | 60 | deg/sample @10 Hz | RMS sai phân bậc 1 giữa mẫu kề đúng chu kỳ 0.1 s |
| 8 | `roll_mean_180` | 11 | roll | 180 | deg | mean(x) |
| 9 | `roll_median_180` | 12 | roll | 180 | deg | Q0.50 Type-7 |
| 10 | `roll_mean_abs_180` | 13 | roll | 180 | deg | mean(|x|) |
| 11 | `roll_dominant_sign_ratio_180` | 14 | roll | 180 | 1 | max(n+,n-)/(n++n-), bỏ số 0 tuyệt đối |
| 12 | `roll_segment_mean_std_180` | 15 | roll | 180 | deg | std quần thể của 3 mean block 60 s |
| 13 | `roll_mean_shift_180` | 16 | roll | 180 | deg | mean(block 3) - mean(block 1) |
| 14 | `roll_rms_early_60` | 17 | roll | 180 | deg | RMS block 60 s cũ nhất |
| 15 | `roll_rms_late_60` | 18 | roll | 180 | deg | RMS block 60 s mới nhất (trùng số học với roll_rms_60) |
| 16 | `roll_rms_ratio_180` | 19 | roll | 180 | 1 | rms_late/rms_early; không xác định nếu rms_early <= 1e-9 |
| 17 | `roll_rms_slope_180` | 20 | roll | 180 | deg/min | độ dốc OLS của 3 RMS block theo tâm [30,90,150] s, x60 |
| 18 | `roll_rms_trend_r2_180` | 21 | roll | 180 | 1 | R^2 của hồi quy 3 điểm; không xác định nếu SST=0 |
| 19 | `roll_p95_trend_slope_180` | 22 | roll | 180 | deg/min | độ dốc OLS của P95|x| 3 block, x60 |
| 20 | `pitch_rms_60` | 26 | pitch | 60 | deg | sqrt(mean(p^2)) |
| 21 | `pitch_std_60` | 27 | pitch | 60 | deg | độ lệch chuẩn quần thể |
| 22 | `pitch_peak_to_peak_60` | 28 | pitch | 60 | deg | max(p)-min(p) |

Dung sai parity đề xuất: tuyệt đối 0.001°, tương đối 0.0001. Đề xuất ban đầu cho float32 vs float64; cần M1/M2 chốt sau khi chạy golden vectors.
