"""Mở rộng mô phỏng có phiên bản (quyết định D5): pitch + IMU 3 trục + nhiễu/bias tùy chọn.

Hậu xử lý một ``ScenarioResult`` đã có; KHÔNG đổi động lực roll, nhãn v2, PRNG của kịch bản hay đường roll-only.
Khi cấu hình tắt (mặc định) hàm trả về nguyên ``result.imu_samples``.

Quy ước: hệ thân FRD (X mũi, Y mạn phải, Z xuống), góc Euler ZYX với yaw = 0. Roll φ quanh +X, pitch θ quanh +Y
(θ > 0: mũi ngóc lên). Lực riêng (không gia tốc tịnh tiến, cánh tay đòn = 0):
    ax = g·sinθ,  ay = −g·sinφ·cosθ,  az = −g·cosφ·cosθ      (θ = 0 trùng IMUSimulator roll-only)
Tốc độ góc thân từ động học Euler (yaw rate = 0):
    gx = p = φ̇,  gy = q = θ̇·cosφ,  gz = r = −θ̇·sinφ
Sau phép quay FRD→cảm biến của Core C (đổi dấu ay, az, gy, gz), pitch của Core C bằng −θ.
Pitch dùng lại ``RollDynamics`` như dao động tử tuyến tính bậc hai (h = 0, κ = 0, heel = 0) với kích động tương quan G1
tỉ lệ với σ_w của roll; tham số pitch là giả định mô phỏng, chưa hiệu chỉnh với tàu thật.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

from simulation.generator.config import RollDynamicsConfig, SimulationTimeConfig
from simulation.generator.imu_simulator import GRAVITY_M_S2, IMUSample
from simulation.generator.rng import XorShift32
from simulation.generator.roll_dynamics import RollDynamics
from simulation.generator.wave_generator import CorrelatedWaveGenerator

SIM_EXTENSION_VERSION = "svmg-sim-pitch-imu-0.1.0"


@dataclass(frozen=True)
class PitchIMUConfig:
    """Đơn vị: chu kỳ s, tắt dần không thứ nguyên, gia tốc m/s², tốc độ góc rad/s. Nhiễu trắng Gaussian theo mẫu 20 Hz;
    bias hằng số mỗi session, mỗi trục rút từ N(0, σ_bias)."""

    pitch_enabled: bool = False
    pitch_period_s: tuple[float, float] = (6.0, 10.0)
    pitch_damping_ratio: tuple[float, float] = (0.10, 0.20)
    pitch_forcing_ratio: float = 0.3           # σ_wθ(t) = tỉ lệ × σ_w roll(t) của kịch bản
    pitch_correlation_time_s: float = 3.0
    accel_noise_std_m_s2: float = 0.0
    accel_bias_std_m_s2: float = 0.0
    gyro_noise_std_rad_s: float = 0.0
    gyro_bias_std_rad_s: float = 0.0

    def __post_init__(self) -> None:
        for name in ("pitch_forcing_ratio", "pitch_correlation_time_s", "accel_noise_std_m_s2", "accel_bias_std_m_s2",
                     "gyro_noise_std_rad_s", "gyro_bias_std_rad_s"):
            value = getattr(self, name)
            if not (math.isfinite(value) and value >= 0.0):
                raise ValueError(f"{name} phải hữu hạn và không âm")
        for name in ("pitch_period_s", "pitch_damping_ratio"):
            low, high = getattr(self, name)
            if not (0.0 < low <= high and math.isfinite(high)):
                raise ValueError(f"{name} phải là khoảng dương (min, max)")
        if self.pitch_correlation_time_s == 0.0:
            raise ValueError("pitch_correlation_time_s phải dương")

    @property
    def enabled(self) -> bool:
        noise = (self.accel_noise_std_m_s2, self.accel_bias_std_m_s2, self.gyro_noise_std_rad_s, self.gyro_bias_std_rad_s)
        return self.pitch_enabled or any(value > 0.0 for value in noise)


ROLL_ONLY = PitchIMUConfig()
PITCH_ONLY = PitchIMUConfig(pitch_enabled=True)
# Phần dư sau hiệu chỉnh kiểu MPU6050 (giả định; offset thô theo datasheet lớn hơn nhiều): ≈2 mg nhiễu, 1 mg bias,
# 0,03 °/s nhiễu gyro, 0,05 °/s bias gyro.
PITCH_MPU6050_RESIDUAL = PitchIMUConfig(pitch_enabled=True, accel_noise_std_m_s2=0.02, accel_bias_std_m_s2=0.01,
                                        gyro_noise_std_rad_s=math.radians(0.03), gyro_bias_std_rad_s=math.radians(0.05))


def extension_seed(session_seed: int, stream: str) -> int:
    """Luồng ngẫu nhiên riêng của phần mở rộng (SHA-256); không tiêu thụ PRNG của kịch bản."""
    digest = hashlib.sha256(f"{SIM_EXTENSION_VERSION}|{session_seed}|{stream}".encode()).digest()
    return int.from_bytes(digest[:4], "little") or 1


def synthesize(result, config: PitchIMUConfig, session_seed: int) -> tuple[tuple[IMUSample, ...], dict]:
    """Trả (mẫu IMU 20 Hz, metadata gồm chuỗi pitch thật). Tất định theo (kết quả kịch bản, cấu hình, seed)."""
    t = result.timestamps_s
    n = len(t)
    if not config.enabled:
        return result.imu_samples, {"version": SIM_EXTENSION_VERSION, "enabled": False, "pitch_rad": [0.0] * n}
    params = XorShift32(extension_seed(session_seed, "parameters"))
    dt = t[1] - t[0]
    theta, theta_rate = [0.0] * n, [0.0] * n
    period = damping = None
    if config.pitch_enabled:
        period = config.pitch_period_s[0] + (config.pitch_period_s[1] - config.pitch_period_s[0]) * params.random()
        damping = config.pitch_damping_ratio[0] + (config.pitch_damping_ratio[1] - config.pitch_damping_ratio[0]) * params.random()
        dynamics = RollDynamics(RollDynamicsConfig(natural_period_s=period, damping_ratio=damping), SimulationTimeConfig())
        forcing = CorrelatedWaveGenerator(sigma_w_rad=1.0, correlation_time_s=config.pitch_correlation_time_s, dt_s=dt,
                                          seed=extension_seed(session_seed, "pitch_forcing"))
        state, unit = dynamics.initial_state(t[0]), 0.0
        for i in range(n):
            theta[i], theta_rate[i] = state.phi_rad, state.omega_rad_s
            if i + 1 < n:
                state = dynamics.step(state, dt_s=dt, wave_excitation_rad=config.pitch_forcing_ratio * result.wave_sigma_rad[i] * unit)
                unit = forcing.step()
    accel_bias = [config.accel_bias_std_m_s2 * params.normal() for _ in range(3)]
    gyro_bias = [config.gyro_bias_std_rad_s * params.normal() for _ in range(3)]
    noise = XorShift32(extension_seed(session_seed, "noise"))
    noisy = config.accel_noise_std_m_s2 > 0 or config.gyro_noise_std_rad_s > 0 or any(accel_bias + gyro_bias)
    samples = []
    for i in range(n):
        phi, p, th, thd = result.true_roll_rad[i], result.true_roll_rate_rad_s[i], theta[i], theta_rate[i]
        accel = (GRAVITY_M_S2 * math.sin(th), -GRAVITY_M_S2 * math.sin(phi) * math.cos(th), -GRAVITY_M_S2 * math.cos(phi) * math.cos(th))
        gyro = (p, thd * math.cos(phi), -thd * math.sin(phi))
        accel = [a + b + (config.accel_noise_std_m_s2 * noise.normal() if config.accel_noise_std_m_s2 else 0.0) for a, b in zip(accel, accel_bias)]
        gyro = [w + b + (config.gyro_noise_std_rad_s * noise.normal() if config.gyro_noise_std_rad_s else 0.0) for w, b in zip(gyro, gyro_bias)]
        samples.append(IMUSample(*accel, *gyro, t=t[i], noise_applied=noisy))
    meta = {"version": SIM_EXTENSION_VERSION, "enabled": True, "config": config.__dict__, "pitch_period_s": period,
            "pitch_damping_ratio": damping, "accel_bias_m_s2": accel_bias, "gyro_bias_rad_s": gyro_bias, "pitch_rad": theta}
    return tuple(samples), meta
