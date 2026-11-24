from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook

from ml.preprocessing.common import (deterministic_duplicate_policy, split_continuous_segments,
                                     window_eligibility)
from ml.preprocessing.hohai import load_sessions as load_hohai
from ml.preprocessing.run import _relative_raw_reference, _relative_repo_path
from ml.preprocessing.schemas import RawSession
from ml.preprocessing.seafar import load_sessions as load_seafar
from ml.preprocessing.signal_processing import (causal_previous_sample, lowpass_causal,
                                                process_session)
from ml.preprocessing.southampton import load_sessions as load_southampton
from ml.preprocessing.units import rad_per_minute_to_rad_per_second


SETTINGS = {"target_sampling_hz": 10.0, "maximum_gap_factor": 1.5,
    "duplicate_tolerance": 0.0, "filter_order": 4, "anti_alias_cutoff_hz": 4.0,
    "filter_warmup_seconds": 2.0, "minimum_segment_seconds": 1.0,
    "valid_fraction_threshold": 0.95}


def make_session(session_id="test_session", start=0.0, fs=10.0, duration=20.0):
    times = start + np.arange(int(duration * fs) + 1) / fs
    roll = np.sin(2 * np.pi * 0.4 * (times - start))
    pitch = 0.5 * np.sin(2 * np.pi * 0.25 * (times - start))
    return RawSession("fixture", session_id, "synthetic-fixture", times,
        {"roll_deg": roll, "pitch_deg": pitch,
         "gyro_x_rad_s": np.full(len(times), np.nan), "gyro_y_rad_s": np.full(len(times), np.nan)},
        original_row_count=len(times))


class PreprocessingTests(unittest.TestCase):
    def test_generated_metadata_paths_are_repository_relative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_path = root / "ml" / "data" / "raw" / "hohai.xlsx"
            raw_path.parent.mkdir(parents=True)
            raw_path.touch()
            self.assertEqual(_relative_repo_path(root / "ml/data/processed/out.parquet", root),
                             "ml/data/processed/out.parquet")
            self.assertEqual(_relative_raw_reference(f"{raw_path}::Sheet_A", root),
                             "ml/data/raw/hohai.xlsx::Sheet_A")

    def test_unit_conversion_rad_per_minute_to_rad_per_second(self):
        result = rad_per_minute_to_rad_per_second(np.array([60.0, -30.0]))
        np.testing.assert_allclose(result, [1.0, -0.5])

    def test_seafar_timestamp_parsing_and_source_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seafar"
            path.mkdir()
            rows = []
            for i in range(4):
                rows.append({"datetime": 1_700_000_000_000 + i * 100,
                    "roll_degrees": 1.0, "pitch_degrees": 2.0,
                    "roll_rate_rad_min": 60.0, "pitch_rate_rad_min": -30.0})
            (path / "cleaned_imu_gps_data.json").write_text(json.dumps({str(i): row for i, row in enumerate(rows)}))
            session = load_seafar(Path(tmp))[0]
        self.assertEqual(session.time_seconds[0], 1_700_000_000.0)
        self.assertAlmostEqual(session.time_seconds[1] - session.time_seconds[0], 0.1, places=6)
        np.testing.assert_allclose(session.signals["gyro_x_rad_s"], 1.0)
        np.testing.assert_allclose(session.signals["gyro_y_rad_s"], -0.5)

    def test_duplicate_policy_keeps_identical_and_drops_conflicting_groups(self):
        times = np.array([0.0, 0.0, 0.1, 0.1])
        signals = {"roll": np.array([1.0, 1.0, 2.0, 3.0])}
        out_t, out_s, report = deterministic_duplicate_policy(times, signals)
        np.testing.assert_allclose(out_t, [0.0])
        np.testing.assert_allclose(out_s["roll"], [1.0])
        self.assertEqual(report["duplicate_rows_removed"], 2)
        self.assertEqual(report["identical_duplicate_rows_removed"], 1)
        self.assertEqual(report["conflicting_timestamp_groups"], 1)
        self.assertEqual(report["conflicting_rows_removed"], 2)

    def test_gap_segmentation_does_not_bridge_large_gap(self):
        times = np.array([0, .1, .2, .3, 2.0, 2.1, 2.2])
        segments, report = split_continuous_segments(times)
        self.assertEqual(segments, [(0, 4), (4, 7)])
        self.assertEqual(report["gap_count"], 1)

    def test_filter_state_restarts_at_each_gap_segment(self):
        first = make_session("gap_session", start=0, fs=50, duration=20)
        second = make_session("isolated_segment", start=30, fs=50, duration=20)
        combined = RawSession("fixture", "gap_session", "synthetic-fixture",
            np.r_[first.time_seconds, second.time_seconds],
            {key: np.r_[first.signals[key], second.signals[key]] for key in first.signals},
            original_row_count=len(first.time_seconds) + len(second.time_seconds))
        segments, summary = process_session(combined, SETTINGS, Path.cwd())
        isolated, _ = process_session(second, SETTINGS, Path.cwd())
        self.assertEqual(len(segments), 2)
        self.assertEqual(summary["gap_count"], 1)
        np.testing.assert_allclose(segments[1].frame.roll_deg, isolated[0].frame.roll_deg)

    def test_sessions_are_processed_independently(self):
        first = make_session("run_a", start=0)
        second = make_session("run_b", start=1000)
        out_a, _ = process_session(first, SETTINGS, Path.cwd())
        out_b, _ = process_session(second, SETTINGS, Path.cwd())
        self.assertEqual({seg.session_id for seg in out_a}, {"run_a"})
        self.assertEqual({seg.session_id for seg in out_b}, {"run_b"})
        self.assertAlmostEqual(out_a[0].frame.time_seconds.iloc[0], 0.0)
        self.assertAlmostEqual(out_b[0].frame.time_seconds.iloc[0], 0.0)

    def test_hohai_time_is_inferred_from_sample_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "hohai"
            root.mkdir()
            path = root / "6-DOF ship motions Data.xlsx"
            wb = Workbook()
            ws = wb.active
            ws.append(["Sway", "Surge", "Heave", "Roll", "Pitch", "Yaw"])
            ws.append([0, 0, 0, 1, 2, 3]); ws.append([0, 0, 0, 1, 2, 3])
            wb.save(path)
            session = load_hohai(Path(tmp))[0]
        self.assertEqual(session.provenance["timestamp_source"], "INFERRED_FROM_SAMPLE_INDEX")
        np.testing.assert_allclose(session.time_seconds, [0, .02])
        self.assertEqual(session.provenance["original_sampling_hz"], 50.0)

    def test_gyro_channels_remain_missing_when_not_measured(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "hohai"
            root.mkdir()
            wb = Workbook(); ws = wb.active
            ws.append(["Sway", "Surge", "Heave", "Roll", "Pitch", "Yaw"])
            ws.append([0, 0, 0, 1, 2, 3]); wb.save(root / "6-DOF ship motions Data.xlsx")
            session = load_hohai(Path(tmp))[0]
        self.assertTrue(np.isnan(session.signals["gyro_x_rad_s"]).all())
        self.assertTrue(np.isnan(session.signals["gyro_y_rad_s"]).all())

    def test_fifty_to_ten_hz_resampling_is_configured(self):
        session = make_session(fs=50.0, duration=20.0)
        segments, summary = process_session(session, SETTINGS, Path.cwd())
        self.assertEqual(summary["target_sampling_hz_effective"], 10.0)
        self.assertTrue(segments[0].provenance["filter"]["applied"])
        self.assertAlmostEqual(segments[0].quality["sampling_rate_after_hz"], 10.0)
        self.assertAlmostEqual(segments[0].frame.time_seconds.iloc[0], 2.0)

    def test_antialias_filter_preserves_low_frequency_and_attenuates_high_frequency(self):
        fs = 50.0
        time = np.arange(0, 30, 1 / fs)
        low = np.sin(2 * np.pi * .5 * time)
        filtered_low = lowpass_causal(low, fs, 4.0)
        high = np.sin(2 * np.pi * 8.0 * time)
        filtered_high = lowpass_causal(high, fs, 4.0)
        warm = int(2 * fs)
        low_ratio = np.sqrt(np.mean(filtered_low[warm:] ** 2)) / np.sqrt(np.mean(low[warm:] ** 2))
        high_ratio = np.sqrt(np.mean(filtered_high[warm:] ** 2)) / np.sqrt(np.mean(high[warm:] ** 2))
        self.assertGreater(low_ratio, 0.97)
        self.assertLess(low_ratio, 1.03)
        self.assertLess(high_ratio, 0.05)

    def test_antialias_filter_covers_continuous_channels_and_preserves_raw_rate_fields(self):
        fs = 50.0
        time = np.arange(0, 30, 1 / fs)
        session = RawSession("fixture", "channel_filter", "synthetic-fixture", time,
            {"roll_deg": np.sin(2 * np.pi * .5 * time),
             "pitch_deg": np.sin(2 * np.pi * .4 * time),
             "accel_x_m_s2": np.sin(2 * np.pi * 8.0 * time),
             "delta_angle_x_deg_s_raw": np.sin(2 * np.pi * 8.0 * time),
             "gyro_x_rad_s": np.full(len(time), np.nan),
             "gyro_y_rad_s": np.full(len(time), np.nan)},
            original_row_count=len(time))
        segments, _ = process_session(session, SETTINGS, Path.cwd())
        segment = segments[0]
        accel = segment.aligned["accel_x_m_s2"]
        raw_rate = segment.aligned["delta_angle_x_deg_s_raw"]
        accel_ratio = np.sqrt(np.mean(accel["after"] ** 2)) / np.sqrt(np.mean(accel["before"] ** 2))
        self.assertLess(accel_ratio, 0.1)
        np.testing.assert_array_equal(raw_rate["after"], raw_rate["before"])
        self.assertIn("accel_x_m_s2", segment.provenance["filter"]["channels_filtered"])
        self.assertIn("delta_angle_x_deg_s_raw", segment.provenance["filter"]["raw_channels_preserved_without_filter"])

    def test_processing_is_deterministic(self):
        session = make_session()
        first, _ = process_session(session, SETTINGS, Path.cwd())
        second, _ = process_session(session, SETTINGS, Path.cwd())
        pd.testing.assert_frame_equal(first[0].frame, second[0].frame)

    def test_no_cross_session_interpolation_or_join(self):
        first = make_session("session_1", start=0, duration=5)
        second = make_session("session_2", start=100, duration=5)
        a, _ = process_session(first, SETTINGS, Path.cwd())
        b, _ = process_session(second, SETTINGS, Path.cwd())
        self.assertEqual(len(a), 1); self.assertEqual(len(b), 1)
        self.assertEqual(a[0].session_id, "session_1")
        self.assertEqual(b[0].session_id, "session_2")
        self.assertEqual(float(a[0].frame.time_seconds.iloc[0]), 0.0)
        self.assertEqual(float(b[0].frame.time_seconds.iloc[0]), 0.0)

    def test_causal_filter_prefix_is_independent_of_future_samples(self):
        fs = 50.0
        prefix = np.zeros(100); prefix[20] = 1.0
        first = lowpass_causal(prefix, fs, 4.0)
        extended = np.r_[prefix, np.ones(100) * 20]
        second = lowpass_causal(extended, fs, 4.0)
        np.testing.assert_allclose(first, second[:len(prefix)])
        source_t = np.array([0.0, 1.0, 2.0]); source_v = np.array([1.0, 2.0, 99.0])
        sampled, _, _ = causal_previous_sample(source_t, source_v, np.array([1.5]))
        self.assertEqual(sampled[0], 2.0)  # không đọc giá trị ở t=2.0

    def test_window_eligibility_uses_elapsed_endpoints(self):
        self.assertEqual(window_eligibility(np.arange(0, 60.01, .1)), {"60s": True, "180s": False})
        self.assertEqual(window_eligibility(np.arange(0, 179.91, .1)), {"60s": True, "180s": False})
        self.assertEqual(window_eligibility(np.arange(0, 180.01, .1)), {"60s": True, "180s": True})

    def test_southampton_schema_preserves_delta_angle_without_gyro_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "southampton" / "Raw Data_IMU"
            folder.mkdir(parents=True)
            p = folder / "Run2_IMU.csv"
            p.write_text("Time Stamp,Heave,Roll,Pitch,Yaw,Accelerometer X,Accelerometer Y,Accelerometer Z,Delta Angle X,Delta Angle Y,Delta Angle Z\n"
                         "(s),(m),(°),(°),(°),(m.s^-2),(m.s^-2),(m.s^-2),(°.s^-1),(°.s^-1),(°.s^-1)\n"
                         "0,0,1,2,3,0,0,-9.8,10,20,30\n0.02,0,1,2,3,0,0,-9.8,10,20,30\n")
            session = load_southampton(Path(tmp))[0]
        self.assertIn("delta_angle_x_deg_s_raw", session.signals)
        self.assertTrue(np.isnan(session.signals["gyro_x_rad_s"]).all())
        self.assertEqual(session.provenance["unit_original"]["Delta Angle X/Y/Z"], "degree/s per CSV unit row")

    def test_missing_required_values_are_detectable_without_zero_fill(self):
        session = make_session()
        session.signals["roll_deg"][5] = np.nan
        segments, summary = process_session(session, SETTINGS, Path.cwd())
        self.assertEqual(summary["invalid_required_rows_removed"], 1)
        self.assertNotIn(0.0, segments[0].frame.roll_deg.to_numpy())
        self.assertTrue(np.isnan(segments[0].frame.gyro_x_rad_s).all())


if __name__ == "__main__":
    unittest.main()
