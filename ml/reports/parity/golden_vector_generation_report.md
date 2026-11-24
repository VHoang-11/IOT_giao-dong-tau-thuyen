# Báo cáo sinh golden vector 23 feature

> **Phạm vi.** Gói này chuẩn bị kiểm chứng parity *tính feature* Python/C cho 23 angle feature của PoC Random Forest phân loại motion phenotype bằng proxy label — KHÔNG phải bộ phân loại an toàn hàng hải đã xác thực. Golden vector đã chuẩn bị KHÔNG có nghĩa parity Python/C hay triển khai ESP32 đã được kiểm chứng.

- Lệnh: `python -m ml.parity.golden --suite all` (chạy từ repository root, `.venv`). Không có dấu thời gian trong file: chạy lại cho byte giống hệt (đã kiểm tra bằng test `test_deterministic_generation_matches_tracked_fixtures`).
- Môi trường: Python 3.14.10, NumPy 2.4.6, pandas 3.0.3.
- Contract: `ml/docs/feature_contract_23_v0.2.json` (sha256 `36a7e59b270a3127…`); schema `svmg-angle23-0.2.0-proposal`.
- Trạng thái: **PYTHON_REFERENCE_READY / C_PARITY_PENDING**.

## 1. Cách sinh

1. Tín hiệu đầu vào được làm tròn về float32 và lưu dạng chuỗi float32 ngắn nhất round-trip; C đọc bằng `strtof` sẽ được đúng cùng bit.
2. Golden được tính bằng **extractor production** (`ml.features.extractor.extract_segment`) trên chính các byte đã lưu (đọc lại file trước khi tính), không bằng một thư viện công thức thứ hai.
3. Với case synthetic, `ml/parity/analytic.py` suy ra đáp án bằng **công thức đóng độc lập** (không import extractor) để bắt lỗi chung giữa tài liệu và mã.
4. Với case real, golden được đối chiếu với feature table đã có trong `ml/data/features` (cùng extractor) để bắt lỗi cắt đoạn/ranh giới.
5. Mọi file được băm SHA-256 trong `ml/parity/fixtures/manifest.json`.

## 2. Cấu trúc fixture

```text
ml/parity/fixtures/                      (theo dõi bằng Git, nhỏ, không nhạy cảm)
  manifest.json                          checksum + tóm tắt kiểm tra
  tolerance_spec.json                    dung sai theo feature (đề xuất)
  interchange_format.json                định dạng đầu ra C phải xuất
  synthetic/inputs/<case_id>.csv         sample_index,time_seconds,roll_deg,pitch_deg,source_sample_index
  synthetic/expected_features.csv        golden dạng dài: 1 dòng/(case, endpoint, feature)
  synthetic/golden_vectors.jsonl         golden dạng vector 23 phần tử/(case, endpoint)
  synthetic/cases.json                   metadata case: endpoint, chỉ số cửa sổ/block, thang dung sai, cờ điều kiện, kiểm tra giải tích
ml/data/parity/real/                     (gitignored: trích từ dữ liệu processed cục bộ)
  inputs/*.csv, expected_features.csv, golden_vectors.jsonl, cases.json
```

| File theo dõi Git | Byte | SHA-256 (16 ký tự đầu) |
|---|---|---|
| `ml/parity/fixtures/interchange_format.json` | 4284 | 2b79f0e48d2a90b3 |
| `ml/parity/fixtures/synthetic/cases.json` | 253245 | c18b84a17099ac84 |
| `ml/parity/fixtures/synthetic/expected_features.csv` | 1223260 | 97390d5ed492b550 |
| `ml/parity/fixtures/synthetic/golden_vectors.jsonl` | 751549 | 5fedb2eda8b19d89 |
| `ml/parity/fixtures/tolerance_spec.json` | 4996 | 7213f2436e0034b0 |

Cộng thêm 31 file input synthetic (2,031,431 byte). Real-data: 8 file, chỉ lưu cục bộ (gitignored).

## 3. Case synthetic — tín hiệu kiểm thử SỐ HỌC (không phải dữ liệu hàng hải tổng hợp)

| Case | Mô tả | Phát hiện | Mẫu | Endpoint | NaN/Inf Roll | Timestamp bỏ | Kiểm tra giải tích |
|---|---|---|---|---|---|---|---|
| `SYN01_const_zero` | Roll/Pitch hằng 0 | division_by_zero, undefined_status, sign_zero | 2101 | 16 | 0 | 0 | 23/23 |
| `SYN02_const_roll_pos` | Roll hằng +3° | offset_sign, zero_variance, r2_undefined | 2101 | 16 | 0 | 0 | 19/19 |
| `SYN03_const_roll_neg_pitch_pos` | Roll hằng -2.5°, Pitch hằng +1.25° | sign_handling, mean_abs | 2101 | 16 | 0 | 0 | 0/0 |
| `SYN04_sine_roll` | Roll sin 5°, 0.1 Hz, số chu kỳ nguyên | variance_convention, diff_rms, sign_ratio_half | 2101 | 16 | 0 | 0 | 9/9 |
| `SYN05_sine_pitch` | Pitch sin 2°, 0.2 Hz | pitch_channel, feature_order | 2101 | 16 | 0 | 0 | 2/2 |
| `SYN06_mixed_order_detector` | Roll/Pitch hỗn hợp: 23 giá trị đôi một khác nhau | feature_order, units, channel_swap | 2101 | 16 | 0 | 0 | 0/0 |
| `SYN07_growing_amplitude` | Biên độ Roll tăng tuyến tính | trend_slope, ratio | 2101 | 16 | 0 | 0 | 0/0 |
| `SYN08_decreasing_amplitude` | Biên độ Roll giảm tuyến tính | negative_slope, ratio_below_one | 2101 | 16 | 0 | 0 | 0/0 |
| `SYN09_block_step_linear` | Biên độ theo block 1, 2, 3 (R² = 1) | block_boundaries, trend_units, r2_one | 2101 | 16 | 0 | 0 | 6/6 |
| `SYN10_block_step_nonlinear` | Biên độ theo block 1, 3, 2 (R² = 0.25) | r2_formula, block_order | 2101 | 16 | 0 | 0 | 6/6 |
| `SYN11_offset_constant_amplitude` | Offset 2° + sin 1° biên độ không đổi | cancellation, r2_ill_conditioned | 2101 | 16 | 0 | 0 | 0/0 |
| `SYN12_spike_window_boundaries` | Gai +10° tại t=150 s, -8° tại t=90 s | half_open_window, block_boundary, extrema | 2101 | 16 | 0 | 0 | 0/0 |
| `SYN13_ramp_quantiles` | Ramp 0.5 + k/256 (chính xác float32) | quantile_interpolation, median, iqr, mean_shift | 2101 | 16 | 0 | 0 | 17/17 |
| `SYN14_square_wave_quantile_discontinuity` | Sóng vuông ±1 (10 mẫu) | quantile_interpolation_at_tie, diff_pairs | 2101 | 16 | 0 | 0 | 8/8 |
| `SYN15_low_amplitude` | Biến thiên rất nhỏ quanh 0 (1e-4°) | relative_tolerance, near_zero | 2101 | 16 | 0 | 0 | 0/0 |
| `SYN16_sign_with_exact_zeros` | Mẫu +1/-1/0 chính xác | exact_zero_sign_semantics | 2101 | 16 | 0 | 0 | 1/1 |
| `SYN17_zero_early_block` | Block đầu bằng 0, sau đó sin | ratio_division_by_zero, slope_valid | 2101 | 16 | 0 | 0 | 3/3 |
| `SYN18_epsilon_below` | Block đầu biên độ 1e-10° (< epsilon) | epsilon_rule | 2101 | 16 | 0 | 0 | 1/1 |
| `SYN19_epsilon_above` | Block đầu biên độ 1e-7° (> epsilon) | epsilon_rule, large_ratio | 2101 | 16 | 0 | 0 | 1/1 |
| `SYN20_insufficient_history` | Chỉ 150 s lịch sử | warmup, insufficient_window | 1501 | 10 | 0 | 0 | 2/2 |
| `SYN21_isolated_nan` | 20 NaN rời rạc trong 60 s cuối | missing_values, diff_pair_coverage | 2101 | 16 | 20 | 0 | 0/0 |
| `SYN22_nan_excess` | 40 NaN liên tiếp (> 5% của 60 s) | signal_coverage, block_coverage | 2101 | 16 | 40 | 0 | 4/4 |
| `SYN23_timestamp_gap` | Bỏ 4 timestamp t=195.2..195.5 s (gap 0.5 s nằm trong cửa sổ cuối) | timestamp_gap, endpoint_anchor | 2097 | 15 | 0 | 4 | 2/2 |
| `SYN24_single_dropped_sample` | Bỏ 1 timestamp tại t=200 s | timestamp_gap, nan_vs_dropped_semantics | 2100 | 15 | 0 | 1 | 2/2 |
| `SYN25_large_amplitude_units` | Roll 20°, Pitch 8° (phát hiện nhầm rad/deg) | units | 2101 | 16 | 0 | 0 | 0/0 |
| `SYN26_infinite_values` | +Inf và -Inf trong Roll | non_finite_handling | 2101 | 16 | 2 | 0 | 2/2 |
| `SYN27_block_coverage_rule` | 40 NaN chỉ trong block đầu (issue C01) | block_validity_rule | 2101 | 16 | 40 | 0 | 3/3 |
| `SYN28_negative_offset_sine` | -1.5° + sin 0.5° (luôn âm) | sign_handling, negative_mean | 2101 | 16 | 0 | 0 | 0/0 |
| `SYN29_block_step_symmetric` | Biên độ theo block 1, 2, 1 (slope 0, R² = 0 VALID) | r2_zero_vs_undefined, slope_zero | 2101 | 16 | 0 | 0 | 6/6 |
| `SYN30_permuted_blocks` | 3 block 60 s là hoán vị của cùng 600 giá trị (SST đúng = 0) | r2_threshold_float32, accumulation_order, ratio_exactly_one | 2101 | 16 | 0 | 0 | 6/6 |
| `SYN31_large_offset_small_variation` | Roll 10° + sin 0.01°, Pitch -5° + sin 0.005° (nghiêng tĩnh) | variance_cancellation, one_pass_variance, near_zero_relative | 2101 | 16 | 0 | 0 | 0/0 |

### Phân bố trạng thái trong golden synthetic

| Status | Reason code | Bản ghi |
|---|---|---|
| INSUFFICIENT_WINDOW | WINDOW_HISTORY_SHORT | 4440 |
| INVALID_INPUT | ADJACENT_PAIR_COVERAGE | 2 |
| INVALID_INPUT | SEGMENT_BLOCK_COVERAGE | 64 |
| INVALID_INPUT | SIGNAL_VALID_COVERAGE | 80 |
| INVALID_INPUT | TIMESTAMP_GAP | 46 |
| UNDEFINED_MATHEMATICALLY | CONSTANT_RMS_TREND | 53 |
| UNDEFINED_MATHEMATICALLY | EARLY_RMS_AT_OR_BELOW_EPSILON | 16 |
| UNDEFINED_MATHEMATICALLY | NON_FINITE_RESULT | 8 |
| VALID | — | 6515 |

Kiểm tra giải tích độc lập: **123/123 đạt**; thất bại: không. Ví dụ: std quần thể của sine 5° = 5/√2; Type-7 P95 của ramp = x_min + 0,95·599·bước; RMS sai phân của sine dùng 599 cặp (không phải 600); R² của RMS block (1,2,3)/√2 = 1, (1,3,2)/√2 = 0,25, (1,2,1)/√2 = 0 (VALID, khác UNDEFINED).

Cờ điều kiện số (`condition_flag`) đánh dấu golden mà quyết định/giá trị phụ thuộc làm tròn: `ILL_CONDITIONED_R2` khi SST/mean(r)² < 1e-6, `NEAR_EPSILON_RATIO` khi rms_early trong [ε/10, 10ε].

## 4. Case dữ liệu thật

Golden real-data chưa được sinh trên máy này (cần `ml/data/processed` và `ml/data/features`).

## 5. Hạn chế

- Golden chỉ chứng minh *tính feature trên chuỗi Roll/Pitch cho sẵn* (Level 1 → chuẩn bị Level 2). Không nói gì về cách ESP32 ước lượng Roll/Pitch (Level 3).
- Kiểm tra giải tích độc lập chỉ phủ các case có đáp án đóng; các case khác dựa vào extractor + test của module `ml/features`.
- 5 đoạn real-data là mẫu đại diện tất định, không phải đánh giá thống kê toàn bộ dataset.

## Giải thích kỹ thuật phục vụ vấn đáp cá nhân

- **Tại sao không viết lại công thức để sinh golden?** Hai bản hiện thực do cùng một người viết dễ mắc cùng một lỗi hiểu sai; golden phải là đúng con số mà RF đã thấy khi huấn luyện, nên lấy thẳng từ extractor production. Kiểm tra độc lập được làm bằng *công thức đóng* trên tín hiệu có đáp án.
- **Tại sao lưu input dạng float32?** ESP32 lưu Roll/Pitch float32. Nếu golden tính từ float64 rồi C đọc float32, phần sai lệch do *đầu vào* sẽ lẫn vào sai lệch do *thuật toán*. Làm tròn trước giúp hai bên dùng đúng cùng bit đầu vào.
- **Tại sao có cả CSV dài và JSONL vector?** CSV dài dễ diff/lọc theo feature và mang tên feature; JSONL vector đúng là định dạng C xuất ra mỗi 10 s.
- **Synthetic có phải dữ liệu huấn luyện giả?** Không. Đây là fixture toán học (hằng, sine, ramp, gai, NaN, gap…) chỉ để kiểm tra tính toán; không dùng để huấn luyện hay đánh giá mô hình.
