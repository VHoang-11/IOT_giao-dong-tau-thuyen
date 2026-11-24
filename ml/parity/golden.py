"""Sinh golden vector cho 23 angle feature bằng extractor production. Chạy từ repository root::

    python -m ml.parity.golden --suite all

- Synthetic (tín hiệu kiểm thử số học, nhỏ, được theo dõi Git): ml/parity/fixtures/synthetic/
- Real (trích từ dữ liệu processed, gitignored): ml/data/parity/real/
- Manifest + checksum: ml/parity/fixtures/manifest.json

Không có dấu thời gian sinh trong file: chạy lại cho byte giống hệt.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import platform
from pathlib import Path

import numpy as np
import pandas as pd

from ml.parity import analytic, interchange
from ml.parity.cases import FS, SYNTHETIC_CASES, real_signal, select_real_cases, synthetic_signal
from ml.parity.contract import (CONTRACT_V02, FEATURE_ORDER, SCHEMA_VERSION, feature_settings, run_extractor,
                                schema_sha256, write_validation)
from ml.parity.tolerance import (EPSILON_REVIEW_FACTOR, FEATURE_CLASS, FEATURE_SCALE, R2_MIN_RELATIVE_SST,
                                 tolerance_document)

FIXTURE_ROOT = Path("ml/parity/fixtures")
SYNTHETIC_ROOT = FIXTURE_ROOT / "synthetic"
REAL_ROOT = Path("ml/data/parity/real")
MANIFEST = FIXTURE_ROOT / "manifest.json"
TOLERANCE_PATH = FIXTURE_ROOT / "tolerance_spec.json"
INTERCHANGE_PATH = FIXTURE_ROOT / "interchange_format.json"
INPUT_COLUMNS = ("sample_index", "time_seconds", "roll_deg", "pitch_deg", "source_sample_index")
EXPECTED_COLUMNS = ("case_id", "endpoint_index", "endpoint_time_seconds", "feature_index", "feature_name", "status",
                    "reason_code", "value", "tolerance_class", "tolerance_scale", "condition_flag")
SOURCE_FILES = ("ml/features/extractor.py", "ml/features/calculations.py", "ml/features/spec.py", "ml/features/config.yaml")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fmt64(value) -> str:
    """Biểu diễn thập phân ngắn nhất round-trip chính xác float64; rỗng cho None."""
    if value is None:
        return ""
    value = float(value)
    if math.isnan(value):
        return "nan"
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    return repr(value)


def fmt32(value) -> str:
    """Biểu diễn thập phân ngắn nhất round-trip chính xác float32 (C đọc bằng strtof)."""
    return str(np.float32(value))


fmt_float = fmt64  # tương thích tên cũ


def inputs_csv_bytes(frame: pd.DataFrame) -> bytes:
    lines = [",".join(INPUT_COLUMNS)]
    for row in frame.itertuples(index=False):
        lines.append(f"{row.sample_index},{fmt64(row.time_seconds)},{fmt32(row.roll_deg)},"
                     f"{fmt32(row.pitch_deg)},{row.source_sample_index}")
    return ("\n".join(lines) + "\n").encode("ascii")


def read_inputs(path: Path) -> pd.DataFrame:
    """Đọc input như C nên đọc: chuỗi thập phân -> float32 (strtof) -> dùng giá trị float32 đó (tính ở float64)."""
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    frame = pd.DataFrame({"sample_index": raw.sample_index.astype(np.int64),
                          "time_seconds": raw.time_seconds.astype(np.float64),
                          "source_sample_index": raw.source_sample_index.astype(np.int64)})
    for column in ("roll_deg", "pitch_deg"):
        values = np.array([float(v) for v in raw[column]], dtype=np.float64).astype(np.float32)
        canonical = [fmt32(v) for v in values]
        if canonical != raw[column].tolist():
            raise ValueError(f"Cột {column} không ở dạng float32 chính tắc (ngắn nhất, round-trip): {path}")
        frame[column] = values.astype(np.float64)
    return frame[list(INPUT_COLUMNS)]


def _max_abs(x: np.ndarray):
    x = x[np.isfinite(x)]
    return float(np.max(np.abs(x))) if len(x) else None


def _slice(t, lower, upper) -> tuple[int, int]:
    return int(np.searchsorted(t, lower, side="right")), int(np.searchsorted(t, upper, side="right"))


def evaluate_case(case_id: str, inputs: pd.DataFrame, settings: dict) -> list[dict]:
    """Chạy extractor production trên đúng chuỗi input đã lưu và gom kết quả theo endpoint."""
    t = inputs.time_seconds.to_numpy(float)
    roll, pitch = inputs.roll_deg.to_numpy(float), inputs.pitch_deg.to_numpy(float)
    values, metadata, _ = run_extractor(t, roll, pitch, settings, case_id)
    gapless = bool(len(t) < 2 or np.all(np.diff(inputs.source_sample_index.to_numpy()) == 1))
    endpoints = []
    for value_row, meta_row in zip(values.itertuples(index=False), metadata.itertuples(index=False)):
        end = float(meta_row.window_end_seconds)
        ke = int(np.searchsorted(t, end, side="left"))
        if t[ke] != end:
            raise RuntimeError("Endpoint không trùng timestamp của mẫu.")
        validity = json.loads(meta_row.validity_json)
        w60, w180 = _slice(t, end - 60.0, end), _slice(t, end - 180.0, end)
        blocks = [_slice(t, end - 180.0 + 60.0 * j, end - 120.0 + 60.0 * j) for j in range(3)]
        integer_ok = (w60 == (ke - 599, ke + 1)) and (ke < 1800 or w180 == (ke - 1799, ke + 1)) if gapless else None
        scales = {"roll_scale_60": _max_abs(roll[w60[0]:w60[1]]), "roll_scale_180": _max_abs(roll[w180[0]:w180[1]]),
                  "pitch_scale_60": _max_abs(pitch[w60[0]:w60[1]])}
        # Metadata điều kiện số (KHÔNG phải giá trị golden): RMS block dùng để phân loại R²/ratio ill-conditioned.
        block_rms = []
        for lo, hi in blocks:
            seg = roll[lo:hi]
            seg = seg[np.isfinite(seg)]
            block_rms.append(float(np.sqrt(np.mean(seg ** 2))) if len(seg) else None)
        relative_sst = None
        if ke >= 1800 and all(b is not None for b in block_rms) and np.mean(block_rms) > 0:
            r = np.array(block_rms)
            relative_sst = float(np.sum((r - r.mean()) ** 2) / r.mean() ** 2)
        eps = settings["numeric_zero_epsilon_deg"]
        flags = {}
        if relative_sst is not None and relative_sst < R2_MIN_RELATIVE_SST:
            flags["roll_rms_trend_r2_180"] = "ILL_CONDITIONED_R2"
        if ke >= 1800 and block_rms[0] is not None and eps / EPSILON_REVIEW_FACTOR <= block_rms[0] <= eps * EPSILON_REVIEW_FACTOR:
            flags["roll_rms_ratio_180"] = "NEAR_EPSILON_RATIO"
        statuses = [validity[f]["status"] for f in FEATURE_ORDER]
        vector = [float(getattr(value_row, f)) if statuses[i] == "VALID" else None for i, f in enumerate(FEATURE_ORDER)]
        if any(v is not None and not math.isfinite(v) for v in vector):
            raise RuntimeError("Feature VALID nhưng không hữu hạn.")
        endpoints.append({"endpoint_index": ke, "endpoint_time_seconds": end,
                          "windows": {"roll_pitch_60s": [w60[0], w60[1] - 1], "roll_180s": [w180[0], w180[1] - 1],
                                      "blocks_60s": [[lo, hi - 1] for lo, hi in blocks]},
                          "window_index_rule_consistent": integer_ok, "scales": scales,
                          "conditioning": {"block_rms": block_rms, "relative_sst": relative_sst},
                          "condition_flags": flags, "vector": vector, "status": statuses,
                          "reason": [validity[f]["reason_code"] for f in FEATURE_ORDER]})
    return endpoints


def expected_rows(case_id: str, input_sha: str, endpoints: list[dict]) -> list[dict]:
    rows = []
    for ep in endpoints:
        for i, name in enumerate(FEATURE_ORDER):
            rows.append({"case_id": case_id,
                         "endpoint_index": ep["endpoint_index"], "endpoint_time_seconds": fmt_float(ep["endpoint_time_seconds"]),
                         "feature_index": i, "feature_name": name, "status": ep["status"][i],
                         "reason_code": ep["reason"][i] or "", "value": fmt_float(ep["vector"][i]),
                         "tolerance_class": FEATURE_CLASS[name], "tolerance_scale": fmt_float(ep["scales"][FEATURE_SCALE[name]]),
                         "condition_flag": ep["condition_flags"].get(name, "")})
    return rows


def golden_records_for(case_id: str, input_sha: str, endpoints: list[dict]) -> list[dict]:
    """Golden ở đúng định dạng trao đổi mà C phải xuất (dùng cho self-consistency và làm ví dụ)."""
    return [{"schema_version": SCHEMA_VERSION, "case_id": case_id, "input_sha256": input_sha,
             "endpoint_index": ep["endpoint_index"], "endpoint_time_seconds": ep["endpoint_time_seconds"],
             "feature_index": i, "feature_name": name, "status": ep["status"][i], "reason_code": ep["reason"][i] or "",
             "value": ep["vector"][i]} for ep in endpoints for i, name in enumerate(FEATURE_ORDER)]


def rows_csv_bytes(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    pd.DataFrame(rows, columns=EXPECTED_COLUMNS).to_csv(buffer, index=False, lineterminator="\n")
    return buffer.getvalue().encode("utf-8")


def _write(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha256_bytes(data)


def build_suite(repo_root: Path, suite: str, settings: dict) -> dict:
    root = repo_root / (SYNTHETIC_ROOT if suite == "synthetic" else REAL_ROOT)
    cases_meta, all_rows, files, golden_records = [], [], {}, []
    if suite == "synthetic":
        definitions = [(c.case_id, synthetic_signal(c), {"kind": "synthetic_numerical_test_signal", "title": c.title,
                        "detects": list(c.detects), "generator": "ml.parity.cases.synthetic_signal",
                        "duration_s": c.duration_s}) for c in SYNTHETIC_CASES]
    else:
        definitions = []
        for c in select_real_cases(repo_root):
            frame, provenance = real_signal(repo_root, c)
            definitions.append((c.case_id, frame, {"kind": "real_data_reference", "dataset_source": c.dataset_source,
                                "session_id": c.session_id, "segment_id": c.segment_id, "source_start_index": c.start_index,
                                "n_samples": c.n_samples, "selection_rule": c.selection_rule,
                                "processed_path": f"ml/data/processed/{c.dataset_source}/{c.session_id}/{c.segment_id}/timeseries.parquet",
                                "source_provenance": provenance}))
    for case_id, frame, meta in definitions:
        data = inputs_csv_bytes(frame)
        rel = (root / "inputs" / f"{case_id}.csv").relative_to(repo_root).as_posix()
        input_sha = _write(repo_root / rel, data)
        files[rel] = input_sha
        stored = read_inputs(repo_root / rel)  # expected tính từ chính bytes đã lưu
        endpoints = evaluate_case(case_id, stored, settings)
        rows = expected_rows(case_id, input_sha, endpoints)
        all_rows.extend(rows)
        golden_records.extend(golden_records_for(case_id, input_sha, endpoints))
        checks = analytic.run_checks(case_id, endpoints[-1], list(FEATURE_ORDER)) if suite == "synthetic" else []
        finite = np.isfinite(stored[["roll_deg", "pitch_deg"]].to_numpy())
        cases_meta.append({"case_id": case_id, **meta, "input_file": rel, "input_sha256": input_sha,
                           "n_samples": int(len(stored)), "sampling_hz": FS, "units": {"roll_deg": "degree", "pitch_deg": "degree"},
                           "time_first_s": float(stored.time_seconds.iloc[0]), "time_last_s": float(stored.time_seconds.iloc[-1]),
                           "non_finite_samples": {"roll": int((~finite[:, 0]).sum()), "pitch": int((~finite[:, 1]).sum())},
                           "dropped_timestamps": int((np.diff(stored.source_sample_index.to_numpy()) - 1).sum()),
                           "window_definition": {"short": "(t-60, t]", "long": "(t-180, t]",
                                                 "blocks": "(t-180+60j, t-120+60j], j=0..2"},
                           "endpoint_count": len(endpoints), "endpoints": endpoints, "analytic_checks": checks})
    expected_rel = (root / "expected_features.csv").relative_to(repo_root).as_posix()
    files[expected_rel] = _write(repo_root / expected_rel, rows_csv_bytes(all_rows))
    vectors_rel = (root / "golden_vectors.jsonl").relative_to(repo_root).as_posix()
    files[vectors_rel] = _write(repo_root / vectors_rel, interchange.write_jsonl(golden_records, None))
    stored_cases = [{**c, "endpoints": [{k: v for k, v in ep.items() if k not in ("vector", "status", "reason")}
                                        for ep in c["endpoints"]]} for c in cases_meta]
    payload = {"schema_version": SCHEMA_VERSION, "suite": suite, "feature_order": list(FEATURE_ORDER),
               "schema_sha256": schema_sha256(),
               "note": "Giá trị golden nằm ở expected_features.csv (dạng dài, có tên feature) và golden_vectors.jsonl (vector 23 phần tử có thứ tự).",
               "cases": stored_cases}
    cases_rel = (root / "cases.json").relative_to(repo_root).as_posix()
    files[cases_rel] = _write(repo_root / cases_rel, json.dumps(payload, ensure_ascii=False, separators=(",", ":"),
                                                                 sort_keys=True, default=float).encode("utf-8"))
    return {"suite": suite, "files": files, "cases": cases_meta, "rows": len(all_rows)}


def real_cross_check(repo_root: Path, real: dict) -> dict:
    """So golden real-data với feature table đã có (cùng extractor) để bắt lỗi cắt đoạn/ranh giới."""
    out = []
    for case in real["cases"]:
        meta = pd.read_parquet(repo_root / "ml/data/features" / case["dataset_source"] / "feature_metadata.parquet",
                               columns=["window_id", "session_id", "segment_id", "window_end_seconds"])
        values = pd.read_parquet(repo_root / "ml/data/features" / case["dataset_source"] / "feature_values.parquet",
                                 columns=["window_id", *FEATURE_ORDER])
        table = meta.loc[meta.session_id.eq(case["session_id"]) & meta.segment_id.eq(case["segment_id"])].merge(values, on="window_id")
        compared, max_diff, status_mismatch = 0, 0.0, 0
        for ep in case["endpoints"]:
            match = table.loc[(table.window_end_seconds - ep["endpoint_time_seconds"]).abs() <= 1e-6]
            if len(match) != 1:
                continue
            for i, name in enumerate(FEATURE_ORDER):
                long_window = i >= 8 and i < 20
                if long_window and ep["endpoint_index"] < 1800:
                    continue  # đoạn trích chưa đủ 180 s lịch sử: WARMUP theo thiết kế
                ref = match.iloc[0][name]
                golden = ep["vector"][i]
                if (golden is None) != pd.isna(ref):
                    status_mismatch += 1
                    continue
                if golden is not None:
                    compared += 1
                    max_diff = max(max_diff, abs(golden - float(ref)))
        out.append({"case_id": case["case_id"], "values_compared": compared, "max_abs_difference": max_diff,
                    "validity_mismatch": status_mismatch})
    return {"cases": out, "passed": all(c["max_abs_difference"] == 0.0 and c["validity_mismatch"] == 0 and c["values_compared"] > 0 for c in out)}


def run(repo_root: Path, suites: tuple[str, ...]) -> dict:
    repo_root = repo_root.resolve()
    validation = write_validation(repo_root)
    settings = feature_settings(repo_root)
    results = {s: build_suite(repo_root, s, settings) for s in suites}
    tol_bytes = json.dumps(tolerance_document(), indent=1, ensure_ascii=False, sort_keys=True).encode("utf-8")
    inter_bytes = json.dumps(interchange.interchange_document(), indent=1, ensure_ascii=False, sort_keys=True).encode("utf-8")
    files = {TOLERANCE_PATH.as_posix(): _write(repo_root / TOLERANCE_PATH, tol_bytes),
             INTERCHANGE_PATH.as_posix(): _write(repo_root / INTERCHANGE_PATH, inter_bytes)}
    previous = json.loads((repo_root / MANIFEST).read_text()) if (repo_root / MANIFEST).is_file() else {}
    entries = {k: v for k, v in previous.get("files", {}).items()} if set(suites) != {"synthetic", "real"} else {}
    for s in results.values():
        for path, digest in s["files"].items():
            entries[path] = {"sha256": digest, "bytes": (repo_root / path).stat().st_size,
                             "tracked_in_git": not path.startswith("ml/data/"), "suite": s["suite"]}
    for path, digest in files.items():
        entries[path] = {"sha256": digest, "bytes": (repo_root / path).stat().st_size, "tracked_in_git": True, "suite": "shared"}
    summary = {"schema_version": SCHEMA_VERSION, "contract": CONTRACT_V02.as_posix(),
               "contract_sha256": sha256_bytes((repo_root / CONTRACT_V02).read_bytes()), "schema_sha256": schema_sha256(),
               "feature_order": list(FEATURE_ORDER), "generator": "python -m ml.parity.golden",
               "reference_sources_sha256": {p: sha256_bytes((repo_root / p).read_bytes()) for p in SOURCE_FILES},
               "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
               "parity_status": ["PYTHON_REFERENCE_READY", "C_PARITY_PENDING"],
               "suites": {s: {"cases": len(r["cases"]), "expected_rows": r["rows"],
                              "endpoints": sum(c["endpoint_count"] for c in r["cases"])} for s, r in results.items()},
               "files": dict(sorted(entries.items()))}
    for key in ("suites", "real_cross_check", "analytic_checks", "window_index_rule_consistent"):
        if key in previous and set(suites) != {"synthetic", "real"}:  # chạy một suite: giữ thông tin suite còn lại
            summary[key] = {**previous[key], **summary[key]} if key == "suites" else previous[key]
    if "real" in results:
        summary["real_cross_check"] = real_cross_check(repo_root, results["real"])
    if "synthetic" in results:
        checks = [c for case in results["synthetic"]["cases"] for c in case["analytic_checks"]]
        summary["analytic_checks"] = {"total": len(checks), "passed": sum(c["passed"] for c in checks),
                                      "failed": [c for c in checks if not c["passed"]]}
        eps = [ep for case in results["synthetic"]["cases"] for ep in case["endpoints"]]
        summary["window_index_rule_consistent"] = all(ep["window_index_rule_consistent"] in (True, None) for ep in eps)
    summary["contract_validation"] = {"blocking_inconsistency": validation["blocking_inconsistency"],
                                      "open_issues": [i["id"] for i in validation["issues"] if i["status"].startswith("OPEN")]}
    (repo_root / MANIFEST).write_text(json.dumps(summary, indent=1, ensure_ascii=False, sort_keys=True, default=float) + "\n", encoding="utf-8")
    return summary


def verify_manifest(repo_root: Path, include_untracked: bool = True) -> dict:
    manifest = json.loads((repo_root / MANIFEST).read_text(encoding="utf-8"))
    problems = []
    for path, entry in manifest["files"].items():
        full = repo_root / path
        if not full.is_file():
            if entry["tracked_in_git"] or include_untracked:
                problems.append({"path": path, "problem": "MISSING"})
            continue
        if sha256_bytes(full.read_bytes()) != entry["sha256"]:
            problems.append({"path": path, "problem": "SHA256_MISMATCH"})
    return {"files": len(manifest["files"]), "problems": problems, "passed": not problems}


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh golden vector 23 feature (tham chiếu Python, không phải kết quả C).")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--suite", choices=["all", "synthetic", "real"], default="all")
    parser.add_argument("--verify-only", action="store_true", help="Chỉ kiểm tra checksum trong manifest.")
    args = parser.parse_args()
    if args.verify_only:
        root = args.repo_root.resolve()
        report = verify_manifest(root, include_untracked=(root / REAL_ROOT).is_dir())
        print(json.dumps(report, indent=1, ensure_ascii=False))
        raise SystemExit(0 if report["passed"] else 1)
    suites = ("synthetic", "real") if args.suite == "all" else (args.suite,)
    summary = run(args.repo_root, suites)
    print(json.dumps({k: summary[k] for k in ("parity_status", "suites", "analytic_checks", "real_cross_check",
                                                "window_index_rule_consistent", "contract_validation") if k in summary},
                     indent=1, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
