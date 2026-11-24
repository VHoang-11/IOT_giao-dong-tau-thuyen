# Báo cáo kiểm chứng bàn giao M2-R8

Ngày chạy: 2026-11-25. Máy: macOS (Apple Silicon), Python 3.14.10, `cc` (clang), PlatformIO 6.2.0. Chỉ ghi lệnh đã chạy thật và kết quả
quan sát được; Test-G1 **không** được đánh giá lại; không chạy Wokwi trực tiếp trong M2-R8.

## 1. Kiểm toán tái lập trên bản clone sạch

Bản clone `git clone` từ HEAD `6258a9a` (sau merge M2-R7) vào thư mục tạm, venv mới tạo bằng `python3.14 -m venv`, không dùng file
gitignored nào của máy gốc.

| Bước | Lệnh | Kết quả |
|---|---|---|
| Cài đặt | `pip install -r ml/train/requirements.txt` | OK (scikit-learn 1.9.1, numpy 2.4.6) |
| Dataset v0.2 | `python -m ml.train.four_class_experimental_dataset` | SHA `b4b249d0…` **khớp** |
| Dataset v0.3 | `python -m ml.train.four_class_v03_dataset` | SHA `f3c893fc…` **khớp**; `labels_match_v02=true` |
| Huấn luyện RF | `python -m ml.train.rf_four_class_m2r6` | `v03/model.joblib` SHA `3d7ecf31…` **khớp**; `v02/model.joblib` `47f15872…` khớp bản gốc |
| Export C99 | `python -m ml.export.rf4_freeze_m2r6b` | header `f83d07cc…`, tau 0,5, parity 0 lệch UNKNOWN; manifest không đổi |
| model.h | `python -m ml.export.prepare_firmware_model_m2r7` | `model.h` SHA `f83d07cc…` **khớp** |
| File đã commit bị sinh lại | `git status` | chỉ `m2_r5c_dataset_quality_report.md` đổi 1 dòng (kiểm toán seed G1 cần manifest G1 gitignored); báo cáo R5d/R6a/R6b trùng từng byte |
| Test (trước sửa) | `pytest -q ml simulation` | **lỗi**: thiếu `openpyxl` (2 lỗi collection) |
| Build (trước sửa) | `import platformio, serial` | **thiếu** `platformio`, `pyserial` trong requirements |

## 2. Sửa lỗi tái lập (trong PR này)

- `ml/train/requirements.txt`: thêm `-r ../preprocessing/requirements.txt` (có `openpyxl`), `platformio==6.2.0`, `pyserial==3.5`.
- 3 test cũ của pilot gán nhãn (`ml/labeling/tests/test_review_app.py`, `test_human_review_workflow.py`) cần
  `ml/data/labels/annotation_pilot/` (gitignored, từ dữ liệu thật) nhưng không có điều kiện bỏ qua; thêm `skipif` như các test dữ liệu
  thật khác. Trên máy có dữ liệu chúng vẫn chạy (9/9 pass).
- Thêm tóm tắt Test-G1 chỉ-đọc `ml/reports/ml/m2_r6c_test_g1_metrics_summary.json` (`python -m ml.eval.final_test_g1_m2r6c
  --export-summary`, chỉ đọc `results.json` đã khóa SHA `8c24739c…`, không đánh giá lại) để bản clone sạch có số Test-G1.

## 3. Kết quả sau sửa (venv sạch, bản clone sạch)

| Hạng mục | Lệnh | Kết quả |
|---|---|---|
| Cài lại | `pip install -r ml/train/requirements.txt` | OK; `openpyxl`, `platformio 6.2.0`, `pyserial 3.5` import được |
| Toàn bộ test M2 | `pytest -q ml simulation` | **344 passed, 9 skipped, 0 failed** (bỏ qua = dữ liệu thật gitignored) |
| Parity 23 đặc trưng | `python tests/firmware/tools/check_features23.py` | 23 ca, 529 phép so, 0 lỗi |
| Adapter mô hình M1 | `python tests/firmware/tools/check_model_adapter.py` | 6/6 PASS |
| Build firmware | `pio run -e esp32dev_rf4_shadow -e esp32dev` (pio của venv sạch) | cả hai SUCCESS; `[RF4] model.h OK sha256=f83d07cc…`; RAM 85 172 B (26,0 %), flash 1 094 679 B (34,8 %) |
| Notebook 26/27 | `python -m nbconvert --to notebook --execute …` | chạy hết, 0 lỗi (chi tiết: `m2_r8a_notebook_execution_report.md`) |

Trên máy gốc: `pytest -q ml simulation` 353 passed (gồm test cần dữ liệu thật).

## 4. Wokwi (lịch sử, không chạy trong M2-R8)

Bản ghi gitignored `ml/data/parity/wokwi_mpu6050/` do người dùng chạy sau M2-R7 (cổng 4001):

| Run | Nguồn | Serial | Kết quả chính |
|---|---|---|---|
| `rf4_sim_01` | SIMULATION (stub M1), 60 s từ t ≈ 412 s | SHA `0cf4b46c…` | 5 cập nhật 23/23; RF 28 lần gọi, NORMAL; infer tối đa 719 µs; `primary` = Baseline B; `cnt_gap` tích lũy 4, loop gap tối đa 555 ms, hàng đợi tối đa 7, 0 tràn; 24 dòng lỗi MQTT |
| `rf4_02` | SENSOR (MPU6050 đứng yên), 300 s | SHA `1541446c…` | tối đa 20/23 (3 đặc trưng 180 s không xác định khi không chuyển động); RF 0 lần gọi, `rf=UNKNOWN`; 0 gap, hàng đợi tối đa 6, 0 tràn; feature update tối đa 296 ms; 115 dòng lỗi MQTT |

Cả hai bản ghi bắt đầu sau boot nên không có dòng `[MODEL]`; mục `rf_model_available` của capture vì thế là `false` (thiếu bằng chứng,
không phải lỗi mô hình). Chưa có RF trên cảm biến chuyển động.

## 5. Kết luận

Tái lập **đạt** cho dataset, mô hình, header C99, `model.h`, test và build trên bản clone sạch sau khi sửa phụ thuộc. Bàn giao ở mức
**PARTIAL**: chưa có bằng chứng RF chạy trên dữ liệu cảm biến chuyển động, chưa kiểm chứng ESP32/tàu thật, mô hình còn giới hạn về
AMPLITUDE_GROWTH (precision Test-G1 0,34).
