"""Test tích hợp runner C host (mã C M1 thật) với golden M2 và harness compare.

Cần clang trong PATH; tự bỏ qua nếu không có. Suite real tự bỏ qua nếu dữ liệu gitignored vắng mặt.
"""
from __future__ import annotations

import copy
import hashlib
import inspect
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.parity import c_host, compare, interchange
from ml.parity.contract import FEATURE_ORDER, SCHEMA_VERSION
from ml.parity.golden import MANIFEST, fmt32
from ml.parity.tolerance import allowed_error

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_AVAILABLE = (REPO_ROOT / compare.suite_root("real") / "expected_features.csv").is_file()
pytestmark = pytest.mark.skipif(shutil.which("clang") is None, reason="clang không có trong PATH")
C_META = {"producer": {"kind": "independent_c_implementation"}}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    return c_host.build(REPO_ROOT, tmp_path_factory.mktemp("c_host_build"))


@pytest.fixture(scope="module")
def golden():
    return compare.load_golden(REPO_ROOT, "synthetic")


@pytest.fixture(scope="module")
def exported(built):
    return c_host.export_suite(REPO_ROOT, "synthetic", built["binary"])


@pytest.fixture(scope="module")
def synthetic_result(golden, exported):
    expected, cases = golden
    return compare.compare_frames(expected, interchange.from_records(exported["records"]), cases, C_META)


def _write_input(path: Path, roll, pitch, times=None) -> Path:
    n = len(roll)
    times = np.arange(n) / 10.0 if times is None else times
    lines = ["sample_index,time_seconds,roll_deg,pitch_deg,source_sample_index"]
    lines += [f"{i},{float(t)!r},{fmt32(r)},{fmt32(p)},{i}" for i, (t, r, p) in enumerate(zip(times, roll, pitch))]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


# ----------------------------------------------------------------------------- contract / metadata


def test_c_coverage_thresholds_used_by_adapter_match_features_c():
    source = (REPO_ROOT / "core/src/features.c").read_text(encoding="utf-8")
    for pattern in (r"r\.n >= 570", r"p\.n >= 570", r"l\.n >= 1710", r"b\[j\]\.n >= 570", r"pairs >= 570"):
        assert re.search(pattern, source), pattern
    assert (c_host.C_MIN_SHORT, c_host.C_MIN_LONG, c_host.C_MIN_BLOCK, c_host.C_MIN_PAIRS) == (570, 1710, 570, 570)


def test_feature_ordering_and_schema_mapping_come_from_compiled_binary(built):
    info = c_host.binary_info(built["binary"])
    assert info["feature_names"] == list(FEATURE_ORDER) and info["n_features"] == 23
    assert info["c_feature_schema_version"] == "svmg-angle-23-v1"  # không bị đổi tên
    mapping = c_host.check_schema_mapping(REPO_ROOT, info)
    assert mapping["compatible"] and mapping["evaluated_against"] == SCHEMA_VERSION
    assert mapping["c_native_schema_version"] != mapping["evaluated_against"]


def test_schema_mapping_refuses_reordered_binary_names(built):
    info = c_host.binary_info(built["binary"])
    info["feature_names"] = info["feature_names"][1:] + info["feature_names"][:1]
    assert not c_host.check_schema_mapping(REPO_ROOT, info)["compatible"]


def test_metadata_records_real_compiler_flags_commit_and_sources(built):
    info = c_host.binary_info(built["binary"])
    meta = c_host.build_metadata(REPO_ROOT, built, info, c_host.check_schema_mapping(REPO_ROOT, info), "test")
    p = meta["producer"]
    assert p["kind"] == "independent_c_implementation" and p["target"] == "host"
    assert p["compiler"].lower().startswith(("apple clang", "clang", "homebrew clang"))
    assert p["compiler_flags"] == " ".join(c_host.DEFAULT_CFLAGS)
    assert re.fullmatch(r"[0-9a-f]{40}", p["source_commit"])
    assert p["source_sha256"]["core/src/features.c"] == hashlib.sha256((REPO_ROOT / "core/src/features.c").read_bytes()).hexdigest()
    assert meta["golden_manifest_sha256"] == hashlib.sha256((REPO_ROOT / MANIFEST).read_bytes()).hexdigest()
    assert meta["schema_version"] == SCHEMA_VERSION and p["c_feature_schema_version"] == "svmg-angle-23-v1"
    assert compare.validate_metadata(meta, REPO_ROOT) == []


# ----------------------------------------------------------------------------- input / endpoint


def test_input_sha256_and_endpoint_alignment(exported, golden):
    expected, cases = golden
    frame = pd.DataFrame(exported["records"])
    for case_id, case in cases.items():
        sub = frame.loc[frame.case_id.eq(case_id)]
        assert set(sub.input_sha256) == {case["input_sha256"]}
        times = c_host.read_input_times(REPO_ROOT / case["input_file"])
        assert np.array_equal(sub.endpoint_time_seconds.to_numpy(), times[sub.endpoint_index.to_numpy()])
    key = ["case_id", "endpoint_index", "feature_index"]
    assert set(map(tuple, frame[key].to_numpy().tolist())) == set(map(tuple, expected[key].to_numpy().tolist()))
    assert len(frame) == len(expected)
    assert (frame.feature_name == [FEATURE_ORDER[i] for i in frame.feature_index]).all()


def test_float32_input_round_trip_is_exact_in_c(built, tmp_path):
    rng = np.random.default_rng(7)
    roll = (rng.normal(size=700) * 3.7).astype(np.float32)
    pitch = (rng.normal(size=700) * 1.3).astype(np.float32)
    raw = c_host.run_case(built["binary"], _write_input(tmp_path / "in.csv", roll, pitch), [699]).iloc[0]
    window_roll, window_pitch = roll[100:700], pitch[100:700]
    # abs_max/peak-to-peak chỉ chọn mẫu: bằng đúng float32 đầu vào khi strtof đọc chính xác.
    assert np.float32(raw.v05) == np.max(np.abs(window_roll))
    assert np.float32(raw.v22) == np.float32(np.float64(window_pitch.max()) - np.float64(window_pitch.min()))
    assert raw.from_series_match == 1


def test_non_finite_samples_with_timestamp_are_excluded_by_c(built, tmp_path):
    roll = np.sin(np.arange(700) / 5.0).astype(np.float32)
    roll[650], roll[660], roll[670] = np.nan, np.inf, -np.inf
    raw = c_host.run_case(built["binary"], _write_input(tmp_path / "nan.csv", roll, roll.copy()), [699]).iloc[0]
    assert raw.roll_finite_60 == 597 and raw.ready_short == 1
    assert c_host.derive_status(raw.to_dict(), 0)[0] == "VALID"


# ----------------------------------------------------------------------------- validity / NOT_EVALUABLE


def test_missing_timestamps_are_not_evaluable_never_pass(exported, synthetic_result):
    frame = pd.DataFrame(exported["records"])
    ne = frame.loc[frame.status.eq(c_host.NOT_EVALUABLE)]
    assert set(ne.case_id) == {"SYN23_timestamp_gap", "SYN24_single_dropped_sample"}
    assert ne.value.isna().all() and set(ne.reason_code) == {c_host.NE_NO_TIMESTAMP}
    rows = synthetic_result["rows"].set_index(["case_id", "endpoint_index", "feature_index"])
    ne_keys = list(ne.set_index(["case_id", "endpoint_index", "feature_index"]).index)
    assert (rows.loc[ne_keys].outcome == "NOT_EVALUABLE").all()  # không bản ghi nào thành PASS
    s = synthetic_result["summary"]
    assert s["not_evaluable_records"] == len(ne) and s["verdict"] == "C_PARITY_PARTIAL"


def test_representability_uses_only_input_timestamps():
    t = np.arange(2101) / 10.0
    assert c_host.representability(t, 2100) == {"60": None, "180": None}
    gap = np.delete(t, 1300)  # gap giữa hàng 1299/1300: ngoài 600 hàng cuối, trong 1800 hàng cuối
    assert c_host.representability(gap, 2099) == {"60": None, "180": c_host.NE_NO_TIMESTAMP}
    for name in ("export_suite", "derive_status", "representability"):
        assert "expected" not in inspect.getsource(getattr(c_host, name)), name


def test_status_adapter_uses_c_state_not_python_expectation():
    base = {f"v{i:02d}": float("nan") for i in range(23)}
    base.update(valid_mask=0, ready_short=0, ready_long=0, roll_finite_60=0, pitch_finite_60=0, roll_pairs_60=0,
                roll_finite_180=0, block0_finite=-1, block1_finite=-1, block2_finite=-1)
    assert c_host.derive_status(base, 0)[:2] == ("INSUFFICIENT_WINDOW", "WINDOW_HISTORY_SHORT")
    ready = {**base, "ready_short": 1, "ready_long": 1, "roll_finite_60": 600, "pitch_finite_60": 600,
             "roll_pairs_60": 560, "roll_finite_180": 1800, "block0_finite": 569, "block1_finite": 600, "block2_finite": 600}
    assert c_host.derive_status(ready, 7)[:2] == ("INVALID_INPUT", "ADJACENT_PAIR_COVERAGE")
    assert c_host.derive_status(ready, 14)[:2] == ("INVALID_INPUT", "SEGMENT_BLOCK_COVERAGE")
    assert c_host.derive_status(ready, 9)[:2] == ("UNDEFINED_MATHEMATICALLY", "NON_FINITE_RESULT")
    valid = {**ready, "valid_mask": 1, "v00": 1.5}
    assert c_host.derive_status(valid, 0) == ("VALID", "", 1.5)
    broken = {**ready, "v01": 2.0}  # mask 0 nhưng C có số: phải bị harness bắt
    assert c_host.derive_status(broken, 1)[2] == 2.0


def test_missing_feature_validity_is_rejected(exported, golden, tmp_path):
    expected, cases = golden
    frame = pd.DataFrame(exported["records"]).drop(columns=["status"])
    path = tmp_path / "no_status.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(interchange.InterchangeError):
        interchange.read_csv(path)
    records = copy.deepcopy(exported["records"])
    records[0]["status"] = ""
    ne_idx = next(i for i, r in enumerate(records) if r["status"] == c_host.NOT_EVALUABLE)
    records[ne_idx]["reason_code"] = ""
    counts = compare.compare_frames(expected, interchange.from_records(records), cases, C_META)["summary"]["outcome_counts"]
    assert counts["FAIL_UNKNOWN_STATUS"] == 2


def test_incorrect_candidates_are_rejected(exported, golden):
    expected, cases = golden
    records = exported["records"]
    valid_idx = next(i for i, r in enumerate(records) if r["status"] == "VALID" and r["case_id"].startswith("SYN04"))
    exp = expected.loc[(expected.case_id == records[valid_idx]["case_id"])
                       & (expected.endpoint_index == records[valid_idx]["endpoint_index"])
                       & (expected.feature_index == records[valid_idx]["feature_index"])].iloc[0]
    allowed = allowed_error(exp.feature_name, exp.value, exp.tolerance_scale)

    def outcome(mutate):
        recs = copy.deepcopy(records)
        mutate(recs)
        return compare.compare_frames(expected, interchange.from_records(recs), cases, C_META)["summary"]

    s = outcome(lambda rs: rs[valid_idx].update(value=rs[valid_idx]["value"] + 10 * allowed))
    assert s["outcome_counts"]["FAIL_VALUE_TOLERANCE"] == 1 and s["verdict"] == "C_PARITY_FAIL"
    s = outcome(lambda rs: rs[valid_idx].update(status="INVALID_INPUT", value=None))
    assert s["outcome_counts"]["FAIL_STATUS_MISMATCH"] == 1
    s = outcome(lambda rs: [r.update(feature_name=FEATURE_ORDER[(r["feature_index"] + 1) % 23]) for r in rs[:23]])
    assert s["outcome_counts"]["FAIL_FEATURE_NAME_ORDER"] == 23
    s = outcome(lambda rs: [r.update(input_sha256="0" * 64) for r in rs if r["case_id"] == rs[0]["case_id"]])
    assert s["outcome_counts"]["FAIL_INPUT_SHA256"] > 0
    s = outcome(lambda rs: rs.__setitem__(slice(0, 23), []))
    assert s["outcome_counts"]["MISSING"] == 23


def test_mutated_c_formula_is_detected(golden, tmp_path):
    """Kiểm tra pipeline có thể FAIL: std mẫu (n-1) cài vào BẢN SAO features.c trong thư mục tạm."""
    source = (REPO_ROOT / "core/src/features.c").read_text(encoding="utf-8")
    assert "s.sd = sqrt(var / s.n);" in source
    mutated = tmp_path / "features_mutated.c"
    mutated.write_text(source.replace("s.sd = sqrt(var / s.n);", "s.sd = sqrt(var / (s.n - 1));"), encoding="utf-8")
    info = c_host.build(REPO_ROOT, tmp_path / "build", feature_sources=(mutated,))
    expected, cases = golden
    records = c_host.export_suite(REPO_ROOT, "synthetic", info["binary"])["records"]
    rows = compare.compare_frames(expected, interchange.from_records(records), cases, C_META)["rows"]
    failed = set(rows.loc[rows.outcome.eq("FAIL_VALUE_TOLERANCE")].feature_name)
    assert {"roll_std_60", "pitch_std_60"} <= failed


# ----------------------------------------------------------------------------- kết quả và tái lập


def test_synthetic_c_parity_has_no_fail_and_no_validity_mismatch(synthetic_result, exported):
    analysis = c_host.analyse(synthetic_result)
    assert analysis["fail"] == 0 and analysis["validity_mismatches"] == 0 and analysis["status_mismatches"] == 0
    assert analysis["not_evaluable"] == 46 and analysis["review"] == 0
    assert analysis["max_error_ratio"] < 1.0
    assert (exported["raw"].from_series_match == 1).all()


def test_c_export_is_reproducible(built, exported, tmp_path):
    again = c_host.export_suite(REPO_ROOT, "synthetic", built["binary"])
    assert interchange.write_csv(again["records"], None) == interchange.write_csv(exported["records"], None)
    other = c_host.build(REPO_ROOT, tmp_path / "o0", cflags=("-std=c99", "-O0"))
    third = c_host.export_suite(REPO_ROOT, "synthetic", other["binary"])
    assert interchange.write_csv(third["records"], None) == interchange.write_csv(exported["records"], None)


def test_gridfill_diagnostic_documents_c04_divergence(built, golden):
    expected, _ = golden
    diag = c_host.gridfill_diagnostic(REPO_ROOT, "synthetic", built["binary"], expected)
    assert {d["case_id"] for d in diag} == {"SYN23_timestamp_gap", "SYN24_single_dropped_sample"}
    assert all(d["python_reason"] == "TIMESTAMP_GAP" and d["c_gridfill_status"] == "VALID" for d in diag)


@pytest.mark.skipif(not REAL_AVAILABLE, reason="Golden real-data (gitignored) vắng mặt")
def test_real_suite_c_parity(built):
    expected, cases = compare.load_golden(REPO_ROOT, "real")
    records = c_host.export_suite(REPO_ROOT, "real", built["binary"])["records"]
    result = compare.compare_frames(expected, interchange.from_records(records), cases, C_META)
    analysis = c_host.analyse(result)
    assert analysis["fail"] == 0 and analysis["not_evaluable"] == 0 and analysis["validity_mismatches"] == 0
    assert result["summary"]["verdict"] == "C_PARITY_PASS"
