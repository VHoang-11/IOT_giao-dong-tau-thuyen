"""G1 correlated stochastic wave forcing for the SVMG roll model.

This produces the equivalent angular forcing ``w(t)`` in radians. It does not
model wave hydrodynamics or assign sea states/scenario labels.
"""

import math
from typing import Optional

from simulation.generator.config import (
    SimulationTimeConfig,
    WaveExcitationConfig,
    WaveGenerator as WaveGeneratorKind,
)
from simulation.generator.rng import XorShift32


def _finite_number(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("{} must be a real number".format(name))
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("{} must be finite".format(name))
    return value


def _finite_nonnegative(name: str, value: float) -> float:
    value = _finite_number(name, value)
    if value < 0.0:
        raise ValueError("{} must be non-negative".format(name))
    return value


class CorrelatedWaveGenerator:
    """Discrete stationary-scale AR(1)/OU process for G1 wave forcing.

    State starts at ``initial_state_rad`` (zero by default), not from the
    stationary distribution. Forcing standard deviation is in radians. If no
    correlation time is configured, 3 seconds is used as the design reference
    from the M2 brief, not as a measured sea-state property.

    Pass either a nonzero ``seed`` or a private ``XorShift32`` instance with a
    nonzero original seed. Xorshift32's all-zero state is absorbing and cannot
    provide stochastic innovations. Each nonzero-sigma step consumes one
    Box-Muller normal draw from that PRNG.
    """

    DEFAULT_CORRELATION_TIME_S = 3.0

    def __init__(
        self,
        config: Optional[WaveExcitationConfig] = None,
        *,
        time_config: Optional[SimulationTimeConfig] = None,
        sigma_w_rad: Optional[float] = None,
        sigma_w_deg: Optional[float] = None,
        correlation_time_s: Optional[float] = None,
        dt_s: Optional[float] = None,
        seed: Optional[int] = None,
        rng: Optional[XorShift32] = None,
        initial_state_rad: float = 0.0,
    ) -> None:
        if config is None:
            config = WaveExcitationConfig()
        if not isinstance(config, WaveExcitationConfig):
            raise TypeError("config must be a WaveExcitationConfig")
        if config.generator is not WaveGeneratorKind.G1:
            raise ValueError("CorrelatedWaveGenerator implements G1 only")
        if time_config is None:
            time_config = SimulationTimeConfig()
        if not isinstance(time_config, SimulationTimeConfig):
            raise TypeError("time_config must be a SimulationTimeConfig")

        if sigma_w_rad is not None and sigma_w_deg is not None:
            raise ValueError("provide sigma_w_rad or sigma_w_deg, not both")
        if sigma_w_deg is not None:
            # Convert once at this API boundary; state and calculations stay rad.
            sigma = _finite_nonnegative("sigma_w_deg", sigma_w_deg)
            sigma = math.radians(sigma)
        elif sigma_w_rad is not None:
            sigma = _finite_nonnegative("sigma_w_rad", sigma_w_rad)
        elif config.g1_forcing_std_rad is not None:
            sigma = _finite_nonnegative(
                "config.g1_forcing_std_rad", config.g1_forcing_std_rad)
        else:
            raise ValueError("sigma_w_rad must be configured or supplied")

        if correlation_time_s is None:
            correlation_time_s = config.g1_correlation_time_s
        if correlation_time_s is None:
            correlation_time_s = self.DEFAULT_CORRELATION_TIME_S
        correlation_time = _finite_nonnegative(
            "correlation_time_s", correlation_time_s)
        if correlation_time <= 0.0:
            raise ValueError("correlation_time_s must be positive")

        step = time_config.dt_s if dt_s is None else dt_s
        step = _finite_nonnegative("dt_s", step)
        if step <= 0.0:
            raise ValueError("dt_s must be positive")

        if (seed is None) == (rng is None):
            raise ValueError("provide exactly one of seed or rng")
        if rng is not None and not isinstance(rng, XorShift32):
            raise TypeError("rng must be an XorShift32 instance")
        if seed is not None:
            rng = XorShift32(seed)
        if rng.seed == 0:
            raise ValueError("wave generation requires a nonzero XorShift32 seed")

        initial = _finite_number("initial_state_rad", initial_state_rad)
        ratio = step / correlation_time
        rho = math.exp(-ratio)
        # -expm1(-2*ratio) is the stable form of 1 - rho**2 for small dt/tau.
        innovation_scale = sigma * math.sqrt(-math.expm1(-2.0 * ratio))
        if not math.isfinite(rho) or not math.isfinite(innovation_scale):
            raise ValueError("wave generator coefficients must be finite")

        self.config = config
        self.sigma_w_rad = sigma
        self.correlation_time_s = correlation_time
        self.dt_s = step
        self.rng = rng
        self.rho = rho
        self.innovation_scale_rad = innovation_scale
        self._current_value_rad = initial
        self._timestamp_s = 0.0

    @property
    def current_value_rad(self) -> float:
        """Current AR(1) state in radian-equivalent forcing units."""
        return self._current_value_rad

    @property
    def timestamp_s(self) -> float:
        """Time reached after the generated steps, in seconds."""
        return self._timestamp_s

    def step(self) -> float:
        """Advance by dt and return the next correlated forcing value in rad."""
        innovation = 0.0
        if self.sigma_w_rad != 0.0:
            innovation = self.innovation_scale_rad * self.rng.normal()
        next_value = self.rho * self._current_value_rad + innovation
        next_time = self._timestamp_s + self.dt_s
        if not math.isfinite(next_value) or not math.isfinite(next_time):
            raise FloatingPointError("wave process produced a non-finite state")
        self._current_value_rad = next_value
        self._timestamp_s = next_time
        return next_value
