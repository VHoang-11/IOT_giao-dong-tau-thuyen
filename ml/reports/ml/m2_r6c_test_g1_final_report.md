# Báo cáo đánh giá Test-G1 cuối cùng M2-R6c (`svmg-rf-four-class-m2r6a-0.1.0`)

> Đánh giá **một lần, chỉ đọc** mô hình đóng băng (M2-R6a/R6b) trên Test-G1 của `svmg-four-class-exp-0.3.0` (`SIMULATION`, nhãn proxy `SIMULATION_SCENARIO_V2_CANDIDATE`). Không huấn luyện/chọn lại, không đổi tau, nhãn, đặc trưng hay exporter. Sinh bởi `python -m ml.eval.final_test_g1_m2r6c`; kết quả khóa (gitignored) tại `ml/data/models/rf_four_class_m2r6/v03/test_g1/results.json`, kiểm tra tái lập bằng `--verify`.

## 1. Xác minh artifact đóng băng (trước khi mở Test-G1)

`class_order`=True, `dataset_sha256`=True, `feature_order`=True, `header_regenerates_identically`=True, `header_sha256`=True, `manifest_status`=True, `model_sha256`=True, `schema_preprocessing`=True, `tau_is_0_5`=True, `test_g1_disjoint_from_train_validation`=True, `test_g1_sessions_frozen`=True. tau = 0.5.

## 2. Phân bố Test-G1

- 10 session, 1190 cửa sổ; 300 cửa sổ CORE có nhãn được đánh giá.
- Cửa sổ/session có nhãn theo lớp: NORMAL 146/2; HIGH_ROLL 39/2; PERSISTENT_OFFSET 100/2; AMPLITUDE_GROWTH 15/3.
- ABSTAIN (không đánh giá): CORE_FEATURE_INVALID 170, ENDPOINT_LABEL_MISMATCH 284, LABEL_WARMUP 48, PHENOTYPE_OVERLAP 13, PRE_EVENT 159, TRANSITION_IN_WINDOW 216.

## 3. Kết quả cuối cùng

| Chỉ số | RF trước tau | RF sau tau = 0,5 (UNKNOWN = bỏ sót) | Baseline B (cùng cửa sổ) | RF Validation trước / sau tau |
|---|---:|---:|---:|---:|
| Accuracy | 0.9267 | 0.8467 | 0.68 | 0.9979 / – |
| Macro-F1 | 0.8698 | 0.8158 | 0.5321 | 0.9876 / – |
| Weighted-F1 | 0.9386 | 0.8974 | 0.7163 | 0.9979 / – |
| Tỉ lệ được phân loại | 1.0 | 0.9167 | 1.0 | 1.0 / 0.9936 |
| Accuracy trên phần được phân loại | 0.9267 | 0.9236 | 0.68 | – |
| KTC 95% macro-F1 trước tau (bootstrap theo session) | [0.5225, 0.9526] | – | – | – |

Macro-F1 trước tau giảm từ 0.9876 (Validation) xuống 0.8698 (Test-G1): Validation chỉ 12 session và đã dùng để chọn cấu hình nên lạc quan; Test-G1 là ước lượng trung thực hơn trong cùng miền mô phỏng.

Precision / recall / F1 theo lớp (sau tau là recall hiệu dụng):

| Lớp | RF trước tau | RF sau tau | Baseline B | Recall hiệu dụng Validation sau tau |
|---|---:|---:|---:|---:|
| NORMAL | 0.992 / 0.856 / 0.919 | 1.000 / 0.843 / 0.914 | 0.924 / 0.671 / 0.778 | 0.9871 |
| HIGH_ROLL | 1.000 / 1.000 / 1.000 | 1.000 / 0.949 / 0.974 | 0.382 / 1.000 / 0.553 | 1.0 |
| PERSISTENT_OFFSET | 1.000 / 1.000 / 1.000 | 1.000 / 0.830 / 0.907 | 0.985 / 0.670 / 0.798 | 1.0 |
| AMPLITUDE_GROWTH | 0.400 / 0.933 / 0.560 | 0.344 / 0.733 / 0.468 | 0.000 / 0.000 / 0.000 | 0.9 |

Ma trận nhầm lẫn RF trước tau:

| Thật \ Dự đoán | NORMAL | HIGH_ROLL | PERSISTENT_OFFSET | AMPLITUDE_GROWTH |
|---|---:|---:|---:|---:|
| NORMAL | 125 | 0 | 0 | 21 |
| HIGH_ROLL | 0 | 39 | 0 | 0 |
| PERSISTENT_OFFSET | 0 | 0 | 100 | 0 |
| AMPLITUDE_GROWTH | 1 | 0 | 0 | 14 |

RF sau tau:

| Thật \ Dự đoán | NORMAL | HIGH_ROLL | PERSISTENT_OFFSET | AMPLITUDE_GROWTH | UNKNOWN |
|---|---:|---:|---:|---:|---:|
| NORMAL | 123 | 0 | 0 | 21 | 2 |
| HIGH_ROLL | 0 | 37 | 0 | 0 | 2 |
| PERSISTENT_OFFSET | 0 | 0 | 83 | 0 | 17 |
| AMPLITUDE_GROWTH | 0 | 0 | 0 | 11 | 4 |

Baseline B:

| Thật \ Dự đoán | NORMAL | HIGH_ROLL | PERSISTENT_OFFSET | AMPLITUDE_GROWTH |
|---|---:|---:|---:|---:|
| NORMAL | 98 | 23 | 1 | 24 |
| HIGH_ROLL | 0 | 39 | 0 | 0 |
| PERSISTENT_OFFSET | 8 | 25 | 67 | 0 |
| AMPLITUDE_GROWTH | 0 | 15 | 0 | 0 |

## 4. UNKNOWN, độ phủ nhãn và lỗi

- UNKNOWN sau tau: 25 cửa sổ, theo lớp thật {'AMPLITUDE_GROWTH': 4, 'HIGH_ROLL': 2, 'NORMAL': 2, 'PERSISTENT_OFFSET': 17}; không UNKNOWN nào được tính là đúng.
- Accuracy trước tau theo `target_coverage_180`: [0.0, 0.25) 0.9688 (n=32); [0.25, 0.5) 1.0 (n=28); [0.5, 0.75) 1.0 (n=25); [0.75, 1.0) 0.7857 (n=42); [1.0, 1.0001) 0.9306 (n=173).
- AMPLITUDE_GROWTH: 15 cửa sổ/3 session; recall Wilson 95% trước tau [0.7018, 0.9881], precision [0.2555, 0.5643]. Ca lỗi liên quan GROWTH sau tau: S0-seed-3616852506 t=572s phủ 1.000 NORMAL→AMPLITUDE_GROWTH (conf 0.5489); S0-seed-3616852506 t=702s phủ 1.000 NORMAL→AMPLITUDE_GROWTH (conf 0.5171); S0-seed-3616852506 t=902s phủ 1.000 NORMAL→AMPLITUDE_GROWTH (conf 0.6426); S0-seed-3616852506 t=912s phủ 1.000 NORMAL→AMPLITUDE_GROWTH (conf 0.6952); S0-seed-3616852506 t=922s phủ 1.000 NORMAL→AMPLITUDE_GROWTH (conf 0.7858); S0-seed-3616852506 t=932s phủ 1.000 NORMAL→AMPLITUDE_GROWTH (conf 0.8441); S0-seed-3616852506 t=942s phủ 1.000 NORMAL→AMPLITUDE_GROWTH (conf 0.6952); S0-seed-3616852506 t=952s phủ 1.000 NORMAL→AMPLITUDE_GROWTH (conf 0.6093); S0-seed-3616852506 t=1062s phủ 1.000 NORMAL→AMPLITUDE_GROWTH (conf 0.5401); S0-seed-3616852506 t=1072s phủ 1.000 NORMAL→AMPLITUDE_GROWTH (conf 0.6068); S0-seed-3616852506 t=1082s phủ 1.000 NORMAL→AMPLITUDE_GROWTH (conf 0.7428); S0-seed-3616852506 t=1092s phủ 1.000 NORMAL→AMPLITUDE_GROWTH (conf 0.7186); S0-seed-3616852506 t=1112s phủ 0.954 NORMAL→AMPLITUDE_GROWTH (conf 0.8174); S0-seed-3616852506 t=1122s phủ 0.954 NORMAL→AMPLITUDE_GROWTH (conf 0.8174); S0-seed-3616852506 t=1132s phủ 0.954 NORMAL→AMPLITUDE_GROWTH (conf 0.8441); S0-seed-2437215599 t=1012s phủ 0.845 NORMAL→AMPLITUDE_GROWTH (conf 0.5286); S0-seed-2437215599 t=1022s phủ 0.845 NORMAL→AMPLITUDE_GROWTH (conf 0.5477); S0-seed-2437215599 t=1032s phủ 0.845 NORMAL→AMPLITUDE_GROWTH (conf 0.5404); S0-seed-2437215599 t=1042s phủ 0.845 NORMAL→AMPLITUDE_GROWTH (conf 0.7586); S0-seed-2437215599 t=1072s phủ 0.759 NORMAL→AMPLITUDE_GROWTH (conf 0.5874); S0-seed-2437215599 t=1082s phủ 0.759 NORMAL→AMPLITUDE_GROWTH (conf 0.5477); S3-seed-3396042960 t=1062s phủ 0.001 AMPLITUDE_GROWTH→UNKNOWN (conf 0.4221); S3-seed-3396042960 t=1072s phủ 0.057 AMPLITUDE_GROWTH→UNKNOWN (conf 0.4908); S3-seed-3396042960 t=1082s phủ 0.112 AMPLITUDE_GROWTH→UNKNOWN (conf 0.4809); S3-seed-3396042960 t=1092s phủ 0.168 AMPLITUDE_GROWTH→UNKNOWN (conf 0.49).
- Lỗi trước tau: AMPLITUDE_GROWTH->NORMAL: 1 cửa sổ/1 session; NORMAL->AMPLITUDE_GROWTH: 21 cửa sổ/2 session.
- Session đúng theo đa số (trước tau): 9/9. Session có lỗi/UNKNOWN sau tau: S0-seed-2437215599 (NORMAL): acc hiệu dụng 0.9041, UNKNOWN 1, sai lớp 6; S0-seed-3616852506 (NORMAL): acc hiệu dụng 0.7808, UNKNOWN 1, sai lớp 15; S1-seed-2133259564 (HIGH_ROLL): acc hiệu dụng 0.9167, UNKNOWN 2, sai lớp 0; S2-seed-0407543745 (PERSISTENT_OFFSET): acc hiệu dụng 0.5641, UNKNOWN 17, sai lớp 0; S3-seed-3396042960 (AMPLITUDE_GROWTH): acc hiệu dụng 0.2, UNKNOWN 4, sai lớp 0.

## 5. Parity C99 / Python trên Test-G1

300 vector: lệch lớp 0, lệch lớp cuối sau tau 0, lệch UNKNOWN 0, max |Δp| 3.29e-08, biên top-2 nhỏ nhất 0.00387, hòa chính xác 0.

## 6. Giới hạn

- Nhãn và đặc trưng cùng sinh từ một bộ mô phỏng; nhãn là proxy theo ngưỡng labeling-v2 candidate, RF học lại các luật đó. Kết quả **không** phải độ chính xác phát hiện nguy hiểm, không phải dự báo lật tàu hay đánh giá GM/GZ.
- Test-G1 cùng miền tham số với Train/Validation (không phải Test-G2 hay dữ liệu MPU6050 thật); số session mỗi lớp nhỏ, cửa sổ trong một session không độc lập. tau = 0,5 là giá trị dự phòng, độ tin cậy chưa hiệu chuẩn.

## 7. Sẵn sàng tích hợp ESP32

- Tiêu chí khai báo trước (macro-F1 hiệu dụng ≥ 0.8, recall hiệu dụng mọi lớp ≥ 0.5, parity C99 không lệch): **ĐẠT**.
- Rủi ro chính: 21 cửa sổ không phải GROWTH bị báo AMPLITUDE_GROWTH sau tau (precision GROWTH 0.3438); UNKNOWN tập trung ở PERSISTENT_OFFSET (17 cửa sổ). Firmware xử lý UNKNOWN là trạng thái UNKNOWN, không phải NORMAL.
- Có thể dùng header đóng băng cho **demo Wokwi trên dữ liệu mô phỏng** (M2-R7, cần M1 review `model.h`); chưa phải triển khai an toàn trên tàu thật, cần đo thời gian suy luận ESP32 và dữ liệu cảm biến thật.
