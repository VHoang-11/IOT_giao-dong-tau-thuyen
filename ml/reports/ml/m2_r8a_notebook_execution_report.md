# Báo cáo chạy notebook M2-R8a (26 huấn luyện, 27 đánh giá RF bốn lớp)

Ngày chạy: 2026-11-25. Kernel mới cho mỗi lần chạy, Python 3.14.10, scikit-learn 1.9.1, numpy 2.4.6, pandas 3.0.3, matplotlib 3.11.0.
Notebook được commit **không có output**; bản đã chạy và hình nằm ở `ml/data/models/rf_four_class_m2r6/notebook_runs/` (gitignored).

```bash
.venv/bin/python -m nbconvert --to notebook --execute ml/notebooks/26_four_class_rf_training.ipynb --output-dir ml/data/models/rf_four_class_m2r6/notebook_runs
.venv/bin/python -m nbconvert --to notebook --execute ml/notebooks/27_four_class_rf_evaluation.ipynb --output-dir ml/data/models/rf_four_class_m2r6/notebook_runs
```

## Kết quả chạy

| Notebook | Môi trường | Ô code chạy | Lỗi | Hình |
|---|---|---:|---:|---:|
| 26 | máy gốc (`.venv`) | 9/9 | 0 | 6 |
| 27 | máy gốc (`.venv`, có `results.json` đã khóa) | 9/9 | 0 | 5 |
| 26 | bản clone sạch + venv sạch (M2-R8) | 9/9 | 0 | 6 |
| 27 | bản clone sạch + venv sạch, **không** có `results.json` | 9/9 | 0 | 5 |

Hình notebook 26: phân bố pitch/roll v0.2 và v0.3, phân bố lớp theo split, macro-F1 theo cấu hình và theo số nút, confusion Validation
v0.2/v0.3, precision/recall/F1 theo lớp, MDI importance. Hình notebook 27: chính sách tau (Validation và S0b), S0b sau tau, confusion
Test-G1 trước/sau tau, Validation và Test-G1, độ tin cậy các ca lỗi AMPLITUDE_GROWTH.

## Kiểm tra số liệu (assert trong notebook)

| Kiểm tra | Giá trị tính lại | Giá trị đóng băng | Dung sai |
|---|---|---|---|
| SHA dataset v0.2 / v0.3 | `b4b249d0…` / `f3c893fc…` | như `R.DATASETS` | trùng tuyệt đối |
| Cấu hình chọn v0.2 / v0.3 | #0 (15 cây, độ sâu 4, lá 5, không class_weight) / #0 | #0 / #0 (M2-R6a) | trùng |
| macro-F1 Validation v0.2 / v0.3 | 0,9112 / 0,9876 | 0,9112 / 0,9876 | ≤ 1e-4 |
| Mô hình fit lại v0.3 | cây trùng (feature, ngưỡng, nhánh, giá trị lá), xác suất Validation trùng | `model.joblib` `3d7ecf31…` | trùng tuyệt đối |
| SHA `model.joblib`, header C99 sinh lại | khớp manifest | `3d7ecf31…`, `f83d07cc…` | trùng tuyệt đối |
| Bảng chính sách tau (5 giá trị, Validation + S0b) | tính lại từ mô hình | `policy_table` trong manifest | trùng tuyệt đối |
| Validation sau tau 0,5 | coverage 0,9936, macro-F1 hiệu dụng 0,9734 | coverage 0,9936 (manifest) | trùng |
| Contract C | lớp = `svmg_class_t`, thứ tự = `SVMG_FEATURE_FIELDS` | – | trùng |
| Leakage | không có Test-G1 trong dữ liệu nạp; Train ∩ Validation rỗng; seed Test-G1 tách biệt | – | – |

Test-G1 (notebook 27) là **số liệu lịch sử, chỉ đọc** từ `ml/reports/ml/m2_r6c_test_g1_metrics_summary.json`; khi máy có `results.json`
đã khóa, notebook kiểm SHA nguồn `8c24739c…` khớp. Không có lần đánh giá Test-G1 mới nào. Số hiển thị: trước tau macro-F1 0,8698; sau
tau macro-F1 hiệu dụng 0,8158, coverage 0,9167, precision AMPLITUDE_GROWTH 0,3438.

## Ghi chú

- Bytes joblib của mô hình fit trong notebook (`0b0aec04…`) khác file đóng băng dù cây trùng hoàn toàn; SHA `3d7ecf31…` được tái lập bởi
  `python -m ml.train.rf_four_class_m2r6` (đã kiểm trên bản clone sạch). Notebook vì vậy so cấu trúc cây, không so SHA joblib.
- Baseline B Validation trong notebook 27 được tính lại bằng đúng hàm C `core/src/baseline.c` (macro-F1 0,6793); Test-G1 là số lịch sử.
- Kết quả Wokwi trong notebook 27 là bảng lịch sử; ô code chỉ đọc bản ghi cục bộ nếu có (gitignored).
