"""Test gói parity 23 feature: contract, golden, dung sai, harness, interchange, manifest.

Các test real-data tự bỏ qua nếu dữ liệu processed/golden real (gitignored) vắng mặt.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.features.calculations import type7_quantile
from ml.labeling.ai_assisted_review import protected_checksums
from ml.parity import analytic, compare, float32_probe, interchange, readiness
from ml.parity.cases import SYNTHETIC_CASES, synthetic_signal
from ml.parity.contract import (CONTRACT_V02, EXPECTED_SELECTION, FEATURE_ORDER, SCHEMA_VERSION, STATUS_VOCABULARY,
                                feature_settings, run_extractor, schema_sha256, validate_contract)
from ml.parity.golden import (MANIFEST, REAL_ROOT, SYNTHETIC_ROOT, build_suite, fmt32, inputs_csv_bytes, read_inputs,
                              verify_manifest)
from ml.parity.tolerance import CLASSES, FEATURE_CLASS, allowed_error

REPO_ROOT = Path(__file__).resolve().parents[3]
SETTINGS = feature_settings(REPO_ROOT)
SYN = REPO_ROOT / SYNTHETIC_ROOT
REAL_AVAILABLE = (REPO_ROOT / REAL_ROOT / "expected_features.csv").is_file()


@pytest.fixture(scope="module")
def golden():
    return compare.load_golden(REPO_ROOT, "synthetic")


@pytest.fixture(scope="module")
def golden_records():
    return readiness._golden_records(REPO_ROOT, "synthetic")


def _value(expected: pd.DataFrame, case: str, feature: str, endpoint: int | None = None):
    sub = expected.loc[(expected.case_id == case) & (expected.feature_name == feature)]
    row = sub.loc[sub.endpoint_index == (endpoint if endpoint is not None else sub.endpoint_index.max())].iloc[0]
    return row.status, row.value, row.reason_code


# ----------------------------------------------------------------------------- contract


def test_feature_count_and_exact_order_match_all_sources():
    from ml.train.rf_poc import FEATURE_ORDER as RF_ORDER
    contract = json.loads((REPO_ROOT / CONTRACT_V02).read_text(encoding="utf-8"))
    assert len(FEATURE_ORDER) == 23
    assert list(FEATURE_ORDER) == list(EXPECTED_SELECTION) == list(RF_ORDER)
    assert [f["name"] for f in contract["features"]] == list(FEATURE_ORDER)
    assert [f["index"] for f in contract["features"]] == list(range(23))
    assert contract["schema_sha256"] == schema_sha256()
    validation = validate_contract(REPO_ROOT)
    assert not validation["blocking_inconsistency"]
    assert all(validation["order_checks"].values())
    assert validation["model_card_schema_matches"] in (True, None)


def test_contract_units_windows_and_conventions():
    contract = json.loads((REPO_ROOT / CONTRACT_V02).read_text(encoding="utf-8"))
    assert contract["sampling_hz"] == 10.0 and contract["update_stride_seconds"] == 10.0
    assert contract["units"] == {"roll_deg": "degree", "pitch_deg": "degree", "time_seconds": "second"}
    units = {f["name"]: f["unit"] for f in contract["features"]}
    assert units["roll_diff_rms_60"].startswith("deg/sample")
    assert units["roll_rms_slope_180"] == units["roll_p95_trend_slope_180"] == "deg/min"
    assert {units[n] for n in ("roll_rms_ratio_180", "roll_rms_trend_r2_180", "roll_dominant_sign_ratio_180")} == {"1"}
    windows = {f["name"]: f["window_seconds"] for f in contract["features"]}
    assert all(windows[n] == 60 for n in FEATURE_ORDER[:8] + FEATURE_ORDER[20:])
    assert all(windows[n] == 180 for n in FEATURE_ORDER[8:20])
    assert contract["status_vocabulary"] == list(STATUS_VOCABULARY)
    assert SETTINGS["quantile_method"] == "type7" and SETTINGS["endpoint_convention"] == "(t-W,t]"


def test_open_contract_issues_are_documented_not_silently_resolved():
    validation = validate_contract(REPO_ROOT)
    ids = {i["id"]: i for i in validation["issues"]}
    assert {"C01", "C02", "C03", "C04"} <= {k for k, v in ids.items() if v["status"].startswith("OPEN")}
    assert all(validation["behaviour_checks"][i]["passed"] for i in range(len(validation["behaviour_checks"])))


# ----------------------------------------------------------------------------- Level 1: golden đúng


def test_independent_analytic_checks_all_pass():
    manifest = json.loads((REPO_ROOT / MANIFEST).read_text(encoding="utf-8"))
    assert manifest["analytic_checks"]["total"] >= 100
    assert manifest["analytic_checks"]["failed"] == []


def test_population_std_and_unit_detection(golden):
    expected, _ = golden
    status, value, _ = _value(expected, "SYN04_sine_roll", "roll_std_60")
    assert status == "VALID" and value == pytest.approx(5.0 / math.sqrt(2), abs=1e-5)
    sample_std = value * math.sqrt(600 / 599)
    assert abs(sample_std - value) > allowed_error("roll_std_60", value, 5.0)
    status, value, _ = _value(expected, "SYN25_large_amplitude_units", "roll_abs_max_60")
    assert 19.9 < value <= 20.0  # độ, không phải radian (0.349)
    assert abs(math.radians(value) - value) > allowed_error("roll_abs_max_60", value, value)


def test_window_boundaries_half_open(golden):
    expected, cases = golden
    # Gai +10° tại k=1500 (t=150): thuộc (140, 200] nhưng KHÔNG thuộc (150, 210].
    assert _value(expected, "SYN12_spike_window_boundaries", "roll_abs_max_60", 2000)[1] == pytest.approx(10.0)
    assert _value(expected, "SYN12_spike_window_boundaries", "roll_abs_max_60", 2100)[1] < 1.0
    for ep in cases["SYN04_sine_roll"]["endpoints"]:
        k = ep["endpoint_index"]
        assert ep["windows"]["roll_pitch_60s"] == [k - 599, k]
        if k >= 1800:
            assert ep["windows"]["roll_180s"] == [k - 1799, k]
            assert ep["windows"]["blocks_60s"] == [[k - 1799, k - 1200], [k - 1199, k - 600], [k - 599, k]]


def test_insufficient_history_is_warmup_not_zero(golden):
    expected, _ = golden
    sub = expected.loc[expected.case_id == "SYN20_insufficient_history"]
    long = sub.loc[sub.feature_index.between(8, 19)]
    assert set(long.status) == {"INSUFFICIENT_WINDOW"} and set(long.reason_code) == {"WINDOW_HISTORY_SHORT"}
    assert long.value.isna().all()
    every_case = expected.loc[expected.endpoint_index < 1800]
    assert set(every_case.loc[every_case.feature_index.between(8, 19), "status"]) <= {"INSUFFICIENT_WINDOW", "INVALID_INPUT"}


def test_constant_and_zero_signals(golden):
    expected, _ = golden
    for feature in ("roll_rms_ratio_180", "roll_rms_trend_r2_180", "roll_dominant_sign_ratio_180"):
        status, value, _ = _value(expected, "SYN01_const_zero", feature)
        assert status == "UNDEFINED_MATHEMATICALLY" and value is None
    assert _value(expected, "SYN01_const_zero", "roll_rms_60")[:2] == ("VALID", 0.0)
    assert _value(expected, "SYN02_const_roll_pos", "roll_std_60")[:2] == ("VALID", 0.0)
    assert _value(expected, "SYN02_const_roll_pos", "roll_rms_ratio_180")[:2] == ("VALID", 1.0)
    assert _value(expected, "SYN03_const_roll_neg_pitch_pos", "roll_mean_60")[1] == -2.5
    assert _value(expected, "SYN03_const_roll_neg_pitch_pos", "roll_mean_abs_180")[1] == 2.5
    # R² = 0 hợp lệ (khác UNDEFINED)
    status, value, _ = _value(expected, "SYN29_block_step_symmetric", "roll_rms_trend_r2_180")
    assert status == "VALID" and value == pytest.approx(0.0, abs=1e-9)


def test_missing_samples_and_gaps(golden):
    expected, _ = golden
    assert _value(expected, "SYN21_isolated_nan", "roll_rms_60")[0] == "VALID"
    assert _value(expected, "SYN21_isolated_nan", "roll_diff_rms_60")[::2] == ("INVALID_INPUT", "ADJACENT_PAIR_COVERAGE")
    assert _value(expected, "SYN22_nan_excess", "roll_rms_60")[::2] == ("INVALID_INPUT", "SIGNAL_VALID_COVERAGE")
    assert _value(expected, "SYN22_nan_excess", "pitch_rms_60")[0] == "VALID"
    for case in ("SYN23_timestamp_gap", "SYN24_single_dropped_sample"):
        assert _value(expected, case, "roll_rms_60")[::2] == ("INVALID_INPUT", "TIMESTAMP_GAP")
    # C01: block đầu thiếu mẫu làm rms_late INVALID dù roll_rms_60 VALID
    assert _value(expected, "SYN27_block_coverage_rule", "roll_rms_60")[0] == "VALID"
    assert _value(expected, "SYN27_block_coverage_rule", "roll_rms_late_60")[::2] == ("INVALID_INPUT", "SEGMENT_BLOCK_COVERAGE")
    assert _value(expected, "SYN26_infinite_values", "roll_rms_60")[0] == "VALID"
    invalid = expected.loc[expected.status != "VALID"]
    assert invalid.value.isna().all(), "Feature không VALID phải có giá trị rỗng, không phải 0"


def test_quantile_convention_type7(golden):
    x = np.array([1.0, 2.0, 4.0, 8.0, 16.0])
    for p in (0.0, 0.25, 0.5, 0.95, 1.0):
        assert type7_quantile(x, p) == pytest.approx(np.quantile(x, p, method="linear"))
    assert type7_quantile(x, 0.95) != pytest.approx(np.quantile(x, 0.95, method="weibull"))
    expected, _ = golden
    p95 = _value(expected, "SYN13_ramp_quantiles", "roll_abs_p95_60")[1]
    lo = 0.5 + 1501 / 256
    assert p95 == pytest.approx(lo + 0.95 * 599 / 256, abs=1e-9)
    nearest = lo + (math.ceil(0.95 * 600) - 1) / 256
    assert abs(nearest - p95) > allowed_error("roll_abs_p95_60", p95, lo + 599 / 256)


# ----------------------------------------------------------------------------- float32 / dung sai


def test_float32_inputs_round_trip_exactly(tmp_path):
    frame = synthetic_signal(SYNTHETIC_CASES[5])
    path = tmp_path / "in.csv"
    path.write_bytes(inputs_csv_bytes(frame))
    back = read_inputs(path)
    np.testing.assert_array_equal(back.roll_deg.to_numpy(), frame.roll_deg.to_numpy())
    assert all(float(np.float32(float(fmt32(v)))) == float(np.float32(v)) for v in back.roll_deg[:50])
    lines = path.read_text().splitlines()
    parts = lines[4].split(",")
    parts[2] = repr(float(parts[2]) + 1e-12)  # không còn là chuỗi float32 chính tắc
    lines[4] = ",".join(parts)
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError):
        read_inputs(path)


def test_tolerance_scales_with_input_not_only_output():
    assert set(FEATURE_CLASS) == set(FEATURE_ORDER) and set(FEATURE_CLASS.values()) <= set(CLASSES)
    # std nhỏ của tín hiệu offset lớn: dung sai theo biên độ đầu vào, không theo giá trị std
    assert allowed_error("roll_std_60", 0.007, 10.0) > 50 * allowed_error("roll_std_60", 0.007, 0.01)
    assert allowed_error("roll_rms_trend_r2_180", 0.5, 1.0) == CLASSES["r_squared"]["abs_floor"]
    assert allowed_error("roll_abs_max_60", 1.0, 1.0) < 1e-6


def test_float32_emulation_passes_and_flags_c03(golden):
    expected, cases = golden
    result = compare.compare_frames(expected, interchange.from_records(float32_probe.emulate_suite(REPO_ROOT, SYNTHETIC_ROOT)),
                                    cases, float32_probe.emulation_metadata(None))
    s = result["summary"]
    assert s["fail_records"] == 0 and not s["is_c_parity_evidence"]
    assert s["verdict"].startswith("FLOAT32_EMULATION_")
    reviews = result["rows"].loc[result["rows"].outcome.eq("REVIEW_ILL_CONDITIONED")]
    assert set(reviews.feature_name) <= {"roll_rms_trend_r2_180", "roll_rms_ratio_180"}
    assert "SYN30_permuted_blocks" in set(reviews.case_id)
    assert max(f["max_error_ratio"] or 0 for f in s["per_feature"]) < 0.5


@pytest.mark.parametrize("mutation", sorted(float32_probe.MUTATIONS))
def test_deliberately_corrupted_c_like_results_are_rejected(golden, mutation):
    expected, cases = golden
    records = float32_probe.emulate_suite(REPO_ROOT, SYNTHETIC_ROOT, mutation)
    result = compare.compare_frames(expected, interchange.from_records(records), cases, float32_probe.emulation_metadata(mutation))
    assert result["summary"]["verdict"] == "FLOAT32_EMULATION_FAIL", mutation


# ----------------------------------------------------------------------------- harness / interchange


def test_csv_and_jsonl_round_trip(tmp_path, golden_records):
    records = golden_records[:23 * 6]
    interchange.write_csv(records, tmp_path / "out.csv")
    interchange.write_jsonl(records, tmp_path / "out.jsonl")
    a, b = interchange.read_csv(tmp_path / "out.csv"), interchange.read_jsonl(tmp_path / "out.jsonl")
    cols = ["case_id", "endpoint_index", "feature_index", "feature_name", "status", "input_sha256"]
    pd.testing.assert_frame_equal(a[cols].reset_index(drop=True), b[cols].reset_index(drop=True))
    for x, y in zip(a.value, b.value):
        assert (x is None and y is None) or x == y
    assert any(v is None for v in a.value) and not any(isinstance(v, float) and math.isnan(v) for v in a.value)


def test_self_consistency_is_labelled_not_c_parity(golden, golden_records):
    expected, cases = golden
    result = compare.compare_frames(expected, interchange.from_records(golden_records), cases,
                                    {"producer": {"kind": "python_reference_self_consistency"}})
    assert result["summary"]["verdict"] == "PYTHON_SELF_CONSISTENCY_PASS"
    assert not result["summary"]["is_c_parity_evidence"]
    unattributed = compare.compare_frames(expected, interchange.from_records(golden_records), cases, None)
    assert unattributed["summary"]["verdict"].startswith("UNATTRIBUTED_")


def test_duplicate_missing_extra_and_corruption_detection(golden, golden_records):
    expected, cases = golden
    for name, (records, outcome) in readiness.corruption_scenarios(golden_records, expected).items():
        s = compare.compare_frames(expected, interchange.from_records(records), cases,
                                   {"producer": {"kind": "independent_c_implementation"}})["summary"]
        if outcome == "PASS":
            assert s["verdict"] == "C_PARITY_PASS", name
        else:
            assert s["verdict"] == "C_PARITY_FAIL" and s["outcome_counts"].get(outcome, 0) > 0, name


def test_validity_status_comparison(golden, golden_records):
    expected, cases = golden
    recs = [dict(r) for r in golden_records]
    target = next(r for r in recs if r["status"] == "UNDEFINED_MATHEMATICALLY" and r["case_id"] == "SYN01_const_zero")
    target.update(status="VALID", value=0.0)  # thay "không xác định" bằng 0 hợp lệ
    s = compare.compare_frames(expected, interchange.from_records(recs), cases, None)["summary"]
    assert s["fail_records"] >= 1 and s["outcome_counts"].get("FAIL_STATUS_MISMATCH", 0) >= 1


def test_cli_comparison_writes_reports(tmp_path, golden_records):
    path = tmp_path / "cand.csv"
    interchange.write_csv(golden_records, path)
    meta = interchange.metadata_template()
    meta["producer"]["kind"] = "python_reference_self_consistency"
    meta["golden_manifest_sha256"] = hashlib.sha256((REPO_ROOT / MANIFEST).read_bytes()).hexdigest()
    (tmp_path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    result = compare.run_comparison(REPO_ROOT, "synthetic", path, tmp_path / "meta.json", tmp_path / "out")
    assert result["summary"]["fail_records"] == 0
    assert {p.name for p in (tmp_path / "out").iterdir()} == {"comparison_rows.csv", "comparison_summary.json", "comparison_report.md"}
    assert result["metadata_warnings"] == []


# ----------------------------------------------------------------------------- manifest / tất định / ledger


def test_manifest_checksums_verify_and_detect_tampering(tmp_path):
    report = verify_manifest(REPO_ROOT, include_untracked=REAL_AVAILABLE)
    assert report["passed"], report["problems"]
    manifest = json.loads((REPO_ROOT / MANIFEST).read_text(encoding="utf-8"))
    tracked = [p for p, e in manifest["files"].items() if e["tracked_in_git"]]
    assert all(not p.startswith("ml/data/") for p in tracked)
    copy_root = tmp_path / "repo"
    for rel in [MANIFEST.as_posix(), *tracked]:
        (copy_root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / rel, copy_root / rel)
    target = copy_root / "ml/parity/fixtures/synthetic/expected_features.csv"
    target.write_bytes(target.read_bytes().replace(b"VALID", b"VALiD", 1))
    problems = verify_manifest(copy_root, include_untracked=False)["problems"]
    assert {"path": "ml/parity/fixtures/synthetic/expected_features.csv", "problem": "SHA256_MISMATCH"} in problems


def test_deterministic_generation_matches_tracked_fixtures(tmp_path):
    ledger_before = protected_checksums(REPO_ROOT)
    result = build_suite(tmp_path, "synthetic", SETTINGS)
    manifest = json.loads((REPO_ROOT / MANIFEST).read_text(encoding="utf-8"))["files"]
    for rel, digest in result["files"].items():
        assert manifest[rel]["sha256"] == digest, rel
    assert protected_checksums(REPO_ROOT) == ledger_before, "Ledger human review bị thay đổi"
    assert not (tmp_path / "ml/data/labels").exists()


def test_golden_generation_never_touches_human_review_ledgers():
    sources = "".join((REPO_ROOT / "ml/parity" / f).read_text(encoding="utf-8")
                      for f in ("golden.py", "cases.py", "compare.py", "readiness.py", "interchange.py", "float32_probe.py"))
    assert "ml/data/labels" not in sources
    assert "annotation_pilot" not in sources and "review_decisions" not in sources


def test_extractor_reproduces_golden_for_stored_inputs(golden):
    expected, cases = golden
    case = cases["SYN06_mixed_order_detector"]
    inputs = read_inputs(REPO_ROOT / case["input_file"])
    values, metadata, _ = run_extractor(inputs.time_seconds, inputs.roll_deg, inputs.pitch_deg, SETTINGS)
    last = values.iloc[-1]
    sub = expected.loc[(expected.case_id == case["case_id"]) & (expected.endpoint_index == case["endpoints"][-1]["endpoint_index"])]
    for row in sub.itertuples(index=False):
        assert row.value == float(last[row.feature_name])
    named = dict(zip(sub.feature_name, sub.value))
    assert named["roll_rms_late_60"] == named["roll_rms_60"]  # C06: cùng mẫu (t-60, t]
    assert len(set(round(v, 9) for v in sub.value)) == 22, "SYN06: 22 giá trị phân biệt (rms_late = rms_60) để bắt lỗi thứ tự"


def test_analytic_module_does_not_call_extractor():
    source = (REPO_ROOT / "ml/parity/analytic.py").read_text(encoding="utf-8")
    for forbidden in ("ml.features", "extract_segment", "run_extractor", "ml.parity.golden", "ml.parity.contract"):
        assert forbidden not in source, forbidden
    assert analytic.expectations("SYN09_block_step_linear")["roll_rms_trend_r2_180"][1] == pytest.approx(1.0)


# ----------------------------------------------------------------------------- dữ liệu thật (bỏ qua nếu vắng)


@pytest.mark.skipif(not REAL_AVAILABLE, reason="Golden real-data (gitignored) chưa được sinh trên máy này")
def test_real_data_golden_matches_feature_tables_and_boundaries():
    manifest = json.loads((REPO_ROOT / MANIFEST).read_text(encoding="utf-8"))
    assert manifest["real_cross_check"]["passed"]
    expected, cases = compare.load_golden(REPO_ROOT, "real")
    assert {c["dataset_source"] for c in cases.values()} == {"hohai", "seafar", "southampton"}
    for case in cases.values():
        assert case["dropped_timestamps"] == 0 and case["n_samples"] == 2401
        processed = REPO_ROOT / case["processed_path"]
        if processed.is_file():
            n = len(pd.read_parquet(processed, columns=["time_seconds"]))
            assert 0 <= case["source_start_index"] and case["source_start_index"] + case["n_samples"] <= n
    assert set(expected.status) <= set(STATUS_VOCABULARY)


def test_parity_status_is_pending_without_real_c_results():
    report = json.loads((REPO_ROOT / readiness.REPORT_JSON).read_text(encoding="utf-8"))
    if not report["c_results_submitted"]:
        assert report["status"] == ["PYTHON_REFERENCE_READY", "C_PARITY_PENDING"]
    assert "Level 2 không chứng minh Level 3" in report["levels"]["level_3_esp32_sensor_to_model"]
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["golden_manifest_sha256"] == hashlib.sha256((REPO_ROOT / MANIFEST).read_bytes()).hexdigest()


def test_wrong_metadata_schema_version_is_rejected(tmp_path):
    candidate = REPO_ROOT / SYNTHETIC_ROOT / "golden_vectors.jsonl"
    metadata = interchange.metadata_template()
    metadata["producer"] = {"kind": "independent_c_implementation", "name": "test_fixture"}
    metadata["schema_version"] = "svmg-angle23-0.1.0-proposal"
    metadata["golden_manifest_sha256"] = hashlib.sha256((REPO_ROOT / MANIFEST).read_bytes()).hexdigest()
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    result = compare.run_comparison(REPO_ROOT, "synthetic", candidate, metadata_path)

    assert result["summary"]["verdict"] == "C_PARITY_FAIL"
    assert result["summary"]["fail_records"] > 0
    assert any("schema_version metadata" in warning for warning in result["metadata_warnings"])


def test_non_finite_endpoint_time_is_rejected(golden):
    expected, cases = golden
    records = readiness._golden_records(REPO_ROOT, "synthetic")
    records[0]["endpoint_time_seconds"] = float("nan")

    result = compare.compare_frames(expected, interchange.from_records(records), cases,
                                    {"producer": {"kind": "python_reference_self_consistency"}})

    assert result["summary"]["outcome_counts"]["FAIL_ENDPOINT_TIME"] == 1
    assert result["summary"]["fail_records"] == 1
