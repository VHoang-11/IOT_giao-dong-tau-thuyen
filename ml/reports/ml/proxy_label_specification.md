# Đặc tả proxy label `proxy_rules_v1.0.0`

> **Phạm vi bắt buộc.** Đây là *proof of concept phân loại motion phenotype dựa trên proxy label*, KHÔNG phải bộ phân loại an toàn hàng hải đã được xác thực. Proxy label được sinh bằng quy tắc tương đối trên chính tín hiệu; không có ground truth độc lập, không có nhãn hazard vận hành đã xác minh và không có quyết định human review nào được dùng.

## 1. Mục tiêu

Chuyển bài toán từ "phân loại trạng thái nguy hiểm" (không có ground truth) sang **phân loại motion phenotype dựa trên proxy**:
mỗi cửa sổ 180 s được gắn trạng thái POS/NEG/ABSTAIN cho từng phenotype quan sát được bằng một quy tắc tái lập, có phiên bản,
có hiệu chuẩn chỉ trên dữ liệu train. Đặc tả máy đọc được: `ml/labeling/proxy_spec.yaml` (SHA-256 `07086545f7724b79…`).

## 2. Bốn khái niệm không được đánh đồng

| Khái niệm | Ai/cái gì tạo ra | Ý nghĩa | Trạng thái trong dự án |
|---|---|---|---|
| Observed motion phenotype | Hình thái tín hiệu Roll/Pitch | "Tín hiệu trông như thế nào" (dao động mạnh tương đối, lệch một phía, biên độ tăng) | Mô tả, chưa phải nhãn |
| Proxy rule label | Quy tắc `proxy_rules_v1.0.0` + hiệu chuẩn | Nhãn tự động, tái lập, có thể sai so với thực tế vật lý | **Được dùng trong PoC này** |
| Human-reviewed observation | Người đánh giá ghi vào ledger có audit | Người xác nhận phenotype quan sát được | 0 quyết định; không dùng |
| Verified operational hazard | Nguồn độc lập (nhật ký vận hành, envelope đã duyệt) | Trạng thái nguy hiểm thật | 0 nhãn; không thể huấn luyện |

## 3. Công thức bài toán

- Target đa nhãn: `RELATIVE_HIGH_ROLL`, `PERSISTENT_OFFSET`, `AMPLITUDE_GROWTH`; mỗi target ∈ {POS, NEG, ABSTAIN}.
- Trạng thái cửa sổ: `PHENOTYPE_PROXY` (≥ 1 target POS, giữ mọi target POS), `NO_PROXY_TRIGGERED` (cả ba NEG),
  `ABSTAIN` (không target nào POS và ít nhất một target ABSTAIN).
- `NO_PROXY_TRIGGERED` **không** có nghĩa NORMAL hay SAFE: nó chỉ nói không quy tắc proxy nào kích hoạt.
- Không ép phenotype chồng lấn về một lớp loại trừ; cột `proxy_phenotypes` giữ danh sách, `multi_label` đánh dấu chồng lấn.

## 4. Quy ước chung

| Mục | Quy ước |
|---|---|
| Kênh tín hiệu | `roll_deg` từ `ml/data/processed/*/*/*/timeseries.parquet` (10 Hz); Pitch chỉ dùng làm feature RF, không định nghĩa proxy |
| Cửa sổ | `(t-180, t]` cùng session/segment, ≥ 95% mẫu, không gap > 1.5 chu kỳ; block 3×60 s và sub-block 9×20 s |
| Lịch sử nhân quả | `(t-360, t-180]` cùng segment (bối cảnh); không dùng mẫu sau `t` |
| Miền hiệu chuẩn | Mỗi nguồn riêng; không gộp model-scale và full-scale. Chỉ Hohai có ≥ 3 nhóm độc lập nên chỉ Hohai được hiệu chuẩn |
| Nhóm độc lập | Hohai: điều kiện thử nghiệm `Tn` (9 nhóm); Seafar/Southampton: session/run (1 nhóm mỗi nguồn) |
| Hiệu chuẩn | Phân vị có trọng số đều theo session, quy ước inverted-CDF, chỉ trên cửa sổ hợp lệ của các nhóm train |
| Cửa sổ không hợp lệ | Thiếu một trong 23 angle feature hoặc thống kê không tính được → ABSTAIN có lý do, không bị xóa |
| Cờ kiểm toán | `near_segment_end_audit` (còn < 10 s đến cuối segment) chỉ dùng phân tích offline, không vào quy tắc |

## 5. Quy tắc `RELATIVE_HIGH_ROLL`

- **Động cơ khoa học:** đo độ mạnh dao động *tương đối* trong một miền thí nghiệm, tách khỏi offset tĩnh.
- **Kênh/cửa sổ:** Roll, 60 s cuối của cửa sổ.
- **Tham chiếu:** phân phối `roll_std_60` của các cửa sổ train cùng miền (Hohai).
- **Phương trình:** `s60 = sqrt(Σ(x_i - x̄)² / n)` trên `(t-60, t]` (trùng feature `roll_std_60`).
- **Hiệu chuẩn:** `T_pos = Q_0.90(s60 | train)`, `T_neg = Q_0.80(s60 | train)`, trọng số đều theo session.
- **Quyết định:** POS nếu `s60 ≥ T_pos`; NEG nếu `s60 < T_neg`; ABSTAIN (`BOUNDARY_BAND`) nếu ở giữa.
- **Ngưỡng đo được qua 9 outer fold (Hohai):** `T_pos` ∈ [0.448, 0.503]°,
  `T_neg` ∈ [0.390, 0.446]°. Đây là **ngưỡng tương đối thực nghiệm của mô hình
  thu nhỏ**, không phải giới hạn Roll vật lý hay an toàn.
- **Điều kiện hợp lệ:** miền đã hiệu chuẩn; `roll_std_60` VALID. Seafar/Southampton → ABSTAIN (`SINGLE_SESSION…`/`SINGLE_RUN…`).
- **Lỗi đã biết:** phụ thuộc mạnh vào điều kiện sóng (nhóm T7–T9 chứa toàn bộ POS) nên thực chất phân biệt *mức kích thích* của thí nghiệm;
  vòng lặp hoàn toàn với feature `roll_std_60` và các feature biên độ tương quan.

## 6. Quy tắc `PERSISTENT_OFFSET` (offset so với mốc 0 cảm biến)

- **Động cơ:** phát hiện Roll đo được nằm lệch một phía kéo dài. Vì mốc 0/mounting và quy ước dấu chưa được xác minh ở cả ba nguồn,
  proxy này được định nghĩa **tương đối với mốc 0 cảm biến** (`offset_reference = SENSOR_DATUM_UNVERIFIED`, `physical_heel_claim = false`).
  Nó không bao giờ khẳng định đó là góc nghiêng (heel/list) thật của tàu.
- **Kênh/cửa sổ:** Roll 180 s + bối cảnh 180 s trước đó.
- **Phương trình/tiêu chí cấu trúc (không ngưỡng biên độ):**
  POS nếu mọi mẫu cửa sổ cùng dấu (`dominant_sign_ratio = 1`), 9/9 mean sub-block 20 s cùng dấu **và** mọi mẫu bối cảnh cùng dấu;
  NEG nếu mean sub-block đổi dấu ít nhất một lần; ABSTAIN nếu cùng dấu nhưng dao động cắt mốc 0, hoặc thiếu bối cảnh đầy đủ.
- **Hiệu chuẩn:** không có.
- **Lỗi đã biết:** sai lệch lắp đặt cảm biến tạo POS giả; tàu có list thật nhưng dao động lớn hơn offset sẽ thành ABSTAIN.

## 7. Quy tắc `AMPLITUDE_GROWTH`

- **Động cơ:** biên độ dao động tăng theo thời gian. Phát hiện trước đó: RMS thô bị offset che (`roll_rms_ratio_180` ≈ 1 dù dao động tăng nhiều lần),
  nên quy tắc dùng **độ lệch chuẩn quanh mean** (centered).
- **Kênh/cửa sổ:** Roll, ba block 60 s trong cửa sổ, chín sub-block 20 s trong bối cảnh.
- **Phương trình:** `g = ln(σ_late60 / σ_early60)` với σ là std quần thể quanh mean của block.
- **Hiệu chuẩn:** `T_pos = Q_0.95(g | train)`, `T_neg = Q_0.90(g | train)`; qua 9 fold `T_pos` ∈ [0.449, 0.466]
  (tức tỷ lệ ≈ 1.58×).
- **Quyết định:** NEG nếu `g < T_neg`; ABSTAIN nếu ở vùng biên; với `g ≥ T_pos` chỉ POS khi **đồng thời** σ ba block tăng đơn điệu,
  bối cảnh đủ ≥ 95% và σ block cuối lớn hơn mọi σ sub-block 20 s của bối cảnh; ngược lại ABSTAIN
  (`HIGH_RATIO_NOT_MONOTONIC`, `HIGH_RATIO_NOT_ABOVE_RECENT_HISTORY`, `HIGH_RATIO_NO_CAUSAL_CONTEXT`).
- **Vì sao không dùng p-value Mann–Kendall để quyết định:** kiểm định giả định các quan sát độc lập; biên độ nửa chu kỳ Hohai có tự tương quan
  lag-1 trung vị 0.76 (94.7% cửa sổ > 0.5),
  tức nhóm sóng làm giả định độc lập bị vi phạm. S Mann–Kendall chỉ được lưu như số đo mô tả.
- **Lỗi đã biết:** nhóm sóng tạm thời, cuối run, nhiễu khi σ_early rất nhỏ (ở mức nhiễu cảm biến).

## 8. Đo lường so với giả định

| Đã đo trên dữ liệu | Giả định/quy ước thực nghiệm |
|---|---|
| Ngưỡng từng fold, số POS/NEG/ABSTAIN, tương quan chéo giữa session | Chọn phân vị 0.90/0.80 và 0.95/0.90 (có nghiên cứu độ nhạy) |
| Tự tương quan biên độ, mức RMS bị offset che | Điều kiện T là khóa nhóm đủ mạnh (có bằng chứng tương quan, chưa có tài liệu thí nghiệm đầy đủ) |
| Kiểm tra quy tắc chỉ dùng mẫu ≤ t (test) | Mốc 0 cảm biến không phản ánh heel thật |

## 9. Tái lập

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

## 10. Giải thích kỹ thuật phục vụ vấn đáp cá nhân

- **Vì sao gọi là "relative"?** Ngưỡng là phân vị của chính dữ liệu train Hohai. Nếu đổi miền (tàu thật, mô hình khác), ngưỡng mất ý nghĩa;
  vì vậy Seafar/Southampton được ABSTAIN thay vì mượn ngưỡng Hohai.
- **Vì sao có ABSTAIN?** Gần ngưỡng, một thay đổi nhỏ của phân vị đổi nhãn; tách vùng biên ra giúp nhãn POS/NEG ổn định hơn.
  Cái giá: đánh giá trên POS/NEG trở nên dễ hơn thực tế (xem báo cáo RF).
- **Vì sao không gọi offset là nghiêng tàu?** Không nguồn nào có hiệu chuẩn mốc 0/mounting; sensor bias và heel cho cùng một tín hiệu.
- **Vì sao không dùng RMS ratio cho growth?** Với offset lớn (Seafar |mean|/std trung vị 27.6),
  RMS gần như bằng |mean|; có 291 cửa sổ Seafar mà tỷ lệ σ centered vượt tỷ lệ RMS thô ≥ 1.5 lần.
