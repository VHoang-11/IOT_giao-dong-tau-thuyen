# M2-R3 – Đánh giá kết quả ML so với yêu cầu M2-07

> **Phạm vi.** Báo cáo chỉ dùng bằng chứng đã có trong repo/artifact; không huấn luyện lại, không sinh dataset mới, không chạy đánh giá mới. Mọi metric RF là **mức khớp với proxy label** `RELATIVE_HIGH_ROLL` trên dữ liệu Hohai model-scale (nhãn sinh từ luật ngưỡng trên chính feature), không phải độ chính xác phát hiện nguy hiểm hàng hải. NEG = proxy-negative, không phải NORMAL đã kiểm chứng.

**Quy ước trạng thái:** **PASS** = có bằng chứng đo đầy đủ theo đúng yêu cầu; **PARTIAL** = có bằng chứng nhưng khác định nghĩa/phạm vi yêu cầu; **NOT_EVALUABLE** = thiếu điều kiện tiên quyết (dữ liệu, nhãn, mô hình) nên chưa thể đo một cách hợp lệ; **NOT_RUN** = điều kiện đã có nhưng chưa chạy.

**Nguồn:** `ml/reports/ml/rf_poc_results.json`, `random_forest_poc_report.md`, `rf_poc_model_card.json`, `esp32_feasibility.json`, `g1_coursework_dataset_audit.md`; `ml/docs/M2_R1_rf_demo_c_export.md`; capture M2-R2 `ml/data/models/rf_demo_m2r1/esp32_replay/wokwi05|wokwi06/` (gitignored); `core/src/baseline.c`; yêu cầu: `KeHoach_ChiaViec_4ThanhVien.md` (M2-07), `SmartVesselMotionGuard_DeCuong_v2.md` §6, §7.5, §10.2, T04.

## 1. Tóm tắt kết luận

| Yêu cầu M2-07 / §10.2 | Trạng thái | Bằng chứng ngắn |
|---|---|---|
| Macro-F1 toàn bộ 4 lớp | **NOT_EVALUABLE** | Chỉ 1/3 target proxy qua cổng readiness (RELATIVE_HIGH_ROLL); không có RF 4 lớp. F1 nhị phân proxy = 1.000 (không phải macro-F1 4 lớp). |
| Precision/recall/F1 + confusion matrix | **PARTIAL** | Có đầy đủ cho target proxy nhị phân trên Hohai; không có cho NORMAL/HIGH_ROLL/PERSISTENT_OFFSET/AMPLITUDE_GROWTH. |
| Đánh giá theo nhóm, không rò rỉ | **PASS** | Nested leave-one-Tn-out, 9 nhóm; kiểm toán rò rỉ 9/9 fold sạch. |
| Cảnh báo giả/giờ | **NOT_EVALUABLE** | Không có NORMAL đã kiểm chứng (Hohai NEG ≠ NORMAL); không có mã đếm WARNING/giờ. |
| ≥ 100 h NORMAL | **NOT_EVALUABLE** | Không tồn tại bộ NORMAL dài; G1 chỉ có 9 phiên S0 × 20 phút = 3,0 h mô phỏng (mọi split). |
| Độ trễ phát hiện (t0 → cảnh báo đầu, cold/warm) | **NOT_EVALUABLE** | Hohai không có t0 sự kiện; G1 có kịch bản nhưng RF G1 bị chặn (`BLOCKED_MISSING_CLASS_GROUP_COVERAGE`). |
| Bootstrap theo phiên (1.000 lần) | **PARTIAL** | Bootstrap 2.000 lần theo **9 nhóm Tn** (chặt hơn phiên vì phiên cùng Tn tương quan), chỉ cho F1 proxy; khoảng suy biến [1,0; 1,0]. |
| RF so với Baseline B | **NOT_EVALUABLE** | Không có dataset chung với ground truth chung (mục 5). |
| RF so với baseline (khác) | **PARTIAL** | Có 4 baseline proxy-rule trên cùng nhãn proxy, nhưng phép so sánh mang tính vòng (mục 4). Baseline A/B theo đề cương chưa đánh giá. |
| RF chạy trên ESP32, tài nguyên thiết bị | **PARTIAL** | Wokwi replay 2 lần `WOKWI_PASS`, 216/216 vector khớp; latency là thời gian **mô phỏng Wokwi**; ESP32 vật lý NOT_RUN. |

## 2. RF: precision, recall, F1, confusion matrix (đo được)

Test = nhóm giữ lại, gộp 9 outer fold, chỉ cửa sổ POS/NEG (ABSTAIN loại khỏi metric). Support: 209 POS / 1118 NEG.

| Mô hình | TP | FP | FN | TN | Precision | Recall | F1 | PR-AUC | F1 bootstrap nhóm 2,5–97,5% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| RF `full_23` (200 cây, chọn tham số lồng) | 209 | 0 | 0 | 1118 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000–1,000 |
| RF `no_direct_alias` (20 feature) | 209 | 0 | 0 | 1118 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000–1,000 |
| RF `no_roll_amplitude` (10 feature) | 113 | 21 | 96 | 1097 | 0,843 | 0,541 | 0,659 | 0,681 | 0,579–0,784 |
| RF compact (25 cây, depth 6 – model demo) | 209 | 0 | 0 | 1118 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000–1,000 |

Model demo xuất C (fold giữ lại `hohai|T9`): TP 46, FP 0, FN 0, TN 124 trên 170 cửa sổ có nhãn của T9.

## 3. Đánh giá theo nhóm và mất cân bằng lớp

- **Nhóm độc lập = điều kiện thử nghiệm Tn**, không phải session: các session cùng Tn có Roll tương quan chéo cao. 9 nhóm, 21 session, 1512 cửa sổ đủ 23 feature.
- **POS chỉ có ở 3/9 nhóm** (T7: 27, T8: 136, T9: 46). Sáu fold T1–T6 chỉ đo được FP (đều 0); recall thực chất được ước lượng trên 3 nhóm.
- **Prevalence 0,157**: PR-AUC của bộ phân loại hằng số bằng 0,157; baseline "luôn NEG" có F1 = 0. RF `full_23` không chọn `class_weight` (inner CV chọn `null` ở cả 9 fold); model compact dùng `balanced_subsample` khai báo trước. Không oversampling, không nhãn tổng hợp.
- **Bootstrap theo nhóm** chỉ có 1943/2000 replicate hợp lệ (replicate không có POS bị loại). Khoảng [1,0; 1,0] hẹp vì mô hình khớp hoàn hảo, **không** vì dữ liệu nhiều.
- **ABSTAIN:** 185 cửa sổ test ở dải phân vị 0,80–0,90 bị loại khỏi metric; RF `full_23` dự đoán POS cho 73/185 cửa sổ này (T7 13/23, T8 39/111, T9 21/46). Bỏ dải biên làm bài toán dễ hơn thực tế.

## 4. RF so với baseline proxy-rule (cùng nhãn proxy, cùng fold)

| Baseline | TP | FP | FN | TN | Precision | Recall | F1 | F1 bootstrap nhóm |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Luôn NEG | 0 | 0 | 209 | 1118 | không xác định | 0,000 | 0,000 | — |
| Luật `roll_std_60` (= chính proxy) | 209 | 0 | 0 | 1118 | 1,000 | 1,000 | 1,000 | 1,000–1,000 |
| Luật `roll_rms_60` | 207 | 0 | 2 | 1118 | 1,000 | 0,990 | 0,995 | 0,989–1,000 |
| Luật `pitch_std_60` | 116 | 19 | 93 | 1099 | 0,859 | 0,555 | 0,674 | 0,593–0,838 |

**Vì sao F1 = 1,0 không chứng minh RF vượt trội:**
1. **Vòng lặp nhãn–feature:** proxy POS là `roll_std_60 ≥ T_pos` (phân vị 0,90 theo session, fit trên train; mô hình cuối T_pos = 0,492°, T_neg = 0,433°). `roll_std_60` là một trong 23 feature đầu vào, nên luật một feature đạt F1 = 1 theo cấu trúc và RF chỉ cần học lại ngưỡng đó.
2. **RF hòa đúng baseline luật proxy** (cùng 209/0/0/1118); chênh với luật `roll_rms_60` chỉ là 2 FN trên 209 POS, nằm trong khoảng bootstrap chồng nhau.
3. **Ablation** bỏ bí danh trực tiếp vẫn F1 = 1 vì nhiều feature biên độ Roll mang cùng thông tin (Spearman với `roll_std_60` ≥ 0,92 trên Hohai); bỏ toàn bộ biên độ Roll thì F1 = 0,659, ngang luật chỉ Pitch (0,674): phần còn lại phản ánh mức kích thích sóng chung.
4. **Không có ground truth độc lập** (không nhãn chuyên gia, không nhật ký hazard), nên không có cơ sở đo khả năng tổng quát hóa ngoài luật proxy.
5. **Dịch miền với chuỗi firmware:** mô phỏng chuỗi lọc 0,5 Hz + 2 Hz (`esp32_feasibility.json`) làm `roll_std_60` còn ≈ 0,67× (median); quyết định proxy POS giảm từ 152 xuống 4 cửa sổ. Ngưỡng/mô hình học trên tiền xử lý Hohai không chuyển thẳng sang IMU production.

## 5. RF so với Baseline B production: hiện **không phải phép so sánh hợp lệ**

Baseline B (`core/src/baseline.c`) là luật **4 lớp với ngưỡng tuyệt đối demo**: HIGH_ROLL khi `roll_std_60 ≥ 6°`; AMPLITUDE_GROWTH khi `roll_rms_slope_180 ≥ 1` và `roll_std_60 ≥ 1,5°` và `|roll_mean_60| < 1,5°`; PERSISTENT_OFFSET khi `|roll_mean_60|, |roll_mean_180| ≥ 1,5°`, cùng dấu, `roll_dominant_sign_ratio_180 ≥ 0,75` và thời lượng tương đương > 120 s; còn lại NORMAL; NaN → UNKNOWN.

Lý do không so sánh được:
- **Khác định nghĩa đầu ra và nhãn:** RF là proxy nhị phân tương đối (phân vị trong miền Hohai); Baseline B là 4 lớp ngưỡng tuyệt đối. Không có tập nào gán cả hai loại nhãn cho cùng một ground truth.
- **Khác thang biên độ:** trên toàn bộ cửa sổ Hohai đủ feature, `roll_std_60` ∈ [0,178°; 0,866°], `|roll_mean_60|` ≤ 0,269°, `|roll_mean_180|` ≤ 0,238° (`rf_poc_model_card.json`, `feature_ranges`). Suy luận trực tiếp từ các khoảng này: mọi điều kiện kích hoạt của Baseline B (6°, 1,5°) đều không thể thỏa, nên Baseline B sẽ trả NORMAL cho mọi cửa sổ Hohai đủ feature. Đây là suy luận từ khoảng giá trị đã ghi, không phải một lần chạy Baseline B; kết quả đó không cho biết gì về chất lượng của hai phương pháp.
- **Khác tiền xử lý:** feature Hohai `candidate-30-v1` khác chuỗi production `imu-cf-bw4-20to10-v1`.
- Dataset đúng nơi so sánh được (Test-G1/G2 + NORMAL dài theo T04) chưa có RF: G1 bị chặn do S3 (AMPLITUDE_GROWTH) có 0 cửa sổ đủ điều kiện ở Train/Validation; Test-G2 và NORMAL dài chưa tồn tại.

→ **RF vs Baseline B: NOT_EVALUABLE.** Theo §7.5 đề cương, khi so sánh được thì kết quả hòa hoặc Baseline B tốt hơn vẫn là kết quả hợp lệ; hiện chưa có dữ liệu để kết luận theo hướng nào.

## 6. Inference trên Wokwi và footprint (đo được)

Hai lần replay độc lập, `execution_kind = wokwi_simulation`, cùng firmware (`firmware.bin` SHA-256 `6ce53872…`), chip báo `ESP32-D0WDQ6-V3`, 240 MHz. Checksum transcript được kiểm lại khớp file.

| Run | Vector | Lỗi transport / status / pred / score | max \|Δscore\| | Đầu vào lỗi | Latency median / p95 / max (µs) |
|---|---:|---|---:|---|---|
| wokwi05 | 216 | 0 / 0 / 0 / 0 | 2,7e-8 | 9/9 | 331 / 435 / 442 |
| wokwi06 | 216 | 0 / 0 / 0 / 0 | 2,7e-8 | 9/9 | 367 / 437 / 442 |

- Latency chỉ đo quanh lời gọi `svmg_rf_proxy_demo_predict()` và là **thời gian mô phỏng Wokwi**. Con số ~27,5 µs trong `esp32_feasibility.json` là **ước tính** cho model 200 cây (20 chu kỳ/phép so sánh), không phải số đo. Latency trên ESP32 vật lý: **NOT_RUN**.
- Footprint model compact: 209 nút (92 nút trong, 117 lá), depth tối đa 5, mảng model 1931 B; object ESP32 `-Os` 2689 B (M2-R1, xtensa-esp32-elf-gcc) / 2726 B (bản build PlatformIO M2-R2).
- Firmware demo cô lập (ELF, `xtensa-esp32-elf-size`): text 201.351 B, data 71.145 B, bss 5.812 B; `firmware.bin` 272.608 B. Log build M2-R2 báo RAM 22.620 B (6,9%), Flash 268.612 B (20,5%); log này không được lưu trong repo.
- Firmware demo không đọc MPU6050, không đăng ký `svmg_engine_set_rf()`, không điều khiển alarm, không thay Baseline B.

## 7. Giới hạn còn lại cho học phần

1. Không có ground truth độc lập; nhãn proxy sinh từ chính feature, nên mọi metric RF là mức tái tạo luật.
2. Một miền duy nhất (Hohai model-scale), 9 nhóm, POS ở 3 nhóm; 2/3 target proxy NOT_TRAINABLE.
3. Không có RF 4 lớp, không có macro-F1 4 lớp, không có confusion matrix theo S0b/H1/Test-G1/Test-G2.
4. Không có bộ NORMAL dài, không đo cảnh báo giả/giờ, không đo độ trễ phát hiện; bootstrap theo nhóm, không theo phiên, chỉ cho F1.
5. Model demo không tương thích tiền xử lý production; dịch miền đã được ước lượng (POS 152 → 4).
6. Latency mới có trong mô phỏng Wokwi; chưa đo trên ESP32 vật lý.

## 8. Việc cần làm để chuyển NOT_EVALUABLE thành có bằng chứng (ngoài phạm vi M2-R3)

- Bổ sung coverage G1 cho S3 ở Train/Validation rồi huấn luyện RF 4 lớp theo hợp đồng `M2_B2a_four_class_label_and_rf_contract.md`; đánh giá RF, Baseline A, Baseline B **trên cùng** Test-G1/Test-G2.
- Sinh bộ NORMAL ≥ 100 h (gồm S0b) để đo cảnh báo WARNING+/giờ cho cả RF và Baseline B.
- Thêm bộ đo độ trễ phát hiện theo t0 của bộ sinh (cold/warm, median, P90, tỉ lệ MISS) và bootstrap theo phiên 1.000 lần.
- Đo latency trên ESP32 vật lý với cùng protocol replay M2-R2.
