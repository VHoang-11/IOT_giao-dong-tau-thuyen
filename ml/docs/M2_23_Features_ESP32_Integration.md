
# SVMG – M2: Danh sách 23 đặc trưng cho ESP32

> **Phạm vi tích hợp đã chốt: 23 đặc trưng A/C/D/F trong tài liệu này.** Đọc file này trước, sau đó tra công thức tại
> [feature_specification_30.md](feature_specification_30.md). File công thức vẫn giữ 30 ứng viên để tham chiếu;
> chỉ triển khai 23 mục được liệt kê ở đây. M1 đã triển khai [contract 23 có version](../../contracts/features.md); vẫn chờ model RF và kiểm chứng thiết bị.

## 1. Tổng quan

M2 đã lựa chọn 23 đặc trưng góc làm đầu vào chính cho mô hình Random Forest nhận diện các kiểu chuyển động tàu (Motion Phenotype Classification).

Các đặc trưng được tính từ hai tín hiệu:
- Roll: góc lắc ngang của tàu.
- Pitch: góc lắc dọc của tàu.

Thông số thiết kế mục tiêu:
- Tần số tín hiệu đầu vào: 10 Hz.
- Đơn vị Roll/Pitch: độ (degree).
- Cửa sổ ngắn: 60 giây, tương ứng 600 mẫu.
- Cửa sổ dài: 180 giây, tương ứng 1.800 mẫu.
- Chu kỳ cập nhật feature: 10 giây.
- Chỉ sử dụng dữ liệu quá khứ và hiện tại.
- Thời gian khởi động: chưa đủ 180 giây thì chưa xuất vector 23 đặc trưng hoàn chỉnh.

Tổng cộng: 23 đặc trưng, chia thành 4 nhóm.

---

## 2. Nhóm A – Roll Statistics (60 giây)

8 đặc trưng.

| STT | Feature | Ý nghĩa |
|---|---|---|
| 1 | roll_rms_60 | RMS của góc Roll trên 60 giây |
| 2 | roll_std_60 | Độ lệch chuẩn Roll |
| 3 | roll_mean_60 | Giá trị trung bình Roll |
| 4 | roll_peak_to_peak_60 | Chênh lệch Roll lớn nhất và nhỏ nhất |
| 5 | roll_abs_p95_60 | Phân vị 95% của giá trị tuyệt đối Roll |
| 6 | roll_abs_max_60 | Giá trị tuyệt đối Roll lớn nhất |
| 7 | roll_iqr_60 | Khoảng tứ phân vị Roll (Q75 − Q25) |
| 8 | roll_diff_rms_60 | RMS của sai phân Roll giữa các mẫu liên tiếp |

Mục đích:
- Đo cường độ dao động Roll.
- Phân biệt độ lệch trung bình với dao động quanh trung bình.
- Phát hiện các biến động lớn hoặc thay đổi nhanh.

---

## 3. Nhóm C – Roll Offset (180 giây)

6 đặc trưng.

| STT | Feature | Ý nghĩa |
|---|---|---|
| 9 | roll_mean_180 | Trung bình Roll trong 180 giây |
| 10 | roll_median_180 | Trung vị Roll |
| 11 | roll_mean_abs_180 | Trung bình giá trị tuyệt đối Roll |
| 12 | roll_dominant_sign_ratio_180 | Tỷ lệ mẫu có dấu Roll chiếm ưu thế |
| 13 | roll_segment_mean_std_180 | Độ lệch chuẩn giữa các giá trị mean Roll theo đoạn |
| 14 | roll_mean_shift_180 | Mức thay đổi mean Roll giữa các đoạn của cửa sổ |

Mục đích:
- Phân tích Roll offset kéo dài.
- Đánh giá tính ổn định của độ lệch.
- Hỗ trợ nhận diện kiểu chuyển động PERSISTENT_OFFSET.

Lưu ý: Roll offset đo được không tự động đồng nghĩa tàu đang nghiêng nguy hiểm. Cần hiệu chuẩn mốc 0 của cảm biến.

---

## 4. Nhóm D – Roll Amplitude Growth (180 giây)

6 đặc trưng.

| STT | Feature | Ý nghĩa |
|---|---|---|
| 15 | roll_rms_early_60 | RMS Roll của 60 giây đầu trong cửa sổ 180 giây |
| 16 | roll_rms_late_60 | RMS Roll của 60 giây cuối |
| 17 | roll_rms_ratio_180 | Tỷ lệ RMS cuối/đầu |
| 18 | roll_rms_slope_180 | Độ dốc xu hướng RMS |
| 19 | roll_rms_trend_r2_180 | Hệ số R² của xu hướng RMS |
| 20 | roll_p95_trend_slope_180 | Độ dốc xu hướng phân vị 95% của Roll theo đặc tả M2 |

Mục đích:
- Nhận diện xu hướng tăng biên độ Roll.
- So sánh chuyển động ở đầu và cuối cửa sổ.
- Phân tích liệu dao động đang mạnh dần hay không.

Lưu ý:
- Cần dùng đúng công thức RMS, cách chia đoạn và đơn vị slope trong đặc tả Python.
- Không tự đổi sang centered RMS khi chưa cập nhật feature specification và huấn luyện lại mô hình.
- Nếu mẫu số gần 0, phải xử lý đúng epsilon theo đặc tả.

---

## 5. Nhóm F – Pitch Statistics (60 giây)

3 đặc trưng.

| STT | Feature | Ý nghĩa |
|---|---|---|
| 21 | pitch_rms_60 | RMS của góc Pitch |
| 22 | pitch_std_60 | Độ lệch chuẩn Pitch |
| 23 | pitch_peak_to_peak_60 | Chênh lệch Pitch lớn nhất và nhỏ nhất |

Mục đích:
- Bổ sung thông tin dao động dọc của tàu.
- Giúp mô hình phân tích chuyển động Roll trong bối cảnh Pitch.

---

## 6. Yêu cầu đối với firmware ESP32

### A. Đọc và xử lý dữ liệu IMU

- Đọc dữ liệu cảm biến IMU.
- Ước lượng Roll/Pitch từ dữ liệu cảm biến.
- Đảm bảo hệ trục và quy ước dấu nhất quán.
- Chuẩn hóa đầu ra Roll/Pitch về 10 Hz.
- Sử dụng đơn vị degree.
- Xử lý và báo trạng thái khi cảm biến lỗi hoặc thiếu dữ liệu.

### B. Quản lý cửa sổ dữ liệu

- Lưu lịch sử tối thiểu 180 giây.
- Dùng ring buffer hoặc giải pháp tương đương.
- Tính nhóm A/F từ cửa sổ 60 giây.
- Tính nhóm C/D từ cửa sổ 180 giây.
- Cập nhật vector 23 features mỗi 10 giây.
- Không sử dụng dữ liệu tương lai.

### C. Feature Extraction

- Implement chính xác 23 feature theo M2.
- Thống nhất công thức mean, RMS, std và quantile.
- Quy ước std là population standard deviation.
- Quantile theo Type-7 như đặc tả M2.
- Thống nhất quy tắc chia đoạn và tính slope.
- Thống nhất xử lý NaN, Inf và thiếu mẫu.
- Thứ tự feature phải khớp chính xác schema của model RF.

### D. Model Integration

- Nhận đủ 23 feature trước khi inference.
- Kiểm tra schema/version của model.
- Trả về kết quả motion phenotype classification.
- Không gọi kết quả là cảnh báo nguy hiểm đã xác minh.
- Báo WARMUP/INVALID nếu chưa có vector hợp lệ.

### E. Kiểm thử

- So sánh kết quả từng feature giữa Python và C/C++.
- Dùng cùng một chuỗi Roll/Pitch đầu vào.
- Kiểm tra sai số số thực.
- Kiểm tra bộ nhớ RAM, Flash và thời gian inference.
- Kiểm tra thời gian khởi động và dữ liệu thiếu.
- Đánh giá ảnh hưởng của bộ lọc và thuật toán ước lượng góc.

---

## 7. Phân công tích hợp

M2 – Machine Learning:
- Chốt 23 feature definitions.
- Cung cấp feature schema/version.
- Huấn luyện Random Forest.
- Cung cấp model artifact.
- Cung cấp dữ liệu và expected outputs phục vụ parity tests.

M1 – ESP32/Firmware:
- Kiểm tra cảm biến và thiết kế phần cứng.
- Đọc IMU và ước lượng Roll/Pitch.
- Thiết kế bộ đệm dữ liệu.
- Implement 23 feature trong firmware.
- Tích hợp Random Forest sau khi model được chốt.
- Đo RAM, Flash và inference latency.

Hai bên phối hợp:
- Chốt C feature contract phiên bản mới.
- Thống nhất thứ tự 23 features.
- Kiểm tra Python/C feature parity.
- Thử nghiệm trên ESP32 thật.

## 8. Tài liệu cần đối chiếu

- [Công thức 30 ứng viên — chỉ lấy 23 mục đã chọn](feature_specification_30.md)
- [Thiết kế preprocessing](preprocessing_design.md)
- [Ma trận tín hiệu khả dụng](feature_availability_matrix.md)
- [Feature contract hiện hành](../../contracts/features.md)
- [C interface hiện hành](../../core/include/svmg_core.h)
- [Các việc M1 cần cập nhật](../../firmware/README.md#chuyển-sang-23-đặc-trưng-theo-m2)

Danh sách 23 feature trên là mục tiêu tích hợp mới của M2.
Bản triển khai M1 dùng contract `svmg-angle-23-v1`; M2 cần xuất model cùng thứ tự và xác nhận các quy ước vận hành trong contract.
