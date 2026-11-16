import csv
import json
import tempfile
import unittest
from pathlib import Path

from ml.audit.audit_all import _feature_candidates
from ml.audit.audit_hohai import (HOHAI_SAMPLING_HZ, HOHAI_UNITS, audit_hohai,
                                  duration_from_sample_count)
from ml.audit.common import csv_audit, continuous_segments, window_eligibility


class AuditRulesTests(unittest.TestCase):
    def test_timestamp_continuity_detects_duplicate_and_gap(self):
        result = continuous_segments([0, 0.1, 0.2, 0.2, 1.0, 1.1])
        self.assertEqual(result["duplicate_timestamps"], 1)
        self.assertEqual(result["gap_count"], 1)
        self.assertEqual(len(result["continuous_segments"]), 2)

    def test_window_eligibility_uses_elapsed_duration(self):
        self.assertEqual(window_eligibility(179.99), {"60s": True, "180s": False})
        self.assertEqual(window_eligibility(None), {"60s": False, "180s": False})

    def test_csv_missing_and_nonfinite_are_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "sample.csv"
            p.write_text("Time Stamp,Roll\n(s),(deg)\n0,1\n0.1,\n0.2,nan\n", encoding="utf-8")
            result = csv_audit(p, units_row=True)
        self.assertEqual(result["sample_count"], 3)
        self.assertEqual(result["missing_by_column"]["Roll"], 2)
        self.assertEqual(result["time"]["sampling_hz"], 10)

    def test_dataset_inventory_is_json_and_keeps_sessions_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "sessions.xlsx"
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "session_a"
            ws.append(["Roll", "Pitch"]); ws.append([1, 2])
            ws2 = wb.create_sheet("session_b")
            ws2.append(["Roll", "Pitch"]); ws2.append([3, 4])
            wb.save(p)
            result = audit_hohai(p)
            encoded = json.dumps(result)
        self.assertEqual(result["session_count"], 2)
        self.assertEqual([s["session_id"] for s in result["sessions"]], ["session_a", "session_b"])
        self.assertIn("session_a", encoded)
        self.assertEqual(result["sessions"][0]["duration_s"], 0)
        self.assertEqual(result["sessions"][0]["sampling_hz"], 50)
        self.assertEqual(result["sessions"][0]["units"], {"Roll": "degree", "Pitch": "degree"})
        self.assertEqual(result["documented_metadata"]["source_document"],
                         "ml/data/raw/hohai/Data Description Example.pdf")
        self.assertEqual(result["documented_metadata"]["pdf_parse_status"],
                         "not_parsed_missing_pdf_dependency")

    def test_hohai_documented_sampling_metadata_and_units_regression(self):
        self.assertEqual(HOHAI_SAMPLING_HZ, 50.0)
        self.assertEqual(HOHAI_UNITS, {"Sway": "m", "Surge": "m", "Heave": "m",
                                      "Roll": "degree", "Pitch": "degree", "Yaw": "degree"})
        self.assertAlmostEqual(duration_from_sample_count(45000), 899.98)
        self.assertEqual(window_eligibility(duration_from_sample_count(45000)),
                         {"60s": True, "180s": True})

    def test_feature_availability_never_calls_derived_angle_rate_measured_gyro(self):
        inv = _feature_candidates({})
        hohai_rate = next(x for x in inv if x["name"] == "roll_rate_mean_60s")["per_source"]["hohai"]
        self.assertEqual(hohai_rate["status"], "UNAVAILABLE")
        self.assertIn("No direct gyro", hohai_rate["detail"])
        self.assertEqual(len(inv), 30)


if __name__ == "__main__":
    unittest.main()
