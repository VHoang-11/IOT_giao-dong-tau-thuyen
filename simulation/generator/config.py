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


@dataclass(frozen=True)
class DatasetPlanConfig:
    """Dataset-scale metadata; this object does not generate any data."""

    total_sessions: int = 605
    session_counts: Dict[DatasetSplit, int] = field(default_factory=_default_session_counts)
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
    ScenarioDefinition(ScenarioCode.H1, "Sensor fault", "FAULT"),
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

    def __post_init__(self) -> None:
        for name, expected_type in (("time", SimulationTimeConfig),
                                    ("roll", RollDynamicsConfig),
                                    ("waves", WaveExcitationConfig),
                                    ("imu", IMUNoiseConfig),
                                    ("dataset", DatasetPlanConfig)):
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

        dataset_data = dict(data.get("dataset", {}))
        raw_counts = dataset_data.get("session_counts", _default_session_counts())
        counts = {DatasetSplit(key): value for key, value in raw_counts.items()}
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
