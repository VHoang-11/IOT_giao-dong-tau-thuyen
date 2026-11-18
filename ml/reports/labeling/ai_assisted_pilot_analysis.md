# Phân tích AI-assisted cho pilot 29 record

> **Cảnh báo bắt buộc.** Toàn bộ nội dung dưới đây là gợi ý do AI tạo (`annotation_method = AI_SUGGESTED`). Đây không phải quyết định human review, không phải nhãn ground truth và không phải đánh giá an toàn hàng hải. Mọi gợi ý vẫn **chưa được xác minh** cho đến khi người đánh giá thực sự xem xét. Không có dòng nào được ghi vào decision ledger, audit history hay bảng nhãn verified.

## 1. Phạm vi và nguyên tắc

- Batch phân tích: `ml/data/labels/annotation_pilot/batches/pilot_29.csv` (29 record), đối chiếu từng khóa với `ml/data/labels/annotation_pilot/annotation_pilot.csv`.
- Output: `ml/data/labels/ai_assisted_review/pilot_29_ai_suggestions.csv` (bảng gợi ý) và `ml/data/labels/ai_assisted_review/pilot_29_ai_metrics.json` (toàn bộ số đo để truy vết). Cả hai nằm trong `ml/data/labels/` nên bị `.gitignore` loại khỏi Git như các artifact nhãn khác.
- Mã tái lập: `ml/labeling/ai_assisted_review.py`, quy tắc `ai_observation_rules_v0.1`; chạy `python -m ml.labeling.ai_assisted_review`.
- Phenotype là mô tả hình thái tín hiệu đo được, không đồng nghĩa hazard vận hành. Không dùng ngưỡng mô phỏng, không tạo ngưỡng phân vị để ép đủ bốn lớp, không gán số confidence.
- Cửa sổ review là `(t-180, t]` trong đúng session/segment; bối cảnh chỉ lấy tối đa 180 s trước cửa sổ, cùng segment, không dùng dữ liệu sau endpoint (giống hình review của pilot).

## 2. Cách phân tích tín hiệu

Với mỗi record, script đọc trực tiếp `timeseries.parquet` đã preprocessing, cắt đúng cửa sổ và tính lại:

- **A. Dao động Roll:** mean, median, độ lệch chuẩn quần thể (mẫu số n), RMS (gồm cả offset), centered RMS (RMS sau khi trừ mean, bằng std quần thể), peak-to-peak, min/max.
- **B. Offset bền vững:** mean có dấu, median, dominant sign ratio, mean của ba block 60 s và chín sub-block 20 s, mean shift, độ lệch chuẩn giữa các block mean, mean của bối cảnh trước cửa sổ và trung bình từ đầu segment đến endpoint.
- **C. Tăng biên độ:** RMS sớm/muộn, RMS ratio, RMS slope, R² (đúng như feature), cộng thêm std quanh trung bình của ba block 60 s và chín sub-block 20 s, kiểm định xu hướng Mann–Kendall chính xác một phía trên chín giá trị std 20 s, so sánh với std 20 s trong bối cảnh trước cửa sổ, tương quan lag-1 giữa biên độ các nửa chu kỳ.
- **D. Chu kỳ:** zero-crossing sau khi trừ mean (tái sử dụng `period_values` của feature pipeline), chu kỳ median, CV chu kỳ, đối chiếu với đỉnh phổ (periodogram cửa sổ Hann, độ phân giải 1/180 Hz). Chu kỳ chỉ được coi là ổn định khi đỉnh phổ nằm trong khoảng tứ phân vị của các chu kỳ zero-crossing.
- **E. Chất lượng dữ liệu:** số mẫu, khoảng cách mẫu, ranh giới segment, coverage bối cảnh, lượng tử hóa, provenance (timestamp suy diễn, thiếu gyro, bộ lọc, model-scale).

Toàn bộ 23 angle feature và 3 period feature được tính lại độc lập bằng numpy rồi so với `feature_values.parquet`.

## 3. Quy tắc quan sát tường minh (`ai_observation_rules_v0.1`, chưa được nhóm phê duyệt)

| Phenotype | Mức | Tiêu chí (không có ngưỡng biên độ tuyệt đối) |
|---|---|---|
| HIGH_ROLL | luôn `NOT_ASSESSABLE_NO_VALIDATED_ENVELOPE` | Định nghĩa của dự án cần ngưỡng vận hành có căn cứ; hiện không có. Hạng phần trăm std chỉ để mô tả. |
| NORMAL | luôn `NOT_ASSESSABLE_NO_VALIDATED_ENVELOPE` | Cần operating envelope NORMAL độc lập; biên độ nhỏ không đủ. |
| PERSISTENT_OFFSET | `OBSERVED_CONSISTENT` | Mọi mẫu trong cửa sổ cùng dấu (tín hiệu không cắt mốc 0), 9/9 sub-block 20 s cùng dấu, và mọi mẫu bối cảnh có sẵn cùng dấu. |
| PERSISTENT_OFFSET | `OBSERVED_WEAK` | 9/9 sub-block cùng dấu và mean bối cảnh cùng dấu, nhưng dao động vẫn cắt mốc 0. |
| AMPLITUDE_GROWTH | `OBSERVED_CONSISTENT` | Mann–Kendall p < 0.05/29 (hiệu chỉnh Bonferroni cho cả batch), std ba block 60 s tăng đơn điệu, và std block cuối lớn hơn mọi std 20 s của bối cảnh. |
| AMPLITUDE_GROWTH | `OBSERVED_WEAK` | Mann–Kendall p < 0.05 danh nghĩa, hoặc std ba block tăng đơn điệu và sub-block 20 s mới nhất là cực đại của toàn bộ lịch sử quan sát. |

Nhãn gợi ý: đúng **một** phenotype `OBSERVED_CONSISTENT` và không có dấu hiệu yếu nào khác → gợi ý phenotype đó; có dấu hiệu yếu hoặc nhiều phenotype → `REVIEW_REQUIRED`; không có dấu hiệu → `UNLABELED` (không bao giờ là `NORMAL`). Mọi dòng đều `requires_human_review = true`. Mức ý nghĩa 0.05 là quy ước thống kê, không phải giới hạn an toàn.

## 4. Kết quả kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| Số record phân tích | 29 |
| Review ID khớp `pilot_29.csv` và form pilot | Đạt |
| Mọi cửa sổ nằm trong một segment, 1.800 mẫu, không gap > 1.5 chu kỳ | Đạt |
| Đối chiếu 26 feature với feature table | Đạt; sai lệch tuyệt đối lớn nhất 4.94e-07 |
| `annotation_method = AI_SUGGESTED`, `requires_human_review = true` | Đạt |
| Không gợi ý NORMAL/HIGH_ROLL, không có trạng thái VERIFIED/HUMAN_REVIEWED | Đạt |
| Mỗi dòng có evidence reference truy vết đến parquet/feature/plot/metrics | Đạt |
| Ledger/audit/verified label không đổi (SHA-256 trước = sau) | Đạt |

| Tệp được bảo vệ | SHA-256 trước và sau |
|---|---|
| `ml/data/labels/annotation_pilot/review_decisions.csv` | `e62a39399d73fb55…` |
| `ml/data/labels/annotation_pilot/review_audit.jsonl` | không tồn tại (không tạo mới) |
| `ml/data/labels/annotation_pilot/annotation_pilot.csv` | `83e96be12b4a68e0…` |
| `ml/data/labels/annotation_pilot/human_annotation_quality_summary.json` | `ba214651cdf6a530…` |
| `ml/data/labels/feasibility/hohai/verified_reviewed_annotations.parquet` | `b8576df1f4b0d316…` |
| `ml/data/labels/feasibility/seafar/verified_reviewed_annotations.parquet` | `b8576df1f4b0d316…` |
| `ml/data/labels/feasibility/southampton/verified_reviewed_annotations.parquet` | `b8576df1f4b0d316…` |

## 5. Tổng hợp pilot

Đã phân tích **29 record thực tế** thuộc 3 nguồn, 23 session và 25 segment.

| Nguồn | Record | Session | Segment | HIGH_ROLL | PERSISTENT_OFFSET | AMPLITUDE_GROWTH | REVIEW_REQUIRED | UNLABELED |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| hohai | 21 | 21 | 21 | 0 | 0 | 0 | 9 | 12 |
| seafar | 4 | 1 | 3 | 0 | 4 | 0 | 0 | 0 |
| southampton | 4 | 1 | 1 | 0 | 2 | 0 | 2 | 0 |
| **Tổng** | **29** | | | **0** | **6** | **0** | **11** | **12** |

| Phenotype | OBSERVED_CONSISTENT | OBSERVED_WEAK | NOT_OBSERVED | NOT_ASSESSABLE |
|---|---:|---:|---:|---:|
| HIGH_ROLL | 0 | 0 | 0 | 29 |
| PERSISTENT_OFFSET | 8 | 9 | 12 | 0 |
| AMPLITUDE_GROWTH | 1 | 3 | 25 | 0 |
| NORMAL | 0 | 0 | 0 | 29 |

**Mẫu hình phenotype chồng lấn** (C = nhất quán, W = yếu):

- không có cờ: 12 record
- PERSISTENT_OFFSET:W: 7 record
- PERSISTENT_OFFSET:C: 6 record
- PERSISTENT_OFFSET:W + AMPLITUDE_GROWTH:W: 2 record
- PERSISTENT_OFFSET:C + AMPLITUDE_GROWTH:W: 1 record
- PERSISTENT_OFFSET:C + AMPLITUDE_GROWTH:C: 1 record

- Số record cần người đánh giá: **29/29** (mọi gợi ý AI đều cần xác nhận). Trong đó 11 record là `REVIEW_REQUIRED` vì bằng chứng yếu hoặc chồng lấn.
- Số record không có đủ bằng chứng cho bất kỳ phenotype nào: **12** (`UNLABELED`). Không record nào đủ căn cứ cho `NORMAL` hoặc `HIGH_ROLL`.
- Cửa sổ chồng lấn trong batch (cùng segment): `PILOT-47dcb093bf41`/`PILOT-e6e911efbddf` chồng 70 s; `PILOT-e6e911efbddf`/`PILOT-db0b97396fc9` chồng 70 s; `PILOT-db0b97396fc9`/`PILOT-c2643af463e2` chồng 70 s. Các cửa sổ này không phải quan sát độc lập.

**Độ mạnh bằng chứng và giới hạn.** Bằng chứng mạnh nhất là offset có dấu của Seafar và Southampton: tín hiệu không cắt mốc 0 trong toàn cửa sổ. Tuy vậy, cả bốn record Seafar thuộc một session tàu thật duy nhất và bốn record Southampton thuộc một run nên số đơn vị độc lập rất nhỏ. Dấu hiệu tăng biên độ duy nhất vượt hiệu chỉnh đa kiểm định nằm ở cửa sổ Southampton cuối run và đi kèm tăng Pitch. Ở Hohai, 17/21 record có chu kỳ zero-crossing khớp đỉnh phổ; tín hiệu chủ yếu là dao động tuần hoàn với chu kỳ zero-crossing khoảng 1.57–1.87 s; các offset nhỏ cùng dấu là có thật về thống kê nhưng chưa thể nói có ý nghĩa vật lý.

## 6. Phân tích chi tiết từng record

## 6.1. Nguồn `hohai`

Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.

### 1. `PILOT-279f4ef04864` — hohai · `Berth_B_T7_Type_A` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_B_T7_Type_A/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-279f4ef04864.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.103 / 0.095 |
| A. Dao động | std quần thể = centered RMS (°) | 0.413 |
| A. Dao động | RMS gồm offset (°) | 0.425 |
| A. Dao động | peak-to-peak; min..max (°) | 3.044; -1.316..1.728 |
| B. Offset | dominant sign ratio; |mean|/std | 0.606; 0.25 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.098, 0.106, 0.106]; `+++++++++` |
| B. Offset | std mean block; mean shift (°) | 0.0037; 0.0081 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.294, 0.436, 0.516]; 1.757 |
| C. Tăng biên độ | RMS slope (°/phút); R² | 0.1112; 0.975 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.277, 0.423, 0.505]; 1.824 |
| C. Tăng biên độ | std 20 s (°) | [0.246, 0.267, 0.314, 0.373, 0.567, 0.276, 0.261, 0.500, 0.667] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | +18; 0.0376 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 204; 1.770; 0.157 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.651; ZC_AND_SPECTRUM_DISAGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; 0.095; 0.350 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.075; 0.066→0.072 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 2.44e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Độ lệch có dấu nhỏ: mean 0.103°, 9/9 sub-block 20 s cùng dấu nhưng dao động vẫn cắt mốc 0 (sign ratio 0.606, |mean|/std 0.25).
- Có dấu hiệu tăng biên độ nhưng chưa nhất quán: block 60 s [0.277, 0.423, 0.505]°, Mann–Kendall p=0.0376 (không đạt α hiệu chỉnh 0.0017).
- Dao động Roll quanh trung bình: std 0.413°, peak-to-peak 3.044°; std 60 s cuối ở hạng phần trăm 92 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ chưa tin cậy: zero-crossing 1.77 s, đỉnh phổ 1.65 s (nằm ngoài IQR chu kỳ zero-crossing), CV 0.16.

**4. Bằng chứng hỗ trợ.**

- Mean các block 60 s [0.098, 0.106, 0.106]° (độ lệch chuẩn giữa block 0.0037°, mean shift 0.0081°).
- Bối cảnh 180 s trước cửa sổ (coverage 100%) có mean 0.095°, sign ratio 0.623; trung bình Roll từ đầu segment đến endpoint (410 s) là 0.097°.
- Std 20 s (cũ→mới): [0.246, 0.267, 0.314, 0.373, 0.567, 0.276, 0.261, 0.500, 0.667]°; Mann–Kendall S=+18.
- Feature gốc: roll_rms_ratio_180 1.757, roll_rms_slope_180 0.1112°/phút, roll_rms_trend_r2_180 0.975; std quanh trung bình: tỷ lệ 1.824, slope 0.1141°/phút, R² 0.975.
- Std ba block 60 s tăng đơn điệu [0.277, 0.423, 0.505]°.
- Std 20 s mới nhất (0.667°) là cực đại của toàn bộ lịch sử quan sát (cửa sổ + bối cảnh); không có dữ liệu sau endpoint để biết nó kéo dài hay chỉ là đỉnh nhóm sóng.
- Std block 60 s cuối 0.505° lớn hơn std 20 s lớn nhất trong bối cảnh trước cửa sổ (0.467°).

**5. Bằng chứng mâu thuẫn.**

- Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực (list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.
- Dao động cắt qua mốc 0 (39.4% mẫu mang dấu ngược) và |mean|/std chỉ 0.25; tiêu chí 9/9 sub-block cùng dấu là bằng chứng thống kê, không phải bằng chứng độ lệch có ý nghĩa vật lý.
- Mann–Kendall p=0.0376 không vượt hiệu chỉnh đa kiểm định (α=0.05/29=0.0017); với 29 kiểm định ở α=0.05, kỳ vọng khoảng 1.45 kết quả dương tính giả.
- Biên độ các nửa chu kỳ liên tiếp tương quan mạnh (lag-1 = 0.82), có thể do nhóm sóng hoặc do chính xu hướng; các sub-block không độc lập nên p-value của Mann–Kendall có xu hướng lạc quan.
- Pitch tăng đồng thời (std 60 s sớm 0.066° → muộn 0.072°), gợi ý thay đổi kích thích bên ngoài (sóng/pha thí nghiệm) chứ không riêng cơ chế Roll; tín hiệu không đủ để xác định nguyên nhân.

**6. Nhãn hoặc trạng thái đề xuất.** `REVIEW_REQUIRED` — REVIEW_REQUIRED (có dấu hiệu nhưng chưa đủ căn cứ hoặc nhiều phenotype chồng lấn). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = dấu hiệu yếu/chưa kết luận; AMPLITUDE_GROWTH = dấu hiệu yếu/chưa kết luận; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- Ước lượng chu kỳ không ổn định (CV 0.16; đỉnh phổ 1.7 s, độ phân giải phổ 0.0056 Hz), nên không dùng chu kỳ làm bằng chứng phân lớp.
- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Độ lệch 0.103° có vượt sai số zero của cảm biến/khung thử không, và nhóm có định nghĩa biên độ tối thiểu cho PERSISTENT_OFFSET không?
- Sự tăng biên độ này có trùng với một pha thí nghiệm/khởi phát sóng hoặc sự kiện vận hành được ghi nhận không? Nhóm có chấp nhận tiêu chí tăng biên độ dựa trên kiểm định xu hướng và vượt lịch sử không?
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?
- Nhiều phenotype cùng xuất hiện: nhóm muốn giữ đồng thời các cờ hay chọn lớp chính theo quy ước nào?

### 2. `PILOT-3fd7945fc918` — hohai · `Berth_B_T8_Type_A` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_B_T8_Type_A/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-3fd7945fc918.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.007 / 0.006 |
| A. Dao động | std quần thể = centered RMS (°) | 0.469 |
| A. Dao động | RMS gồm offset (°) | 0.470 |
| A. Dao động | peak-to-peak; min..max (°) | 2.579; -1.270..1.309 |
| B. Offset | dominant sign ratio; |mean|/std | 0.505; 0.01 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.013, 0.008, 0.000]; `++-++---+` |
| B. Offset | std mean block; mean shift (°) | 0.0052; -0.0128 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.528, 0.456, 0.419]; 0.793 |
| C. Tăng biên độ | RMS slope (°/phút); R² | -0.0547; 0.967 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.528, 0.456, 0.419]; 0.793 |
| C. Tăng biên độ | std 20 s (°) | [0.637, 0.417, 0.503, 0.529, 0.511, 0.284, 0.274, 0.323, 0.586] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | -8; 0.8208 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 192; 1.843; 0.181 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.731; ZC_AND_SPECTRUM_DISAGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; 0.010; 0.472 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.093; 0.113→0.074 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 1.50e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Không thấy độ lệch có dấu bền vững: mean 0.007°, mẫu dấu sub-block `++-++---+`, sign ratio 0.505.
- Không thấy tăng biên độ bền vững: std block 60 s [0.528, 0.456, 0.419]°, Mann–Kendall p=0.8208.
- Dao động Roll quanh trung bình: std 0.469°, peak-to-peak 2.579°; std 60 s cuối ở hạng phần trăm 76 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ chưa tin cậy: zero-crossing 1.84 s, đỉnh phổ 1.73 s (nằm ngoài IQR chu kỳ zero-crossing), CV 0.18.

**4. Bằng chứng hỗ trợ.**

- Không có bằng chứng ủng hộ phenotype nào theo quy tắc quan sát; các chỉ số mô tả được liệt kê ở trên.

**5. Bằng chứng mâu thuẫn.**

- Không ghi nhận mâu thuẫn nội tại; giới hạn chính nằm ở phần độ không chắc chắn.

**6. Nhãn hoặc trạng thái đề xuất.** `UNLABELED` — UNLABELED (không có dấu hiệu phenotype theo quy tắc, nhưng không đủ căn cứ để gọi NORMAL). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = không quan sát thấy theo quy tắc; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- Ước lượng chu kỳ không ổn định (CV 0.18; đỉnh phổ 1.7 s, độ phân giải phổ 0.0056 Hz), nên không dùng chu kỳ làm bằng chứng phân lớp.
- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Không có phenotype nổi bật theo quy tắc. Nhóm có operating envelope NORMAL độc lập cho nguồn này không? Nếu không, cửa sổ phải giữ UNLABELED.
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 3. `PILOT-88aebf3cd137` — hohai · `Berth_B_T9_Type_A` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_B_T9_Type_A/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-88aebf3cd137.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.219 / 0.195 |
| A. Dao động | std quần thể = centered RMS (°) | 0.308 |
| A. Dao động | RMS gồm offset (°) | 0.378 |
| A. Dao động | peak-to-peak; min..max (°) | 1.938; -0.466..1.473 |
| B. Offset | dominant sign ratio; |mean|/std | 0.749; 0.71 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.240, 0.227, 0.190]; `+++++++++` |
| B. Offset | std mean block; mean shift (°) | 0.0211; -0.0496 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.370, 0.417, 0.343]; 0.927 |
| C. Tăng biên độ | RMS slope (°/phút); R² | -0.0136; 0.129 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.282, 0.350, 0.285]; 1.012 |
| C. Tăng biên độ | std 20 s (°) | [0.292, 0.260, 0.287, 0.287, 0.444, 0.266, 0.325, 0.250, 0.261] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | -6; 0.7616 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 176; 1.569; 0.510 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 45.000; ZC_AND_SPECTRUM_DISAGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; 0.202; 0.282 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.083; 0.094→0.067 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 9.82e-08 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Độ lệch có dấu nhỏ: mean 0.219°, 9/9 sub-block 20 s cùng dấu nhưng dao động vẫn cắt mốc 0 (sign ratio 0.749, |mean|/std 0.71).
- Không thấy tăng biên độ bền vững: std block 60 s [0.282, 0.350, 0.285]°, Mann–Kendall p=0.7616.
- Dao động Roll quanh trung bình: std 0.308°, peak-to-peak 1.938°; std 60 s cuối ở hạng phần trăm 25 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ chưa tin cậy: zero-crossing 1.57 s, đỉnh phổ 45.00 s (nằm ngoài IQR chu kỳ zero-crossing), CV 0.51.

**4. Bằng chứng hỗ trợ.**

- Mean các block 60 s [0.240, 0.227, 0.190]° (độ lệch chuẩn giữa block 0.0211°, mean shift -0.0496°).
- Bối cảnh 180 s trước cửa sổ (coverage 100%) có mean 0.202°, sign ratio 0.757; trung bình Roll từ đầu segment đến endpoint (410 s) là 0.193°.

**5. Bằng chứng mâu thuẫn.**

- Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực (list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.
- Dao động cắt qua mốc 0 (25.1% mẫu mang dấu ngược) và |mean|/std chỉ 0.71; tiêu chí 9/9 sub-block cùng dấu là bằng chứng thống kê, không phải bằng chứng độ lệch có ý nghĩa vật lý.

**6. Nhãn hoặc trạng thái đề xuất.** `REVIEW_REQUIRED` — REVIEW_REQUIRED (có dấu hiệu nhưng chưa đủ căn cứ hoặc nhiều phenotype chồng lấn). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = dấu hiệu yếu/chưa kết luận; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- Ước lượng chu kỳ không ổn định (CV 0.51; đỉnh phổ 45.0 s, độ phân giải phổ 0.0056 Hz), nên không dùng chu kỳ làm bằng chứng phân lớp.
- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Độ lệch 0.219° có vượt sai số zero của cảm biến/khung thử không, và nhóm có định nghĩa biên độ tối thiểu cho PERSISTENT_OFFSET không?
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 4. `PILOT-b028a7937b2d` — hohai · `Berth_C_T7_Type_A` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_C_T7_Type_A/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-b028a7937b2d.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.002 / -0.000 |
| A. Dao động | std quần thể = centered RMS (°) | 0.359 |
| A. Dao động | RMS gồm offset (°) | 0.359 |
| A. Dao động | peak-to-peak; min..max (°) | 2.371; -1.165..1.206 |
| B. Offset | dominant sign ratio; |mean|/std | 0.501; 0.01 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [-0.005, 0.006, 0.005]; `-+--++--+` |
| B. Offset | std mean block; mean shift (°) | 0.0049; 0.0101 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.351, 0.363, 0.362]; 1.032 |
| C. Tăng biên độ | RMS slope (°/phút); R² | 0.0056; 0.666 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.351, 0.363, 0.362]; 1.032 |
| C. Tăng biên độ | std 20 s (°) | [0.424, 0.385, 0.202, 0.276, 0.305, 0.475, 0.260, 0.352, 0.447] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | +4; 0.3807 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 199; 1.787; 0.188 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.651; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; -0.007; 0.280 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.085; 0.075→0.088 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 3.60e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Không thấy độ lệch có dấu bền vững: mean 0.002°, mẫu dấu sub-block `-+--++--+`, sign ratio 0.501.
- Không thấy tăng biên độ bền vững: std block 60 s [0.351, 0.363, 0.362]°, Mann–Kendall p=0.3807.
- Dao động Roll quanh trung bình: std 0.359°, peak-to-peak 2.371°; std 60 s cuối ở hạng phần trăm 59 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 1.79 s (zero-crossing) khớp đỉnh phổ 1.65 s; CV chu kỳ 0.19.

**4. Bằng chứng hỗ trợ.**

- Không có bằng chứng ủng hộ phenotype nào theo quy tắc quan sát; các chỉ số mô tả được liệt kê ở trên.

**5. Bằng chứng mâu thuẫn.**

- Không ghi nhận mâu thuẫn nội tại; giới hạn chính nằm ở phần độ không chắc chắn.

**6. Nhãn hoặc trạng thái đề xuất.** `UNLABELED` — UNLABELED (không có dấu hiệu phenotype theo quy tắc, nhưng không đủ căn cứ để gọi NORMAL). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = không quan sát thấy theo quy tắc; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Không có phenotype nổi bật theo quy tắc. Nhóm có operating envelope NORMAL độc lập cho nguồn này không? Nếu không, cửa sổ phải giữ UNLABELED.
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 5. `PILOT-956fc7400682` — hohai · `Berth_C_T8_Type_A` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_C_T8_Type_A/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-956fc7400682.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.070 / 0.063 |
| A. Dao động | std quần thể = centered RMS (°) | 0.403 |
| A. Dao động | RMS gồm offset (°) | 0.409 |
| A. Dao động | peak-to-peak; min..max (°) | 2.908; -1.116..1.792 |
| B. Offset | dominant sign ratio; |mean|/std | 0.562; 0.17 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.081, 0.075, 0.055]; `+++++++++` |
| B. Offset | std mean block; mean shift (°) | 0.0110; -0.0255 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.490, 0.367, 0.356]; 0.727 |
| C. Tăng biên độ | RMS slope (°/phút); R² | -0.0670; 0.808 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.484, 0.359, 0.352]; 0.728 |
| C. Tăng biên độ | std 20 s (°) | [0.592, 0.246, 0.537, 0.340, 0.429, 0.282, 0.370, 0.286, 0.390] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | -6; 0.7616 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 191; 1.822; 0.258 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.636; ZC_AND_SPECTRUM_DISAGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; 0.080; 0.384 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.102; 0.123→0.087 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 4.94e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Độ lệch có dấu nhỏ: mean 0.070°, 9/9 sub-block 20 s cùng dấu nhưng dao động vẫn cắt mốc 0 (sign ratio 0.562, |mean|/std 0.17).
- Không thấy tăng biên độ bền vững: std block 60 s [0.484, 0.359, 0.352]°, Mann–Kendall p=0.7616.
- Dao động Roll quanh trung bình: std 0.403°, peak-to-peak 2.908°; std 60 s cuối ở hạng phần trăm 56 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ chưa tin cậy: zero-crossing 1.82 s, đỉnh phổ 1.64 s (nằm ngoài IQR chu kỳ zero-crossing), CV 0.26.

**4. Bằng chứng hỗ trợ.**

- Mean các block 60 s [0.081, 0.075, 0.055]° (độ lệch chuẩn giữa block 0.0110°, mean shift -0.0255°).
- Bối cảnh 180 s trước cửa sổ (coverage 100%) có mean 0.080°, sign ratio 0.563; trung bình Roll từ đầu segment đến endpoint (410 s) là 0.067°.

**5. Bằng chứng mâu thuẫn.**

- Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực (list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.
- Dao động cắt qua mốc 0 (43.8% mẫu mang dấu ngược) và |mean|/std chỉ 0.17; tiêu chí 9/9 sub-block cùng dấu là bằng chứng thống kê, không phải bằng chứng độ lệch có ý nghĩa vật lý.

**6. Nhãn hoặc trạng thái đề xuất.** `REVIEW_REQUIRED` — REVIEW_REQUIRED (có dấu hiệu nhưng chưa đủ căn cứ hoặc nhiều phenotype chồng lấn). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = dấu hiệu yếu/chưa kết luận; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- Ước lượng chu kỳ không ổn định (CV 0.26; đỉnh phổ 1.6 s, độ phân giải phổ 0.0056 Hz), nên không dùng chu kỳ làm bằng chứng phân lớp.
- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Độ lệch 0.070° có vượt sai số zero của cảm biến/khung thử không, và nhóm có định nghĩa biên độ tối thiểu cho PERSISTENT_OFFSET không?
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 6. `PILOT-090f81a94959` — hohai · `Berth_C_T9_Type_A` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_C_T9_Type_A/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-090f81a94959.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.006 / -0.024 |
| A. Dao động | std quần thể = centered RMS (°) | 0.404 |
| A. Dao động | RMS gồm offset (°) | 0.404 |
| A. Dao động | peak-to-peak; min..max (°) | 2.819; -1.307..1.513 |
| B. Offset | dominant sign ratio; |mean|/std | 0.531; 0.01 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.039, 0.000, -0.021]; `+--+----+` |
| B. Offset | std mean block; mean shift (°) | 0.0246; -0.0595 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.490, 0.304, 0.396]; 0.808 |
| C. Tăng biên độ | RMS slope (°/phút); R² | -0.0470; 0.255 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.488, 0.304, 0.395]; 0.810 |
| C. Tăng biên độ | std 20 s (°) | [0.471, 0.492, 0.484, 0.386, 0.220, 0.273, 0.381, 0.190, 0.536] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | -10; 0.8702 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 176; 1.871; 0.327 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.818; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; 0.029; 0.384 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.104; 0.119→0.098 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 1.74e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Không thấy độ lệch có dấu bền vững: mean 0.006°, mẫu dấu sub-block `+--+----+`, sign ratio 0.531.
- Không thấy tăng biên độ bền vững: std block 60 s [0.488, 0.304, 0.395]°, Mann–Kendall p=0.8702.
- Dao động Roll quanh trung bình: std 0.404°, peak-to-peak 2.819°; std 60 s cuối ở hạng phần trăm 70 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 1.87 s (zero-crossing) khớp đỉnh phổ 1.82 s; CV chu kỳ 0.33.

**4. Bằng chứng hỗ trợ.**

- Không có bằng chứng ủng hộ phenotype nào theo quy tắc quan sát; các chỉ số mô tả được liệt kê ở trên.

**5. Bằng chứng mâu thuẫn.**

- Không ghi nhận mâu thuẫn nội tại; giới hạn chính nằm ở phần độ không chắc chắn.

**6. Nhãn hoặc trạng thái đề xuất.** `UNLABELED` — UNLABELED (không có dấu hiệu phenotype theo quy tắc, nhưng không đủ căn cứ để gọi NORMAL). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = không quan sát thấy theo quy tắc; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Không có phenotype nổi bật theo quy tắc. Nhóm có operating envelope NORMAL độc lập cho nguồn này không? Nếu không, cửa sổ phải giữ UNLABELED.
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 7. `PILOT-fb9568c660df` — hohai · `Berth_D_T1_Type_A` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_D_T1_Type_A/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-fb9568c660df.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | -0.020 / -0.018 |
| A. Dao động | std quần thể = centered RMS (°) | 0.292 |
| A. Dao động | RMS gồm offset (°) | 0.293 |
| A. Dao động | peak-to-peak; min..max (°) | 2.138; -1.150..0.988 |
| B. Offset | dominant sign ratio; |mean|/std | 0.528; 0.07 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [-0.022, -0.018, -0.020]; `---------` |
| B. Offset | std mean block; mean shift (°) | 0.0019; 0.0029 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.266, 0.233, 0.363]; 1.366 |
| C. Tăng biên độ | RMS slope (°/phút); R² | 0.0487; 0.516 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.265, 0.233, 0.363]; 1.369 |
| C. Tăng biên độ | std 20 s (°) | [0.259, 0.283, 0.251, 0.231, 0.252, 0.213, 0.449, 0.378, 0.223] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | -4; 0.6939 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 201; 1.753; 0.188 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.818; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; -0.018; 0.267 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.074; 0.070→0.086 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 1.23e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Độ lệch có dấu nhỏ: mean -0.020°, 9/9 sub-block 20 s cùng dấu nhưng dao động vẫn cắt mốc 0 (sign ratio 0.528, |mean|/std 0.07).
- Không thấy tăng biên độ bền vững: std block 60 s [0.265, 0.233, 0.363]°, Mann–Kendall p=0.6939.
- Dao động Roll quanh trung bình: std 0.292°, peak-to-peak 2.138°; std 60 s cuối ở hạng phần trăm 60 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 1.75 s (zero-crossing) khớp đỉnh phổ 1.82 s; CV chu kỳ 0.19.

**4. Bằng chứng hỗ trợ.**

- Mean các block 60 s [-0.022, -0.018, -0.020]° (độ lệch chuẩn giữa block 0.0019°, mean shift 0.0029°).
- Bối cảnh 180 s trước cửa sổ (coverage 100%) có mean -0.018°, sign ratio 0.511; trung bình Roll từ đầu segment đến endpoint (410 s) là -0.019°.

**5. Bằng chứng mâu thuẫn.**

- Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực (list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.
- Dao động cắt qua mốc 0 (47.2% mẫu mang dấu ngược) và |mean|/std chỉ 0.07; tiêu chí 9/9 sub-block cùng dấu là bằng chứng thống kê, không phải bằng chứng độ lệch có ý nghĩa vật lý.

**6. Nhãn hoặc trạng thái đề xuất.** `REVIEW_REQUIRED` — REVIEW_REQUIRED (có dấu hiệu nhưng chưa đủ căn cứ hoặc nhiều phenotype chồng lấn). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = dấu hiệu yếu/chưa kết luận; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Độ lệch -0.020° có vượt sai số zero của cảm biến/khung thử không, và nhóm có định nghĩa biên độ tối thiểu cho PERSISTENT_OFFSET không?
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 8. `PILOT-20a033e3fa2b` — hohai · `Berth_D_T2_Type_A` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_D_T2_Type_A/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-20a033e3fa2b.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | -0.002 / 0.000 |
| A. Dao động | std quần thể = centered RMS (°) | 0.271 |
| A. Dao động | RMS gồm offset (°) | 0.271 |
| A. Dao động | peak-to-peak; min..max (°) | 1.584; -0.768..0.816 |
| B. Offset | dominant sign ratio; |mean|/std | 0.501; 0.01 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [-0.009, 0.001, 0.003]; `+--+-+++-` |
| B. Offset | std mean block; mean shift (°) | 0.0050; 0.0113 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.250, 0.282, 0.279]; 1.114 |
| C. Tăng biên độ | RMS slope (°/phút); R² | 0.0142; 0.656 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.250, 0.282, 0.279]; 1.115 |
| C. Tăng biên độ | std 20 s (°) | [0.258, 0.273, 0.215, 0.290, 0.264, 0.292, 0.292, 0.307, 0.230] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | +14; 0.0901 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 203; 1.752; 0.194 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.682; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; 0.006; 0.253 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.077; 0.080→0.082 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 3.96e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Không thấy độ lệch có dấu bền vững: mean -0.002°, mẫu dấu sub-block `+--+-+++-`, sign ratio 0.501.
- Không thấy tăng biên độ bền vững: std block 60 s [0.250, 0.282, 0.279]°, Mann–Kendall p=0.0901.
- Dao động Roll quanh trung bình: std 0.271°, peak-to-peak 1.584°; std 60 s cuối ở hạng phần trăm 22 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 1.75 s (zero-crossing) khớp đỉnh phổ 1.68 s; CV chu kỳ 0.19.

**4. Bằng chứng hỗ trợ.**

- Không có bằng chứng ủng hộ phenotype nào theo quy tắc quan sát; các chỉ số mô tả được liệt kê ở trên.

**5. Bằng chứng mâu thuẫn.**

- Không ghi nhận mâu thuẫn nội tại; giới hạn chính nằm ở phần độ không chắc chắn.

**6. Nhãn hoặc trạng thái đề xuất.** `UNLABELED` — UNLABELED (không có dấu hiệu phenotype theo quy tắc, nhưng không đủ căn cứ để gọi NORMAL). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = không quan sát thấy theo quy tắc; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Không có phenotype nổi bật theo quy tắc. Nhóm có operating envelope NORMAL độc lập cho nguồn này không? Nếu không, cửa sổ phải giữ UNLABELED.
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 9. `PILOT-bbe8594ca0be` — hohai · `Berth_D_T3_Type_A` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_D_T3_Type_A/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-bbe8594ca0be.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.043 / 0.049 |
| A. Dao động | std quần thể = centered RMS (°) | 0.350 |
| A. Dao động | RMS gồm offset (°) | 0.353 |
| A. Dao động | peak-to-peak; min..max (°) | 2.555; -1.199..1.356 |
| B. Offset | dominant sign ratio; |mean|/std | 0.551; 0.12 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.052, 0.038, 0.038]; `+++++++++` |
| B. Offset | std mean block; mean shift (°) | 0.0068; -0.0145 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.396, 0.362, 0.292]; 0.736 |
| C. Tăng biên độ | RMS slope (°/phút); R² | -0.0523; 0.961 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.393, 0.360, 0.289]; 0.737 |
| C. Tăng biên độ | std 20 s (°) | [0.521, 0.338, 0.275, 0.301, 0.382, 0.390, 0.363, 0.189, 0.288] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | -10; 0.8702 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 188; 1.835; 0.188 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.875; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; 0.017; 0.280 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.080; 0.084→0.067 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 8.41e-08 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Độ lệch có dấu nhỏ: mean 0.043°, 9/9 sub-block 20 s cùng dấu nhưng dao động vẫn cắt mốc 0 (sign ratio 0.551, |mean|/std 0.12).
- Không thấy tăng biên độ bền vững: std block 60 s [0.393, 0.360, 0.289]°, Mann–Kendall p=0.8702.
- Dao động Roll quanh trung bình: std 0.350°, peak-to-peak 2.555°; std 60 s cuối ở hạng phần trăm 27 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 1.83 s (zero-crossing) khớp đỉnh phổ 1.88 s; CV chu kỳ 0.19.

**4. Bằng chứng hỗ trợ.**

- Mean các block 60 s [0.052, 0.038, 0.038]° (độ lệch chuẩn giữa block 0.0068°, mean shift -0.0145°).
- Bối cảnh 180 s trước cửa sổ (coverage 100%) có mean 0.017°, sign ratio 0.526; trung bình Roll từ đầu segment đến endpoint (410 s) là 0.026°.

**5. Bằng chứng mâu thuẫn.**

- Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực (list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.
- Dao động cắt qua mốc 0 (44.9% mẫu mang dấu ngược) và |mean|/std chỉ 0.12; tiêu chí 9/9 sub-block cùng dấu là bằng chứng thống kê, không phải bằng chứng độ lệch có ý nghĩa vật lý.

**6. Nhãn hoặc trạng thái đề xuất.** `REVIEW_REQUIRED` — REVIEW_REQUIRED (có dấu hiệu nhưng chưa đủ căn cứ hoặc nhiều phenotype chồng lấn). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = dấu hiệu yếu/chưa kết luận; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Độ lệch 0.043° có vượt sai số zero của cảm biến/khung thử không, và nhóm có định nghĩa biên độ tối thiểu cho PERSISTENT_OFFSET không?
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 10. `PILOT-cf348b067c1e` — hohai · `Berth_D_T3_Type_B` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_D_T3_Type_B/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-cf348b067c1e.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | -0.062 / -0.071 |
| A. Dao động | std quần thể = centered RMS (°) | 0.303 |
| A. Dao động | RMS gồm offset (°) | 0.309 |
| A. Dao động | peak-to-peak; min..max (°) | 1.836; -0.980..0.856 |
| B. Offset | dominant sign ratio; |mean|/std | 0.588; 0.20 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [-0.063, -0.047, -0.077]; `---------` |
| B. Offset | std mean block; mean shift (°) | 0.0122; -0.0137 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.303, 0.342, 0.281]; 0.927 |
| C. Tăng biên độ | RMS slope (°/phút); R² | -0.0110; 0.126 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.296, 0.338, 0.270]; 0.912 |
| C. Tăng biên độ | std 20 s (°) | [0.368, 0.226, 0.276, 0.333, 0.371, 0.309, 0.300, 0.137, 0.332] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | -4; 0.6939 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 190; 1.839; 0.227 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.856; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; -0.050; 0.263 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.058; 0.057→0.046 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 4.81e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Độ lệch có dấu nhỏ: mean -0.062°, 9/9 sub-block 20 s cùng dấu nhưng dao động vẫn cắt mốc 0 (sign ratio 0.588, |mean|/std 0.20).
- Không thấy tăng biên độ bền vững: std block 60 s [0.296, 0.338, 0.270]°, Mann–Kendall p=0.6939.
- Dao động Roll quanh trung bình: std 0.303°, peak-to-peak 1.836°; std 60 s cuối ở hạng phần trăm 18 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 1.84 s (zero-crossing) khớp đỉnh phổ 1.86 s; CV chu kỳ 0.23.

**4. Bằng chứng hỗ trợ.**

- Mean các block 60 s [-0.063, -0.047, -0.077]° (độ lệch chuẩn giữa block 0.0122°, mean shift -0.0137°).
- Bối cảnh 180 s trước cửa sổ (coverage 100%) có mean -0.050°, sign ratio 0.607; trung bình Roll từ đầu segment đến endpoint (410 s) là -0.053°.

**5. Bằng chứng mâu thuẫn.**

- Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực (list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.
- Dao động cắt qua mốc 0 (41.2% mẫu mang dấu ngược) và |mean|/std chỉ 0.20; tiêu chí 9/9 sub-block cùng dấu là bằng chứng thống kê, không phải bằng chứng độ lệch có ý nghĩa vật lý.

**6. Nhãn hoặc trạng thái đề xuất.** `REVIEW_REQUIRED` — REVIEW_REQUIRED (có dấu hiệu nhưng chưa đủ căn cứ hoặc nhiều phenotype chồng lấn). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = dấu hiệu yếu/chưa kết luận; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Độ lệch -0.062° có vượt sai số zero của cảm biến/khung thử không, và nhóm có định nghĩa biên độ tối thiểu cho PERSISTENT_OFFSET không?
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 11. `PILOT-e0713611700d` — hohai · `Berth_D_T3_Type_C` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_D_T3_Type_C/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-e0713611700d.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.008 / 0.008 |
| A. Dao động | std quần thể = centered RMS (°) | 0.272 |
| A. Dao động | RMS gồm offset (°) | 0.272 |
| A. Dao động | peak-to-peak; min..max (°) | 2.060; -0.971..1.089 |
| B. Offset | dominant sign ratio; |mean|/std | 0.511; 0.03 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.003, 0.014, 0.007]; `-+++-++-+` |
| B. Offset | std mean block; mean shift (°) | 0.0047; 0.0046 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.280, 0.304, 0.227]; 0.809 |
| C. Tăng biên độ | RMS slope (°/phút); R² | -0.0268; 0.456 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.280, 0.304, 0.226]; 0.808 |
| C. Tăng biên độ | std 20 s (°) | [0.227, 0.217, 0.368, 0.262, 0.329, 0.315, 0.268, 0.204, 0.201] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | -10; 0.8702 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 190; 1.869; 0.256 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.837; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; -0.007; 0.289 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.060; 0.068→0.050 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 1.27e-09 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Không thấy độ lệch có dấu bền vững: mean 0.008°, mẫu dấu sub-block `-+++-++-+`, sign ratio 0.511.
- Không thấy tăng biên độ bền vững: std block 60 s [0.280, 0.304, 0.226]°, Mann–Kendall p=0.8702.
- Dao động Roll quanh trung bình: std 0.272°, peak-to-peak 2.060°; std 60 s cuối ở hạng phần trăm 3 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 1.87 s (zero-crossing) khớp đỉnh phổ 1.84 s; CV chu kỳ 0.26.

**4. Bằng chứng hỗ trợ.**

- Không có bằng chứng ủng hộ phenotype nào theo quy tắc quan sát; các chỉ số mô tả được liệt kê ở trên.

**5. Bằng chứng mâu thuẫn.**

- Không ghi nhận mâu thuẫn nội tại; giới hạn chính nằm ở phần độ không chắc chắn.

**6. Nhãn hoặc trạng thái đề xuất.** `UNLABELED` — UNLABELED (không có dấu hiệu phenotype theo quy tắc, nhưng không đủ căn cứ để gọi NORMAL). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = không quan sát thấy theo quy tắc; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Không có phenotype nổi bật theo quy tắc. Nhóm có operating envelope NORMAL độc lập cho nguồn này không? Nếu không, cửa sổ phải giữ UNLABELED.
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 12. `PILOT-eb227a45a3de` — hohai · `Berth_D_T4_Type_A` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_D_T4_Type_A/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-eb227a45a3de.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | -0.021 / -0.022 |
| A. Dao động | std quần thể = centered RMS (°) | 0.289 |
| A. Dao động | RMS gồm offset (°) | 0.290 |
| A. Dao động | peak-to-peak; min..max (°) | 1.635; -0.848..0.787 |
| B. Offset | dominant sign ratio; |mean|/std | 0.527; 0.07 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [-0.018, -0.024, -0.020]; `---------` |
| B. Offset | std mean block; mean shift (°) | 0.0024; -0.0020 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.235, 0.318, 0.310]; 1.322 |
| C. Tăng biên độ | RMS slope (°/phút); R² | 0.0378; 0.677 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.234, 0.317, 0.309]; 1.324 |
| C. Tăng biên độ | std 20 s (°) | [0.269, 0.206, 0.221, 0.346, 0.388, 0.174, 0.202, 0.354, 0.347] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | +6; 0.3061 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 199; 1.799; 0.170 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.782; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; -0.012; 0.306 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.080; 0.072→0.081 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 1.92e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Độ lệch có dấu nhỏ: mean -0.021°, 9/9 sub-block 20 s cùng dấu nhưng dao động vẫn cắt mốc 0 (sign ratio 0.527, |mean|/std 0.07).
- Không thấy tăng biên độ bền vững: std block 60 s [0.234, 0.317, 0.309]°, Mann–Kendall p=0.3061.
- Dao động Roll quanh trung bình: std 0.289°, peak-to-peak 1.635°; std 60 s cuối ở hạng phần trăm 38 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 1.80 s (zero-crossing) khớp đỉnh phổ 1.78 s; CV chu kỳ 0.17.

**4. Bằng chứng hỗ trợ.**

- Mean các block 60 s [-0.018, -0.024, -0.020]° (độ lệch chuẩn giữa block 0.0024°, mean shift -0.0020°).
- Bối cảnh 180 s trước cửa sổ (coverage 100%) có mean -0.012°, sign ratio 0.509; trung bình Roll từ đầu segment đến endpoint (410 s) là -0.015°.

**5. Bằng chứng mâu thuẫn.**

- Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực (list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.
- Dao động cắt qua mốc 0 (47.3% mẫu mang dấu ngược) và |mean|/std chỉ 0.07; tiêu chí 9/9 sub-block cùng dấu là bằng chứng thống kê, không phải bằng chứng độ lệch có ý nghĩa vật lý.

**6. Nhãn hoặc trạng thái đề xuất.** `REVIEW_REQUIRED` — REVIEW_REQUIRED (có dấu hiệu nhưng chưa đủ căn cứ hoặc nhiều phenotype chồng lấn). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = dấu hiệu yếu/chưa kết luận; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Độ lệch -0.021° có vượt sai số zero của cảm biến/khung thử không, và nhóm có định nghĩa biên độ tối thiểu cho PERSISTENT_OFFSET không?
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 13. `PILOT-946d956f1ec8` — hohai · `Berth_D_T5_Type_A` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_D_T5_Type_A/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-946d956f1ec8.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.006 / -0.001 |
| A. Dao động | std quần thể = centered RMS (°) | 0.274 |
| A. Dao động | RMS gồm offset (°) | 0.274 |
| A. Dao động | peak-to-peak; min..max (°) | 1.926; -0.921..1.005 |
| B. Offset | dominant sign ratio; |mean|/std | 0.503; 0.02 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.004, -0.001, 0.016]; `-++-+--++` |
| B. Offset | std mean block; mean shift (°) | 0.0073; 0.0119 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.259, 0.218, 0.333]; 1.282 |
| C. Tăng biên độ | RMS slope (°/phút); R² | 0.0366; 0.397 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.259, 0.218, 0.332]; 1.281 |
| C. Tăng biên độ | std 20 s (°) | [0.221, 0.280, 0.273, 0.287, 0.148, 0.195, 0.229, 0.280, 0.446] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | +10; 0.1792 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 200; 1.767; 0.183 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.800; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; -0.004; 0.254 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.085; 0.092→0.087 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 3.82e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Không thấy độ lệch có dấu bền vững: mean 0.006°, mẫu dấu sub-block `-++-+--++`, sign ratio 0.503.
- Không thấy tăng biên độ bền vững: std block 60 s [0.259, 0.218, 0.332]°, Mann–Kendall p=0.1792.
- Dao động Roll quanh trung bình: std 0.274°, peak-to-peak 1.926°; std 60 s cuối ở hạng phần trăm 48 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 1.77 s (zero-crossing) khớp đỉnh phổ 1.80 s; CV chu kỳ 0.18.

**4. Bằng chứng hỗ trợ.**

- Không có bằng chứng ủng hộ phenotype nào theo quy tắc quan sát; các chỉ số mô tả được liệt kê ở trên.

**5. Bằng chứng mâu thuẫn.**

- Không ghi nhận mâu thuẫn nội tại; giới hạn chính nằm ở phần độ không chắc chắn.

**6. Nhãn hoặc trạng thái đề xuất.** `UNLABELED` — UNLABELED (không có dấu hiệu phenotype theo quy tắc, nhưng không đủ căn cứ để gọi NORMAL). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = không quan sát thấy theo quy tắc; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Không có phenotype nổi bật theo quy tắc. Nhóm có operating envelope NORMAL độc lập cho nguồn này không? Nếu không, cửa sổ phải giữ UNLABELED.
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 14. `PILOT-863838c95dfb` — hohai · `Berth_D_T6_Type_A` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_D_T6_Type_A/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-863838c95dfb.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.002 / -0.005 |
| A. Dao động | std quần thể = centered RMS (°) | 0.312 |
| A. Dao động | RMS gồm offset (°) | 0.312 |
| A. Dao động | peak-to-peak; min..max (°) | 1.706; -0.781..0.924 |
| B. Offset | dominant sign ratio; |mean|/std | 0.507; 0.01 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.010, 0.010, -0.013]; `++-++-+--` |
| B. Offset | std mean block; mean shift (°) | 0.0110; -0.0236 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.304, 0.309, 0.324]; 1.065 |
| C. Tăng biên độ | RMS slope (°/phút); R² | 0.0098; 0.936 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.304, 0.309, 0.323]; 1.064 |
| C. Tăng biên độ | std 20 s (°) | [0.317, 0.353, 0.226, 0.303, 0.296, 0.321, 0.350, 0.335, 0.277] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | +0; 0.5403 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 196; 1.831; 0.207 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.875; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; 0.005; 0.291 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.082; 0.082→0.073 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 2.04e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Không thấy độ lệch có dấu bền vững: mean 0.002°, mẫu dấu sub-block `++-++-+--`, sign ratio 0.507.
- Không thấy tăng biên độ bền vững: std block 60 s [0.304, 0.309, 0.323]°, Mann–Kendall p=0.5403.
- Dao động Roll quanh trung bình: std 0.312°, peak-to-peak 1.706°; std 60 s cuối ở hạng phần trăm 44 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 1.83 s (zero-crossing) khớp đỉnh phổ 1.88 s; CV chu kỳ 0.21.

**4. Bằng chứng hỗ trợ.**

- Không có bằng chứng ủng hộ phenotype nào theo quy tắc quan sát; các chỉ số mô tả được liệt kê ở trên.

**5. Bằng chứng mâu thuẫn.**

- Không ghi nhận mâu thuẫn nội tại; giới hạn chính nằm ở phần độ không chắc chắn.

**6. Nhãn hoặc trạng thái đề xuất.** `UNLABELED` — UNLABELED (không có dấu hiệu phenotype theo quy tắc, nhưng không đủ căn cứ để gọi NORMAL). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = không quan sát thấy theo quy tắc; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Không có phenotype nổi bật theo quy tắc. Nhóm có operating envelope NORMAL độc lập cho nguồn này không? Nếu không, cửa sổ phải giữ UNLABELED.
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 15. `PILOT-145c94faa7bc` — hohai · `Berth_D_T6_Type_B` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_D_T6_Type_B/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-145c94faa7bc.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | -0.003 / -0.011 |
| A. Dao động | std quần thể = centered RMS (°) | 0.308 |
| A. Dao động | RMS gồm offset (°) | 0.308 |
| A. Dao động | peak-to-peak; min..max (°) | 1.823; -0.903..0.920 |
| B. Offset | dominant sign ratio; |mean|/std | 0.515; 0.01 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.001, -0.009, -0.000]; `+--+--++-` |
| B. Offset | std mean block; mean shift (°) | 0.0044; -0.0009 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.300, 0.344, 0.277]; 0.922 |
| C. Tăng biên độ | RMS slope (°/phút); R² | -0.0117; 0.119 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.300, 0.343, 0.277]; 0.922 |
| C. Tăng biên độ | std 20 s (°) | [0.393, 0.221, 0.257, 0.343, 0.409, 0.260, 0.322, 0.243, 0.260] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | -4; 0.6939 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 188; 1.865; 0.239 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.875; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; -0.003; 0.319 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.069; 0.070→0.061 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 2.28e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Không thấy độ lệch có dấu bền vững: mean -0.003°, mẫu dấu sub-block `+--+--++-`, sign ratio 0.515.
- Không thấy tăng biên độ bền vững: std block 60 s [0.300, 0.343, 0.277]°, Mann–Kendall p=0.6939.
- Dao động Roll quanh trung bình: std 0.308°, peak-to-peak 1.823°; std 60 s cuối ở hạng phần trăm 21 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 1.86 s (zero-crossing) khớp đỉnh phổ 1.88 s; CV chu kỳ 0.24.

**4. Bằng chứng hỗ trợ.**

- Không có bằng chứng ủng hộ phenotype nào theo quy tắc quan sát; các chỉ số mô tả được liệt kê ở trên.

**5. Bằng chứng mâu thuẫn.**

- Không ghi nhận mâu thuẫn nội tại; giới hạn chính nằm ở phần độ không chắc chắn.

**6. Nhãn hoặc trạng thái đề xuất.** `UNLABELED` — UNLABELED (không có dấu hiệu phenotype theo quy tắc, nhưng không đủ căn cứ để gọi NORMAL). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = không quan sát thấy theo quy tắc; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Không có phenotype nổi bật theo quy tắc. Nhóm có operating envelope NORMAL độc lập cho nguồn này không? Nếu không, cửa sổ phải giữ UNLABELED.
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 16. `PILOT-e84b4d335a75` — hohai · `Berth_D_T6_Type_C` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_D_T6_Type_C/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-e84b4d335a75.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | -0.003 / 0.007 |
| A. Dao động | std quần thể = centered RMS (°) | 0.373 |
| A. Dao động | RMS gồm offset (°) | 0.373 |
| A. Dao động | peak-to-peak; min..max (°) | 2.199; -1.186..1.013 |
| B. Offset | dominant sign ratio; |mean|/std | 0.504; 0.01 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.009, -0.030, 0.011]; `-++---+++` |
| B. Offset | std mean block; mean shift (°) | 0.0188; 0.0023 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.310, 0.466, 0.323]; 1.044 |
| C. Tăng biên độ | RMS slope (°/phút); R² | 0.0069; 0.006 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.309, 0.465, 0.323]; 1.044 |
| C. Tăng biên độ | std 20 s (°) | [0.279, 0.322, 0.324, 0.554, 0.455, 0.366, 0.446, 0.216, 0.260] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | -2; 0.6193 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 193; 1.845; 0.153 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.837; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; -0.006; 0.341 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.068; 0.067→0.048 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 2.62e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Không thấy độ lệch có dấu bền vững: mean -0.003°, mẫu dấu sub-block `-++---+++`, sign ratio 0.504.
- Không thấy tăng biên độ bền vững: std block 60 s [0.309, 0.465, 0.323]°, Mann–Kendall p=0.6193.
- Dao động Roll quanh trung bình: std 0.373°, peak-to-peak 2.199°; std 60 s cuối ở hạng phần trăm 44 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 1.85 s (zero-crossing) khớp đỉnh phổ 1.84 s; CV chu kỳ 0.15.

**4. Bằng chứng hỗ trợ.**

- Không có bằng chứng ủng hộ phenotype nào theo quy tắc quan sát; các chỉ số mô tả được liệt kê ở trên.

**5. Bằng chứng mâu thuẫn.**

- Không ghi nhận mâu thuẫn nội tại; giới hạn chính nằm ở phần độ không chắc chắn.

**6. Nhãn hoặc trạng thái đề xuất.** `UNLABELED` — UNLABELED (không có dấu hiệu phenotype theo quy tắc, nhưng không đủ căn cứ để gọi NORMAL). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = không quan sát thấy theo quy tắc; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Không có phenotype nổi bật theo quy tắc. Nhóm có operating envelope NORMAL độc lập cho nguồn này không? Nếu không, cửa sổ phải giữ UNLABELED.
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 17. `PILOT-fb456420a73f` — hohai · `Berth_D_T7_Type_A` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_D_T7_Type_A/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-fb456420a73f.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.095 / 0.091 |
| A. Dao động | std quần thể = centered RMS (°) | 0.506 |
| A. Dao động | RMS gồm offset (°) | 0.515 |
| A. Dao động | peak-to-peak; min..max (°) | 3.455; -1.641..1.814 |
| B. Offset | dominant sign ratio; |mean|/std | 0.579; 0.19 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.108, 0.084, 0.094]; `+++++++++` |
| B. Offset | std mean block; mean shift (°) | 0.0095; -0.0131 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.431, 0.498, 0.601]; 1.392 |
| C. Tăng biên độ | RMS slope (°/phút); R² | 0.0846; 0.986 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.418, 0.491, 0.593]; 1.420 |
| C. Tăng biên độ | std 20 s (°) | [0.468, 0.357, 0.421, 0.536, 0.545, 0.371, 0.290, 0.514, 0.840] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | +8; 0.2384 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 199; 1.795; 0.112 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.782; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; 0.098; 0.453 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.115; 0.112→0.109 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 3.15e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Độ lệch có dấu nhỏ: mean 0.095°, 9/9 sub-block 20 s cùng dấu nhưng dao động vẫn cắt mốc 0 (sign ratio 0.579, |mean|/std 0.19).
- Có dấu hiệu tăng biên độ nhưng chưa nhất quán: block 60 s [0.418, 0.491, 0.593]°, Mann–Kendall p=0.2384 (không đạt α hiệu chỉnh 0.0017).
- Dao động Roll quanh trung bình: std 0.506°, peak-to-peak 3.455°; std 60 s cuối ở hạng phần trăm 98 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 1.80 s (zero-crossing) khớp đỉnh phổ 1.78 s; CV chu kỳ 0.11.

**4. Bằng chứng hỗ trợ.**

- Mean các block 60 s [0.108, 0.084, 0.094]° (độ lệch chuẩn giữa block 0.0095°, mean shift -0.0131°).
- Bối cảnh 180 s trước cửa sổ (coverage 100%) có mean 0.098°, sign ratio 0.601; trung bình Roll từ đầu segment đến endpoint (410 s) là 0.095°.
- Std 20 s (cũ→mới): [0.468, 0.357, 0.421, 0.536, 0.545, 0.371, 0.290, 0.514, 0.840]°; Mann–Kendall S=+8.
- Feature gốc: roll_rms_ratio_180 1.392, roll_rms_slope_180 0.0846°/phút, roll_rms_trend_r2_180 0.986; std quanh trung bình: tỷ lệ 1.420, slope 0.0877°/phút, R² 0.991.
- Std ba block 60 s tăng đơn điệu [0.418, 0.491, 0.593]°.
- Std 20 s mới nhất (0.840°) là cực đại của toàn bộ lịch sử quan sát (cửa sổ + bối cảnh); không có dữ liệu sau endpoint để biết nó kéo dài hay chỉ là đỉnh nhóm sóng.

**5. Bằng chứng mâu thuẫn.**

- Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực (list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.
- Dao động cắt qua mốc 0 (42.1% mẫu mang dấu ngược) và |mean|/std chỉ 0.19; tiêu chí 9/9 sub-block cùng dấu là bằng chứng thống kê, không phải bằng chứng độ lệch có ý nghĩa vật lý.
- Std block 60 s cuối 0.593° không vượt std 20 s lớn nhất trong bối cảnh trước cửa sổ (0.796°).
- Mann–Kendall p=0.2384 không vượt hiệu chỉnh đa kiểm định (α=0.05/29=0.0017); với 29 kiểm định ở α=0.05, kỳ vọng khoảng 1.45 kết quả dương tính giả.
- Biên độ các nửa chu kỳ liên tiếp tương quan mạnh (lag-1 = 0.85), có thể do nhóm sóng hoặc do chính xu hướng; các sub-block không độc lập nên p-value của Mann–Kendall có xu hướng lạc quan.

**6. Nhãn hoặc trạng thái đề xuất.** `REVIEW_REQUIRED` — REVIEW_REQUIRED (có dấu hiệu nhưng chưa đủ căn cứ hoặc nhiều phenotype chồng lấn). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = dấu hiệu yếu/chưa kết luận; AMPLITUDE_GROWTH = dấu hiệu yếu/chưa kết luận; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Độ lệch 0.095° có vượt sai số zero của cảm biến/khung thử không, và nhóm có định nghĩa biên độ tối thiểu cho PERSISTENT_OFFSET không?
- Sự tăng biên độ này có trùng với một pha thí nghiệm/khởi phát sóng hoặc sự kiện vận hành được ghi nhận không? Nhóm có chấp nhận tiêu chí tăng biên độ dựa trên kiểm định xu hướng và vượt lịch sử không?
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?
- Nhiều phenotype cùng xuất hiện: nhóm muốn giữ đồng thời các cờ hay chọn lớp chính theo quy ước nào?

### 18. `PILOT-ef69299acddb` — hohai · `Berth_D_T8_Type_A` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_D_T8_Type_A/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-ef69299acddb.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.015 / 0.011 |
| A. Dao động | std quần thể = centered RMS (°) | 0.370 |
| A. Dao động | RMS gồm offset (°) | 0.370 |
| A. Dao động | peak-to-peak; min..max (°) | 1.960; -0.978..0.982 |
| B. Offset | dominant sign ratio; |mean|/std | 0.511; 0.04 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [-0.003, 0.016, 0.032]; `-++++-+++` |
| B. Offset | std mean block; mean shift (°) | 0.0140; 0.0343 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.368, 0.347, 0.394]; 1.071 |
| C. Tăng biên độ | RMS slope (°/phút); R² | 0.0131; 0.307 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.368, 0.347, 0.393]; 1.068 |
| C. Tăng biên độ | std 20 s (°) | [0.253, 0.279, 0.512, 0.338, 0.390, 0.303, 0.416, 0.460, 0.282] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | +10; 0.1792 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 201; 1.767; 0.186 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.731; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; 0.020; 0.412 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.115; 0.111→0.123 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 1.92e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Không thấy độ lệch có dấu bền vững: mean 0.015°, mẫu dấu sub-block `-++++-+++`, sign ratio 0.511.
- Không thấy tăng biên độ bền vững: std block 60 s [0.368, 0.347, 0.393]°, Mann–Kendall p=0.1792.
- Dao động Roll quanh trung bình: std 0.370°, peak-to-peak 1.960°; std 60 s cuối ở hạng phần trăm 69 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 1.77 s (zero-crossing) khớp đỉnh phổ 1.73 s; CV chu kỳ 0.19.

**4. Bằng chứng hỗ trợ.**

- Không có bằng chứng ủng hộ phenotype nào theo quy tắc quan sát; các chỉ số mô tả được liệt kê ở trên.

**5. Bằng chứng mâu thuẫn.**

- Không ghi nhận mâu thuẫn nội tại; giới hạn chính nằm ở phần độ không chắc chắn.

**6. Nhãn hoặc trạng thái đề xuất.** `UNLABELED` — UNLABELED (không có dấu hiệu phenotype theo quy tắc, nhưng không đủ căn cứ để gọi NORMAL). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = không quan sát thấy theo quy tắc; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Không có phenotype nổi bật theo quy tắc. Nhóm có operating envelope NORMAL độc lập cho nguồn này không? Nếu không, cửa sổ phải giữ UNLABELED.
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 19. `PILOT-d9f72dfb21ea` — hohai · `Berth_D_T8_Type_B` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_D_T8_Type_B/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-d9f72dfb21ea.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.019 / 0.028 |
| A. Dao động | std quần thể = centered RMS (°) | 0.429 |
| A. Dao động | RMS gồm offset (°) | 0.429 |
| A. Dao động | peak-to-peak; min..max (°) | 2.524; -1.251..1.273 |
| B. Offset | dominant sign ratio; |mean|/std | 0.527; 0.04 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.040, 0.003, 0.014]; `++++-++++` |
| B. Offset | std mean block; mean shift (°) | 0.0153; -0.0252 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.449, 0.432, 0.404]; 0.900 |
| C. Tăng biên độ | RMS slope (°/phút); R² | -0.0225; 0.982 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.448, 0.432, 0.404]; 0.903 |
| C. Tăng biên độ | std 20 s (°) | [0.274, 0.434, 0.580, 0.440, 0.388, 0.464, 0.326, 0.458, 0.417] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | +2; 0.4597 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 190; 1.857; 0.235 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.800; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; 0.029; 0.448 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.104; 0.113→0.096 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 4.72e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Không thấy độ lệch có dấu bền vững: mean 0.019°, mẫu dấu sub-block `++++-++++`, sign ratio 0.527.
- Không thấy tăng biên độ bền vững: std block 60 s [0.448, 0.432, 0.404]°, Mann–Kendall p=0.4597.
- Dao động Roll quanh trung bình: std 0.429°, peak-to-peak 2.524°; std 60 s cuối ở hạng phần trăm 73 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 1.86 s (zero-crossing) khớp đỉnh phổ 1.80 s; CV chu kỳ 0.24.

**4. Bằng chứng hỗ trợ.**

- Không có bằng chứng ủng hộ phenotype nào theo quy tắc quan sát; các chỉ số mô tả được liệt kê ở trên.

**5. Bằng chứng mâu thuẫn.**

- Không ghi nhận mâu thuẫn nội tại; giới hạn chính nằm ở phần độ không chắc chắn.

**6. Nhãn hoặc trạng thái đề xuất.** `UNLABELED` — UNLABELED (không có dấu hiệu phenotype theo quy tắc, nhưng không đủ căn cứ để gọi NORMAL). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = không quan sát thấy theo quy tắc; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Không có phenotype nổi bật theo quy tắc. Nhóm có operating envelope NORMAL độc lập cho nguồn này không? Nếu không, cửa sổ phải giữ UNLABELED.
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 20. `PILOT-340669505244` — hohai · `Berth_D_T8_Type_C` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_D_T8_Type_C/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-340669505244.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.048 / 0.058 |
| A. Dao động | std quần thể = centered RMS (°) | 0.453 |
| A. Dao động | RMS gồm offset (°) | 0.455 |
| A. Dao động | peak-to-peak; min..max (°) | 2.475; -1.194..1.281 |
| B. Offset | dominant sign ratio; |mean|/std | 0.546; 0.11 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.037, 0.048, 0.058]; `+++++++++` |
| B. Offset | std mean block; mean shift (°) | 0.0088; 0.0216 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.419, 0.544, 0.388]; 0.925 |
| C. Tăng biên độ | RMS slope (°/phút); R² | -0.0157; 0.036 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.418, 0.542, 0.383]; 0.918 |
| C. Tăng biên độ | std 20 s (°) | [0.385, 0.350, 0.500, 0.433, 0.573, 0.604, 0.315, 0.312, 0.494] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | +0; 0.5403 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 192; 1.855; 0.156 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.875; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; 0.068; 0.443 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.105; 0.118→0.094 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 4.27e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Độ lệch có dấu nhỏ: mean 0.048°, 9/9 sub-block 20 s cùng dấu nhưng dao động vẫn cắt mốc 0 (sign ratio 0.546, |mean|/std 0.11).
- Không thấy tăng biên độ bền vững: std block 60 s [0.418, 0.542, 0.383]°, Mann–Kendall p=0.5403.
- Dao động Roll quanh trung bình: std 0.453°, peak-to-peak 2.475°; std 60 s cuối ở hạng phần trăm 66 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 1.86 s (zero-crossing) khớp đỉnh phổ 1.88 s; CV chu kỳ 0.16.

**4. Bằng chứng hỗ trợ.**

- Mean các block 60 s [0.037, 0.048, 0.058]° (độ lệch chuẩn giữa block 0.0088°, mean shift 0.0216°).
- Bối cảnh 180 s trước cửa sổ (coverage 100%) có mean 0.068°, sign ratio 0.567; trung bình Roll từ đầu segment đến endpoint (410 s) là 0.062°.

**5. Bằng chứng mâu thuẫn.**

- Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực (list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.
- Dao động cắt qua mốc 0 (45.4% mẫu mang dấu ngược) và |mean|/std chỉ 0.11; tiêu chí 9/9 sub-block cùng dấu là bằng chứng thống kê, không phải bằng chứng độ lệch có ý nghĩa vật lý.

**6. Nhãn hoặc trạng thái đề xuất.** `REVIEW_REQUIRED` — REVIEW_REQUIRED (có dấu hiệu nhưng chưa đủ căn cứ hoặc nhiều phenotype chồng lấn). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = dấu hiệu yếu/chưa kết luận; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Độ lệch 0.048° có vượt sai số zero của cảm biến/khung thử không, và nhóm có định nghĩa biên độ tối thiểu cho PERSISTENT_OFFSET không?
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 21. `PILOT-9299db975778` — hohai · `Berth_D_T9_Type_A` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (232.0, 412.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 899.9 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/hohai/Berth_D_T9_Type_A/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/hohai/PILOT-9299db975778.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | -0.049 / -0.060 |
| A. Dao động | std quần thể = centered RMS (°) | 0.472 |
| A. Dao động | RMS gồm offset (°) | 0.475 |
| A. Dao động | peak-to-peak; min..max (°) | 3.131; -1.463..1.668 |
| B. Offset | dominant sign ratio; |mean|/std | 0.556; 0.10 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [-0.007, -0.055, -0.085]; `++-------` |
| B. Offset | std mean block; mean shift (°) | 0.0320; -0.0776 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.532, 0.481, 0.403]; 0.758 |
| C. Tăng biên độ | RMS slope (°/phút); R² | -0.0644; 0.985 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.532, 0.478, 0.394]; 0.741 |
| C. Tăng biên độ | std 20 s (°) | [0.487, 0.653, 0.419, 0.399, 0.445, 0.570, 0.560, 0.312, 0.230] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | -14; 0.9403 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 198; 1.799; 0.168 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 1.875; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; -0.014; 0.429 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.114; 0.128→0.089 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 4.30e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Không thấy độ lệch có dấu bền vững: mean -0.049°, mẫu dấu sub-block `++-------`, sign ratio 0.556.
- Không thấy tăng biên độ bền vững: std block 60 s [0.532, 0.478, 0.394]°, Mann–Kendall p=0.9403.
- Dao động Roll quanh trung bình: std 0.472°, peak-to-peak 3.131°; std 60 s cuối ở hạng phần trăm 70 trong 1512 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 1.80 s (zero-crossing) khớp đỉnh phổ 1.88 s; CV chu kỳ 0.17.

**4. Bằng chứng hỗ trợ.**

- Không có bằng chứng ủng hộ phenotype nào theo quy tắc quan sát; các chỉ số mô tả được liệt kê ở trên.

**5. Bằng chứng mâu thuẫn.**

- Mean 20 s đổi dấu đúng một lần (mẫu `++-------`, mean shift -0.0776°): đây là trôi trung bình qua mốc 0, không phải lệch ổn định về dấu.

**6. Nhãn hoặc trạng thái đề xuất.** `UNLABELED` — UNLABELED (không có dấu hiệu phenotype theo quy tắc, nhưng không đủ căn cứ để gọi NORMAL). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = không quan sát thấy theo quy tắc; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Hohai là dữ liệu mô hình thí nghiệm (model-scale); thời gian suy từ chỉ số mẫu ở 50 Hz nên không phát hiện được dropout; không có gyro đo trực tiếp; Roll/Pitch đã lọc Butterworth nhân quả bậc 4, cắt 4 Hz rồi lấy mẫu 10 Hz; quy ước lắp đặt cảm biến chưa rõ nên mốc 0 của Roll chưa được xác nhận.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Không có phenotype nổi bật theo quy tắc. Nhóm có operating envelope NORMAL độc lập cho nguồn này không? Nếu không, cửa sổ phải giữ UNLABELED.
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

## 6.2. Nguồn `seafar`

Seafar là tàu thật nhưng chỉ có một session; timestamp epoch ms, khoảng 10 Hz gốc, không áp bộ lọc; Roll lượng tử hóa theo bước 0.01°; trường rate chưa xác minh trục/dấu nên gyro không được dùng; session bị tách segment do gap/duplicate; độ tin cậy trục/dấu được provenance ghi là thấp.

### 22. `PILOT-5e1196364be9` — seafar · `seafar_session_001` · `segment_001`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (1.0, 181.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 1.0 đến 2638.5 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/seafar/seafar_session_001/segment_001/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/seafar/PILOT-5e1196364be9.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 3.106 / 3.120 |
| A. Dao động | std quần thể = centered RMS (°) | 0.065 |
| A. Dao động | RMS gồm offset (°) | 3.106 |
| A. Dao động | peak-to-peak; min..max (°) | 0.380; 2.850..3.230 |
| B. Offset | dominant sign ratio; |mean|/std | 1.000; 47.76 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [3.086, 3.129, 3.103]; `+++++++++` |
| B. Offset | std mean block; mean shift (°) | 0.0177; 0.0176 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [3.087, 3.129, 3.104]; 1.005 |
| C. Tăng biên độ | RMS slope (°/phút); R² | 0.0084; 0.155 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.085, 0.049, 0.047]; 0.551 |
| C. Tăng biên độ | std 20 s (°) | [0.098, 0.032, 0.066, 0.050, 0.049, 0.046, 0.044, 0.051, 0.029] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | -16; 0.9624 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 58; 4.090; 0.612 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 4.091; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1; 0%; 2.970; không xác định |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.018; 0.020→0.014 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 4.79e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Roll lệch dương ổn định: mean 3.106°, median 3.120°, 100% mẫu cùng dấu (tín hiệu không cắt mốc 0 trong 180 s), 9/9 sub-block 20 s cùng dấu.
- Không thấy tăng biên độ bền vững: std block 60 s [0.085, 0.049, 0.047]°, Mann–Kendall p=0.9624.
- Dao động Roll quanh trung bình: std 0.065°, peak-to-peak 0.380°; std 60 s cuối ở hạng phần trăm 22 trong 1318 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 4.09 s (zero-crossing) khớp đỉnh phổ 4.09 s; CV chu kỳ 0.61.

**4. Bằng chứng hỗ trợ.**

- Mean các block 60 s [3.086, 3.129, 3.103]° (độ lệch chuẩn giữa block 0.0177°, mean shift 0.0176°).

**5. Bằng chứng mâu thuẫn.**

- Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực (list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.

**6. Nhãn hoặc trạng thái đề xuất.** `PERSISTENT_OFFSET` — PERSISTENT_OFFSET (phenotype tín hiệu đo, AI gợi ý, cần người xác nhận). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = quan sát thấy, nhất quán; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- Roll lượng tử hóa 0.01°; chỉ 39 giá trị khác nhau trong cửa sổ, std 0.065° ≈ 6.5 bước lượng tử, nên zero-crossing và chu kỳ bị nhiễu lượng tử chi phối.
- Cửa sổ bắt đầu ngay đầu segment: không có lịch sử trước cửa sổ, thời lượng quan sát chỉ 180 s.
- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Seafar là tàu thật nhưng chỉ có một session; timestamp epoch ms, khoảng 10 Hz gốc, không áp bộ lọc; Roll lượng tử hóa theo bước 0.01°; trường rate chưa xác minh trục/dấu nên gyro không được dùng; session bị tách segment do gap/duplicate; độ tin cậy trục/dấu được provenance ghi là thấp.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Mốc 0 của Roll ở nguồn seafar đã được hiệu chuẩn chưa? Độ lệch 3.106° là nghiêng thực của tàu/mô hình hay sai lệch lắp đặt?
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 23. `PILOT-03a267c60f6b` — seafar · `seafar_session_001` · `segment_002`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (4568.8, 4748.8] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2638.8 đến 8630.8 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/seafar/seafar_session_001/segment_002/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/seafar/PILOT-03a267c60f6b.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 3.212 / 3.200 |
| A. Dao động | std quần thể = centered RMS (°) | 0.097 |
| A. Dao động | RMS gồm offset (°) | 3.214 |
| A. Dao động | peak-to-peak; min..max (°) | 0.470; 2.990..3.460 |
| B. Offset | dominant sign ratio; |mean|/std | 1.000; 33.12 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [3.200, 3.171, 3.266]; `+++++++++` |
| B. Offset | std mean block; mean shift (°) | 0.0399; 0.0664 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [3.201, 3.172, 3.268]; 1.021 |
| C. Tăng biên độ | RMS slope (°/phút); R² | 0.0332; 0.457 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.096, 0.073, 0.095]; 0.991 |
| C. Tăng biên độ | std 20 s (°) | [0.079, 0.108, 0.076, 0.072, 0.041, 0.091, 0.073, 0.085, 0.055] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | -10; 0.8702 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 55; 4.200; 0.731 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 180.000; ZC_AND_SPECTRUM_DISAGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; 3.216; 0.072 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.031; 0.047→0.016 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 1.37e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Roll lệch dương ổn định: mean 3.212°, median 3.200°, 100% mẫu cùng dấu (tín hiệu không cắt mốc 0 trong 180 s), 9/9 sub-block 20 s cùng dấu.
- Không thấy tăng biên độ bền vững: std block 60 s [0.096, 0.073, 0.095]°, Mann–Kendall p=0.8702.
- Dao động Roll quanh trung bình: std 0.097°, peak-to-peak 0.470°; std 60 s cuối ở hạng phần trăm 50 trong 1318 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ chưa tin cậy: zero-crossing 4.20 s, đỉnh phổ 180.00 s (nằm ngoài IQR chu kỳ zero-crossing), CV 0.73.

**4. Bằng chứng hỗ trợ.**

- Mean các block 60 s [3.200, 3.171, 3.266]° (độ lệch chuẩn giữa block 0.0399°, mean shift 0.0664°).
- Bối cảnh 180 s trước cửa sổ (coverage 100%) có mean 3.216°, sign ratio 1.000; trung bình Roll từ đầu segment đến endpoint (2110 s) là 3.172°.

**5. Bằng chứng mâu thuẫn.**

- Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực (list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.

**6. Nhãn hoặc trạng thái đề xuất.** `PERSISTENT_OFFSET` — PERSISTENT_OFFSET (phenotype tín hiệu đo, AI gợi ý, cần người xác nhận). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = quan sát thấy, nhất quán; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- Ước lượng chu kỳ không ổn định (CV 0.73; đỉnh phổ 180.0 s, độ phân giải phổ 0.0056 Hz), nên không dùng chu kỳ làm bằng chứng phân lớp.
- Roll lượng tử hóa 0.01°; chỉ 48 giá trị khác nhau trong cửa sổ, std 0.097° ≈ 9.7 bước lượng tử, nên zero-crossing và chu kỳ bị nhiễu lượng tử chi phối.
- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Seafar là tàu thật nhưng chỉ có một session; timestamp epoch ms, khoảng 10 Hz gốc, không áp bộ lọc; Roll lượng tử hóa theo bước 0.01°; trường rate chưa xác minh trục/dấu nên gyro không được dùng; session bị tách segment do gap/duplicate; độ tin cậy trục/dấu được provenance ghi là thấp.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Mốc 0 của Roll ở nguồn seafar đã được hiệu chuẩn chưa? Độ lệch 3.212° là nghiêng thực của tàu/mô hình hay sai lệch lắp đặt?
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 24. `PILOT-7ae54dba45e4` — seafar · `seafar_session_001` · `segment_031`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (9762.0, 9942.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 9512.0 đến 14332.5 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/seafar/seafar_session_001/segment_031/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/seafar/PILOT-7ae54dba45e4.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 3.515 / 3.480 |
| A. Dao động | std quần thể = centered RMS (°) | 0.239 |
| A. Dao động | RMS gồm offset (°) | 3.523 |
| A. Dao động | peak-to-peak; min..max (°) | 1.100; 3.100..4.200 |
| B. Offset | dominant sign ratio; |mean|/std | 1.000; 14.72 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [3.442, 3.638, 3.465]; `+++++++++` |
| B. Offset | std mean block; mean shift (°) | 0.0876; 0.0227 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [3.446, 3.648, 3.472]; 1.008 |
| C. Tăng biên độ | RMS slope (°/phút); R² | 0.0129; 0.014 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.164, 0.268, 0.221]; 1.348 |
| C. Tăng biên độ | std 20 s (°) | [0.123, 0.169, 0.080, 0.113, 0.206, 0.127, 0.088, 0.164, 0.167] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | +6; 0.3061 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 23; 4.571; 1.491 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 90.000; ZC_AND_SPECTRUM_DISAGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; 3.479; 0.241 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.048; 0.035→0.020 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 2.06e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Roll lệch dương ổn định: mean 3.515°, median 3.480°, 100% mẫu cùng dấu (tín hiệu không cắt mốc 0 trong 180 s), 9/9 sub-block 20 s cùng dấu.
- Không thấy tăng biên độ bền vững: std block 60 s [0.164, 0.268, 0.221]°, Mann–Kendall p=0.3061.
- Dao động Roll quanh trung bình: std 0.239°, peak-to-peak 1.100°; std 60 s cuối ở hạng phần trăm 89 trong 1318 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ chưa tin cậy: zero-crossing 4.57 s, đỉnh phổ 90.00 s (nằm ngoài IQR chu kỳ zero-crossing), CV 1.49.

**4. Bằng chứng hỗ trợ.**

- Mean các block 60 s [3.442, 3.638, 3.465]° (độ lệch chuẩn giữa block 0.0876°, mean shift 0.0227°).
- Bối cảnh 180 s trước cửa sổ (coverage 100%) có mean 3.479°, sign ratio 1.000; trung bình Roll từ đầu segment đến endpoint (430 s) là 3.492°.

**5. Bằng chứng mâu thuẫn.**

- Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực (list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.

**6. Nhãn hoặc trạng thái đề xuất.** `PERSISTENT_OFFSET` — PERSISTENT_OFFSET (phenotype tín hiệu đo, AI gợi ý, cần người xác nhận). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = quan sát thấy, nhất quán; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- Ước lượng chu kỳ không ổn định (CV 1.49; đỉnh phổ 90.0 s, độ phân giải phổ 0.0056 Hz), nên không dùng chu kỳ làm bằng chứng phân lớp.
- Roll lượng tử hóa 0.01°; chỉ 111 giá trị khác nhau trong cửa sổ, std 0.239° ≈ 23.9 bước lượng tử, nên zero-crossing và chu kỳ bị nhiễu lượng tử chi phối.
- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Seafar là tàu thật nhưng chỉ có một session; timestamp epoch ms, khoảng 10 Hz gốc, không áp bộ lọc; Roll lượng tử hóa theo bước 0.01°; trường rate chưa xác minh trục/dấu nên gyro không được dùng; session bị tách segment do gap/duplicate; độ tin cậy trục/dấu được provenance ghi là thấp.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Mốc 0 của Roll ở nguồn seafar đã được hiệu chuẩn chưa? Độ lệch 3.515° là nghiêng thực của tàu/mô hình hay sai lệch lắp đặt?
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 25. `PILOT-9115297d34b5` — seafar · `seafar_session_001` · `segment_031`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (14152.0, 14332.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 9512.0 đến 14332.5 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/seafar/seafar_session_001/segment_031/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/seafar/PILOT-9115297d34b5.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 3.452 / 3.450 |
| A. Dao động | std quần thể = centered RMS (°) | 0.031 |
| A. Dao động | RMS gồm offset (°) | 3.453 |
| A. Dao động | peak-to-peak; min..max (°) | 0.140; 3.390..3.530 |
| B. Offset | dominant sign ratio; |mean|/std | 1.000; 110.84 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [3.456, 3.452, 3.450]; `+++++++++` |
| B. Offset | std mean block; mean shift (°) | 0.0024; -0.0058 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [3.456, 3.452, 3.450]; 0.998 |
| C. Tăng biên độ | RMS slope (°/phút); R² | -0.0029; 0.973 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.031, 0.024, 0.037]; 1.190 |
| C. Tăng biên độ | std 20 s (°) | [0.018, 0.027, 0.034, 0.019, 0.016, 0.015, 0.011, 0.011, 0.025] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | -14; 0.9403 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 25; 11.550; 0.662 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 180.000; ZC_AND_SPECTRUM_DISAGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; 3.462; 0.022 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.013; 0.010→0.012 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 1.88e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Roll lệch dương ổn định: mean 3.452°, median 3.450°, 100% mẫu cùng dấu (tín hiệu không cắt mốc 0 trong 180 s), 9/9 sub-block 20 s cùng dấu.
- Không thấy tăng biên độ bền vững: std block 60 s [0.031, 0.024, 0.037]°, Mann–Kendall p=0.9403.
- Dao động Roll quanh trung bình: std 0.031°, peak-to-peak 0.140°; std 60 s cuối ở hạng phần trăm 15 trong 1318 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ chưa tin cậy: zero-crossing 11.55 s, đỉnh phổ 180.00 s (nằm ngoài IQR chu kỳ zero-crossing), CV 0.66.

**4. Bằng chứng hỗ trợ.**

- Mean các block 60 s [3.456, 3.452, 3.450]° (độ lệch chuẩn giữa block 0.0024°, mean shift -0.0058°).
- Bối cảnh 180 s trước cửa sổ (coverage 100%) có mean 3.462°, sign ratio 1.000; trung bình Roll từ đầu segment đến endpoint (4820 s) là 3.480°.

**5. Bằng chứng mâu thuẫn.**

- Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực (list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.

**6. Nhãn hoặc trạng thái đề xuất.** `PERSISTENT_OFFSET` — PERSISTENT_OFFSET (phenotype tín hiệu đo, AI gợi ý, cần người xác nhận). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = quan sát thấy, nhất quán; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- Ước lượng chu kỳ không ổn định (CV 0.66; đỉnh phổ 180.0 s, độ phân giải phổ 0.0056 Hz), nên không dùng chu kỳ làm bằng chứng phân lớp.
- Roll lượng tử hóa 0.01°; chỉ 15 giá trị khác nhau trong cửa sổ, std 0.031° ≈ 3.1 bước lượng tử, nên zero-crossing và chu kỳ bị nhiễu lượng tử chi phối.
- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Seafar là tàu thật nhưng chỉ có một session; timestamp epoch ms, khoảng 10 Hz gốc, không áp bộ lọc; Roll lượng tử hóa theo bước 0.01°; trường rate chưa xác minh trục/dấu nên gyro không được dùng; session bị tách segment do gap/duplicate; độ tin cậy trục/dấu được provenance ghi là thấp.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Mốc 0 của Roll ở nguồn seafar đã được hiệu chuẩn chưa? Độ lệch 3.452° là nghiêng thực của tàu/mô hình hay sai lệch lắp đặt?
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

## 6.3. Nguồn `southampton`

Southampton là mô hình KCS trong bể thử (model-scale), chỉ Run 14 đủ 180 giây; timestamp lấy từ CSV; Roll/Pitch lọc Butterworth nhân quả 4 Hz, 50→10 Hz; Delta Angle chưa map sang gyro; bốn cửa sổ pilot cùng một run nên không phải quan sát độc lập.

### 26. `PILOT-47dcb093bf41` — southampton · `southampton_run_14` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (2.0, 182.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 513.6 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/southampton/southampton_run_14/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/southampton/PILOT-47dcb093bf41.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.698 / 0.705 |
| A. Dao động | std quần thể = centered RMS (°) | 0.053 |
| A. Dao động | RMS gồm offset (°) | 0.700 |
| A. Dao động | peak-to-peak; min..max (°) | 0.238; 0.592..0.830 |
| B. Offset | dominant sign ratio; |mean|/std | 1.000; 13.15 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.723, 0.665, 0.705]; `+++++++++` |
| B. Offset | std mean block; mean shift (°) | 0.0241; -0.0174 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.725, 0.667, 0.706]; 0.973 |
| C. Tăng biên độ | RMS slope (°/phút); R² | -0.0096; 0.105 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.060, 0.047, 0.030]; 0.504 |
| C. Tăng biên độ | std 20 s (°) | [0.021, 0.020, 0.026, 0.013, 0.032, 0.014, 0.009, 0.016, 0.010] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | -14; 0.9403 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 41; 1.335; 2.228 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 180.000; ZC_AND_SPECTRUM_DISAGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1; 0%; 0.794; không xác định |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.020; 0.020→0.016 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 4.37e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Roll lệch dương ổn định: mean 0.698°, median 0.705°, 100% mẫu cùng dấu (tín hiệu không cắt mốc 0 trong 180 s), 9/9 sub-block 20 s cùng dấu.
- Không thấy tăng biên độ bền vững: std block 60 s [0.060, 0.047, 0.030]°, Mann–Kendall p=0.9403.
- Dao động Roll quanh trung bình: std 0.053°, peak-to-peak 0.238°; std 60 s cuối ở hạng phần trăm 79 trong 34 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ chưa tin cậy: zero-crossing 1.34 s, đỉnh phổ 180.00 s (nằm ngoài IQR chu kỳ zero-crossing), CV 2.23.

**4. Bằng chứng hỗ trợ.**

- Mean các block 60 s [0.723, 0.665, 0.705]° (độ lệch chuẩn giữa block 0.0241°, mean shift -0.0174°).

**5. Bằng chứng mâu thuẫn.**

- Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực (list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.

**6. Nhãn hoặc trạng thái đề xuất.** `PERSISTENT_OFFSET` — PERSISTENT_OFFSET (phenotype tín hiệu đo, AI gợi ý, cần người xác nhận). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = quan sát thấy, nhất quán; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- Ước lượng chu kỳ không ổn định (CV 2.23; đỉnh phổ 180.0 s, độ phân giải phổ 0.0056 Hz), nên không dùng chu kỳ làm bằng chứng phân lớp.
- Cửa sổ bắt đầu ngay đầu segment: không có lịch sử trước cửa sổ, thời lượng quan sát chỉ 180 s.
- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Southampton là mô hình KCS trong bể thử (model-scale), chỉ Run 14 đủ 180 giây; timestamp lấy từ CSV; Roll/Pitch lọc Butterworth nhân quả 4 Hz, 50→10 Hz; Delta Angle chưa map sang gyro; bốn cửa sổ pilot cùng một run nên không phải quan sát độc lập.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Mốc 0 của Roll ở nguồn southampton đã được hiệu chuẩn chưa? Độ lệch 0.698° là nghiêng thực của tàu/mô hình hay sai lệch lắp đặt?
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 27. `PILOT-e6e911efbddf` — southampton · `southampton_run_14` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (112.0, 292.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 513.6 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/southampton/southampton_run_14/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/southampton/PILOT-e6e911efbddf.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.695 / 0.691 |
| A. Dao động | std quần thể = centered RMS (°) | 0.024 |
| A. Dao động | RMS gồm offset (°) | 0.696 |
| A. Dao động | peak-to-peak; min..max (°) | 0.117; 0.642..0.758 |
| B. Offset | dominant sign ratio; |mean|/std | 1.000; 28.40 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.715, 0.676, 0.694]; `+++++++++` |
| B. Offset | std mean block; mean shift (°) | 0.0159; -0.0212 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.716, 0.676, 0.694]; 0.970 |
| C. Tăng biên độ | RMS slope (°/phút); R² | -0.0108; 0.298 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.027, 0.012, 0.013]; 0.480 |
| C. Tăng biên độ | std 20 s (°) | [0.011, 0.008, 0.020, 0.009, 0.012, 0.007, 0.015, 0.014, 0.008] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | -2; 0.6193 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 87; 1.248; 2.080 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 180.000; ZC_AND_SPECTRUM_DISAGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1101; 61%; 0.691; 0.063 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.021; 0.021→0.012 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 2.55e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Roll lệch dương ổn định: mean 0.695°, median 0.691°, 100% mẫu cùng dấu (tín hiệu không cắt mốc 0 trong 180 s), 9/9 sub-block 20 s cùng dấu.
- Không thấy tăng biên độ bền vững: std block 60 s [0.027, 0.012, 0.013]°, Mann–Kendall p=0.6193.
- Dao động Roll quanh trung bình: std 0.024°, peak-to-peak 0.117°; std 60 s cuối ở hạng phần trăm 12 trong 34 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ chưa tin cậy: zero-crossing 1.25 s, đỉnh phổ 180.00 s (nằm ngoài IQR chu kỳ zero-crossing), CV 2.08.

**4. Bằng chứng hỗ trợ.**

- Mean các block 60 s [0.715, 0.676, 0.694]° (độ lệch chuẩn giữa block 0.0159°, mean shift -0.0212°).
- Bối cảnh 180 s trước cửa sổ (coverage 61%) có mean 0.691°, sign ratio 1.000; trung bình Roll từ đầu segment đến endpoint (290 s) là 0.694°.

**5. Bằng chứng mâu thuẫn.**

- Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực (list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.

**6. Nhãn hoặc trạng thái đề xuất.** `PERSISTENT_OFFSET` — PERSISTENT_OFFSET (phenotype tín hiệu đo, AI gợi ý, cần người xác nhận). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = quan sát thấy, nhất quán; AMPLITUDE_GROWTH = không quan sát thấy theo quy tắc; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- Ước lượng chu kỳ không ổn định (CV 2.08; đỉnh phổ 180.0 s, độ phân giải phổ 0.0056 Hz), nên không dùng chu kỳ làm bằng chứng phân lớp.
- Bối cảnh trước cửa sổ chỉ phủ 61% của 180 s.
- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Southampton là mô hình KCS trong bể thử (model-scale), chỉ Run 14 đủ 180 giây; timestamp lấy từ CSV; Roll/Pitch lọc Butterworth nhân quả 4 Hz, 50→10 Hz; Delta Angle chưa map sang gyro; bốn cửa sổ pilot cùng một run nên không phải quan sát độc lập.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Mốc 0 của Roll ở nguồn southampton đã được hiệu chuẩn chưa? Độ lệch 0.695° là nghiêng thực của tàu/mô hình hay sai lệch lắp đặt?
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?

### 28. `PILOT-db0b97396fc9` — southampton · `southampton_run_14` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (222.0, 402.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 513.6 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/southampton/southampton_run_14/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/southampton/PILOT-db0b97396fc9.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.695 / 0.694 |
| A. Dao động | std quần thể = centered RMS (°) | 0.019 |
| A. Dao động | RMS gồm offset (°) | 0.695 |
| A. Dao động | peak-to-peak; min..max (°) | 0.132; 0.624..0.757 |
| B. Offset | dominant sign ratio; |mean|/std | 1.000; 36.95 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.689, 0.696, 0.699]; `+++++++++` |
| B. Offset | std mean block; mean shift (°) | 0.0043; 0.0102 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.689, 0.696, 0.699]; 1.015 |
| C. Tăng biên độ | RMS slope (°/phút); R² | 0.0052; 0.944 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.016, 0.017, 0.021]; 1.286 |
| C. Tăng biên độ | std 20 s (°) | [0.011, 0.011, 0.008, 0.015, 0.016, 0.013, 0.011, 0.016, 0.018] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | +18; 0.0376 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 145; 1.065; 1.488 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 60.000; ZC_AND_SPECTRUM_DISAGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; 0.681; 0.039 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.029; 0.012→0.014 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 3.38e-07 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Roll lệch dương ổn định: mean 0.695°, median 0.694°, 100% mẫu cùng dấu (tín hiệu không cắt mốc 0 trong 180 s), 9/9 sub-block 20 s cùng dấu.
- Có dấu hiệu tăng biên độ nhưng chưa nhất quán: block 60 s [0.016, 0.017, 0.021]°, Mann–Kendall p=0.0376 (không đạt α hiệu chỉnh 0.0017).
- Dao động Roll quanh trung bình: std 0.019°, peak-to-peak 0.132°; std 60 s cuối ở hạng phần trăm 65 trong 34 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ chưa tin cậy: zero-crossing 1.06 s, đỉnh phổ 60.00 s (nằm ngoài IQR chu kỳ zero-crossing), CV 1.49.

**4. Bằng chứng hỗ trợ.**

- Mean các block 60 s [0.689, 0.696, 0.699]° (độ lệch chuẩn giữa block 0.0043°, mean shift 0.0102°).
- Bối cảnh 180 s trước cửa sổ (coverage 100%) có mean 0.681°, sign ratio 1.000; trung bình Roll từ đầu segment đến endpoint (400 s) là 0.695°.
- Std 20 s (cũ→mới): [0.011, 0.011, 0.008, 0.015, 0.016, 0.013, 0.011, 0.016, 0.018]°; Mann–Kendall S=+18.
- Feature gốc: roll_rms_ratio_180 1.015, roll_rms_slope_180 0.0052°/phút, roll_rms_trend_r2_180 0.944; std quanh trung bình: tỷ lệ 1.286, slope 0.0023°/phút, R² 0.905.
- Std ba block 60 s tăng đơn điệu [0.016, 0.017, 0.021]°.

**5. Bằng chứng mâu thuẫn.**

- Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực (list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.
- Std block 60 s cuối 0.021° không vượt std 20 s lớn nhất trong bối cảnh trước cửa sổ (0.032°).
- Mann–Kendall p=0.0376 không vượt hiệu chỉnh đa kiểm định (α=0.05/29=0.0017); với 29 kiểm định ở α=0.05, kỳ vọng khoảng 1.45 kết quả dương tính giả.
- Pitch tăng đồng thời (std 60 s sớm 0.012° → muộn 0.014°), gợi ý thay đổi kích thích bên ngoài (sóng/pha thí nghiệm) chứ không riêng cơ chế Roll; tín hiệu không đủ để xác định nguyên nhân.

**6. Nhãn hoặc trạng thái đề xuất.** `REVIEW_REQUIRED` — REVIEW_REQUIRED (có dấu hiệu nhưng chưa đủ căn cứ hoặc nhiều phenotype chồng lấn). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = quan sát thấy, nhất quán; AMPLITUDE_GROWTH = dấu hiệu yếu/chưa kết luận; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- Ước lượng chu kỳ không ổn định (CV 1.49; đỉnh phổ 60.0 s, độ phân giải phổ 0.0056 Hz), nên không dùng chu kỳ làm bằng chứng phân lớp.
- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Southampton là mô hình KCS trong bể thử (model-scale), chỉ Run 14 đủ 180 giây; timestamp lấy từ CSV; Roll/Pitch lọc Butterworth nhân quả 4 Hz, 50→10 Hz; Delta Angle chưa map sang gyro; bốn cửa sổ pilot cùng một run nên không phải quan sát độc lập.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Mốc 0 của Roll ở nguồn southampton đã được hiệu chuẩn chưa? Độ lệch 0.695° là nghiêng thực của tàu/mô hình hay sai lệch lắp đặt?
- Sự tăng biên độ này có trùng với một pha thí nghiệm/khởi phát sóng hoặc sự kiện vận hành được ghi nhận không? Nhóm có chấp nhận tiêu chí tăng biên độ dựa trên kiểm định xu hướng và vượt lịch sử không?
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?
- Nhiều phenotype cùng xuất hiện: nhóm muốn giữ đồng thời các cờ hay chọn lớp chính theo quy ước nào?

### 29. `PILOT-c2643af463e2` — southampton · `southampton_run_14` · `segment_000`

**1. Dữ liệu và cửa sổ quan sát.** Cửa sổ (332.0, 512.0] s, 1800/1800 mẫu 10 Hz, khoảng cách mẫu 0.100–0.100 s; segment chạy từ 2.0 đến 513.6 s nên cửa sổ không vượt ranh giới segment. Bối cảnh lịch sử dùng tối đa 180 s trước cửa sổ, không dùng dữ liệu sau endpoint. Nguồn: `ml/data/processed/southampton/southampton_run_14/segment_000/timeseries.parquet`; hình: `ml/data/labels/annotation_pilot/figures/southampton/PILOT-c2643af463e2.png`.

**2. Các chỉ số quan trọng.**

| Nhóm | Chỉ số | Giá trị |
|---|---|---|
| A. Dao động | mean / median (°) | 0.705 / 0.704 |
| A. Dao động | std quần thể = centered RMS (°) | 0.074 |
| A. Dao động | RMS gồm offset (°) | 0.709 |
| A. Dao động | peak-to-peak; min..max (°) | 0.626; 0.420..1.046 |
| B. Offset | dominant sign ratio; |mean|/std | 1.000; 9.48 |
| B. Offset | mean block 60 s (°); dấu mean 20 s | [0.695, 0.709, 0.712]; `+++++++++` |
| B. Offset | std mean block; mean shift (°) | 0.0074; 0.0172 |
| C. Tăng biên độ | RMS block 60 s (°); ratio | [0.695, 0.710, 0.722]; 1.039 |
| C. Tăng biên độ | RMS slope (°/phút); R² | 0.0135; 0.999 |
| C. Tăng biên độ | std quanh mean block 60 s (°); ratio | [0.019, 0.041, 0.120]; 6.430 |
| C. Tăng biên độ | std 20 s (°) | [0.014, 0.011, 0.018, 0.015, 0.017, 0.061, 0.109, 0.120, 0.127] |
| C. Tăng biên độ | Mann–Kendall S; p một phía | +30; 0.0004 |
| D. Chu kỳ | zero-crossings; chu kỳ median (s); CV | 310; 0.704; 2.656 |
| D. Chu kỳ | đỉnh phổ (s); trạng thái | 0.695; ZC_AND_SPECTRUM_AGREE |
| Bối cảnh | mẫu; coverage; mean; std (°) | 1800; 100%; 0.687; 0.017 |
| Pitch | std 180 s; std 60 s sớm→muộn (°) | 0.106; 0.011→0.122 |
| Đối chiếu | sai lệch lớn nhất so với feature table | 7.26e-08 (26 feature) |

**3. Dấu hiệu chuyển động quan sát được.**

- Roll lệch dương ổn định: mean 0.705°, median 0.704°, 100% mẫu cùng dấu (tín hiệu không cắt mốc 0 trong 180 s), 9/9 sub-block 20 s cùng dấu.
- Biên độ dao động (std quanh trung bình) tăng nhất quán: block 60 s [0.019, 0.041, 0.120]° (tỷ lệ muộn/sớm 6.43), Mann–Kendall p=0.0004 < α hiệu chỉnh 0.0017.
- Dao động Roll quanh trung bình: std 0.074°, peak-to-peak 0.626°; std 60 s cuối ở hạng phần trăm 100 trong 34 cửa sổ hợp lệ cùng nguồn (chỉ mô tả, không phải ngưỡng HIGH_ROLL).
- Chu kỳ ước lượng 0.70 s (zero-crossing) khớp đỉnh phổ 0.69 s; CV chu kỳ 2.66. Tuy vậy CV > 1 (độ phân tán chu kỳ lớn hơn chính chu kỳ trung bình) nên chu kỳ chỉ đại diện cho phần dao động rõ trong cửa sổ, không ổn định trên toàn 180 s.

**4. Bằng chứng hỗ trợ.**

- Mean các block 60 s [0.695, 0.709, 0.712]° (độ lệch chuẩn giữa block 0.0074°, mean shift 0.0172°).
- Bối cảnh 180 s trước cửa sổ (coverage 100%) có mean 0.687°, sign ratio 1.000; trung bình Roll từ đầu segment đến endpoint (510 s) là 0.698°.
- Std 20 s (cũ→mới): [0.014, 0.011, 0.018, 0.015, 0.017, 0.061, 0.109, 0.120, 0.127]°; Mann–Kendall S=+30.
- Feature gốc: roll_rms_ratio_180 1.039, roll_rms_slope_180 0.0135°/phút, roll_rms_trend_r2_180 0.999; std quanh trung bình: tỷ lệ 6.430, slope 0.0506°/phút, R² 0.908.
- Std ba block 60 s tăng đơn điệu [0.019, 0.041, 0.120]°.
- Std 20 s mới nhất (0.127°) là cực đại của toàn bộ lịch sử quan sát (cửa sổ + bối cảnh); không có dữ liệu sau endpoint để biết nó kéo dài hay chỉ là đỉnh nhóm sóng.
- Khởi phát ước lượng tại khoảng 432 s (sub-block 6/9); mọi sub-block sau đó đều cao hơn mọi sub-block trước đó và bối cảnh.
- Std block 60 s cuối 0.120° lớn hơn std 20 s lớn nhất trong bối cảnh trước cửa sổ (0.020°).

**5. Bằng chứng mâu thuẫn.**

- Mốc 0 của Roll chưa được hiệu chuẩn/xác nhận (mounting datum), nên độ lệch đo được có thể là nghiêng thực (list/heel) hoặc sai lệch lắp đặt cảm biến; tín hiệu không phân biệt được hai khả năng này.
- Biên độ các nửa chu kỳ liên tiếp tương quan mạnh (lag-1 = 0.66), có thể do nhóm sóng hoặc do chính xu hướng; các sub-block không độc lập nên p-value của Mann–Kendall có xu hướng lạc quan.
- Pitch tăng đồng thời (std 60 s sớm 0.011° → muộn 0.122°), gợi ý thay đổi kích thích bên ngoài (sóng/pha thí nghiệm) chứ không riêng cơ chế Roll; tín hiệu không đủ để xác định nguyên nhân.
- Cửa sổ kết thúc sát cuối run/segment (segment chỉ còn 1.6 s sau endpoint), nên không thể kiểm tra tăng biên độ có duy trì hay là pha cuối thí nghiệm.
- Feature roll_rms_ratio_180 = 1.039 che mất tăng biên độ vì RMS bị offset chi phối (|mean|/std = 9.5); tỷ lệ std quanh trung bình là 6.43.

**6. Nhãn hoặc trạng thái đề xuất.** `REVIEW_REQUIRED` — REVIEW_REQUIRED (có dấu hiệu nhưng chưa đủ căn cứ hoặc nhiều phenotype chồng lấn). Cờ: HIGH_ROLL = không đánh giá được (chưa có operating envelope được xác thực); PERSISTENT_OFFSET = quan sát thấy, nhất quán; AMPLITUDE_GROWTH = quan sát thấy, nhất quán; NORMAL = không đánh giá được (chưa có operating envelope được xác thực). `requires_human_review = true`.

**7. Lý do chưa thể xác minh.**

- HIGH_ROLL và NORMAL không được đánh giá vì chưa có operating envelope/giới hạn vận hành được xác thực độc lập cho tàu hoặc mô hình này; biên độ nhỏ không đồng nghĩa NORMAL.
- Southampton là mô hình KCS trong bể thử (model-scale), chỉ Run 14 đủ 180 giây; timestamp lấy từ CSV; Roll/Pitch lọc Butterworth nhân quả 4 Hz, 50→10 Hz; Delta Angle chưa map sang gyro; bốn cửa sổ pilot cùng một run nên không phải quan sát độc lập.
- Quy tắc ai_observation_rules_v0.1 do AI đề xuất, chưa được nhóm phê duyệt.

**8. Câu hỏi cần người đánh giá xác nhận.**

- Mốc 0 của Roll ở nguồn southampton đã được hiệu chuẩn chưa? Độ lệch 0.705° là nghiêng thực của tàu/mô hình hay sai lệch lắp đặt?
- Sự tăng biên độ này có trùng với một pha thí nghiệm/khởi phát sóng hoặc sự kiện vận hành được ghi nhận không? Nhóm có chấp nhận tiêu chí tăng biên độ dựa trên kiểm định xu hướng và vượt lịch sử không?
- HIGH_ROLL: có giới hạn vận hành hoặc operating envelope được xác thực cho tàu/mô hình này không?
- Nhiều phenotype cùng xuất hiện: nhóm muốn giữ đồng thời các cờ hay chọn lớp chính theo quy ước nào?

## 7. Giải thích kết quả phục vụ vấn đáp cá nhân

### 7.1. Tín hiệu được phân tích như thế nào?

Em không chỉ nhìn biểu đồ hay đọc lại feature có sẵn. Script đọc chuỗi Roll/Pitch 10 Hz đã preprocessing của từng record, cắt đúng cửa sổ `(t-180, t]`, chia thành ba block 60 s và chín sub-block 20 s, rồi tính lại thống kê. Kết quả được so với feature table: 26 feature của cả 29 record khớp đến sai số làm tròn float32, nên các con số trong báo cáo là cùng một nguồn dữ liệu với pipeline. Điểm quan trọng là em tách **mức trung bình** (offset) khỏi **dao động quanh trung bình** (std). RMS gộp cả hai nên có thể gây hiểu nhầm.

### 7.2. Các phenotype khác nhau thế nào?

- **PERSISTENT_OFFSET** nói về *vị trí trung bình*: Roll lệch về một phía và giữ dấu theo thời gian. Ví dụ `PILOT-5e1196364be9` (Seafar) có mean 3.106°, std chỉ 0.065°, 100% mẫu dương.
- **AMPLITUDE_GROWTH** nói về *độ lớn dao động thay đổi theo thời gian*. Ví dụ `PILOT-c2643af463e2` (Southampton): std 20 s đi từ 0.014° lên 0.127°, Mann–Kendall p=0.0004.
- **HIGH_ROLL** nói về *dao động lớn so với giới hạn vận hành*. Vì chưa có giới hạn được xác thực, em chỉ mô tả "tương đối mạnh trong nguồn" bằng hạng phần trăm, ví dụ `PILOT-fb456420a73f` có std 60 s cuối ở hạng 98 trong Hohai, nhưng không gọi đó là HIGH_ROLL.
- **NORMAL** cần envelope vận hành bình thường độc lập. `PILOT-e0713611700d` có biên độ nhỏ nhất nhóm Hohai (std 60 s cuối ở hạng 3) nhưng vẫn để `UNLABELED`, vì biên độ nhỏ không chứng minh trạng thái bình thường.

### 7.3. Vì sao offset có thể che mất tăng biên độ?

Ở `PILOT-c2643af463e2`, feature `roll_rms_ratio_180` chỉ bằng 1.039 vì RMS bị offset 0.705° chi phối, trong khi tỷ lệ std quanh trung bình muộn/sớm là 6.43. Nếu chỉ dùng RMS ratio làm proxy, mẫu này sẽ bị bỏ sót. Đây là lý do em báo cáo cả RMS và centered RMS, và cũng là câu hỏi nên đưa cho nhóm khi chốt định nghĩa feature nhóm D.

### 7.4. Vì sao một số mẫu vẫn mơ hồ?

- **Tăng ngắn hạn so với tăng bền vững.** `PILOT-fb456420a73f` có RMS ba block tăng (ratio 1.39), nhưng std 20 s dao động lên xuống [0.47, 0.36, 0.42, 0.54, 0.54, 0.37, 0.29, 0.51, 0.84] và Mann–Kendall p=0.24; bối cảnh trước đó đã có sub-block 0.80°. Đây giống nhóm sóng (wave group) hơn là tăng bền vững, nhưng không có dữ liệu sau endpoint để chắc chắn.
- **Đa kiểm định.** `PILOT-279f4ef04864` và `PILOT-db0b97396fc9` có p=0.038 và p=0.038: dưới 0.05 nhưng với 29 kiểm định thì kỳ vọng khoảng 1.45 kết quả dương tính giả, nên em chỉ xếp vào mức yếu.
- **Offset nhỏ.** `PILOT-88aebf3cd137` có mean 0.219° và 9/9 sub-block dương, nhưng dao động vẫn cắt mốc 0 (sign ratio 0.749). Có thật về thống kê nhưng chưa biết có lớn hơn sai số zero của cảm biến hay không.
- **Trôi trung bình.** `PILOT-9299db975778` có mean 20 s đổi dấu `++-------`; đây là trôi qua mốc 0 chứ không phải lệch ổn định, nên không gắn PERSISTENT_OFFSET.
- **Chất lượng tín hiệu.** `PILOT-9115297d34b5` (Seafar) chỉ có 15 giá trị Roll khác nhau do lượng tử 0.01°, std 0.031°, nên chu kỳ zero-crossing 11.5 s chủ yếu phản ánh nhiễu lượng tử.
- **Mốc 0 chưa xác nhận.** Ngay cả offset mạnh của Seafar/Southampton vẫn có thể là sai lệch lắp đặt thay vì nghiêng thật.

### 7.5. Vì sao AI-assisted annotation không phải ground truth?

- Quy tắc do AI đề xuất, chưa được nhóm phê duyệt; nó chỉ làm minh bạch cách đọc tín hiệu.
- AI nhìn cùng tín hiệu và cùng loại thống kê mà mô hình sau này sẽ học. Nếu dùng nhãn AI để train rồi test trên feature tương tự thì chỉ đo được khả năng tái tạo quy tắc (circular labeling).
- Không có nguồn độc lập như nhật ký vận hành, ghi chú thí nghiệm hoặc envelope được xác thực. Không được tính "inter-reviewer agreement" bằng cách chạy AI nhiều lần, vì các lần chạy đó không độc lập như hai người đánh giá.

### 7.6. Cần thêm bằng chứng gì để huấn luyện đáng tin cậy?

1. Ít nhất hai người đánh giá độc lập review 29 record trên giao diện Streamlit *trước khi* xem bảng gợi ý AI (tránh anchoring), sau đó so sánh với bảng AI để tìm bất đồng.
2. Xác nhận mốc 0/mounting của cảm biến Roll cho từng nguồn và sai số zero.
3. Envelope NORMAL và giới hạn HIGH_ROLL có tài liệu độc lập, đúng quy mô (tàu thật khác mô hình).
4. Ghi chú pha thí nghiệm (thời điểm sóng tới, kết thúc run) cho Southampton/Hohai, nhật ký vận hành cho Seafar.
5. Thêm session độc lập; chia train/test theo session/run, không theo cửa sổ chồng lấn.

### 7.7. Có thể và không thể khẳng định gì?

| Có thể khẳng định | Không thể khẳng định |
|---|---|
| Các số đo được tính lại trực tiếp từ dữ liệu và khớp feature table | Bất kỳ record nào là nguy hiểm hoặc an toàn |
| Seafar/Southampton có Roll lệch một phía trong toàn cửa sổ | Độ lệch đó là nghiêng thật của tàu/mô hình |
| `PILOT-c2643af463e2` có biên độ Roll và Pitch tăng rõ trong 80 s cuối | Đó là cơ chế mất ổn định Roll thay vì thay đổi kích thích/pha thí nghiệm |
| Hohai chủ yếu là dao động tuần hoàn đều, offset rất nhỏ | Mẫu Hohai nào là NORMAL hay HIGH_ROLL |
| Bảng gợi ý giúp người đánh giá tập trung vào chỗ mơ hồ | Bảng gợi ý là nhãn huấn luyện hay ground truth |
