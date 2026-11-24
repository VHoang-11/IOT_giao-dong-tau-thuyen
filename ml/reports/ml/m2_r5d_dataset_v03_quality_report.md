# Báo cáo chất lượng bộ dữ liệu bốn lớp thử nghiệm M2-R5d (`svmg-four-class-exp-0.3.0`)

> `svmg-four-class-exp-0.2.0` + pitch/nhiễu IMU `svmg-sim-pitch-imu-0.1.0` cấu hình `PITCH_MPU6050_RESIDUAL`. Cùng session/seed, nhãn, ngưỡng đóng băng và chính sách `endpoint-phenotype-180s-history-0.2.0-APPROVED-EXPERIMENTAL` như v0.2; Test-G1 giữ nguyên. Nguồn `SIMULATION`, nhãn là proxy mô phỏng, không phải ground truth nguy hiểm. Sinh bởi `python -m ml.train.four_class_v03_dataset`; dữ liệu và manifest gitignored tại `ml/data/simulation_four_class_exp_v03/`. Không huấn luyện/đánh giá RF.

Session: 79; cửa sổ: 9401; có nhãn: 1959. Cổng chất lượng: all_classes_in_train_and_validation=True, no_nan_in_eligible_features=True, coverage_recorded_for_all_eligible=True, feature_columns_match_contract_order=True, unique_session_seeds_across_splits=True, pitch_features_not_identically_zero=True, labels_match_v02=True.

## Phân bố lớp theo split (cửa sổ/session), v0.2 so với v0.3

| Tập | Split | Lớp | v0.2 | v0.3 | Session hiệu dụng v0.3 | Phủ trung vị v0.3 |
|---|---|---|---:|---:|---:|---:|
| CHALLENGE_S0B | Train | NORMAL | 200/4 | 200/4 | 3.96 | 1.000 |
| CHALLENGE_S0B | Validation | NORMAL | 104/2 | 104/2 | 1.98 | 1.000 |
| CORE | Test-G1 | AMPLITUDE_GROWTH | 15/3 | 15/3 | 2.42 | 0.116 |
| CORE | Test-G1 | HIGH_ROLL | 39/2 | 39/2 | 1.9 | 0.392 |
| CORE | Test-G1 | NORMAL | 146/2 | 146/2 | 2.0 | 1.000 |
| CORE | Test-G1 | PERSISTENT_OFFSET | 100/2 | 100/2 | 1.91 | 0.896 |
| CORE | Train | AMPLITUDE_GROWTH | 59/13 | 59/13 | 10.27 | 0.149 |
| CORE | Train | HIGH_ROLL | 104/6 | 104/6 | 5.27 | 0.621 |
| CORE | Train | NORMAL | 460/6 | 460/6 | 5.99 | 1.000 |
| CORE | Train | PERSISTENT_OFFSET | 263/5 | 263/5 | 4.57 | 1.000 |
| CORE | Validation | AMPLITUDE_GROWTH | 10/3 | 10/3 | 1.52 | 0.106 |
| CORE | Validation | HIGH_ROLL | 44/3 | 44/3 | 2.66 | 0.734 |
| CORE | Validation | NORMAL | 232/3 | 232/3 | 3.0 | 1.000 |
| CORE | Validation | PERSISTENT_OFFSET | 183/3 | 183/3 | 3.0 | 1.000 |

## So sánh v0.2 và v0.3

- Khớp cửa sổ: 9401/9401; trùng nhãn 1.0; trùng lý do loại 1.0; nhãn đổi: không. SHA v0.2 `b4b249d08dc2…` không đổi.
- Tỉ lệ ABSTAIN (v0.2 → v0.3): CHALLENGE_S0B Train 0.5798 → 0.5798; CHALLENGE_S0B Validation 0.563 → 0.563; CORE Test-G1 0.7479 → 0.7479; CORE Train 0.8227 → 0.8227; CORE Validation 0.8123 → 0.8123.
- Lý do ABSTAIN v0.3: CORE_FEATURE_INVALID 1343, ENDPOINT_LABEL_MISMATCH 2649, LABEL_WARMUP 264, PHENOTYPE_OVERLAP 122, PRE_EVENT 1228, TRANSITION_IN_WINDOW 1836.
- Đặc trưng pitch trên cửa sổ có nhãn, p5 / trung vị / p95 (độ), kèm tỉ lệ bằng 0: `pitch_rms_60` 0.0 / 0.0 / 0.0 (0: 1.0) → 0.2216 / 0.5846 / 1.7543 (0: 0.0); `pitch_std_60` 0.0 / 0.0 / 0.0 (0: 1.0) → 0.1604 / 0.3759 / 1.7163 (0: 0.0); `pitch_peak_to_peak_60` 0.0 / 0.0 / 0.0 (0: 1.0) → 0.7065 / 1.6793 / 6.8983 (0: 0.0).
- |Δ| đặc trưng roll trên cửa sổ có nhãn ở cả hai bản (p5 / trung vị / p95): `roll_mean_60` 0.0403 / 0.1988 / 0.7144; `roll_std_60` 0.0002 / 0.0023 / 0.0066; `roll_rms_slope_180` 0.0007 / 0.0113 / 0.0907.
- AMPLITUDE_GROWTH (cửa sổ/session hiệu dụng/phủ trung vị): Test-G1 15/2.42/0.116; Train 59/10.27/0.149; Validation 10/1.52/0.106.

## Giới hạn

- Pitch, sea state và nhiễu là giả định mô phỏng chưa hiệu chỉnh với tàu/MPU6050 thật; chưa có gia tốc tịnh tiến, yaw, lượng tử hóa, trôi nhiệt, lệch trục (xem `ml/docs/M2_R5c2_pitch_imu_simulation.md`).
- Nhãn lấy từ roll thật nên pitch/nhiễu không đổi nhãn; AMPLITUDE_GROWTH Validation vẫn mỏng. Chưa có Test-G2.

SHA-256 dataset: `f3c893fcaa498fba9ebac62ffe9ab4a06632f50b0d97fd332547cf04fa15370c`.
