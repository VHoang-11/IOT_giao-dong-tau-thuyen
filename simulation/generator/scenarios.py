"""Scenario orchestration for repeatable SVMG vessel-motion sessions.

This module composes the existing roll, G1 wave, IMU and xorshift32 modules;
it does not reimplement their numerical algorithms. Sea-state forcing levels
must be supplied by the caller because the repository has no SS0--SS5 to
``sigma_w`` calibration table.
"""

from collections import deque
from dataclasses import dataclass, replace
import math
from typing import Any, Deque, Dict, Mapping, Optional, Tuple

from simulation.generator.config import (
    DatasetSplit,
    ScenarioCode,
    SimulationConfig,
    WaveExcitationConfig,
    WaveGenerator as WaveGeneratorKind,
)
from simulation.generator.imu_simulator import IMUSample, IMUSimulator
from simulation.generator.rng import XorShift32
from simulation.generator.roll_dynamics import (
    RollDynamics,
    RollState,
    reference_nonlinear_coefficient_rad_minus2,
)
from simulation.generator.wave_generator import CorrelatedWaveGenerator


GRAVITY_ROLL_RMS_THRESHOLD_RAD = math.radians(6.0)
PERSISTENT_HEEL_THRESHOLD_RAD = math.radians(3.0)
PERSISTENT_HEEL_DURATION_S = 120.0
TRANSITION_DURATION_S = 90.0
SAMPLE_COUNT_CONVENTION = "t_i = i*dt for i=0..N-1; duration is N*dt"


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("{} must be a real number".format(name))
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("{} must be finite".format(name))
    return value


def assign_motion_label(
    rolling_rms_roll_rad: Optional[float],
    *,
    parametric_excitation_active: bool,
    heel_offset_rad: float,
    heel_duration_s: float,
    high_roll_threshold_rad: float = GRAVITY_ROLL_RMS_THRESHOLD_RAD,
    persistent_heel_threshold_rad: float = PERSISTENT_HEEL_THRESHOLD_RAD,
    persistent_duration_s: float = PERSISTENT_HEEL_DURATION_S,
) -> Optional[str]:
    """Apply SVMG label priority to clean roll and current event conditions.

    Return ``None`` until a complete rolling-RMS window is available. The
    priority after warm-up is HIGH_ROLL, AMPLITUDE_GROWTH, PERSISTENT_OFFSET,
    then NORMAL.
    """
    heel_offset = _finite("heel_offset_rad", heel_offset_rad)
    heel_duration = _finite("heel_duration_s", heel_duration_s)
    high_threshold = _finite("high_roll_threshold_rad", high_roll_threshold_rad)
    heel_threshold = _finite("persistent_heel_threshold_rad",
                             persistent_heel_threshold_rad)
    persistent_duration = _finite("persistent_duration_s", persistent_duration_s)
    if heel_duration < 0.0 or high_threshold < 0.0 or heel_threshold < 0.0:
        raise ValueError("label thresholds and duration must be non-negative")
    if persistent_duration <= 0.0:
        raise ValueError("persistent_duration_s must be positive")
    if rolling_rms_roll_rad is None:
        return None
    rms = _finite("rolling_rms_roll_rad", rolling_rms_roll_rad)
    if rms < 0.0:
        raise ValueError("rolling_rms_roll_rad must be non-negative")
    if rms >= high_threshold:
        return "HIGH_ROLL"
    if parametric_excitation_active:
        return "AMPLITUDE_GROWTH"
    if (abs(heel_offset) >= heel_threshold and
            heel_duration_s >= persistent_duration):
        return "PERSISTENT_OFFSET"
    return "NORMAL"


@dataclass(frozen=True)
class ScenarioResult:
    """Aligned truth, IMU measurements, labels and replay metadata for a run."""

    scenario_id: ScenarioCode
    nominal_target_label: Optional[str]
    timestamps_s: Tuple[float, ...]
    true_roll_rad: Tuple[float, ...]
    true_roll_rate_rad_s: Tuple[float, ...]
    true_roll_acceleration_rad_s2: Tuple[float, ...]
    wave_excitation_rad: Tuple[float, ...]
    wave_sigma_rad: Tuple[float, ...]
    sea_states: Tuple[str, ...]
    heel_offset_rad: Tuple[float, ...]
    parametric_excitation_amplitude: Tuple[float, ...]
    rolling_rms_roll_rad: Tuple[Optional[float], ...]
    labels: Tuple[Optional[str], ...]
    transition_flags: Tuple[bool, ...]
    imu_samples: Tuple[IMUSample, ...]
    events: Tuple[Dict[str, Any], ...]
    metadata: Dict[str, Any]

    def __post_init__(self) -> None:
        count = len(self.timestamps_s)
        aligned_fields = (
            self.true_roll_rad,
            self.true_roll_rate_rad_s,
            self.true_roll_acceleration_rad_s2,
            self.wave_excitation_rad,
            self.wave_sigma_rad,
            self.sea_states,
            self.heel_offset_rad,
            self.parametric_excitation_amplitude,
            self.rolling_rms_roll_rad,
            self.labels,
            self.transition_flags,
            self.imu_samples,
        )
        if any(len(values) != count for values in aligned_fields):
            raise ValueError("all scenario result streams must have equal length")


class ScenarioRunner:
    """Generate one deterministic scenario session from ``SimulationConfig``.

    ``sea_state_sigma_deg`` is a required caller-provided profile mapping for
    SS0--SS5. These are forcing-level assumptions, not values supplied by the
    repository or verified sea-state measurements.
    """

    _SPLIT_DOMAIN_NAME = {
        DatasetSplit.TRAIN: "train",
        DatasetSplit.VALIDATION: "validation",
        DatasetSplit.TEST_G1: "test_g1",
        DatasetSplit.TEST_G2: "test_g2",
    }
    _SCENARIO_TARGET = {
        ScenarioCode.S0: "NORMAL",
        ScenarioCode.S0B: "NORMAL",
        ScenarioCode.S1: "HIGH_ROLL",
        ScenarioCode.S2: "PERSISTENT_OFFSET",
        ScenarioCode.S3: "AMPLITUDE_GROWTH",
        ScenarioCode.H1: None,
    }

    def __init__(
        self,
        config: SimulationConfig,
        *,
        sea_state_sigma_deg: Mapping[str, float],
        lever_arm_body_m: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        if not isinstance(config, SimulationConfig):
            raise TypeError("config must be a SimulationConfig")
        if config.waves.generator is not WaveGeneratorKind.G1:
            raise ValueError("ScenarioRunner currently supports G1 wave forcing only")
        if not isinstance(sea_state_sigma_deg, Mapping):
            raise TypeError("sea_state_sigma_deg must be a mapping")
        required_states = {"SS0", "SS1", "SS2", "SS3", "SS4", "SS5"}
        if set(sea_state_sigma_deg) != required_states:
            raise ValueError("sea_state_sigma_deg must define SS0 through SS5 exactly")
        profile = {}
        for sea_state, sigma_deg in sea_state_sigma_deg.items():
            sigma = _finite("sea_state_sigma_deg[{}]".format(sea_state), sigma_deg)
            if sigma < 0.0:
                raise ValueError("sea-state sigma values must be non-negative")
            profile[sea_state] = sigma
        if (not isinstance(lever_arm_body_m, (tuple, list)) or
                len(lever_arm_body_m) != 3):
            raise ValueError("lever_arm_body_m must contain three coordinates")
        self.config = config
        self.sea_state_sigma_deg = profile
        self._sea_state_sigma_rad = {
            sea_state: math.radians(sigma_deg)
            for sea_state, sigma_deg in profile.items()
        }
        self.lever_arm_body_m = tuple(
            _finite("lever_arm_body_m", value) for value in lever_arm_body_m)
        self.dt_s = config.time.dt_s
        self.sample_count = config.time.sample_count
        self._window_intervals = 60.0 / self.dt_s
        if not math.isclose(self._window_intervals,
                            round(self._window_intervals), rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("dt_s must divide the 60-second label window")
        # Samples at both window endpoints span exactly 60 s.
        self._window_samples = int(round(self._window_intervals)) + 1

    @staticmethod
    def _uniform(rng: XorShift32, low: float, high: float) -> float:
        return low + (high - low) * rng.random()

    @staticmethod
    def _choice(rng: XorShift32, choices: Tuple[str, ...]) -> str:
        return choices[int(rng.random() * len(choices))]

    def _sample_parameter(self, rng: XorShift32, split: DatasetSplit,
                          name: str) -> float:
        domain_name = self._SPLIT_DOMAIN_NAME[split]
        domain = getattr(self.config.dataset.domains, domain_name)
        parameter = domain.parameters[name]
        return self._uniform(rng, parameter.minimum, parameter.maximum)

    def _sample_event_time(self, rng: XorShift32, split: DatasetSplit) -> float:
        domain_name = self._SPLIT_DOMAIN_NAME[split]
        interval = getattr(self.config.dataset.domains, domain_name).parameters["t0_s"]
        first_index = int(math.ceil(interval.minimum / self.dt_s - 1e-12))
        last_index = int(math.floor(interval.maximum / self.dt_s + 1e-12))
        if last_index < first_index:
            raise ValueError("t0_s domain contains no simulation sample time")
        index = first_index + int(rng.random() * (last_index - first_index + 1))
        return index * self.dt_s

    @staticmethod
    def _child_seed(rng: XorShift32) -> int:
        # xorshift32's zero state is absorbing; remap this one derived child seed.
        value = rng.next_uint32()
        return value if value != 0 else 1

    def _plan(self, scenario: ScenarioCode, split: DatasetSplit,
              rng: XorShift32) -> Dict[str, Any]:
        if scenario is ScenarioCode.S2:
            domain_name = self._SPLIT_DOMAIN_NAME[split]
            t0_max = getattr(self.config.dataset.domains,
                             domain_name).parameters["t0_s"].maximum
            if self.config.time.duration_s - t0_max < 600.0:
                raise ValueError("S2 config must allow at least 600 s after every possible t0_s")
        t0_s = None if scenario is ScenarioCode.S0 else self._sample_event_time(rng, split)
        t0_index = None if t0_s is None else int(round(t0_s / self.dt_s))

        if scenario is ScenarioCode.S3:
            baseline_choices = ("SS1", "SS2")
        else:
            baseline_choices = ("SS0", "SS1", "SS2", "SS3")
        baseline_sea_state = self._choice(rng, baseline_choices)
        baseline_sigma_deg = self.sea_state_sigma_deg[baseline_sea_state]
        baseline_sigma_rad = self._sea_state_sigma_rad[baseline_sea_state]

        event_sea_state = None
        event_sigma_deg = None
        if scenario in (ScenarioCode.S1, ScenarioCode.H1):
            if scenario is ScenarioCode.S1:
                event_sea_state = self._choice(rng, ("SS4", "SS5"))
                # Explicitly supplied S1 forcing range from the task brief.
                lower_bound = max(3.0, math.nextafter(baseline_sigma_deg, math.inf))
                if lower_bound > 4.5:
                    raise ValueError(
                        "S1 baseline sea-state sigma must be below 4.5 degrees")
                event_sigma_deg = self._uniform(rng, lower_bound, 4.5)
            else:
                eligible_high_states = tuple(
                    sea_state for sea_state in ("SS4", "SS5")
                    if self.sea_state_sigma_deg[sea_state] > baseline_sigma_deg
                )
                if not eligible_high_states:
                    raise ValueError("H1 profile must provide SS4/SS5 sigma above baseline")
                event_sea_state = self._choice(rng, eligible_high_states)
                event_sigma_deg = self.sea_state_sigma_deg[event_sea_state]
        event_sigma_rad = (None if event_sigma_deg is None else
                           (self._sea_state_sigma_rad[event_sea_state]
                            if scenario is ScenarioCode.H1
                            else math.radians(event_sigma_deg)))

        heel_offset_deg = None
        heel_duration_s = None
        if scenario is ScenarioCode.S0B:
            heel_offset_deg = self._uniform(rng, 3.0, 6.0)
            heel_duration_s = self._uniform(rng, 20.0, 90.0)
            heel_duration_s = round(heel_duration_s / self.dt_s) * self.dt_s
        elif scenario is ScenarioCode.S2:
            heel_offset_deg = self._uniform(rng, 3.0, 8.0)
            heel_duration_s = self.config.time.duration_s - t0_s
            if heel_duration_s < 600.0:
                raise ValueError("S2 requires at least 600 s after t0_s")
        elif scenario is ScenarioCode.H1:
            heel_offset_deg = self._uniform(rng, 3.0, 6.0)
            heel_duration_s = self.config.time.duration_s - t0_s
        heel_offset_rad = (None if heel_offset_deg is None
                           else math.radians(heel_offset_deg))

        h_value = None
        excitation_omega = None
        if scenario is ScenarioCode.S3:
            h_value = self._uniform(rng, 0.25, 0.5)

        natural_period_s = self._sample_parameter(rng, split, "natural_period_s")
        damping_ratio = self._sample_parameter(rng, split, "damping_ratio")

        # Ω must use the same sampled T0 that configures RollDynamics.
        if scenario is ScenarioCode.S3:
            excitation_omega = 2.0 * (2.0 * math.pi / natural_period_s)

        return {
            "t0_s": t0_s,
            "t0_index": t0_index,
            "baseline_sea_state": baseline_sea_state,
            "baseline_sigma_deg": baseline_sigma_deg,
            "baseline_sigma_rad": baseline_sigma_rad,
            "event_sea_state": event_sea_state,
            "event_sigma_deg": event_sigma_deg,
            "event_sigma_rad": event_sigma_rad,
            "heel_offset_deg": heel_offset_deg,
            "heel_offset_rad": heel_offset_rad,
            "heel_duration_s": heel_duration_s,
            "h_value": h_value,
            "excitation_omega_rad_s": excitation_omega,
            "natural_period_s": natural_period_s,
            "damping_ratio": damping_ratio,
        }

    def _event_values(self, scenario: ScenarioCode, plan: Dict[str, Any],
                      timestamp_s: float) -> Tuple[float, float, float, str]:
        t0_s = plan["t0_s"]
        active = t0_s is not None and timestamp_s >= t0_s
        heel_deg = plan["heel_offset_deg"]
        heel_rad = 0.0
        if active and heel_deg is not None:
            if scenario is ScenarioCode.S0B:
                active = timestamp_s < t0_s + plan["heel_duration_s"]
            if active:
                heel_rad = plan["heel_offset_rad"]

        h_value = plan["h_value"] if active and scenario is ScenarioCode.S3 else 0.0
        sigma_rad = plan["baseline_sigma_rad"]
        sea_state = plan["baseline_sea_state"]
        if active and scenario in (ScenarioCode.S1, ScenarioCode.H1):
            sigma_rad = plan["event_sigma_rad"]
            sea_state = plan["event_sea_state"]
        return heel_rad, h_value or 0.0, sigma_rad, sea_state

    def generate(self, scenario_id: ScenarioCode,
                 *, seed: Optional[int] = None,
                 dataset_split: DatasetSplit = DatasetSplit.TRAIN) -> ScenarioResult:
        """Generate one full scenario session with sample-aligned metadata."""
        try:
            scenario = scenario_id if isinstance(scenario_id, ScenarioCode) else ScenarioCode(scenario_id)
        except (ValueError, TypeError) as exc:
            raise ValueError("unknown scenario id: {!r}".format(scenario_id)) from exc
        try:
            split = dataset_split if isinstance(dataset_split, DatasetSplit) else DatasetSplit(dataset_split)
        except (ValueError, TypeError) as exc:
            raise ValueError("unknown dataset split: {!r}".format(dataset_split)) from exc

        actual_seed = self.config.random_seed if seed is None else seed
        if actual_seed == 0:
            raise ValueError("scenario generation requires a nonzero xorshift32 seed")
        parameter_rng = XorShift32(actual_seed)
        plan = self._plan(scenario, split, parameter_rng)
        wave_seed = self._child_seed(parameter_rng)
        imu_seed = self._child_seed(parameter_rng)
        wave_rng = XorShift32(wave_seed)
        imu_rng = XorShift32(imu_seed)

        kappa_configured = self.config.roll.nonlinear_coefficient
        if scenario is ScenarioCode.S3 and kappa_configured is None:
            kappa_used = reference_nonlinear_coefficient_rad_minus2()
            kappa_source = "provided 25-degree reference; simulation assumption"
        else:
            kappa_used = 0.0 if kappa_configured is None else kappa_configured
            kappa_source = "config" if kappa_configured is not None else "neutral zero"

        roll_config = replace(
            self.config.roll,
            natural_period_s=plan["natural_period_s"],
            damping_ratio=plan["damping_ratio"],
            nonlinear_coefficient=kappa_used,
        )
        roll_model = RollDynamics(roll_config, self.config.time)
        imu_model = IMUSimulator(
            noise_config=self.config.imu,
            time_config=self.config.time,
            rng=imu_rng,
            lever_arm_body_m=self.lever_arm_body_m,
        )
        base_sigma_rad = plan["baseline_sigma_rad"]
        base_wave_config = replace(
            self.config.waves,
            generator=WaveGeneratorKind.G1,
            g1_forcing_std_rad=base_sigma_rad,
        )
        wave_model = CorrelatedWaveGenerator(
            base_wave_config,
            time_config=self.config.time,
            rng=wave_rng,
        )

        timestamps = []
        roll_angles = []
        roll_rates = []
        roll_accelerations = []
        wave_values = []
        wave_sigmas = []
        sea_states = []
        heel_values = []
        h_values = []
        rolling_rms_values = []
        labels = []
        transition_flags = []
        imu_samples = []
        roll_square_window: Deque[float] = deque()
        square_sum = 0.0
        heel_active_since = None
        state = roll_model.initial_state(timestamp_s=0.0)
        active_sigma_rad = base_sigma_rad

        for sample_index in range(self.sample_count):
            timestamp_s = sample_index * self.dt_s
            heel_rad, h_value, sigma_rad, sea_state = self._event_values(
                scenario, plan, timestamp_s)

            if not math.isclose(sigma_rad, active_sigma_rad, rel_tol=0.0, abs_tol=1e-15):
                replacement_wave_config = replace(
                    self.config.waves,
                    generator=WaveGeneratorKind.G1,
                    g1_forcing_std_rad=sigma_rad,
                )
                wave_model = CorrelatedWaveGenerator(
                    replacement_wave_config,
                    time_config=self.config.time,
                    rng=wave_rng,
                    initial_state_rad=wave_model.current_value_rad,
                )
                active_sigma_rad = sigma_rad
            if sample_index > 0:
                wave_value = wave_model.step()
            else:
                wave_value = wave_model.current_value_rad

            alpha = roll_model.angular_acceleration(
                state,
                wave_excitation_rad=wave_value,
                heel_offset_rad=heel_rad,
                parametric_excitation_amplitude=h_value,
                excitation_angular_frequency_rad_s=plan["excitation_omega_rad_s"],
                nonlinear_coefficient_rad_minus2=kappa_used,
            )
            imu_sample = imu_model.sample(state, alpha)

            timestamps.append(timestamp_s)
            roll_angles.append(state.phi_rad)
            roll_rates.append(state.omega_rad_s)
            roll_accelerations.append(alpha)
            wave_values.append(wave_value)
            wave_sigmas.append(sigma_rad)
            sea_states.append(sea_state)
            heel_values.append(heel_rad)
            h_values.append(h_value)
            imu_samples.append(imu_sample)

            square = state.phi_rad * state.phi_rad
            roll_square_window.append(square)
            square_sum += square
            if len(roll_square_window) > self._window_samples:
                square_sum -= roll_square_window.popleft()
            has_full_window = len(roll_square_window) == self._window_samples
            rolling_rms = math.sqrt(max(0.0, square_sum / len(roll_square_window))) \
                if has_full_window else None
            rolling_rms_values.append(rolling_rms)

            if abs(heel_rad) >= PERSISTENT_HEEL_THRESHOLD_RAD:
                if heel_active_since is None:
                    heel_active_since = timestamp_s
                heel_duration = timestamp_s - heel_active_since
            else:
                heel_active_since = None
                heel_duration = 0.0
            label = assign_motion_label(
                rolling_rms,
                parametric_excitation_active=h_value > 0.0,
                heel_offset_rad=heel_rad,
                heel_duration_s=heel_duration,
            )
            labels.append(label)
            t0_s = plan["t0_s"]
            transition_flags.append(
                t0_s is not None and t0_s <= timestamp_s < t0_s + TRANSITION_DURATION_S)

            if sample_index + 1 < self.sample_count:
                next_state = roll_model.step(
                    state,
                    wave_excitation_rad=wave_value,
                    heel_offset_rad=heel_rad,
                    parametric_excitation_amplitude=h_value,
                    excitation_angular_frequency_rad_s=plan["excitation_omega_rad_s"],
                    nonlinear_coefficient_rad_minus2=kappa_used,
                )
                state = RollState(
                    phi_rad=next_state.phi_rad,
                    omega_rad_s=next_state.omega_rad_s,
                    timestamp_s=(sample_index + 1) * self.dt_s,
                )

        observed_labels = sorted({value for value in labels if value is not None})
        outcome_checks: Dict[str, Any] = {
            "observed_labels": observed_labels,
            "high_roll_threshold_reached": "HIGH_ROLL" in observed_labels,
            "persistent_offset_label_reached": "PERSISTENT_OFFSET" in observed_labels,
        }
        if scenario is ScenarioCode.S3:
            start_index = plan["t0_index"]
            end_early = min(start_index + self._window_samples - 1,
                            self.sample_count - 1)
            end_late = self.sample_count - 1
            early_rms = self._rms_window(roll_angles, end_early)
            late_rms = self._rms_window(roll_angles, end_late)
            outcome_checks["amplitude_growth"] = {
                "early_post_t0_rms_rad": early_rms,
                "late_session_rms_rad": late_rms,
                "increased": late_rms > early_rms,
                "criterion": "late 60-second RMS greater than first post-t0 60-second RMS",
            }
        if scenario in (ScenarioCode.S0, ScenarioCode.S0B):
            outcome_checks["expected_outcome_met"] = bool(labels and labels[-1] == "NORMAL")
        elif scenario is ScenarioCode.S1:
            outcome_checks["expected_outcome_met"] = outcome_checks["high_roll_threshold_reached"]
        elif scenario is ScenarioCode.S2:
            outcome_checks["expected_outcome_met"] = outcome_checks["persistent_offset_label_reached"]
        elif scenario is ScenarioCode.S3:
            outcome_checks["expected_outcome_met"] = outcome_checks["amplitude_growth"]["increased"]
        else:
            # H1 is composite; the applicable class follows the priority rule.
            outcome_checks["expected_outcome_met"] = None

        event = self._event_metadata(scenario, plan)
        metadata = {
            "scenario_id": scenario.value,
            "nominal_target_label": self._SCENARIO_TARGET[scenario],
            "dataset_split": split.value,
            "seed": actual_seed,
            "prng": "xorshift32 with independent parameter, wave and IMU streams",
            "child_seeds": {"wave": wave_seed, "imu": imu_seed},
            "final_prng_states": {
                "parameters": parameter_rng.state,
                "wave": wave_rng.state,
                "imu": imu_rng.state,
            },
            "config": self.config.to_dict(),
            "sample_count": self.sample_count,
            "duration_s": self.config.time.duration_s,
            "dt_s": self.dt_s,
            "first_timestamp_s": timestamps[0],
            "last_timestamp_s": timestamps[-1],
            "timestamp_convention": SAMPLE_COUNT_CONVENTION,
            "units": {
                "roll": "rad",
                "roll_rate": "rad/s",
                "roll_acceleration": "rad/s^2",
                "wave_excitation": "rad",
                "accelerometer": "m/s^2",
                "gyroscope": "rad/s",
                "time": "s",
            },
            "sampled_parameters": {
                "t0_s": plan["t0_s"],
                "natural_period_s": plan["natural_period_s"],
                "damping_ratio": plan["damping_ratio"],
                "baseline_sea_state": plan["baseline_sea_state"],
                "baseline_sigma_w_deg": plan["baseline_sigma_deg"],
                "baseline_sigma_w_rad": base_sigma_rad,
                "event_sea_state": plan["event_sea_state"],
                "event_sigma_w_deg": plan["event_sigma_deg"],
                "event_sigma_w_rad": plan["event_sigma_rad"],
                "heel_offset_deg": plan["heel_offset_deg"],
                "heel_offset_rad": plan["heel_offset_rad"],
                "heel_duration_s": plan["heel_duration_s"],
                "parametric_excitation_amplitude": plan["h_value"],
                "excitation_angular_frequency_rad_s": plan["excitation_omega_rad_s"],
                "kappa_configured_rad_minus2": kappa_configured,
                "kappa_used_rad_minus2": kappa_used,
                "kappa_source": kappa_source,
                "sea_state_sigma_profile_deg": dict(self.sea_state_sigma_deg),
                "wave_correlation_time_s": wave_model.correlation_time_s,
                "imu_lever_arm_body_m": self.lever_arm_body_m,
            },
            "events": [event] if event is not None else [],
            "outcome_checks": outcome_checks,
            "label_rules": {
                "high_roll_rms_threshold_deg": 6.0,
                "persistent_heel_threshold_deg": 3.0,
                "persistent_heel_duration_s": PERSISTENT_HEEL_DURATION_S,
                "transition_duration_s": TRANSITION_DURATION_S,
                "rms_window_s": 60.0,
                "rms_source": "clean true roll before IMU noise",
            },
        }
        return ScenarioResult(
            scenario_id=scenario,
            nominal_target_label=self._SCENARIO_TARGET[scenario],
            timestamps_s=tuple(timestamps),
            true_roll_rad=tuple(roll_angles),
            true_roll_rate_rad_s=tuple(roll_rates),
            true_roll_acceleration_rad_s2=tuple(roll_accelerations),
            wave_excitation_rad=tuple(wave_values),
            wave_sigma_rad=tuple(wave_sigmas),
            sea_states=tuple(sea_states),
            heel_offset_rad=tuple(heel_values),
            parametric_excitation_amplitude=tuple(h_values),
            rolling_rms_roll_rad=tuple(rolling_rms_values),
            labels=tuple(labels),
            transition_flags=tuple(transition_flags),
            imu_samples=tuple(imu_samples),
            events=tuple([event] if event is not None else []),
            metadata=metadata,
        )

    def _event_metadata(self, scenario: ScenarioCode,
                        plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        t0_s = plan["t0_s"]
        if t0_s is None:
            return None
        event: Dict[str, Any] = {"t0_s": t0_s}
        if scenario is ScenarioCode.S0B:
            event.update({
                "type": "temporary_heel_offset",
                "end_s": t0_s + plan["heel_duration_s"],
                "heel_offset_deg": plan["heel_offset_deg"],
                "expected_label": "NORMAL",
            })
        elif scenario is ScenarioCode.S1:
            event.update({
                "type": "high_wave_forcing",
                "sea_state": plan["event_sea_state"],
                "sigma_w_deg": plan["event_sigma_deg"],
                "expected_label": "HIGH_ROLL",
            })
        elif scenario is ScenarioCode.S2:
            event.update({
                "type": "persistent_heel_offset",
                "end_s": self.config.time.duration_s,
                "heel_offset_deg": plan["heel_offset_deg"],
                "minimum_label_delay_s": PERSISTENT_HEEL_DURATION_S,
                "expected_label": "PERSISTENT_OFFSET",
            })
        elif scenario is ScenarioCode.S3:
            event.update({
                "type": "parametric_excitation",
                "end_s": self.config.time.duration_s,
                "h": plan["h_value"],
                "Omega_rad_s": plan["excitation_omega_rad_s"],
                "expected_label": "AMPLITUDE_GROWTH",
            })
        elif scenario is ScenarioCode.H1:
            event.update({
                "type": "combined_high_sea_and_heel",
                "end_s": self.config.time.duration_s,
                "sea_state": plan["event_sea_state"],
                "sigma_w_deg": plan["event_sigma_deg"],
                "heel_offset_deg": plan["heel_offset_deg"],
                "label_policy": "derived from clean roll using priority rules",
            })
        return event

    def _rms_window(self, signal: list, end_index: int) -> float:
        start_index = end_index - self._window_samples + 1
        if start_index < 0:
            start_index = 0
        values = signal[start_index:end_index + 1]
        if not values:
            return 0.0
        return math.sqrt(sum(value * value for value in values) / len(values))


def generate_scenario(
    config: SimulationConfig,
    scenario_id: ScenarioCode,
    *,
    sea_state_sigma_deg: Mapping[str, float],
    seed: Optional[int] = None,
    dataset_split: DatasetSplit = DatasetSplit.TRAIN,
    lever_arm_body_m: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> ScenarioResult:
    """Convenience wrapper for generating one configured scenario session."""
    return ScenarioRunner(
        config,
        sea_state_sigma_deg=sea_state_sigma_deg,
        lever_arm_body_m=lever_arm_body_m,
    ).generate(scenario_id, seed=seed, dataset_split=dataset_split)
