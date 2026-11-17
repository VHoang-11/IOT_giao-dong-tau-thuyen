# Motion Phenotype Proxy PoC (M2)

> Proof of concept phân loại motion phenotype dựa trên **proxy label** — KHÔNG phải bộ phân loại an toàn hàng hải đã xác thực.

## Thành phần

| Module | Vai trò |
|---|---|
| `ml/labeling/proxy_spec.yaml` | Đặc tả proxy có phiên bản (`proxy_rules_v1.0.0`) |
| `ml/labeling/proxy_rules.py` | Thống kê nhân quả, hiệu chuẩn chỉ trên train, gán POS/NEG/ABSTAIN |
| `ml/labeling/proxy_dataset.py` | CLI dựng proxy dataset, nhãn out-of-fold, độ nhạy, cổng readiness |
| `ml/train/grouping.py` | Khóa nhóm độc lập (Hohai = điều kiện `Tn`), leave-one-group-out, kiểm toán rò rỉ |
| `ml/train/rf_poc.py` | Nested group CV, baseline, ablation, mô hình cuối + model card |
| `ml/train/predict.py` | CLI dự đoán (kiểm tra schema/SHA, ABSTAIN khi input không hợp lệ hoặc ngoài miền) |
| `ml/train/esp32_feasibility.py` | Đề xuất contract 23 feature, ước lượng ESP32, thí nghiệm lệch miền chuỗi lọc |
| `ml/train/reports.py` | Sinh báo cáo tiếng Việt trong `ml/reports/ml/` từ artifact JSON |
| `ml/eval/metrics.py`, `ml/baselines/proxy_baselines.py` | Metric, bootstrap theo nhóm, baseline |

## Chạy lại (từ repository root, venv đã activate)

```bash
python -m pip install -r ml/train/requirements.txt
python -m ml.labeling.proxy_dataset
python -m ml.train.rf_poc
python -m ml.train.esp32_feasibility
python -m ml.train.reports
python -m pytest ml/train/tests -q
```

Artifact lớn nằm trong `ml/data/labels/proxy_v1/` và `ml/data/models/rf_poc_v1/` (gitignored). Không tạo `ml/export/model.h`
vì firmware tự include file đó; tích hợp phải qua phối hợp với M1 (xem `ml/reports/ml/esp32_feature_compatibility.md`).
