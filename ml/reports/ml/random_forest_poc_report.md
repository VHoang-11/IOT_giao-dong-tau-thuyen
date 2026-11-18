# Báo cáo Random Forest PoC `rf_proxy_phenotype_poc_v0.1.0`

> **Phạm vi bắt buộc.** Đây là *proof of concept phân loại motion phenotype dựa trên proxy label*, KHÔNG phải bộ phân loại an toàn hàng hải đã được xác thực. Proxy label được sinh bằng quy tắc tương đối trên chính tín hiệu; không có ground truth độc lập, không có nhãn hazard vận hành đã xác minh và không có quyết định human review nào được dùng.

## 1. Mục tiêu

Kiểm tra liệu một Random Forest trên 23 angle feature có tái tạo được proxy label `RELATIVE_HIGH_ROLL` ở các điều kiện thử nghiệm Hohai chưa thấy hay không, so với baseline tầm thường và baseline quy tắc xác định, và đo mức phụ thuộc vào feature định nghĩa proxy.

## 2. Phương pháp

- Target huấn luyện: RELATIVE_HIGH_ROLL (target khác NOT_TRAINABLE, xem báo cáo chất lượng). Dạng đa nhãn được triển khai *per-label* (một RF nhị phân cho mỗi target qua cổng); với chỉ một target qua cổng, macro F1 = F1 của target đó.
- Miền: Hohai, 9 nhóm điều kiện T. **Nested leave-one-group-out:** outer fold giữ 1 nhóm làm test; nhãn của fold dùng hiệu chuẩn fit trên 8 nhóm train; bên trong train, GroupKFold 4 nhóm (round-robin xác định) chọn siêu tham số theo PR-AUC gộp, rồi chọn ngưỡng xác suất tối đa F1 trên dự đoán out-of-fold *của train*.
- Cửa sổ ABSTAIN bị loại khỏi train và khỏi metric của target (được đếm riêng); không cửa sổ nào bị xóa khỏi dataset.
- Lưới siêu tham số: 8 cấu hình (max_depth ∈ {8, None}, min_samples_leaf ∈ {10, 1}, class_weight ∈ {None, balanced_subsample}), n_estimators = 200, max_features = sqrt, seed `20261117`. Class imbalance chỉ xử lý bằng `class_weight` nếu inner CV chọn; không oversampling/không nhãn tổng hợp.
- Không có preprocessing học được (RF không cần chuẩn hóa); không imputation; cửa sổ thiếu feature → ABSTAIN.
- Baseline: luôn NEG; quy tắc một feature với ngưỡng phân vị fit trên train (`roll_std_60` = chính proxy, `roll_rms_60` = RMS thô, `pitch_std_60` = chỉ Pitch).
- Ablation: `no_direct_alias` bỏ `roll_std_60`, `roll_rms_60`, `roll_rms_late_60` (bí danh: hiệu tuyệt đối lớn nhất giữa `roll_rms_60` và `roll_rms_late_60` trên Hohai = 0); `no_roll_amplitude` bỏ mọi feature biên độ/độ phân tán Roll.
- Khoảng tin cậy: bootstrap 2.000 lần trên **9 nhóm độc lập**, không trên cửa sổ chồng lấn.

### Feature huấn luyện (schema `060095dd1f6bf426…`, 23 feature theo thứ tự)

| # | Feature | # | Feature | # | Feature |
|---:|---|---:|---|---:|---|
| 0 | `roll_rms_60` | 1 | `roll_std_60` | 2 | `roll_mean_60` |
| 3 | `roll_peak_to_peak_60` | 4 | `roll_abs_p95_60` | 5 | `roll_abs_max_60` |
| 6 | `roll_iqr_60` | 7 | `roll_diff_rms_60` | 8 | `roll_mean_180` |
| 9 | `roll_median_180` | 10 | `roll_mean_abs_180` | 11 | `roll_dominant_sign_ratio_180` |
| 12 | `roll_segment_mean_std_180` | 13 | `roll_mean_shift_180` | 14 | `roll_rms_early_60` |
| 15 | `roll_rms_late_60` | 16 | `roll_rms_ratio_180` | 17 | `roll_rms_slope_180` |
| 18 | `roll_rms_trend_r2_180` | 19 | `roll_p95_trend_slope_180` | 20 | `pitch_rms_60` |
| 21 | `pitch_std_60` | 22 | `pitch_peak_to_peak_60` |  |  |

Không dùng gyro (Hohai không có; Seafar/Southampton mapping chưa xác minh) và không dùng 3 feature chu kỳ (ngoài tập angle-only 23).

## 3. Kết quả đo được (test = nhóm giữ lại, gộp 9 outer fold)

| Mô hình / baseline | Precision | Recall | F1 | PR-AUC | Khoảng F1 bootstrap theo nhóm (2.5–97.5%) |
|---|---:|---:|---:|---:|---|
| RF `full_23` (23 feature) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000–1.000 |
| RF `no_direct_alias` (20 feature) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000–1.000 |
| RF `no_roll_amplitude` (10 feature) | 0.843 | 0.541 | 0.659 | 0.681 | 0.579–0.784 |
| RF compact (25 cây, depth 6, khai báo trước) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000–1.000 |
| Baseline `majority` | không xác định | 0.000 | 0.000 | prevalence = 0.157 | — |
| Baseline `proxy_rule_roll_std_60` | 1.000 | 1.000 | 1.000 | — | 1.000–1.000 |
| Baseline `raw_rms_rule_roll_rms_60` | 1.000 | 0.990 | 0.995 | — | 0.989–1.000 |
| Baseline `pitch_only_rule_pitch_std_60` | 0.859 | 0.555 | 0.674 | — | 0.593–0.838 |

Support test gộp: 209 POS / 1118 NEG (prevalence 0.157).

### Ma trận nhầm lẫn và support theo nhóm độc lập

| Feature set | Nhóm | Session | POS | TP | FP | FN | TN |
|---|---|---:|---:|---:|---:|---:|---:|
| full_23 | hohai|T1 | 1 | 0 | 0 | 0 | 0 | 72 |
| full_23 | hohai|T2 | 1 | 0 | 0 | 0 | 0 | 72 |
| full_23 | hohai|T3 | 3 | 0 | 0 | 0 | 0 | 216 |
| full_23 | hohai|T4 | 1 | 0 | 0 | 0 | 0 | 72 |
| full_23 | hohai|T5 | 1 | 0 | 0 | 0 | 0 | 72 |
| full_23 | hohai|T6 | 3 | 0 | 0 | 0 | 0 | 211 |
| full_23 | hohai|T7 | 3 | 27 | 27 | 0 | 0 | 166 |
| full_23 | hohai|T8 | 5 | 136 | 136 | 0 | 0 | 113 |
| full_23 | hohai|T9 | 3 | 46 | 46 | 0 | 0 | 124 |
| no_direct_alias | hohai|T1 | 1 | 0 | 0 | 0 | 0 | 72 |
| no_direct_alias | hohai|T2 | 1 | 0 | 0 | 0 | 0 | 72 |
| no_direct_alias | hohai|T3 | 3 | 0 | 0 | 0 | 0 | 216 |
| no_direct_alias | hohai|T4 | 1 | 0 | 0 | 0 | 0 | 72 |
| no_direct_alias | hohai|T5 | 1 | 0 | 0 | 0 | 0 | 72 |
| no_direct_alias | hohai|T6 | 3 | 0 | 0 | 0 | 0 | 211 |
| no_direct_alias | hohai|T7 | 3 | 27 | 27 | 0 | 0 | 166 |
| no_direct_alias | hohai|T8 | 5 | 136 | 136 | 0 | 0 | 113 |
| no_direct_alias | hohai|T9 | 3 | 46 | 46 | 0 | 0 | 124 |
| no_roll_amplitude | hohai|T1 | 1 | 0 | 0 | 0 | 0 | 72 |
| no_roll_amplitude | hohai|T2 | 1 | 0 | 0 | 0 | 0 | 72 |
| no_roll_amplitude | hohai|T3 | 3 | 0 | 0 | 0 | 0 | 216 |
| no_roll_amplitude | hohai|T4 | 1 | 0 | 0 | 0 | 0 | 72 |
| no_roll_amplitude | hohai|T5 | 1 | 0 | 0 | 0 | 0 | 72 |
| no_roll_amplitude | hohai|T6 | 3 | 0 | 0 | 0 | 0 | 211 |
| no_roll_amplitude | hohai|T7 | 3 | 27 | 11 | 0 | 16 | 166 |
| no_roll_amplitude | hohai|T8 | 5 | 136 | 64 | 8 | 72 | 105 |
| no_roll_amplitude | hohai|T9 | 3 | 46 | 38 | 13 | 8 | 111 |

### Hành vi trên vùng ABSTAIN (không có nhãn, không vào metric)

| Feature set | Nhóm test | Cửa sổ ABSTAIN | RF dự đoán POS |
|---|---|---:|---:|
| full_23 | hohai|T6 | 5 | 0 |
| full_23 | hohai|T7 | 23 | 13 |
| full_23 | hohai|T8 | 111 | 39 |
| full_23 | hohai|T9 | 46 | 21 |
| no_direct_alias | hohai|T6 | 5 | 0 |
| no_direct_alias | hohai|T7 | 23 | 12 |
| no_direct_alias | hohai|T8 | 111 | 47 |
| no_direct_alias | hohai|T9 | 46 | 24 |
| no_roll_amplitude | hohai|T6 | 5 | 0 |
| no_roll_amplitude | hohai|T7 | 23 | 1 |
| no_roll_amplitude | hohai|T8 | 111 | 37 |
| no_roll_amplitude | hohai|T9 | 46 | 30 |

### Siêu tham số được chọn (chỉ dùng dữ liệu train)

| Feature set | Fold | Tham số | PR-AUC inner | Ngưỡng xác suất |
|---|---:|---|---:|---:|
| full_23 | 0 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.143 |
| full_23 | 1 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.143 |
| full_23 | 2 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.253 |
| full_23 | 3 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.759 |
| full_23 | 4 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.759 |
| full_23 | 5 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.271 |
| full_23 | 6 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.192 |
| full_23 | 7 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.476 |
| full_23 | 8 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.625 |
| no_direct_alias | 0 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.281 |
| no_direct_alias | 1 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.575 |
| no_direct_alias | 2 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.566 |
| no_direct_alias | 3 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.563 |
| no_direct_alias | 4 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.563 |
| no_direct_alias | 5 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.364 |
| no_direct_alias | 6 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.501 |
| no_direct_alias | 7 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.566 |
| no_direct_alias | 8 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 1.000 | 0.331 |
| no_roll_amplitude | 0 | `{"max_depth": null, "min_samples_leaf": 10, "class_weight": null}` | 0.437 | 0.355 |
| no_roll_amplitude | 1 | `{"max_depth": null, "min_samples_leaf": 10, "class_weight": null}` | 0.434 | 0.341 |
| no_roll_amplitude | 2 | `{"max_depth": null, "min_samples_leaf": 10, "class_weight": null}` | 0.368 | 0.241 |
| no_roll_amplitude | 3 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 0.443 | 0.352 |
| no_roll_amplitude | 4 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 0.447 | 0.341 |
| no_roll_amplitude | 5 | `{"max_depth": null, "min_samples_leaf": 10, "class_weight": null}` | 0.373 | 0.251 |
| no_roll_amplitude | 6 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 0.486 | 0.460 |
| no_roll_amplitude | 7 | `{"max_depth": null, "min_samples_leaf": 10, "class_weight": null}` | 0.674 | 0.627 |
| no_roll_amplitude | 8 | `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}` | 0.547 | 0.519 |

### Phân tích lỗi

- RF `full_23`: FP = 0, FN = 0. Không có lỗi nào trên cửa sổ POS/NEG giữ lại.
- RF `no_roll_amplitude`: lỗi tập trung ở hohai|T7 (FN 16, FP 0), hohai|T8 (FN 72, FP 8), hohai|T9 (FN 8, FP 13).

### Feature importance và giới hạn

- MDI (mô hình cuối, 9 nhóm): `roll_diff_rms_60` 0.192, `roll_rms_60` 0.188, `roll_rms_late_60` 0.142, `roll_std_60` 0.125, `roll_abs_p95_60` 0.108, `roll_iqr_60` 0.078.
- Permutation importance trên outer test fold có cả hai lớp: |giá trị| lớn nhất ≈ 7.4e-17. Lý do: nhiều feature biên độ gần như thay thế được nhau, hoán vị một feature không làm giảm PR-AUC. Điều này **không** có nghĩa feature vô dụng; importance không đáng tin khi feature cộng tuyến mạnh.

### Mô hình cuối cho CLI dự đoán (không có test riêng)

- Huấn luyện trên 1361 cửa sổ POS/NEG (152 POS) của 9 nhóm, 21 session; hiệu chuẩn `cal-5192d29f3b11` (T_pos = 0.4922°, T_neg = 0.4334°).
- Tham số chọn bằng GroupKFold: `{"max_depth": 8, "min_samples_leaf": 10, "class_weight": null}`, ngưỡng xác suất 0.769.
- Cây: 200 cây, 1150 nút, depth tối đa 5; SHA-256 model `eab2891044256ac2…`; schema `060095dd1f6bf426…`; model card `ml/reports/ml/rf_poc_model_card.json`.
- Tái lập: cùng seed cho cây giống hệt và cùng SHA-256 khi serialize; `predict_proba` với `n_jobs=-1` có thể lệch ~1e-16 do cộng song song, nên CLI đặt `n_jobs=1`.

## 4. Kiểm toán rò rỉ

- 9/9 outer fold: không chung nhóm/session/segment, 0 khoảng thời gian chồng lấn, 0 vector feature trùng giữa train và test: **True**.
- Ngưỡng proxy, siêu tham số và ngưỡng xác suất đều fit trên train của fold; nhóm test không tham gia.

## 5. Diễn giải khoa học

1. **F1 = 1 không phải thành tựu nhận diện.** Proxy là `roll_std_60 ≥ T_pos`; RF chỉ học lại ngưỡng đó. Baseline quy tắc `roll_std_60` cũng F1 = 1 theo cấu trúc.
2. **Ablation bỏ feature trực tiếp vẫn F1 = 1** vì `roll_diff_rms_60`, `roll_iqr_60`, `roll_abs_p95_60`… mang gần như cùng thông tin (Spearman với `roll_std_60` ≥ 0.92 trên Hohai). Ablation thành công cũng **không** tạo ra ground truth độc lập.
3. **Khi bỏ mọi feature biên độ Roll**, F1 giảm xuống 0.659, gần baseline chỉ Pitch (0.674): phần còn lại chủ yếu phản ánh *mức kích thích sóng chung* của điều kiện thử nghiệm.
4. **Việc loại vùng ABSTAIN làm bài toán dễ hơn:** POS và NEG cách nhau một dải phân vị 0.80–0.90; trong dải đó RF chia đôi tùy ý (bảng ở trên).
5. POS chỉ có ở 3/9 nhóm (T7–T9), nên recall đo trên 3 nhóm; 6 fold còn lại chỉ đo FP. Khoảng bootstrap hẹp vì mô hình khớp hoàn hảo, không phải vì dữ liệu nhiều.

## 6. Giới hạn

- Không có ground truth độc lập; mọi metric là **mức khớp với proxy label**, không phải độ chính xác phát hiện hazard.
- Một miền (Hohai model-scale), 9 nhóm, POS ở 3 nhóm; không có tuyên bố tổng quát hóa sang Seafar/Southampton hay tàu thật.
- `AMPLITUDE_GROWTH` và `PERSISTENT_OFFSET` không được huấn luyện (NOT_TRAINABLE).

## 7. Tái lập

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

Artifact model (gitignored): `ml/data/models/rf_poc_v1/` (`relative_high_roll_rf.joblib`, model card, `outer_fold_predictions.parquet`). Kết quả đầy đủ: `ml/reports/ml/rf_poc_results.json`.
- Môi trường: Python 3.14.10, scikit-learn 1.9.1, numpy 2.4.6, pandas 3.0.3; thời gian chạy 166.2 s.

## 8. Giải thích kỹ thuật phục vụ vấn đáp cá nhân

- **Có thể khẳng định:** pipeline nested group-held-out không rò rỉ đã chạy; RF tái tạo được quy tắc proxy tương đối trên điều kiện thử nghiệm Hohai chưa thấy; thông tin đến từ các feature biên độ Roll (ablation).
- **Không thể khẳng định:** mô hình phát hiện Roll nguy hiểm; mô hình dùng được cho tàu thật; F1 = 1 là độ chính xác vận hành.
- **Câu hỏi hay gặp — vì sao không chia ngẫu nhiên?** Cửa sổ chồng nhau 94%; split ngẫu nhiên đo trí nhớ, không đo tổng quát hóa.
- **Vì sao chọn ngưỡng xác suất trên train?** Nếu chọn trên test, test đã ảnh hưởng mô hình → metric lạc quan.
- **Bước tiếp theo đúng:** cần nhãn độc lập (human review nhiều người, nhật ký thí nghiệm/vận hành) trước khi so sánh RF với quy tắc một cách có ý nghĩa.
