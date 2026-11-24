from __future__ import annotations

import csv
import re
from pathlib import Path

from openpyxl import load_workbook

from .common import csv_audit, window_eligibility


def _test_plan(path: Path) -> dict:
    if not path.exists(): return {"available": False, "runs": {}}
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        rows = ws.iter_rows(values_only=True)
        headers = [str(v).strip() if v is not None else "" for v in next(rows, ())]
        ix = {h: i for i, h in enumerate(headers) if h}
        result = {}
        last = {}
        for row in rows:
            vals = {h: (row[i] if i < len(row) else None) for h, i in ix.items()}
            # Excel's plan repeats run number for multiple speed/propulsion settings.
            run = vals.get("Run Number") or vals.get("Run Number ")
            if run is not None: last["Run Number"] = int(run)
            if not last: continue
            run_id = vals.get("Run ID")
            if run_id is None: continue
            key = str(run_id).strip()
            result[key] = {k: v.isoformat() if hasattr(v, "isoformat") else v
                           for k, v in vals.items() if v is not None}
            result[key]["run_number"] = last.get("Run Number")
        return {"available": True, "runs": result, "rows_by_run_id": len(result)}
    finally: wb.close()


def audit_southampton(root: Path) -> dict:
    imu_dir = root / "Raw Data_IMU"
    files = sorted(imu_dir.glob("*.csv"), key=lambda p: int(re.search(r"Run(\d+)", p.name).group(1)))
    runs = []
    for path in files:
        entry = csv_audit(path, units_row=True)
        entry["run_id"] = int(re.search(r"Run(\d+)", path.name).group(1))
        t = entry.get("time")
        entry["window_eligibility"] = window_eligibility(t.get("duration_s") if t else None)
        runs.append(entry)
    lasso_files = sorted((root / "Raw Data_Lasso").glob("*.csv"), key=lambda p: int(re.search(r"Run(\d+)", p.name).group(1)))
    lasso_ids = {int(re.search(r"Run(\d+)", p.name).group(1)) for p in lasso_files}
    plan = _test_plan(root / "Readme/KCS Test Plan June 2023.xlsx")
    planned_run_numbers = {x.get("run_number") for x in plan["runs"].values() if isinstance(x.get("run_number"), int)}
    wave_rows = [x for x in plan["runs"].values()
                 if isinstance(x.get("Wave frequency, Hz"), (int, float))
                 or isinstance(x.get("Wave amplitude, m"), (int, float))]
    wave_run_numbers = sorted({x["run_number"] for x in wave_rows if isinstance(x.get("run_number"), int)})
    imu_ids = {r["run_id"] for r in runs}
    eligible60 = [r["run_id"] for r in runs if r["window_eligibility"]["60s"]]
    eligible180 = [r["run_id"] for r in runs if r["window_eligibility"]["180s"]]
    return {"dataset": "southampton", "imu_csv_count": len(files), "lasso_csv_count": len(lasso_files),
        "runs": runs, "eligible_60s_run_ids": eligible60, "eligible_180s_run_ids": eligible180,
        "run_id_matching": {"imu_ids": sorted(imu_ids), "lasso_ids": sorted(lasso_ids),
            "matching_ids": sorted(imu_ids & lasso_ids), "imu_without_lasso": sorted(imu_ids - lasso_ids),
            "lasso_without_imu": sorted(lasso_ids - imu_ids), "merge_performed": False,
            "timestamp_alignment_assessed": False},
        "test_plan": {**plan, "imu_run_numbers_in_plan": sorted(imu_ids & planned_run_numbers),
                      "imu_missing_from_plan": sorted(imu_ids - planned_run_numbers),
                      "wave_test_run_numbers": wave_run_numbers,
                      "wave_test_run_numbers_with_imu": sorted(imu_ids & set(wave_run_numbers)),
                      "wave_test_run_numbers_with_eligible_60s": sorted(set(eligible60) & set(wave_run_numbers)),
                      "wave_test_run_numbers_with_eligible_180s": sorted(set(eligible180) & set(wave_run_numbers))},
        "units": {"Time Stamp": "s, elapsed/relative value (starts vary by run)", "Roll/Pitch/Yaw": "degrees",
            "Accelerometer X/Y/Z": "m/s^2", "Delta Angle X/Y/Z": "degrees/s per CSV unit row; field name says Delta Angle, units row says angular rate"},
        "notes": ["Every IMU CSV is a separate run; no runs concatenated.",
            "Lasso matching is by run number only; timestamp synchronization was not inferred."]}


def main():
    import json
    from .audit_all import write_json
    root = Path(__file__).resolve().parents[2] / "ml/data/raw/southampton"
    result = audit_southampton(root)
    write_json(Path(__file__).resolve().parents[1] / "audit/dataset_inventory.json", {"southampton": result})
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__": main()
