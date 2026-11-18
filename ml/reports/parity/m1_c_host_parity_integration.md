# Tích hợp mã C M1 với golden 23 feature M2 — parity trên host

> **Phạm vi:** chỉ `HOST_C_FEATURE_PARITY` — mã C M1 (`core/src/features.c`, không sửa) biên dịch bằng Apple Clang trên macOS arm64, chạy trên đúng chuỗi Roll/Pitch float32 của golden. **Không** đo trên ESP32, **không** chứng minh chuỗi cảm biến ESP32 (`ESP32_SENSOR_PIPELINE_COMPATIBILITY`), **không** liên quan tích hợp Random Forest (`RANDOM_FOREST_MODEL_INTEGRATION`).

Lượt chạy tham chiếu: `run_id = m1v1_host_clang`, commit nguồn `b82c609` (nhánh `feat/M2-m1-golden-parity-integration`; `core/` không có thay đổi chưa commit), `Apple clang version 21.0.0 (clang-2100.3.34.2)`, target `arm64-apple-darwin27.0.0`, cờ `-std=c99 -O2 -ffp-contract=off -Wall -Wextra`. Artefact sinh ra nằm ở `ml/data/parity/c_host/m1v1_host_clang/` và `ml/data/parity/runs/c_host_m1v1_host_clang_*` (gitignored).

## 1. So sánh contract M1 `svmg-angle-23-v1` và M2 `svmg-angle23-0.2.0-proposal`

| Khía cạnh | M1 v1 (`contracts/features23.json`, `svmg_feature_schema.h`) | M2 v0.2 (`ml/docs/feature_contract_23_v0.2.json`) | Tương thích |
|---|---|---|---|
| Tên, thứ tự, index 0-based 23 feature | 23 tên, index 0..22 | trùng | **Trùng** (kiểm tra từ binary đã biên dịch) |
| Nhịp, stride, cửa sổ | 10 Hz, 10 s, [60, 180] s | trùng | Trùng |
| Biên cửa sổ | `(t-W,t]` | `(t-W, t]` | Trùng |
| Std / RMS / phân vị | ddof 0, RMS không trừ mean, Type-7 | trùng | Trùng |
| Coverage tối thiểu | `minimum_valid_fraction` 0,95 (C: 570/1710 mẫu hữu hạn) | 570/1710, cặp sai phân 570, block 570 | Trùng về số |
| Epsilon ratio / ngưỡng SST R² | 1e-9 deg / 1e-15 | 1e-9 / 1e-15 | Trùng (C01–C04 vẫn mở) |
| Đơn vị | `deg/sample`, `dimensionless` | `deg/sample @10 Hz`, `1` | Cùng nghĩa, khác cách viết |
| Trục thời gian | **không có**: cửa sổ = N mẫu cuối, warm-up đếm mẫu | theo timestamp, gap > 0,15 s → INVALID | **Khác** (C04) |
| Status / reason | chỉ NaN + `valid_mask` | 4 status + 10 reason code | **C không biểu diễn** |
| Mã hóa feature không hợp lệ | NaN | `null`/ô rỗng | Khác cách mã hóa, cùng nghĩa |
| Tiền xử lý | `imu-cf-bw4-20to10-v1`, raw 20 Hz, `nraw` (2 mẫu raw/mẫu 10 Hz) | không quy định (Level 3) | Ngoài phạm vi golden |
| Trạng thái phát hành | `-v1` (M1 đã hiện thực) | `PROPOSAL_PENDING_M1_REVIEW` | Chưa thống nhất chính thức |

**Quyết định tích hợp (ghi rõ, không đổi tên phiên bản):** candidate khai báo `schema_version = svmg-angle23-0.2.0-proposal` vì đó là contract dùng để *đánh giá*; schema gốc của C được ghi trong `metadata.producer.c_feature_schema_version = svmg-angle-23-v1` cùng khối `schema_mapping`. Runner dừng nếu tên/thứ tự/tham số trong binary khác golden.

## 2. Cách tích hợp C

- `ml/parity/c_host/feature23_host_runner.c` (mới): đọc input golden (`strtof` cho roll/pitch, `strtod` cho thời gian), đẩy **từng mẫu** qua `svmg_window_push(..., nraw=2, valid=1)` như `engine.c`, gọi `svmg_features_compute` tại đúng `endpoint_index` golden, đối chiếu **bitwise** với `svmg_features_from_series` trên cùng đoạn, in giá trị `%.9g` (round-trip float32) cùng trạng thái cửa sổ C (`ready_short/long`, `valid_mask`, số mẫu hữu hạn trong ring C, số cặp kề nhau, số mẫu mỗi block).
- `ml/parity/c_host.py` (mới): biên dịch, chạy, chuyển sang định dạng interchange, ghi metadata (`producer.kind = independent_c_implementation`), gọi `ml.parity.compare`.
- **Validity** = bit `valid_mask` của C. **Status không-VALID** = adapter `c_state_status_adapter_v1` chỉ từ trạng thái cửa sổ C (không đọc status Python). Reason code là sản phẩm của adapter, không phải của C.
- **NOT_EVALUABLE** (`C_API_NO_TIMESTAMP_INPUT`): nhóm 60 s (hoặc 180 s) tại endpoint e khi các hàng input `[e-599, e]` (hoặc `[e-1799, e]`) có |Δt − 0,1| > 1e-6 s. Chỉ dựa vào `time_seconds` của input.
- `compare.py` được mở rộng tối thiểu: status `NOT_EVALUABLE` do producer khai báo → kết quả `NOT_EVALUABLE`, không bao giờ PASS; verdict tối đa `C_PARITY_PARTIAL`. `readiness.suite_passed` không tính suite có NOT_EVALUABLE là đạt.

## 3. Kết quả

| Suite | Case | Endpoint | Bản ghi feature | PASS (giá trị / chỉ status) | FAIL | REVIEW | NOT_EVALUABLE | Lệch validity | Max \|Δ\| | Max \|Δ\|/cho phép | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| synthetic | 31 | 488 | 11224 | 11178 (6515 / 4663) | 0 | 0 | 46 | 0 | 2,90e-4 (ratio 1e7 của SYN19, tương đối 5,4e-8) | 0,187 | `C_PARITY_PARTIAL` |
| real | 5 | 95 | 2185 | 2185 (1465 / 720) | 0 | 0 | 0 | 0 | 1,24e-7 | 0,191 | `C_PARITY_PASS` |

- `svmg_features_from_series` trùng bitwise với đường streaming ở mọi endpoint của cả hai suite.
- Ứng viên **giống hệt từng byte** khi biên dịch `-O0`, `-O2 -ffp-contract=off`, `-O2 -ffp-contract=fast`.
- Lệch status giữa adapter và golden: 0; lệch reason code: 0 (chỉ là cảnh báo).
- Sai số tương đối tối đa ≈ 5,9e-8 ≈ 2⁻²⁴: chi phối bởi phép ép double → float32 ở đầu ra C (`assign()`); các tổng nội bộ C tính bằng double.

### Sai số theo feature

| # | Feature | Lớp | Syn: so giá trị | Syn: max abs | Syn: max rel | Syn: max Δ/cho phép | Real: so giá trị | Real: max abs | Real: max Δ/cho phép |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | `roll_rms_60` | rms | 476 | 4.00e-07 | 5.16e-08 | 2.21e-03 | 95 | 1.16e-07 | 2.28e-03 |
| 1 | `roll_std_60` | dispersion | 476 | 1.21e-07 | 5.20e-08 | 5.00e-04 | 95 | 2.81e-08 | 3.18e-04 |
| 2 | `roll_mean_60` | mean | 476 | 5.78e-08 | 5.31e-08 | 5.97e-04 | 95 | 1.17e-07 | 1.97e-03 |
| 3 | `roll_peak_to_peak_60` | extremum | 476 | 5.10e-07 | 5.67e-08 | 1.87e-01 | 95 | 1.24e-07 | 1.79e-01 |
| 4 | `roll_abs_p95_60` | quantile | 476 | 2.38e-07 | 5.55e-08 | 1.05e-02 | 95 | 4.08e-08 | 7.22e-03 |
| 5 | `roll_abs_max_60` | extremum | 476 | 2.48e-08 | 2.48e-09 | 6.19e-03 | 95 | 4.98e-09 | 1.19e-02 |
| 6 | `roll_iqr_60` | quantile | 476 | 4.77e-07 | 3.40e-05 | 1.46e-02 | 95 | 5.95e-08 | 1.51e-02 |
| 7 | `roll_diff_rms_60` | difference_rms | 474 | 2.90e-08 | 5.82e-08 | 1.96e-03 | 95 | 7.06e-09 | 1.23e-03 |
| 8 | `roll_mean_180` | mean | 116 | 2.89e-08 | 4.45e-08 | 5.97e-04 | 35 | 1.07e-07 | 1.42e-03 |
| 9 | `roll_median_180` | quantile | 116 | 6.38e-08 | 5.59e-08 | 4.26e-03 | 35 | 3.02e-08 | 7.28e-03 |
| 10 | `roll_mean_abs_180` | mean | 116 | 4.59e-07 | 4.50e-08 | 1.28e-03 | 35 | 1.07e-07 | 1.42e-03 |
| 11 | `roll_dominant_sign_ratio_180` | count_ratio | 108 | 2.72e-08 | 4.90e-08 | 2.72e-02 | 35 | 2.98e-08 | 2.98e-02 |
| 12 | `roll_segment_mean_std_180` | dispersion | 108 | 2.98e-09 | 4.62e-08 | 2.01e-05 | 35 | 1.26e-08 | 5.80e-05 |
| 13 | `roll_mean_shift_180` | mean_difference | 108 | 4.72e-09 | 5.60e-08 | 2.14e-05 | 35 | 1.50e-08 | 1.00e-04 |
| 14 | `roll_rms_early_60` | rms | 108 | 4.00e-07 | 4.65e-08 | 2.03e-03 | 35 | 1.15e-07 | 2.28e-03 |
| 15 | `roll_rms_late_60` | rms | 108 | 4.00e-07 | 5.16e-08 | 2.03e-03 | 35 | 1.09e-07 | 1.84e-03 |
| 16 | `roll_rms_ratio_180` | ratio | 92 | 2.90e-04 | 5.41e-08 | 1.08e-03 | 35 | 6.01e-08 | 1.12e-03 |
| 17 | `roll_rms_slope_180` | slope | 108 | 1.14e-07 | 5.75e-08 | 5.75e-04 | 35 | 1.19e-08 | 1.40e-04 |
| 18 | `roll_rms_trend_r2_180` | r_squared | 55 | 3.00e-08 | 4.01e-08 | 1.50e-05 | 35 | 3.01e-08 | 1.51e-05 |
| 19 | `roll_p95_trend_slope_180` | slope | 108 | 1.22e-07 | 9.48e-07 | 1.10e-03 | 35 | 2.41e-08 | 8.16e-04 |
| 20 | `pitch_rms_60` | rms | 486 | 2.27e-07 | 4.91e-08 | 2.09e-03 | 95 | 6.10e-08 | 1.98e-03 |
| 21 | `pitch_std_60` | dispersion | 486 | 2.10e-07 | 4.91e-08 | 5.38e-04 | 95 | 7.33e-09 | 2.97e-04 |
| 22 | `pitch_peak_to_peak_60` | extremum | 486 | 7.35e-09 | 4.27e-09 | 1.40e-02 | 95 | 3.03e-08 | 1.91e-01 |

Ghi chú: lớp `extremum` có dung sai hẹp nhất (rel 2e-7) nên tỷ số cao nhất (~0,19) chỉ do làm tròn float32 đầu ra. `roll_iqr_60` có max rel 3,4e-5 vì IQR nhỏ và C trừ hai phân vị đã ép float32; `roll_p95_trend_slope_180` (rel 9,5e-7) vì P95 block được ép float32 trước khi tính slope. Đều trong dung sai, không đổi dung sai.

## 4. Case không biểu diễn được

| Case | Endpoint | Bản ghi | Lý do |
|---|---|---:|---|
| `SYN23_timestamp_gap` | 2000 | 23 | 4 timestamp bị bỏ trong cả cửa sổ 60 s và 180 s |
| `SYN24_single_dropped_sample` | 2000 | 23 | 1 timestamp bị bỏ trong cả hai cửa sổ |

Chẩn đoán (không phải parity, chỉ là bằng chứng cho C04): khi chèn mẫu invalid giữ nhịp 10 Hz (cách `engine.c` vẫn push mẫu `valid=0`), C trả **VALID cho cả 46 bản ghi** còn Python trả `INVALID_INPUT/TIMESTAMP_GAP`.

Golden **không phủ**: `SAMPLING_RATE_MISMATCH`, `TIME_SAMPLE_COVERAGE`, mẫu 10 Hz chỉ có 1/2 mẫu raw hợp lệ (`nraw`), `svmg_window_shift` sau hiệu chuẩn lại, gating chất lượng `svmg_features_status` (95 %/50 %, 100 mẫu lỗi liên tiếp), chạy dài với ring buffer quay vòng nhiều lần (golden dài tối đa 2401 mẫu). Suite real không có NaN hay gap.

## 5. C01–C04 đối chiếu với M1 v1

| Issue | Python | C M1 v1 | Bằng chứng | Tương đương | Cần M1 duyệt | Khuyến nghị |
|---|---|---|---|---|---|---|
| C01 block validity | 8 feature block cần cửa sổ 180 s hợp lệ **và** cả 3 block ≥ 570 | `bok &= b[j].n >= 570` cho cả 3 block; không cần `lok` riêng nhưng 3·570 = 1710 nên tương đương khi không có gap | SYN22, SYN27: 64 bản ghi `SEGMENT_BLOCK_COVERAGE` trùng status | **Có** (khi không có gap) | Có — cả hai lệch so với chữ của đặc tả | Ghi quy tắc "cả 3 block" vào contract chính thức; không đổi feature huấn luyện |
| C02 epsilon ratio | `rms_early <= 1e-9` → UNDEFINED, so bằng float64 | `b[0].rms > 1e-9` so bằng double | 16 bản ghi `EARLY_RMS_AT_OR_BELOW_EPSILON` (SYN01, SYN05, SYN17, SYN18) trùng status; SYN19 VALID (ratio 1e7) PASS_VALUE | **Có** | Có — 1e-9 là epsilon số học, không theo cảm biến | Giữ 1e-9 cho parity; quyết định epsilon vật lý là thay đổi contract + huấn luyện lại |
| C03 ngưỡng SST R² | SST ≤ 1e-15 → UNDEFINED, RMS block float64 | RMS block và SST tính bằng **double** từ mẫu float32 | 53 bản ghi `CONSTANT_RMS_TREND` ở 15 case (gồm SYN30 hoán vị block, SYN11, SYN31) trùng status; R² VALID có cờ `ILL_CONDITIONED_R2` ở SYN21/SYN26 đạt PASS_VALUE; 0 REVIEW | **Có trên host** | Có — rủi ro float32 (từ `float32_probe`) không xảy ra vì C dùng double; chưa xác nhận trên ESP32 | Ghi yêu cầu "tích lũy double" vào contract; vẫn nên chốt ngưỡng tương đối |
| C04 NaN có timestamp vs timestamp bị bỏ | NaN bỏ khỏi thống kê; timestamp bị bỏ → INVALID | NaN/Inf → mẫu invalid (trùng); C **không có timestamp**, firmware giữ nhịp bằng mẫu invalid | NaN: SYN21/22/26 trùng; gap: SYN23/24 NOT_EVALUABLE; gridfill: 46/46 C VALID vs Python INVALID | **NaN: có; gap: không** | **Có, chặn** | Chốt: firmware phát mẫu invalid khi lỡ nhịp (C hiện tại), và Python biểu diễn mẫu lỡ bằng NaN có timestamp; hoặc M1 thêm phát hiện gap vào API |

## 6. Yêu cầu bàn giao cho M1

1. Duyệt C01–C04 (C04 là chặn) và phát hành contract chung không còn `-proposal`; quyết định có giữ mapping v1 → v0.2 như ở mục 1 hay không.
2. Nếu cần status/reason trên thiết bị: xuất lý do không hợp lệ từ C thay cho adapter host hiện tại.
3. Chạy lại cùng golden trên ESP32 (`xtensa-esp32-elf-gcc`, double phần mềm) và đo RAM/stack/thời gian — chưa có số đo nào.
4. `svmg_features_from_series` có khung stack ~25 kB (báo cáo `run_native.py`): chỉ dùng trên host, không gọi trong task ESP32.
5. Level 3: chuỗi Roll/Pitch 10 Hz thật của ESP32, quy ước trục/dấu, mốc 0, `nraw` — chưa kiểm chứng.

## 7. Kết luận theo cấp độ

| Cấp độ | Trạng thái |
|---|---|
| `HOST_C_FEATURE_PARITY` | **Xác minh một phần**: 0 FAIL trên 13363 bản ghi đánh giá được (synthetic + real); 46 bản ghi gap NOT_EVALUABLE; C04 mở |
| `ESP32_SENSOR_PIPELINE_COMPATIBILITY` | **Chưa kiểm chứng** — không có số đo ESP32 |
| `RANDOM_FOREST_MODEL_INTEGRATION` | **Chưa kiểm chứng** — ngoài phạm vi, không xuất `model.h` |

Tái lập: `.venv/bin/python -m ml.parity.c_host --suite all --run-id m1v1_host_clang`; test: `.venv/bin/python -m pytest ml/parity/tests/test_c_host.py`.
