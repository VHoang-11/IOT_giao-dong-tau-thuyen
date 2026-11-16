from __future__ import annotations

import csv
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence


def window_eligibility(duration_s: float | None, windows: Sequence[float] = (60, 180)) -> dict[str, bool]:
    return {f"{int(w)}s": duration_s is not None and duration_s >= w for w in windows}


def continuous_segments(timestamps: Iterable[float], nominal_dt: float | None = None) -> dict:
    """Summarize ordered timestamp continuity; a gap is >1.5x median positive step."""
    ts = list(timestamps)
    deltas = [b - a for a, b in zip(ts, ts[1:])]
    positive = [d for d in deltas if d > 0 and math.isfinite(d)]
    base = statistics.median(positive) if positive else nominal_dt
    duplicates = sum(d == 0 for d in deltas)
    non_increasing = sum(d <= 0 for d in deltas)
    gaps = [i + 1 for i, d in enumerate(deltas) if base and d > 1.5 * base]
    starts = [0] + gaps
    ends = gaps + [len(ts)]
    segments = []
    for start, end in zip(starts, ends):
        if end <= start:
            continue
        duration = ts[end - 1] - ts[start] if end - start > 1 else 0.0
        segments.append({"start_index": start, "end_index_exclusive": end,
                         "samples": end - start, "duration_s": duration})
    return {
        "samples": len(ts), "start_s": ts[0] if ts else None,
        "end_s": ts[-1] if ts else None,
        "duration_s": ts[-1] - ts[0] if len(ts) > 1 else (0.0 if ts else None),
        "median_dt_s": base, "sampling_hz": 1.0 / base if base and base > 0 else None,
        "duplicate_timestamps": duplicates, "non_increasing_steps": non_increasing,
        "gap_count": len(gaps), "continuous_segments": segments,
        "eligible_segment_counts": {
            "60s": sum(s["duration_s"] >= 60 for s in segments),
            "180s": sum(s["duration_s"] >= 180 for s in segments),
        },
    }


@dataclass
class Moments:
    n: int = 0
    missing: int = 0
    total: float = 0.0
    total_sq: float = 0.0
    minimum: float | None = None
    maximum: float | None = None

    def add(self, value) -> None:
        try:
            x = float(value)
            if not math.isfinite(x):
                raise ValueError
        except (TypeError, ValueError):
            self.missing += 1
            return
        self.n += 1
        self.total += x
        self.total_sq += x * x
        self.minimum = x if self.minimum is None else min(self.minimum, x)
        self.maximum = x if self.maximum is None else max(self.maximum, x)

    def summary(self) -> dict:
        mean = self.total / self.n if self.n else None
        variance = max(0.0, self.total_sq / self.n - mean * mean) if self.n else None
        return {"valid": self.n, "missing_or_nonfinite": self.missing, "min": self.minimum,
                "max": self.maximum, "mean": mean,
                "std": math.sqrt(variance) if variance is not None else None}


def csv_audit(path: Path, units_row: bool = False) -> dict:
    """Stream a CSV and compute numeric quality summaries; never materializes rows."""
    with path.open("r", newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        headers = next(reader, [])
        units = next(reader, []) if units_row else []
        cols = {name: Moments() for name in headers}
        ts = []
        row_count = 0
        malformed_rows = 0
        for row in reader:
            if not row or all(not cell.strip() for cell in row):
                continue
            row_count += 1
            if len(row) != len(headers):
                malformed_rows += 1
            for i, name in enumerate(headers):
                cols[name].add(row[i].strip() if i < len(row) else None)
            if headers and headers[0].strip().lower() in {"time stamp", "timestamp", "time", "datetime"}:
                try:
                    ts.append(float(row[0]))
                except (IndexError, ValueError):
                    pass
    result = {"path": str(path), "sample_count": row_count, "columns": headers,
              "units": dict(zip(headers, units)), "malformed_rows": malformed_rows,
              "statistics": {k: v.summary() for k, v in cols.items()},
              "missing_by_column": {k: v.missing for k, v in cols.items()}}
    result["time"] = continuous_segments(ts) if ts else None
    return result


def percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def angle_summary(values: Sequence[float]) -> dict:
    m = Moments()
    for v in values:
        m.add(v)
    out = m.summary()
    out["p05"] = percentile(values, .05)
    out["p95"] = percentile(values, .95)
    return out
