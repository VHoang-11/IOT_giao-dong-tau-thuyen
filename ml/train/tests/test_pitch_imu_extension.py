"""Test D5 (`svmg-sim-pitch-imu-0.1.0`): tương thích ngược roll-only, vật lý trục FRD, tất định, nhiễu, đường Core C."""
from __future__ import annotations

import math
import statistics as st
from dataclasses import replace

import pytest

from ml.train import four_class_pilot_dataset as pilot
from ml.train.g1_simulation_dataset import _core_rows, _features
from simulation.generator import pitch_imu as P
from simulation.generator.config import DatasetSplit, LabelingVersion, ScenarioCode

FIELDS = ("ax", "ay", "az", "gx", "gy", "gz", "t")
SEED = 987654321


@pytest.fixture(scope="module")
def result():
    runner, _ = pilot.make_runner()
    return runner.generate(ScenarioCode.S1, seed=SEED, dataset_split=DatasetSplit.TRAIN, labeling_version=LabelingVersion.V2)


def test_backward_compatible_roll_only(result):
    same, meta = P.synthesize(result, P.ROLL_ONLY, SEED)
    assert same is result.imu_samples and meta["enabled"] is False
    zero_forcing, _ = P.synthesize(result, replace(P.PITCH_ONLY, pitch_forcing_ratio=0.0), SEED)
    assert all(getattr(a, f) == getattr(b, f) for a, b in zip(zero_forcing, result.imu_samples) for f in FIELDS)


def test_axes_gravity_and_euler_kinematics(result):
    imu, meta = P.synthesize(result, P.PITCH_ONLY, SEED)
    theta = meta["pitch_rad"]
    assert max(map(abs, theta)) > math.radians(0.2), "pitch phải phản ứng với kích động"
    for i, s in enumerate(imu):
        assert abs(math.sqrt(s.ax ** 2 + s.ay ** 2 + s.az ** 2) - P.GRAVITY_M_S2) < 1e-9
        assert abs(math.atan2(s.ax, math.hypot(s.ay, s.az)) - theta[i]) < 1e-9          # pitch từ gia tốc (FRD) = θ
        assert abs(math.atan2(-s.ay, -s.az) - result.true_roll_rad[i]) < 1e-9          # roll từ gia tốc = φ
        assert s.gx == result.true_roll_rate_rad_s[i]
        if i:
            assert abs(math.hypot(s.gy, s.gz) - abs(theta[i] - theta[i - 1]) / 0.05) < 1e-9   # |(q, r)| = |θ̇|
    assert all(abs(b.t - a.t - 0.05) < 1e-9 for a, b in zip(imu, imu[1:]))


def test_deterministic_and_seed_diverse(result):
    first, _ = P.synthesize(result, P.PITCH_MPU6050_RESIDUAL, SEED)
    again, _ = P.synthesize(result, P.PITCH_MPU6050_RESIDUAL, SEED)
    other, _ = P.synthesize(result, P.PITCH_MPU6050_RESIDUAL, SEED + 1)
    assert first == again and first != other


def test_noise_and_bias_statistics(result):
    clean, _ = P.synthesize(result, P.PITCH_ONLY, SEED)
    noisy, meta = P.synthesize(result, P.PITCH_MPU6050_RESIDUAL, SEED)
    ax = [a.ax - b.ax for a, b in zip(noisy, clean)]
    gy = [a.gy - b.gy for a, b in zip(noisy, clean)]
    assert abs(st.pstdev(ax) / P.PITCH_MPU6050_RESIDUAL.accel_noise_std_m_s2 - 1) < 0.05
    assert abs(st.pstdev(gy) / P.PITCH_MPU6050_RESIDUAL.gyro_noise_std_rad_s - 1) < 0.05
    assert abs(st.fmean(ax) - meta["accel_bias_m_s2"][0]) < 1e-3 and abs(st.fmean(gy) - meta["gyro_bias_rad_s"][1]) < 1e-4
    assert all(s.noise_applied for s in noisy)
    with pytest.raises(ValueError):
        P.PitchIMUConfig(gyro_noise_std_rad_s=-1.0)


def test_core_c_pitch_features_and_full_vector(result):
    imu, meta = P.synthesize(result, P.PITCH_MPU6050_RESIDUAL, SEED)
    rows = [r for r in _core_rows(imu) if r[3]]
    names = list(_features())
    assert len(names) == 23 and all(int(r[1]) == (1 << 23) - 1 and all(map(math.isfinite, r[7:])) for r in rows)
    theta_rms = math.degrees(math.sqrt(sum(x * x for x in meta["pitch_rad"]) / len(meta["pitch_rad"])))
    pitch_std = st.median(r[7 + names.index("pitch_std_60")] for r in rows)
    assert 0.7 < pitch_std / theta_rms < 1.3
