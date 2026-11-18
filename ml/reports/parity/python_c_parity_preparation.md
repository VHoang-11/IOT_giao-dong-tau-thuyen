# Chuẩn bị parity Python/C cho 23 feature

> **Phạm vi.** Gói này chuẩn bị kiểm chứng parity *tính feature* Python/C cho 23 angle feature của PoC Random Forest phân loại motion phenotype bằng proxy label — KHÔNG phải bộ phân loại an toàn hàng hải đã xác thực. Golden vector đã chuẩn bị KHÔNG có nghĩa parity Python/C hay triển khai ESP32 đã được kiểm chứng.

## Trạng thái: **PYTHON_REFERENCE_READY** · **C_PARITY_PENDING**

Chưa có đầu ra C/C++ thật nào được nộp (`ml/data/parity/c_results/` trống), nên **không có kết luận parity Python/C**. Mọi kết quả 'PASS' dưới đây là kiểm tra harness/dung sai bằng Python và được gắn nhãn tương ứng.

## 1. Ba mức kiểm chứng (tách bạch)

| Mức | Câu hỏi | Trạng thái hiện tại |
|---|---|---|
| Level 1 — tham chiếu Python đúng | Extractor tính đúng định nghĩa? | Đã kiểm: test `ml/features`, kiểm tra giải tích độc lập, cross-check feature table, test parity. |
| Level 2 — parity Python/C | C cho cùng số trên CÙNG chuỗi Roll/Pitch? | CHƯA CÓ kết quả C thật — C_PARITY_PENDING. |
| Level 3 — ESP32 cảm biến → mô hình | IMU thật + ước lượng góc + lọc cho feature cùng phân phối huấn luyện? | CHƯA ĐÁNH GIÁ. Level 2 không chứng minh Level 3; lệch miền do chuỗi lọc firmware đã đo: POS 188 -> 4 (esp32_feature_compatibility.md). |

**Level 2 không suy ra Level 3.** Báo cáo `ml/reports/ml/esp32_feature_compatibility.md` đã đo: khi tính lại 23 feature trên Roll/Pitch Hohai đi qua Butterworth bậc 2, 0,5 Hz (mô phỏng chuỗi lọc firmware hiện tại), số dự đoán POS của RF giảm từ **188** xuống **4** (1512 cửa sổ; 505 ABSTAIN vì feature ngoài miền huấn luyện). Một hiện thực C hoàn hảo về số học vẫn cho dự đoán sai nếu chuỗi Roll/Pitch đầu vào khác miền huấn luyện. Giới hạn này giữ nguyên.

## 2. Thiết kế dung sai (ĐỀ XUẤT KỸ THUẬT, chưa đo trên thiết bị)

Công thức: `abs(actual - expected) <= abs_floor + rel*abs(expected) + scale_rel*S`, trong đó S = max |x| trên các mẫu hữu hạn của tín hiệu/cửa sổ tương ứng (cột tolerance_scale trong golden). Tham số u32 = 2⁻²⁴ ≈ 5.96e-08.

Lý do có hạng `scale_rel·S`: sai số làm tròn float32 tỷ lệ với độ lớn **đầu vào**, không với giá trị đầu ra. Ví dụ std 0,007° của tín hiệu offset 10° (SYN31) có sai số tuyệt đối cỡ u·10, lớn hơn rất nhiều u·0,007. Một dung sai tương đối thuần theo giá trị sẽ đánh trượt C trung thực; một dung sai tuyệt đối chung (v0.1: 1e-3°) lại quá lỏng để bắt Type-6/Type-7 hay n/(n-1) ở biên độ nhỏ.

| Lớp | abs_floor | rel | scale_rel | Feature | Cơ sở |
|---|---|---|---|---|---|
| count_ratio | 1e-06 | 0.0 | 0.0 | `roll_dominant_sign_ratio_180` | Đếm dấu trên giá trị float32 chính xác; chỉ sai số chia. |
| difference_rms | 1e-07 | 2e-05 | 2e-06 | `roll_diff_rms_60` | Hiệu hai mẫu float32 kề nhau rồi RMS. |
| dispersion | 1e-07 | 2e-05 | 5e-05 | `pitch_std_60`, `roll_segment_mean_std_180`, `roll_std_60` | Phương sai có triệt tiêu khi \|mean\| >> std; hạng tỷ lệ theo biên độ đầu vào. Vẫn đủ chặt để phân biệt std quần thể/mẫu (lệch 8.3e-4 tương đối) ở tín hiệu mean 0. |
| extremum | 1e-09 | 2e-07 | 2e-07 | `pitch_peak_to_peak_60`, `roll_abs_max_60`, `roll_peak_to_peak_60` | Chọn đúng một giá trị float32 đầu vào (abs_max) hoặc một phép trừ (peak-to-peak): gần như chính xác. |
| mean | 1e-07 | 0.0 | 2e-05 | `roll_mean_180`, `roll_mean_60`, `roll_mean_abs_180` | Tổng N <= 1800 phần tử float32: sai số điển hình ~sqrt(N)·u ≈ 2.5e-6, chặn xấu N·u ≈ 1.1e-4 nếu cộng tuần tự; đề xuất C cộng dồn compensated/double. |
| mean_difference | 1e-07 | 0.0 | 4e-05 | `roll_mean_shift_180` | Hiệu hai mean block: cộng dồn sai số hai tổng. |
| quantile | 1e-09 | 1e-06 | 4e-06 | `roll_abs_p95_60`, `roll_iqr_60`, `roll_median_180` | Sắp xếp chính xác + một phép nội suy Type-7 (IQR thêm một phép trừ). Đủ chặt để bắt sai quy ước phân vị. |
| r_squared | 0.002 | 0.0 | 0.0 | `roll_rms_trend_r2_180` | Chỉ áp dụng khi SST/mean(r)^2 >= 1e-6; dưới mức đó R² ill-conditioned -> REVIEW. |
| ratio | 1e-09 | 5e-05 | 0.0 | `roll_rms_ratio_180` | Tỷ số hai RMS: sai số tương đối cộng dồn của tử và mẫu. |
| rms | 1e-07 | 2e-05 | 2e-06 | `pitch_rms_60`, `roll_rms_60`, `roll_rms_early_60`, `roll_rms_late_60` | Tổng bình phương dương, không triệt tiêu; sai số tương đối theo giá trị. |
| slope | 1e-07 | 1e-05 | 2e-05 | `roll_p95_trend_slope_180`, `roll_rms_slope_180` | OLS 3 điểm cách đều = (r3 - r1)/2 deg/phút; sai số theo biên độ đầu vào. |

Điều kiện REVIEW (không PASS/FAIL tự động):

- `roll_rms_ratio_180`: rms block đầu trong [eps/10, eps*10] -> REVIEW_ILL_CONDITIONED
- `roll_rms_trend_r2_180`: SST/mean(block_rms)^2 < 1e-06 -> REVIEW_ILL_CONDITIONED (giá trị và validity)

- Trạng thái phải trùng chính xác; feature không VALID phải có value rỗng/null; VALID mà NaN là FAIL.
- R² VALID ngoài [0, 1] luôn FAIL; feature không VALID có giá trị (kể cả 0) luôn FAIL; VALID mà NaN/rỗng luôn FAIL.

## 3. Hiệu chỉnh dung sai bằng mô phỏng float32 (KHÔNG phải kết quả C)

`ml/parity/float32_probe.py` mô phỏng cách một hiện thực C đơn giản tính trong float32: cộng tuần tự (không pairwise), std hai lượt, sắp xếp + Type-7, OLS 3 điểm. Chỉ số cửa sổ/validity cửa sổ lấy từ golden; probe chỉ đo phần số học. Kết quả gắn nhãn `FLOAT32_EMULATION_*`.

### Suite synthetic: **FLOAT32_EMULATION_PASS_WITH_REVIEW** — tỷ lệ sai số/cho phép lớn nhất 0.188

| # | Feature | Pass | Fail | Review | Max |Δ| | Max sai số tương đối | Max |Δ|/cho phép |
|---|---|---|---|---|---|---|---|
| 0 | `roll_rms_60` | 488 | 0 | 0 | 2.21e-06 | 1.23e-06 | 0.0528 |
| 1 | `roll_std_60` | 488 | 0 | 0 | 2.59e-06 | 3.82e-06 | 0.0166 |
| 2 | `roll_mean_60` | 488 | 0 | 0 | 1.46e-06 | 0.00209 | 0.0133 |
| 3 | `roll_peak_to_peak_60` | 488 | 0 | 0 | 4.77e-07 | 5.7e-08 | 0.188 |
| 4 | `roll_abs_p95_60` | 488 | 0 | 0 | 5.84e-07 | 2.2e-07 | 0.0399 |
| 5 | `roll_abs_max_60` | 488 | 0 | 0 | 0 | 0 | 0 |
| 6 | `roll_iqr_60` | 488 | 0 | 0 | 4.77e-07 | 3.4e-05 | 0.0147 |
| 7 | `roll_diff_rms_60` | 488 | 0 | 0 | 1.6e-07 | 1.69e-06 | 0.0102 |
| 8 | `roll_mean_180` | 488 | 0 | 0 | 1.64e-06 | 0.00566 | 0.0149 |
| 9 | `roll_median_180` | 488 | 0 | 0 | 5.96e-08 | 1.32e-06 | 0.00426 |
| 10 | `roll_mean_abs_180` | 488 | 0 | 0 | 3.31e-06 | 2.08e-06 | 0.0441 |
| 11 | `roll_dominant_sign_ratio_180` | 488 | 0 | 0 | 2.76e-08 | 4.87e-08 | 0.0276 |
| 12 | `roll_segment_mean_std_180` | 488 | 0 | 0 | 6.95e-07 | 117 | 0.00251 |
| 13 | `roll_mean_shift_180` | 488 | 0 | 0 | 1.52e-06 | 481 | 0.00688 |
| 14 | `roll_rms_early_60` | 488 | 0 | 0 | 2.21e-06 | 1.23e-06 | 0.0431 |
| 15 | `roll_rms_late_60` | 488 | 0 | 0 | 2.02e-06 | 5.14e-07 | 0.0225 |
| 16 | `roll_rms_ratio_180` | 488 | 0 | 0 | 2 | 1.42e-06 | 0.0284 |
| 17 | `roll_rms_slope_180` | 488 | 0 | 0 | 1.79e-06 | 0.000239 | 0.00975 |
| 18 | `roll_rms_trend_r2_180` | 487 | 0 | 1 | 1.07e-05 | 3.55e-05 | 0.00536 |
| 19 | `roll_p95_trend_slope_180` | 488 | 0 | 0 | 3.22e-07 | 1.39e-06 | 0.00434 |
| 20 | `pitch_rms_60` | 488 | 0 | 0 | 1.79e-06 | 4.46e-06 | 0.184 |
| 21 | `pitch_std_60` | 488 | 0 | 0 | 2.18e-06 | 3.82e-06 | 0.0347 |
| 22 | `pitch_peak_to_peak_60` | 488 | 0 | 0 | 0 | 0 | 0 |

Bản ghi REVIEW:

- `SYN30_permuted_blocks` endpoint 2100 `roll_rms_trend_r2_180`: golden UNDEFINED_MATHEMATICALLY, float32 VALID = 0.0.

### Suite real: **FLOAT32_EMULATION_PASS** — tỷ lệ sai số/cho phép lớn nhất 0.190

| # | Feature | Pass | Fail | Review | Max |Δ| | Max sai số tương đối | Max |Δ|/cho phép |
|---|---|---|---|---|---|---|---|
| 0 | `roll_rms_60` | 95 | 0 | 0 | 4.56e-06 | 1.34e-06 | 0.06 |
| 1 | `roll_std_60` | 95 | 0 | 0 | 2.51e-07 | 2.38e-06 | 0.00322 |
| 2 | `roll_mean_60` | 95 | 0 | 0 | 7.56e-06 | 2.01e-06 | 0.0888 |
| 3 | `roll_peak_to_peak_60` | 95 | 0 | 0 | 1.19e-07 | 5.58e-08 | 0.181 |
| 4 | `roll_abs_p95_60` | 95 | 0 | 0 | 2.44e-07 | 3.46e-07 | 0.0468 |
| 5 | `roll_abs_max_60` | 95 | 0 | 0 | 0 | 0 | 0 |
| 6 | `roll_iqr_60` | 95 | 0 | 0 | 5.96e-08 | 1.78e-06 | 0.0151 |
| 7 | `roll_diff_rms_60` | 95 | 0 | 0 | 7.17e-08 | 2.46e-06 | 0.0123 |
| 8 | `roll_mean_180` | 95 | 0 | 0 | 1.21e-05 | 3.64e-06 | 0.143 |
| 9 | `roll_median_180` | 95 | 0 | 0 | 2.98e-08 | 5.09e-08 | 0.00719 |
| 10 | `roll_mean_abs_180` | 95 | 0 | 0 | 1.21e-05 | 3.64e-06 | 0.143 |
| 11 | `roll_dominant_sign_ratio_180` | 95 | 0 | 0 | 2.97e-08 | 5.18e-08 | 0.0297 |
| 12 | `roll_segment_mean_std_180` | 95 | 0 | 0 | 2.76e-06 | 4.8e-05 | 0.0127 |
| 13 | `roll_mean_shift_180` | 95 | 0 | 0 | 7.11e-06 | 0.000173 | 0.0475 |
| 14 | `roll_rms_early_60` | 95 | 0 | 0 | 2.72e-06 | 7.77e-07 | 0.035 |
| 15 | `roll_rms_late_60` | 95 | 0 | 0 | 4.56e-06 | 1.34e-06 | 0.0595 |
| 16 | `roll_rms_ratio_180` | 95 | 0 | 0 | 2.06e-06 | 1.93e-06 | 0.0386 |
| 17 | `roll_rms_slope_180` | 95 | 0 | 0 | 3.16e-06 | 2.87e-05 | 0.0367 |
| 18 | `roll_rms_trend_r2_180` | 95 | 0 | 0 | 1.43e-05 | 4.76e-05 | 0.00716 |
| 19 | `roll_p95_trend_slope_180` | 95 | 0 | 0 | 1.18e-07 | 1.31e-05 | 0.00415 |
| 20 | `pitch_rms_60` | 95 | 0 | 0 | 1.77e-06 | 2.17e-06 | 0.0974 |
| 21 | `pitch_std_60` | 95 | 0 | 0 | 1.61e-07 | 3.23e-06 | 0.00324 |
| 22 | `pitch_peak_to_peak_60` | 95 | 0 | 0 | 2.98e-08 | 5.92e-08 | 0.19 |

Diễn giải: tỷ lệ sai số/cho phép lớn nhất của mô phỏng float32 là synthetic 0.188, real 0.190 (biên an toàn ≈ 5.3 lần), tức dung sai không đánh trượt một hiện thực float32 hợp lý. Bản ghi REVIEW của `SYN30_permuted_blocks` tái hiện rủi ro C03: ba block là hoán vị của cùng 600 giá trị; RMS block theo Python (`math.fsum`, không phụ thuộc thứ tự) = 1.490180883822287, 1.490180883822287, 1.490180883822287 → SST = 0 → UNDEFINED; float32 cộng tuần tự = 1.4901810884475708, 1.4901807308197021, 1.4901812076568604 → SST = 1.28e-13 > 1e-15 → VALID với R² không có ý nghĩa vật lý. Khuyến nghị: C cộng dồn bằng double, và nhóm chốt ngưỡng SST tương đối.

## 4. Ma trận phát hiện lỗi hiện thực C điển hình

Mọi đột biến đều phải bị phát hiện: **đạt**.

| Đột biến | Mô tả | Kết luận harness | Bản ghi FAIL | Case phát hiện | Feature FAIL |
|---|---|---|---|---|---|
| `sample_std_ddof1` | std mẫu (chia n-1) thay vì std quần thể | FLOAT32_EMULATION_FAIL | 589 | 26 | `roll_std_60`, `roll_segment_mean_std_180`, `pitch_std_60` |
| `quantile_nearest_rank` | phân vị nearest-rank thay vì Type-7 | FLOAT32_EMULATION_FAIL | 586 | 26 | `roll_abs_p95_60`, `roll_iqr_60`, `roll_median_180`, `roll_p95_trend_slope_180` |
| `quantile_type6` | phân vị Type-6 h=(n+1)p thay vì Type-7 | FLOAT32_EMULATION_FAIL | 529 | 25 | `roll_abs_p95_60`, `roll_iqr_60`, `roll_p95_trend_slope_180` |
| `window_includes_lower_bound` | cửa sổ [t-W, t) (lệch 1 mẫu) thay vì (t-W, t] | FLOAT32_EMULATION_FAIL | 929 | 17 | `roll_rms_60`, `roll_std_60`, `roll_mean_60`, `roll_peak_to_peak_60`, `roll_abs_p95_60`, `roll_abs_max_60` … |
| `radians_input` | dùng Roll/Pitch theo radian | FLOAT32_EMULATION_FAIL | 4473 | 30 | `roll_rms_60`, `roll_std_60`, `roll_mean_60`, `roll_peak_to_peak_60`, `roll_abs_p95_60`, `roll_abs_max_60` … |
| `diff_per_second` | roll_diff_rms_60 chia cho dt (deg/s) thay vì deg/mẫu | FLOAT32_EMULATION_FAIL | 398 | 27 | `roll_diff_rms_60` |
| `slope_per_second` | slope không nhân 60 (deg/s thay vì deg/phút) | FLOAT32_EMULATION_FAIL | 95 | 14 | `roll_rms_slope_180`, `roll_p95_trend_slope_180` |
| `p95_without_abs` | P95 trên x thay vì \|x\| | FLOAT32_EMULATION_FAIL | 333 | 20 | `roll_abs_p95_60`, `roll_p95_trend_slope_180` |
| `centered_rms` | RMS quanh mean (thực chất là std) thay vì RMS gồm offset | FLOAT32_EMULATION_FAIL | 486 | 15 | `roll_rms_60`, `roll_rms_early_60`, `roll_rms_late_60`, `roll_rms_ratio_180`, `roll_rms_slope_180`, `roll_rms_trend_r2_180` … |
| `swap_roll_pitch_rms` | đảo vị trí roll_rms_60 (0) và pitch_rms_60 (20) | FLOAT32_EMULATION_FAIL | 916 | 30 | `roll_rms_60`, `pitch_rms_60` |
| `invalid_as_zero` | feature không VALID được xuất VALID = 0 | FLOAT32_EMULATION_FAIL | 4663 | 31 | `roll_rms_60`, `roll_std_60`, `roll_mean_60`, `roll_peak_to_peak_60`, `roll_abs_p95_60`, `roll_abs_max_60` … |
| `sign_ratio_counts_zero_as_positive` | đếm số 0 tuyệt đối là dương | FLOAT32_EMULATION_FAIL | 16 | 4 | `roll_dominant_sign_ratio_180` |
| `one_pass_variance` | phương sai một lượt E[x²]-E[x]² trong float32 (không ổn định) | FLOAT32_EMULATION_FAIL | 32 | 1 | `roll_std_60`, `pitch_std_60` |
| `ratio_without_epsilon` | roll_rms_ratio_180 chỉ kiểm tra rms_early > 0, bỏ epsilon 1e-9 | FLOAT32_EMULATION_FAIL | 4 | 1 | `roll_rms_ratio_180` |
| `r2_zero_when_undefined` | R² = 0 VALID khi SST <= ngưỡng thay vì UNDEFINED | FLOAT32_EMULATION_FAIL | 8 | 2 | `roll_rms_trend_r2_180` |

## 5. Kịch bản file đầu ra hỏng (harness phải từ chối)

Tất cả xử lý đúng: **đạt**.

| Kịch bản | Kết quả mong đợi | Kết luận | Đếm lỗi |
|---|---|---|---|
| missing_case | MISSING | PYTHON_SELF_CONSISTENCY_FAIL | {'MISSING': 368} |
| missing_rows | MISSING | PYTHON_SELF_CONSISTENCY_FAIL | {'MISSING': 3} |
| duplicate_rows | DUPLICATE | PYTHON_SELF_CONSISTENCY_FAIL | {'DUPLICATE': 2} |
| extra_case | EXTRA | PYTHON_SELF_CONSISTENCY_FAIL | {'EXTRA': 1} |
| wrong_input_sha256 | FAIL_INPUT_SHA256 | PYTHON_SELF_CONSISTENCY_FAIL | {'FAIL_INPUT_SHA256': 368} |
| wrong_schema_version | FAIL_SCHEMA_VERSION | PYTHON_SELF_CONSISTENCY_FAIL | {'FAIL_SCHEMA_VERSION': 1} |
| feature_names_shifted_by_one | FAIL_FEATURE_NAME_ORDER | PYTHON_SELF_CONSISTENCY_FAIL | {'FAIL_FEATURE_NAME_ORDER': 23} |
| nan_reported_as_valid | FAIL_VALID_NOT_FINITE | PYTHON_SELF_CONSISTENCY_FAIL | {'FAIL_VALID_NOT_FINITE': 1} |
| empty_value_reported_as_valid | FAIL_VALID_NOT_FINITE | PYTHON_SELF_CONSISTENCY_FAIL | {'FAIL_VALID_NOT_FINITE': 1} |
| invalid_written_as_zero | FAIL_INVALID_HAS_VALUE | PYTHON_SELF_CONSISTENCY_FAIL | {'FAIL_INVALID_HAS_VALUE': 1} |
| status_flipped | FAIL_STATUS_MISMATCH | PYTHON_SELF_CONSISTENCY_FAIL | {'FAIL_STATUS_MISMATCH': 1} |
| unknown_status | FAIL_UNKNOWN_STATUS | PYTHON_SELF_CONSISTENCY_FAIL | {'FAIL_UNKNOWN_STATUS': 1} |
| endpoint_time_shifted | FAIL_ENDPOINT_TIME | PYTHON_SELF_CONSISTENCY_FAIL | {'FAIL_ENDPOINT_TIME': 1} |
| value_outside_tolerance | FAIL_VALUE_TOLERANCE | PYTHON_SELF_CONSISTENCY_FAIL | {'FAIL_VALUE_TOLERANCE': 1} |
| value_inside_tolerance | PASS | PYTHON_SELF_CONSISTENCY_PASS | — |

## 6. Harness và định dạng trao đổi

- `python -m ml.parity.compare --suite synthetic --candidate <c_output.csv|jsonl> --metadata <metadata.json> --out <thư mục>`
- Kiểm tra: schema_version, số feature/thứ tự (tên khớp index), case_id, input_sha256, endpoint_index/endpoint_time hữu hạn, bản ghi thiếu/thừa/trùng, từ vựng status, mã hóa giá trị, dung sai theo feature, so khớp status, R² ∈ [0,1]; schema/manifest metadata sai → `FAIL_METADATA`; reason_code chỉ cảnh báo.
- Xuất `comparison_rows.csv` (mỗi bản ghi: giá trị Python, giá trị C, |Δ|, sai số tương đối, cho phép, kết luận), `comparison_summary.json`, `comparison_report.md`.
- Nhãn kết luận theo `producer.kind`: chỉ `independent_c_implementation` mới cho `C_PARITY_*`. Harness không thể tự xác minh nguồn gốc — M1 phải kèm `source_commit`, trình biên dịch và cờ để người duyệt đối chiếu.
- Manifest: 44 file, lỗi checksum: 0.

## 7. Hạn chế

- Dung sai là đề xuất từ phân tích làm tròn + mô phỏng; chưa có số đo từ trình biên dịch Xtensa/ESP32 (có `madd.s` fused multiply-add) hay từ mã C thật.
- Probe float32 dùng validity cửa sổ của golden nên KHÔNG kiểm tra logic coverage/gap của C; golden synthetic (SYN20–SYN27) mới kiểm tra phần đó.
- Các issue C01–C04 còn mở: nếu nhóm đổi quyết định, phải tăng phiên bản contract, sinh lại golden và (nếu công thức đổi) huấn luyện lại RF.

## Giải thích kỹ thuật phục vụ vấn đáp cá nhân

- **Vì sao không dùng một dung sai chung?** Các feature có độ nhạy khác nhau: max/peak-to-peak chỉ chọn lại giá trị đầu vào (gần như chính xác), mean/std tích lũy sai số theo N và theo biên độ, R² có thể ill-conditioned vô hạn khi SST → 0.
- **Tại sao mô phỏng float32 mà vẫn nói chưa có parity?** Mô phỏng chỉ trả lời 'dung sai có hợp lý không' và 'harness có bắt lỗi không'. Parity là tính chất của *mã C thật* với *trình biên dịch thật*; không thể chứng minh bằng mã Python.
- **REVIEW khác FAIL thế nào?** REVIEW dành cho bài toán ill-conditioned (R² khi SST rất nhỏ, ratio sát epsilon): hai hiện thực đúng có thể ra quyết định khác nhau chỉ vì làm tròn. Người duyệt xem giá trị/điều kiện, không tự động đánh rớt.
- **Tại sao FAIL khi C ghi 0 cho feature không hợp lệ?** Vì 0 là giá trị có nghĩa (ví dụ std = 0 của tín hiệu hằng). Đổi 'không xác định' thành 0 có thể đẩy mô hình về NORMAL — trái nguyên tắc an toàn 'lỗi → UNKNOWN, không NORMAL'.
