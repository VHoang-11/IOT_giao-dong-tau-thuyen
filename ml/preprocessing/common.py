from __future__ import annotations

import math
from collections import Counter

import numpy as np

from .schemas import RawSession


def iter_json_records(path):
    """Đọc tuần tự các record trong JSON object top-level, không nạp toàn bộ tệp."""
    import json

    decoder = json.JSONDecoder()
    with path.open("r", encoding="utf-8") as stream:
        buffer = ""
        position = 0
        eof = False

        def fill():
            nonlocal buffer, position, eof
            if position:
                buffer = buffer[position:]
                position = 0
            chunk = stream.read(1024 * 1024)
            buffer += chunk
            eof = not chunk

        def decode_value():
            nonlocal position
            while True:
                while position < len(buffer) and buffer[position].isspace():
                    position += 1
                try:
                    value, position = decoder.raw_decode(buffer, position)
                    return value
                except json.JSONDecodeError:
                    if eof:
                        raise
                    fill()

        while True:
            while position >= len(buffer) and not eof:
                fill()
            while position < len(buffer) and buffer[position].isspace():
                position += 1
            if position >= len(buffer):
                return
            if buffer[position] == "{":
                position += 1
                break
            raise ValueError("JSON nguồn phải có top-level object.")

        while True:
            while position >= len(buffer) and not eof:
                fill()
            while position < len(buffer) and (buffer[position].isspace() or buffer[position] == ","):
                position += 1
            if position >= len(buffer):
                if eof:
                    raise ValueError("JSON bị kết thúc trước dấu đóng object.")
                fill()
                continue
            if buffer[position] == "}":
                return
            decode_value()  # khóa record, thường là chuỗi chỉ số
            while True:
                while position < len(buffer) and buffer[position].isspace():
                    position += 1
                if position < len(buffer):
                    break
                fill()
            if buffer[position] != ":":
                raise ValueError("JSON record thiếu dấu hai chấm.")
            position += 1
            row = decode_value()
            if not isinstance(row, dict):
                raise ValueError("Mỗi record JSON phải là object.")
            yield row


def estimate_sampling_rate(times: np.ndarray) -> tuple[float | None, float | None, float]:
    if len(times) < 2:
        return None, None, 0.0
    differences = np.diff(times)
    positive = differences[np.isfinite(differences) & (differences > 0)]
    if not len(positive):
        return None, None, 1.0
    median_dt = float(np.median(positive))
    rate = 1.0 / median_dt
    irregularity = float(np.median(np.abs(positive - median_dt)) / median_dt)
    return rate, median_dt, irregularity


def deterministic_duplicate_policy(times: np.ndarray, signals: dict[str, np.ndarray], tolerance: float = 0.0):
    """Sort stably; keep first exact duplicate, drop all records at conflicting times."""
    if not len(times):
        return times, {k: v for k, v in signals.items()}, {"reordered_rows": 0, "duplicate_rows_removed": 0,
            "identical_duplicate_rows_removed": 0,
            "conflicting_timestamp_groups": 0, "conflicting_rows_removed": 0, "duplicate_groups": 0}
    order = np.argsort(times, kind="stable")
    reordered = int(np.count_nonzero(order != np.arange(len(times))))
    times = np.asarray(times, dtype=np.float64)[order]
    signals = {k: np.asarray(v)[order] for k, v in signals.items()}
    keep = np.ones(len(times), dtype=bool)
    duplicate_rows = identical_duplicate_rows = conflicting_groups = conflicting_rows = groups = 0
    starts = np.r_[0, np.flatnonzero(np.diff(times) != 0) + 1]
    ends = np.r_[starts[1:], len(times)]
    for start, end in zip(starts, ends):
        size = end - start
        if size <= 1:
            continue
        groups += 1
        duplicate_rows += size - 1
        reference = start
        conflict = False
        for index in range(start + 1, end):
            for values in signals.values():
                a, b = values[reference], values[index]
                if np.issubdtype(values.dtype, np.number):
                    if not (np.isnan(a) and np.isnan(b)) and not np.isclose(a, b, rtol=0, atol=tolerance, equal_nan=True):
                        conflict = True
                        break
                elif a != b:
                    conflict = True
                    break
            if conflict:
                break
        if conflict:
            keep[start:end] = False
            conflicting_groups += 1
            conflicting_rows += size
        else:
            keep[start + 1:end] = False
            identical_duplicate_rows += size - 1
    return times[keep], {k: v[keep] for k, v in signals.items()}, {
        "reordered_rows": int(reordered), "duplicate_rows_removed": int(duplicate_rows),
        "identical_duplicate_rows_removed": int(identical_duplicate_rows),
        "conflicting_timestamp_groups": conflicting_groups,
        "conflicting_rows_removed": int(conflicting_rows), "duplicate_groups": int(groups),
    }


def clean_required_values(session: RawSession):
    count = len(session.time_seconds)
    keep = np.isfinite(session.time_seconds)
    for key in session.required_signals:
        keep &= np.isfinite(session.signals[key])
    dropped = int(count - keep.sum())
    return RawSession(session.dataset_source, session.session_id, session.raw_reference,
        session.time_seconds[keep], {k: v[keep] for k, v in session.signals.items()},
        session.required_signals, session.provenance, session.warnings, count), dropped


def split_continuous_segments(times: np.ndarray, maximum_gap_factor: float = 1.5):
    """Split only at gaps > factor * median positive time step."""
    if len(times) < 2:
        return [(0, len(times))], {"median_dt_seconds": None, "gap_count": 0, "gap_indices": []}
    dt = np.diff(times)
    positive = dt[dt > 0]
    median_dt = float(np.median(positive)) if len(positive) else None
    if median_dt is None:
        return [(0, len(times))], {"median_dt_seconds": None, "gap_count": 0, "gap_indices": []}
    gaps = np.flatnonzero(dt > maximum_gap_factor * median_dt) + 1
    starts = np.r_[0, gaps]
    ends = np.r_[gaps, len(times)]
    segments = [(int(a), int(b)) for a, b in zip(starts, ends) if b > a]
    return segments, {"median_dt_seconds": median_dt, "gap_count": int(len(gaps)),
                      "gap_indices": gaps.astype(int).tolist()}


def window_eligibility(times: np.ndarray, windows=(60.0, 180.0)) -> dict[str, bool]:
    duration = float(times[-1] - times[0]) if len(times) > 1 else 0.0
    return {f"{int(window)}s": duration >= window for window in windows}


def count_missing(signals: dict[str, np.ndarray]) -> dict[str, int]:
    return {name: int(np.count_nonzero(~np.isfinite(values))) for name, values in signals.items()}


def finite_stats(values: np.ndarray) -> dict:
    x = np.asarray(values, dtype=np.float64)
    x = x[np.isfinite(x)]
    if not len(x):
        return {"count": 0, "missing": int(len(values)), "mean": None, "std_population": None,
                "min": None, "max": None, "p05": None, "p50": None, "p95": None,
                "rms": None, "peak_to_peak": None}
    return {"count": int(len(x)), "missing": int(len(values) - len(x)),
        "mean": float(np.mean(x)), "std_population": float(np.std(x, ddof=0)),
        "min": float(np.min(x)), "max": float(np.max(x)),
        "p05": float(np.quantile(x, .05, method="linear")),
        "p50": float(np.quantile(x, .50, method="linear")),
        "p95": float(np.quantile(x, .95, method="linear")),
        "rms": float(np.sqrt(np.mean(np.square(x)))),
        "peak_to_peak": float(np.ptp(x))}
