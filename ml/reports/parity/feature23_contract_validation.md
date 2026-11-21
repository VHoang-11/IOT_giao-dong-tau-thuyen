# Kiểm định contract 23 feature (`svmg-angle23` v0.2.0-proposal)

> **Phạm vi.** Gói này chuẩn bị kiểm chứng parity *tính feature* Python/C cho 23 angle feature của PoC Random Forest phân loại motion phenotype bằng proxy label — KHÔNG phải bộ phân loại an toàn hàng hải đã xác thực. Golden vector đã chuẩn bị KHÔNG có nghĩa parity Python/C hay triển khai ESP32 đã được kiểm chứng.

- Schema: `svmg-angle23-0.2.0-proposal`; SHA-256 thứ tự tên: `060095dd1f6bf4264fdf1d95e601fe66880837cde08ec5896e35a67f7ff8a1c8`.
- SHA-256 schema trong model card RF: `060095dd1f6bf4264fdf1d95e601fe66880837cde08ec5896e35a67f7ff8a1c8` → khớp: **True**.
- Tham chiếu số học: ml/features/extractor.py (feature_extractor_version 0.1.0, feature_spec_version candidate-30-v1). Công thức KHÔNG bị sửa; contract v0.1 giữ nguyên, v0.2 là file mới.
- Bất nhất chặn (thứ tự/cửa sổ): **KHÔNG** — vì vậy được phép sinh golden.
- Vấn đề mở cần nhóm quyết định: C01, C02, C03. C04 đã được xử lý theo ranh giới timestamp-aware và restart end-to-end; contract vẫn là proposal do các mục khác còn mở.

## 1. Thứ tự 23 feature trên mọi nguồn

| Nguồn | Khớp thứ tự contract |
|---|---|
| `milestone_expected_selection` | ✅ |
| `ml.features.spec.PRACTICAL_SUBSETS` | ✅ |
| `ml.labeling.human_review_workflow.ANGLE_FEATURES` | ✅ |
| `ml.train.rf_poc.FEATURE_ORDER` | ✅ |
| `feature_contract_23_v0.1.json` | ✅ |
| `M2_23_Features_ESP32_Integration.md` | ✅ |

## 2. Bảng contract đã kiểm định

| Index | Feature | Nhóm | Cửa sổ (s) | Đơn vị | Định nghĩa | Lớp dung sai |
|---|---|---|---|---|---|---|
| 0 | `roll_rms_60` | A_roll_60 | 60 | deg | sqrt(mean(x^2)) trên (t-60,t] | rms |
| 1 | `roll_std_60` | A_roll_60 | 60 | deg | độ lệch chuẩn quần thể (mẫu số n) | dispersion |
| 2 | `roll_mean_60` | A_roll_60 | 60 | deg | mean(x) | mean |
| 3 | `roll_peak_to_peak_60` | A_roll_60 | 60 | deg | max(x)-min(x) | extremum |
| 4 | `roll_abs_p95_60` | A_roll_60 | 60 | deg | phân vị Type-7 0.95 của \|x\| | quantile |
| 5 | `roll_abs_max_60` | A_roll_60 | 60 | deg | max(\|x\|) | extremum |
| 6 | `roll_iqr_60` | A_roll_60 | 60 | deg | Q0.75-Q0.25 Type-7 | quantile |
| 7 | `roll_diff_rms_60` | A_roll_60 | 60 | deg/sample @10 Hz | RMS sai phân bậc 1 giữa mẫu kề đúng chu kỳ 0.1 s | difference_rms |
| 8 | `roll_mean_180` | C_roll_offset_180 | 180 | deg | mean(x) | mean |
| 9 | `roll_median_180` | C_roll_offset_180 | 180 | deg | Q0.50 Type-7 | quantile |
| 10 | `roll_mean_abs_180` | C_roll_offset_180 | 180 | deg | mean(\|x\|) | mean |
| 11 | `roll_dominant_sign_ratio_180` | C_roll_offset_180 | 180 | 1 | max(n+,n-)/(n++n-), bỏ số 0 tuyệt đối | count_ratio |
| 12 | `roll_segment_mean_std_180` | C_roll_offset_180 | 180 | deg | std quần thể của 3 mean block 60 s | dispersion |
| 13 | `roll_mean_shift_180` | C_roll_offset_180 | 180 | deg | mean(block 3) - mean(block 1) | mean_difference |
| 14 | `roll_rms_early_60` | D_roll_growth_180 | 180 | deg | RMS block 60 s cũ nhất | rms |
| 15 | `roll_rms_late_60` | D_roll_growth_180 | 180 | deg | RMS block 60 s mới nhất (trùng số học với roll_rms_60) | rms |
| 16 | `roll_rms_ratio_180` | D_roll_growth_180 | 180 | 1 | rms_late/rms_early; không xác định nếu rms_early <= 1e-9 | ratio |
| 17 | `roll_rms_slope_180` | D_roll_growth_180 | 180 | deg/min | độ dốc OLS của 3 RMS block theo tâm [30,90,150] s, x60 | slope |
| 18 | `roll_rms_trend_r2_180` | D_roll_growth_180 | 180 | 1 | R^2 của hồi quy 3 điểm; không xác định nếu SST=0 | r_squared |
| 19 | `roll_p95_trend_slope_180` | D_roll_growth_180 | 180 | deg/min | độ dốc OLS của P95\|x\| 3 block, x60 | slope |
| 20 | `pitch_rms_60` | F_pitch_60 | 60 | deg | sqrt(mean(p^2)) | rms |
| 21 | `pitch_std_60` | F_pitch_60 | 60 | deg | độ lệch chuẩn quần thể | dispersion |
| 22 | `pitch_peak_to_peak_60` | F_pitch_60 | 60 | deg | max(p)-min(p) | extremum |

## 3. Quy ước đã xác nhận (đối chiếu `ml/features/config.yaml` và extractor)

| Hạng mục | Giá trị/quy tắc | Xác nhận |
|---|---|---|
| Tần số đầu vào | 10 Hz (chu kỳ 0,1 s) | ✅ |
| Đơn vị Roll/Pitch | độ (degree); `roll_diff_rms_60` là deg/mẫu ở 10 Hz; slope là deg/phút | ✅ (contract `units`) |
| Cửa sổ trượt | 60 s và 180 s, nửa mở `(t-W, t]`, không vượt ranh giới segment | ✅ |
| Bước cập nhật | 10 s; endpoint theo CHỈ SỐ mẫu 600 + 100·j từ đầu segment (C05) | ✅ |
| Độ lệch chuẩn | quần thể, mẫu số n (std, segment_mean_std) | ✅ (kiểm tra hành vi `population_std`) |
| Phân vị | Type-7: h=(n-1)p, nội suy tuyến tính | ✅ |
| Sai phân | chỉ cặp (x[i-1], x[i]) đều nằm trong cửa sổ, đều hữu hạn, cách đúng 0,1 s; 600 mẫu → 599 cặp; cần ≥ 570 cặp | ✅ (kiểm tra `difference_pair_semantics`) |
| 3 block 180 s | (t-180,t-120], (t-120,t-60], (t-60,t]; mỗi block ≥ 570 mẫu, không gap | ✅ |
| Hồi quy xu hướng | OLS 3 điểm tại u = 30/90/150 s; slope × 60 → deg/phút = (r3 - r1)/2 | ✅ (kiểm tra `trend_slope_units`) |
| R² | 1 - SSE/SST; UNDEFINED nếu SST ≤ 1e-15; kẹp về [0,1] chỉ trong 1e-12 | ✅ (tolerance 1e-15) |
| Epsilon ratio | rms_early ≤ 1e-09 deg → UNDEFINED | ✅ (epsilon số học, xem C02) |
| Coverage | ≥ 95% mẫu: 570/600 và 1710/1800; số timestamp ≤ N+1 | ✅ |
| Gap | khoảng cách timestamp > 1,5 chu kỳ (0,15 s) trong cửa sổ → INVALID_INPUT/TIMESTAMP_GAP | ✅ |
| Warm-up | feature 60 s cần ≥ 60 s lịch sử, 180 s cần ≥ 180 s → INSUFFICIENT_WINDOW/WINDOW_HISTORY_SHORT | ✅ (kiểm tra `warmup`) |
| Giá trị không hợp lệ | value = null/ô rỗng, KHÔNG bao giờ 0; vector thiếu → ABSTAIN/UNKNOWN, không NORMAL | ✅ |

## 4. Kiểm tra hành vi trên chính extractor (đáp án giải tích)

| Kiểm tra | Kỳ vọng | Quan sát | Đạt | Ghi chú |
|---|---|---|---|---|
| population_std | 0.7071067811865476 | 0.7071067811865475 | ✅ | Sine biên độ 1, số chu kỳ nguyên: std quần thể = 1/sqrt(2); std mẫu (n-1) sẽ lớn hơn 0,083%. |
| type7_quantile | 8.7802 | 8.780199999999999 | ✅ | Cấp số cộng 600 giá trị: Q_0.95 Type-7 = x_min + 0.95*(n-1)*bước. |
| half_open_window | 0.0 | 0.0 | ✅ | Mẫu tại đúng t-60 bị loại khỏi cửa sổ 60 s nhưng thuộc cửa sổ 180 s. |
| zero_signal_undefined | UNDEFINED_MATHEMATICALLY x3 | ['UNDEFINED_MATHEMATICALLY', 'EARLY_RMS_AT_OR_BELOW_EPSILON', 'UNDEFINED_MATHEMATICALLY', 'CONSTANT_RMS_TREND', 'UNDEFINED_MATHEMATICALLY'] | ✅ | Tín hiệu 0: ratio (rms_early <= epsilon), R² (SST = 0), sign ratio (không có mẫu khác 0) đều không xác định, không bằng 0. |
| warmup | 60 s VALID, 180 s INSUFFICIENT_WINDOW | ['VALID', 'INSUFFICIENT_WINDOW', 'WINDOW_HISTORY_SHORT'] | ✅ | 150 s lịch sử: feature 180 s chưa được tính (WARMUP). |
| trend_slope_units | 0.7071067811865475 | 0.7071067811865474 | ✅ | RMS block 1/√2, 2/√2, 3/√2 tại tâm 30/90/150 s: slope = (r3-r1)/120 s × 60 = deg/phút. |
| difference_pair_semantics | rms VALID, diff_rms INVALID_INPUT/ADJACENT_PAIR_COVERAGE | ['VALID', 'INVALID_INPUT', 'ADJACENT_PAIR_COVERAGE'] | ✅ | 20 NaN rời rạc (3,3%) giữ feature pointwise hợp lệ nhưng xóa 40 cặp kề nhau: 559 < 570 cặp. |

## 5. Bất nhất và điểm cần làm rõ (không giải quyết ngầm)

| ID | Mức | Trạng thái | Vấn đề | Đặc tả | Extractor | Chính sách golden |
|---|---|---|---|---|---|---|
| C01 | MATERIAL | OPEN_TEAM_DECISION | Điều kiện hợp lệ của feature block 180 s | feature_specification_30.md: roll_rms_early_60 chỉ cần block đầu, roll_rms_late_60 chỉ cần block cuối, mean_shift cần block đầu và cuối. | extractor.py: cả 8 feature dựa trên block (C/D trừ 4 feature pointwise 180 s) INVALID nếu cửa sổ 180 s hoặc BẤT KỲ block nào không đạt coverage. | Golden theo extractor (tham chiếu số học). Hiện thực C theo đúng chữ của đặc tả sẽ lệch validity ở cửa sổ thiếu mẫu. |
| C02 | MATERIAL | OPEN_TEAM_DECISION | Epsilon mẫu số của roll_rms_ratio_180 | Đặc tả yêu cầu epsilon_rms theo độ phân giải/nhiễu cảm biến (chưa chốt). | extractor dùng numeric_zero_epsilon_deg = 1e-09 (epsilon số học, không phải vật lý). | Golden dùng 1e-9 deg; case sát epsilon được đánh dấu ILL_CONDITIONED. |
| C03 | MATERIAL | OPEN_TEAM_DECISION | Ngưỡng SST của roll_rms_trend_r2_180 thấp hơn độ phân giải float32 | R² không xác định nếu SST = 0. | SST <= 1e-15 deg² -> UNDEFINED. Với biên độ ~1°, nhiễu làm tròn float32 của RMS block (~1e-7) cho SST ~1e-14 > 1e-15, nên C float32 có thể báo VALID với R² vô nghĩa khi Python báo UNDEFINED. | Golden giữ quyết định của extractor; harness xếp R² có SST tương đối nhỏ vào REVIEW_ILL_CONDITIONED thay vì PASS/FAIL. Cần nhóm chốt ngưỡng tương đối. |
| C04 | MATERIAL | RESOLVED_LAYERED_TIMESTAMP_BOUNDARY | Biểu diễn mẫu thiếu: NaN có timestamp khác với timestamp bị bỏ | ≥ 95% mẫu hợp lệ; gap > 1,5 chu kỳ làm cửa sổ không hợp lệ. | M2 giữ quy tắc timestamp-aware: gap > 0,15 s trong cửa sổ là INVALID_INPUT/TIMESTAMP_GAP. M1 stream restart/xóa history/UNKNOWN với gap hữu hạn; NaN/Inf bị loại và engine UNKNOWN tức thì. C feature-only không nhận timestamp. | Giữ nguyên SYN23/SYN24 expected outputs; C host API không timestamp giữ 46 NOT_EVALUABLE. Không chuyển sang PASS nếu chưa có C timestamp-aware output thực. |
| C05 | CLARIFICATION | DOCUMENTED_IN_V0_2 | Neo lưới endpoint | — | Endpoint theo CHỈ SỐ mẫu: mẫu thứ 600, 700, … tính từ mẫu đầu segment; mẫu đầu tiên không bao giờ thuộc cửa sổ 60 s đầu. Sau một timestamp bị bỏ, thời điểm endpoint lệch theo chỉ số. | Golden ghi rõ endpoint (chỉ số và thời gian) cho từng case; C đánh giá đúng tại các endpoint đó. |
| C06 | CLARIFICATION | DOCUMENTED_IN_V0_2 | roll_rms_late_60 trùng giá trị nhưng khác validity với roll_rms_60 | — | Cùng mẫu (t-60, t] nên cùng giá trị khi cả hai hợp lệ; rms_late chỉ hợp lệ khi đủ 180 s và đủ 3 block. | — |
| C08 | CLARIFICATION | DOCUMENTED_IN_V0_2 | Mã lý do của roll_dominant_sign_ratio_180 khi mọi mẫu bằng 0 | Không xác định nếu mọi giá trị đúng bằng 0. | dominant_sign_ratio trả NaN, _valid() đổi thành UNDEFINED_MATHEMATICALLY với reason_code NON_FINITE_RESULT (không có mã riêng như NO_NONZERO_SAMPLES). | Status được so khớp bắt buộc; reason_code chỉ so như cảnh báo. M1 nên xuất NON_FINITE_RESULT để trùng golden. |
| C09 | CLARIFICATION | DOCUMENTED_IN_V0_2 | Chỉ số 0-based của contract và STT 1-based trong tài liệu M1 | M2_23_Features_ESP32_Integration.md đánh STT 1..23; contract JSON và golden dùng feature_index 0..22. | — | Interchange dùng feature_index 0-based; harness kiểm tra feature_name khớp index để bắt lệch 1 vị trí. |
| C07 | MATERIAL | SUPERSEDED_IN_V0_2 | Dung sai parity một giá trị chung trong v0.1 | v0.1 đề xuất tuyệt đối 1e-3°, tương đối 1e-4 cho mọi feature. | — | v0.2 thay bằng dung sai theo nhóm feature có hạng tỷ lệ theo biên độ đầu vào (ml/parity/fixtures/tolerance_spec.json). |

Không có bất nhất nào về **tên, thứ tự, cửa sổ hay công thức** giữa contract, extractor, RF và tài liệu M1. Các mục MATERIAL còn mở là bất nhất giữa *chữ của đặc tả 30 feature* và *hành vi đã hiện thực* (C01), hoặc tham số chưa được nhóm chốt (C02–C03). C04 có hai chính sách validity khác tầng được ghi rõ; golden timestamp-aware không đổi và 46 bản ghi host C không timestamp vẫn NOT_EVALUABLE.

## Giải thích kỹ thuật phục vụ vấn đáp cá nhân

- **Vì sao extractor là chuẩn số học, không phải tài liệu?** Mô hình RF đã được huấn luyện trên đúng các số do `extractor.py` sinh ra. Nếu C làm theo một cách hiểu khác của tài liệu, vector đầu vào sẽ lệch phân phối huấn luyện dù 'đúng chữ'. Vì vậy mọi khác biệt được ghi thành issue có mã thay vì sửa lặng lẽ.
- **SHA-256 của thứ tự tên dùng để làm gì?** Một chuỗi băm ngắn đại diện cho thứ tự 23 tên; model card RF ghi cùng giá trị nên firmware có thể từ chối model/feature lệch schema chỉ bằng so sánh 64 ký tự.
- **C01 nghĩa là gì trong thực tế?** Nếu 40 mẫu đầu của cửa sổ 180 s bị thiếu, extractor đánh dấu cả `roll_rms_late_60` là INVALID dù block cuối đủ mẫu. Hiện thực C 'đúng đặc tả' sẽ báo VALID → khác validity. Case SYN27 bắt đúng tình huống này.
- **Tại sao cửa sổ nửa mở `(t-W, t]`?** Để mỗi mẫu thuộc đúng một block và cửa sổ có đúng 600 mẫu ở 10 Hz; nếu dùng `[t-W, t]` sẽ có 601 mẫu, thay đổi mean/RMS và phân vị — case SYN12 đặt gai đúng tại t-60 để phát hiện.
- **Population std khác sample std bao nhiêu?** Hệ số √(n/(n-1)) = 1,00083 với n = 600; với 3 mean block thì là √(3/2) = 1,22. Golden + dung sai phát hiện được cả hai.
