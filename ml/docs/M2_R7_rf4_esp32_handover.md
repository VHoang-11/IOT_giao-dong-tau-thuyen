# M2-R7 – Hướng dẫn bàn giao: RF bốn lớp đóng băng chạy trên ESP32/Wokwi (chế độ SHADOW)

**Mô hình:** `svmg-rf-four-class-m2r6a-0.1.0` (15 cây, độ sâu 4, 23 đặc trưng `svmg-angle-23-v1`, preprocessing
`imu-cf-bw4-20to10-v1`, lớp 0 NORMAL · 1 HIGH_ROLL · 2 PERSISTENT_OFFSET · 3 AMPLITUDE_GROWTH, UNKNOWN khi conf < 0,5).
Header C99 đóng băng SHA-256 `f83d07cc1ed4b3d55b89933ba545425d7da7acf3eaa4e2f06021b505f342dd09`. Dữ liệu huấn luyện `SIMULATION`,
nhãn proxy; Test-G1 (một lần) macro-F1 hiệu dụng 0,816, precision AMPLITUDE_GROWTH 0,34. **Không phải bộ phân loại an toàn hàng hải.**

## Kiến trúc

```
MPU6050 (I2C, 20 Hz) -> task lấy mẫu SVMG_ACQ_TASK -> Core C (lọc, 10 Hz, cửa sổ 60/180 s) -> 23 đặc trưng
  -> svmg_features_status + svmg_features_vector_valid (đủ 23/23, hữu hạn, sẵn sàng)
  -> infer_predict (firmware/src/infer.cpp) -> model_predict_conf (model.h) -> cls_rf (UNKNOWN nếu conf < 0,5 hoặc lỗi)
  -> Baseline B (cls_b) + an toàn cứng phi_hard -> cls_primary = cls_b  (RF chỉ SHADOW, không điều khiển cảnh báo)
```

- Env `esp32dev_rf4_shadow` = `esp32dev` + `SVMG_DIAG_FEATURES` + `SVMG_ACQ_TASK` + `SVMG_RF_SHADOW`, thêm `-I` tới thư mục
  `model.h` đã kiểm SHA. Production `esp32dev` **không đổi** (các section không phải debug trùng bản build HEAD) và vẫn dùng stub.
- `SVMG_RF_SHADOW` (chỉ env này): mô hình chính luôn là `BASELINE_B` (lúc khởi động, khi áp cấu hình, lệnh đổi sang RF bị từ chối
  `UNSUPPORTED`); thêm dòng Serial `M,` sau mỗi lần cập nhật đặc trưng.
- Không đặt `model.h` vào `ml/export/`: mọi env firmware có `-I../ml/export`, nên file ở đó sẽ âm thầm thay stub cả production.

## Tạo lại và kiểm tra model.h

```bash
.venv/bin/python -m ml.export.prepare_firmware_model_m2r7   # sinh lại từ model.joblib đã khóa, chỉ ghi nếu SHA đúng
shasum -a 256 ml/data/models/rf_four_class_m2r6/v03/firmware/model.h   # phải là f83d07cc…
```

Cần artifact M2-R6a (`ml/data/models/rf_four_class_m2r6/v03/model.joblib`, SHA `3d7ecf31…`; tạo lại bằng
`python -m ml.train.rf_four_class_m2r6` sau khi sinh dataset v0.3). Script dừng nếu SHA mô hình, tau hay header khác bản đóng băng.
Pre-script PlatformIO `ml/export/pio_verify_rf4_model.py` dừng build nếu `model.h` thiếu hoặc khác SHA (không tự sinh).

## Build và chạy Wokwi

```bash
cd firmware && ../.venv/bin/pio run -e esp32dev_rf4_shadow
```

VS Code: dừng mọi simulator, `Wokwi: Select Config File` → `firmware/wokwi/wokwi.rf4_shadow.toml`, rồi `Wokwi: Start Simulator`
(RFC2217 cổng **4001**, khác cổng 4000 của HV01/M2-R4; nếu cổng cũ vẫn bị giữ: `Developer: Reload Window`; để tab simulator hiển
thị). Kiểm tra `lsof -nP -iTCP:4001` có LISTEN. Ghi Serial (chỉ đọc) ít nhất 240 s vì cửa sổ 180 s cần ~185 s để đủ 23 đặc trưng:

```bash
.venv/bin/python firmware/tools/wokwi_sensor_capture.py --port rfc2217://localhost:4001 --seconds 300 --run-id rf4_02
```

Kết quả: `ml/data/parity/wokwi_mpu6050/<run-id>/summary.json` (gitignored), mục `rf_shadow` và `checks`.

## Quan sát phân loại, UNKNOWN và fallback

- Khởi động: `[MODEL] status=AVAILABLE version=svmg-rf-four-class-m2r6a-0.1.0 kind=generated … requested=BASELINE_B active=BASELINE_B`.
- Mỗi 10 s: `M,t,mode,rf,b,primary,status,infer_last_us,infer_max_us,calls`. `rf` là lớp RF (UNKNOWN khi chưa đủ 23/23 đặc
  trưng, conf < 0,5 hoặc đầu vào lỗi); `primary` luôn bằng `b` (Baseline B). Dòng `T,` và `F,` giữ nguyên như M2-R4.
- Trước ~185 s: `rf=UNKNOWN`, `calls=0` (chưa đủ cửa sổ) – đúng contract, không bao giờ hiển thị NORMAL thay cho UNKNOWN.
- Fallback: xóa/đổi `model.h` → build dừng; build env `esp32dev` (stub) → `[MODEL] status=STUB … active=BASELINE_B`, `class_rf=UNKNOWN`.
- Bốn lớp: thanh trượt MPU6050 của Wokwi chủ yếu tạo nghiêng tĩnh (NORMAL/PERSISTENT_OFFSET). Chế độ SIMULATION của firmware là
  **stub sóng sin của M1**, không phải bộ sinh M2: chỉ để xem đường ống chạy, không phải bằng chứng độ chính xác. Bằng chứng bốn lớp
  + UNKNOWN trên đúng `infer.cpp` + `model.h`: test host `ml/export/tests/test_firmware_rf4_adapter.py` (773 vector Validation/S0b,
  vector **replay**, không phải cảm biến).

## Trạng thái xác minh (M2-R7, 2026-11-24)

| Hạng mục | Kết quả |
|---|---|
| `model.h` sinh lại từ mô hình khóa | SHA `f83d07cc…` đúng; build dừng nếu thiếu/khác SHA |
| Build `esp32dev_rf4_shadow` | SUCCESS, 0 cảnh báo; RAM 85 172 B (26,0 %), flash 1 094 679 B (34,8 %); ELF chứa version mô hình, không chứa stub |
| Chi phí RF so với `esp32dev_diag_acq` | `.flash.rodata` +3 360 B, `.flash.text` +668 B, RAM +0 |
| Production `esp32dev`, `esp32dev_diag_acq` | Mọi section không phải debug trùng bản build HEAD |
| `infer.cpp` thật + `model.h` (host, replay vector) | 773/773 khớp sklearn + tau trên Validation/S0b (đủ 4 lớp + UNKNOWN); 22 giá trị, NaN, inf → UNKNOWN |
| Wokwi end-to-end (MPU6050 → RF trên ESP32) | `rf4_01` nhận 0 byte (cổng 4000 do simulator khác giữ). Sau đó (cổng 4001): SIMULATION stub `rf4_sim_01` RF chạy, tối đa 719 µs; SENSOR đứng yên `rf4_02` chỉ 20/23 đặc trưng nên RF không được gọi. Chi tiết: `ml/docs/M2_handover.md` §7 |

## Cần M1 duyệt

`firmware/platformio.ini` (env mới), `firmware/src/app.cpp` (3 chỗ trong `#ifdef SVMG_RF_SHADOW`, 1 dòng `M,` trong diag),
`firmware/wokwi/wokwi.rf4_shadow.toml`, `firmware/tools/wokwi_sensor_capture.py`. Quyết định còn mở cho M1: có bật `SVMG_ACQ_TASK`
cho production không; cập nhật đặc trưng chặn loop ~0,5 s (M2-R4); có cho RF làm mô hình chính hay không (khuyến nghị: không).

## Giới hạn đã biết

- Nhãn/huấn luyện từ mô phỏng; chưa có Test-G2 hay dữ liệu MPU6050 thật; AMPLITUDE_GROWTH hay báo nhầm.
- Thời gian trên Wokwi không phải thời gian ESP32 thật; chưa đo trên phần cứng.
- Wokwi chỉ mô phỏng MPU6050 bằng thanh trượt, không tái tạo chuyển động tàu; bốn lớp chỉ kiểm chứng bằng replay vector trên host.
