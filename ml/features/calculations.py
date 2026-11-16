from __future__ import annotations

import math

import numpy as np


def finite_array(values) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    return array[np.isfinite(array)]


def population_std(values) -> float:
    x = finite_array(values)
    if not len(x):
        return math.nan
    mean = math.fsum(float(v) for v in x) / len(x)
    variance = math.fsum((float(v) - mean) ** 2 for v in x) / len(x)
    return math.sqrt(max(0.0, variance))


def rms(values) -> float:
    x = finite_array(values)
    if not len(x):
        return math.nan
    return math.sqrt(math.fsum(float(v) * float(v) for v in x) / len(x))


def type7_quantile(values, probability: float) -> float:
    """Phân vị Type-7: h=(n-1)p và nội suy tuyến tính."""
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability phải nằm trong [0, 1].")
    x = np.sort(finite_array(values), kind="stable")
    if not len(x):
        return math.nan
    h = (len(x) - 1) * probability
    lower = int(math.floor(h))
    fraction = h - lower
    upper = min(lower + 1, len(x) - 1)
    return float(x[lower] + fraction * (x[upper] - x[lower]))


def interquartile_range(values) -> float:
    return type7_quantile(values, 0.75) - type7_quantile(values, 0.25)


def diff_rms(values, times, nominal_dt: float, minimum_pairs: int) -> tuple[float, int]:
    x = np.asarray(values, dtype=np.float64)
    t = np.asarray(times, dtype=np.float64)
    if len(x) != len(t) or len(x) < 2:
        return math.nan, 0
    dt = np.diff(t)
    tolerance = max(1e-8, nominal_dt * 1e-5)
    adjacent = (np.isfinite(x[:-1]) & np.isfinite(x[1:])
                & np.isfinite(dt) & (np.abs(dt - nominal_dt) <= tolerance))
    differences = np.diff(x)[adjacent]
    if len(differences) < minimum_pairs:
        return math.nan, int(len(differences))
    return rms(differences), int(len(differences))


def dominant_sign_ratio(values) -> float:
    x = finite_array(values)
    positives = int(np.count_nonzero(x > 0.0))
    negatives = int(np.count_nonzero(x < 0.0))
    nonzero = positives + negatives
    if not nonzero:
        return math.nan
    return max(positives, negatives) / nonzero


def linear_slope(times, values) -> float:
    t = np.asarray(times, dtype=np.float64)
    y = np.asarray(values, dtype=np.float64)
    if len(t) != len(y) or len(t) < 2 or not np.all(np.isfinite(t)) or not np.all(np.isfinite(y)):
        return math.nan
    t_mean = math.fsum(float(v) for v in t) / len(t)
    y_mean = math.fsum(float(v) for v in y) / len(y)
    denominator = math.fsum((float(v) - t_mean) ** 2 for v in t)
    if denominator == 0.0:
        return math.nan
    numerator = math.fsum((float(a) - t_mean) * (float(b) - y_mean) for a, b in zip(t, y))
    return numerator / denominator


def linear_r_squared(times, values, zero_tolerance: float = 0.0) -> float:
    t = np.asarray(times, dtype=np.float64)
    y = np.asarray(values, dtype=np.float64)
    if len(t) != len(y) or len(t) < 2 or not np.all(np.isfinite(t)) or not np.all(np.isfinite(y)):
        return math.nan
    mean = math.fsum(float(v) for v in y) / len(y)
    sst = math.fsum((float(v) - mean) ** 2 for v in y)
    if sst <= zero_tolerance:
        return math.nan
    slope = linear_slope(t, y)
    intercept = mean - slope * (math.fsum(float(v) for v in t) / len(t))
    sse = math.fsum((float(value) - (intercept + slope * float(time))) ** 2
                    for time, value in zip(t, y))
    score = 1.0 - sse / sst
    if -1e-12 <= score < 0.0:
        return 0.0
    if 1.0 < score <= 1.0 + 1e-12:
        return 1.0
    return score


def zero_crossings(times, values, nominal_dt: float, maximum_gap_factor: float = 1.5) -> list[tuple[float, int]]:
    """Trả các crossing (thời gian, hướng); không nối missing/gap."""
    t = np.asarray(times, dtype=np.float64)
    y = np.asarray(values, dtype=np.float64)
    if len(t) != len(y):
        raise ValueError("times và values phải cùng chiều dài.")
    events: list[tuple[float, int]] = []
    last_nonzero_index: int | None = None
    last_observed_index: int | None = None
    zero_start: int | None = None
    zero_end: int | None = None
    for index, value in enumerate(y):
        if not np.isfinite(value) or not np.isfinite(t[index]):
            last_nonzero_index = None
            last_observed_index = None
            zero_start = zero_end = None
            continue
        if last_observed_index is not None and t[index] - t[last_observed_index] > maximum_gap_factor * nominal_dt + 1e-9:
            last_nonzero_index = None
            zero_start = zero_end = None
        last_observed_index = index
        if value == 0.0:
            if last_nonzero_index is not None:
                zero_start = index if zero_start is None else zero_start
                zero_end = index
            continue
        if last_nonzero_index is None:
            last_nonzero_index = index
            zero_start = zero_end = None
            continue
        left = float(y[last_nonzero_index])
        right = float(value)
        if (left < 0.0 < right) or (left > 0.0 > right):
            direction = 1 if left < right else -1
            if zero_start is not None and zero_end is not None:
                crossing_time = (float(t[zero_start]) + float(t[zero_end])) / 2.0
            else:
                crossing_time = float(t[last_nonzero_index] - left * (t[index] - t[last_nonzero_index]) / (right - left))
            events.append((crossing_time, direction))
        last_nonzero_index = index
        zero_start = zero_end = None
    return events


def period_values(times, values, nominal_dt: float, maximum_gap_factor: float = 1.5) -> tuple[list[float], int]:
    x = np.asarray(values, dtype=np.float64)
    finite = x[np.isfinite(x)]
    if not len(finite):
        return [], 0
    centered = x - math.fsum(float(v) for v in finite) / len(finite)
    crossings = zero_crossings(times, centered, nominal_dt, maximum_gap_factor)
    periods: list[float] = []
    run_start: int | None = None

    def consume_run(start: int, stop: int) -> None:
        run_crossings = zero_crossings(times[start:stop], centered[start:stop], nominal_dt, maximum_gap_factor)
        upward = [time for time, direction in run_crossings if direction == 1]
        run_periods = np.diff(upward)
        periods.extend(run_periods[np.isfinite(run_periods) & (run_periods > 0)].tolist())

    for index, value in enumerate(centered):
        valid = np.isfinite(value) and np.isfinite(times[index])
        if not valid:
            if run_start is not None:
                consume_run(run_start, index)
                run_start = None
            continue
        if index > 0 and np.isfinite(times[index - 1]) and times[index] - times[index - 1] > maximum_gap_factor * nominal_dt + 1e-9:
            if run_start is not None:
                consume_run(run_start, index)
            run_start = index
        elif run_start is None:
            run_start = index
    if run_start is not None:
        consume_run(run_start, len(centered))
    return periods, len(crossings)
