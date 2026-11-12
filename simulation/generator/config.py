"""Typed, validated configuration objects for SVMG simulations.

Angles used by the simulation configuration are radians and angular rates are
radians per second. Fields containing ``_deg`` are intentionally absent here;
conversion to degrees belongs at an output or device-contract boundary.
"""

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
import math
from typing import Any, Dict, Optional, Tuple


class WaveGenerator(str, Enum):
    """Wave excitation families described by the simulation README."""

    G1 = "G1"
    G2 = "G2"


class ScenarioCode(str, Enum):
    """Scenario identifiers currently named in the project README."""

    S0 = "S0"
    S0B = "S0b"
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    H1 = "H1"


class DatasetSplit(str, Enum):
    """Evaluation domains required by the M2 plan."""

    TRAIN = "Train"
    VALIDATION = "Validation"
    TEST_G1 = "Test-G1"
    TEST_G2 = "Test-G2"


class LabelingVersion(str, Enum):
    """Versioned motion-label definitions used by scenario generation."""

    V1 = "v1"
    V2 = "v2"


class GrowthCriterion(str, Enum):
    """How configured causal growth metrics combine into one phenotype."""

    SLOPE = "slope"
    RATIO = "ratio"
    SLOPE_AND_RATIO = "slope_and_ratio"
    SLOPE_OR_RATIO = "slope_or_ratio"


class ProfileCalibrationStatus(str, Enum):
    """Whether a sea-state forcing profile is only a candidate or calibrated."""

    CANDIDATE = "candidate"
    CALIBRATED = "calibrated"


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError("{} must be finite".format(name))


def _optional_number(name: str, value: Optional[float], *, minimum: Optional[float] = None,
                     strict_minimum: bool = False) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("{} must be a number or None".format(name))
    _require_finite(name, float(value))
    if minimum is not None:
        invalid = value <= minimum if strict_minimum else value < minimum
        if invalid:
            operator = ">" if strict_minimum else ">="
            raise ValueError("{} must be {} {}".format(name, operator, minimum))


_SEA_STATE_CODES = ("SS0", "SS1", "SS2", "SS3", "SS4", "SS5")
_CANDIDATE_SEA_STATE_SIGMA_DEG = {
    "SS0": 0.5,
    "SS1": 0.9,
    "SS2": 1.5,
    "SS3": 2.2,
    "SS4": 3.0,
    "SS5": 4.5,
}


def _candidate_sea_state_sigma_rad() -> Dict[str, float]:
    """Convert the approved candidate profile to canonical radians once."""
    return {state: math.radians(value)
            for state, value in _CANDIDATE_SEA_STATE_SIGMA_DEG.items()}


@dataclass(frozen=True)
class SeaStateProfileConfig:
    """Equivalent-angle wave forcing profile, stored canonically in radians.

    The default profile is an approved simulation candidate, not an empirical
    calibration or a mapping to physical wave height.
    """

    profile_id: str = "svmg-sea-state-candidate-v1"
    calibration_status: ProfileCalibrationStatus = ProfileCalibrationStatus.CANDIDATE
    sigma_w_by_state_rad: Dict[str, float] = field(
        default_factory=_candidate_sea_state_sigma_rad)

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id.strip():
            raise ValueError("profile_id must be a non-empty string")
        if not isinstance(self.calibration_status, ProfileCalibrationStatus):
            raise TypeError("calibration_status must be a ProfileCalibrationStatus")
        if not isinstance(self.sigma_w_by_state_rad, dict):
            raise TypeError("sigma_w_by_state_rad must be a mapping")
        if set(self.sigma_w_by_state_rad) != set(_SEA_STATE_CODES):
            raise ValueError("profile must define SS0 through SS5 exactly")
        previous = -1.0
        for state in _SEA_STATE_CODES:
            value = self.sigma_w_by_state_rad[state]
            _optional_number("sigma_w_by_state_rad[{}]".format(state), value,
                             minimum=0.0)
            if value <= previous:
                raise ValueError("sea-state sigma values must increase from SS0 to SS5")
            previous = float(value)

    @classmethod
    def from_degrees(
        cls,
        sigma_w_by_state_deg: Dict[str, float],
        *,
        profile_id: str = "svmg-custom-sea-state-profile",
        calibration_status: ProfileCalibrationStatus = ProfileCalibrationStatus.CANDIDATE,
    ) -> "SeaStateProfileConfig":
        """Convert degree-equivalent forcing values at the config boundary."""
        if not isinstance(sigma_w_by_state_deg, dict):
            raise TypeError("sigma_w_by_state_deg must be a dictionary")
        return cls(
            profile_id=profile_id,
            calibration_status=calibration_status,
            sigma_w_by_state_rad={
                state: math.radians(value)
                for state, value in sigma_w_by_state_deg.items()
            },
        )

    @property
    def sigma_w_by_state_deg(self) -> Dict[str, float]:
        """Return a metadata/display copy in degree-equivalent units."""
        return {state: round(math.degrees(value), 12)
                for state, value in self.sigma_w_by_state_rad.items()}


@dataclass(frozen=True)
class MotionLabelConfig:
    """Label thresholds and causal windows for labeling_v1/v2.

    V2 thresholds without validation calibration intentionally remain unset;
    this prevents candidate values from being mistaken for official criteria.
    """

    high_roll_centered_threshold_deg: Optional[float] = None
    persistent_offset_threshold_deg: float = 3.0
    persistent_offset_window_s: float = 180.0
    persistent_offset_duration_s: float = 120.0
    growth_window_s: float = 180.0
    growth_ratio_lag_s: float = 120.0
    growth_criterion: Optional[GrowthCriterion] = None
    growth_slope_threshold_deg_per_min: Optional[float] = None
    growth_ratio_threshold: Optional[float] = None
    growth_ratio_floor_deg: Optional[float] = None
    growth_confirmation_s: Optional[float] = None
    threshold_calibration_status: ProfileCalibrationStatus = (
        ProfileCalibrationStatus.CANDIDATE)

    def __post_init__(self) -> None:
        _optional_number("high_roll_centered_threshold_deg",
                         self.high_roll_centered_threshold_deg,
                         minimum=0.0, strict_minimum=True)
        _optional_number("persistent_offset_threshold_deg",
                         self.persistent_offset_threshold_deg,
                         minimum=0.0, strict_minimum=True)
        for name in ("persistent_offset_window_s", "persistent_offset_duration_s",
                     "growth_window_s", "growth_ratio_lag_s"):
            _optional_number(name, getattr(self, name), minimum=0.0,
                             strict_minimum=True)
        _optional_number("growth_slope_threshold_deg_per_min",
                         self.growth_slope_threshold_deg_per_min,
                         minimum=0.0, strict_minimum=True)
        _optional_number("growth_ratio_threshold", self.growth_ratio_threshold,
                         minimum=1.0, strict_minimum=True)
        _optional_number("growth_ratio_floor_deg", self.growth_ratio_floor_deg,
                         minimum=0.0, strict_minimum=True)
        _optional_number("growth_confirmation_s", self.growth_confirmation_s,
                         minimum=0.0)
        if self.growth_confirmation_s == 0.0:
            raise ValueError("growth_confirmation_s must be positive when configured")
        if self.growth_criterion is not None and not isinstance(
                self.growth_criterion, GrowthCriterion):
            raise TypeError("growth_criterion must be a GrowthCriterion or None")
        if not isinstance(self.threshold_calibration_status, ProfileCalibrationStatus):
            raise TypeError(
                "threshold_calibration_status must be a ProfileCalibrationStatus")
        if self.growth_window_s < self.growth_ratio_lag_s:
            raise ValueError("growth_ratio_lag_s cannot exceed growth_window_s")

    @property
    def unresolved_v2_thresholds(self) -> Tuple[str, ...]:
        missing = []
        if self.high_roll_centered_threshold_deg is None:
            missing.append("high_roll_centered_threshold_deg")
        criterion = self.growth_criterion
        if criterion is None:
            missing.append("growth_criterion")
        else:
            if criterion in (GrowthCriterion.SLOPE, GrowthCriterion.SLOPE_AND_RATIO,
                             GrowthCriterion.SLOPE_OR_RATIO):
                if self.growth_slope_threshold_deg_per_min is None:
                    missing.append("growth_slope_threshold_deg_per_min")
            if criterion in (GrowthCriterion.RATIO, GrowthCriterion.SLOPE_AND_RATIO,
                             GrowthCriterion.SLOPE_OR_RATIO):
                if self.growth_ratio_threshold is None:
                    missing.append("growth_ratio_threshold")
                if self.growth_ratio_floor_deg is None:
                    missing.append("growth_ratio_floor_deg")
            if self.growth_confirmation_s is None:
                missing.append("growth_confirmation_s")
        return tuple(missing)

    @property
    def labeling_v2_configured(self) -> bool:
        return not self.unresolved_v2_thresholds

    @property
    def labeling_v2_ready(self) -> bool:
        return (self.labeling_v2_configured and
                self.threshold_calibration_status is
                ProfileCalibrationStatus.CALIBRATED)


@dataclass(frozen=True)
class SimulationTimeConfig:
    """Session timing; the configured sample rate is the simulation rate."""

    duration_s: float = 1200.0
    dt_s: float = 0.05
    sample_rate_hz: float = 20.0
    output_rate_hz: float = 2.0

    def __post_init__(self) -> None:
        for name, value in (("duration_s", self.duration_s),
                            ("dt_s", self.dt_s),
                            ("sample_rate_hz", self.sample_rate_hz),
                            ("output_rate_hz", self.output_rate_hz)):
            _optional_number(name, value, minimum=0.0, strict_minimum=True)
        if not math.isclose(1.0 / self.dt_s, self.sample_rate_hz,
                            rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("dt_s must be the reciprocal of sample_rate_hz")
        if self.output_rate_hz > self.sample_rate_hz:
            raise ValueError("output_rate_hz cannot exceed sample_rate_hz")
        ratio = self.sample_rate_hz / self.output_rate_hz
        if not math.isclose(ratio, round(ratio), rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("sample_rate_hz must be an integer multiple of output_rate_hz")
        self.sample_count

    @property
    def sample_count(self) -> int:
        """Number of input samples in a session, requiring an integral count."""
        count = self.duration_s * self.sample_rate_hz
        rounded = round(count)
        if not math.isclose(count, rounded, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("duration_s * sample_rate_hz must be an integer")
        return int(rounded)


@dataclass(frozen=True)
class RollDynamicsConfig:
    """Roll model parameters; unspecified physics stay unset until agreed."""

    natural_period_s: Optional[float] = None
    damping_ratio: Optional[float] = None
    parametric_excitation_amplitude: Optional[float] = None
    parametric_excitation_angular_frequency_rad_s: Optional[float] = None
    nonlinear_coefficient: Optional[float] = None
    heel_offset_rad: float = 0.0
    initial_roll_rad: float = 0.0
    initial_roll_rate_rad_s: float = 0.0

    def __post_init__(self) -> None:
        _optional_number("natural_period_s", self.natural_period_s,
                         minimum=0.0, strict_minimum=True)
        _optional_number("damping_ratio", self.damping_ratio, minimum=0.0)
        _optional_number("parametric_excitation_amplitude",
                         self.parametric_excitation_amplitude, minimum=0.0)
        _optional_number("parametric_excitation_angular_frequency_rad_s",
                         self.parametric_excitation_angular_frequency_rad_s, minimum=0.0)
        _optional_number("nonlinear_coefficient", self.nonlinear_coefficient)
        _optional_number("heel_offset_rad", self.heel_offset_rad)
        _optional_number("initial_roll_rad", self.initial_roll_rad)
        _optional_number("initial_roll_rate_rad_s", self.initial_roll_rate_rad_s)


@dataclass(frozen=True)
class WaveExcitationConfig:
    """G1/G2 wave forcing settings with explicit physical units."""

    generator: WaveGenerator = WaveGenerator.G1
    g1_forcing_std_rad: Optional[float] = None
    g1_correlation_time_s: Optional[float] = None
    g2_significant_height_m: Optional[float] = None
    g2_peak_period_s: Optional[float] = None
    g2_gamma: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.generator, WaveGenerator):
            raise TypeError("generator must be a WaveGenerator")
        _optional_number("g1_forcing_std_rad", self.g1_forcing_std_rad, minimum=0.0)
        _optional_number("g1_correlation_time_s", self.g1_correlation_time_s,
                         minimum=0.0, strict_minimum=True)
        _optional_number("g2_significant_height_m", self.g2_significant_height_m,
                         minimum=0.0)
        _optional_number("g2_peak_period_s", self.g2_peak_period_s,
                         minimum=0.0, strict_minimum=True)
        _optional_number("g2_gamma", self.g2_gamma, minimum=0.0, strict_minimum=True)


@dataclass(frozen=True)
class IMUNoiseConfig:
    """Optional IMU noise and bias; angles/rates use radians and rad/s.

    Values are unset until sensor characteristics are agreed; zero is not
    presented as a measured MPU6050 noise specification.
    """

    roll_noise_std_rad: Optional[float] = None
    pitch_noise_std_rad: Optional[float] = None
    roll_bias_rad: Optional[float] = None
    pitch_bias_rad: Optional[float] = None
    gyro_noise_std_rad_s: Optional[float] = None
    gyro_bias_rad_s: Optional[float] = None

    def __post_init__(self) -> None:
        for name in ("roll_noise_std_rad", "pitch_noise_std_rad",
                     "gyro_noise_std_rad_s"):
            _optional_number(name, getattr(self, name), minimum=0.0)
        for name in ("roll_bias_rad", "pitch_bias_rad", "gyro_bias_rad_s"):
            _optional_number(name, getattr(self, name))


@dataclass(frozen=True)
class ParameterRange:
    """Inclusive numeric interval for sampling one parameter domain."""

    minimum: float
    maximum: float
    unit: str

    def __post_init__(self) -> None:
        _optional_number("minimum", self.minimum)
        _optional_number("maximum", self.maximum)
        if self.minimum > self.maximum:
            raise ValueError("minimum cannot exceed maximum")
        if not isinstance(self.unit, str) or not self.unit.strip():
            raise ValueError("unit must be a non-empty string")


@dataclass(frozen=True)
class ParameterDomain:
    """Parameter ranges for one data split; empty until ranges are agreed."""

    parameters: Dict[str, ParameterRange] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in self.parameters.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("parameter names must be non-empty strings")
            if not isinstance(value, ParameterRange):
                raise TypeError("domain values must be ParameterRange instances")


@dataclass(frozen=True)
class ParameterDomains:
    """Independent parameter domains for train, validation, and both tests."""

    train: ParameterDomain = field(default_factory=ParameterDomain)
    validation: ParameterDomain = field(default_factory=ParameterDomain)
    test_g1: ParameterDomain = field(default_factory=ParameterDomain)
    test_g2: ParameterDomain = field(default_factory=ParameterDomain)

    def __post_init__(self) -> None:
        for name in ("train", "validation", "test_g1", "test_g2"):
            if not isinstance(getattr(self, name), ParameterDomain):
                raise TypeError("{} must be a ParameterDomain".format(name))


def _default_parameter_domains() -> ParameterDomains:
    """Return the agreed M2 split intervals, using seconds and dimensionless damping."""
    common_train_validation = {
        "natural_period_s": ParameterRange(14.0, 26.0, "s"),
        "damping_ratio": ParameterRange(0.03, 0.06, "1"),
        "t0_s": ParameterRange(240.0, 480.0, "s"),
    }
    common_test = {
        "natural_period_s": ParameterRange(12.0, 32.0, "s"),
        "damping_ratio": ParameterRange(0.02, 0.08, "1"),
        "t0_s": ParameterRange(180.0, 540.0, "s"),
    }
    return ParameterDomains(
        train=ParameterDomain(parameters=dict(common_train_validation)),
        validation=ParameterDomain(parameters=dict(common_train_validation)),
        test_g1=ParameterDomain(parameters=dict(common_test)),
        test_g2=ParameterDomain(parameters=dict(common_test)),
    )


def _default_session_counts() -> Dict[DatasetSplit, int]:
    return {
        DatasetSplit.TRAIN: 280,
        DatasetSplit.VALIDATION: 85,
        DatasetSplit.TEST_G1: 120,
        DatasetSplit.TEST_G2: 120,
    }


def _default_scenario_counts() -> Dict[ScenarioCode, Dict[DatasetSplit, int]]:
    """Approved 605-session allocation, keyed by scenario then split."""
    rows = {
        ScenarioCode.S0: (80, 20, 30, 30),
        ScenarioCode.S0B: (30, 10, 15, 15),
        ScenarioCode.S1: (50, 15, 20, 20),
        ScenarioCode.S2: (50, 15, 20, 20),
        ScenarioCode.S3: (50, 15, 20, 20),
        ScenarioCode.H1: (20, 10, 15, 15),
    }
    split_order = tuple(DatasetSplit)
    return {scenario: dict(zip(split_order, values))
            for scenario, values in rows.items()}


@dataclass(frozen=True)
class DatasetPlanConfig:
    """Dataset-scale metadata; this object does not generate any data."""

    total_sessions: int = 605
    session_counts: Dict[DatasetSplit, int] = field(default_factory=_default_session_counts)
    scenario_counts: Dict[ScenarioCode, Dict[DatasetSplit, int]] = field(
        default_factory=_default_scenario_counts)
    domains: ParameterDomains = field(default_factory=_default_parameter_domains)

    def __post_init__(self) -> None:
        if isinstance(self.total_sessions, bool) or not isinstance(self.total_sessions, int):
            raise TypeError("total_sessions must be an integer")
        if self.total_sessions < 1:
            raise ValueError("total_sessions must be at least 1")
        if self.total_sessions != 605:
            raise ValueError("the SVMG dataset plan must contain 605 sessions")
        expected_splits = set(DatasetSplit)
        if not isinstance(self.session_counts, dict):
            raise TypeError("session_counts must map DatasetSplit values to counts")
        if set(self.session_counts) != expected_splits:
            raise ValueError("session_counts must define every DatasetSplit exactly once")
        for split, count in self.session_counts.items():
            if not isinstance(split, DatasetSplit):
                raise TypeError("session_counts keys must be DatasetSplit values")
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError("session counts must be non-negative integers")
        if sum(self.session_counts.values()) != 605:
            raise ValueError("session counts across all splits must sum to 605")
        if not isinstance(self.scenario_counts, dict):
            raise TypeError("scenario_counts must map ScenarioCode to split counts")
        if set(self.scenario_counts) != set(ScenarioCode):
            raise ValueError("scenario_counts must define every scenario exactly once")
        column_totals = {split: 0 for split in DatasetSplit}
        for scenario, split_counts in self.scenario_counts.items():
            if not isinstance(scenario, ScenarioCode):
                raise TypeError("scenario_counts keys must be ScenarioCode values")
            if not isinstance(split_counts, dict) or set(split_counts) != expected_splits:
                raise ValueError("each scenario must define every DatasetSplit exactly once")
            for split, count in split_counts.items():
                if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                    raise ValueError("scenario split counts must be non-negative integers")
                column_totals[split] += count
        if column_totals != self.session_counts:
            raise ValueError("scenario allocation column totals must match session_counts")
        if not isinstance(self.domains, ParameterDomains):
            raise TypeError("domains must be a ParameterDomains instance")


@dataclass(frozen=True)
class ScenarioDefinition:
    """Human-readable meaning and target label for a scenario identifier."""

    code: ScenarioCode
    description: str
    expected_label: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, ScenarioCode):
            raise TypeError("code must be a ScenarioCode")
        if (not isinstance(self.description, str) or
                not isinstance(self.expected_label, str) or
                not self.description.strip() or not self.expected_label.strip()):
            raise ValueError("scenario description and expected_label are required")


DEFAULT_SCENARIOS: Tuple[ScenarioDefinition, ...] = (
    ScenarioDefinition(ScenarioCode.S0, "Calm sea", "NORMAL"),
    ScenarioDefinition(ScenarioCode.S0B, "Harbor anchorage", "NORMAL"),
    ScenarioDefinition(ScenarioCode.S1, "Moderate waves and high roll", "HIGH_ROLL"),
    ScenarioDefinition(ScenarioCode.S2, "Persistent heel offset", "PERSISTENT_OFFSET"),
    ScenarioDefinition(ScenarioCode.S3, "Parametric resonance and amplitude growth",
                       "AMPLITUDE_GROWTH"),
    ScenarioDefinition(ScenarioCode.H1, "Combined high sea state and heel offset",
                       "COMBINED_SCENARIO"),
)


@dataclass(frozen=True)
class SimulationConfig:
    """Top-level reproducible configuration and metadata for one run plan."""

    time: SimulationTimeConfig = field(default_factory=SimulationTimeConfig)
    roll: RollDynamicsConfig = field(default_factory=RollDynamicsConfig)
    waves: WaveExcitationConfig = field(default_factory=WaveExcitationConfig)
    imu: IMUNoiseConfig = field(default_factory=IMUNoiseConfig)
    dataset: DatasetPlanConfig = field(default_factory=DatasetPlanConfig)
    random_seed: int = 1
    scenarios: Tuple[ScenarioDefinition, ...] = field(
        default_factory=lambda: DEFAULT_SCENARIOS)
    config_version: str = "1.0.0"
    generator_version: str = "0.1.0"
    sea_state_profile: SeaStateProfileConfig = field(default_factory=SeaStateProfileConfig)
    labeling: MotionLabelConfig = field(default_factory=MotionLabelConfig)

    def __post_init__(self) -> None:
        for name, expected_type in (("time", SimulationTimeConfig),
                                    ("roll", RollDynamicsConfig),
                                    ("waves", WaveExcitationConfig),
                                    ("imu", IMUNoiseConfig),
                                    ("dataset", DatasetPlanConfig),
                                    ("sea_state_profile", SeaStateProfileConfig),
                                    ("labeling", MotionLabelConfig)):
            if not isinstance(getattr(self, name), expected_type):
                raise TypeError("{} must be a {}".format(name, expected_type.__name__))
        self._validate_parameter_domains()
        if isinstance(self.random_seed, bool) or not isinstance(self.random_seed, int):
            raise TypeError("random_seed must be an integer")
        # xorshift32's all-zero state remains zero; keep the seed usable by the C port.
        if not 1 <= self.random_seed <= 0xFFFFFFFF:
            raise ValueError("random_seed must be in [1, 2**32 - 1]")
        if not self.scenarios:
            raise ValueError("at least one scenario is required")
        if not all(isinstance(item, ScenarioDefinition) for item in self.scenarios):
            raise TypeError("scenarios must contain ScenarioDefinition instances")
        codes = [scenario.code for scenario in self.scenarios]
        if len(codes) != len(set(codes)):
            raise ValueError("scenario codes must be unique")
        for name in ("config_version", "generator_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError("{} must be a non-empty string".format(name))

    def _validate_parameter_domains(self) -> None:
        for split_name in ("train", "validation", "test_g1", "test_g2"):
            domain = getattr(self.dataset.domains, split_name)
            required = {"natural_period_s", "damping_ratio", "t0_s"}
            missing = required.difference(domain.parameters)
            if missing:
                raise ValueError("{} domain missing parameters: {}".format(
                    split_name, ", ".join(sorted(missing))))
            for parameter, unit in (("natural_period_s", "s"),
                                    ("damping_ratio", "1"),
                                    ("t0_s", "s")):
                if domain.parameters[parameter].unit != unit:
                    raise ValueError("{}.{} must use unit {!r}".format(
                        split_name, parameter, unit))
            if domain.parameters["natural_period_s"].minimum <= 0:
                raise ValueError("natural_period_s must be positive")
            if domain.parameters["damping_ratio"].minimum < 0:
                raise ValueError("damping_ratio cannot be negative")
            t0_range = domain.parameters["t0_s"]
            if t0_range.minimum < 0 or t0_range.maximum > self.time.duration_s:
                raise ValueError("t0_s range must fit inside duration_s")

    @property
    def official_dataset_ready(self) -> bool:
        """True only when v2 thresholds and sea-state profile are calibrated."""
        return (self.labeling.labeling_v2_ready and
                self.sea_state_profile.calibration_status is
                ProfileCalibrationStatus.CALIBRATED)

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-friendly metadata without changing this configuration."""
        return _to_plain_data(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulationConfig":
        """Restore a configuration from the JSON-compatible form of ``to_dict``."""
        if not isinstance(data, dict):
            raise TypeError("configuration data must be a dictionary")

        time = SimulationTimeConfig(**data.get("time", {}))
        roll = RollDynamicsConfig(**data.get("roll", {}))

        wave_data = dict(data.get("waves", {}))
        if "generator" in wave_data:
            wave_data["generator"] = WaveGenerator(wave_data["generator"])
        waves = WaveExcitationConfig(**wave_data)
        imu = IMUNoiseConfig(**data.get("imu", {}))

        profile_data = dict(data.get("sea_state_profile", {}))
        if "calibration_status" in profile_data:
            profile_data["calibration_status"] = ProfileCalibrationStatus(
                profile_data["calibration_status"])
        sea_state_profile = SeaStateProfileConfig(**profile_data)

        labeling_data = dict(data.get("labeling", {}))
        if labeling_data.get("growth_criterion") is not None:
            labeling_data["growth_criterion"] = GrowthCriterion(
                labeling_data["growth_criterion"])
        if "threshold_calibration_status" in labeling_data:
            labeling_data["threshold_calibration_status"] = ProfileCalibrationStatus(
                labeling_data["threshold_calibration_status"])
        labeling = MotionLabelConfig(**labeling_data)

        dataset_data = dict(data.get("dataset", {}))
        raw_counts = dataset_data.get("session_counts", _default_session_counts())
        counts = {DatasetSplit(key): value for key, value in raw_counts.items()}
        raw_scenario_counts = dataset_data.get("scenario_counts", _default_scenario_counts())
        scenario_counts = {
            ScenarioCode(scenario): {
                DatasetSplit(split): count for split, count in split_counts.items()
            }
            for scenario, split_counts in raw_scenario_counts.items()
        }
        raw_domains = dataset_data.get("domains")
        default_domains = _default_parameter_domains()
        domains_kwargs = {}
        for key in ("train", "validation", "test_g1", "test_g2"):
            if raw_domains is None or key not in raw_domains:
                domains_kwargs[key] = getattr(default_domains, key)
                continue
            raw_domain = raw_domains[key]
            raw_parameters = raw_domain.get("parameters", {})
            parameters = {
                name: ParameterRange(**parameter_range)
                for name, parameter_range in raw_parameters.items()
            }
            domains_kwargs[key] = ParameterDomain(parameters=parameters)
        domains = ParameterDomains(**domains_kwargs)
        dataset = DatasetPlanConfig(
            total_sessions=dataset_data.get("total_sessions", 605),
            session_counts=counts,
            scenario_counts=scenario_counts,
            domains=domains,
        )

        raw_scenarios = data.get("scenarios")
        scenarios = None
        if raw_scenarios is not None:
            scenarios = tuple(
                ScenarioDefinition(
                    code=ScenarioCode(item["code"]),
                    description=item["description"],
                    expected_label=item["expected_label"],
                )
                for item in raw_scenarios
            )
        kwargs = {
            "time": time,
            "roll": roll,
            "waves": waves,
            "imu": imu,
            "dataset": dataset,
            "sea_state_profile": sea_state_profile,
            "labeling": labeling,
            "random_seed": data.get("random_seed", 1),
            "config_version": data.get("config_version", "1.0.0"),
            "generator_version": data.get("generator_version", "0.1.0"),
        }
        if scenarios is not None:
            kwargs["scenarios"] = scenarios
        return cls(**kwargs)


def _to_plain_data(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {_to_plain_data(key): _to_plain_data(item)
                for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(_to_plain_data(key)): _to_plain_data(item)
                for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_to_plain_data(item) for item in value]
    return value
