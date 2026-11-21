import math

import numpy as np

from ml.features.calculations import (
    diff_rms, dominant_sign_ratio, interquartile_range, linear_r_squared,
    linear_slope, period_values, population_std, rms, type7_quantile,
    zero_crossings,
)


def test_rms_population_std_and_quantile_conventions():
    assert rms([3.0, 4.0]) ==  math.sqrt(12.5)
    assert population_std([1.0, 2.0, 3.0]) == math.sqrt(2.0 / 3.0)
    assert type7_quantile([0.0, 10.0], 0.25) == 2.5
    assert interquartile_range([0.0, 10.0]) == 5.0


def test_constant_zero_and_signed_offset_sign_ratio():
    assert population_std([4.0] * 4) == 0.0
    assert rms([0.0, 0.0]) == 0.0
    assert dominant_sign_ratio([1.0, 2.0, -1.0, 0.0]) == 2.0 / 3.0
    assert dominant_sign_ratio([-1.0, -2.0, 1.0]) == 2.0 / 3.0
    assert math.isnan(dominant_sign_ratio([0.0, 0.0]))


def test_consecutive_difference_ignores_non_adjacent_samples():
    value, count = diff_rms([0.0, 1.0, 3.0], [0.0, 0.1, 0.3], 0.1, 1)
    assert value == 1.0
    assert count == 1


def test_linear_slope_and_r_squared_known_trend_and_constant():
    time = np.array([30.0, 90.0, 150.0])
    value = np.array([1.0, 3.0, 5.0])
    assert linear_slope(time, value) == 1.0 / 30.0
    assert linear_r_squared(time, value) == 1.0
    assert math.isnan(linear_r_squared(time, np.ones(3)))


def test_c03_absolute_sst_boundary_zero_below_equal_and_above():
    time = np.array([30.0, 90.0, 150.0])
    tolerance = 1e-15

    assert math.isnan(linear_r_squared(time, [2.0, 2.0, 2.0], tolerance))  # SST = 0
    delta = math.sqrt(0.5e-15)
    at_threshold = [-delta, 0.0, delta]
    mean = math.fsum(at_threshold) / 3
    assert math.fsum((value - mean) ** 2 for value in at_threshold) == tolerance
    assert math.isnan(linear_r_squared(time, at_threshold, tolerance))  # SST = threshold

    below = [-delta * 0.99, 0.0, delta * 0.99]
    above = [-delta * 1.01, 0.0, delta * 1.01]
    assert math.isnan(linear_r_squared(time, below, tolerance))
    assert math.isfinite(linear_r_squared(time, above, tolerance))
    assert linear_r_squared(time, [-1.0, 0.0, 1.0], tolerance) == 1.0


def test_c03_symmetric_rms_trend_has_valid_zero_r_squared():
    time = np.array([30.0, 90.0, 150.0])
    assert linear_r_squared(time, [1.0, 2.0, 1.0], 1e-15) == 0.0


def test_zero_crossing_interpolation_plateau_and_gap_handling():
    t = np.arange(7, dtype=float) * 0.1
    y = np.array([-1.0, 0.0, 0.0, 1.0, 1.0, -1.0, 1.0])
    crossings = zero_crossings(t, y, 0.1)
    assert crossings[0] == (0.15000000000000002, 1)
    assert crossings[1] == (0.45, -1)
    assert crossings[2] == (0.55, 1)
    # Gap > 1.5 dt must prevent a fabricated crossing across the gap.
    gap_t = np.array([0.0, 0.1, 0.4, 0.5])
    assert zero_crossings(gap_t, [-1.0, -1.0, 1.0, 1.0], 0.1) == []


def test_period_estimation_for_fixed_frequency_sine():
    t = np.arange(0.0, 20.0, 0.01)
    y = np.sin(2.0 * np.pi * 0.5 * t)
    periods, count = period_values(t, y, 0.01)
    assert count >= 18
    assert len(periods) >= 8
    assert np.median(periods) == pytest_approx(2.0, abs=0.01)
    assert population_std(periods) / np.mean(periods) < 0.01


def test_period_does_not_bridge_separate_continuous_runs():
    times = np.array([0.0, 0.1, 0.2, 0.3, 2.0, 2.1, 2.2, 2.3])
    values = np.array([-1.0, -1.0, 1.0, 1.0, -1.0, -1.0, 1.0, 1.0])
    periods, crossings = period_values(times, values, 0.1)
    assert crossings == 2
    assert periods == []


def pytest_approx(value, **kwargs):
    # Wrapper keeps this test module's expected values explicit.
    import pytest
    return pytest.approx(value, **kwargs)
