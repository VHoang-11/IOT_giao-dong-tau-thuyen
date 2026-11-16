from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterator

from .common import Moments, angle_summary, continuous_segments


class _JSONStream:
    """Small buffered decoder for a top-level JSON object; keeps only one record at a time."""
    def __init__(self, path: Path):
        self.file = path.open("r", encoding="utf-8")
        self.decoder = json.JSONDecoder()
        self.buf = ""
        self.pos = 0
        self.eof = False

    def _fill(self):
        if self.pos:
            self.buf = self.buf[self.pos:]
            self.pos = 0
        more = self.file.read(1024 * 1024)
        self.buf += more
        self.eof = not more

    def _value(self):
        while True:
            while self.pos < len(self.buf) and self.buf[self.pos].isspace(): self.pos += 1
            try:
                value, end = self.decoder.raw_decode(self.buf, self.pos)
                self.pos = end
                return value
            except json.JSONDecodeError:
                if self.eof: raise
                self._fill()

    def items(self) -> Iterator[dict]:
        while True:
            while True:
                if self.pos >= len(self.buf) and not self.eof: self._fill()
                while self.pos < len(self.buf) and self.buf[self.pos].isspace(): self.pos += 1
                if self.pos < len(self.buf): break
            ch = self.buf[self.pos]
            if ch == "{": self.pos += 1; continue
            if ch == "}": return
            if ch == ",": self.pos += 1; continue
            _key = self._value()
            while True:
                while self.pos < len(self.buf) and self.buf[self.pos].isspace(): self.pos += 1
                if self.pos < len(self.buf): break
                self._fill()
            if self.buf[self.pos] != ":": raise ValueError("Invalid JSON object: expected colon")
            self.pos += 1
            yield self._value()

    def close(self): self.file.close()


def audit_seafar(path: Path) -> dict:
    names = None
    counts, stats, timestamps, roll, pitch = 0, {}, [], [], []
    rates = {}
    stream = _JSONStream(path)
    try:
        for row in stream.items():
            if not isinstance(row, dict): continue
            counts += 1
            names = list(row) if names is None else names
            for key, value in row.items(): stats.setdefault(key, Moments()).add(value)
            try: timestamps.append(float(row["datetime"]) / 1000.0)
            except (KeyError, TypeError, ValueError): pass
            for field, target in (("roll_degrees", roll), ("pitch_degrees", pitch)):
                try: target.append(float(row[field]))
                except (KeyError, TypeError, ValueError): pass
            for field in ("roll_rate_rad_min", "pitch_rate_rad_min", "yaw_rate_rad_min", "yaw_rate_degrees_min"):
                if field in row: rates.setdefault(field, Moments()).add(row[field])
    finally: stream.close()
    time = continuous_segments(timestamps)
    time["eligible_windows"] = {"60s": sum(s["duration_s"] >= 60 for s in time["continuous_segments"]),
                                "180s": sum(s["duration_s"] >= 180 for s in time["continuous_segments"])}
    return {"dataset": "seafar", "path": str(path), "record_count": counts, "columns": names or [],
            "types": {k: "numeric" if v.n else "non-numeric_or_empty" for k, v in stats.items()},
            "missing_by_column": {k: v.missing for k, v in stats.items()},
            "statistics": {k: v.summary() for k, v in stats.items()}, "time": time,
            "angles_deg": {"roll_degrees": angle_summary(roll), "pitch_degrees": angle_summary(pitch)},
            "angular_rate_statistics": {k: v.summary() for k, v in rates.items()},
            "units": {"datetime": "Unix epoch milliseconds", "roll_degrees": "degrees",
                      "pitch_degrees": "degrees", "roll_rate_rad_min": "rad/min",
                      "pitch_rate_rad_min": "rad/min", "yaw_rate_rad_min": "rad/min",
                      "yaw_rate_degrees_min": "degrees/min", "accel_*_ms2": "field name indicates m/s^2"},
            "notes": ["JSON records streamed one at a time.", "No explicit IMU gyroscope unit calibration metadata was found."]}


def main():
    from .audit_all import write_json
    root = Path(__file__).resolve().parents[2]
    result = audit_seafar(root / "ml/data/raw/seafar/cleaned_imu_gps_data.json")
    write_json(root / "ml/audit/dataset_inventory.json", {"seafar": result})
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__": main()
