# M2-R5b – Kiểm toán nghiên cứu bộ dữ liệu mô phỏng (pilot `svmg-four-class-pilot-0.1.0`)

> Kiểm toán bộ pilot SIMULATION M2-R5 hiện có (SHA-256 dataset `8f1fae84…36ae`) bằng `ml/notebooks/25_synthetic_motion_scenarios.ipynb`. Không huấn luyện mô hình, không đổi ngưỡng hay công thức; nhãn là proxy theo kịch bản mô phỏng được xác nhận bằng ngưỡng labeling-v2 **candidate**, không phải ground truth ngoài thực tế. Notebook trong repo không kèm output; hình `01`–`05` được ghi vào `ml/data/simulation_four_class_pilot/figures/` (gitignored). Tái lập: `python -m ml.train.four_class_pilot_dataset`, rồi `.venv/bin/python -m nbconvert --to notebook --execute ml/notebooks/25_synthetic_motion_scenarios.ipynb --output-dir ml/data/simulation_four_class_pilot/executed` (≈ 30 s). Notebook kiểm tra SHA của CSV và mọi file nguồn của bộ sinh/Core C so với manifest, và kiểm tra nhãn của session sinh lại trùng CSV. Lần chạy kiểm chứng: 16/16 cell (8 cell code, `execution_count` 1–8), 0 lỗi, 5 hình, 10 bảng; hai lần chạy từ kernel sạch cho output và hình giống hệt (`executed/execution_summary.json`).

## Số lượng (cửa sổ đủ điều kiện / số session đóng góp; session theo kế hoạch mỗi split = 4·4·4·8, 2·2·2·4, 2·2·2·4)

| Split | NORMAL | HIGH_ROLL | PERSISTENT_OFFSET | AMPLITUDE_GROWTH |
|---|---:|---:|---:|---:|
| Train | 312 / 4 | 55 / 4 | 172 / 4 | 13 / 3 |
| Validation | 156 / 2 | 36 / 2 | 125 / 2 | 6 / 2 |
| Test-G1 | 146 / 2 | 39 / 2 | 100 / 2 | 15 / 3 |

Trạng thái của toàn bộ 4760 cửa sổ (hình 03): Core C chưa sẵn sàng (180 s đầu) 680; labeler v2 đang khởi động 192 (chỉ S0);
trước sự kiện 623; chuyển tiếp 864; nhãn tại điểm cuối ≠ nhãn đích của kịch bản 1174; chồng lấn phenotype 52; đủ điều kiện 1175.

## Phát hiện

1. **Gán nhãn tại điểm cuối so với đồng nhất 180 s.** Nếu đòi mọi mẫu trong cửa sổ 180 s mang nhãn v2 đích (quy tắc kiểu G1) thì còn NORMAL 294/156/121, PERSISTENT_OFFSET 125/103/45, HIGH_ROLL 7/10/7 và **AMPLITUDE_GROWTH 0/0/0** (Train/Validation/Test-G1). Như vậy chính sách điểm cuối tạo ra gần như toàn bộ cửa sổ HIGH_ROLL và toàn bộ cửa sổ growth.
2. **Cửa sổ trộn trạng thái phổ biến ngoài NORMAL.** Trung vị tỉ lệ mẫu mang nhãn v2 đích trong cửa sổ: NORMAL 1,00 (nhỏ nhất 0,53), PERSISTENT_OFFSET 1,00 (trung bình 0,87, nhỏ nhất 0,04), HIGH_ROLL 0,42, AMPLITUDE_GROWTH **0,13** (34 cửa sổ). Cửa sổ growth đủ điều kiện phần lớn là lịch sử NORMAL/HIGH_ROLL kết thúc bằng một đợt growth ngắn; 36 cửa sổ NORMAL đủ điều kiện cũng chứa mẫu growth và 32 cửa sổ chứa mẫu HIGH_ROLL (dao động vượt ngưỡng trong session đối chứng).
3. **Vì sao AMPLITUDE_GROWTH chỉ có 13/6/15 cửa sổ.** Chỉ 8/16 session S3 cho ra cửa sổ đủ điều kiện. Sau chuyển tiếp, nhãn growth chiếm 0–19,7 % thời gian (HIGH_ROLL tới 82,3 %); đợt growth liên tục dài nhất 0–88,7 s (trung vị 35 s). Trong 834 điểm cuối S3 bị loại vì lệch nhãn, 495 điểm cuối là NORMAL và 339 là HIGH_ROLL. Growth xuất hiện theo từng đợt (hình 02, 05) và, theo thứ tự ưu tiên v2, chuyển thành HIGH_ROLL; nguyên nhân không phải thiếu kích thích: mọi session S3 có h = 0,29–0,50, cao hơn biên tham chiếu Mathieu tuyến tính h = 4ζ (≤ 0,24).
4. **Độ đa dạng seed.** Pilot (seed băm): 32/32 thời điểm sự kiện khác nhau (t0 252,8–523,6 s), mọi T0/ζ/t0 nằm trong miền tham số đã thống nhất; baseline S0/S1 trải SS0–SS3, S2 không rút SS2 trong 8 session, S3 chỉ SS1/SS2 theo thiết kế. Chạy lại kế hoạch với seed tuần tự chỉ cho **1/12** giá trị t0 (339,9–340,3 s) và 11/12 là SS3; chín seed S1 của G1 cho **1/9** giá trị t0, đều SS2.
5. **Giai đoạn trước sự kiện của S1 không giống NORMAL.** Session S1 đại diện đã dao động ≈ ±20° trước t0 = 283,7 s (baseline SS3, T0 = 25,7 s, ζ = 0,038), nên không được gán lại các cửa sổ trước sự kiện thành NORMAL.

## Đề xuất quyết định cho M1/M2

1. Chọn rõ chính sách cửa sổ: điểm cuối (nhiều dữ liệu hơn, có cửa sổ trộn trạng thái) hay đồng nhất (không còn lớp growth), hoặc quy tắc tỉ lệ nhãn đích tối thiểu; dù chọn phương án nào, giữ cửa sổ trộn là ABSTAIN hoặc là một tập con riêng có kiểm toán.
2. Quyết định AMPLITUDE_GROWTH là lớp loại trừ để huấn luyện hay chỉ là cờ phenotype (phương án C của B2a); với bộ mô phỏng và ngưỡng v2 candidate hiện tại, growth xảy ra theo đợt và chồng lấn nhiều với HIGH_ROLL.
3. Sửa cách dẫn xuất seed trong bộ mô phỏng (hoặc bắt buộc seed băm) và kiểm toán lại G1 cùng các lần hiệu chỉnh labeling-v2 đã dùng seed tuần tự.
4. Bổ sung kích thích pitch và nhiễu/bias IMU trước M2-R6 (ba đặc trưng pitch bằng đúng 0 trong pilot).
5. Giữ mọi nhãn ở dạng `SIMULATION_SCENARIO_V2_CANDIDATE`; không gán nhãn bốn lớp cho dữ liệu thật khi chưa có tham chiếu độc lập.

## Giới hạn

Nhãn và đặc trưng cùng từ một bộ mô phỏng; ngưỡng candidate được hiệu chỉnh trên chính bộ mô phỏng đó; profile sea state chưa
hiệu chỉnh; chưa có Test-G2; pilot chỉ 40 session; đường h = 4ζ là tham chiếu tuyến tính khi tắt dần nhỏ, không phải thuộc tính
của bộ mô phỏng.
