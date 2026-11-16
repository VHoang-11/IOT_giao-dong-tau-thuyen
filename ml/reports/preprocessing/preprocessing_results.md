# Báo cáo kết quả Data Preprocessing — SVMG

Ngày chạy: 2026-11-16T13:12:44.026037+00:00. Data Preprocessing (tiền xử lý dữ liệu) chuẩn hóa và kiểm định Time Series; pipeline không trích xuất 30 candidate features, không tạo nhãn và không huấn luyện Random Forest.

## A. Mục tiêu và nguồn dữ liệu

Pipeline đọc dữ liệu thực Seafar, Hohai 6-DOF và Southampton KCS IMU; giữ từng session/sheet/run độc lập. Báo cáo audit gốc: [Real Dataset Audit](../../audit/real_dataset_audit_report.md).

| Nguồn | Phiên đầu vào | Hàng nguồn | Hàng đầu ra | Segment đầu ra | Đủ 60 s | Đủ 180 s |
|---|---:|---:|---:|---:|---:|---:|
| Seafar | 1 | 143,318 | 143,264 | 24 | 7 | 4 |
| Hohai | 21 | 944,998 | 188,580 | 21 | 21 | 21 |
| Southampton | 47 | 274,317 | 53,942 | 47 | 47 | 1 |

## B. Môi trường và dependencies

Python `3.14.6`; NumPy `2.4.6`, pandas `3.0.3`, SciPy `1.18.0`, openpyxl `3.1.5`, PyArrow `23.0.1`, PyYAML `6.0.3`, Matplotlib `3.11.0`.
Môi trường hiện tại có các dependency cần thiết. Phiên bản cấu hình được ghi trong `preprocessing_summary.json`; cài đặt từ môi trường Python dự án như mô tả ở `ml/preprocessing/README.md`.

## C. Kết quả kiểm thử tự động: 18 bài, 18 đạt, 0 không đạt, 0 bỏ qua. Lệnh: `python -m pytest ml/preprocessing/tests -q`. Kết quả pytest: `18 passed in 1.62s`.

## D. Quy tắc làm sạch và lý do

- Sắp xếp timestamp ổn định; timestamp trùng có cùng giá trị tín hiệu thì giữ bản ghi đầu. Nếu cùng timestamp nhưng tín hiệu xung đột, loại toàn bộ nhóm timestamp đó; không lấy trung bình.
- Loại hàng có timestamp, Roll hoặc Pitch thiếu/không hữu hạn; gyro là nullable nên thiếu gyro không làm rơi hàng.
- Phân đoạn tại khoảng thời gian lớn hơn 1,5 lần median chu kỳ mẫu; tuyệt đối không lọc/resample qua gap hoặc ranh giới phiên.
- Không nội suy và không điền 0. Resampling dùng mẫu trước gần nhất trên lưới đích (zero-order hold có giới hạn tuổi), nên không đọc mẫu tương lai.
- Các kênh liên tục dạng số hữu hạn ở dữ liệu 50 Hz được lọc Butterworth thông thấp causal dạng SOS trước khi lấy mẫu 10 Hz; trường hậu tố `_raw` được giữ nguyên theo nguồn. Khởi tạo trạng thái ở steady state theo mẫu đầu, bỏ 2 s warmup; không bù pha vì bù pha causal có thể cần dữ liệu tương lai.
- Không fit scaler/imputer toàn cục; không xử lý theo nhãn; không tạo split Train/Test.

## E. Chuyển đổi đơn vị và nguồn tín hiệu gyro

Roll/Pitch đã ở degree ở cả ba nguồn. Hohai dùng metadata tài liệu: 50 Hz, Roll/Pitch/Yaw degree, Surge/Sway/Heave meter; thời gian được suy từ sample index và không thể phát hiện dropout. Seafar rate fields có tên đơn vị rad/min; pipeline chuyển `roll_rate_rad_min` và `pitch_rate_rad_min` sang rad/s bằng chia 60, giữ nguyên dấu và ghi rõ phần cứng/trục/dấu chưa xác nhận. Southampton `Delta Angle X/Y` có unit row degree/s nhưng ý nghĩa vật lý chưa đủ rõ; giữ các trường raw thêm và để gyro canonical missing. Hohai cũng không có gyro đo. Không dùng đạo hàm Roll/Pitch làm gyro.

## F. Tần số lấy mẫu, bộ lọc và Resampling

Cấu hình: target `10.0 Hz`, Butterworth order `4`, cutoff `4.0 Hz`, causal SOS, warmup `2.0 s`, gap threshold `1.5× median dt`.
Đây là baseline thực nghiệm 10 Hz/4 Hz. Đáp ứng lý thuyết chỉ suy giảm khoảng 8,8 dB tại Nyquist đầu ra 5 Hz; chưa đủ cơ sở tuyên bố anti-alias đã được xác nhận đầy đủ. Giai đoạn kế tiếp cần so sánh bộ lọc mạnh hơn và đánh giá độ ổn định của feature theo cấu hình lọc/tần số lấy mẫu.
Số liệu dưới đây là phép so sánh cùng timestamp đầu ra: giá trị nguồn tại mẫu trước gần nhất so với giá trị đã lọc. RMSE đo sai khác tuyệt đối cùng đơn vị; tỷ lệ RMS sau/trước mô tả thay đổi biên độ. Đây là diagnostics, không phải ngưỡng an toàn.

## G. So sánh thống kê trước/sau

### Seafar

Đầu vào: `143,318` hàng; sau xử lý timestamp trùng `143,290`; sau kiểm tra trường bắt buộc `143,290`; đầu ra `143,264` hàng trên 1 phiên. Loại duplicate đồng nhất: 0; loại 28 hàng thuộc 14 nhóm timestamp xung đột; loại thiếu/không hữu hạn trường bắt buộc: 0; bỏ segment ngắn dưới 1.0 s: 8 segment / 10 hàng; giảm mẫu/warmup/regularization: 16 hàng.
Phát hiện 31 gap, sắp xếp lại 0 hàng timestamp, 32 segment đầu vào; xuất 24 segment riêng. Sampling Rate median 10 → 10 Hz; median jitter ratio 0. Cửa sổ đủ 60 s: 7; đủ 180 s: 4. Thời lượng cumulative trước 14332.60 s (tổng span phiên, có thể chứa gap), sau 14324.00 s (tổng span segment giữ). Missing Roll trước/sau 0%/0%; Pitch 0%/0%.

| Tín hiệu | Thống kê | Trước | Sau |
|---|---|---:|---:|
Đối soát Seafar: `143,318 − 28` hàng xung đột `− 0` duplicate đồng nhất `− 0` invalid `− 10` hàng thuộc đoạn ngắn `= 143,280` hàng nguồn trong segment giữ. Lưới 10 Hz xuất `143,264` điểm, chênh đếm `16` điểm; đây là regularization/resampling, không phải hàng invalid. Rà soát timestamp xác nhận không có target point invalid và Seafar không có filter warmup. Trong lần audit này, 16/24 segment có ít hơn một điểm lưới so với hàng nguồn; 8 segment giữ cùng số đếm.
| Roll (degree) | Số mẫu | 143318 | 143264 |
| Roll (degree) | Giá trị thiếu | 0 | 0 |
| Roll (degree) | Trung bình | 3.3131862 | 3.3131846 |
| Roll (degree) | Độ lệch chuẩn tổng thể | 0.23508973 | 0.23508698 |
| Roll (degree) | Nhỏ nhất | 2.18 | 2.18 |
| Roll (degree) | Lớn nhất | 4.65 | 4.65 |
| Roll (degree) | Phân vị 5% | 2.96 | 2.96 |
| Roll (degree) | Trung vị (P50) | 3.3 | 3.3 |
| Roll (degree) | Phân vị 95% | 3.7 | 3.7 |
| Roll (degree) | RMS | 3.3215162 | 3.3215144 |
| Roll (degree) | Đỉnh-đỉnh | 2.47 | 2.47 |
| Pitch (degree) | Số mẫu | 143318 | 143264 |
| Pitch (degree) | Giá trị thiếu | 0 | 0 |
| Pitch (degree) | Trung bình | 0.84007605 | 0.84005493 |
| Pitch (degree) | Độ lệch chuẩn tổng thể | 0.10873763 | 0.10873727 |
| Pitch (degree) | Nhỏ nhất | 0.39 | 0.39 |
| Pitch (degree) | Lớn nhất | 1.21 | 1.21 |
| Pitch (degree) | Phân vị 5% | 0.65 | 0.65 |
| Pitch (degree) | Trung vị (P50) | 0.85 | 0.85 |
| Pitch (degree) | Phân vị 95% | 1 | 1 |
| Pitch (degree) | RMS | 0.8470842 | 0.84706321 |
| Pitch (degree) | Đỉnh-đỉnh | 0.82 | 0.82 |

| Tín hiệu | Mẫu căn thời gian | RMSE | Tương quan | RMS trước | RMS sau | Tỷ lệ RMS sau/trước |
|---|---:|---:|---:|---:|---:|---:|
| Roll | 143264 | 0 | 1 | 3.3215 | 3.3215 | 1 |
| Pitch | 143264 | 0 | 1 | 0.84706 | 0.84706 | 1 |
| Gyro X | 143264 | 0 | 1 | 0.0015615 | 0.0015615 | 1 |
| Gyro Y | 143264 | 0 | 1 | 0.00035239 | 0.00035239 | 1 |

Gyro canonical: X `AVAILABLE`, Y `AVAILABLE`. Bảng đầy đủ theo phiên/run nằm trong `preprocessing_summary.json`.

### Hohai

Đầu vào: `944,998` hàng; sau xử lý timestamp trùng `944,998`; sau kiểm tra trường bắt buộc `944,998`; đầu ra `188,580` hàng trên 21 phiên. Loại duplicate đồng nhất: 0; loại 0 hàng thuộc 0 nhóm timestamp xung đột; loại thiếu/không hữu hạn trường bắt buộc: 0; bỏ segment ngắn dưới 1.0 s: 0 segment / 0 hàng; giảm mẫu/warmup/regularization: 756,418 hàng.
Phát hiện 0 gap, sắp xếp lại 0 hàng timestamp, 21 segment đầu vào; xuất 21 segment riêng. Sampling Rate median 50 → 10 Hz; median jitter ratio 0. Cửa sổ đủ 60 s: 21; đủ 180 s: 21. Thời lượng cumulative trước 18899.54 s (tổng span phiên, có thể chứa gap), sau 18855.90 s (tổng span segment giữ). Missing Roll trước/sau 0%/0%; Pitch 0%/0%.

| Tín hiệu | Thống kê | Trước | Sau |
|---|---|---:|---:|
| Roll (degree) | Số mẫu | 944998 | 188580 |
| Roll (degree) | Giá trị thiếu | 0 | 0 |
| Roll (degree) | Trung bình | 0.014113416 | 0.014095417 |
| Roll (degree) | Độ lệch chuẩn tổng thể | 0.36249247 | 0.36272402 |
| Roll (degree) | Nhỏ nhất | -2.18 | -2.1701927 |
| Roll (degree) | Lớn nhất | 2.24 | 2.2333397 |
| Roll (degree) | Phân vị 5% | -0.57 | -0.5695928 |
| Roll (degree) | Trung vị (P50) | 0 | 0.0079883497 |
| Roll (degree) | Phân vị 95% | 0.62 | 0.61789501 |
| Roll (degree) | RMS | 0.36276711 | 0.36299779 |
| Roll (degree) | Đỉnh-đỉnh | 4.42 | 4.4035324 |
| Pitch (degree) | Số mẫu | 944998 | 188580 |
| Pitch (degree) | Giá trị thiếu | 0 | 0 |
| Pitch (degree) | Trung bình | 0.0015432096 | 0.0015544307 |
| Pitch (degree) | Độ lệch chuẩn tổng thể | 0.088360337 | 0.088175288 |
| Pitch (degree) | Nhỏ nhất | -0.53 | -0.53279916 |
| Pitch (degree) | Lớn nhất | 0.51 | 0.51240003 |
| Pitch (degree) | Phân vị 5% | -0.15 | -0.14148087 |
| Pitch (degree) | Trung vị (P50) | 0 | 0.00053689984 |
| Pitch (degree) | Phân vị 95% | 0.15 | 0.1447858 |
| Pitch (degree) | RMS | 0.088373812 | 0.088188988 |
| Pitch (degree) | Đỉnh-đỉnh | 1.04 | 1.0451992 |

| Tín hiệu | Mẫu căn thời gian | RMSE | Tương quan | RMS trước | RMS sau | Tỷ lệ RMS sau/trước |
|---|---:|---:|---:|---:|---:|---:|
| Roll | 188580 | 0.1245 | 0.94111 | 0.36312 | 0.363 | 0.99966 |
| Pitch | 188580 | 0.027938 | 0.94997 | 0.088472 | 0.088189 | 0.9968 |
| Gyro X | 0 | — | — | — | — | — |
| Gyro Y | 0 | — | — | — | — | — |

Gyro canonical: X `UNAVAILABLE`, Y `UNAVAILABLE`. Bảng đầy đủ theo phiên/run nằm trong `preprocessing_summary.json`.

### Southampton

Đầu vào: `274,317` hàng; sau xử lý timestamp trùng `274,317`; sau kiểm tra trường bắt buộc `274,317`; đầu ra `53,942` hàng trên 47 phiên. Loại duplicate đồng nhất: 0; loại 0 hàng thuộc 0 nhóm timestamp xung đột; loại thiếu/không hữu hạn trường bắt buộc: 0; bỏ segment ngắn dưới 1.0 s: 0 segment / 0 hàng; giảm mẫu/warmup/regularization: 220,375 hàng.
Phát hiện 0 gap, sắp xếp lại 0 hàng timestamp, 47 segment đầu vào; xuất 47 segment riêng. Sampling Rate median 50 → 10 Hz; median jitter ratio 0. Cửa sổ đủ 60 s: 47; đủ 180 s: 1. Thời lượng cumulative trước 5485.40 s (tổng span phiên, có thể chứa gap), sau 5389.50 s (tổng span segment giữ). Missing Roll trước/sau 0%/0%; Pitch 0%/0%.

| Tín hiệu | Thống kê | Trước | Sau |
|---|---|---:|---:|
| Roll (degree) | Số mẫu | 274317 | 53942 |
| Roll (degree) | Giá trị thiếu | 0 | 0 |
| Roll (degree) | Trung bình | 0.37825116 | 0.37841911 |
| Roll (degree) | Độ lệch chuẩn tổng thể | 0.2826333 | 0.28287574 |
| Roll (degree) | Nhỏ nhất | -1.077604 | -1.0575532 |
| Roll (degree) | Lớn nhất | 1.445598 | 1.381815 |
| Roll (degree) | Phân vị 5% | -0.0392236 | -0.039879467 |
| Roll (degree) | Trung vị (P50) | 0.347153 | 0.34706572 |
| Roll (degree) | Phân vị 95% | 0.8345968 | 0.83440833 |
| Roll (degree) | RMS | 0.47218166 | 0.47246133 |
| Roll (degree) | Đỉnh-đỉnh | 2.523202 | 2.4393682 |
| Pitch (degree) | Số mẫu | 274317 | 53942 |
| Pitch (degree) | Giá trị thiếu | 0 | 0 |
| Pitch (degree) | Trung bình | 0.56586253 | 0.56801319 |
| Pitch (degree) | Độ lệch chuẩn tổng thể | 1.187733 | 1.190525 |
| Pitch (degree) | Nhỏ nhất | -5.086149 | -5.0841062 |
| Pitch (degree) | Lớn nhất | 4.336892 | 4.2932905 |
| Pitch (degree) | Phân vị 5% | -1.1948918 | -1.2005547 |
| Pitch (degree) | Trung vị (P50) | 0.51888 | 0.51928126 |
| Pitch (degree) | Phân vị 95% | 2.0699828 | 2.0797045 |
| Pitch (degree) | RMS | 1.3156405 | 1.3190864 |
| Pitch (degree) | Đỉnh-đỉnh | 9.423041 | 9.3773967 |

| Tín hiệu | Mẫu căn thời gian | RMSE | Tương quan | RMS trước | RMS sau | Tỷ lệ RMS sau/trước |
|---|---:|---:|---:|---:|---:|---:|
| Roll | 53942 | 0.13253 | 0.89041 | 0.47276 | 0.47246 | 0.99936 |
| Pitch | 53942 | 0.40527 | 0.94207 | 1.3191 | 1.3191 | 1 |
| Gyro X | 0 | — | — | — | — | — |
| Gyro Y | 0 | — | — | — | — | — |

Gyro canonical: X `UNAVAILABLE`, Y `UNAVAILABLE`. Bảng đầy đủ theo phiên/run nằm trong `preprocessing_summary.json`.

## H. Đánh giá lọc và giảm Sampling Rate

Band-power được tính bằng Welch trên từng segment trước/sau filter, ở cùng Sampling Rate nguồn. Low band dùng 0,1–2 Hz; out-of-band dùng từ 5,25 Hz tới Nyquist nguồn 25 Hz. Bảng dưới đây tổng hợp median và khoảng min–max qua các segment. Tỷ lệ low-band gần 1 biểu thị giữ năng lượng thấp tần; attenuation âm dB biểu thị giảm out-of-band. Đây là diagnostics, không phải ngưỡng an toàn.

| Nguồn / tín hiệu | Số segment | Tỷ lệ low-band median [min, max] | Attenuation out-of-band median dB [min, max] |
|---|---:|---:|---:|
| Seafar / Roll, Pitch | 0 | Không áp filter anti-alias | Không áp filter anti-alias |
| Hohai / roll_deg | 21 | 0.99991 [0.99938, 1.00042] | -24.690 [-25.563, -24.277] |
| Hohai / pitch_deg | 21 | 0.99995 [0.99945, 1.00034] | -23.748 [-24.160, -23.277] |
| Southampton / roll_deg | 47 | 0.99764 [0.99083, 1.00347] | -16.265 [-21.235, -13.449] |
| Southampton / pitch_deg | 47 | 0.99979 [0.99593, 1.01820] | -24.550 [-30.635, -18.573] |

Phép đo low-band là tỷ lệ tích phân PSD sau/trước trong cùng dải; attenuation là `10*log10(P_after/P_before)` trên 5,25–25 Hz tại đầu ra bộ lọc nhưng trước decimation. Chúng mô tả tác động của filter trên dữ liệu thật. Seafar khoảng 10 Hz không bị lọc/giảm mẫu, nên không có kiểm định chống alias 50→10. Các đường dẫn trong summary, provenance và inventory được ghi tương đối từ repository root để dùng trên clone khác.

### Hình chẩn đoán

- `ml/data/processed/diagnostics/roll_raw_processed.png` — So sánh tín hiệu Roll trước và sau tiền xử lý; dữ liệu đại diện theo từng nguồn.
- `ml/data/processed/diagnostics/pitch_raw_processed.png` — So sánh tín hiệu Pitch trước và sau tiền xử lý; dữ liệu đại diện theo từng nguồn.
- `ml/data/processed/diagnostics/timestamp_gaps_segments.png` — Khoảng cách timestamp trên dữ liệu đầu vào; đường ngang biểu thị ngưỡng gap của cấu hình.
- `ml/data/processed/diagnostics/signal_distributions.png` — Phân bố Roll/Pitch trước xử lý và sau xử lý; histogram mô tả biến đổi do lọc/lấy mẫu.
- `ml/data/processed/diagnostics/resampling_frequency_diagnostics.png` — Mật độ phổ công suất trước/sau; đường Nyquist cho lưới đầu ra.

## I. Kiểm định chất lượng và window eligibility

- Eligibility được tính riêng trên mỗi segment sau processing: timestamp đầu-cuối phải phủ ít nhất 60/180 s; không cộng dồn qua gap/session. Lưới đích chứa mẫu endpoint nếu endpoint nằm đúng grid; mỗi cửa sổ trailing dùng quy ước `(t-W, t]`.
- Số dòng thiếu/non-finite đầu ra và rate jitter theo từng segment được lưu trong JSON; kênh gyro missing được giữ NaN/null, không điền.
- Filter response được đo trên tín hiệu thực và kiểm tra độc lập bằng sine fixtures: chi tiết định lượng và số kiểm thử được cập nhật sau lần chạy suite cuối.
- Cumulative duration trước/sau có ý nghĩa khác nhau khi có gaps: trước là span thời gian phiên; sau cộng span các segment được giữ. Không diễn giải chênh lệch này như dữ liệu thời gian bị tạo mới.

## J. Hạn chế còn lại

1. Seafar có timestamp trùng/gap; duplicate conflict được loại cả nhóm theo chính sách tất định. Unit field name rate cho biết rad/min, nhưng nguồn cảm biến, body axis và quy ước dấu chưa xác nhận.
2. Hohai không có timestamp; relative time và continuity là suy luận từ 50 Hz tài liệu. Không thể xác nhận mất mẫu bên trong sheet.
3. Southampton chỉ có Run 14 đủ 180 s. `Delta Angle` chưa map sang gyro canonical; không merge Lasso.
4. Causal Butterworth có phase delay và warmup; config không bù pha. Filter cutoff 4 Hz cần xác nhận bảo toàn các dynamics có ý nghĩa, nhất là khi chọn target 10 Hz.
5. Đầu ra 10 Hz là engineering choice; cần đối chiếu với 50 Hz và kiến thức tần số dao động mục tiêu trước khi dùng cho feature/model.
6. Các kết quả thống kê mô tả dataset, không chứng minh tính đại diện ngoài các phiên này và không phải đánh giá an toàn hàng hải.

## K. Giải thích kỹ thuật phục vụ vấn đáp

### Đọc nguồn và chuẩn hóa schema

- **Em đã làm gì?** Đọc Seafar JSON theo record tuần tự, Hohai theo từng worksheet read-only, Southampton theo từng CSV và bỏ hàng đơn vị thứ hai.
- **Vì sao?** Mỗi nguồn có schema/thời gian khác nhau; đọc tuần tự tránh nạp toàn bộ JSON lớn, và giữ session riêng tránh Data Leakage giữa runs.
- **Thuật toán?** Map các cột cần thiết sang schema `dataset_source/session_id/segment_id/time_seconds/roll_deg/pitch_deg/gyro_x_rad_s/gyro_y_rad_s`, giữ thêm motion channels và metadata provenance.
- **Kết quả thực nghiệm?** Đã đọc các nguồn trong phạm vi chạy: seafar (143,318 hàng/1 phiên), hohai (944,998 hàng/21 phiên), southampton (274,317 hàng/47 phiên); số output theo bảng trên.
- **Nếu bỏ qua?** Nhầm cột/đơn vị hoặc ghép phiên có thể tạo tín hiệu giả và rò rỉ nguồn/session vào đánh giá.
- **Giới hạn?** Hohai time là inferred; Southampton rate semantics chưa xác nhận; Seafar rate lineage thiếu tài liệu.

### Duplicate, invalid row và gap segmentation

- **Em đã làm gì?** Giữ một bản ghi nếu duplicate cùng thời điểm giống nhau; bỏ toàn nhóm timestamp xung đột; loại hàng thiếu/non-finite Roll/Pitch/time; cắt segment tại gap >1,5× median dt.
- **Vì sao?** Trung bình duplicate có thể làm thay đổi phép đo; segment riêng ngăn tạo cửa sổ xuyên qua mất dữ liệu.
- **Kết quả?** Số duplicate/conflict/gap/hàng bị loại theo từng nguồn và phiên nằm trong JSON; không tự gộp các segment.
- **Nếu bỏ qua?** Trùng timestamp làm sai trọng số thống kê; gap lớn có thể bị hiểu nhầm như chuyển động liên tục.
- **Giới hạn?** Ngưỡng 1,5× là quy tắc kỹ thuật cấu hình được, chưa được kiểm chứng với mọi sensor mode; Hohai không có timestamps để phát hiện dropout.

### Đổi đơn vị và xử lý gyro

- **Em đã làm gì?** Giữ Roll/Pitch ở degree; chuyển rate Seafar rad/min sang rad/s bằng chia 60, giữ dấu; Hohai/Southampton canonical gyro để missing khi thiếu hoặc chưa đủ bằng chứng.
- **Vì sao?** C contract hiện dùng rad/s cho gyro; không được xem đạo hàm góc hoặc trường tên mơ hồ là phép đo gyro đã xác nhận.
- **Kết quả?** Seafar rate-reported fields được đưa vào canonical với cảnh báo lineage; Hohai không có gyro; Southampton giữ Delta Angle raw, gyro canonical null.
- **Nếu bỏ qua?** Đơn vị sai tạo scale lệch 60 lần hoặc 57,3 lần; trục/dấu sai đảo nghĩa vật lý.
- **Giới hạn?** Trục, dấu, hiệu chuẩn và vật lý sensor chưa được xác minh với chủ sở hữu dataset.

### Lọc causal và Resampling

- **Em đã làm gì?** Với 50→10 Hz, lọc Butterworth order 4, cutoff 4 Hz bằng SOS causal, warm-start và bỏ 2 s warmup; sau đó chọn mẫu trước gần nhất tại lưới 10 Hz. Seafar khoảng 10 Hz không upsample.
- **Vì sao?** Anti-aliasing giảm năng lượng có thể gập phổ khi giảm tần số; causal filter không dùng tương lai nên phù hợp hướng embedded.
- **Kết quả?** RMSE, RMS ratio, low-band preservation và out-of-band attenuation được đo cho mẫu thực; hình và số liệu cụ thể nằm ở các phần F/G.
- **Nếu bỏ qua?** Thành phần trên Nyquist có thể alias vào dải thấp; zero-phase filter có thể gây lookahead khi dùng offline.
- **Giới hạn?** Filter tạo phase delay, warmup làm mất 2 s mỗi segment; cutoff 4 Hz/10 Hz cần xác nhận theo băng tần tàu và benchmark 50 Hz.

### Kiểm định, đầu ra và khả năng tái lập

- **Em đã làm gì?** Ghi Parquet nén Zstandard, JSON provenance/quality, thống kê before-after, figures và chạy test suite với fixture tổng hợp nhỏ.
- **Vì sao?** Tạo artifact có thể tái lập và kiểm tra source mapping, units, causal behavior, aliasing và ranh giới session mà không dùng fixture làm dữ liệu huấn luyện.
- **Kết quả?** Suite chạy 18 bài: 18 đạt, 0 không đạt, 0 bỏ qua. Suite kiểm tra chuyển đổi units, parse timestamp/schema, duplicate, gap/session, thời gian suy Hohai, gyro nullable, 50→10 Hz, Anti-aliasing, tính tất định, không lookahead và window eligibility.
- **Nếu bỏ qua?** Có thể không phát hiện sai lệch giữa Python, session logic, filter hoặc schema Parquet.
- **Giới hạn?** Test nhỏ xác nhận quy tắc code, không thay thế xác nhận sensor, chuyên môn hàng hải, hoặc đánh giá mô hình.

## L. Tái lập kết quả

Từ repository root:

```bash
python -m ml.preprocessing.run --config ml/preprocessing/config.yaml --dry-run
python -m ml.preprocessing.run --config ml/preprocessing/config.yaml --dataset seafar
python -m ml.preprocessing.run --config ml/preprocessing/config.yaml --dataset hohai
python -m ml.preprocessing.run --config ml/preprocessing/config.yaml --dataset southampton
python -m ml.preprocessing.run --config ml/preprocessing/config.yaml --dataset all
python -m pytest ml/preprocessing/tests -q
```

Xử lý tất định theo cấu hình; các file Parquet nằm trong `ml/data/processed/` (gitignored), summary và báo cáo nhỏ nằm trong `ml/reports/preprocessing/`.

## M. Khuyến nghị trước Feature Extraction

Xác nhận axis/sign và provenance gyro với chủ sở hữu dữ liệu; quyết định ngưỡng gap/coverage, endpoint và cutoff; đánh giá run Hohai/Southampton đại diện ở 10 Hz so với 50 Hz; kiểm tra số mẫu Run 14 có đáp ứng cửa sổ 180 s sau warmup. Sau đó review validity mask và metadata riêng, rồi mới chốt contract Python/C. Hiện dữ liệu đủ điều kiện cho thử nghiệm Feature Extraction ngắn hạn, nhưng Hohai continuity, Seafar duplicate/rate lineage, Southampton 180 s scarcity và gyro mapping khiến pipeline **chưa sẵn sàng cho training/ESP32 deployment**.
