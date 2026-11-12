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
    GrowthCriterion,
    LabelingVersion,
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
LABEL_PRIORITY_V2 = (
    "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH", "NORMAL")


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
class MotionPhenotypeFlags:
    """Independent v2 phenotype states; ``None`` means not yet decidable."""

    high_roll_active: Optional[bool]
    persistent_offset_active: Optional[bool]
    observed_amplitude_growth: Optional[bool]


@dataclass(frozen=True)
class MotionLabelMetrics:
    """Causal v2 intermediate metrics, with units explicit in field names."""

    rms_centered_60_rad: Optional[float]
    mean_roll_180_rad: Optional[float]
    persistent_offset_duration_s: Optional[float]
    rms_trend_slope_deg_per_min: Optional[float]
    growth_ratio_180: Optional[float]


@dataclass(frozen=True)
class CausalLabelStep:
    """One streaming label decision and its independent phenotype evidence."""

    label: Optional[str]
    flags: MotionPhenotypeFlags
    metrics: MotionLabelMetrics


class CausalMotionLabelerV2:
    """Streaming labeler that only consumes roll samples through current time.

    A v2 decision requires configured HIGH_ROLL and growth criteria. Dataset
    readiness additionally requires those thresholds to be marked calibrated.
    The default config leaves criteria unset; then this class reports
    metrics/flags where possible and returns no primary class. Heel evidence
    comes from signed roll means, never scenario or generator metadata.
    """

    def __init__(self, config: SimulationConfig) -> None:
        if not isinstance(config, SimulationConfig):
            raise TypeError("config must be a SimulationConfig")
        self.config = config.labeling
        self.dt_s = config.time.dt_s
        self._n60 = self._sample_count(60.0)
        self._n_offset = self._sample_count(self.config.persistent_offset_window_s)
        self._n_growth = self._sample_count(self.config.growth_window_s)
        self._ratio_lag = self._sample_count(self.config.growth_ratio_lag_s)
        self._roll60 = deque()
        self._roll180 = deque()
        self._mean60 = self._m2_60 = 0.0
        self._sum180 = 0.0
        self._growth_values = deque()
        self._growth_sum = self._growth_sum_xy = 0.0
        self._centered_history: List[Optional[float]] = []
        self._sample_index = -1
        self._last_timestamp: Optional[float] = None
        self._offset_sign = 0
        self._offset_since: Optional[float] = None
        self._growth_since: Optional[float] = None
        self._high_threshold_rad = (
            None if self.config.high_roll_centered_threshold_deg is None else
            math.radians(self.config.high_roll_centered_threshold_deg))
        self._offset_threshold_rad = math.radians(
            self.config.persistent_offset_threshold_deg)
        self._ratio_floor_rad = (
            None if self.config.growth_ratio_floor_deg is None else
            math.radians(self.config.growth_ratio_floor_deg))

    def _sample_count(self, duration_s: float) -> int:
        count = duration_s / self.dt_s
        rounded = round(count)
        if not math.isclose(count, rounded, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("labeling windows must be integral multiples of dt_s")
        # Include both endpoints so the represented interval is exactly duration_s.
        return int(rounded) + 1

    @staticmethod
    def _append_window(window: Any, value: float, maximum: int) -> Optional[float]:
        window.append(value)
        if len(window) > maximum:
            return window.popleft()
        return None

    def _append_growth_value(self, value: float) -> Optional[float]:
        count = len(self._growth_values)
        if count < self._n_growth:
            self._growth_sum_xy += count * value
            self._growth_sum += value
            self._growth_values.append(value)
            return None
        removed = self._growth_values.popleft()
        # Shift the remaining sample indices left by one, then append at N-1.
        self._growth_sum_xy = (
            self._growth_sum_xy - (self._growth_sum - removed)
            + (self._n_growth - 1) * value
        )
        self._growth_sum += value - removed
        self._growth_values.append(value)
        sum_x = self._n_growth * (self._n_growth - 1) / 2.0
        sum_x2 = (self._n_growth * (self._n_growth - 1) *
                  (2 * self._n_growth - 1) / 6.0)
        denominator = self._n_growth * sum_x2 - sum_x * sum_x
        slope_per_sample = (
            self._n_growth * self._growth_sum_xy - sum_x * self._growth_sum
        ) / denominator
        slope_rad_s = slope_per_sample / self.dt_s
        return math.degrees(slope_rad_s) * 60.0

    def step(self, timestamp_s: float, roll_rad: float) -> CausalLabelStep:
        """Consume one current sample and return a decision without look-ahead."""
        timestamp = _finite("timestamp_s", timestamp_s)
        roll = _finite("roll_rad", roll_rad)
        if self._last_timestamp is not None:
            expected = self._last_timestamp + self.dt_s
            if not math.isclose(timestamp, expected, rel_tol=0.0, abs_tol=1e-9):
                raise ValueError("labeler timestamps must increase by configured dt_s")
        self._last_timestamp = timestamp
        self._sample_index += 1

        if len(self._roll60) == self._n60:
            removed = self._roll60.popleft()
            old_count = self._n60
            new_count = old_count - 1
            if new_count:
                new_mean = (old_count * self._mean60 - removed) / new_count
                self._m2_60 -= (removed - self._mean60) * (removed - new_mean)
                self._mean60 = new_mean
            else:
                self._mean60 = self._m2_60 = 0.0
        self._roll60.append(roll)
        new_count = len(self._roll60)
        delta = roll - self._mean60
        self._mean60 += delta / new_count
        self._m2_60 += delta * (roll - self._mean60)
        rms_centered = None
        if len(self._roll60) == self._n60:
            variance = max(0.0, self._m2_60 / self._n60)
            rms_centered = math.sqrt(variance)

        removed180 = self._append_window(self._roll180, roll, self._n_offset)
        if removed180 is not None:
            self._sum180 -= removed180
        self._sum180 += roll
        mean180 = (self._sum180 / self._n_offset
                   if len(self._roll180) == self._n_offset else None)

        self._centered_history.append(rms_centered)
        slope = None
        if rms_centered is not None:
            slope = self._append_growth_value(rms_centered)
        ratio = None
        old_index = self._sample_index - self._ratio_lag
        if (rms_centered is not None and old_index >= 0 and
                old_index < len(self._centered_history)):
            older = self._centered_history[old_index]
            if older is not None and older > 0.0:
                floor = 0.0 if self._ratio_floor_rad is None else self._ratio_floor_rad
                ratio = rms_centered / max(older, floor)

        persistent_duration = None
        persistent_active: Optional[bool] = None
        if mean180 is not None:
            if abs(mean180) >= self._offset_threshold_rad:
                sign = 1 if mean180 > 0.0 else -1
                if sign != self._offset_sign:
                    self._offset_sign = sign
                    self._offset_since = timestamp
                persistent_duration = timestamp - (
                    timestamp if self._offset_since is None else self._offset_since)
                persistent_active = (
                    persistent_duration >= self.config.persistent_offset_duration_s)
            else:
                self._offset_sign = 0
                self._offset_since = None
                persistent_duration = 0.0
                persistent_active = False

        high_active: Optional[bool] = None
        if rms_centered is not None and self._high_threshold_rad is not None:
            high_active = rms_centered >= self._high_threshold_rad

        growth_condition: Optional[bool] = None
        criterion = self.config.growth_criterion
        slope_condition = (
            None if slope is None or self.config.growth_slope_threshold_deg_per_min is None
            else slope >= self.config.growth_slope_threshold_deg_per_min
        )
        ratio_condition = (
            None if ratio is None or self.config.growth_ratio_threshold is None
            else ratio >= self.config.growth_ratio_threshold
        )
        if criterion is GrowthCriterion.SLOPE and slope_condition is not None:
            growth_condition = slope_condition
        elif criterion is GrowthCriterion.RATIO and ratio_condition is not None:
            growth_condition = ratio_condition
        elif (criterion is GrowthCriterion.SLOPE_AND_RATIO and
              slope_condition is not None and ratio_condition is not None):
            growth_condition = slope_condition and ratio_condition
        elif (criterion is GrowthCriterion.SLOPE_OR_RATIO and
              slope_condition is not None and ratio_condition is not None):
            growth_condition = slope_condition or ratio_condition

        growth_active: Optional[bool] = None
        if growth_condition is not None:
            if growth_condition:
                if self._growth_since is None:
                    self._growth_since = timestamp
                growth_active = (
                    timestamp - self._growth_since >=
                    self.config.growth_confirmation_s
                )
            else:
                self._growth_since = None
                growth_active = False

        metrics = MotionLabelMetrics(
            rms_centered_60_rad=rms_centered,
            mean_roll_180_rad=mean180,
            persistent_offset_duration_s=persistent_duration,
            rms_trend_slope_deg_per_min=slope,
            growth_ratio_180=ratio,
        )
        flags = MotionPhenotypeFlags(
            high_roll_active=high_active,
            persistent_offset_active=persistent_active,
            observed_amplitude_growth=growth_active,
        )

        ready_metrics = (high_active is not None and persistent_active is not None and
                         growth_active is not None)
        label = None
        if self.config.labeling_v2_configured and ready_metrics:
            if high_active:
                label = "HIGH_ROLL"
            elif persistent_active:
                label = "PERSISTENT_OFFSET"
            elif growth_active:
                label = "AMPLITUDE_GROWTH"
            else:
                label = "NORMAL"
        return CausalLabelStep(label=label, flags=flags, metrics=metrics)


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
    labels_v1: Tuple[Optional[str], ...]
    labels_v2: Tuple[Optional[str], ...]
    phenotype_flags_v2: Tuple[MotionPhenotypeFlags, ...]
    labeling_metrics_v2: Tuple[MotionLabelMetrics, ...]
    selected_labeling_version: LabelingVersion
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
            self.labels_v1,
            self.labels_v2,
            self.phenotype_flags_v2,
            self.labeling_metrics_v2,
            self.transition_flags,
            self.imu_samples,
        )
        if any(len(values) != count for values in aligned_fields):
            raise ValueError("all scenario result streams must have equal length")

    def labels_for(self, version: LabelingVersion) -> Tuple[Optional[str], ...]:
        """Return one labeler stream without changing the selected ``labels``."""
        parsed = version if isinstance(version, LabelingVersion) else LabelingVersion(version)
        return self.labels_v1 if parsed is LabelingVersion.V1 else self.labels_v2


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
        sea_state_sigma_deg: Optional[Mapping[str, float]] = None,
        lever_arm_body_m: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        if not isinstance(config, SimulationConfig):
            raise TypeError("config must be a SimulationConfig")
        if config.waves.generator is not WaveGeneratorKind.G1:
            raise ValueError("ScenarioRunner currently supports G1 wave forcing only")
        if sea_state_sigma_deg is None:
            profile = config.sea_state_profile.sigma_w_by_state_deg
            profile_rad = dict(config.sea_state_profile.sigma_w_by_state_rad)
            profile_id = config.sea_state_profile.profile_id
            profile_status = config.sea_state_profile.calibration_status.value
        else:
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
            if any(profile[left] >= profile[right]
                   for left, right in zip(("SS0", "SS1", "SS2", "SS3", "SS4"),
                                          ("SS1", "SS2", "SS3", "SS4", "SS5"))):
                raise ValueError("sea-state sigma values must increase from SS0 to SS5")
            profile_rad = {state: math.radians(value) for state, value in profile.items()}
            profile_id = "caller-supplied-unverified"
            profile_status = "candidate"
        if (not isinstance(lever_arm_body_m, (tuple, list)) or
                len(lever_arm_body_m) != 3):
            raise ValueError("lever_arm_body_m must contain three coordinates")
        self.config = config
        self.sea_state_sigma_deg = profile
        self._sea_state_sigma_rad = profile_rad
        self.sea_state_profile_id = profile_id
        self.sea_state_profile_status = profile_status
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
            eligible_high_states = tuple(
                sea_state for sea_state in ("SS4", "SS5")
                if self.sea_state_sigma_deg[sea_state] > baseline_sigma_deg
            )
            if not eligible_high_states:
                raise ValueError("profile must provide SS4/SS5 sigma above baseline")
            event_sea_state = self._choice(rng, eligible_high_states)
            event_sigma_deg = self.sea_state_sigma_deg[event_sea_state]
            if scenario is ScenarioCode.S1 and not 3.0 <= event_sigma_deg <= 4.5:
                raise ValueError(
                    "S1 SS4/SS5 profile sigma must lie within the specified 3-4.5 degree range")
        event_sigma_rad = (None if event_sea_state is None else
                           self._sea_state_sigma_rad[event_sea_state])

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
                 dataset_split: DatasetSplit = DatasetSplit.TRAIN,
                 labeling_version: LabelingVersion = LabelingVersion.V1) -> ScenarioResult:
        """Generate one full scenario session with sample-aligned metadata."""
        try:
            scenario = scenario_id if isinstance(scenario_id, ScenarioCode) else ScenarioCode(scenario_id)
        except (ValueError, TypeError) as exc:
            raise ValueError("unknown scenario id: {!r}".format(scenario_id)) from exc
        try:
            split = dataset_split if isinstance(dataset_split, DatasetSplit) else DatasetSplit(dataset_split)
        except (ValueError, TypeError) as exc:
            raise ValueError("unknown dataset split: {!r}".format(dataset_split)) from exc
        try:
            label_version = (labeling_version if isinstance(labeling_version, LabelingVersion)
                             else LabelingVersion(labeling_version))
        except (ValueError, TypeError) as exc:
            raise ValueError("unknown labeling version: {!r}".format(labeling_version)) from exc

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
        v2_labeler = CausalMotionLabelerV2(self.config)

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
        labels_v1 = []
        labels_v2 = []
        phenotype_flags_v2 = []
        labeling_metrics_v2 = []
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
            label_v1 = assign_motion_label(
                rolling_rms,
                parametric_excitation_active=h_value > 0.0,
                heel_offset_rad=heel_rad,
                heel_duration_s=heel_duration,
            )
            v2_step = v2_labeler.step(timestamp_s, state.phi_rad)
            labels_v1.append(label_v1)
            labels_v2.append(v2_step.label)
            phenotype_flags_v2.append(v2_step.flags)
            labeling_metrics_v2.append(v2_step.metrics)
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

        selected_labels = labels_v1 if label_version is LabelingVersion.V1 else labels_v2
        observed_labels = sorted({value for value in labels_v1 if value is not None})
        observed_labels_v2 = sorted({value for value in labels_v2 if value is not None})
        outcome_checks: Dict[str, Any] = {
            "observed_labels": observed_labels,
            "high_roll_threshold_reached": "HIGH_ROLL" in observed_labels,
            "persistent_offset_label_reached": "PERSISTENT_OFFSET" in observed_labels,
            "observed_labels_v2": observed_labels_v2,
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
            outcome_checks["expected_outcome_met"] = bool(
                labels_v1 and labels_v1[-1] == "NORMAL")
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
            "labeling": {
                "selected_version": label_version.value,
                "available_versions": [LabelingVersion.V1.value,
                                        LabelingVersion.V2.value],
                "v1_status": "ready",
                "v2_status": ("ready" if self.config.labeling.labeling_v2_ready
                              else "not_ready_missing_calibrated_thresholds"),
                "v2_ready": self.config.labeling.labeling_v2_ready,
                "v2_configured": self.config.labeling.labeling_v2_configured,
                "v2_threshold_calibration_status": (
                    self.config.labeling.threshold_calibration_status.value),
                "v2_thresholds": {
                    "high_roll_centered_threshold_deg": (
                        self.config.labeling.high_roll_centered_threshold_deg),
                    "persistent_offset_threshold_deg": (
                        self.config.labeling.persistent_offset_threshold_deg),
                    "persistent_offset_window_s": (
                        self.config.labeling.persistent_offset_window_s),
                    "persistent_offset_duration_s": (
                        self.config.labeling.persistent_offset_duration_s),
                    "growth_criterion": (
                        self.config.labeling.growth_criterion.value
                        if self.config.labeling.growth_criterion is not None else None),
                    "growth_window_s": self.config.labeling.growth_window_s,
                    "growth_ratio_lag_s": self.config.labeling.growth_ratio_lag_s,
                    "growth_slope_threshold_deg_per_min": (
                        self.config.labeling.growth_slope_threshold_deg_per_min),
                    "growth_ratio_threshold": self.config.labeling.growth_ratio_threshold,
                    "growth_ratio_floor_deg": self.config.labeling.growth_ratio_floor_deg,
                    "growth_confirmation_s": self.config.labeling.growth_confirmation_s,
                },
                "v2_unresolved_thresholds": list(
                    self.config.labeling.unresolved_v2_thresholds),
                "v2_priority": list(LABEL_PRIORITY_V2),
                "v2_warmup_requirement_s": (
                    60.0 + self.config.labeling.growth_window_s
                    if self.config.labeling.growth_criterion in (
                        GrowthCriterion.SLOPE, GrowthCriterion.SLOPE_AND_RATIO,
                        GrowthCriterion.SLOPE_OR_RATIO)
                    else max(60.0, self.config.labeling.persistent_offset_window_s,
                             self.config.labeling.growth_ratio_lag_s)
                ),
                "official_dataset_ready": self.config.official_dataset_ready,
            },
            "sea_state_profile": {
                "profile_id": self.sea_state_profile_id,
                "calibration_status": self.sea_state_profile_status,
                "sigma_w_by_state_deg_equivalent": dict(self.sea_state_sigma_deg),
                "sigma_w_by_state_rad": dict(self._sea_state_sigma_rad),
                "physical_wave_height_calibration": False,
            },
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
                "labeling_v1": {
                    "high_roll_rms_threshold_deg": 6.0,
                    "high_roll_metric": "60-second RMS about zero",
                    "priority": ["HIGH_ROLL", "AMPLITUDE_GROWTH",
                                 "PERSISTENT_OFFSET", "NORMAL"],
                },
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
            labels=tuple(selected_labels),
            labels_v1=tuple(labels_v1),
            labels_v2=tuple(labels_v2),
            phenotype_flags_v2=tuple(phenotype_flags_v2),
            labeling_metrics_v2=tuple(labeling_metrics_v2),
            selected_labeling_version=label_version,
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
    sea_state_sigma_deg: Optional[Mapping[str, float]] = None,
    seed: Optional[int] = None,
    dataset_split: DatasetSplit = DatasetSplit.TRAIN,
    labeling_version: LabelingVersion = LabelingVersion.V1,
    lever_arm_body_m: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> ScenarioResult:
    """Convenience wrapper for generating one configured scenario session."""
    return ScenarioRunner(
        config,
        sea_state_sigma_deg=sea_state_sigma_deg,
        lever_arm_body_m=lever_arm_body_m,
    ).generate(scenario_id, seed=seed, dataset_split=dataset_split,
                labeling_version=labeling_version)
