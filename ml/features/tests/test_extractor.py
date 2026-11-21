import json
import math

import numpy as np
import pandas as pd
import pytest

from ml.features.extractor import FeatureInputError, extract_segment, validate_segment
from ml.features.spec import FEATURE_NAMES, PRACTICAL_SUBSETS


def settings(dataset="test", gyro_status="VALID"):
    return {
        "target_sampling_hz": 10.0,
        "window_stride_seconds": 10.0,
        "minimum_valid_fraction": 0.95,
        "numeric_zero_epsilon_deg": 1e-9,
        "r_squared_zero_tolerance": 1e-15,
        "period_minimum_upward_crossings": 3,
        "period_cv_minimum_periods": 3,
        "source_gyro_status": {dataset: gyro_status},
    }


def frame(duration, roll=None, pitch=None, dataset="test", session="session-a", segment="segment-a"):
    times = np.arange(int(duration * 10) + 1, dtype=float) / 10.0
    count = len(times)
    return pd.DataFrame({
        "dataset_source": dataset,
        "session_id": session,
        "segment_id": segment,
        "time_seconds": times,
        "roll_deg": np.asarray(roll if roll is not None else np.zeros(count), dtype=float),
        "pitch_deg": np.asarray(pitch if pitch is not None else np.zeros(count), dtype=float),
        "gyro_x_rad_s": np.ones(count, dtype=float),
        "gyro_y_rad_s": np.ones(count, dtype=float) * 2.0,
    })


def provenance():
    return {"target_sampling_hz_effective": 10.0, "configuration_sha256": "fixture"}


def test_exact_60_and_180_second_windows_and_feature_order():
    data = frame(180)
    values, metadata, summary = extract_segment(data, provenance(), settings(), "test")
    assert values.columns.tolist() == ["window_id", *FEATURE_NAMES]
    assert len(values) == 13  # 60, 70, ..., 180 s
    assert summary["candidate_windows_180s"] == 1
    first = json.loads(metadata.iloc[0]["validity_json"])
    assert first["roll_rms_60"]["status"] == "VALID"
    assert first["roll_mean_180"]["status"] == "INSUFFICIENT_WINDOW"
    last = json.loads(metadata.iloc[-1]["validity_json"])
    assert last["roll_mean_180"]["status"] == "VALID"


def test_short_session_and_missing_gyro_are_not_fabricated():
    data = frame(60, dataset="hohai")
    cfg = settings("hohai", "MISSING_SOURCE_SIGNAL")
    values, metadata, summary = extract_segment(data, provenance(), cfg, "hohai")
    assert len(values) == 1
    status = json.loads(metadata.iloc[0]["validity_json"])
    assert status["gyro_x_rms_60"]["status"] == "MISSING_SOURCE_SIGNAL"
    assert values.iloc[0]["gyro_x_rms_60"] is None
    assert status["roll_mean_180"]["status"] == "INSUFFICIENT_WINDOW"
    assert summary["candidate_windows_180s"] == 0


def test_constant_roll_has_undefined_zero_denominator_and_period_cv():
    data = frame(180, roll=np.ones(1801) * 2.0)
    values, metadata, _ = extract_segment(data, provenance(), settings(), "test")
    status = json.loads(metadata.iloc[-1]["validity_json"])
    assert status["roll_rms_ratio_180"]["status"] == "VALID"
    assert status["roll_period_est_180"]["status"] == "UNDEFINED_MATHEMATICALLY"
    assert status["roll_period_cv_180"]["status"] == "UNDEFINED_MATHEMATICALLY"


def test_zero_early_rms_is_undefined_instead_of_infinite_ratio():
    roll = np.zeros(1801)
    roll[1200:] = 1.0
    data = frame(180, roll=roll)
    values, metadata, _ = extract_segment(data, provenance(), settings(), "test")
    status = json.loads(metadata.iloc[-1]["validity_json"])
    assert status["roll_rms_ratio_180"]["status"] == "UNDEFINED_MATHEMATICALLY"
    assert pd.isna(values.iloc[-1]["roll_rms_ratio_180"])


def test_increasing_amplitude_sine_has_positive_growth_slope():
    times = np.arange(1801, dtype=float) / 10.0
    amplitude = 0.2 + times / 180.0
    roll = amplitude * np.sin(2.0 * np.pi * 0.2 * times)
    data = frame(180, roll=roll)
    values, metadata, _ = extract_segment(data, provenance(), settings(), "test")
    last = values.iloc[-1]
    validity = json.loads(metadata.iloc[-1]["validity_json"])
    assert validity["roll_rms_slope_180"]["status"] == "VALID"
    assert last["roll_rms_late_60"] > last["roll_rms_early_60"]
    assert last["roll_rms_slope_180"] > 0.0
    assert last["roll_rms_trend_r2_180"] > 0.95


def test_extractor_period_features_use_roll_signal_and_known_sine_period():
    times = np.arange(1801, dtype=float) / 10.0
    roll = np.sin(2.0 * np.pi * 0.5 * times)
    data = frame(180, roll=roll)
    values, metadata, _ = extract_segment(data, provenance(), settings(), "test")
    last = values.iloc[-1]
    validity = json.loads(metadata.iloc[-1]["validity_json"])
    assert validity["roll_zero_crossings_180"]["status"] == "VALID"
    assert last["roll_zero_crossings_180"] >= 170
    assert validity["roll_period_est_180"]["status"] == "VALID"
    assert abs(last["roll_period_est_180"] - 2.0) < 0.01
    assert validity["roll_period_cv_180"]["status"] == "VALID"
    assert last["roll_period_cv_180"] < 0.01

    future_row = pd.DataFrame({
        "dataset_source": ["test"], "session_id": ["session-a"], "segment_id": ["segment-a"],
        "time_seconds": [180.1], "roll_deg": [1000.0], "pitch_deg": [1000.0],
        "gyro_x_rad_s": [1000.0], "gyro_y_rad_s": [1000.0],
    })
    extended = pd.concat([data, future_row], ignore_index=True)
    extended_values, _, _ = extract_segment(extended, provenance(), settings(), "test")
    same_endpoint = extended_values[extended_values.window_id == values.iloc[-1].window_id].iloc[0]
    for feature in ("roll_period_est_180", "roll_zero_crossings_180", "roll_period_cv_180"):
        assert same_endpoint[feature] == last[feature]


def test_angle_only_23_subset_order_and_realizable_validity():
    expected = (
        "roll_rms_60", "roll_std_60", "roll_mean_60", "roll_peak_to_peak_60",
        "roll_abs_p95_60", "roll_abs_max_60", "roll_iqr_60", "roll_diff_rms_60",
        "roll_mean_180", "roll_median_180", "roll_mean_abs_180",
        "roll_dominant_sign_ratio_180", "roll_segment_mean_std_180", "roll_mean_shift_180",
        "roll_rms_early_60", "roll_rms_late_60", "roll_rms_ratio_180", "roll_rms_slope_180",
        "roll_rms_trend_r2_180", "roll_p95_trend_slope_180", "pitch_rms_60", "pitch_std_60",
        "pitch_peak_to_peak_60",
    )
    assert PRACTICAL_SUBSETS["angle_only_23_without_gyro_or_period"] == expected
    assert len(expected) == 23
    times = np.arange(1801, dtype=float) / 10.0
    data = frame(180, roll=(0.2 + times / 180.0) * np.sin(2 * np.pi * 0.5 * times),
                 pitch=np.cos(2 * np.pi * 0.25 * times))
    _, metadata, _ = extract_segment(data, provenance(), settings(), "test")
    validity = json.loads(metadata.iloc[-1]["validity_json"])
    assert all(validity[name]["status"] == "VALID" for name in expected)
    assert validity["roll_zero_crossings_180"]["status"] == "VALID"
    assert "roll_zero_crossings_180" not in expected


def test_missing_observations_preserve_missingness_and_enforce_coverage():
    data = frame(60)
    data.loc[1:30, "roll_deg"] = np.nan  # 570/600 samples: exactly the configured minimum.
    _, metadata, _ = extract_segment(data, provenance(), settings(), "test")
    validity = json.loads(metadata.iloc[0]["validity_json"])
    assert validity["roll_rms_60"]["status"] == "VALID"
    data.loc[31, "roll_deg"] = np.nan  # 569/600: below minimum coverage.
    values, metadata, _ = extract_segment(data, provenance(), settings(), "test")
    validity = json.loads(metadata.iloc[0]["validity_json"])
    assert validity["roll_rms_60"]["status"] == "INVALID_INPUT"
    assert pd.isna(values.iloc[0]["roll_rms_60"])


@pytest.mark.parametrize("missing_start", [1, 601, 1201], ids=["first", "middle", "last"])
def test_c01_conservative_all_three_block_gate(missing_start):
    data = frame(180)
    data.loc[missing_start:missing_start + 30, "roll_deg"] = np.nan  # 569/600 in one block; total remains >=1710.
    values, metadata, _ = extract_segment(data, provenance(), settings(), "test")
    validity = json.loads(metadata.iloc[-1]["validity_json"])
    block_features = (
        "roll_segment_mean_std_180", "roll_mean_shift_180", "roll_rms_early_60", "roll_rms_late_60",
        "roll_rms_ratio_180", "roll_rms_slope_180", "roll_rms_trend_r2_180", "roll_p95_trend_slope_180",
    )
    assert validity["roll_mean_180"]["status"] == "VALID"
    for name in block_features:
        assert validity[name]["status"] == "INVALID_INPUT"
        assert validity[name]["reason_code"] == "SEGMENT_BLOCK_COVERAGE"
        assert pd.isna(values.iloc[-1][name])


@pytest.mark.parametrize("early_rms, expected", [
    (np.nextafter(1e-9, 0.0), "UNDEFINED_MATHEMATICALLY"),
    (1e-9, "UNDEFINED_MATHEMATICALLY"),
    (np.nextafter(1e-9, np.inf), "VALID"),
])
def test_c02_ratio_epsilon_boundary_and_large_finite_value(early_rms, expected):
    roll = np.zeros(1801, dtype=float)
    roll[1:601] = early_rms
    roll[601:1201] = 0.5
    roll[1201:] = 1.0
    values, metadata, _ = extract_segment(frame(180, roll=roll), provenance(), settings(), "test")
    validity = json.loads(metadata.iloc[-1]["validity_json"])
    assert validity["roll_rms_ratio_180"]["status"] == expected
    if expected == "VALID":
        assert math.isfinite(values.iloc[-1]["roll_rms_ratio_180"])
        assert values.iloc[-1]["roll_rms_ratio_180"] > 1e8


def test_gap_invalidates_window_and_causal_endpoint_ignores_future():
    data = frame(70)
    data.loc[data["time_seconds"] >= 65.0, "time_seconds"] += 1.0
    values, metadata, _ = extract_segment(data, provenance(), settings(), "test")
    statuses = [json.loads(value)["roll_rms_60"]["status"] for value in metadata["validity_json"]]
    assert statuses[0] == "VALID"
    assert "INVALID_INPUT" in statuses[1:]

    short = frame(60, roll=np.sin(np.arange(601) / 10.0))
    extended = pd.concat([short, pd.DataFrame({
        **{key: [short.iloc[-1][key]] for key in ("dataset_source", "session_id", "segment_id")},
        "time_seconds": [60.1], "roll_deg": [1000.0], "pitch_deg": [1000.0],
        "gyro_x_rad_s": [1000.0], "gyro_y_rad_s": [1000.0],
    })], ignore_index=True)
    a = extract_segment(short, provenance(), settings(), "test")[0].iloc[0]
    b = extract_segment(extended, provenance(), settings(), "test")[0].iloc[0]
    assert a["roll_rms_60"] == b["roll_rms_60"]


def test_segment_identity_must_not_mix_sessions_or_runs():
    data = frame(60)
    data.loc[data.index[-1], "session_id"] = "other-session"
    try:
        validate_segment(data, "test")
    except FeatureInputError as error:
        assert "session_id" in str(error)
    else:
        raise AssertionError("Mixed session identities must be rejected.")


def test_unverified_gyro_mapping_has_explicit_validity_status():
    data = frame(60)
    _, metadata, _ = extract_segment(
        data, provenance(), settings("test", "UNVERIFIED_SIGNAL_MAPPING"), "test")
    status = json.loads(metadata.iloc[0]["validity_json"])
    assert status["gyro_x_rms_60"]["status"] == "UNVERIFIED_SIGNAL_MAPPING"
    assert status["gyro_y_rms_60"]["status"] == "UNVERIFIED_SIGNAL_MAPPING"
