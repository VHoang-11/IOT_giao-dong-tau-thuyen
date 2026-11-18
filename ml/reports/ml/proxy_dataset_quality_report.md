# Báo cáo chất lượng proxy dataset `proxy_rules_v1.0.0`

> **Phạm vi bắt buộc.** Đây là *proof of concept phân loại motion phenotype dựa trên proxy label*, KHÔNG phải bộ phân loại an toàn hàng hải đã được xác thực. Proxy label được sinh bằng quy tắc tương đối trên chính tín hiệu; không có ground truth độc lập, không có nhãn hazard vận hành đã xác minh và không có quyết định human review nào được dùng.

## 1. Mục tiêu

Đánh giá trước khi huấn luyện: độ phủ, phân phối nhãn proxy, chồng lấn đa nhãn, ABSTAIN, độ ổn định quy tắc, độ nhạy hiệu chuẩn và cổng training-readiness theo nhóm độc lập.

## 2. Phương pháp

- Dựng bảng đo cho mọi window endpoint của feature table (`python -m ml.labeling.proxy_dataset`).
- Nhãn **out-of-fold**: mỗi cửa sổ Hohai được gắn nhãn bằng hiệu chuẩn fit trên 8 điều kiện T *khác* điều kiện của nó; Seafar/Southampton không hiệu chuẩn được nên chỉ có quy tắc offset cấu trúc.
- Độ nhạy: lặp lại toàn bộ quy trình out-of-fold với các cặp phân vị trong spec.
- Cổng readiness (spec `readiness`): miền ≥ 3 nhóm độc lập; POS ở ≥ 3 nhóm và ≥ 5 session; NEG ở ≥ 3 nhóm; ≥ 20 cửa sổ POS. Lý do chọn: với leave-one-group-out, mỗi fold train phải còn POS từ ≥ 2 nhóm khác nhau, nếu không mô hình chỉ học một điều kiện thí nghiệm.

## 3. Kiểm kê thực tế (tính lại từ artifact)

| Chỉ số | Giá trị đo | Trạng thái báo cáo trước |
|---|---:|---|
| Window endpoint trong feature table | 3425 | — |
| Cửa sổ đủ 23 angle feature | 2864 | 2.864 (khớp) |
| Session có cửa sổ đủ 23 feature | 23 | 23 (khớp) |
| Nhóm độc lập (sau khi gộp Hohai theo điều kiện T) | 11 | chưa từng báo cáo |

### Bằng chứng chọn khóa nhóm Hohai

Tên sheet Hohai = bến × điều kiện thử nghiệm `Tn` × cấu hình dây neo (theo `Data Description Example.pdf`). Tương quan chéo cực đại |ρ| của Roll (lag ±30 s) giữa các cặp session:

| Cặp session | Số cặp | Trung vị | Min | Max |
|---|---:|---:|---:|---:|
| Cùng điều kiện T | 22 | 0.354 | 0.114 | 0.612 |
| Cùng T, khác bến | 13 | 0.227 | 0.114 | 0.406 |
| Khác điều kiện T | 188 | 0.125 | 0.046 | 0.659 |

Session cùng điều kiện T có chung chuỗi sóng tới nên không độc lập; split theo session sẽ rò rỉ. Một số cặp khác T vẫn có |ρ| cao (max ở trên) nên T là khóa *mạnh hơn* session nhưng chưa chắc là đủ; đây là giới hạn còn lại.

## 4. Phân phối proxy label (out-of-fold)

| Nguồn | Cửa sổ | Đủ 23 feature | PHENOTYPE_PROXY | NO_PROXY_TRIGGERED | ABSTAIN | Đa nhãn |
|---|---:|---:|---:|---:|---:|---:|
| hohai | 1764 | 1512 | 209 | 592 | 963 | 8 |
| seafar | 1384 | 1318 | 1246 | 0 | 138 | 0 |
| southampton | 277 | 34 | 16 | 0 | 261 | 0 |

| Nguồn | Target | POS | NEG | ABSTAIN | Nhóm có POS | Session có POS | Quyết định | Lý do chặn |
|---|---|---:|---:|---:|---:|---:|---|---|
| hohai | RELATIVE_HIGH_ROLL | 209 | 1118 | 437 | 3 | 9 | **TRAINABLE** | — |
| hohai | PERSISTENT_OFFSET | 0 | 839 | 925 | 0 | 0 | **NOT_TRAINABLE** | POSITIVE_GROUPS_0<3, POSITIVE_SESSIONS_0<5, POSITIVE_WINDOWS_0<20 |
| hohai | AMPLITUDE_GROWTH | 8 | 1360 | 396 | 3 | 3 | **NOT_TRAINABLE** | POSITIVE_SESSIONS_3<5, POSITIVE_WINDOWS_8<20 |
| seafar | RELATIVE_HIGH_ROLL | 0 | 0 | 1384 | 0 | 0 | **NOT_TRAINABLE** | DOMAIN_HAS_1_INDEPENDENT_GROUP(S), POSITIVE_GROUPS_0<3, NEGATIVE_GROUPS_0<3, POSITIVE_SESSIONS_0<5, POSITIVE_WINDOWS_0<20 |
| seafar | PERSISTENT_OFFSET | 1246 | 0 | 138 | 1 | 1 | **NOT_TRAINABLE** | DOMAIN_HAS_1_INDEPENDENT_GROUP(S), POSITIVE_GROUPS_1<3, NEGATIVE_GROUPS_0<3, POSITIVE_SESSIONS_1<5 |
| seafar | AMPLITUDE_GROWTH | 0 | 0 | 1384 | 0 | 0 | **NOT_TRAINABLE** | DOMAIN_HAS_1_INDEPENDENT_GROUP(S), POSITIVE_GROUPS_0<3, NEGATIVE_GROUPS_0<3, POSITIVE_SESSIONS_0<5, POSITIVE_WINDOWS_0<20 |
| southampton | RELATIVE_HIGH_ROLL | 0 | 0 | 277 | 0 | 0 | **NOT_TRAINABLE** | DOMAIN_HAS_1_INDEPENDENT_GROUP(S), POSITIVE_GROUPS_0<3, NEGATIVE_GROUPS_0<3, POSITIVE_SESSIONS_0<5, POSITIVE_WINDOWS_0<20 |
| southampton | PERSISTENT_OFFSET | 16 | 0 | 261 | 1 | 1 | **NOT_TRAINABLE** | DOMAIN_HAS_1_INDEPENDENT_GROUP(S), POSITIVE_GROUPS_1<3, NEGATIVE_GROUPS_0<3, POSITIVE_SESSIONS_1<5, POSITIVE_WINDOWS_16<20 |
| southampton | AMPLITUDE_GROWTH | 0 | 0 | 277 | 0 | 0 | **NOT_TRAINABLE** | DOMAIN_HAS_1_INDEPENDENT_GROUP(S), POSITIVE_GROUPS_0<3, NEGATIVE_GROUPS_0<3, POSITIVE_SESSIONS_0<5, POSITIVE_WINDOWS_0<20 |

### Tổ hợp phenotype (chồng lấn đa nhãn)

- **hohai:** `[]` = 1555; `["RELATIVE_HIGH_ROLL"]` = 201; `["RELATIVE_HIGH_ROLL", "AMPLITUDE_GROWTH"]` = 8
- **seafar:** `["PERSISTENT_OFFSET"]` = 1246; `[]` = 138
- **southampton:** `[]` = 261; `["PERSISTENT_OFFSET"]` = 16

### Lý do ABSTAIN/NEG/POS theo target (Hohai)

- **RELATIVE_HIGH_ROLL:** `S60_BELOW_TRAIN_LOWER_QUANTILE` = 1118; `INCOMPLETE_ANGLE_FEATURES` = 252; `S60_AT_OR_ABOVE_TRAIN_UPPER_QUANTILE` = 209; `BOUNDARY_BAND` = 185
- **PERSISTENT_OFFSET:** `SUB_BLOCK_MEAN_SIGN_NOT_PERSISTENT` = 839; `SIGNED_BIAS_BUT_OSCILLATION_CROSSES_DATUM` = 673; `INCOMPLETE_ANGLE_FEATURES` = 252
- **AMPLITUDE_GROWTH:** `CENTERED_RATIO_BELOW_TRAIN_LOWER_QUANTILE` = 1360; `INCOMPLETE_ANGLE_FEATURES` = 252; `BOUNDARY_BAND` = 73; `HIGH_RATIO_NO_CAUSAL_CONTEXT` = 42; `HIGH_RATIO_NOT_ABOVE_RECENT_HISTORY` = 21; `HIGH_RATIO_MONOTONIC_AND_ABOVE_HISTORY` = 8; `HIGH_RATIO_NOT_MONOTONIC` = 8

### Độ phủ theo nhóm độc lập Hohai

| Nhóm | Cửa sổ | RELATIVE_HIGH_ROLL (POS/NEG/ABSTAIN) | AMPLITUDE_GROWTH (POS/NEG/ABSTAIN) |
|---|---:|---|---|
| hohai|T1 | 84 | 0/72/12 | 0/68/16 |
| hohai|T2 | 84 | 0/72/12 | 0/64/20 |
| hohai|T3 | 252 | 0/216/36 | 0/201/51 |
| hohai|T4 | 84 | 0/72/12 | 0/67/17 |
| hohai|T5 | 84 | 0/72/12 | 0/60/24 |
| hohai|T6 | 252 | 0/211/41 | 0/195/57 |
| hohai|T7 | 252 | 27/166/59 | 3/201/48 |
| hohai|T8 | 420 | 136/113/171 | 3/325/92 |
| hohai|T9 | 252 | 46/124/82 | 2/179/71 |

Cột cửa sổ gồm cả cửa sổ thiếu feature (ABSTAIN `INCOMPLETE_ANGLE_FEATURES`).

## 5. Support theo split (outer fold, target TRAINABLE)

| Fold | Nhóm test | Train POS/tổng | Nhóm train có POS | Test POS/tổng | Test ABSTAIN |
|---:|---|---:|---:|---:|---:|
| 0 | hohai|T1 | 145/1296 | 3 | 0/72 | 0 |
| 1 | hohai|T2 | 145/1296 | 3 | 0/72 | 0 |
| 2 | hohai|T3 | 130/1166 | 3 | 0/216 | 0 |
| 3 | hohai|T4 | 145/1296 | 3 | 0/72 | 0 |
| 4 | hohai|T5 | 145/1296 | 3 | 0/72 | 0 |
| 5 | hohai|T6 | 130/1166 | 3 | 0/211 | 5 |
| 6 | hohai|T7 | 130/1166 | 2 | 27/193 | 23 |
| 7 | hohai|T8 | 116/1037 | 3 | 136/249 | 111 |
| 8 | hohai|T9 | 130/1166 | 2 | 46/170 | 46 |

## 6. Độ ổn định quy tắc và độ nhạy hiệu chuẩn

| Target | Ngưỡng | Min qua 9 fold | Trung vị | Max |
|---|---|---:|---:|---:|
| RELATIVE_HIGH_ROLL | positive_threshold | 0.4478 | 0.4956 | 0.5028 |
| RELATIVE_HIGH_ROLL | negative_threshold | 0.3896 | 0.4380 | 0.4456 |
| AMPLITUDE_GROWTH | positive_threshold | 0.4485 | 0.4592 | 0.4663 |
| AMPLITUDE_GROWTH | negative_threshold | 0.3637 | 0.3803 | 0.3840 |

| Target | (q_pos, q_neg) | POS | NEG | ABSTAIN | Nhóm có POS | Session có POS | Jaccard tập POS so với mặc định |
|---|---|---:|---:|---:|---:|---:|---:|
| RELATIVE_HIGH_ROLL | (0.8, 0.7) | 394 | 989 | 381 | 4 | 10 | 0.53 |
| RELATIVE_HIGH_ROLL | (0.85, 0.75) | 308 | 1039 | 417 | 3 | 9 | 0.68 |
| RELATIVE_HIGH_ROLL | (0.9, 0.8) | 209 | 1118 | 437 | 3 | 9 | 1.00 |
| RELATIVE_HIGH_ROLL | (0.95, 0.9) | 112 | 1303 | 349 | 3 | 8 | 0.54 |
| AMPLITUDE_GROWTH | (0.9, 0.8) | 11 | 1206 | 547 | 4 | 4 | 0.73 |
| AMPLITUDE_GROWTH | (0.95, 0.9) | 8 | 1360 | 396 | 3 | 3 | 1.00 |
| AMPLITUDE_GROWTH | (0.975, 0.95) | 3 | 1433 | 328 | 2 | 2 | 0.38 |

## 7. Kiểm tra giả định và trường hợp mơ hồ

| Nguồn | Lag-1 biên độ nửa chu kỳ (trung vị) | Tỷ lệ cửa sổ lag-1 > 0.5 | |mean|/std trung vị | Cửa sổ có tỷ lệ σ centered > 1.5× tỷ lệ RMS thô |
|---|---:|---:|---:|---:|
| hohai | 0.76 | 94.7% | 0.08 | 0 |
| seafar | -0.09 | 1.7% | 27.58 | 291 |
| southampton | -0.11 | 20.6% | 27.72 | 9 |

- Vùng biên `RELATIVE_HIGH_ROLL`: 185 cửa sổ Hohai bị ABSTAIN.
- `AMPLITUDE_GROWTH` có tỷ lệ cao nhưng thiếu tính nhất quán thời gian: không đơn điệu 8, không vượt lịch sử gần 21, thiếu bối cảnh 42 cửa sổ.
- `PERSISTENT_OFFSET` Hohai: 673 cửa sổ có mean cùng dấu nhưng dao động cắt mốc 0 (ABSTAIN).
- Cửa sổ POS sát cuối segment (cờ kiểm toán): hohai {'RELATIVE_HIGH_ROLL': 3, 'PERSISTENT_OFFSET': 0, 'AMPLITUDE_GROWTH': 0}; seafar {'RELATIVE_HIGH_ROLL': 0, 'PERSISTENT_OFFSET': 4, 'AMPLITUDE_GROWTH': 0}; southampton {'RELATIVE_HIGH_ROLL': 0, 'PERSISTENT_OFFSET': 1, 'AMPLITUDE_GROWTH': 0}.
- Không cửa sổ khó nào bị xóa; mọi cửa sổ đều có trạng thái và lý do.

## 8. Quyết định training-readiness

- **TRAINABLE:** chỉ `RELATIVE_HIGH_ROLL` trong miền Hohai (vừa đủ mức tối thiểu 3 nhóm có POS: T7, T8, T9).
- **NOT_TRAINABLE:** `AMPLITUDE_GROWTH` (quá ít POS và session), `PERSISTENT_OFFSET` (Hohai không có POS; Seafar/Southampton không có NEG và chỉ một nhóm), mọi target ở Seafar và Southampton (một nhóm độc lập, không thể đánh giá giữ-nhóm).
- Không tạo nhãn giả để cân bằng lớp; không gộp nguồn để tăng support.

## 9. Giới hạn

- Proxy label phụ thuộc phân vị được chọn; độ nhạy ở mục 6 cho thấy tập POS thay đổi đáng kể khi đổi phân vị.
- Chỉ 9 nhóm độc lập Hohai và POS tập trung ở 3 nhóm có kích thích mạnh nhất.
- Dữ liệu Hohai là mô hình thu nhỏ, thời gian suy từ 50 Hz, không gyro; mốc 0 cảm biến ở mọi nguồn chưa xác minh.

## 10. Tái lập

```bash
source .venv/bin/activate
python -m pip install -r ml/train/requirements.txt
python -m ml.labeling.proxy_dataset --spec ml/labeling/proxy_spec.yaml
python -m ml.train.rf_poc --config ml/train/rf_poc_config.yaml
python -m ml.train.esp32_feasibility
python -m ml.train.reports
python -m ml.train.predict --model-card ml/data/models/rf_poc_v1/relative_high_roll_model_card.json \
    --input ml/data/labels/proxy_v1/measurements.parquet --output ml/data/models/rf_poc_v1/predict_cli_demo.csv
python -m pytest ml/labeling/tests ml/features/tests ml/preprocessing/tests ml/audit ml/train/tests -q
for nb in 17_proxy_label_design 18_proxy_label_distribution 19_rf_grouped_evaluation 20_rf_deployment_feasibility; do
  python -m nbconvert --to notebook --execute --inplace ml/notebooks/$nb.ipynb
done
```

Dùng `python -m nbconvert` của `.venv` (không phải `python -m jupyter nbconvert` khi venv chưa activate): lệnh `jupyter` tìm
`jupyter-nbconvert` trên `PATH` và có thể chạy kernel của một Python khác. Cell đầu của mỗi notebook in interpreter và phiên bản scikit-learn đã dùng.

Output lớn (gitignored): `ml/data/labels/proxy_v1/` gồm `measurements.parquet`, `proxy_labels_oof.parquet`, `proxy_labels_by_fold.parquet`, `proxy_labels_final_calibration.parquet`, `calibrations.json`, `hohai_session_xcorr.csv`. Tóm tắt nhỏ được theo dõi: `ml/reports/ml/proxy_dataset_summary.json`.
- Checksum human-review ledger/verified/AI không đổi sau khi chạy: **True**.

## 11. Diễn giải khoa học

Proxy dataset đủ để *thử nghiệm kỹ thuật* một target tương đối trong một miền mô hình thu nhỏ. Nó không đủ để huấn luyện bốn lớp, không đủ cho offset hay growth, và không cho phép bất kỳ tuyên bố tổng quát hóa liên session ở Seafar/Southampton.

## 12. Giải thích kỹ thuật phục vụ vấn đáp cá nhân

- **Vì sao không chia ngẫu nhiên theo cửa sổ?** Cửa sổ 180 s bước 10 s chồng nhau ~94%; chia ngẫu nhiên đưa gần như cùng một đoạn tín hiệu vào cả train và test.
- **Vì sao nhóm theo T chứ không theo session?** Số liệu tương quan chéo ở mục 3: session cùng T có chung sóng tới.
- **Vì sao chỉ một target được huấn luyện?** Cổng readiness đòi POS ở ≥ 3 nhóm độc lập; growth chỉ có 8 cửa sổ POS ở 3 session, offset Hohai không có POS.
- **Nhãn out-of-fold là gì?** Ngưỡng dùng để gắn nhãn một cửa sổ không bao giờ được học từ nhóm chứa cửa sổ đó.
