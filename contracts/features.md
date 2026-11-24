# SVMG — Feature contract 23 góc (M1/M2)

Phiên bản triển khai M1 ngày 18/11/2026: **`svmg-angle-23-v1`**. Thay contract 14 đặc trưng.
Phạm vi do M2 chọn tại [tài liệu tích hợp](../ml/docs/M2_23_Features_ESP32_Integration.md).
Danh sách máy đọc được: [features23.json](features23.json); định nghĩa C duy nhất: [svmg_feature_schema.h](../core/include/svmg_feature_schema.h).

## Tín hiệu, thời gian và thứ tự

- Roll/Pitch theo **độ**, 10 Hz; lấy mẫu IMU 20 Hz, cửa sổ causal `(t-W,t]`, không vượt qua phiên/đoạn liên tục.
- 60 s = 600 mẫu; 180 s = 1.800 mẫu. Cập nhật vector mỗi 10 s. Nhóm A/F dùng 60 s cuối; C/D dùng 180 s.
- Lõi bỏ 2 s khởi động bộ lọc trước khi tích lũy lịch sử feature. Vector đầy đủ sớm nhất khoảng **182 s** sau khởi động/reset pipeline.
- Nhóm C/D chia thành đúng ba đoạn 60 s cũ → giữa → mới. Tâm thời gian `[30,90,150]` giây.
- Index **0–22** sau đây là thứ tự model; không sử dụng trực tiếp index của bảng 30 ứng viên.

| Index | Feature | Đơn vị |
|---|---|---|
| 0 | `roll_rms_60` | deg |
| 1 | `roll_std_60` | deg |
| 2 | `roll_mean_60` | deg |
| 3 | `roll_peak_to_peak_60` | deg |
| 4 | `roll_abs_p95_60` | deg |
| 5 | `roll_abs_max_60` | deg |
| 6 | `roll_iqr_60` | deg |
| 7 | `roll_diff_rms_60` | deg/sample |
| 8 | `roll_mean_180` | deg |
| 9 | `roll_median_180` | deg |
| 10 | `roll_mean_abs_180` | deg |
| 11 | `roll_dominant_sign_ratio_180` | dimensionless |
| 12 | `roll_segment_mean_std_180` | deg |
| 13 | `roll_mean_shift_180` | deg |
| 14 | `roll_rms_early_60` | deg |
| 15 | `roll_rms_late_60` | deg |
| 16 | `roll_rms_ratio_180` | dimensionless |
| 17 | `roll_rms_slope_180` | deg/min |
| 18 | `roll_rms_trend_r2_180` | dimensionless |
| 19 | `roll_p95_trend_slope_180` | deg/min |
| 20 | `pitch_rms_60` | deg |
| 21 | `pitch_std_60` | deg |
| 22 | `pitch_peak_to_peak_60` | deg |

## Công thức đã triển khai

Công thức chi tiết tham chiếu [đặc tả M2](../ml/docs/feature_specification_30.md), với quy ước vận hành khớp
`ml/features/config.yaml` và `ml/features/extractor.py` tại thời điểm triển khai:

- RMS = `sqrt(mean(x²))`, **quanh 0**, không đổi thành centered RMS. Std chia N, tính ổn định qua hai lượt.
- Quantile Type-7: `h=(n-1)p`, nội suy hai phần tử lân cận sau sắp xếp. IQR dùng Roll có dấu; P95 dùng |Roll|.
- Sai phân dùng đúng cặp mẫu liên tiếp 0,1 s; tối thiểu **570/599 cặp**. Không nối qua NaN/mẫu thiếu; không chia sai phân cho dt.
- Tối thiểu **570/600** và **1.710/1.800** mẫu hữu hạn. Theo extractor Python hiện có, cả tám đặc trưng chia đoạn C/D
  đều không hợp lệ nếu một trong ba đoạn không đạt 570 mẫu; không xuất riêng giá trị late khi block early bị thiếu.
- `roll_mean_shift_180 = mean_late - mean_early`; std giữa đoạn chia 3.
- Hai slope xuất **deg/min**. Với ba tâm cách đều, slope RMS = `(rms_late-rms_early)/2`.
- Ratio không xác định khi RMS early ≤ **1e-9 độ** (epsilon số học đang dùng trong Python, chưa phải ngưỡng nhiễu phần cứng).
- R² không xác định khi SST ≤ **1e-15**; các giá trị hữu hạn được kẹp [0,1] cho sai số làm tròn.
- Dominant-sign ratio bỏ exact zero; không có deadband ngầm; toàn zero → không xác định.
- `roll_rms_60` và `roll_rms_late_60` trùng nhau theo thiết kế danh sách M2. Chỉ M2 đổi model/contract mới được loại một mục.

## Chất lượng và giá trị không xác định

`data_quality_pct`, `sensor_ok`, `valid_mask`, WARMUP/INVALID **nằm ngoài vector 23 số**.
Mỗi bit `valid_mask` tương ứng một index. Bit chỉ bật khi đáp ứng coverage và giá trị hữu hạn; đủ vector khi mask = `0x7fffff`.
Giữ NaN cho đại lượng không xác định; không thế bằng 0, không gửi vector đó vào RF. Không xuất NaN/Inf thành số JSON giả.

- Dữ liệu chưa đủ cửa sổ/không đạt 95% → UNKNOWN; lỗi cảm biến → FAULT, không mặc định NORMAL.
- Thiếu mẫu hoàn toàn 10 s (100 mẫu 10 Hz) → FAULT; chất lượng thô dưới 50% → FAULT.
- Một block 10 Hz chỉ được coi là đo hợp lệ khi đủ 2/2 mẫu IMU hợp lệ. NaN của từng kênh không được biến thành số 0.
- Khoảng trống timestamp thô > 0,075 s (1,5 × 20 Hz), thời gian đi lùi hoặc đổi nguồn → reset lịch sử và warmup.
  Đây là chính sách bảo thủ trước resampling; không nối khoảng trống vượt 0,15 s trên lưới 10 Hz.
- API `svmg_features_from_series` chỉ nhận lưới 10 Hz cố định đã phân đoạn. Bên gọi phải xử lý timestamp/gap trước;
  mảng không mang timestamp nên không thể tự suy ra một mẫu đã bị xóa khỏi chuỗi.

## Tiền xử lý và model

Preprocessing **`imu-cf-bw4-20to10-v1`**: MPU6050 ±2 g/±250°/s, DLPF ~10 Hz; bộ lọc bù τ=7,5 s;
Butterworth causal bậc 4, fc=4 Hz tại fs=20 Hz; giảm mẫu 2:1, khởi tạo filter tại giá trị đầu, bỏ 2 s đầu khỏi lịch sử feature.
Bộ lọc đã đối chiếu với SciPy. Hệ trục M1: Z lên; Roll `atan2(ay,az)`, Pitch `atan2(-ax,sqrt(ay²+az²))`.
Mẫu mô phỏng FRD của M2 phải qua adapter đổi trục, không đổi dấu tùy ý.

`model.h` cần khai báo `SVMG_MODEL_N_FEATURES=23`, `SVMG_MODEL_FEATURE_SCHEMA_VERSION`,
`SVMG_MODEL_PREPROCESSING_VERSION`, `SVMG_MODEL_VERSION` và `model_predict(const float*,int)` trả 0–3.
Metadata thiếu/sai hoặc đầu vào không hữu hạn → không dùng RF; firmware báo UNKNOWN hoặc fallback Baseline B đã chỉ rõ.
M2 phải xuất model cùng thứ tự, công thức, quy tắc INVALID và xác nhận tiền xử lý/lắp đặt cảm biến phù hợp.
Chưa có model RF thật trong repo; bộ sinh C M2 vẫn chưa bàn giao.

## Giữ độc lập an toàn và tương thích

Ngưỡng cứng, LED/còi, ACK/mute, TTL và bộ đệm sự kiện không phụ thuộc RF hay mạng.
Baseline B dùng `roll_std_60`, mean 60/180 s, slope và sign ratio trong bộ 23. Thời lượng offset tương đương là heuristic,
không phải thời gian heel liên tục đo được; `grow_max_heel_s` được giữ cho tương thích nguồn tham số và không còn dùng.
Tham số Baseline/MAI hiện là demo, cần M2 hiệu chỉnh lại. Không coi nhãn chuyển động là mức nguy hiểm hàng hải đã xác minh.
Tên trường telemetry hiện có được giữ; số chưa xác định ở các trường thống kê tùy chọn được bỏ.
Status/health bổ sung schema/preprocessing version, feature count; health có validity mask và data status.

## Kiểm chứng

```bash
python tests/firmware/tools/run_native.py
python tests/firmware/tools/check_features23.py
python tests/firmware/tools/check_filter23.py
python tests/firmware/tools/check_model_adapter.py
python tests/firmware/tools/validate_messages.py
python tests/firmware/tools/crosscheck_crc.py
```

C lưu float32, cộng dồn moments bằng double và dùng workspace tĩnh 7.200 byte; parity kiểm với Python thực tế,
không phải chỉ một bản công thức Python viết lại. Dung sai feature `atol=2e-5, rtol=2e-5` trên cùng đầu vào float32.
