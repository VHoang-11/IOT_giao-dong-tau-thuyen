# M2-R5c-2 – Mở rộng mô phỏng pitch và nhiễu IMU (`svmg-sim-pitch-imu-0.1.0`, quyết định D5)

**Phạm vi:** mô phỏng dữ liệu, tùy chọn và có phiên bản. Không huấn luyện RF, không sửa firmware/Core C, không đổi nhãn, ngưỡng, công thức đặc trưng hay chính sách nhãn điểm cuối. Mã: `simulation/generator/pitch_imu.py`; chẩn đoán: `python -m ml.train.pitch_imu_diagnostic` → `ml/reports/ml/m2_r5c2_pitch_imu_diagnostic.md`.

## Giả định mô phỏng

- **Hậu xử lý** một `ScenarioResult` có sẵn: roll φ(t), tốc độ roll φ̇(t), σ_w(t) và nhãn v2 giữ nguyên; nhãn vẫn tính từ roll thật nên pitch/nhiễu không đổi nhãn.
- **Pitch θ:** dao động tử tuyến tính bậc hai, dùng lại `RollDynamics` (h = 0, κ = 0, heel = 0) với kích động tương quan G1 (`CorrelatedWaveGenerator`, τ = 3 s) có σ_wθ(t) = `pitch_forcing_ratio` × σ_w roll(t). Pitch độc lập với roll (không có ghép nối thủy động).
- **Hướng:** hệ thân FRD (X mũi, Y mạn phải, Z xuống), Euler ZYX, yaw = 0. Lực riêng khi không có gia tốc tịnh tiến và cánh tay đòn = 0: `ax = g·sinθ`, `ay = −g·sinφ·cosθ`, `az = −g·cosφ·cosθ`. Gyro từ động học Euler: `gx = φ̇`, `gy = θ̇·cosφ`, `gz = −θ̇·sinφ`. Với θ = 0 công thức trùng `IMUSimulator` roll-only (đã kiểm tra bằng nhau từng giá trị).
- **Core C:** sau phép quay FRD→cảm biến (đổi dấu ay, az, gy, gz) roll của Core C = φ, pitch của Core C = −θ; ba đặc trưng pitch (RMS, std, đỉnh-đỉnh) không phụ thuộc dấu.

## Tham số (đơn vị tường minh)

| Tham số | Mặc định | Đơn vị | Ghi chú |
|---|---|---|---|
| `pitch_enabled` | `False` | – | Tắt: trả nguyên mẫu IMU roll-only |
| `pitch_period_s` | 6–10 (đều) | s | Giả định cho tàu container, chưa hiệu chỉnh |
| `pitch_damping_ratio` | 0,10–0,20 (đều) | – | Pitch tắt dần mạnh hơn roll |
| `pitch_forcing_ratio` | 0,3 | – | σ_wθ / σ_w roll |
| `accel_noise_std_m_s2` / `accel_bias_std_m_s2` | 0 / 0 | m/s² | Nhiễu trắng mỗi mẫu 20 Hz; bias hằng mỗi session, mỗi trục ~ N(0, σ) |
| `gyro_noise_std_rad_s` / `gyro_bias_std_rad_s` | 0 / 0 | rad/s | Như trên |

Cấu hình đặt sẵn: `ROLL_ONLY` (mặc định, tắt), `PITCH_ONLY`, `PITCH_MPU6050_RESIDUAL` (pitch + nhiễu accel 0,02 m/s² ≈ 2 mg, bias 0,01 m/s², nhiễu gyro 0,03 °/s, bias gyro 0,05 °/s) – mô tả **phần dư sau hiệu chỉnh**, không phải offset thô của MPU6050.

## Nguồn gốc dữ liệu và tái lập

Nguồn `SIMULATION`. Ngẫu nhiên của phần mở rộng dùng luồng xorshift32 riêng với seed `sha256("svmg-sim-pitch-imu-0.1.0|<seed session>|<luồng>")` cho ba luồng `parameters`, `pitch_forcing`, `noise`; không tiêu thụ PRNG của kịch bản. Cùng (kết quả kịch bản, cấu hình, seed) cho cùng từng mẫu; seed khác cho dữ liệu khác. Metadata trả về ghi phiên bản, cấu hình, chu kỳ/tắt dần pitch, bias đã rút và chuỗi θ thật.

## Tương thích phiên bản

- `ROLL_ONLY` trả nguyên `result.imu_samples`; `scenarios.py`, `imu_simulator.py`, PRNG và nhãn không đổi.
- Pilot `svmg-four-class-pilot-0.1.0` và dataset `svmg-four-class-exp-0.2.0` **không bị sinh lại hay ghi đè**; chúng vẫn là roll-only (pitch = 0, không nhiễu).
- Dataset dùng pitch/nhiễu (nếu được duyệt) phải có phiên bản dataset mới và ghi `svmg-sim-pitch-imu-0.1.0` cùng cấu hình vào manifest.

## Khoảng cách miền còn lại so với MPU6050 thật

Chưa mô phỏng: gia tốc tịnh tiến (heave/surge/sway), yaw, cánh tay đòn cảm biến, ghép nối roll–pitch, offset thô theo datasheet (accel ±50 mg, gyro ±20 °/s trước hiệu chỉnh), trôi theo nhiệt độ, lượng tử hóa/bão hòa 16 bit, lệch trục lắp đặt, jitter thời gian lấy mẫu, mất mẫu I2C. Tham số pitch và sea state là giả định, chưa hiệu chỉnh với tàu thật. Đây vẫn là dữ liệu mô phỏng, không phải ground truth ngoài thực tế.

## Làm rõ số đếm M2-R5c (`svmg-four-class-exp-0.2.0`, không đổi)

1959 là **số cửa sổ có nhãn (khác ABSTAIN)**, gồm CORE 1655 (Train 886 + Validation 469 + Test-G1 300) và CHALLENGE_S0B 304 (Train 200 + Validation 104). 7442 cửa sổ ABSTAIN (CORE 7032, S0b 410) không nằm trong 1959. Ứng viên huấn luyện mặc định chỉ là CORE Train 886; Validation 469 dùng chọn mô hình; Test-G1 300 giữ kín; S0b 304 là tập challenge, không mặc định là dữ liệu huấn luyện NORMAL.
