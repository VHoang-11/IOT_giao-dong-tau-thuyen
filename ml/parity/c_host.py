"""Tích hợp host: chạy mã C THẬT của M1 (core/src/features.c) trên golden M2 và so bằng ml.parity.compare.

Chạy từ repository root::

    .venv/bin/python -m ml.parity.c_host --suite all --run-id m1v1_host_clang

Luồng:
1. Biên dịch ``ml/parity/c_host/feature23_host_runner.c`` + ``core/src/features.c`` (không sửa) bằng Apple Clang.
2. Runner C đọc input golden (roll/pitch bằng ``strtof`` -> float32), đẩy từng mẫu qua ``svmg_window_push`` như
   firmware, gọi ``svmg_features_compute`` tại đúng ``endpoint_index`` golden, đối chiếu bitwise với
   ``svmg_features_from_series``. Mọi giá trị số đến từ C; Python chỉ định dạng lại.
3. Validity (VALID hay không) lấy từ ``valid_mask`` của C. C KHÔNG xuất status/reason: status không-VALID được
   phân loại bởi adapter host (``STATUS_ADAPTER``) chỉ từ trạng thái cửa sổ C (ready flag, số mẫu hữu hạn trong
   ring buffer C) — không bao giờ đọc status Python kỳ vọng.
4. C API không có timestamp (lưới 10 Hz cố định, warm-up theo số mẫu). Nhóm feature có cửa sổ chứa nhịp
   thời gian khác 0,1 s được khai báo ``NOT_EVALUABLE`` (không phải PASS).
5. Ghi candidate + metadata vào ``ml/data/parity/c_host/<run_id>/`` (gitignored) và chạy ``compare``.

Kết quả chỉ là HOST_C_FEATURE_PARITY (Level 2 trên host). Không chứng minh tương thích chuỗi cảm biến ESP32
(Level 3) hay tích hợp mô hình Random Forest.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import platform
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from ml.parity import compare, interchange
from ml.parity.contract import FEATURE_ORDER, SCHEMA_VERSION
from ml.parity.golden import MANIFEST

RUNNER_SOURCE = Path("ml/parity/c_host/feature23_host_runner.c")
C_SOURCES = ("core/src/features.c",)
C_HEADERS = ("core/include/svmg_features.h", "core/include/svmg_feature_schema.h", "core/include/svmg_common.h")
M1_CONTRACT = Path("contracts/features23.json")
OUT_ROOT = Path("ml/data/parity/c_host")
RUN_ROOT = Path("ml/data/parity/runs")
DEFAULT_CFLAGS = ("-std=c99", "-O2", "-ffp-contract=off", "-Wall", "-Wextra")
SENSITIVITY_CFLAGS = ("-std=c99", "-O2", "-ffp-contract=fast", "-Wall", "-Wextra")
C_NATIVE_SCHEMA = "svmg-angle-23-v1"
NOMINAL_DT_S = 0.1
GRID_TOLERANCE_S = 1e-6  # trùng dung sai cặp kề nhau của diff_rms trong extractor
NOT_EVALUABLE = compare.NOT_EVALUABLE_STATUS
NE_NO_TIMESTAMP = "C_API_NO_TIMESTAMP_INPUT"

# Ngưỡng coverage là literal trong core/src/features.c (test kiểm tra không trôi).
C_MIN_SHORT, C_MIN_LONG, C_MIN_BLOCK, C_MIN_PAIRS = 570, 1710, 570, 570
ROLL_60 = range(0, 8)
POINTWISE_180 = range(8, 12)
BLOCK_180 = range(12, 20)
PITCH_60 = range(20, 23)
RAW_INT_COLUMNS = ("endpoint_index", "stream_total", "ready_short", "ready_long", "valid_mask", "n_valid_60",
                   "n_valid_180", "roll_finite_60", "pitch_finite_60", "roll_pairs_60", "roll_finite_180",
                   "block0_finite", "block1_finite", "block2_finite", "placeholders_pushed", "from_series_status",
                   "from_series_match")
VALUE_COLUMNS = tuple(f"v{i:02d}" for i in range(23))

STATUS_ADAPTER = {
    "name": "c_state_status_adapter_v1",
    "validity_source": "svmg_features_t.valid_mask của C (bit i = feature i VALID)",
    "status_source": "adapter host; C chỉ xuất NaN + valid_mask, không có status/reason",
    "inputs": ["ready_short", "ready_long", "số mẫu roll/pitch hữu hạn trong 600/1800 slot mới nhất của ring C",
               "số cặp roll kề nhau hữu hạn", "số mẫu hữu hạn trong 3 block 600 slot"],
    "rules": [
        "bit valid_mask = 1 -> VALID, value = giá trị float32 C",
        "feature 60 s (0-7, 20-22): ready_short = 0 -> INSUFFICIENT_WINDOW/WINDOW_HISTORY_SHORT",
        "feature 180 s (8-19): ready_long = 0 -> INSUFFICIENT_WINDOW/WINDOW_HISTORY_SHORT",
        "số mẫu hữu hạn < 570 (60 s) hoặc < 1710 (180 s) -> INVALID_INPUT/SIGNAL_VALID_COVERAGE",
        "roll_diff_rms_60: số cặp < 570 -> INVALID_INPUT/ADJACENT_PAIR_COVERAGE",
        "feature block (12-19): block bất kỳ < 570 -> INVALID_INPUT/SEGMENT_BLOCK_COVERAGE",
        "còn lại: roll_rms_ratio_180 -> UNDEFINED_MATHEMATICALLY/EARLY_RMS_AT_OR_BELOW_EPSILON; "
        "roll_rms_trend_r2_180 -> UNDEFINED_MATHEMATICALLY/CONSTANT_RMS_TREND; khác -> UNDEFINED_MATHEMATICALLY/NON_FINITE_RESULT",
        "bit valid_mask = 0 nhưng giá trị C hữu hạn -> giữ giá trị để harness báo FAIL_INVALID_HAS_VALUE",
    ],
}
NOT_EVALUABLE_POLICY = {
    "status": NOT_EVALUABLE,
    "reason_code": NE_NO_TIMESTAMP,
    "rule": ("Nhóm feature 60 s (hoặc 180 s) tại endpoint e là NOT_EVALUABLE khi trong các hàng input "
             "[max(0, e-599), e] (hoặc [max(0, e-1799), e]) có hai timestamp kề nhau lệch |Δt-0,1| > 1e-6 s."),
    "why": ("svmg_window_push/svmg_features_from_series không nhận timestamp: cửa sổ C là N mẫu cuối và warm-up "
            "đếm mẫu, nên timestamp bị bỏ hoặc nhịp lệch làm cửa sổ C khác cửa sổ thời gian (t-W, t] của contract."),
    "derived_from": "chỉ cột time_seconds của file input golden; không dùng status/giá trị kỳ vọng",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def feature_group(index: int) -> str:
    return "60" if index in ROLL_60 or index in PITCH_60 else "180"


# ----------------------------------------------------------------------------- build / provenance


def _git(repo_root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def source_provenance(repo_root: Path) -> dict:
    paths = (*C_SOURCES, *C_HEADERS, RUNNER_SOURCE.as_posix())
    dirty = _git(repo_root, "status", "--porcelain", "--", *paths)
    return {"source_commit": _git(repo_root, "rev-parse", "HEAD") or "unknown",
            "source_branch": _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD") or "unknown",
            "c_sources_uncommitted_changes": [line[3:] for line in dirty.splitlines()],
            "m1_core_sources_modified": any(line[3:].startswith("core/") for line in dirty.splitlines()),
            "source_sha256": {p: sha256_file(repo_root / p) for p in paths}}


def build(repo_root: Path, build_dir: Path, cflags=DEFAULT_CFLAGS, compiler: str | None = None,
          feature_sources: tuple[Path, ...] | None = None) -> dict:
    """Biên dịch runner + features.c. Trả thông tin trình biên dịch thật (đọc từ ``--version``).

    ``feature_sources`` chỉ dùng cho test đột biến (bản sao features.c bị sửa trong thư mục tạm); mặc định là
    nguồn M1 không sửa trong ``core/src``.
    """
    repo_root = Path(repo_root)
    sources = [str(p) for p in feature_sources] if feature_sources else [str(repo_root / s) for s in C_SOURCES]
    cc = compiler or shutil.which("clang")
    if not cc:
        raise RuntimeError("Không tìm thấy clang trong PATH.")
    build_dir = Path(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    binary = build_dir / "feature23_host_runner"
    rel_cmd = [Path(cc).name, *cflags, "-I", "core/include", *C_SOURCES, RUNNER_SOURCE.as_posix(), "-lm",
               "-o", binary.relative_to(repo_root).as_posix() if binary.is_relative_to(repo_root) else str(binary)]
    proc = subprocess.run([cc, *cflags, "-I", str(repo_root / "core/include"), *sources,
                           str(repo_root / RUNNER_SOURCE), "-lm", "-o", str(binary)], capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f"Biên dịch thất bại:\n{proc.stderr}")
    version = subprocess.run([cc, "--version"], capture_output=True, text=True).stdout.splitlines()
    target = next((line.split(":", 1)[1].strip() for line in version if line.startswith("Target:")), platform.machine())
    return {"binary": binary, "compiler": version[0] if version else cc, "compiler_path": cc,
            "compiler_flags": " ".join(cflags), "compiler_target": target, "build_command": " ".join(rel_cmd),
            "compiler_warnings": proc.stderr.strip()}


def binary_info(binary: Path) -> dict:
    return json.loads(subprocess.run([str(binary), "--info"], check=True, capture_output=True, text=True).stdout)


def check_schema_mapping(repo_root: Path, info: dict) -> dict:
    """Ánh xạ C svmg-angle-23-v1 -> golden svmg-angle23-0.2.0-proposal chỉ hợp lệ khi tên/thứ tự/tham số trùng.

    Không đổi tên phiên bản: candidate khai báo schema được đánh giá; schema gốc của C nằm trong metadata.
    """
    m1 = json.loads((repo_root / M1_CONTRACT).read_text(encoding="utf-8"))
    v02 = json.loads((repo_root / "ml/docs/feature_contract_23_v0.2.json").read_text(encoding="utf-8"))
    checks = {
        "binary_schema_is_m1_v1": info["c_feature_schema_version"] == m1["feature_schema_version"] == C_NATIVE_SCHEMA,
        "binary_feature_names_equal_golden_order": info["feature_names"] == list(FEATURE_ORDER),
        "m1_contract_names_equal_golden_order": [f["name"] for f in m1["features"]] == list(FEATURE_ORDER),
        "m1_contract_indices_0_based": [f["index"] for f in m1["features"]] == list(range(23)),
        "sampling_hz": info["feature_hz"] == m1["sampling_hz"] == v02["sampling_hz"],
        "update_stride_s": info["update_s"] == m1["update_interval_s"] == v02["update_stride_seconds"],
        "windows_s": [info["win_short"] // info["feature_hz"], info["win_long"] // info["feature_hz"]]
                     == m1["windows_s"] == v02["window_seconds"],
        "window_endpoint": m1["window_endpoint"].replace(" ", "") == v02["endpoint_convention"].replace(" ", ""),
        "minimum_valid_fraction": m1["minimum_valid_fraction"] == v02["minimum_valid_fraction"],
        "rms_epsilon": info["rms_epsilon_deg"] == m1["epsilon_rms_deg"] == v02["statistics"]["ratio_epsilon_deg"],
        "r2_zero_tolerance": info["r2_zero_tolerance"] == m1["r_squared_zero_tolerance"],
    }
    return {"c_native_schema_version": info["c_feature_schema_version"], "evaluated_against": SCHEMA_VERSION,
            "mapping": "identity theo feature_index và feature_name (không đổi tên phiên bản)",
            "checks": checks, "compatible": all(checks.values())}


# ----------------------------------------------------------------------------- chạy và chuyển đổi


def run_case(binary: Path, input_path: Path, endpoints: list[int], mode: str = "native") -> pd.DataFrame:
    proc = subprocess.run([str(binary), str(input_path), ",".join(str(int(e)) for e in endpoints), mode],
                          capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f"Runner C lỗi ({proc.returncode}) trên {input_path}: {proc.stderr}")
    raw = pd.read_csv(io.StringIO(proc.stdout), dtype=str, keep_default_na=False)
    for column in RAW_INT_COLUMNS:
        raw[column] = raw[column].astype(np.int64)
    raw["endpoint_time_seconds"] = raw.endpoint_time_seconds.astype(float)
    for column in VALUE_COLUMNS:
        raw[column] = [float(v) for v in raw[column]]  # 'nan' -> NaN; chuỗi %.9g round-trip float32
    if list(raw.endpoint_index) != sorted(int(e) for e in endpoints):
        raise RuntimeError("Runner C không trả đúng tập endpoint yêu cầu.")
    return raw


def representability(times: np.ndarray, endpoint: int) -> dict[str, str | None]:
    """Nhóm feature nào C API biểu diễn trung thực tại endpoint (chỉ dựa vào timestamp input)."""
    out = {}
    for group, n in (("60", 600), ("180", 1800)):
        lo = max(0, endpoint - n + 1)
        dt = np.diff(times[lo:endpoint + 1])
        out[group] = NE_NO_TIMESTAMP if np.any(np.abs(dt - NOMINAL_DT_S) > GRID_TOLERANCE_S) else None
    return out


def derive_status(raw: dict, index: int) -> tuple[str, str, float | None]:
    """(status, reason_code, value) cho feature ``index`` CHỈ từ đầu ra C (xem STATUS_ADAPTER)."""
    value = float(raw[VALUE_COLUMNS[index]])
    if (int(raw["valid_mask"]) >> index) & 1:
        return "VALID", "", value
    keep = None if math.isnan(value) else value  # C vi phạm: mask 0 nhưng có số -> để harness bắt
    if feature_group(index) == "60":
        if not raw["ready_short"]:
            return "INSUFFICIENT_WINDOW", "WINDOW_HISTORY_SHORT", keep
        finite = raw["pitch_finite_60"] if index in PITCH_60 else raw["roll_finite_60"]
        if finite < C_MIN_SHORT:
            return "INVALID_INPUT", "SIGNAL_VALID_COVERAGE", keep
        if index == 7 and raw["roll_pairs_60"] < C_MIN_PAIRS:
            return "INVALID_INPUT", "ADJACENT_PAIR_COVERAGE", keep
        return "UNDEFINED_MATHEMATICALLY", "NON_FINITE_RESULT", keep
    if not raw["ready_long"]:
        return "INSUFFICIENT_WINDOW", "WINDOW_HISTORY_SHORT", keep
    if raw["roll_finite_180"] < C_MIN_LONG:
        return "INVALID_INPUT", "SIGNAL_VALID_COVERAGE", keep
    if index in BLOCK_180 and min(raw["block0_finite"], raw["block1_finite"], raw["block2_finite"]) < C_MIN_BLOCK:
        return "INVALID_INPUT", "SEGMENT_BLOCK_COVERAGE", keep
    if FEATURE_ORDER[index] == "roll_rms_ratio_180":
        return "UNDEFINED_MATHEMATICALLY", "EARLY_RMS_AT_OR_BELOW_EPSILON", keep
    if FEATURE_ORDER[index] == "roll_rms_trend_r2_180":
        return "UNDEFINED_MATHEMATICALLY", "CONSTANT_RMS_TREND", keep
    return "UNDEFINED_MATHEMATICALLY", "NON_FINITE_RESULT", keep


def read_input_times(path: Path) -> np.ndarray:
    return pd.read_csv(path, usecols=["time_seconds"], dtype={"time_seconds": str}).time_seconds.astype(float).to_numpy()


def load_cases(repo_root: Path, suite: str) -> list[dict]:
    return json.loads((Path(repo_root) / compare.suite_root(suite) / "cases.json").read_text(encoding="utf-8"))["cases"]


def export_suite(repo_root: Path, suite: str, binary: Path) -> dict:
    """Chạy C cho mọi case/endpoint golden; trả bản ghi interchange + đầu ra thô C."""
    records, raw_frames = [], []
    for case in load_cases(repo_root, suite):
        path = Path(repo_root) / case["input_file"]
        input_sha = sha256_file(path)
        times = read_input_times(path)
        endpoints = [int(ep["endpoint_index"]) for ep in case["endpoints"]]
        raw = run_case(binary, path, endpoints)
        raw.insert(0, "case_id", case["case_id"])
        raw.insert(1, "input_sha256", input_sha)
        raw_frames.append(raw)
        for row in raw.to_dict("records"):
            groups = representability(times, int(row["endpoint_index"]))
            for i, name in enumerate(FEATURE_ORDER):
                status, reason, value = derive_status(row, i)
                if groups[feature_group(i)]:
                    status, reason, value = NOT_EVALUABLE, groups[feature_group(i)], None
                records.append({"schema_version": SCHEMA_VERSION, "case_id": case["case_id"], "input_sha256": input_sha,
                                "endpoint_index": int(row["endpoint_index"]),
                                "endpoint_time_seconds": float(row["endpoint_time_seconds"]), "feature_index": i,
                                "feature_name": name, "status": status, "reason_code": reason, "value": value})
    return {"records": records, "raw": pd.concat(raw_frames, ignore_index=True) if raw_frames else pd.DataFrame()}


def gridfill_diagnostic(repo_root: Path, suite: str, binary: Path, expected: pd.DataFrame) -> list[dict]:
    """CHẨN ĐOÁN (không phải parity): case có timestamp bị bỏ, chèn mẫu invalid như firmware giữ nhịp 10 Hz.

    So validity C với status Python để làm bằng chứng cho C04; không bao giờ đi vào candidate.
    """
    out = []
    for case in load_cases(repo_root, suite):
        path = Path(repo_root) / case["input_file"]
        times = read_input_times(path)
        if not np.any(np.abs(np.diff(times) - NOMINAL_DT_S) > GRID_TOLERANCE_S):
            continue
        endpoints = [int(ep["endpoint_index"]) for ep in case["endpoints"]]
        raw = run_case(binary, path, endpoints, "gridfill")
        exp = expected.loc[expected.case_id.eq(case["case_id"])].set_index(["endpoint_index", "feature_index"])
        for row in raw.to_dict("records"):
            groups = representability(times, int(row["endpoint_index"]))
            for i, name in enumerate(FEATURE_ORDER):
                if not groups[feature_group(i)]:
                    continue
                status, _, value = derive_status(row, i)
                e = exp.loc[(int(row["endpoint_index"]), i)]
                out.append({"case_id": case["case_id"], "endpoint_index": int(row["endpoint_index"]), "feature_name": name,
                            "placeholders_pushed": int(row["placeholders_pushed"]), "python_status": e.status,
                            "python_reason": e.reason_code, "c_gridfill_status": status, "c_gridfill_value": value,
                            "validity_agrees": (e.status == "VALID") == (status == "VALID")})
    return out


def build_metadata(repo_root: Path, build_info: dict, info: dict, mapping: dict, run_id: str) -> dict:
    meta = interchange.metadata_template()
    meta["golden_manifest_sha256"] = sha256_file(Path(repo_root) / MANIFEST)
    meta["producer"] = {
        "kind": "independent_c_implementation", "name": "svmg_feature23_host_runner", "version": "0.1.0",
        **{k: v for k, v in source_provenance(repo_root).items()},
        "compiler": build_info["compiler"], "compiler_version_macro": info["compiler_version_macro"],
        "compiler_flags": build_info["compiler_flags"], "build_command": build_info["build_command"],
        "target": "host", "target_triple": build_info["compiler_target"],
        "host_platform": f"{platform.system()} {platform.release()} {platform.machine()}",
        "float_type": "float32", "accumulator_type": "float64",
        "flt_eval_method": info["flt_eval_method"],
        "quantile_algorithm": "heapsort tại chỗ + Type-7 (static quantile() trong core/src/features.c)",
        "std_algorithm": "two-pass, tích lũy double",
        "c_feature_schema_version": info["c_feature_schema_version"],
        "c_preprocessing_version": info["c_preprocessing_version"],
        "c_api_used": ["svmg_window_clear", "svmg_window_push", "svmg_features_compute", "svmg_features_to_vector",
                       "svmg_features_from_series (đối chiếu bitwise)"],
        "input_reading": "strtof cho roll_deg/pitch_deg, strtod cho time_seconds (C runner)",
    }
    meta["run_id"] = run_id
    meta["schema_mapping"] = mapping
    meta["status_adapter"] = STATUS_ADAPTER
    meta["not_evaluable_policy"] = NOT_EVALUABLE_POLICY
    meta["notes"] = ("Giá trị số do mã C M1 biên dịch trên host tạo ra. HOST_C_FEATURE_PARITY chỉ; không phải đo trên "
                     "ESP32, không chứng minh chuỗi cảm biến ESP32 hay tích hợp Random Forest.")
    return meta


# ----------------------------------------------------------------------------- tổng hợp


def _num(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else x


def analyse(result: dict) -> dict:
    rows = result["rows"]
    s = result["summary"]
    evaluated = rows.loc[~rows.outcome.isin(compare.NOT_EVALUABLE_OUTCOMES + ("MISSING", "EXTRA"))]
    validity_mismatch = evaluated.loc[(evaluated.expected_status == "VALID") != (evaluated.actual_status == "VALID")]
    status_mismatch = evaluated.loc[evaluated.expected_status != evaluated.actual_status]
    valued = evaluated.loc[evaluated.abs_error.notna()] if "abs_error" in evaluated else evaluated.iloc[:0]
    worst = valued.sort_values("error_ratio", ascending=False).head(1)
    ne = rows.loc[rows.outcome.isin(compare.NOT_EVALUABLE_OUTCOMES)]
    return {
        "verdict": s["verdict"], "is_c_parity_evidence": s["is_c_parity_evidence"],
        "cases": int(rows.case_id.nunique()),
        "endpoints": int(rows[["case_id", "endpoint_index"]].drop_duplicates().shape[0]),
        "feature_records": int(len(rows)), "outcome_counts": s["outcome_counts"],
        "pass": int(rows.outcome.isin(compare.PASS_OUTCOMES).sum()), "fail": s["fail_records"],
        "review": s["review_records"], "not_evaluable": s.get("not_evaluable_records", 0),
        "values_compared": int(len(valued)),
        "max_abs_error": _num(float(valued.abs_error.max())) if len(valued) else None,
        "max_error_ratio": _num(float(valued.error_ratio.max())) if len(valued) else None,
        "worst_record": worst[["case_id", "endpoint_index", "feature_name", "abs_error", "allowed_error", "error_ratio"]]
                        .to_dict("records")[0] if len(worst) else None,
        "validity_mismatches": int(len(validity_mismatch)), "status_mismatches": int(len(status_mismatch)),
        "status_mismatch_detail": status_mismatch[["case_id", "endpoint_index", "feature_name", "expected_status",
                                                   "actual_status", "outcome"]].to_dict("records")[:50],
        "reason_code_mismatches_warning": s["reason_code_mismatches_warning"],
        "not_evaluable_endpoints": sorted({(r.case_id, int(r.endpoint_index)) for r in ne.itertuples()}),
        "not_evaluable_by_case": {k: int(v) for k, v in ne.groupby("case_id").size().items()},
        "per_feature": s["per_feature"], "metadata_warnings": s.get("metadata_warnings", []),
    }


def run(repo_root: Path, suites: tuple[str, ...], run_id: str, cflags=DEFAULT_CFLAGS, with_diagnostic: bool = True) -> dict:
    repo_root = Path(repo_root).resolve()
    out_dir = repo_root / OUT_ROOT / run_id
    build_info = build(repo_root, out_dir / "build", cflags)
    info = binary_info(build_info["binary"])
    mapping = check_schema_mapping(repo_root, info)
    if not mapping["compatible"]:
        raise RuntimeError(f"C schema không tương thích golden, dừng: {mapping['checks']}")
    metadata = build_metadata(repo_root, build_info, info, mapping, run_id)
    meta_path = out_dir / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {"run_id": run_id, "level": "HOST_C_FEATURE_PARITY", "producer": metadata["producer"],
               "schema_mapping": mapping, "suites": {}}
    for suite in suites:
        if not (repo_root / compare.suite_root(suite) / "expected_features.csv").is_file():
            summary["suites"][suite] = {"available": False, "note": "Golden/input suite vắng mặt (gitignored)."}
            continue
        exported = export_suite(repo_root, suite, build_info["binary"])
        candidate = out_dir / f"{suite}.csv"
        interchange.write_csv(exported["records"], candidate)
        exported["raw"].to_csv(out_dir / f"{suite}_c_raw.csv", index=False, lineterminator="\n")
        result = compare.run_comparison(repo_root, suite, candidate, meta_path, repo_root / RUN_ROOT / f"c_host_{run_id}_{suite}",
                                        f"Parity C host (M1 features.c) — suite {suite}")
        entry = {"available": True, "candidate": candidate.relative_to(repo_root).as_posix(),
                 "candidate_sha256": sha256_file(candidate),
                 "from_series_bitwise_match": bool((exported["raw"].from_series_match == 1).all()),
                 **analyse(result)}
        if with_diagnostic:
            expected, _ = compare.load_golden(repo_root, suite)
            diag = gridfill_diagnostic(repo_root, suite, build_info["binary"], expected)
            if diag:
                pd.DataFrame(diag).to_csv(out_dir / f"{suite}_gridfill_diagnostic.csv", index=False, lineterminator="\n")
            entry["gridfill_diagnostic"] = {
                "label": "DIAGNOSTIC_NOT_PARITY (C04)", "records": len(diag),
                "validity_disagreements": sum(not d["validity_agrees"] for d in diag),
                "c_valid_python_invalid": sum(d["c_gridfill_status"] == "VALID" and d["python_status"] != "VALID" for d in diag),
                "examples": [d for d in diag if not d["validity_agrees"]][:6]}
        summary["suites"][suite] = entry
    (out_dir / "c_host_parity_summary.json").write_text(
        json.dumps(summary, indent=1, ensure_ascii=False, default=compare._json_default) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy mã C M1 thật trên golden M2 (host) và so sánh parity.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--suite", choices=["all", "synthetic", "real"], default="all")
    parser.add_argument("--run-id", default="m1v1_host_clang")
    parser.add_argument("--cflags", help="Ghi đè cờ biên dịch (chuỗi cách nhau bởi dấu cách).")
    parser.add_argument("--no-diagnostic", action="store_true")
    args = parser.parse_args()
    suites = ("synthetic", "real") if args.suite == "all" else (args.suite,)
    cflags = tuple(args.cflags.split()) if args.cflags else DEFAULT_CFLAGS
    summary = run(args.repo_root, suites, args.run_id, cflags, not args.no_diagnostic)
    brief = {s: ({k: v[k] for k in ("verdict", "cases", "endpoints", "feature_records", "pass", "fail", "review",
                                    "not_evaluable", "max_abs_error", "max_error_ratio", "validity_mismatches",
                                    "status_mismatches", "from_series_bitwise_match")} if v.get("available") else v)
             for s, v in summary["suites"].items()}
    print(json.dumps({"run_id": args.run_id, "level": summary["level"], "suites": brief}, indent=1, ensure_ascii=False,
                     default=compare._json_default))
    raise SystemExit(1 if any(v.get("fail") for v in summary["suites"].values() if v.get("available")) else 0)


if __name__ == "__main__":
    main()
