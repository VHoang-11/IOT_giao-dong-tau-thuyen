# Hướng dẫn tích hợp 23 feature cho M1 (Hoàng và nhóm firmware)

> **Phạm vi.** Gói này chuẩn bị kiểm chứng parity *tính feature* Python/C cho 23 angle feature của PoC Random Forest phân loại motion phenotype bằng proxy label — KHÔNG phải bộ phân loại an toàn hàng hải đã xác thực. Golden vector đã chuẩn bị KHÔNG có nghĩa parity Python/C hay triển khai ESP32 đã được kiểm chứng.

- Contract: `ml/docs/feature_contract_23_v0.2.json` — `svmg-angle23-0.2.0-proposal`, trạng thái `PROPOSAL_PENDING_M1_REVIEW`; SHA-256 thứ tự tên `060095dd1f6bf4264fdf1d95e601fe66880837cde08ec5896e35a67f7ff8a1c8`.
- Contract C hiện hành (`contracts/features.md`, `core/include/svmg_core.h`, `core/include/svmg_features.h`) **không bị sửa**. Việc thêm vector 23 feature vào C là quyết định của M1 sau khi duyệt đề xuất này.
- Trạng thái hiện tại: **PYTHON_REFERENCE_READY / C_PARITY_PENDING**. Golden đã sẵn sàng; parity Python/C chưa được kiểm chứng vì chưa có đầu ra C.

## 1. Tín hiệu đầu vào

| Trường | Kiểu | Đơn vị | Quy ước |
|---|---|---|---|
| `time_seconds` | float64 (C: double hoặc bộ đếm mẫu) | giây | tăng nghiêm ngặt trong một segment; nhịp danh định 0,1 s |
| `roll_deg` | float32 | độ | góc lắc ngang; NaN/±Inf = mẫu lỗi có timestamp |
| `pitch_deg` | float32 | độ | góc lắc dọc; NaN/±Inf = mẫu lỗi có timestamp |

- **Lấy mẫu:** 10 Hz đều. Feature `roll_diff_rms_60` có đơn vị deg/mẫu nên **phụ thuộc trực tiếp** vào 10 Hz; không tính ở 20 Hz hay 2 Hz rồi quy đổi.
- **Mẫu lỗi:** khuyến nghị giữ nhịp 10 Hz và ghi NaN (≤ 5% cửa sổ vẫn hợp lệ cho thống kê từng điểm). Bỏ hẳn timestamp tạo gap > 0,15 s làm MỌI cửa sổ chứa nó INVALID_INPUT/TIMESTAMP_GAP (issue C04).
- **Trục và dấu:** golden kiểm tra phép tính trên chuỗi số cho sẵn; dấu dương của Roll/Pitch trên ESP32 (`svmg_filter.h`: roll = atan2(ay, az), pitch = atan2(-ax, √(ay²+az²))) và mốc 0 sau hiệu chuẩn thuộc Level 3, cần M1 xác nhận khớp quy ước dataset trước khi dùng mô hình.
- **Segment:** cửa sổ không được vượt ranh giới phiên/khởi động lại; sau reboot, đếm warm-up lại từ đầu.

## 2. Cửa sổ, endpoint, warm-up

- Endpoint e (thời điểm tính) là một mẫu; cửa sổ W chứa mẫu i khi `t_e - W < t_i ≤ t_e`. Ở 10 Hz không gap: 60 s = chỉ số `[k_e-599, k_e]`, 180 s = `[k_e-1799, k_e]`.
- 3 block của cửa sổ 180 s (cũ → mới): `(t-180, t-120]`, `(t-120, t-60]`, `(t-60, t]` — mỗi block 600 mẫu.
- Lưới endpoint: chỉ số mẫu 600, 700, 800, … tính từ mẫu đầu segment (mỗi 10 s). Golden liệt kê `endpoint_index` cho từng case; C phải tính đúng tại các chỉ số đó.
- Warm-up: < 60 s → mọi feature INSUFFICIENT_WINDOW; 60–180 s → 11 feature 60 s có thể VALID, 12 feature 180 s là INSUFFICIENT_WINDOW. Chỉ khi đủ 23 VALID mới đưa vào RF; nếu thiếu → ABSTAIN/UNKNOWN, KHÔNG NORMAL.

## 3. Thứ tự 23 feature và định nghĩa số học

`feature_index` là 0-based (0..22); bảng STT trong `M2_23_Features_ESP32_Integration.md` là 1-based (issue C09).

| Index | Feature | Cửa sổ | Đơn vị | Định nghĩa | Lớp dung sai |
|---|---|---|---|---|---|
| 0 | `roll_rms_60` | 60 | deg | sqrt(mean(x^2)) trên (t-60,t] | rms |
| 1 | `roll_std_60` | 60 | deg | độ lệch chuẩn quần thể (mẫu số n) | dispersion |
| 2 | `roll_mean_60` | 60 | deg | mean(x) | mean |
| 3 | `roll_peak_to_peak_60` | 60 | deg | max(x)-min(x) | extremum |
| 4 | `roll_abs_p95_60` | 60 | deg | phân vị Type-7 0.95 của \|x\| | quantile |
| 5 | `roll_abs_max_60` | 60 | deg | max(\|x\|) | extremum |
| 6 | `roll_iqr_60` | 60 | deg | Q0.75-Q0.25 Type-7 | quantile |
| 7 | `roll_diff_rms_60` | 60 | deg/sample @10 Hz | RMS sai phân bậc 1 giữa mẫu kề đúng chu kỳ 0.1 s | difference_rms |
| 8 | `roll_mean_180` | 180 | deg | mean(x) | mean |
| 9 | `roll_median_180` | 180 | deg | Q0.50 Type-7 | quantile |
| 10 | `roll_mean_abs_180` | 180 | deg | mean(\|x\|) | mean |
| 11 | `roll_dominant_sign_ratio_180` | 180 | 1 | max(n+,n-)/(n++n-), bỏ số 0 tuyệt đối | count_ratio |
| 12 | `roll_segment_mean_std_180` | 180 | deg | std quần thể của 3 mean block 60 s | dispersion |
| 13 | `roll_mean_shift_180` | 180 | deg | mean(block 3) - mean(block 1) | mean_difference |
| 14 | `roll_rms_early_60` | 180 | deg | RMS block 60 s cũ nhất | rms |
| 15 | `roll_rms_late_60` | 180 | deg | RMS block 60 s mới nhất (trùng số học với roll_rms_60) | rms |
| 16 | `roll_rms_ratio_180` | 180 | 1 | rms_late/rms_early; không xác định nếu rms_early <= 1e-9 | ratio |
| 17 | `roll_rms_slope_180` | 180 | deg/min | độ dốc OLS của 3 RMS block theo tâm [30,90,150] s, x60 | slope |
| 18 | `roll_rms_trend_r2_180` | 180 | 1 | R^2 của hồi quy 3 điểm; không xác định nếu SST=0 | r_squared |
| 19 | `roll_p95_trend_slope_180` | 180 | deg/min | độ dốc OLS của P95\|x\| 3 block, x60 | slope |
| 20 | `pitch_rms_60` | 60 | deg | sqrt(mean(p^2)) | rms |
| 21 | `pitch_std_60` | 60 | deg | độ lệch chuẩn quần thể | dispersion |
| 22 | `pitch_peak_to_peak_60` | 60 | deg | max(p)-min(p) | extremum |

Chi tiết bắt buộc:

- `x` là các mẫu **hữu hạn** trong cửa sổ (NaN/Inf bị loại); n = số mẫu hữu hạn. mean = Σx/n; RMS = √(Σx²/n) (gồm offset, KHÔNG trừ mean); std = √(Σ(x-mean)²/n) (quần thể).
- Phân vị Type-7: sắp xếp tăng z[0..n-1]; h = (n-1)p; j = ⌊h⌋; g = h-j; Q = z[j] + g·(z[min(j+1,n-1)] - z[j]). P95 dùng |x|; IQR = Q0.75 - Q0.25 trên x có dấu; median = Q0.50.
- `roll_diff_rms_60`: chỉ cặp (x[i-1], x[i]) cùng nằm trong cửa sổ, cùng hữu hạn, |Δt - 0,1| ≤ 1e-6 s; m cặp (tối đa 599); cần m ≥ 570; giá trị √(Σd²/m).
- `roll_dominant_sign_ratio_180`: n+ = #(x>0), n- = #(x<0); số 0 tuyệt đối bị loại; max(n+,n-)/(n++n-). Mọi mẫu bằng 0 → UNDEFINED_MATHEMATICALLY / NON_FINITE_RESULT (C08).
- Block: m_j, r_j (RMS), p_j (P95 của |x|) cho j = 1..3. `segment_mean_std` = std quần thể của (m1,m2,m3); `mean_shift` = m3 - m1; `rms_early` = r1; `rms_late` = r3 (trùng giá trị `roll_rms_60` khi cả hai VALID, C06).
- `roll_rms_ratio_180` = r3/r1; nếu r1 ≤ 1e-9 → UNDEFINED / EARLY_RMS_AT_OR_BELOW_EPSILON.
- Slope OLS trên u = (30, 90, 150) s, đổi sang deg/phút: với 3 điểm cách đều, **slope = (r3 - r1)/2** (tương tự cho p_j).
- R² = 1 - SSE/SST với SST = Σ(r_j - r̄)²; dạng đóng cho 3 điểm cách đều: **R² = (r3 - r1)²/(2·SST)**. SST ≤ 1e-15 → UNDEFINED / CONSTANT_RMS_TREND. Kẹp về [0,1] chỉ khi lệch ≤ 1e-12.
- Kết quả VALID nhưng không hữu hạn → UNDEFINED / NON_FINITE_RESULT.

Khuyến nghị số học (không bắt buộc nhưng được dung sai giả định): cộng dồn tổng bằng `double` (hoặc Kahan float32), std hai lượt hoặc Welford — KHÔNG dùng E[x²]-E[x]² trong float32 (đột biến `one_pass_variance` bị FAIL ở SYN31); sắp xếp bản sao 600/1800 phần tử cho phân vị; khi so sánh ngưỡng epsilon/SST nên tính bằng double.

## 4. Ngữ nghĩa validity/status

| Status | Reason code | Khi nào |
|---|---|---|
| VALID | — | giá trị hữu hạn, mọi điều kiện đạt |
| INSUFFICIENT_WINDOW | WINDOW_HISTORY_SHORT | t_e - t_đầu-segment < W (warm-up) |
| INVALID_INPUT | SAMPLING_RATE_MISMATCH | nhịp segment không phải 10 Hz (±1%) |
| INVALID_INPUT | TIMESTAMP_GAP | trong cửa sổ có hai timestamp liên tiếp cách > 0,15 s |
| INVALID_INPUT | TIME_SAMPLE_COVERAGE | số timestamp trong cửa sổ < 570/1710 hoặc > N+1 |
| INVALID_INPUT | SIGNAL_VALID_COVERAGE | số mẫu hữu hạn của tín hiệu < 570/1710 |
| INVALID_INPUT | ADJACENT_PAIR_COVERAGE | `roll_diff_rms_60`: < 570 cặp kề hợp lệ |
| INVALID_INPUT | SEGMENT_BLOCK_COVERAGE | 8 feature block: một block bất kỳ < 570 mẫu hoặc có gap (C01) |
| UNDEFINED_MATHEMATICALLY | EARLY_RMS_AT_OR_BELOW_EPSILON | `roll_rms_ratio_180`: r1 ≤ 1e-9 |
| UNDEFINED_MATHEMATICALLY | CONSTANT_RMS_TREND | `roll_rms_trend_r2_180`: SST ≤ 1e-15 |
| UNDEFINED_MATHEMATICALLY | NON_FINITE_RESULT | kết quả NaN/Inf (gồm sign ratio khi mọi mẫu = 0) |

Thứ tự ưu tiên trong một cửa sổ: WINDOW_HISTORY_SHORT → SAMPLING_RATE_MISMATCH → TIMESTAMP_GAP → TIME_SAMPLE_COVERAGE → SIGNAL_VALID_COVERAGE. 8 feature block dùng lại status của cửa sổ 180 s nếu cửa sổ đó lỗi. Harness so khớp **status bắt buộc**, reason_code chỉ cảnh báo.

## 5. Fixture

| Đường dẫn | Nội dung | Git |
|---|---|---|
| `ml/parity/fixtures/synthetic/inputs/*.csv` | 31 chuỗi kiểm thử số học | có |
| `ml/parity/fixtures/synthetic/expected_features.csv` | 11224 bản ghi golden dạng dài | có |
| `ml/parity/fixtures/synthetic/golden_vectors.jsonl` | 488 vector 23 phần tử | có |
| `ml/parity/fixtures/synthetic/cases.json` | endpoint, chỉ số cửa sổ/block, thang dung sai, cờ điều kiện | có |
| `ml/parity/fixtures/interchange_format.json` | định dạng đầu ra C | có |
| `ml/parity/fixtures/tolerance_spec.json` | dung sai theo feature | có |
| `ml/parity/fixtures/manifest.json` | checksum mọi file | có |
| `ml/data/parity/real/…` | 5 đoạn Hohai/Seafar/Southampton (sinh cục bộ) | không (gitignored) |

Đọc input: `roll_deg`/`pitch_deg` là chuỗi float32 ngắn nhất (đọc bằng `strtof`), chấp nhận `nan`, `inf`, `-inf`; `source_sample_index` nhảy cóc là timestamp bị bỏ — C phải phát hiện gap bằng `time_seconds`.

## 6. Định dạng đầu ra C

CSV (một dòng cho mỗi case × endpoint × feature):

```csv
schema_version,case_id,input_sha256,endpoint_index,endpoint_time_seconds,feature_index,feature_name,status,reason_code,value
svmg-angle23-0.2.0-proposal,SYN04_sine_roll,a1ef3eb3d6abe5c3ce2fd06f72ebf20bcd88b4b4f70364e7e246ebb117fa6312,2100,210.0,0,roll_rms_60,VALID,,3.53553392
svmg-angle23-0.2.0-proposal,SYN04_sine_roll,a1ef3eb3d6abe5c3ce2fd06f72ebf20bcd88b4b4f70364e7e246ebb117fa6312,2100,210.0,18,roll_rms_trend_r2_180,UNDEFINED_MATHEMATICALLY,CONSTANT_RMS_TREND,
```

Hoặc JSONL (một dòng mỗi case × endpoint, mảng 23 phần tử, `null` cho feature không VALID). Kèm `metadata.json`:

```json
{
 "interchange_schema": "svmg-parity-output-v1",
 "schema_version": "svmg-angle23-0.2.0-proposal",
 "producer": {
  "kind": "independent_c_implementation",
  "name": "svmg_feature23_host_test",
  "version": "0.1.0",
  "source_commit": "<git commit>",
  "compiler": "<gcc/xtensa-esp32-elf-gcc + version>",
  "compiler_flags": "<-O2 ...>",
  "target": "host|esp32",
  "float_type": "float32",
  "accumulator_type": "float64"
 },
 "golden_manifest_sha256": "<sha256 ml/parity/fixtures/manifest.json>"
}
```

Giá trị VALID ghi ≥ 9 chữ số có nghĩa (`%.9g`); feature không VALID để trống — ghi `0` là FAIL.

## 7. Lệnh chạy cho M1

```bash
# 0) Từ repository root, dùng môi trường dự án
.venv/bin/python -m ml.parity.golden --verify-only            # kiểm tra checksum fixture
# 1) Chương trình C (host trước, ESP32 sau) đọc từng ml/parity/fixtures/synthetic/inputs/<case>.csv,
#    tính 23 feature tại các endpoint_index trong expected_features.csv, ghi out/synthetic.csv + out/metadata.json
# 2) So sánh
.venv/bin/python -m ml.parity.compare --suite synthetic \
    --candidate out/synthetic.csv --metadata out/metadata.json --out ml/data/parity/runs/m1_host_v1
# 3) (Tùy chọn) nộp để tổng hợp trạng thái: ml/data/parity/c_results/<run>/{synthetic.csv,real.csv,metadata.json}
.venv/bin/python -m ml.parity.readiness
# Suite real cần dữ liệu processed cục bộ:
.venv/bin/python -m ml.parity.golden --suite real
```

Mã thoát của `compare` là 0 khi không có FAIL, 1 khi có FAIL. Metadata khai báo sai schema hoặc checksum manifest bị từ chối (`FAIL_METADATA`). Chỉ khi `producer.kind = independent_c_implementation` và cả hai suite đạt, trạng thái mới chuyển thành `C_PARITY_VERIFIED`.

## 8. Diễn giải lỗi parity

| Triệu chứng trong comparison_rows.csv | Nguyên nhân thường gặp | Case nhạy nhất |
|---|---|---|
| FAIL_FEATURE_NAME_ORDER | sai thứ tự hoặc lệch 0/1-based | mọi case |
| std (index 1, 12, 21) lệch tỷ lệ ≈ 1,00083 hoặc 1,22 | std mẫu (n-1) | SYN04, SYN13 |
| Mọi feature góc lệch hệ số ≈ 0,01745 | dùng radian | SYN25 |
| Chỉ P95/IQR/median/p95_slope lệch | sai nội suy phân vị (Type-6, nearest-rank) hoặc quên \|x\| | SYN13, SYN14 |
| Nhiều feature lệch quanh gai | biên cửa sổ `[t-W, t)` hoặc `[t-W, t]` | SYN12 |
| `roll_diff_rms_60` lệch ×10 | chia cho dt (deg/s) | SYN04 |
| Slope lệch ÷60 | để deg/s thay vì deg/phút | SYN07–SYN09 |
| std lệch lớn ở tín hiệu offset | phương sai một lượt float32 | SYN31 |
| FAIL_STATUS_MISMATCH ở hàng INVALID | quy tắc coverage/gap/block khác extractor (C01, C04) | SYN21–SYN27 |
| FAIL_INVALID_HAS_VALUE | ghi 0 thay vì để trống | SYN01, SYN17, SYN20 |
| REVIEW_ILL_CONDITIONED (R²/ratio) | quyết định phụ thuộc làm tròn; xem accumulator, chờ quyết định C02/C03 | SYN30 |
| FAIL_INPUT_SHA256 / MISSING / EXTRA | đọc sai file, sai lưới endpoint | — |

## 9. Việc cần làm tiếp ở Level 3 (chưa thực hiện)

1. Đo trên ESP32 thật: RAM (ring Roll 180 s + Pitch 60 s + scratch 1800 float ≈ 17,2 kB theo ước lượng `esp32_feature_compatibility.md`, trạng thái ESTIMATE_NOT_MEASURED_ON_DEVICE), stack high-water mark, Flash của mã + mô hình, thời gian một lần cập nhật 10 s (sắp xếp 1800 phần tử).
2. Chạy lại đúng golden trên ESP32 (không chỉ host) để thấy ảnh hưởng `madd.s`/cờ biên dịch.
3. Chuỗi Roll/Pitch 10 Hz riêng cho feature (firmware hiện xuất 2 Hz sau lọc 0,5 Hz) và đánh giá lại lệch miền: thí nghiệm đã có cho thấy POS 188 → 4 khi lọc 0,5 Hz.
4. Xác nhận trục/dấu và hiệu chuẩn mốc 0 của Roll/Pitch so với quy ước dataset.
5. Thống nhất C01–C04 với M2 rồi phát hành contract có phiên bản (không phải `-proposal`).

## 10. Quyết định cần M1 phản hồi

| Issue | Câu hỏi |
|---|---|
| C01 | Giữ quy tắc 'cả 3 block hợp lệ' cho 8 feature block (như extractor), hay theo chữ đặc tả (rms_early chỉ cần block 1, …)? Đổi → sinh lại golden + huấn luyện lại. |
| C02 | Epsilon của ratio: giữ 1e-9 deg (số học) hay đặt theo độ phân giải/nhiễu cảm biến? |
| C03 | Ngưỡng SST của R²: giữ 1e-15 deg² tuyệt đối hay chuyển sang ngưỡng tương đối (đề xuất SST/mean(r)² < 1e-6)? |
| C04 | Mẫu lỗi biểu diễn bằng NaN có timestamp (khuyến nghị) hay bỏ timestamp? |

## Giải thích kỹ thuật phục vụ vấn đáp cá nhân

- **Vì sao M1 phải xuất cả status chứ không chỉ 23 số?** Vì mô hình chỉ được chạy khi đủ 23 feature hợp lệ; nếu status sai, firmware có thể suy luận trên vector không hợp lệ hoặc bỏ qua vector hợp lệ — đều là lỗi parity dù số khớp.
- **Vì sao golden đánh giá tại endpoint_index cố định?** Để so cùng một tập mẫu. So theo thời gian thực của ESP32 sẽ trộn lẫn sai lệch đồng hồ với sai lệch thuật toán.
- **Parity đạt rồi có triển khai được không?** Chưa. Parity chỉ chứng minh C tính giống Python trên cùng chuỗi đầu vào. Còn phải chứng minh chuỗi Roll/Pitch mà ESP32 tạo ra giống miền dữ liệu huấn luyện (Level 3) và đo tài nguyên trên chip.
- **Tại sao khuyến nghị cộng dồn bằng double trên ESP32 không có FPU double?** Mỗi 10 s chỉ cộng vài nghìn số; chi phí phần mềm nhỏ so với sắp xếp phân vị, đổi lại loại bỏ rủi ro C03 và sai số tích lũy.
