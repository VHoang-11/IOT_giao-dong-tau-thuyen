# Bàn giao M2 – Mô phỏng và học máy (Smart Vessel Motion Guard)

Tài liệu cho thành viên tiếp nhận M2. Mọi dữ liệu ở đây là `SIMULATION`; nhãn là proxy `SIMULATION_SCENARIO_V2_CANDIDATE`. Kết quả **không**
phải dự báo lật tàu, không phải đánh giá GM/GZ; ngưỡng chỉ là tham số demo. Bằng chứng kiểm chứng: `ml/reports/ml/m2_r8_handover_verification.md`.

## 1. Tổng quan và kiến trúc

```
simulation/generator (roll 1-DOF S0/S1/S2/S3/S0b + pitch/nhiễu IMU svmg-sim-pitch-imu-0.1.0)
  → IMU 20 Hz → Core C (lọc, 10 Hz, cửa sổ 60/180 s) → 23 đặc trưng svmg-angle-23-v1 → nhãn điểm cuối (ABSTAIN khi mơ hồ)
  → dataset svmg-four-class-exp-0.3.0 → RF 15 cây, độ sâu 4 (chọn trên Validation) → Test-G1 đánh giá MỘT lần
  → header C99 đóng băng (model.h, tau 0,5) → firmware env esp32dev_rf4_shadow: RF chạy SHADOW, Baseline B + phi_hard là mô hình chính
```

Lớp trùng `svmg_class_t`: `0 NORMAL`, `1 HIGH_ROLL`, `2 PERSISTENT_OFFSET`, `3 AMPLITUDE_GROWTH`; `UNKNOWN` khi đặc trưng chưa đủ/không
hợp lệ hoặc độ tin cậy < 0,5 – **không bao giờ** hiển thị thành NORMAL.

## 2. Các mốc đã hoàn thành

| Mốc | Nội dung | Tài liệu/báo cáo |
|---|---|---|
| M2-R1–R3 | RF PoC trên Hohai (proxy nhị phân), export C demo, đánh giá ML | `ml/docs/M2_R1_rf_demo_c_export.md`, `ml/reports/ml/M2_R3_ml_evaluation_report.md` |
| M2-R4 | Đường MPU6050 → 23 đặc trưng trên Wokwi, task lấy mẫu `SVMG_ACQ_TASK` | `firmware/tools/wokwi_sensor_capture.py` |
| M2-R5/R5b/R5c | Pilot bốn lớp, kiểm toán, hợp đồng nhãn và dataset v0.2 | `ml/docs/M2_R5c_four_class_dataset_contract.md`, `m2_r5c_dataset_quality_report.md` |
| M2-R5c-2/R5d | Mở rộng pitch + nhiễu IMU, dataset v0.3 | `ml/docs/M2_R5c2_pitch_imu_simulation.md`, `m2_r5d_dataset_v03_quality_report.md` |
| M2-R6a/b/c | Huấn luyện RF, export C99 + tau đóng băng, Test-G1 một lần | `m2_r6a_four_class_rf_report.md`, `m2_r6b_c99_export_report.md`, `m2_r6c_test_g1_final_report.md` |
| M2-R7 | Tích hợp ESP32 chế độ shadow | `ml/docs/M2_R7_rf4_esp32_handover.md` |
| M2-R8/R8a | Bàn giao, kiểm toán tái lập, notebook 26/27 | tài liệu này, `ml/notebooks/26_*.ipynb`, `27_*.ipynb` |

## 3. Cài đặt (máy mới, bản clone sạch)

Yêu cầu: Python **3.14** (đã kiểm 3.14.10), trình biên dịch C (`cc`), mạng để PlatformIO tải toolchain ESP32 lần đầu.

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r ml/train/requirements.txt      # numpy/pandas/scikit-learn đã ghim + openpyxl, platformio, pyserial
```

Phiên bản ghim quyết định SHA mô hình (scikit-learn 1.9.1, numpy 2.4.6, joblib 1.6.0); đổi phiên bản có thể làm SHA khác và các bước
dưới sẽ dừng thay vì âm thầm dùng mô hình khác.

## 4. Tái lập dataset, mô hình đóng băng và model.h

Chạy từ thư mục gốc repo; mọi dữ liệu sinh ra nằm trong `ml/data/` (gitignored).

```bash
.venv/bin/python -m ml.train.four_class_experimental_dataset   # v0.2 (~45 s)
.venv/bin/python -m ml.train.four_class_v03_dataset             # v0.3 (~35 s)
.venv/bin/python -m ml.train.rf_four_class_m2r6                 # RF v0.2/v0.3, chọn trên Validation (~10 s)
.venv/bin/python -m ml.export.prepare_firmware_model_m2r7       # model.h firmware, chỉ ghi nếu SHA đúng
```

| Artifact | SHA-256 kỳ vọng |
|---|---|
| `ml/data/simulation_four_class_exp_v02/windows.csv` | `b4b249d08dc2fae17476a62c2b596d14ead0ea1b8de75fd412a96d5110b4ad5c` |
| `ml/data/simulation_four_class_exp_v03/windows.csv` | `f3c893fcaa498fba9ebac62ffe9ab4a06632f50b0d97fd332547cf04fa15370c` |
| `ml/data/models/rf_four_class_m2r6/v03/model.joblib` | `3d7ecf315e237b00e26da4338ed0aa313d6efc9e5488dd6b227e18cc80f41f89` |
| `ml/data/models/rf_four_class_m2r6/v03/firmware/model.h` | `f83d07cc1ed4b3d55b89933ba545425d7da7acf3eaa4e2f06021b505f342dd09` |

- Tùy chọn: `python -m ml.export.rf4_freeze_m2r6b` sinh lại header C99, parity và manifest (`ml/reports/ml/m2_r6b_frozen_model_manifest.json`
  phải không đổi).
- **Không** chạy lại đánh giá Test-G1 (`ml/eval/final_test_g1_m2r6c.py` từ chối nếu đã có kết quả khóa). Bản clone sạch dùng tóm tắt đã
  commit `ml/reports/ml/m2_r6c_test_g1_metrics_summary.json` (trích chỉ-đọc từ `results.json` đã khóa, SHA nguồn `8c24739c…`).
- Sinh lại v0.2 làm đổi 1 dòng kiểm toán seed G1 trong `ml/reports/ml/m2_r5c_dataset_quality_report.md` (cần manifest G1 gitignored);
  dataset SHA không đổi – **không commit** thay đổi đó.
- Notebook: `ml/notebooks/26_four_class_rf_training.ipynb` (huấn luyện) và `27_four_class_rf_evaluation.ipynb` (đánh giá); chạy bằng
  `.venv/bin/python -m nbconvert --to notebook --execute <notebook> --output-dir ml/data/models/rf_four_class_m2r6/notebook_runs`.

## 5. Build firmware RF shadow và chạy Wokwi

```bash
cd firmware && ../.venv/bin/pio run -e esp32dev_rf4_shadow    # pre-script dừng build nếu model.h thiếu/khác SHA
```

VS Code (extension Wokwi): dừng mọi simulator → `Wokwi: Select Config File` → `firmware/wokwi/wokwi.rf4_shadow.toml` →
`Wokwi: Start Simulator`; để tab simulator hiển thị. Cổng RFC2217 **4001** (4000 dùng cho HV01/M2-R4; trùng cổng làm nhận 0 byte;
nếu cổng cũ bị giữ: `Developer: Reload Window`). Kiểm tra `lsof -nP -iTCP:4001` có LISTEN, rồi ghi Serial (chỉ đọc), **bắt đầu trước
khi khởi động lại simulator** để bắt dòng `[MODEL]` lúc boot; cần ≥ 240 s vì cửa sổ 180 s mất ~185 s mới đủ:

```bash
.venv/bin/python firmware/tools/wokwi_sensor_capture.py --port rfc2217://localhost:4001 --seconds 300 --run-id rf4_03
```

Kết quả: `ml/data/parity/wokwi_mpu6050/<run-id>/summary.json` (mục `rf_shadow`, `timing`, `checks`). Chế độ SIMULATION của firmware dùng
**stub sóng sin của M1** (`firmware/stubs/sim_stub.cpp`), không phải bộ sinh M2: nút MODE (nhấn ngắn) đổi SENSOR ↔ SIMULATION, nút SCN
đổi kịch bản stub (chỉ ở SIMULATION). Đổi chế độ xóa cửa sổ (chờ lại ~185 s); đổi kịch bản giữ cửa sổ, nên lịch sử 180 s trộn hai kịch bản.

## 6. Đọc các dòng Serial

| Dòng | Trường | Ý nghĩa chính |
|---|---|---|
| `[MODEL]` (boot) | `status, version, kind, features, schema_ok, preprocessing_ok, requested, active` | phải là `status=AVAILABLE version=svmg-rf-four-class-m2r6a-0.1.0 … active=BASELINE_B` |
| `M,` (mỗi 10 s) | `t, mode, rf, b, primary, status, infer_last_us, infer_max_us, calls` | lớp RF (shadow), Baseline B, lớp chính (luôn bằng `b`); `status` 0 OK / 1 UNKNOWN / 2 FAULT; `calls` chỉ tăng khi đủ 23/23 |
| `F,` (mỗi 10 s) | `t, mode, update, status, reason, mask, n_valid, ready_s, ready_l, n60, n180, consec_inv, dq_pct, 23 giá trị` | `mask=0x7fffff` và `n_valid=23` mới gọi RF; `nan` = đặc trưng không hợp lệ |
| `G,` (mỗi 1 s) | `t, cnt_gap, cnt_invalid, overruns, late, max_ms(sample_dt, loop_gap, sampling, lcd, net), feat_upd_last_ms, feat_upd_max_ms, acq_ovf, acq_qmax` | `cnt_gap` tăng = khoảng mẫu > 75 ms làm reset cửa sổ; `acq_ovf` > 0 = tràn hàng đợi |
| `[DIAG] invalid:` | tên đặc trưng không hợp lệ | in khi mask đổi |

## 7. Ma trận bằng chứng

| Mức | Bằng chứng | Kết quả | Chưa chứng minh |
|---|---|---|---|
| Host (Python/C, máy tính) | parity C99/sklearn; `infer.cpp` thật + `model.h` | lớp khớp 469 Validation + 304 S0b + 170 vector ngưỡng + 300 Test-G1; `infer.cpp` 773/773 (đủ 4 lớp + UNKNOWN); max \|Δp\| 3,3e-8 | – |
| SIM (Wokwi, stub M1) | `rf4_sim_01` (60 s, từ t ≈ 412 s) | 23/23 đặc trưng; RF chạy 28 lần, dự đoán NORMAL; tối đa 719 µs; Baseline B chính | 4 lớp trên thiết bị; stub không phải bộ sinh M2 |
| SENSOR (Wokwi, MPU6050 mô phỏng đứng yên) | `rf4_02` (300 s) | tối đa 20/23 đặc trưng; RF không được gọi (`calls=0`), `rf=UNKNOWN` | RF trên cảm biến chuyển động |
| ESP32 thật / tàu thật | – | chưa thực hiện | thời gian thật, dữ liệu thật |

Các bản ghi Wokwi là lịch sử (gitignored, không chạy lại trong M2-R8) và đều bắt đầu sau boot nên không chứa dòng `[MODEL]`.

## 8. Độ chính xác và giới hạn của mô hình

- Validation (dùng để chọn, lạc quan): macro-F1 0,988. **Test-G1 (một lần, cùng miền mô phỏng):** macro-F1 trước tau 0,870; sau tau
  0,5 macro-F1 hiệu dụng **0,816**, coverage 0,917 (25 UNKNOWN). Baseline B Test-G1 macro-F1 0,532.
- **AMPLITUDE_GROWTH precision 0,34**: 21 cửa sổ NORMAL từ 2 session bị báo GROWTH, nhiều ca conf > 0,5 nên tau không chặn được.
- Nhãn proxy sinh từ ngưỡng trên roll thật của chính bộ mô phỏng: RF học lại luật, không phải ground truth nguy hiểm.
- Khi đứng yên, `roll_dominant_sign_ratio_180`, `roll_rms_ratio_180`, `roll_rms_trend_r2_180` không xác định về toán học → vector
  không đủ 23/23 → RF trả UNKNOWN (đúng contract) và Baseline B có thể UNKNOWN.
- Tau 0,5 là giá trị dự phòng (không tau nào đạt quy tắc chọn), độ tin cậy chưa hiệu chuẩn.

## 9. Vấn đề đã biết và việc tiếp theo

- Chưa có bằng chứng RF trên dữ liệu cảm biến chuyển động; chưa có Test-G2, dữ liệu MPU6050 thật, kiểm chứng trên tàu.
- Wokwi không có broker MQTT nên log có dòng lỗi `E (` (115 dòng/300 s ở `rf4_02`); không ảnh hưởng LED/còi.
- Cập nhật đặc trưng chặn vòng lặp ~0,3–0,5 s (M2-R4: 494 ms; `rf4_02` 296 ms). Ở SIMULATION, mẫu vẫn sinh trong loop nên `rf4_sim_01`
  có `cnt_gap` tích lũy 4 và vòng lặp chậm tối đa 555 ms; SENSOR dùng task riêng (`rf4_02`: 0 gap, hàng đợi tối đa 6/64, 0 tràn).
- `core/src/sim` (bộ sinh M2 bằng C) còn là khung; firmware vẫn dùng stub.
- Bytes joblib của mô hình fit trong notebook khác file đóng băng dù cây trùng hoàn toàn; SHA đóng băng chỉ được tái lập bởi script.
- Việc tiếp theo: dữ liệu MPU6050 thật / Test-G2; thêm session S3 để giảm báo nhầm GROWTH; hiệu chỉnh lại Baseline B trên Validation;
  đo thời gian trên ESP32 thật; M1 quyết định bật `SVMG_ACQ_TASK` cho production và giảm chặn loop.

## 10. Quyền sở hữu và review

- **M2:** `simulation/`, `ml/`, `core/src/sim/`. **M1:** `core/`, `firmware/`, `tests/firmware/`.
- Thay đổi firmware của M2-R7 (env `esp32dev_rf4_shadow`, 4 đoạn `#ifdef SVMG_RF_SHADOW` trong `app.cpp`, cấu hình Wokwi, tool capture)
  đã merge qua PR #52, cần M1 tiếp tục review. Production `esp32dev` không đổi và vẫn dùng stub mô hình.
- Không đặt `model.h` vào `ml/export/` (mọi env firmware có `-I../ml/export`, sẽ âm thầm thay stub production). M2 khuyến nghị **không**
  cho RF làm mô hình chính.
- Theo AGENTS.md: commit/push/merge do người dùng thực hiện; PR ≤ 400 dòng; thay đổi liên module cần review của chủ sở hữu module.
