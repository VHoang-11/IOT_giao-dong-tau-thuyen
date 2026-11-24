"""Đánh giá MỨC SẴN SÀNG parity Python/C (không có kết quả C thật nào được tạo ở đây).

    python -m ml.parity.readiness

Chạy:
1. Self-consistency Python (golden_vectors.jsonl so với expected_features.csv) — kiểm tra harness/IO.
2. Mô phỏng float32 (``float32_probe``) — hiệu chỉnh dung sai; nhãn FLOAT32_EMULATION_*, KHÔNG phải C.
3. Ma trận đột biến: các lỗi C điển hình phải bị golden + dung sai bắt.
4. Kịch bản file đầu ra hỏng (thiếu/trùng/thừa bản ghi, sai sha, sai thứ tự, NaN VALID, 0 thay invalid...).
5. Tìm kết quả C thật đã nộp trong ml/data/parity/c_results/*/ (metadata kind = independent_c_implementation).

Ghi ml/reports/parity/parity_readiness.json; chi tiết từng bản ghi ở ml/data/parity/runs/ (gitignored).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.parity import compare, float32_probe, interchange
from ml.parity.contract import SCHEMA_VERSION
from ml.parity.golden import MANIFEST, verify_manifest
from ml.parity.tolerance import allowed_error

REPORT_JSON = Path("ml/reports/parity/parity_readiness.json")
RUN_ROOT = Path("ml/data/parity/runs")
C_RESULTS_ROOT = Path("ml/data/parity/c_results")
SUITES = ("synthetic", "real")


def _golden_records(repo_root: Path, suite: str) -> list[dict]:
    frame = interchange.read_jsonl(Path(repo_root) / compare.suite_root(suite) / "golden_vectors.jsonl")
    return [{**r, "value": r["value"]} for r in frame.to_dict("records")]


def _available(repo_root: Path, suite: str) -> bool:
    return (Path(repo_root) / compare.suite_root(suite) / "expected_features.csv").is_file()


def corruption_scenarios(records: list[dict], expected: pd.DataFrame) -> dict[str, tuple[list[dict], str]]:
    """Kịch bản file C hỏng có chủ đích. Trả {tên: (bản ghi, kết quả FAIL mong đợi | 'PASS')}."""
    valid_idx = next(i for i, r in enumerate(records) if r["status"] == "VALID")
    invalid_idx = next(i for i, r in enumerate(records) if r["status"] != "VALID")
    first_case = records[0]["case_id"]
    exp_row = expected.loc[(expected.case_id == records[valid_idx]["case_id"])
                           & (expected.endpoint_index == int(records[valid_idx]["endpoint_index"]))
                           & (expected.feature_index == int(records[valid_idx]["feature_index"]))].iloc[0]
    allowed = allowed_error(exp_row.feature_name, exp_row.value, exp_row.tolerance_scale)

    def mutate(fn):
        out = copy.deepcopy(records)
        fn(out)
        return out

    def set_value(delta):
        return lambda rs: rs[valid_idx].update(value=float(rs[valid_idx]["value"]) + delta)

    return {
        "missing_case": ([r for r in records if r["case_id"] != first_case], "MISSING"),
        "missing_rows": ([r for i, r in enumerate(records) if i not in (3, 4, 5)], "MISSING"),
        "duplicate_rows": (records + copy.deepcopy(records[:2]), "DUPLICATE"),
        "extra_case": (records + [{**copy.deepcopy(records[0]), "case_id": "UNKNOWN_CASE"}], "EXTRA"),
        "wrong_input_sha256": (mutate(lambda rs: [r.update(input_sha256="0" * 64) for r in rs if r["case_id"] == first_case]), "FAIL_INPUT_SHA256"),
        "wrong_schema_version": (mutate(lambda rs: rs[0].update(schema_version="svmg-angle23-0.1.0-proposal")), "FAIL_SCHEMA_VERSION"),
        "feature_names_shifted_by_one": (mutate(lambda rs: [r.update(feature_name=interchange.FEATURE_ORDER[(int(r["feature_index"]) + 1) % 23]) for r in rs[:23]]), "FAIL_FEATURE_NAME_ORDER"),
        "nan_reported_as_valid": (mutate(lambda rs: rs[valid_idx].update(value=float("nan"))), "FAIL_VALID_NOT_FINITE"),
        "empty_value_reported_as_valid": (mutate(lambda rs: rs[valid_idx].update(value=None)), "FAIL_VALID_NOT_FINITE"),
        "invalid_written_as_zero": (mutate(lambda rs: rs[invalid_idx].update(value=0.0)), "FAIL_INVALID_HAS_VALUE"),
        "status_flipped": (mutate(lambda rs: rs[valid_idx].update(status="INVALID_INPUT", value=None)), "FAIL_STATUS_MISMATCH"),
        "unknown_status": (mutate(lambda rs: rs[valid_idx].update(status="OK")), "FAIL_UNKNOWN_STATUS"),
        "endpoint_time_shifted": (mutate(lambda rs: rs[0].update(endpoint_time_seconds=float(rs[0]["endpoint_time_seconds"]) + 0.1)), "FAIL_ENDPOINT_TIME"),
        "value_outside_tolerance": (mutate(set_value(3.0 * allowed)), "FAIL_VALUE_TOLERANCE"),
        "value_inside_tolerance": (mutate(set_value(0.5 * allowed)), "PASS"),
    }


def _row_summary(result: dict) -> dict:
    s = result["summary"]
    return {"verdict": s["verdict"], "outcome_counts": s["outcome_counts"], "fail_records": s["fail_records"],
            "review_records": s["review_records"], "not_evaluable_records": s.get("not_evaluable_records", 0)}


def suite_passed(result: dict) -> bool:
    """Suite chỉ đạt khi là bằng chứng C, không FAIL và không có NOT_EVALUABLE (verdict *_PARTIAL chưa phủ đủ golden)."""
    return bool(result["is_c_parity_evidence"]) and result["fail_records"] == 0 and not result.get("not_evaluable_records")


def find_c_results(repo_root: Path) -> list[dict]:
    """Kết quả C thật do M1 nộp: mỗi thư mục con có <suite>.csv|jsonl + metadata.json."""
    found = []
    root = Path(repo_root) / C_RESULTS_ROOT
    if not root.is_dir():
        return found
    for run_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        meta_path = run_dir / "metadata.json"
        if not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for suite in SUITES:
            for ext in (".csv", ".jsonl"):
                candidate = run_dir / f"{suite}{ext}"
                if candidate.is_file() and _available(repo_root, suite):
                    result = compare.run_comparison(repo_root, suite, candidate, meta_path, Path(repo_root) / RUN_ROOT / f"c_{run_dir.name}_{suite}")
                    found.append({"run": run_dir.name, "suite": suite, "producer": meta.get("producer"), **_row_summary(result),
                                  "is_c_parity_evidence": result["summary"]["is_c_parity_evidence"]})
    return found


def c03_evidence(repo_root: Path) -> dict | None:
    """Đo SST của 3 RMS block ở SYN30 (hoán vị): Python fsum vs float32 cộng tuần tự (issue C03)."""
    import math

    from ml.features.calculations import rms
    from ml.parity.golden import read_inputs

    cases = json.loads((Path(repo_root) / compare.suite_root("synthetic") / "cases.json").read_text(encoding="utf-8"))["cases"]
    case = next((c for c in cases if c["case_id"] == "SYN30_permuted_blocks"), None)
    if case is None:
        return None
    roll = read_inputs(Path(repo_root) / case["input_file"]).roll_deg.to_numpy(float)
    blocks = [roll[lo:hi + 1] for lo, hi in case["endpoints"][-1]["windows"]["blocks_60s"]]
    r64 = [rms(b) for b in blocks]
    m64 = math.fsum(r64) / 3
    r32 = np.array([float32_probe.rms32(b.astype(np.float32)) for b in blocks], dtype=np.float32)
    m32 = float32_probe.mean32(r32)
    sst32 = float(float32_probe.seqsum((r32 - m32) * (r32 - m32)))
    return {"case_id": case["case_id"], "endpoint_index": case["endpoints"][-1]["endpoint_index"],
            "python_block_rms": r64, "python_sst": math.fsum((x - m64) ** 2 for x in r64),
            "float32_block_rms": [float(x) for x in r32], "float32_sst": sst32,
            "sst_threshold": float(json.loads((Path(repo_root) / "ml/docs/feature_contract_23_v0.2.json").read_text(encoding="utf-8"))["statistics"]["r_squared"].split("SST <= ")[1].split(";")[0])}


def run(repo_root: Path) -> dict:
    repo_root = Path(repo_root).resolve()
    manifest_sha = hashlib.sha256((repo_root / MANIFEST).read_bytes()).hexdigest()
    out = {"schema_version": SCHEMA_VERSION, "golden_manifest_sha256": manifest_sha,
           "manifest_verification": verify_manifest(repo_root), "suites": {}}
    for suite in SUITES:
        if not _available(repo_root, suite):
            out["suites"][suite] = {"available": False, "note": "Golden chưa được sinh (dữ liệu processed vắng mặt?)."}
            continue
        expected, cases = compare.load_golden(repo_root, suite)
        entry = {"available": True, "cases": len(cases), "expected_records": int(len(expected))}
        records = _golden_records(repo_root, suite)
        meta_self = {"producer": {"kind": "python_reference_self_consistency"}}
        entry["python_self_consistency"] = _row_summary(compare.compare_frames(expected, interchange.from_records(records), cases, meta_self))
        emu = compare.compare_frames(expected, interchange.from_records(float32_probe.emulate_suite(repo_root, compare.suite_root(suite))),
                                     cases, float32_probe.emulation_metadata(None))
        run_dir = repo_root / RUN_ROOT / f"float32_emulation_{suite}"
        run_dir.mkdir(parents=True, exist_ok=True)
        emu["rows"].to_csv(run_dir / "comparison_rows.csv", index=False, lineterminator="\n")
        reviews = emu["rows"].loc[emu["rows"].outcome.isin(compare.REVIEW_OUTCOMES),
                                  ["case_id", "endpoint_index", "feature_name", "expected_status", "actual_status", "actual_value", "detail"]]
        entry["float32_emulation"] = {**_row_summary(emu), "per_feature": emu["summary"]["per_feature"],
                                      "review_rows": reviews.replace({np.nan: None}).to_dict("records"),
                                      "max_error_ratio_overall": max((f["max_error_ratio"] or 0.0) for f in emu["summary"]["per_feature"])}
        if suite == "synthetic":
            matrix = []
            for mutation, description in float32_probe.MUTATIONS.items():
                res = compare.compare_frames(expected, interchange.from_records(float32_probe.emulate_suite(repo_root, compare.suite_root(suite), mutation)),
                                             cases, float32_probe.emulation_metadata(mutation))
                rows = res["rows"]
                fails = rows.loc[rows.outcome.isin(compare.FAIL_OUTCOMES)]
                matrix.append({"mutation": mutation, "description_vi": description, "verdict": res["summary"]["verdict"],
                               "detected": bool(len(fails)), "fail_records": int(len(fails)),
                               "detecting_cases": sorted(fails.case_id.unique().tolist()),
                               "failing_features": sorted(fails.feature_name.unique().tolist(), key=interchange.FEATURE_ORDER.index)})
            entry["mutation_matrix"] = matrix
            entry["all_mutations_detected"] = all(m["detected"] for m in matrix)
            scenarios = []
            for name, (recs, expected_outcome) in corruption_scenarios(records, expected).items():
                res = compare.compare_frames(expected, interchange.from_records(recs), cases, meta_self)
                counts = res["summary"]["outcome_counts"]
                ok = (res["summary"]["fail_records"] == 0) if expected_outcome == "PASS" else counts.get(expected_outcome, 0) > 0
                scenarios.append({"scenario": name, "expected_outcome": expected_outcome, "verdict": res["summary"]["verdict"],
                                  "outcome_counts": {k: v for k, v in counts.items() if not k.startswith("PASS")}, "behaved_as_expected": bool(ok)})
            entry["corruption_scenarios"] = scenarios
            entry["all_corruptions_behaved"] = all(s["behaved_as_expected"] for s in scenarios)
        out["suites"][suite] = entry
    out["c03_evidence"] = c03_evidence(repo_root)
    c_results = find_c_results(repo_root)
    c_pass = [r for r in c_results if suite_passed(r)]
    c_suites_passed = {r["suite"] for r in c_pass}
    available = {s for s, e in out["suites"].items() if e.get("available")}
    out["c_results_submitted"] = c_results
    out["status"] = ["PYTHON_REFERENCE_READY" if out["manifest_verification"]["passed"] else "PYTHON_REFERENCE_INCOMPLETE",
                     "C_PARITY_VERIFIED" if c_results and available <= c_suites_passed else "C_PARITY_PENDING"]
    out["levels"] = {
        "level_1_python_reference": "Golden do extractor production tạo; kiểm tra giải tích độc lập + cross-check feature table + test.",
        "level_2_python_c_parity": ("CHƯA CÓ kết quả C thật — C_PARITY_PENDING." if not c_results else
                                    f"{len(c_results)} lần nộp kết quả C; suite đạt: {sorted(c_suites_passed)}"),
        "level_3_esp32_sensor_to_model": "CHƯA ĐÁNH GIÁ. Level 2 không chứng minh Level 3; lệch miền do chuỗi lọc firmware đã đo: POS 188 -> 4 (esp32_feature_compatibility.md)."}
    path = repo_root / REPORT_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=compare._json_default) + "\n", encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Đánh giá mức sẵn sàng parity (không tạo kết quả C).")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    out = run(args.repo_root)
    brief = {"status": out["status"], "manifest_ok": out["manifest_verification"]["passed"]}
    for suite, e in out["suites"].items():
        if e.get("available"):
            brief[suite] = {"self": e["python_self_consistency"]["verdict"], "float32": e["float32_emulation"]["verdict"],
                            "float32_max_error_ratio": round(e["float32_emulation"]["max_error_ratio_overall"], 4),
                            "mutations_detected": e.get("all_mutations_detected"), "corruptions_ok": e.get("all_corruptions_behaved")}
    print(json.dumps(brief, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
