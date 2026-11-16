from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from .common import Moments, angle_summary, window_eligibility

HOHAI_SAMPLING_HZ = 50.0
HOHAI_UNITS = {"Sway": "m", "Surge": "m", "Heave": "m",
               "Roll": "degree", "Pitch": "degree", "Yaw": "degree"}
HOHAI_METADATA_SOURCE = "User-provided confirmation from ml/data/raw/hohai/Data Description Example.pdf; PDF text was not parsed in this environment."


def duration_from_sample_count(sample_count: int, sampling_hz: float = HOHAI_SAMPLING_HZ) -> float | None:
    """Elapsed time between first and last samples for a uniform sample cadence."""
    return (sample_count - 1) / sampling_hz if sample_count > 0 and sampling_hz > 0 else None


def audit_hohai(path: Path, sampling_hz: float | None = HOHAI_SAMPLING_HZ) -> dict:
    wb = load_workbook(path, read_only=True, data_only=True)
    sessions = []
    try:
        for ws in wb.worksheets:
            it = ws.iter_rows(values_only=True)
            headers = [str(x).strip() if x is not None else "" for x in next(it, ())]
            cols = {h: Moments() for h in headers}
            roll, pitch, n = [], [], 0
            for row in it:
                if not any(v is not None for v in row): continue
                n += 1
                for i, h in enumerate(headers):
                    cols[h].add(row[i] if i < len(row) else None)
                try: roll.append(float(row[headers.index("Roll")]))
                except (ValueError, TypeError, IndexError): pass
                try: pitch.append(float(row[headers.index("Pitch")]))
                except (ValueError, TypeError, IndexError): pass
            duration = duration_from_sample_count(n, sampling_hz) if sampling_hz else None
            sessions.append({"session_id": ws.title, "sample_count": n, "columns": headers,
                "missing_by_column": {k: v.missing for k, v in cols.items()},
                "statistics": {k: v.summary() for k, v in cols.items()},
                "angles": {"roll": angle_summary(roll), "pitch": angle_summary(pitch)},
                "sampling_hz": sampling_hz, "sample_interval_s": 1 / sampling_hz if sampling_hz else None,
                "duration_s": duration, "units": {k: HOHAI_UNITS.get(k) for k in headers},
                "window_eligibility": window_eligibility(duration),
                "gyro_direct": False, "timestamp_present": False})
    finally:
        wb.close()
    return {"dataset": "hohai", "path": str(path), "session_count": len(sessions),
            "sessions": sessions,
            "documented_metadata": {"sampling_hz": sampling_hz,
                "units": HOHAI_UNITS if sampling_hz else None,
                "source_document": "ml/data/raw/hohai/Data Description Example.pdf",
                "source_confirmation": HOHAI_METADATA_SOURCE if sampling_hz else None,
                "pdf_parse_status": "not_parsed_missing_pdf_dependency"},
            "notes": ["Each worksheet is an independent experimental session.",
                "The workbook has no timestamp column; sample rate and units come from supplied source metadata, not workbook fields.",
                "Only six DOF motion columns are present; no directly measured gyro columns."]}


def main():
    import json
    from .audit_all import write_json
    root = Path(__file__).resolve().parents[2]
    result = audit_hohai(root / "ml/data/raw/hohai/6-DOF ship motions Data.xlsx")
    write_json(root / "ml/audit/dataset_inventory.json", {"hohai": result})
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__": main()
