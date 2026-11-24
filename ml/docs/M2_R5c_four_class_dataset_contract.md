# Hợp đồng nhãn/bộ dữ liệu bốn lớp thử nghiệm `svmg-four-class-label-contract-0.2.0`

**Trạng thái:** APPROVED-EXPERIMENTAL (chủ sở hữu M2 duyệt cho phiên bản mô hình thử nghiệm đầu tiên). Không phải ontology an toàn hàng hải; không thay thế đề xuất B2a. Bộ dữ liệu: `svmg-four-class-exp-0.2.0`, sinh bởi `ml/train/four_class_experimental_dataset.py`. Pilot `svmg-four-class-pilot-0.1.0` giữ nguyên.

## Quyết định đã duyệt

| Mã | Quyết định | Cách hiện thực |
|---|---|---|
| D1 | Nhãn bốn lớp theo **điểm cuối**: mục tiêu là phenotype tại thời điểm dự đoán, chỉ dùng 180 s quan sát trước đó. | Dùng nguyên `four_class_pilot_dataset.window_label`. Không tuyên bố cả cửa sổ thuộc lớp đó. |
| D2 | Đóng băng `simulation/calibration/labeling_v2_candidate.json` (SHA-256 `c57194ea…959e9d`). | Bộ sinh dừng nếu SHA khác. Ngưỡng là proxy rút từ mô phỏng, chưa được kiểm chứng độc lập ngoài thực tế. |
| D3 | Giữ `ABSTAIN` cho phenotype điểm cuối mơ hồ, khởi động, chuyển tiếp và đặc trưng không hợp lệ; ghi độ phủ lớp đích trong lịch sử 180 s. | Cột `target_coverage_180`; manifest/báo cáo có phân bố độ phủ và độ nhạy theo ngưỡng 0 / 0,25 / 0,5 / 0,75 / 1,0. Chính sách chính không dùng ngưỡng độ phủ. |
| D4 | Seed session ổn định dẫn xuất từ SHA-256; giữ hành vi PRNG và khả năng tái lập lịch sử. | `sha256("svmg-four-class-exp-0.2.0" + "|" + chỉ số)[:4]`; xorshift32 của bộ mô phỏng không đổi. G1 chỉ được kiểm toán (đọc), không ghi lại. |
| D5 | Pitch và nhiễu IMU tùy chọn chỉ qua cấu hình mô phỏng có phiên bản mới. | **Chưa thực hiện trong v0.2** (PR riêng); ba đặc trưng pitch vẫn bằng 0. |

## Lớp, kịch bản và tập con

| `class_id` | Lớp | Kịch bản nguồn | Tập |
|---:|---|---|---|
| 0 | `NORMAL` | S0 (biển lặng) | `CORE` |
| 1 | `HIGH_ROLL` | S1 | `CORE` |
| 2 | `PERSISTENT_OFFSET` | S2 | `CORE` |
| 3 | `AMPLITUDE_GROWTH` | S3 | `CORE` |
| 0 | `NORMAL` | S0b (nghiêng tạm thời 20–90 s) | `CHALLENGE_S0B` – tập challenge/đối chứng, không mặc định đưa vào huấn luyện |

`class_id` trùng `svmg_class_t`. H1 không thuộc phiên bản này (chưa có chính sách chồng lấn). Cửa sổ S0b không được giả định là NORMAL: mọi cửa sổ trước sự kiện hoặc có lịch sử chứa đoạn chuyển tiếp/nghiêng là `ABSTAIN`.

## Quy tắc cửa sổ (không đổi so với pilot)

Một cửa sổ (t-180 s, t] chỉ có lớp khi: Core C sẵn sàng 60/180 s, đủ 23/23 đặc trưng hữu hạn, n60 ≥ 570, n180 ≥ 1710; t sau thời điểm sự kiện t0; lịch sử không chứa mẫu chuyển tiếp (t0..t0+90 s) hay mẫu khởi động v2; nhãn v2 nhân quả tại t bằng lớp đích; chỉ đúng cờ phenotype đích đang bật. Ngược lại: `ABSTAIN` + `exclusion_reason`. Cửa sổ S1 trước sự kiện **không** được gán lại thành NORMAL. Không impute NaN.

## Chia tập, seed và phiên bản

- Chia theo session (seed); Train/Validation dùng miền tham số đã thống nhất. Kế hoạch khai báo trước (Train, Validation): S0 6/3, S1 6/3, S2 6/3, S3 24/12, S0b 4/2.
- **Test-G1 giữ nguyên** đúng 10 session Test-G1 của pilot (cùng seed); không chỉnh kế hoạch theo kết quả Test-G1.
- Đặc trưng: `svmg-angle-23-v1`, preprocessing `imu-cf-bw4-20to10-v1`, đúng 23 tên/thứ tự theo `contracts/features23.json` và Core C.
- Manifest ghi SHA-256 của dataset, của ngưỡng đóng băng và của mọi file nguồn liên quan; cùng cấu hình phải tái tạo đúng SHA.

## Lưu ý bắt buộc khi dùng (M2-R6)

1. Nhãn là `SIMULATION_SCENARIO_V2_CANDIDATE`, không phải ground truth nguy hiểm; không tuyên bố độ chính xác ngoài thực tế.
2. Lịch sử 180 s có thể trộn trạng thái; phải báo cáo kết quả theo độ phủ (`target_coverage_180`), không chỉ tổng thể.
3. Báo cáo cả số cửa sổ lẫn số session độc lập và session hiệu dụng; đánh giá theo nhóm session.
4. Chưa có pitch/nhiễu IMU và Test-G2; cần thực hiện D5 trước khi so sánh với dữ liệu MPU6050 thật.
