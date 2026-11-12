"""Single-axis roll IMU model with MPU6050-compatible sample fields.

Coordinate convention: right-handed body FRD (X forward toward the bow,
Y starboard, Z down). Positive roll follows the right-hand rule about +X.
Gravity points along +Z in the level body frame, while a stationary
accelerometer reports specific force opposite gravity, so level output has
``az = -g``. The sensor axes are assumed aligned with this body frame.

The model includes gravity projection and rigid-body rotational acceleration
from an optional sensor lever arm. It does not add vessel translation, pitch,
yaw, or hydrodynamic effects.
"""

from dataclasses import dataclass
import math
from typing import Optional, Tuple

from simulation.generator.config import IMUNoiseConfig, SimulationTimeConfig
from simulation.generator.rng import XorShift32
from simulation.generator.roll_dynamics import RollState


GRAVITY_M_S2 = 9.80665
SIMULATION_SOURCE_MODE = 1


def _finite_number(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("{} must be a real number".format(name))
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("{} must be finite".format(name))
    return value


@dataclass(frozen=True)
class IMUSample:
    """Synthetic sample using the field names and units of C ``MotionSample``.

    Accelerations ``ax/ay/az`` are m/s²; angular rates ``gx/gy/gz`` are
    rad/s; ``t`` is seconds. ``source_mode=1`` denotes simulation. The
    ``noise_applied`` flag reports whether configured gyro noise or bias was
    actually applied to this sample.
    """

    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float
    t: float
    valid: bool = True
    source_mode: int = SIMULATION_SOURCE_MODE
    noise_applied: bool = False

    def __post_init__(self) -> None:
        for name in ("ax", "ay", "az", "gx", "gy", "gz", "t"):
            _finite_number(name, getattr(self, name))
        if not isinstance(self.valid, bool):
            raise TypeError("valid must be a bool")
        if (isinstance(self.source_mode, bool) or
                not isinstance(self.source_mode, int) or
                self.source_mode != SIMULATION_SOURCE_MODE):
            raise ValueError("source_mode must identify simulation samples (1)")
        if not isinstance(self.noise_applied, bool):
            raise TypeError("noise_applied must be a bool")

    @property
    def timestamp_s(self) -> float:
        """Timestamp alias with an explicit unit-bearing name."""
        return self.t


class IMUSimulator:
    """Convert a roll state into accelerometer and gyroscope measurements.

    ``lever_arm_body_m`` is the IMU position relative to the roll axis in body
    coordinates (X forward, Y starboard, Z down). Only its Y and Z components
    affect rotation about X. Exactly one nonzero ``seed`` or private
    ``XorShift32`` instance is required, even for clean runs, to make ownership
    of randomness explicit. Configured scalar gyro noise is applied
    independently to X/Y/Z; configured scalar gyro bias is added equally to
    all three axes because the current config has no per-axis bias fields.

    ``roll_noise_std_rad``, ``pitch_noise_std_rad`` and their angle biases do
    not describe raw accelerometer noise in SI units, so they are not mapped to
    accelerometer samples. Accelerometer noise/bias, gyro bias drift, and
    anomalous faults require additional configuration fields.
    """

    def __init__(
        self,
        noise_config: Optional[IMUNoiseConfig] = None,
        time_config: Optional[SimulationTimeConfig] = None,
        *,
        seed: Optional[int] = None,
        rng: Optional[XorShift32] = None,
        lever_arm_body_m: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        if noise_config is None:
            noise_config = IMUNoiseConfig()
        if not isinstance(noise_config, IMUNoiseConfig):
            raise TypeError("noise_config must be an IMUNoiseConfig")
        if time_config is None:
            time_config = SimulationTimeConfig()
        if not isinstance(time_config, SimulationTimeConfig):
            raise TypeError("time_config must be a SimulationTimeConfig")
        if (seed is None) == (rng is None):
            raise ValueError("provide exactly one of seed or rng")
        if rng is not None and not isinstance(rng, XorShift32):
            raise TypeError("rng must be an XorShift32 instance")
        if seed is not None:
            rng = XorShift32(seed)
        if rng.seed == 0:
            raise ValueError("IMU simulation requires a nonzero XorShift32 seed")

        if (not isinstance(lever_arm_body_m, (tuple, list)) or
                len(lever_arm_body_m) != 3):
            raise ValueError("lever_arm_body_m must contain three coordinates")
        lever_arm = tuple(_finite_number("lever_arm_body_m", value)
                          for value in lever_arm_body_m)

        self.noise_config = noise_config
        self.time_config = time_config
        self.dt_s = _finite_number("time_config.dt_s", time_config.dt_s)
        self.rng = rng
        self.lever_arm_body_m = lever_arm

    def sample(
        self,
        state: RollState,
        angular_acceleration_rad_s2: float,
    ) -> IMUSample:
        """Create one IMU sample at the supplied roll state and timestamp.

        Specific force is ``a_sensor - g_body``. For angular rate and
        acceleration about +X, rigid-body terms are ``alpha × r`` and
        ``omega × (omega × r)``. There is no added translational acceleration.
        ``angular_acceleration_rad_s2`` is required to model tangential force.
        """
        if not isinstance(state, RollState):
            raise TypeError("state must be a RollState")
        phi = _finite_number("state.phi_rad", state.phi_rad)
        omega = _finite_number("state.omega_rad_s", state.omega_rad_s)
        timestamp = _finite_number("state.timestamp_s", state.timestamp_s)
        alpha = _finite_number("angular_acceleration_rad_s2",
                               angular_acceleration_rad_s2)

        _, lever_y, lever_z = self.lever_arm_body_m

        # In body FRD coordinates, gravity is (0, g*sin(phi), g*cos(phi)).
        # A stationary accelerometer reports specific force, i.e. -gravity.
        ax = 0.0
        ay = -GRAVITY_M_S2 * math.sin(phi)
        az = -GRAVITY_M_S2 * math.cos(phi)

        # Rotational acceleration of the sensor relative to the roll axis.
        ay += -alpha * lever_z - omega * omega * lever_y
        az += alpha * lever_y - omega * omega * lever_z

        gyro_std = self.noise_config.gyro_noise_std_rad_s
        gyro_std = 0.0 if gyro_std is None else _finite_number(
            "gyro_noise_std_rad_s", gyro_std)
        gyro_bias = self.noise_config.gyro_bias_rad_s
        gyro_bias = 0.0 if gyro_bias is None else _finite_number(
            "gyro_bias_rad_s", gyro_bias)
        noise_applied = gyro_std != 0.0 or gyro_bias != 0.0

        gx, gy, gz = omega, 0.0, 0.0
        if gyro_std != 0.0:
            gx += gyro_std * self.rng.normal()
            gy += gyro_std * self.rng.normal()
            gz += gyro_std * self.rng.normal()
        if gyro_bias != 0.0:
            gx += gyro_bias
            gy += gyro_bias
            gz += gyro_bias

        values = (ax, ay, az, gx, gy, gz, timestamp)
        if not all(math.isfinite(value) for value in values):
            raise FloatingPointError("IMU simulation produced a non-finite sample")
        return IMUSample(
            ax=ax, ay=ay, az=az,
            gx=gx, gy=gy, gz=gz,
            t=timestamp,
            valid=True,
            source_mode=SIMULATION_SOURCE_MODE,
            noise_applied=noise_applied,
        )
