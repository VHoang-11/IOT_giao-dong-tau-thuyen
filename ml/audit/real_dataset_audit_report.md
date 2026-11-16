# Real Dataset Audit — Smart Vessel Motion Guard

Ngày audit: 2026-11-16T08:58:17.131159+00:00. Đây là audit chất lượng dữ liệu chỉ đọc; không preprocessing, feature extraction, labeling hay training.

## 1. Tổng quan nguồn dữ liệu

| Nguồn | Phiên/run | Mẫu | Nhận xét |
|---|---:|---:|---|
| Seafar | 1 file/session | 143,318 | JSON có timestamp epoch ms, góc, angular rate và accelerometer. |
| Hohai | 21 sheet/session | 944,998 | Mỗi sheet là session riêng; sáu DOF, không có timestamp/gyro. |
| Southampton IMU | 47 run | 274,317 | CSV có timestamp, roll/pitch, acceleration và ba cột Delta Angle. |

Repository hiện chỉ có feature contract **14 trường** ở `contracts/features.md` (0–13) và `FeatureVector` C ở `core/include/svmg_core.h`, cùng 14 trường. `ml/README.md` cũng nói 14 feature. Không tìm thấy danh sách 30 feature ứng viên đã được phê duyệt. Bảng 30 mục dưới đây là **working inventory tạm suy ra từ nhóm tín hiệu người dùng nêu**, không thay đổi hợp đồng/định nghĩa và cần nhóm xác nhận.

## 2. Seafar

- Số bản ghi: **143,318**; có 16 cột, tất cả parse được dưới dạng numeric; tên cột: datetime, heading_degrees, rot_degrees_min, lat_degrees, lon_degrees, sog_kph, roll_degrees, pitch_degrees, yaw_degrees, roll_rate_rad_min, pitch_rate_rad_min, yaw_rate_rad_min, accel_x_ms2, accel_y_ms2, accel_z_ms2, yaw_rate_degrees_min.
- Timestamp: Unix epoch milliseconds; khoảng 2022-02-15T10:23:35+00:00–2022-02-15T14:22:27.600000+00:00; thời lượng quan sát 14332.600 s; median dt 0.100000 s, xấp xỉ 10.000 Hz.
- Duplicate timestamp: 14; bước không tăng: 14; time gap >1.5× median dt: 17; segment liên tục đủ 60 s: 7; đủ 180 s: 4.
- Roll (degree): min 2.18, max 4.65, mean 3.313186201314502, std 0.23508972977661627.
- Pitch (degree): min 0.39, max 1.21, mean 0.840076054647487, std 0.10873763186885595.
- Angular rate và accelerometer phân bố trên toàn session:

| Cột | Min | Max | Mean | Std |
|---|---:|---:|---:|---:|
| roll_rate_rad_min | -1.81 | 0.81 | -7.31939e-05 | 0.0936983 |
| pitch_rate_rad_min | -0.23 | 0.28 | -8.48463e-05 | 0.0211589 |
| yaw_rate_rad_min | -1.6 | 1.73 | 0.00629544 | 0.240676 |
| yaw_rate_degrees_min | -91.6732 | 99.1217 | 0.360702 | 13.7897 |
| accel_x_ms2 | -0.18638 | 0.18455 | 0.000236322 | 0.0130706 |
| accel_y_ms2 | -1.4237 | 0.48757 | -0.000485179 | 0.0194131 |
| accel_z_ms2 | -0.10367 | 0.1216 | 0.00181457 | 0.0120707 |
- Missing/non-finite theo cột: {"datetime": 0, "heading_degrees": 0, "rot_degrees_min": 0, "lat_degrees": 0, "lon_degrees": 0, "sog_kph": 0, "roll_degrees": 0, "pitch_degrees": 0, "yaw_degrees": 0, "roll_rate_rad_min": 0, "pitch_rate_rad_min": 0, "yaw_rate_rad_min": 0, "accel_x_ms2": 0, "accel_y_ms2": 0, "accel_z_ms2": 0, "yaw_rate_degrees_min": 0}.
- Tốc độ roll/pitch/yaw được ghi rad/min; có thêm yaw rate degree/min. Đơn vị gia tốc được gợi ý từ tên `*_ms2`, nhưng metadata không xác nhận. Cần rà soát mức gia tốc rất nhỏ/độ tin cậy hiệu chuẩn.

## 3. Hohai

- Workbook có **21 sheet/session**, mỗi sheet 6 cột: `Sway, Surge, Heave, Roll, Pitch, Yaw`; mẫu/sheet: 44,999–45,000.
- Sáu cột giá trị đọc được dưới dạng numeric; unit của góc không thể xác nhận từ workbook.
- Workbook không có timestamp; sample interval được gán **0.02 s (50 Hz)** theo metadata do người dùng cung cấp từ tài liệu `ml/data/raw/hohai/Data Description Example.pdf`. PDF đúng tên/path và workbook đã được đối chiếu; môi trường thiếu `pypdf`, `PyPDF2`, `pdfminer`, `pdfplumber`, `fitz`, nên PDF **không được parse** trong lần audit này. Inventory ghi rõ nguồn xác nhận và giới hạn này.
- Metadata đơn vị: Roll/Pitch/Yaw = degree; Surge/Sway/Heave = meter. Đây là metadata tài liệu được cung cấp, không suy luận từ workbook.
- Thời lượng mỗi session tính theo `(N - 1) / 50 Hz`: 899.96–899.98 s. Sheet đủ 60 s: 21/21; đủ 180 s: 21/21.
- Số sheet có missing/non-finite cell theo scan: 0/21.
- Roll/pitch thống kê gộp mô tả (độ): roll min/max/mean/std = -2.18/2.24/0.01411341611304998/0.3624924650979117; pitch = -0.53/0.51/0.0015432096152583814/0.0883603373292193.
- Roll/pitch là góc nhưng workbook không ghi unit; không có gyro trực tiếp. Không xem đạo hàm góc là gyro đo.
- Phân bố roll/pitch theo sheet nằm trong `dataset_inventory.json` (min/max/mean/std/p05/p95); các sheet giữ tách biệt.

## 4. Southampton

- Quét được **47 IMU CSV**, 47 Lasso CSV. Test Plan: 189 Run ID.
- Số run đủ uninterrupted 60 s: **47**; đủ 180 s: **1**. Run IDs 60s: [2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49]; 180s: [14].
- Timestamp gap, missing count và thống kê mỗi cột/run được ghi trong inventory chi tiết. Mỗi CSV là một run độc lập, không ghép run.
- Delta Angle unit row ghi `°.s^-1` (degree/s), dù tên cột có thể gợi ý delta angle. Đây là angular-rate column trực tiếp theo metadata của CSV, nhưng cần xác nhận ý nghĩa/định hướng trục và hiệu chuẩn.
- Khả năng matching IMU↔Lasso hiện chỉ theo run ID: 46 ID chung; chưa merge và chưa xác minh đồng bộ timestamp.
- Điều kiện sóng theo Test Plan có wave frequency/amplitude cho run numbers: [7, 8, 14, 17, 22, 24, 25, 27, 29, 30, 32, 33, 37, 39, 43, 45, 48, 49]. Có file IMU tương ứng: [7, 8, 14, 17, 22, 24, 25, 27, 29, 30, 32, 33, 37, 39, 43, 45, 48, 49]; đủ 60s: [7, 8, 14, 17, 22, 24, 25, 27, 29, 30, 32, 33, 37, 39, 43, 45, 48, 49]; đủ 180s: [14]. Đây chỉ là điều kiện thí nghiệm, không diễn giải thành nhãn ML.
- Tổng hợp roll/pitch/accelerometer/angular-rate trên 47 CSV (gộp thống kê để mô tả, không tạo chuỗi dữ liệu chung):

| Cột | Mẫu hợp lệ | Missing | Min | Max | Mean | Std |
|---|---:|---:|---:|---:|---:|---:|
| Roll | 274,317 | 0 | -1.0776 | 1.4456 | 0.378251 | 0.282633 |
| Pitch | 274,317 | 0 | -5.08615 | 4.33689 | 0.565863 | 1.18773 |
| Accelerometer X | 274,317 | 0 | -1.324 | 1.231 | 0.0892347 | 0.289537 |
| Accelerometer Y | 274,317 | 0 | -0.947 | 1.002 | -0.0654239 | 0.10331 |
| Accelerometer Z | 274,317 | 0 | -11.381 | -8.018 | -9.80533 | 0.322438 |
| Delta Angle X | 274,317 | 0 | -11.0081 | 12.7772 | 0.0546691 | 1.37293 |
| Delta Angle Y | 274,317 | 0 | -15.8866 | 15.432 | 0.0154669 | 3.98896 |
| Delta Angle Z | 274,317 | 0 | -2.0889 | 2.05008 | -0.0233088 | 0.308083 |
- Missing/non-finite tổng trên các cột: 0; timestamp gaps tổng: 0.

### Tóm tắt từng run IMU

| Run | Mẫu | Thời lượng (s) | Hz | Đủ 60s | Đủ 180s | Gap |
|---:|---:|---:|---:|:---:|:---:|---:|
| Run 2 | 5,816 | 116.30 | 50.000 | True | False | 0 |
| Run 3 | 8,735 | 174.68 | 50.000 | True | False | 0 |
| Run 4 | 6,556 | 131.10 | 50.000 | True | False | 0 |
| Run 5 | 6,003 | 120.04 | 50.000 | True | False | 0 |
| Run 6 | 4,235 | 84.68 | 50.000 | True | False | 0 |
| Run 7 | 5,077 | 101.52 | 50.000 | True | False | 0 |
| Run 8 | 4,551 | 91.00 | 50.000 | True | False | 0 |
| Run 10 | 4,633 | 92.64 | 50.000 | True | False | 0 |
| Run 11 | 7,425 | 148.48 | 50.000 | True | False | 0 |
| Run 12 | 4,976 | 99.50 | 50.000 | True | False | 0 |
| Run 13 | 7,439 | 148.76 | 50.000 | True | False | 0 |
| Run 14 | 25,684 | 513.66 | 50.000 | True | True | 0 |
| Run 15 | 4,993 | 99.84 | 50.000 | True | False | 0 |
| Run 16 | 5,066 | 101.30 | 50.000 | True | False | 0 |
| Run 17 | 4,821 | 96.40 | 50.000 | True | False | 0 |
| Run 18 | 4,824 | 96.46 | 50.000 | True | False | 0 |
| Run 19 | 4,938 | 98.74 | 50.000 | True | False | 0 |
| Run 20 | 4,935 | 98.68 | 50.000 | True | False | 0 |
| Run 21 | 5,003 | 100.04 | 50.000 | True | False | 0 |
| Run 22 | 5,509 | 110.16 | 50.000 | True | False | 0 |
| Run 23 | 5,232 | 104.62 | 50.000 | True | False | 0 |
| Run 24 | 6,352 | 127.02 | 50.000 | True | False | 0 |
| Run 25 | 6,047 | 120.92 | 50.000 | True | False | 0 |
| Run 26 | 6,797 | 135.92 | 50.000 | True | False | 0 |
| Run 27 | 5,968 | 119.34 | 50.000 | True | False | 0 |
| Run 28 | 5,607 | 112.12 | 50.000 | True | False | 0 |
| Run 29 | 4,978 | 99.54 | 50.000 | True | False | 0 |
| Run 30 | 6,110 | 122.18 | 50.000 | True | False | 0 |
| Run 31 | 4,759 | 95.16 | 50.000 | True | False | 0 |
| Run 32 | 5,019 | 100.36 | 50.000 | True | False | 0 |
| Run 33 | 6,000 | 119.98 | 50.000 | True | False | 0 |
| Run 34 | 4,473 | 89.44 | 50.000 | True | False | 0 |
| Run 35 | 4,874 | 97.46 | 50.000 | True | False | 0 |
| Run 36 | 5,203 | 104.04 | 50.000 | True | False | 0 |
| Run 37 | 5,024 | 100.46 | 50.000 | True | False | 0 |
| Run 38 | 4,819 | 96.36 | 50.000 | True | False | 0 |
| Run 39 | 4,370 | 87.38 | 50.000 | True | False | 0 |
| Run 40 | 4,476 | 89.50 | 50.000 | True | False | 0 |
| Run 41 | 4,963 | 99.24 | 50.000 | True | False | 0 |
| Run 42 | 4,567 | 91.32 | 50.000 | True | False | 0 |
| Run 43 | 5,342 | 106.82 | 50.000 | True | False | 0 |
| Run 44 | 4,867 | 97.32 | 50.000 | True | False | 0 |
| Run 45 | 4,472 | 89.42 | 50.000 | True | False | 0 |
| Run 46 | 5,105 | 102.08 | 50.000 | True | False | 0 |
| Run 47 | 5,348 | 106.94 | 50.000 | True | False | 0 |
| Run 48 | 5,509 | 110.16 | 50.000 | True | False | 0 |
| Run 49 | 6,817 | 136.32 | 50.000 | True | False | 0 |

## 5. Feature Availability Audit

Phân loại theo nguồn: `AVAILABLE` = tín hiệu/cadence cần thiết sẵn có cho phép tính trên segment đủ cửa sổ; `DERIVABLE_WITH_ASSUMPTIONS` = thiếu định nghĩa/đơn vị/tần số đã xác nhận; `UNAVAILABLE` = thiếu tín hiệu bắt buộc. Tên feature và cách tính vẫn chỉ là đề xuất kiểm kê, không phải định nghĩa được duyệt.

| Feature ứng viên | Tín hiệu | Cửa sổ | Seafar | Hohai | Southampton |
|---|---|---:|---|---|---|
| `roll_mean_60s` | roll | 60s | AVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE |
| `roll_std_60s` | roll | 60s | AVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE |
| `roll_rms_60s` | roll | 60s | AVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE |
| `roll_p95_abs_60s` | roll | 60s | AVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE |
| `roll_max_abs_60s` | roll | 60s | AVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE |
| `roll_zero_crossing_rate_60s` | roll | 60s | AVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE |
| `pitch_mean_60s` | pitch | 60s | AVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE |
| `pitch_std_60s` | pitch | 60s | AVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE |
| `pitch_rms_60s` | pitch | 60s | AVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE |
| `pitch_p95_abs_60s` | pitch | 60s | AVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE |
| `pitch_max_abs_60s` | pitch | 60s | AVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE |
| `pitch_zero_crossing_rate_60s` | pitch | 60s | AVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE |
| `roll_rate_mean_60s` | gyro_roll | 60s | DERIVABLE_WITH_ASSUMPTIONS | UNAVAILABLE | DERIVABLE_WITH_ASSUMPTIONS |
| `roll_rate_std_60s` | gyro_roll | 60s | DERIVABLE_WITH_ASSUMPTIONS | UNAVAILABLE | DERIVABLE_WITH_ASSUMPTIONS |
| `roll_rate_rms_60s` | gyro_roll | 60s | DERIVABLE_WITH_ASSUMPTIONS | UNAVAILABLE | DERIVABLE_WITH_ASSUMPTIONS |
| `pitch_rate_mean_60s` | gyro_pitch | 60s | DERIVABLE_WITH_ASSUMPTIONS | UNAVAILABLE | DERIVABLE_WITH_ASSUMPTIONS |
| `pitch_rate_std_60s` | gyro_pitch | 60s | DERIVABLE_WITH_ASSUMPTIONS | UNAVAILABLE | DERIVABLE_WITH_ASSUMPTIONS |
| `pitch_rate_rms_60s` | gyro_pitch | 60s | DERIVABLE_WITH_ASSUMPTIONS | UNAVAILABLE | DERIVABLE_WITH_ASSUMPTIONS |
| `accel_x_rms_60s` | accel_x | 60s | AVAILABLE | UNAVAILABLE | AVAILABLE |
| `accel_y_rms_60s` | accel_y | 60s | AVAILABLE | UNAVAILABLE | AVAILABLE |
| `accel_z_rms_60s` | accel_z | 60s | AVAILABLE | UNAVAILABLE | AVAILABLE |
| `persistent_roll_offset_180s` | roll | 180s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS |
| `persistent_pitch_offset_180s` | pitch | 180s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS |
| `roll_amplitude_growth_180s` | roll | 180s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS |
| `pitch_amplitude_growth_180s` | pitch | 180s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS |
| `roll_oscillation_period_60s` | roll | 60s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS |
| `pitch_oscillation_period_60s` | pitch | 60s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS |
| `roll_pitch_correlation_60s` | roll_pitch | 60s | AVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE |
| `roll_angular_acceleration_60s` | gyro_roll | 60s | DERIVABLE_WITH_ASSUMPTIONS | UNAVAILABLE | DERIVABLE_WITH_ASSUMPTIONS |
| `pitch_angular_acceleration_60s` | gyro_pitch | 60s | DERIVABLE_WITH_ASSUMPTIONS | UNAVAILABLE | DERIVABLE_WITH_ASSUMPTIONS |

Tổng feature ứng viên tạm thời: **30**. Trong đó các mục period, amplitude growth, persistence và angular acceleration cần quyết định thuật toán/ngưỡng/chất lượng; không thể gán số giả hay coi rate suy ra là gyro.

## 6. Vấn đề chất lượng, đồng bộ và đơn vị

- Hohai tần số và đơn vị dùng metadata tài liệu do người dùng cung cấp; vì không có per-sample timestamp, continuity/dropout không thể kiểm tra riêng cho từng sheet. PDF không được parse do thiếu dependency trong môi trường.
- Seafar rate dùng rad/min, Southampton degree/s; chuẩn hóa đơn vị chỉ nên diễn ra sau khi nhóm thống nhất trục/quy ước và xác minh nguồn. Seafar accel có giá trị rất nhỏ so với Southampton (xấp xỉ trọng lực ở trục Z), cần làm rõ scale/calibration/đơn vị.
- Southampton time stamp bắt đầu ở mốc khác nhau giữa runs; so sánh thời gian tuyệt đối giữa các nguồn/run không có căn cứ. Lasso có matching ID không đồng nghĩa đồng bộ thời gian.
- Chỉ định nghĩa gap dùng kiểm toán: step >1.5× median positive step; đây là cờ phát hiện để review, không phải dữ liệu đã được sửa.
- Missing values: Seafar bảng đếm theo field trong inventory; Southampton theo cột/run; Hohai theo sheet/cột. Không nội suy hay thay bằng 0.

## 7. Khuyến nghị nguồn

Southampton phù hợp nhất để đánh giá thực nghiệm roll/pitch dynamics trên cửa sổ 60/180 s: có timestamp, accelerometer và rate columns, nhiều run và Test Plan mô tả điều kiện. Chỉ dùng các run qua kiểm tra continuity và xác nhận đơn vị Delta Angle. Seafar hữu ích cho dữ liệu thực với timestamp và nhiều trường IMU nhưng cần xác minh scale/đơn vị và tính chất liên tục. Hohai có thể cung cấp cửa sổ thời gian dựa trên cadence 50 Hz được cung cấp; do workbook thiếu timestamp nên không thể kiểm chứng dropout/gap trong mỗi session.

## 8. Quyết định cần nhóm xác nhận

1. Phê duyệt danh sách/tên/định nghĩa của 30 ứng viên; hiện repository có contract 14 mục, không có danh sách 30 chính thức.
2. Hohai: khi có PDF reader, đối chiếu trực tiếp metadata 50 Hz/units với tài liệu; do workbook không có timestamp nên xác nhận cách chấp nhận giới hạn kiểm tra dropout/gap.
3. Southampton: xác nhận ý nghĩa cột Delta Angle, trục/quy ước dấu, scale và đồng hồ đồng bộ với Lasso.
4. Seafar: xác nhận đơn vị/calibration của accelerometer, nguồn đo rate và tiêu chuẩn quality/gap.
5. Chốt cách tính oscillation period, amplitude growth, persistent offset (threshold/duration), angular acceleration, detrending/filtering, và quy tắc minimum valid samples.
6. Chốt dùng feature contract 14 hiện tại hay quy trình thay đổi contract sau khi audit; không sửa contract trong bước này.

## 9. Tệp audit

- `ml/audit/audit_seafar.py`, `audit_hohai.py`, `audit_southampton.py`, `audit_all.py`.
- `ml/audit/dataset_inventory.json`: metadata/statistics tổng hợp, không chứa raw samples.
- Chạy lại từ repository root: `python -m ml.audit.audit_all`; kiểm thử: `python -m unittest ml.audit.test_audit -v`.
- Tệp raw không được chỉnh sửa. Không preprocessing, merge, labeling hay training.
