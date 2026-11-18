# Bàn giao M1 — firmware 1.1.0, 23 đặc trưng

Ngày cập nhật: **18/11/2026**. Phần mềm M1 đã chuyển sang mục tiêu M2 chọn; chưa coi toàn hệ thống đã nghiệm thu phần cứng/ML.

## Đã triển khai

- Contract `svmg-angle-23-v1`, manifest và thứ tự index 0–22; chất lượng/mask nằm ngoài đầu vào RF.
- IMU 20 Hz → bộ lọc bù → Butterworth4 4 Hz → Roll/Pitch 10 Hz; bỏ 2 s warmup filter.
- Ring 1.800 mẫu mỗi góc, 23 feature mỗi 10 s; std population, Type-7, raw RMS, slope deg/min; INVALID giữ NaN.
- Heapsort in-place và workspace cố định để không đặt mảng quantile 7,2 KB trên stack ESP32.
- RF chỉ nhận vector hợp lệ và model có đúng feature/preprocessing/version; không dùng model 14 mục hoặc stub để báo NORMAL.
- Baseline B/MAI chuyển sang feature mới. Hiệu chuẩn vẫn 30 s; giải tỏa theo 3 cập nhật 10 s; kiểm soát lệnh và ngưỡng cứng giữ độc lập.
- Thiếu mẫu hiển thị UNKNOWN ngay; thiếu liên tục 10 s → FAULT; gap reset history. Cảnh báo đang có không bị hạ vì lỗi cảm biến.
- Status/health báo schema; health thêm mask/status và thời gian cập nhật engine. Trace khai báo 10 Hz.
- Giữ nguyên mạch MPU6050, LCD, nút, đèn, buzzer và bảng chân.

## Kiểm chứng đã chạy

| Kiểm tra | Kết quả |
|---|---|
| Native Unity | 208/208 PASS |
| C vs extractor Python M2 | 529/529 giá trị, 23 chuỗi; thứ tự và kiểm không đọc tương lai PASS |
| CF + Butterworth vs SciPy | 8.000 giá trị PASS; max error 1,681e-7 rad |
| Adapter model | 6 loại artifact PASS, gồm metadata sai/thiếu và không có model |
| MQTT schema/lifecycle/ACL | 46 bản tin hợp lệ, 0 vi phạm |
| CRC | 4.004 payload + 300 số thực chính xác cao khớp tham chiếu backend |
| Baseline parameter generator | Ví dụ hợp lệ + 3 đầu vào sai (version/Inf/bool) PASS |
| ESP32 build | `esp32dev`, `esp32dev_inject` PASS |

[Nhật ký và thủ tục mạch](../../tests/firmware/TEST_LOG.md), [tài nguyên](M1-08_resource_table.md),
[contract](../../contracts/features.md), [manifest](../../contracts/features23.json).

## Còn phải nghiệm thu/tích hợp

1. M2 bàn giao model RF cùng schema/order/preprocessing; xác nhận các quy ước đang khớp Python và hiệu chỉnh tham số Baseline trên validation.
2. M2 hoàn thiện cổng C của bộ sinh tín hiệu; firmware vẫn dùng sim stub, không dùng nó làm kết quả ML thật.
3. Chạy T01/T05/T07 trên Wokwi/ESP32; broker round-trip, LWT, NVS qua reset, stack/heap/latency runtime. Các mục này vẫn NOT RUN.
4. M3/M4 xử lý các lệch ACK từ xa/mute/config đã ghi trong [CONTRACT_PROPOSALS.md](CONTRACT_PROPOSALS.md).

Baseline hiện là heuristic demo; thời lượng offset tương đương không phải heel liên tục đo trực tiếp.
S3-like trong host test được phát hiện dưới lớp HIGH_ROLL, không phải bằng chứng đã phân loại AMPLITUDE_GROWTH đúng.
Cảm biến đủ kênh đo không chứng minh độ chính xác góc trong điều kiện thực tế. Không gọi kết quả là dự báo lật tàu hay GM/GZ.

## Danh sách file cập nhật trong lần chuyển đổi

Contract/lõi:

- `contracts/features.md`, `contracts/features23.json`
- `core/include/svmg_feature_schema.h`, `core/include/svmg_core.h`, `core/include/svmg_contract.h`
- `core/include/svmg_features.h`, `core/include/svmg_filter.h`, `core/include/svmg_engine.h`
- `core/include/svmg_calib.h`, `core/include/svmg_decision.h`, `core/include/svmg_alarm.h`
- `core/src/features.c`, `core/src/filter.c`, `core/src/engine.c`, `core/src/baseline.c`, `core/src/mai.c`

Firmware:

- `firmware/src/app.cpp`, `firmware/src/infer.cpp`, `firmware/src/infer.h`
- `firmware/src/net.cpp`, `firmware/src/trace.cpp`, `firmware/src/trace.h`
- `firmware/include/svmg_build.h`, `firmware/stubs/model_stub.h`
- `firmware/lib/svmg_msg/src/msg.cpp`, `firmware/lib/svmg_msg/src/msg.h`
- `firmware/tools/gen_baseline_header.py`, `firmware/tools/baseline_params.example.json`

Kiểm thử:

- `tests/firmware/test/test_features/test_features.c`, `tests/firmware/test/test_filter/test_filter.c`
- `tests/firmware/test/test_decision/test_decision.c`, `tests/firmware/test/test_engine/test_engine.c`
- `tests/firmware/test/test_cmd_config/test_cmd_config.c`, `tests/firmware/test/test_msg/test_msg.cpp`
- `tests/firmware/test/test_sim_frd/test_sim_frd.c`, `tests/firmware/test/test_t01_t05_t07/test_t01_t05_t07.c`
- `tests/firmware/tools/run_native.py`, `tests/firmware/tools/check_features23.py`
- `tests/firmware/tools/check_filter23.py`, `tests/firmware/tools/filter_parity.c`, `tests/firmware/tools/check_model_adapter.py`

Tài liệu:

- `README.md`, `core/README.md`, `firmware/README.md`, `ml/README.md`, `ml/features/README.md`
- `ml/docs/M2_23_Features_ESP32_Integration.md`, `ml/docs/feature_specification_30.md`
- `ml/docs/preprocessing_design.md`, `ml/docs/feature_availability_matrix.md`
- `firmware/docs/CONTRACT_PROPOSALS.md`, `firmware/docs/M1-06_mqtt_json_decision.md`
- `firmware/docs/M1-08_resource_table.md`, `firmware/docs/M1_23_UPDATE_REPORT.md`
- `tests/firmware/README.md`, `tests/firmware/TEST_LOG.md`

Đã xóa các tài liệu/fixture 14 mục bị thay thế: `firmware/docs/features_clarification.md`,
`tests/firmware/tools/ref_features14.py`, `tests/firmware/golden/features_golden.json`,
`tests/firmware/test/test_features/golden_cases.h`.
Các thay đổi có sẵn trước lần chuyển đổi được giữ nguyên; danh sách này không nhận là đã thực hiện mọi thay đổi khác trong working tree.

Chưa commit/push. Commit gợi ý: `feat(firmware): implement versioned 23-feature motion pipeline`.
Có thể chia bàn giao theo M1-02/03 (pipeline/feature), M1-04/08 (decision/model), M1-09 (test/tài liệu).
