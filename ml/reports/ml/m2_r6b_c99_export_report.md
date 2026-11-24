# Báo cáo export C99 RF bốn lớp M2-R6b (`svmg-rf-four-class-m2r6a-0.1.0`)

> Mô hình chọn ở M2-R6a, **không huấn luyện/chọn lại**; dữ liệu `SIMULATION` `svmg-four-class-exp-0.3.0`, nhãn proxy `SIMULATION_SCENARIO_V2_CANDIDATE`; không phải độ chính xác ngoài thực tế. **Test-G1 chưa được nạp/đánh giá.** Sinh bởi `python -m ml.export.rf4_freeze_m2r6b`; header gitignored tại `ml/data/models/rf_four_class_m2r6/v03/c99/`, manifest đóng băng `ml/reports/ml/m2_r6b_frozen_model_manifest.json`. Không ghi `ml/export/model.h`, không sửa firmware.

## Cấu trúc C99

- Header tự chứa `svmg_rf_four_class_m2r6a_0_1_0.h` (SHA-256 `f83d07cc1ed4b3d5…`, 13679 B), theo contract `model.h` của `firmware/src/infer.cpp`: `model_predict`, `model_predict_conf`, `model_predict_proba`; macro `SVMG_MODEL_VERSION`, `SVMG_MODEL_N_FEATURES` = 23, `SVMG_MODEL_FEATURE_SCHEMA_VERSION`, `SVMG_MODEL_PREPROCESSING_VERSION`, `SVMG_MODEL_HAS_PROBA`, `SVMG_TAU_CONF` = 0.5.
- 15 cây, 185 nút (100 lá, độ sâu ≤ 4); mảng: feature int8, ngưỡng float32 làm tròn xuống (x ≤ t32 ⇔ x ≤ t64 như sklearn), trái/phải int16, xác suất lá float32 × 4. Lớp = argmax trung bình xác suất lá (cộng double), hòa → chỉ số lớp nhỏ nhất như numpy. Đầu vào NULL/sai độ dài/không hữu hạn → −1 (infer.cpp đổi thành UNKNOWN). Ước tính mảng 3295 B; object `-Os`: esp32_xtensa_Os: text 3624 B, data 0 B.
- Biên dịch `-std=c99 -O2 -Wall -Wextra -Werror -pedantic` sạch; probe C++ gnu++11 `-pedantic` (cách infer.cpp dùng): True; sinh lại tất định: True.

## Chính sách UNKNOWN (chọn chỉ trên CORE Validation)

Độ tin cậy = max mean leaf probability (sklearn predict_proba semantics), NOT calibrated. Quy tắc khai báo trước: largest tau with every class effective recall >= 0.95; dự phòng 0.5. **Chọn tau = 0.5** — **không tau nào đạt quy tắc** (kể cả 0,5: một cửa sổ AMPLITUDE_GROWTH có conf < 0,5), nên giữ giá trị dự phòng = mặc định `SVMG_TAU_CONF` của infer.cpp; không hạ tau dưới mặc định và không ánh xạ UNKNOWN thành NORMAL.

| tau | Phủ Validation | Recall hiệu dụng N / H / P / G | Lỗi được chấp nhận | S0b UNKNOWN | S0b báo sai bất thường |
|---:|---:|---:|---:|---:|---:|
| 0.5 | 0.9936 | 0.9871 / 1.0 / 1.0 / 0.9 | 1 | 1 | 5 |
| 0.6 | 0.9787 | 0.9569 / 1.0 / 1.0 / 0.9 | 1 | 7 | 2 |
| 0.7 | 0.9701 | 0.9483 / 0.9773 / 1.0 / 0.8 | 1 | 10 | 1 |
| 0.8 | 0.9104 | 0.931 / 0.8636 / 0.9235 / 0.4 | 0 | 14 | 0 |
| 0.9 | 0.823 | 0.8664 / 0.5455 / 0.8798 / 0.0 | 0 | 21 | 0 |

## Parity Python (sklearn) / C

| Tập | Vector | Lệch lớp | Max |Δp| | Biên top-2 nhỏ nhất | Hòa chính xác | Lệch UNKNOWN |
|---|---:|---:|---:|---:|---:|---:|
| validation | 469 | 0 | 3.29e-08 | 0.0223 | 0 | 0 |
| s0b | 304 | 0 | 2.88e-08 | 0.0127 | 0 | 0 |
| threshold_boundaries | 170 | 0 | 2.80e-08 | 0.6 | 0 | 0 |

Đầu vào lỗi (độ dài 22/24/0, NaN, ±inf) trả −1: {'length_22': True, 'length_24': True, 'length_0': True, 'nan': True, 'pos_inf': True, 'neg_inf': True}.

## Giới hạn

- Độ tin cậy là tỉ lệ phiếu/xác suất lá chưa hiệu chuẩn; Validation chỉ 12 session (AMPLITUDE_GROWTH 10 cửa sổ/3 session), nên tau chỉ là chính sách bảo thủ có thể tái lập, không phải xác suất đúng.
- Chưa đánh giá Test-G1 (đánh giá một lần, chỉ đọc, sau đóng băng); chưa đo thời gian suy luận trên ESP32 thật; chưa tích hợp firmware (M2-R7 cần M1 review).
