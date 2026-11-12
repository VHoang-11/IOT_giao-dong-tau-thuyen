"""Container-vessel roll dynamics with a Semi-Implicit Euler integrator.

The model is a simulation component, not a validated vessel stability model.
All angles are radians, angular rates are rad/s, and angular accelerations are
rad/s². The input wave forcing is the equivalent ``w(t)`` term in radians.
"""

from dataclasses import dataclass
import math
from typing import Optional

from simulation.generator.config import RollDynamicsConfig, SimulationTimeConfig


def _finite_number(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("{} must be a real number".format(name))
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("{} must be finite".format(name))
    return value


@dataclass(frozen=True)
class RollState:
    """Instantaneous roll state, represented entirely in SI-compatible units."""

    phi_rad: float
    omega_rad_s: float
    timestamp_s: float

    def __post_init__(self) -> None:
        for name in ("phi_rad", "omega_rad_s", "timestamp_s"):
            _finite_number(name, getattr(self, name))


def reference_nonlinear_coefficient_rad_minus2() -> float:
    """Return the provided reference κ = 1/(25 degrees converted to radians)².

    This is only the project's suggested simulation reference, not an
    experimentally validated coefficient for a real vessel. It is not applied
    automatically; pass it in config or as a step override when desired.
    """
    reference_angle_rad = math.radians(25.0)
    return 1.0 / (reference_angle_rad * reference_angle_rad)


class RollDynamics:
    """Evaluate angular acceleration and advance roll state by one time step.

    ``natural_period_s`` and ``damping_ratio`` must be set in the supplied
    ``RollDynamicsConfig``. Optional excitation and nonlinear parameters use a
    neutral zero contribution when left unset; κ can be set to the documented
    reference via :func:`reference_nonlinear_coefficient_rad_minus2`.
    """

    def __init__(self, config: RollDynamicsConfig,
                 time_config: Optional[SimulationTimeConfig] = None) -> None:
        if not isinstance(config, RollDynamicsConfig):
            raise TypeError("config must be a RollDynamicsConfig")
        if time_config is None:
            time_config = SimulationTimeConfig()
        if not isinstance(time_config, SimulationTimeConfig):
            raise TypeError("time_config must be a SimulationTimeConfig")
        if config.natural_period_s is None:
            raise ValueError("natural_period_s (T0) must be configured")
        if config.damping_ratio is None:
            raise ValueError("damping_ratio (zeta) must be configured")

        self.config = config
        self.time_config = time_config
        self.dt_s = _finite_number("dt_s", time_config.dt_s)
        if self.dt_s <= 0.0:
            raise ValueError("dt_s must be positive")

        self.omega0_rad_s = 2.0 * math.pi / config.natural_period_s
        if not math.isfinite(self.omega0_rad_s):
            raise ValueError("natural period produces a non-finite omega0")
        self._omega0_squared = self.omega0_rad_s * self.omega0_rad_s
        if not math.isfinite(self._omega0_squared):
            raise ValueError("natural period produces a non-finite omega0 squared")

    def initial_state(self, timestamp_s: float = 0.0) -> RollState:
        """Build initial state from configured roll angle and angular rate."""
        timestamp = _finite_number("timestamp_s", timestamp_s)
        return RollState(
            phi_rad=self.config.initial_roll_rad,
            omega_rad_s=self.config.initial_roll_rate_rad_s,
            timestamp_s=timestamp,
        )

    def angular_acceleration(
        self,
        state: RollState,
        *,
        wave_excitation_rad: float = 0.0,
        heel_offset_rad: Optional[float] = None,
        parametric_excitation_amplitude: Optional[float] = None,
        excitation_angular_frequency_rad_s: Optional[float] = None,
        nonlinear_coefficient_rad_minus2: Optional[float] = None,
    ) -> float:
        """Compute φ'' in rad/s² from the configured model at ``state``.

        ``excitation_angular_frequency_rad_s`` is Ω in rad/s, not frequency in
        Hz. For a nonzero h, Ω must be configured or supplied explicitly.
        """
        if not isinstance(state, RollState):
            raise TypeError("state must be a RollState")
        phi = _finite_number("state.phi_rad", state.phi_rad)
        omega = _finite_number("state.omega_rad_s", state.omega_rad_s)
        timestamp = _finite_number("state.timestamp_s", state.timestamp_s)
        wave = _finite_number("wave_excitation_rad", wave_excitation_rad)

        heel = (self.config.heel_offset_rad if heel_offset_rad is None
                else heel_offset_rad)
        heel = _finite_number("heel_offset_rad", heel)
        h = (self.config.parametric_excitation_amplitude
             if parametric_excitation_amplitude is None
             else parametric_excitation_amplitude)
        h = 0.0 if h is None else _finite_number("parametric_excitation_amplitude", h)
        excitation_omega = (
            self.config.parametric_excitation_angular_frequency_rad_s
            if excitation_angular_frequency_rad_s is None
            else excitation_angular_frequency_rad_s
        )
        if excitation_omega is not None:
            excitation_omega = _finite_number(
                "excitation_angular_frequency_rad_s", excitation_omega)
        elif h != 0.0:
            raise ValueError("Ω must be set when parametric excitation h is nonzero")
        else:
            excitation_omega = 0.0

        kappa = (self.config.nonlinear_coefficient
                 if nonlinear_coefficient_rad_minus2 is None
                 else nonlinear_coefficient_rad_minus2)
        kappa = 0.0 if kappa is None else _finite_number(
            "nonlinear_coefficient_rad_minus2", kappa)

        phase = excitation_omega * timestamp
        if not math.isfinite(phase):
            raise ValueError("Ω * timestamp_s must be finite")
        try:
            parametric_factor = 1.0 + h * math.cos(phase)
            acceleration = (
                self._omega0_squared * (heel + wave)
                - 2.0 * self.config.damping_ratio * self.omega0_rad_s * omega
                - self._omega0_squared * parametric_factor * phi
                - self._omega0_squared * kappa * (phi ** 3)
            )
        except (OverflowError, ValueError) as exc:
            raise FloatingPointError("roll acceleration calculation overflowed") from exc
        if not math.isfinite(acceleration):
            raise FloatingPointError("roll acceleration is not finite")
        return acceleration

    def step(
        self,
        state: RollState,
        *,
        dt_s: Optional[float] = None,
        wave_excitation_rad: float = 0.0,
        heel_offset_rad: Optional[float] = None,
        parametric_excitation_amplitude: Optional[float] = None,
        excitation_angular_frequency_rad_s: Optional[float] = None,
        nonlinear_coefficient_rad_minus2: Optional[float] = None,
    ) -> RollState:
        """Advance one step using Semi-Implicit (symplectic) Euler.

        First update ``omega`` from the current acceleration, then update
        ``phi`` from that new angular rate. The default step is dt from the
        supplied ``SimulationTimeConfig``; no degree conversion or angle clamp
        is applied.
        """
        step_s = self.dt_s if dt_s is None else _finite_number("dt_s", dt_s)
        if step_s <= 0.0:
            raise ValueError("dt_s must be positive")
        acceleration = self.angular_acceleration(
            state,
            wave_excitation_rad=wave_excitation_rad,
            heel_offset_rad=heel_offset_rad,
            parametric_excitation_amplitude=parametric_excitation_amplitude,
            excitation_angular_frequency_rad_s=excitation_angular_frequency_rad_s,
            nonlinear_coefficient_rad_minus2=nonlinear_coefficient_rad_minus2,
        )
        omega_next = state.omega_rad_s + acceleration * step_s
        phi_next = state.phi_rad + omega_next * step_s
        timestamp_next = state.timestamp_s + step_s
        if not all(math.isfinite(value)
                   for value in (omega_next, phi_next, timestamp_next)):
            raise FloatingPointError("roll state update produced a non-finite value")
        return RollState(phi_next, omega_next, timestamp_next)
