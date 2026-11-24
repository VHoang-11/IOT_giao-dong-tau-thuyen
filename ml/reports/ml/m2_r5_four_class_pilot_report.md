# Bộ dữ liệu pilot mô phỏng bốn lớp M2-R5 (`svmg-four-class-pilot-0.1.0`)

> Nhãn là **proxy theo kịch bản mô phỏng**, được xác nhận bằng ngưỡng labeling-v2 *candidate* đã đóng băng (`calibration_status=candidate`). Đây không phải ground truth nguy hiểm ngoài thực tế; chính sách gán nhãn cửa sổ đang **PROPOSED** (chờ M1/M2 duyệt) và không mô hình nào được huấn luyện. Báo cáo sinh tự động bởi `python -m ml.train.four_class_pilot_dataset` (dữ liệu gitignored tại `ml/data/simulation_four_class_pilot/`).

## Phương pháp

- Nguồn: `ScenarioRunner` có sẵn (dao động tử roll phi tuyến bậc hai 1 bậc tự do, kích động tương quan G1, tổng hợp IMU hệ FRD ở 20 Hz; gia tốc kế = lực riêng từ cùng góc roll, con quay gx = cùng tốc độ roll). Kịch bản S0→NORMAL, S1→HIGH_ROLL, S2→PERSISTENT_OFFSET, S3→AMPLITUDE_GROWTH; S0b và H1 không đưa vào pilot.
- Đặc trưng: bộ lọc Core C production + `features.c` qua `g1_core_feature_runner.c` (đổi hệ FRD→cảm biến, 20→10 Hz, bỏ 20 output khởi động). Schema `svmg-angle-23-v1`, preprocessing `imu-cf-bw4-20to10-v1`, 23 đặc trưng đúng thứ tự contract, một cửa sổ nhân quả (t-180 s, t] mỗi 10 s.
- Một cửa sổ chỉ được gán lớp khi thỏa mọi điều kiện: Core C sẵn sàng 60/180 s, 23/23 hợp lệ và hữu hạn, n60 ≥ 570, n180 ≥ 1710; cửa sổ kết thúc sau thời điểm sự kiện t0; trong cửa sổ không có mẫu chuyển tiếp của bộ mô phỏng (t0..t0+90 s) và không có mẫu khởi động v2; nhãn v2 nhân quả tại điểm cuối cửa sổ bằng nhãn đích của kịch bản; và chỉ đúng cờ phenotype đích đang bật (NORMAL: không cờ nào). Ngược lại cửa sổ là `ABSTAIN` kèm lý do. NaN không bao giờ được thay bằng 0.
- Chia tập theo session, dùng các miền tham số đã thống nhất. Seed session = sha256(dataset_version|seed_base|index)[:4] little-endian uint32 (seed_base 2026120100), tách biệt với seed của G1 và của các lần hiệu chỉnh/xác nhận labeling-v2. Lần sinh đầu dùng seed tuần tự (seed_base+n) chỉ cho bốn thời điểm sự kiện khác nhau (330-341 s) và không có baseline SS0, vì lần rút đầu của xorshift32 gần như trùng nhau với các seed liên tiếp; G1 và các lần hiệu chỉnh v2 cũng dùng seed tuần tự nên cần kiểm toán lại độ đa dạng tham số (bộ mô phỏng không bị sửa ở đây).

## Số lượng (cửa sổ đủ điều kiện / số session đóng góp)

| Split | NORMAL | HIGH_ROLL | PERSISTENT_OFFSET | AMPLITUDE_GROWTH |
|---|---:|---:|---:|---:|
| Train | 312 / 4 | 55 / 4 | 172 / 4 | 13 / 3 |
| Validation | 156 / 2 | 36 / 2 | 125 / 2 | 6 / 2 |
| Test-G1 | 146 / 2 | 39 / 2 | 100 / 2 | 15 / 3 |

Số session: 40; số cửa sổ: 4760; đủ điều kiện: 1175; độ phủ: **ALL_CLASSES_IN_ALL_SPLITS**. Theo quy tắc chặt kiểu G1 (mọi mẫu trong cửa sổ 180 s mang nhãn đích), số cửa sổ đủ điều kiện sẽ là: NORMAL 571, HIGH_ROLL 24, PERSISTENT_OFFSET 273, AMPLITUDE_GROWTH 0.

Lý do ABSTAIN theo kịch bản: S0: CORE_FEATURE_INVALID 136, ENDPOINT_LABEL_MISMATCH 10, LABEL_WARMUP 192; S1: CORE_FEATURE_INVALID 136, ENDPOINT_LABEL_MISMATCH 270, PHENOTYPE_OVERLAP 48, PRE_EVENT 152, TRANSITION_IN_WINDOW 216; S2: CORE_FEATURE_INVALID 136, ENDPOINT_LABEL_MISMATCH 60, PHENOTYPE_OVERLAP 4, PRE_EVENT 139, TRANSITION_IN_WINDOW 216; S3: CORE_FEATURE_INVALID 272, ENDPOINT_LABEL_MISMATCH 834, PRE_EVENT 332, TRANSITION_IN_WINDOW 432.

## Giới hạn

- Nhãn và đặc trưng cùng sinh ra từ một chuỗi roll mô phỏng; nhãn dạng quy tắc có thể làm việc phân lớp trông dễ (xem M2-R3). Ngưỡng là candidate được hiệu chỉnh trên chính bộ mô phỏng này.
- AMPLITUDE_GROWTH ngắn ngủi và thưa: tăng biên độ tham số không xuất hiện ở mọi session S3 và nhanh chóng chuyển thành HIGH_ROLL, nên ít cửa sổ đạt điều kiện.
- Bộ mô phỏng chỉ có roll, nhiễu/bias IMU chưa đặt (None): ba đặc trưng pitch bằng đúng 0 ở mọi cửa sổ (cột hằng, không mang thông tin) và MPU6050 thật sẽ khác (lệch miền). Test-G2 (G2/JONSWAP) chưa được triển khai nên chỉ có Train/Validation/Test-G1. Profile sea state chưa được hiệu chỉnh với sóng thật.
- Cỡ pilot nhỏ hơn rất nhiều so với 605 session theo kế hoạch; số lượng không phù hợp cho metric cuối cùng.

## Kiểm chứng

`pytest ml/train/tests/test_four_class_pilot_dataset.py` kiểm tra tính tất định, class id so với `svmg_class_t`, loại cửa sổ trước sự kiện/chuyển tiếp, cô lập split theo session và seed không trùng, thứ tự 23 đặc trưng và tính hữu hạn (không impute bằng 0), tính nhân quả (đặc trưng từ 600 s đầu bằng đặc trưng của cả session) và sự nhất quán manifest/CSV. Parity đặc trưng Core C so với Python M2 do `tests/firmware/tools/check_features23.py` đảm nhận; sinh lại phải tái tạo đúng SHA-256 bên dưới.

## Mức sẵn sàng cho M2-R6

Chỉ dùng được để phát triển pipeline và thử nghiệm RF theo nhóm đầu tiên sau khi M1/M2 duyệt chính sách gán nhãn cửa sổ, cách xử lý chồng lấn/ABSTAIN và việc dùng ngưỡng candidate. Không dùng để tuyên bố độ chính xác ngoài thực tế.
SHA-256 của dataset: `8f1fae840b659dfe253db3c6d6c88c27beb19034f0e9aaa8f0bd64234a3536ae`.
