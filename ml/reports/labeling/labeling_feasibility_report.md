# Nghiên cứu tính khả thi gán nhãn — SVMG M2

## Kết luận tổng quát

Dữ liệu hiện có cần được đánh giá theo evidence riêng cho mỗi lớp. Không có annotation external reference hoặc quyết định human review trong artifact đầu ra hiện tại. Quy tắc mặc định không suy diễn nhãn từ phân vị dữ liệu. Hàng chưa có tham chiếu giữ `UNLABELED`; điều này phản ánh thiếu bằng chứng gán nhãn, không khẳng định lớp vật lý không tồn tại.

## Kiểm kê cửa sổ hợp lệ

Một cửa sổ được đưa vào nghiên cứu khi đủ 180 giây trong cùng session/segment, endpoint theo `(t-W,t]`, và toàn bộ 23 feature góc được đánh dấu `VALID`. Stride 10 giây làm cửa sổ chồng lấn mạnh; số cửa sổ không phải số mẫu độc lập.

## Đối chiếu feature input thực tế

Artifact đang được dùng có 30 candidate columns. Số feature có ít nhất một hàng validity `VALID` được tính lại từ Parquet metadata; đây không đồng nghĩa đủ dữ liệu ở mọi cửa sổ hay đủ nhãn. 23 angle-only feature là subset được sử dụng để chọn cửa sổ 180 giây. Bốn gyro candidates không được xem là đo canonical hợp lệ do Hohai thiếu gyro, còn Seafar/Southampton mapping chưa xác nhận.

| Nguồn | Candidate feature | Feature từng có VALID | Gyro feature VALID | Cửa sổ angle-only 180 giây |
|---|---:|---:|---:|---:|
| Seafar | 30 | 26 | 0 | 1,318 |
| Hohai | 30 | 26 | 0 | 1,512 |
| Southampton | 30 | 26 | 0 | 34 |

Đặc biệt, ba candidate chu kỳ (`roll_period_est_180`, `roll_zero_crossings_180`, `roll_period_cv_180`) có thể có validity `VALID`, nhưng bị loại khỏi tập angle-only 23 theo thiết kế. Không dùng gyro suy ra hoặc trường chưa xác nhận để tạo nhãn.

| Nguồn | Candidate 60 giây | Cửa sổ 180 giây angle-only hợp lệ | Session hỗ trợ | Segment | Nhãn đã xác minh | Human review |
|---|---:|---:|---:|---:|---:|---:|
| Seafar | 1,384 | 1,318 | 1 | 4 | 0 | 0 |
| Hohai | 1,764 | 1,512 | 21 | 1 | 0 | 0 |
| Southampton | 277 | 34 | 1 | 1 | 0 | 0 |

## Bằng chứng và khả năng bao phủ lớp

### Seafar

- Nguồn tàu thực; audit không ghi nhận event/ground-truth annotation.
- Roll có offset trung bình dương; không lấy zero-centered làm NORMAL.
- Chỉ một session, nhiều segment do timestamp trùng/gap; không có xác nhận sự kiện vận hành.

Thống kê mô tả trên cửa sổ angle-only 180 giây:

- Roll mean 180s: trung bình 3.3098°, trung vị 3.2907°, P05–P95 3.0672–3.5431°.
- Roll standard deviation 60s: trung vị 0.095261°, P95 0.28509°.
- Roll RMS slope 180s: trung vị 0.00074861°/phút; R² trung vị 0.63585.
- Các giá trị trên mô tả phân bố; không được dùng làm ngưỡng hazard hoặc lớp NORMAL.

### Hohai

- 21 sheet là 21 session thực nghiệm riêng; roll/pitch degree, sample rate 50 Hz theo tài liệu được cung cấp.
- Không có gyro đo trực tiếp và workbook không có timestamp để kiểm tra dropout.
- Tên loại/thử nghiệm không được coi là nhãn nguy hiểm; PDF nguồn đã được báo cáo là không parse được trong audit.

Thống kê mô tả trên cửa sổ angle-only 180 giây:

- Roll mean 180s: trung bình 0.015181°, trung vị -0.0020993°, P05–P95 -0.063894–0.10513°.
- Roll standard deviation 60s: trung vị 0.34009°, P95 0.53308°.
- Roll RMS slope 180s: trung vị 0.0049245°/phút; R² trung vị 0.52737.
- Các giá trị trên mô tả phân bố; không được dùng làm ngưỡng hazard hoặc lớp NORMAL.

### Southampton

- Dữ liệu mô hình KCS quy mô phòng thí nghiệm; Test Plan là ngữ cảnh sóng/thử nghiệm, không phải hazard label.
- 47 IMU runs, chỉ Run 14 đủ 180 giây theo audit.
- Điều kiện tần số/biên độ sóng không được chuyển trực tiếp thành nhãn; không ghép IMU với Lasso.
- Không có human review hoặc reference label được cung cấp.

Thống kê mô tả trên cửa sổ angle-only 180 giây:

- Roll mean 180s: trung bình 0.6936°, trung vị 0.69209°, P05–P95 0.682–0.70584°.
- Roll standard deviation 60s: trung vị 0.017848°, P95 0.10655°.
- Roll RMS slope 180s: trung vị 0.0070825°/phút; R² trung vị 0.76716.
- Các giá trị trên mô tả phân bố; không được dùng làm ngưỡng hazard hoặc lớp NORMAL.

## Đánh giá bốn lớp mục tiêu

| Lớp | Proxy windows | External verified | Human reviewed | Session có evidence độc lập |
|---|---:|---:|---:|---:|
| `NORMAL` | 0 | 0 | 0 | 0 |
| `HIGH_ROLL` | 0 | 0 | 0 | 0 |
| `PERSISTENT_OFFSET` | 0 | 0 | 0 | 0 |
| `AMPLITUDE_GROWTH` | 0 | 0 | 0 | 0 |

Chỉ được coi là có căn cứ độc lập khi có external reference hoặc human review. `NORMAL` phải dựa trên positive operating envelope; không suy NORMAL từ việc không phát hiện bất thường.

Không tạo class counts dựa trên percentile, không cân bằng lớp nhân tạo. Thông tin wave của Southampton chỉ lưu làm experimental context/provenance; Hohai type labels không được xem là nhãn nguy hiểm; Seafar không có event annotation được tìm thấy.

## Khả năng hỗ trợ từng nguồn

Seafar cung cấp tín hiệu tàu thật nhưng chỉ một session, offset nền không zero và có giới hạn đơn vị/trục đã nêu trong audit. Hohai và Southampton là thí nghiệm mô hình quy mô nhỏ, không đại diện trực tiếp cho giới hạn full-scale. Southampton chỉ có một run đủ 180 giây nên không thể đánh giá độ lặp của phenotype dài hạn. Không nguồn nào hiện có bằng chứng chấp nhận được cho nhãn NORMAL hoặc hazard ground truth.

## Hình chẩn đoán

- `seafar_representative_window.png`
- `seafar_offset_vs_oscillation.png`
- `hohai_representative_window.png`
- `hohai_offset_vs_oscillation.png`
- `southampton_representative_window.png`
- `southampton_offset_vs_oscillation.png`
- `comparison_roll_std.png`

## Giải thích kỹ thuật phục vụ vấn đáp

**Em đã làm gì?** Đối chiếu feature windows đã kiểm định với tài liệu/audit nguồn và tạo hàng khảo sát 180 giây theo session/segment. **Vì sao?** Cửa sổ dài phù hợp phân tích offset/growth, đồng thời ranh giới ngăn ghép dữ liệu độc lập. **Phương pháp?** Chỉ dùng thống kê mô tả và trạng thái validity; không đặt ngưỡng bằng percentile. **Kết quả?** Các nguồn có lần lượt 1.318, 1.512 và 34 cửa sổ đủ 23 feature góc, nhưng không có nhãn external/human. **Nếu tự gọi các cực trị là HIGH_ROLL?** Sẽ biến phân bố nội bộ thành ground truth vòng tròn và nhầm biến thiên với nguy hiểm. **Giới hạn?** Thiếu operating envelope, tiêu chí hazard, event annotation và human review; các cửa sổ chồng lấn không độc lập.
