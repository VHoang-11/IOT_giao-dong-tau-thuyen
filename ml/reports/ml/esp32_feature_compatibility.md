# Tương thích feature 23 và khả thi ESP32

> **Phạm vi bắt buộc.** Đây là *proof of concept phân loại motion phenotype dựa trên proxy label*, KHÔNG phải bộ phân loại an toàn hàng hải đã được xác thực. Proxy label được sinh bằng quy tắc tương đối trên chính tín hiệu; không có ground truth độc lập, không có nhãn hazard vận hành đã xác minh và không có quyết định human review nào được dùng.

## 1. Mục tiêu

Theo quyết định thiết kế của nhóm M2, 23 angle feature là schema đầu vào chính của RF. Báo cáo này đưa ra đề xuất contract có phiên bản cho M1, ước lượng tài nguyên ESP32, chỉ ra khác biệt giữa Roll/Pitch của dataset và của ESP32, và lập kế hoạch parity Python/C. Không sửa contract C, firmware hay cấu hình phần cứng hiện có.

## 2. Đề xuất contract `svmg-angle23` v0.1.0

- Máy đọc được: `ml/docs/feature_contract_23_v0.1.json`; bảng người đọc: `ml/docs/feature_contract_23_proposal.md`.
- Giữ nguyên tên, công thức, đơn vị, thứ tự và ngữ nghĩa cửa sổ của `ml/features/extractor.py` (extractor 0.1.0). Không đơn giản hóa công thức.
- 10 Hz, endpoint `(t-W, t]`, cập nhật mỗi 10 s, cửa sổ 60/180 s, ≥ 95% mẫu hợp lệ, gap > 1.5 chu kỳ → feature không hợp lệ (không thay bằng 0).
- Contract cũ 14 trường (`contracts/features.md`, `core/include/svmg_core.h`) và vector 10 trường của `svmg_features.h` **không bị chỉnh sửa**.
- Không tạo `ml/export/model.h`: firmware tự `#include` file này nếu tồn tại (`firmware/src/infer.cpp`) và giả định 4 lớp loại trừ NORMAL…AMPLITUDE_GROWTH, không tương thích với PoC đa nhãn/proxy hiện tại. Cần thống nhất interface với M1 trước.

## 3. So sánh chuỗi hiện tại của firmware với chuỗi dataset

| Hạng mục | Firmware hiện tại (đã đọc mã) | Dataset/feature 23 | Hệ quả |
|---|---|---|---|
| Tần số đầu vào/đầu ra | 20 Hz → 2 Hz | 10 Hz | Cần chuỗi 10 Hz riêng cho feature |
| Lọc | Butterworth bậc 2, 0.5 Hz + bộ lọc bù τ = 7.5 s | Butterworth nhân quả bậc 4, 4 Hz (Hohai/Southampton), Seafar không lọc | Biên độ khác nhau |
| Cửa sổ | 120/360 mẫu 2 Hz | 600/1.800 mẫu 10 Hz | Định nghĩa feature phụ thuộc số mẫu |
| Feature | 10 trường riêng (`svmg_features.h`) | 23 angle feature | Không có tập con trùng định nghĩa |
| Đơn vị `roll_diff_rms_60` | — | deg/mẫu ở 10 Hz | Phải tính đúng ở 10 Hz |
| Nguồn | `core/include/svmg_filter.h, core/src/filter.c, core/include/svmg_features.h` | `ml/features/extractor.py` | |

### Thí nghiệm mô phỏng chuỗi lọc hiện tại trên Hohai (đã chạy)

Áp Butterworth bậc 2, 0.5 Hz rồi lấy 2 Hz trên Roll Hohai đã xử lý, tính lại std 60 s (120 mẫu) ở 1512 cửa sổ:

| Chỉ số | Giá trị |
|---|---:|
| Tỷ lệ std (chuỗi firmware / 10 Hz), trung vị | 0.666 |
| Tỷ lệ std, P05–P95 | 0.631–0.728 |
| Quyết định proxy RELATIVE_HIGH_ROLL thay đổi | 299 / 1512 |
| POS gốc không còn POS | 148 |
| Quyết định gốc | {'NEG': 1209, 'POS': 152, 'ABSTAIN': 151} |
| Quyết định sau chuỗi firmware | {'NEG': 1502, 'ABSTAIN': 6, 'POS': 4} |

Độ khuếch đại lý thuyết của Butterworth bậc 2 fc = 0.5 Hz: hohai_dominant_roll_hz_approx → 0.629, southampton_test_plan_wave_hz → 0.366, southampton_late_window_roll_hz_approx → 0.122. Đầu ra 2 Hz có Nyquist 1.0 Hz. *Xấp xỉ:* Lọc 0.5 Hz trên chuỗi 10 Hz rồi lấy mỗi mẫu thứ 5; không mô phỏng bộ lọc bù/gia tốc kế.

### Thí nghiệm lệch miền với đủ 23 feature và mô hình cuối (đã chạy)

Trích lại 23 feature bằng `ml/features/extractor.py` trên Roll/Pitch Hohai đã lọc Butterworth bậc 2, 0.5 Hz (giữ 10 Hz), rồi dự đoán bằng mô hình cuối:

| Dự đoán RF | Tín hiệu gốc 10 Hz | Sau lọc 0.5 Hz |
|---|---:|---:|
| POS | 188 | 4 |
| NEG | 1324 | 1003 |
| ABSTAIN | 0 | 505 |

Lý do ABSTAIN sau lọc: {'FEATURE_OUTSIDE_TRAINING_RANGE': 505}; tỷ lệ `roll_std_60` lọc/gốc trung vị 0.666. *Xấp xỉ:* Butterworth bậc 2 fc=0.5 Hz nhân quả trên chuỗi 10 Hz đã xử lý; extractor 0.1.0; không giảm mẫu, không mô phỏng gia tốc kế.

## 4. ESP32 ước lượng Roll/Pitch như thế nào

Theo `core/include/svmg_filter.h`: MPU6050 (±2 g, ±250 °/s) → SI; `roll = atan2(ay, az)`, `pitch = atan2(-ax, sqrt(ay² + az²))` từ gia tốc kế; bộ lọc bù trộn tích phân gyro với góc gia tốc (α = τ/(τ+dt), τ = 7.5 s), cổng gia tốc [0.5 g, 1.5 g]; sau đó lọc 0.5 Hz và giảm mẫu 20 → 2 Hz; hiệu chuẩn zero (`svmg_calib.h`) trừ mean 30 s khi tĩnh.

### Khác biệt với Roll/Pitch của dataset

| Nguồn | Cách có Roll | Ghi chú |
|---|---|---|
| Hohai | Hệ đo chuyển động 6-DOF của thí nghiệm mô hình neo (không có gyro/timestamp) | Mô hình thu nhỏ, chu kỳ Roll ~1.8 s |
| Seafar | Trường Roll của IMU tàu (thuật toán fusion không rõ) | Lượng tử 0.01°, offset ~3°; trục/dấu tin cậy thấp |
| Southampton | Cột Roll của IMU mô hình KCS | Có gia tốc kế, Delta Angle chưa map |
| ESP32 | Bộ lọc bù MPU6050 + lọc 0.5 Hz + 2 Hz | Gia tốc ngang khi lắc làm sai góc từ gia tốc; mốc 0 do hiệu chuẩn tĩnh |

Kiểm tra thực tế trên Southampton Run 14 (5117 mẫu, quy ước atan2(-ay, -az) (chọn để khớp dấu; chưa xác minh)): Roll dataset mean 0.698°, std 0.055°; Roll suy từ gia tốc kế mean 0.703°, std 0.142°; Pearson r = 0.551, RMS chênh lệch 0.121°. Mean khớp, nhưng góc chỉ từ gia tốc kế nhiễu/dao động khác nhiều so với Roll đã fusion — feature biên độ sẽ lệch nếu không có fusion tương đương.

## 5. Ước lượng tài nguyên (chưa đo trên thiết bị)

| Thành phần RAM cho 23 feature | Byte |
|---|---:|
| roll_ring_180s_float32 | 7200 |
| pitch_ring_60s_float32 | 2400 |
| validity_bits | 300 |
| quantile_scratch_1800_float32 | 7200 |
| outputs_and_flags | 115 |
| total | 17215 |
| Lõi C hiện tại (`svmg_engine_t`, tài liệu M1) | 3336 |
| RAM trống tài liệu M1 ghi (trước heap WiFi) | ≈ 270000 |

Nguồn số liệu M1: firmware/docs/M1-08_resource_table.md (đo với stub, ngày 12/11/2026). Không lưu timestamp từng mẫu (nhịp cố định + bộ đếm gap); nếu lưu uint32 thêm 7.200 B.

| Mô hình | Cây | Nút | Depth | Ước lượng mảng C | So sánh trung bình/tối đa mỗi suy luận | Latency ước lượng (240 MHz, 20 chu kỳ/so sánh) |
|---|---:|---:|---:|---:|---:|---:|
| RF cuối (PoC) | 200 | 1150 | 5 | 8400 B | 316.8 / 330 | ≈ 27.5 µs |
| RF compact (`{"n_estimators": 25, "max_depth": 6, "min_samples_leaf": 10, "class_weight": "balanced_subsample", "max_features": "sqrt"}`), F1 proxy 1.000 | 25 | — | 6 | ≈ 1380 B (trung vị fold) | — | — |

Ngân sách flash M1 còn lại ≈ 1900000 B; mô hình ước lượng vài KB, không phải nút thắt. Sắp xếp cho phân vị: ≈ 47151 phép so sánh mỗi lần cập nhật 10 s. Tất cả là **ước lượng**, trạng thái `ESTIMATE_NOT_MEASURED_ON_DEVICE`.

### Độ phức tạp tính feature

| # | Feature | Cửa sổ | Đơn vị | Chiến lược nhúng |
|---:|---|---:|---|---|
| 0 | `roll_rms_60` | 60 s | deg | O(1) tổng bình phương trượt |
| 1 | `roll_std_60` | 60 s | deg | O(1) moment trượt ổn định |
| 2 | `roll_mean_60` | 60 s | deg | O(1) tổng trượt |
| 3 | `roll_peak_to_peak_60` | 60 s | deg | O(1) khấu hao bằng deque đơn điệu |
| 4 | `roll_abs_p95_60` | 60 s | deg | sắp xếp 600 phần tử/lần cập nhật |
| 5 | `roll_abs_max_60` | 60 s | deg | O(1) khấu hao bằng deque |
| 6 | `roll_iqr_60` | 60 s | deg | sắp xếp 600 phần tử |
| 7 | `roll_diff_rms_60` | 60 s | deg/sample @10 Hz | O(1); PHỤ THUỘC tần số lấy mẫu |
| 8 | `roll_mean_180` | 180 s | deg | O(1) tổng trượt |
| 9 | `roll_median_180` | 180 s | deg | sắp xếp 1800 phần tử |
| 10 | `roll_mean_abs_180` | 180 s | deg | O(1) tổng trượt |
| 11 | `roll_dominant_sign_ratio_180` | 180 s | 1 | O(1) bộ đếm dấu |
| 12 | `roll_segment_mean_std_180` | 180 s | deg | O(1) sau tổng block |
| 13 | `roll_mean_shift_180` | 180 s | deg | O(1) sau tổng block |
| 14 | `roll_rms_early_60` | 180 s | deg | O(1) sau tổng block |
| 15 | `roll_rms_late_60` | 180 s | deg | O(1) |
| 16 | `roll_rms_ratio_180` | 180 s | 1 | O(1) |
| 17 | `roll_rms_slope_180` | 180 s | deg/min | O(1) |
| 18 | `roll_rms_trend_r2_180` | 180 s | 1 | O(1) |
| 19 | `roll_p95_trend_slope_180` | 180 s | deg/min | sắp xếp 3x600 phần tử |
| 20 | `pitch_rms_60` | 60 s | deg | O(1) |
| 21 | `pitch_std_60` | 60 s | deg | O(1) |
| 22 | `pitch_peak_to_peak_60` | 60 s | deg | O(1) deque |

## 6. Kế hoạch parity Python/C cho 23 feature (tương lai)

1. **Golden vectors:** xuất từ `ml/features/extractor.py` các chuỗi 10 Hz (sin nhiều tần số, offset, tăng biên độ, tín hiệu hằng, có gap, có NaN, mẫu đúng 0) kèm 23 giá trị float64 và validity.
2. **Dữ liệu thật:** chọn cửa sổ Hohai/Seafar/Southampton (gồm biên phân vị, cửa sổ có gap) làm vector kiểm thử.
3. **Dung sai đề xuất:** tuyệt đối 0.001°, tương đối 0.0001; chốt sau khi đo float32.
4. **Validity parity:** C phải trả cùng trạng thái VALID/không hợp lệ (đủ 95%, gap, R² không xác định, rms_early ≤ epsilon).
5. **Quy ước phân vị Type-7**, std quần thể, block `(lower, upper]`, tâm block [30, 90, 150] s, slope × 60 phải giống hệt.
6. **Model parity:** cùng vector đầu vào → cùng xác suất RF (dung sai float32) trên bộ golden; đo latency `infer_stats()` và `stack_hwm` trên thiết bị.
7. **End-to-end:** chạy firmware trên tín hiệu mô phỏng/thật 10 Hz, so 23 feature với Python trên cùng chuỗi.

## 7. Thay đổi đề xuất cho M1 (cần phối hợp, chưa thực hiện)

- Thêm nhánh xử lý 10 Hz (lọc chống aliasing phù hợp, ví dụ 4 Hz như preprocessing) song song chuỗi 2 Hz hiện tại.
- Thêm module C tính 23 feature theo contract đề xuất, giữ nguyên vector cũ cho Baseline B.
- Thống nhất interface mô hình đa nhãn/proxy (xác suất + ABSTAIN) thay vì 4 lớp loại trừ trong `infer.cpp`.
- Đánh giá lại hiệu chuẩn mốc 0 và fusion Roll/Pitch so với nguồn dữ liệu huấn luyện.

## 8. Kết luận khả thi

- **Chưa thể triển khai** (`deployable = False`). Lý do: Chưa đo RAM/flash/latency trên ESP32 với model thật; Chưa có cài đặt C 23 feature và golden-vector parity; Chuỗi firmware hiện tại 2 Hz + lọc 0.5 Hz khác chuỗi 10 Hz của dataset; Roll ESP32 từ bộ lọc bù MPU6050 khác nguồn đo của dataset; chưa có hiệu chuẩn chéo; Mô hình học trên Hohai model-scale (chu kỳ ~1.8 s), không đại diện tàu full-scale; Nhãn là proxy tương đối, không phải hazard đã xác minh.
- RAM/flash ước lượng không phải trở ngại chính; trở ngại chính là **khác biệt tín hiệu và miền** (2 Hz/0.5 Hz, fusion MPU6050, model-scale vs full-scale) và proxy label chưa có ý nghĩa vận hành.

## 9. Giới hạn

- Mọi số RAM/flash/latency là ước lượng desktop; mô phỏng chuỗi firmware chỉ xấp xỉ (lọc ở 10 Hz thay vì 20 Hz, không mô phỏng gia tốc kế).
- Kiểm tra gia tốc kế Southampton dùng quy ước trục chọn thực nghiệm, chưa xác minh.

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

## 11. Giải thích kỹ thuật phục vụ vấn đáp cá nhân

- **Vì sao không chỉ copy model sang ESP32?** Feature tính trên tín hiệu khác (2 Hz, lọc 0.5 Hz) cho giá trị khác: mô phỏng cho thấy std giảm còn ≈ 0.67× và 299 quyết định proxy đổi. Model đúng trên PC có thể sai hệ thống trên thiết bị.
- **Vì sao 23 feature vẫn khả thi về bộ nhớ?** Bộ đệm 180 s × 10 Hz float32 cho Roll + 60 s cho Pitch + scratch sắp xếp ≈ 17215 B, nhỏ so với RAM trống M1 ghi nhận.
- **Vì sao chưa gọi là deployable?** Chưa đo trên thiết bị, chưa parity, chưa đồng nhất cảm biến và nhãn vẫn là proxy.
