# Báo cáo chất lượng bộ dữ liệu bốn lớp thử nghiệm M2-R5c (`svmg-four-class-exp-0.2.0`)

> Hợp đồng `svmg-four-class-label-contract-0.2.0` (`ml/docs/M2_R5c_four_class_dataset_contract.md`), chính sách `endpoint-phenotype-180s-history-0.2.0-APPROVED-EXPERIMENTAL`. Nhãn là proxy mô phỏng theo kịch bản + ngưỡng labeling-v2 candidate đóng băng, không phải ground truth nguy hiểm ngoài thực tế. Báo cáo sinh tự động bởi `python -m ml.train.four_class_experimental_dataset`; dữ liệu gitignored tại `ml/data/simulation_four_class_exp_v02/`. Không huấn luyện hay đánh giá RF.

Session: 79; cửa sổ: 9401; đủ điều kiện: 1959. Cổng chất lượng: all_classes_in_train_and_validation=True, no_nan_in_eligible_features=True, coverage_recorded_for_all_eligible=True.

## Phân bố lớp, độ đa dạng session và độ phủ nhãn đích trong lịch sử 180 s

Cột: cửa sổ, session đóng góp, session hiệu dụng (Σn)²/Σn², tỉ phần lớn nhất của một session, trung vị và nhỏ nhất của `target_coverage_180`, rồi số cửa sổ/session còn lại nếu yêu cầu độ phủ ≥ 0,5 / 0,75 / 1,0 (chỉ là phân tích độ nhạy; chính sách chính không đổi).

| Tập | Split | Lớp | Cửa sổ | Session | Session hiệu dụng | Tỉ phần lớn nhất | Phủ trung vị | Phủ nhỏ nhất | ≥0,5 | ≥0,75 | =1,0 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CHALLENGE_S0B | Train | NORMAL | 200 | 4 | 3.96 | 0.29 | 1.000 | 1.000 | 200/4 | 200/4 | 200/4 |
| CHALLENGE_S0B | Validation | NORMAL | 104 | 2 | 1.98 | 0.548 | 1.000 | 0.585 | 104/2 | 90/2 | 86/2 |
| CORE | Test-G1 | AMPLITUDE_GROWTH | 15 | 3 | 2.42 | 0.533 | 0.116 | 0.001 | 0/0 | 0/0 | 0/0 |
| CORE | Test-G1 | HIGH_ROLL | 39 | 2 | 1.9 | 0.615 | 0.392 | 0.097 | 16/2 | 12/2 | 7/2 |
| CORE | Test-G1 | NORMAL | 146 | 2 | 2.0 | 0.5 | 1.000 | 0.718 | 146/2 | 144/2 | 121/2 |
| CORE | Test-G1 | PERSISTENT_OFFSET | 100 | 2 | 1.91 | 0.61 | 0.896 | 0.036 | 78/2 | 59/2 | 45/1 |
| CORE | Train | AMPLITUDE_GROWTH | 59 | 13 | 10.27 | 0.169 | 0.149 | 0.005 | 1/1 | 0/0 | 0/0 |
| CORE | Train | HIGH_ROLL | 104 | 6 | 5.27 | 0.26 | 0.621 | 0.036 | 60/5 | 30/4 | 24/4 |
| CORE | Train | NORMAL | 460 | 6 | 5.99 | 0.17 | 1.000 | 0.661 | 460/6 | 458/6 | 431/6 |
| CORE | Train | PERSISTENT_OFFSET | 263 | 5 | 4.57 | 0.255 | 1.000 | 0.029 | 238/5 | 215/5 | 193/4 |
| CORE | Validation | AMPLITUDE_GROWTH | 10 | 3 | 1.52 | 0.8 | 0.106 | 0.011 | 0/0 | 0/0 | 0/0 |
| CORE | Validation | HIGH_ROLL | 44 | 3 | 2.66 | 0.5 | 0.734 | 0.023 | 27/3 | 18/2 | 1/1 |
| CORE | Validation | NORMAL | 232 | 3 | 3.0 | 0.336 | 1.000 | 0.918 | 232/3 | 232/3 | 214/3 |
| CORE | Validation | PERSISTENT_OFFSET | 183 | 3 | 3.0 | 0.344 | 1.000 | 0.275 | 177/3 | 164/3 | 150/3 |

## Lý do ABSTAIN theo kịch bản

S0 CORE_FEATURE_INVALID 187; S0 ENDPOINT_LABEL_MISMATCH 20; S0 LABEL_WARMUP 264; S0b CORE_FEATURE_INVALID 102; S0b ENDPOINT_LABEL_MISMATCH 7; S0b PRE_EVENT 139; S0b TRANSITION_IN_WINDOW 162; S1 CORE_FEATURE_INVALID 187; S1 ENDPOINT_LABEL_MISMATCH 279; S1 PHENOTYPE_OVERLAP 119; S1 PRE_EVENT 240; S1 TRANSITION_IN_WINDOW 297; S2 CORE_FEATURE_INVALID 187; S2 ENDPOINT_LABEL_MISMATCH 110; S2 PHENOTYPE_OVERLAP 3; S2 PRE_EVENT 166; S2 TRANSITION_IN_WINDOW 297; S3 CORE_FEATURE_INVALID 680; S3 ENDPOINT_LABEL_MISMATCH 2233; S3 PRE_EVENT 683; S3 TRANSITION_IN_WINDOW 1080.

## Kiểm toán độ đa dạng seed

- Bộ dữ liệu này (seed SHA-256; Test-G1 lấy nguyên từ pilot): S0: không có sự kiện, sea state {'SS0': 3, 'SS1': 3, 'SS2': 2, 'SS3': 3}; S0b: t0 khác nhau 6/6, sea state {'SS0': 4, 'SS2': 2}; S1: t0 khác nhau 11/11, sea state {'SS0': 5, 'SS2': 3, 'SS3': 3}; S2: t0 khác nhau 10/11, sea state {'SS0': 5, 'SS1': 1, 'SS2': 4, 'SS3': 1}; S3: t0 khác nhau 39/40, sea state {'SS1': 23, 'SS2': 17}.
- G1 (seed tuần tự, chỉ đọc; khớp manifest G1: True): S0: không có sự kiện, sea state {'SS3': 9}; S1: t0 khác nhau 2/9, sea state {'SS2': 9}; S2: t0 khác nhau 3/9, sea state {'SS1': 8, 'SS2': 1}; S3: t0 khác nhau 3/9, sea state {'SS1': 9}. Artifact G1 không bị ghi lại.

## Giới hạn

- Nhãn và đặc trưng cùng sinh từ một bộ mô phỏng; ngưỡng candidate hiệu chỉnh trên chính bộ mô phỏng đó (D2).
- Nhãn mô tả phenotype tại thời điểm dự đoán; lịch sử 180 s có thể trộn trạng thái (D1, D3) — xem độ phủ ở trên.
- Chưa có pitch và nhiễu IMU (D5, PR riêng); ba đặc trưng pitch bằng 0. Chưa có Test-G2. S0b là tập challenge, không mặc định là dữ liệu huấn luyện NORMAL.

SHA-256 dataset: `b4b249d08dc2fae17476a62c2b596d14ead0ea1b8de75fd412a96d5110b4ad5c`.
