# Chẩn đoán mô phỏng pitch/IMU M2-R5c-2 (`svmg-sim-pitch-imu-0.1.0`)

> Mẫu chẩn đoán nhỏ (8 session miền Train, 2 mỗi lớp S0–S3; không dùng Test-G1), không phải dataset huấn luyện. Nhãn vẫn lấy từ roll thật theo quy tắc điểm cuối của pilot; ngưỡng/công thức không đổi. Sinh bởi `python -m ml.train.pitch_imu_diagnostic`; số liệu đầy đủ tại `ml/data/simulation_pitch_imu_diag/summary.json` (gitignored). Giả định và giới hạn: `ml/docs/M2_R5c2_pitch_imu_simulation.md`.

| Chỉ số | ROLL_ONLY | PITCH_ONLY | PITCH_MPU6050_RESIDUAL |
|---|---:|---:|---:|
| RMS pitch thật [độ] min/trung vị/max | 0.0/0.0/0.0 | 0.19/0.567/1.667 | 0.19/0.567/1.667 |
| Tỉ lệ cửa sổ đủ 23/23 khi đã sẵn sàng 180 s | 1.0 | 1.0 | 1.0 |
| Cửa sổ đủ điều kiện N/H/P/G | 156/23/100/0 | 156/23/100/0 | 156/23/100/0 |
| Nhãn trùng roll-only | 1.0 | 1.0 | 1.0 |
| `pitch_rms_60` p5/trung vị/p95 [độ] | 0.0/0.0/0.0 | 0.1676/0.5398/1.7917 | 0.5347/0.7457/1.8595 |
| `pitch_std_60` p5/trung vị/p95 [độ] | 0.0/0.0/0.0 | 0.1641/0.5374/1.7899 | 0.1655/0.5375/1.7911 |
| `pitch_peak_to_peak_60` p5/trung vị/p95 [độ] | 0.0/0.0/0.0 | 0.7231/2.2797/7.4657 | 0.7223/2.293/7.4706 |
| Trung vị |Δ`roll_std_60`| so với roll-only | 0.0 | 0.0 | 0.00198 |
| Trung vị |Δ`roll_mean_60`| so với roll-only | 0.0 | 0.0 | 0.08817 |
| Trung vị |Δ`roll_rms_slope_180`| so với roll-only | 0.0 | 0.0 | 0.00729 |

Chu kỳ pitch đã rút (s): [6.4, 6.85, 7.34, 7.9, 8.28, 8.6, 9.02, 9.51]. Phần dư nhiễu đo được (cấu hình MPU6050 dư): độ lệch chuẩn nhiễu trong session (trung vị) accel X 0.020035 m/s² (cấu hình 0,02), gyro Y 0.000522 rad/s (cấu hình ≈ 0,000524); độ phân tán bias giữa 8 session accel X 0.008697 m/s² (cấu hình 0,01), gyro Y 0.000877 rad/s (cấu hình ≈ 0,000873; ước lượng thô vì chỉ 8 session).
