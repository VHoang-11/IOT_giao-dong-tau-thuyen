"""Harness so sánh golden Python với đầu ra feature được tạo bên ngoài (C/C++ của M1).

Chạy từ repository root::

    python -m ml.parity.compare --suite synthetic --candidate out/c_features.csv \\
        --metadata out/c_features.meta.json --out ml/data/parity/runs/c_host_v1

Harness KHÔNG tự tạo kết quả C. Nhãn kết luận phụ thuộc ``producer.kind`` trong metadata:
``independent_c_implementation`` -> C_PARITY_*; ``python_float32_emulation`` -> FLOAT32_EMULATION_*;
``python_reference_self_consistency`` -> PYTHON_SELF_CONSISTENCY_*; không có metadata -> UNATTRIBUTED_*.
Chỉ C_PARITY_PASS trên mọi suite mới được phép gọi là parity Python/C (Level 2). Level 2 không chứng minh Level 3.

Producer có thể khai báo status ``NOT_EVALUABLE`` (kèm reason_code, value rỗng) cho bản ghi mà API của nó không
biểu diễn trung thực được (ví dụ C không nhận timestamp). Bản ghi đó KHÔNG bao giờ là PASS: kết quả
``NOT_EVALUABLE`` và verdict tối đa ``<prefix>_PARTIAL`` (không FAIL nhưng chưa phủ đủ golden).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from ml.parity import interchange
from ml.parity.contract import FEATURE_ORDER, SCHEMA_VERSION, STATUS_VOCABULARY
from ml.parity.golden import MANIFEST, REAL_ROOT, SYNTHETIC_ROOT
from ml.parity.tolerance import CLASSES, FEATURE_CLASS, allowed_error

ENDPOINT_TIME_TOLERANCE_S = 1e-6
FAIL_OUTCOMES = ("FAIL_VALUE_TOLERANCE", "FAIL_STATUS_MISMATCH", "FAIL_VALID_NOT_FINITE", "FAIL_INVALID_HAS_VALUE",
                 "FAIL_FEATURE_NAME_ORDER", "FAIL_UNKNOWN_STATUS", "FAIL_INPUT_SHA256", "FAIL_SCHEMA_VERSION",
                 "FAIL_ENDPOINT_TIME", "FAIL_UNPARSEABLE_VALUE", "FAIL_R2_OUT_OF_RANGE", "FAIL_METADATA",
                 "MISSING", "EXTRA", "DUPLICATE")
PASS_OUTCOMES = ("PASS_VALUE", "PASS_STATUS_ONLY")
REVIEW_OUTCOMES = ("REVIEW_ILL_CONDITIONED",)
NOT_EVALUABLE_STATUS = "NOT_EVALUABLE"  # khai báo của producer, không thuộc từ vựng status feature
NOT_EVALUABLE_OUTCOMES = ("NOT_EVALUABLE",)
VERDICT_PREFIX = {"independent_c_implementation": "C_PARITY", "python_float32_emulation": "FLOAT32_EMULATION",
                  "python_reference_self_consistency": "PYTHON_SELF_CONSISTENCY"}


def suite_root(suite: str) -> Path:
    return SYNTHETIC_ROOT if suite == "synthetic" else REAL_ROOT


def load_golden(repo_root: Path, suite: str) -> tuple[pd.DataFrame, dict]:
    root = Path(repo_root) / suite_root(suite)
    expected = pd.read_csv(root / "expected_features.csv", dtype=str, keep_default_na=False)
    expected["endpoint_index"] = expected.endpoint_index.astype(int)
    expected["feature_index"] = expected.feature_index.astype(int)
    expected["endpoint_time_seconds"] = expected.endpoint_time_seconds.astype(float)
    expected["value"] = pd.Series([interchange.parse_value(v) for v in expected.value], dtype=object, index=expected.index)
    expected["tolerance_scale"] = pd.Series([interchange.parse_value(v) for v in expected.tolerance_scale], dtype=object,
                                            index=expected.index)
    cases = json.loads((root / "cases.json").read_text(encoding="utf-8"))
    if cases["schema_version"] != SCHEMA_VERSION or cases["feature_order"] != list(FEATURE_ORDER):
        raise ValueError("Golden không khớp schema/thứ tự feature của contract hiện hành.")
    return expected, {c["case_id"]: c for c in cases["cases"]}


def _relative(actual: float, expected: float) -> float | None:
    return abs(actual - expected) / abs(expected) if expected != 0.0 else None


def _classify(exp: pd.Series, cand: pd.Series | None, case_sha: str | None) -> dict:
    out = {"case_id": exp.case_id, "endpoint_index": int(exp.endpoint_index), "feature_index": int(exp.feature_index),
           "feature_name": exp.feature_name, "expected_status": exp.status, "expected_reason": exp.reason_code,
           "expected_value": exp.value, "condition_flag": exp.condition_flag, "tolerance_class": exp.tolerance_class,
           "actual_status": None, "actual_reason": None, "actual_value": None, "abs_error": None, "rel_error": None,
           "allowed_error": None, "error_ratio": None, "reason_match": None, "outcome": "MISSING", "detail": ""}
    if cand is None:
        out["detail"] = "Không có bản ghi C cho (case, endpoint, feature)."
        return out
    out.update(actual_status=cand.status, actual_reason=cand.reason_code, actual_value=cand.value)
    out["reason_match"] = (cand.reason_code == exp.reason_code) if cand.reason_code else None
    checks = [
        (cand.schema_version != SCHEMA_VERSION, "FAIL_SCHEMA_VERSION", f"schema_version '{cand.schema_version}'"),
        (case_sha is not None and cand.input_sha256 != case_sha, "FAIL_INPUT_SHA256", "input_sha256 khác file input golden"),
        (not math.isfinite(cand.endpoint_time_seconds)
         or abs(cand.endpoint_time_seconds - exp.endpoint_time_seconds) > ENDPOINT_TIME_TOLERANCE_S, "FAIL_ENDPOINT_TIME",
         f"endpoint_time {cand.endpoint_time_seconds} != {exp.endpoint_time_seconds}"),
        (cand.feature_name != exp.feature_name, "FAIL_FEATURE_NAME_ORDER", f"index {exp.feature_index} phải là {exp.feature_name}, nhận {cand.feature_name}"),
        (cand.status not in STATUS_VOCABULARY and cand.status != NOT_EVALUABLE_STATUS, "FAIL_UNKNOWN_STATUS",
         f"status '{cand.status}' ngoài từ vựng"),
        (cand.parse_problem == "UNPARSEABLE_VALUE", "FAIL_UNPARSEABLE_VALUE", f"value '{cand.value_text}' không đọc được"),
    ]
    for failed, outcome, detail in checks:
        if failed:
            out.update(outcome=outcome, detail=detail)
            return out
    actual = cand.value
    if cand.status == NOT_EVALUABLE_STATUS:
        if actual is not None or not cand.reason_code:
            out.update(outcome="FAIL_INVALID_HAS_VALUE" if actual is not None else "FAIL_UNKNOWN_STATUS",
                       detail="NOT_EVALUABLE phải có value rỗng và reason_code giải thích")
        else:
            out.update(outcome="NOT_EVALUABLE", reason_match=None,
                       detail=f"Producer khai báo không biểu diễn được case: {cand.reason_code}")
        return out
    if cand.status != "VALID" and actual is not None:
        out.update(outcome="FAIL_INVALID_HAS_VALUE",
                   detail=f"status {cand.status} nhưng value = {cand.value_text} (không được thay giá trị không hợp lệ bằng số/0)")
        return out
    if cand.status == "VALID" and (actual is None or not math.isfinite(actual)):
        out.update(outcome="FAIL_VALID_NOT_FINITE", detail=f"status VALID nhưng value = '{cand.value_text}'")
        return out
    flagged = bool(exp.condition_flag)
    if exp.feature_name == "roll_rms_trend_r2_180" and cand.status == "VALID" and not (-1e-9 <= actual <= 1 + 1e-9):
        out.update(outcome="FAIL_R2_OUT_OF_RANGE", detail=f"R² = {actual} ngoài [0, 1]")
        return out
    if cand.status != exp.status:
        if flagged:
            out.update(outcome="REVIEW_ILL_CONDITIONED",
                       detail=f"{exp.condition_flag}: status {exp.status} vs {cand.status}; quyết định phụ thuộc làm tròn (xem C02/C03)")
        else:
            out.update(outcome="FAIL_STATUS_MISMATCH", detail=f"status {exp.status} vs {cand.status}")
        return out
    if exp.status != "VALID":
        out["outcome"] = "PASS_STATUS_ONLY"
        return out
    allowed = allowed_error(exp.feature_name, exp.value, exp.tolerance_scale)
    error = abs(actual - exp.value)
    out.update(abs_error=error, rel_error=_relative(actual, exp.value), allowed_error=allowed,
               error_ratio=error / allowed if allowed > 0 else math.inf)
    if error <= allowed:
        out["outcome"] = "PASS_VALUE"
    elif flagged:
        out.update(outcome="REVIEW_ILL_CONDITIONED", detail=f"{exp.condition_flag}: sai số {error:.3g} > {allowed:.3g} trên feature ill-conditioned")
    else:
        out.update(outcome="FAIL_VALUE_TOLERANCE", detail=f"|Δ| = {error:.6g} > cho phép {allowed:.6g}")
    return out


def compare_frames(expected: pd.DataFrame, candidate: pd.DataFrame, case_meta: dict | None = None,
                   metadata: dict | None = None) -> dict:
    """So khớp từng (case, endpoint, feature). Trả {'rows': DataFrame, 'summary': dict}."""
    key = list(interchange.KEY)
    dup_mask = candidate.duplicated(key, keep=False)
    duplicates = candidate.loc[dup_mask]
    cand_unique = candidate.loc[~candidate.duplicated(key, keep="first")]
    cand_index = {tuple(k): row for k, row in zip(cand_unique[key].itertuples(index=False, name=None), cand_unique.itertuples(index=False))}
    expected_keys = set(expected[key].itertuples(index=False, name=None))
    shas = {cid: meta.get("input_sha256") for cid, meta in (case_meta or {}).items()}
    dup_keys = set(duplicates[key].itertuples(index=False, name=None))
    rows = []
    for exp in expected.itertuples(index=False):
        k = (exp.case_id, int(exp.endpoint_index), int(exp.feature_index))
        row = _classify(exp, cand_index.get(k), shas.get(exp.case_id))
        if k in dup_keys:
            row.update(outcome="DUPLICATE", detail="Bản ghi C trùng khóa (case, endpoint, feature).")
        rows.append(row)
    for cand in cand_unique.itertuples(index=False):
        k = (cand.case_id, int(cand.endpoint_index), int(cand.feature_index))
        if k not in expected_keys:
            rows.append({"case_id": cand.case_id, "endpoint_index": int(cand.endpoint_index), "feature_index": int(cand.feature_index),
                         "feature_name": cand.feature_name, "actual_status": cand.status, "actual_value": cand.value,
                         "outcome": "EXTRA", "detail": "Bản ghi không có trong golden (case/endpoint/feature lạ)."})
    frame = pd.DataFrame(rows)
    return {"rows": frame, "summary": summarize(frame, expected, candidate, metadata)}


def summarize(frame: pd.DataFrame, expected: pd.DataFrame, candidate: pd.DataFrame, metadata: dict | None) -> dict:
    counts = {k: int(v) for k, v in frame.outcome.value_counts().sort_index().items()}
    fails = sum(counts.get(k, 0) for k in FAIL_OUTCOMES)
    reviews = sum(counts.get(k, 0) for k in REVIEW_OUTCOMES)
    not_evaluable = sum(counts.get(k, 0) for k in NOT_EVALUABLE_OUTCOMES)
    kind = (metadata or {}).get("producer", {}).get("kind")
    prefix = VERDICT_PREFIX.get(kind, "UNATTRIBUTED")
    verdict = (f"{prefix}_FAIL" if fails else f"{prefix}_PARTIAL" if not_evaluable
               else f"{prefix}_PASS_WITH_REVIEW" if reviews else f"{prefix}_PASS")
    per_feature = []
    for i, name in enumerate(FEATURE_ORDER):
        sub = frame.loc[frame.feature_name.eq(name) & frame.outcome.ne("EXTRA")]
        valued = sub.loc[sub.abs_error.notna()] if "abs_error" in sub else sub.iloc[:0]
        per_feature.append({"feature_index": i, "feature_name": name, "tolerance_class": FEATURE_CLASS[name],
                            "records": int(len(sub)),
                            "pass": int(sub.outcome.isin(PASS_OUTCOMES).sum()),
                            "fail": int(sub.outcome.isin(FAIL_OUTCOMES).sum()),
                            "review": int(sub.outcome.isin(REVIEW_OUTCOMES).sum()),
                            "not_evaluable": int(sub.outcome.isin(NOT_EVALUABLE_OUTCOMES).sum()),
                            "values_compared": int(len(valued)),
                            "max_abs_error": float(valued.abs_error.max()) if len(valued) else None,
                            "max_rel_error": float(valued.rel_error.dropna().max()) if len(valued) and valued.rel_error.notna().any() else None,
                            "max_error_ratio": float(valued.error_ratio.max()) if len(valued) else None})
    reason_mismatch = int((frame.get("reason_match") == False).sum()) if "reason_match" in frame else 0  # noqa: E712
    cases_expected = sorted(expected.case_id.unique())
    cases_candidate = sorted(candidate.case_id.unique())
    return {"verdict": verdict, "producer_kind": kind, "producer": (metadata or {}).get("producer"),
            "is_c_parity_evidence": prefix == "C_PARITY", "schema_version": SCHEMA_VERSION,
            "expected_records": int(len(expected)), "candidate_records": int(len(candidate)),
            "outcome_counts": counts, "fail_records": fails, "review_records": reviews,
            "not_evaluable_records": not_evaluable,
            "missing_cases": sorted(set(cases_expected) - set(cases_candidate)),
            "extra_cases": sorted(set(cases_candidate) - set(cases_expected)),
            "reason_code_mismatches_warning": reason_mismatch, "per_feature": per_feature,
            "level_note": "Level 2 (cùng chuỗi Roll/Pitch đầu vào). Không chứng minh Level 3 (IMU thật, ước lượng góc, lọc trên ESP32)."}


def validate_metadata(metadata: dict | None, repo_root: Path) -> list[str]:
    if metadata is None:
        return ["Không có metadata: kết quả UNATTRIBUTED, không thể dùng làm bằng chứng parity C."]
    warnings = []
    if metadata.get("interchange_schema") != interchange.INTERCHANGE_SCHEMA:
        warnings.append(f"interchange_schema '{metadata.get('interchange_schema')}' != {interchange.INTERCHANGE_SCHEMA}")
    if metadata.get("schema_version") != SCHEMA_VERSION:
        warnings.append(f"schema_version metadata '{metadata.get('schema_version')}' != {SCHEMA_VERSION}")
    kind = metadata.get("producer", {}).get("kind")
    if kind not in interchange.PRODUCER_KINDS:
        warnings.append(f"producer.kind '{kind}' không thuộc {interchange.PRODUCER_KINDS}")
    manifest = Path(repo_root) / MANIFEST
    if manifest.is_file():
        current = hashlib.sha256(manifest.read_bytes()).hexdigest()
        if metadata.get("golden_manifest_sha256") != current:
            warnings.append("golden_manifest_sha256 không khớp manifest hiện tại: C có thể đã dùng golden cũ.")
    return warnings


def markdown_report(result: dict, title: str) -> str:
    s = result["summary"]
    lines = [f"# {title}", "", f"- Kết luận: **{s['verdict']}**",
             f"- Loại nguồn kết quả: `{s['producer_kind']}` — bằng chứng parity C: **{'có' if s['is_c_parity_evidence'] else 'không'}**",
             f"- Bản ghi golden: {s['expected_records']}; bản ghi ứng viên: {s['candidate_records']}",
             f"- FAIL: {s['fail_records']}; REVIEW: {s['review_records']}; NOT_EVALUABLE: {s.get('not_evaluable_records', 0)}; "
             f"cảnh báo reason_code: {s['reason_code_mismatches_warning']}",
             f"- Case thiếu: {s['missing_cases'] or 'không'}; case thừa: {s['extra_cases'] or 'không'}",
             f"- {s['level_note']}", ""]
    if result.get("metadata_warnings"):
        lines += ["## Cảnh báo metadata", ""] + [f"- {w}" for w in result["metadata_warnings"]] + [""]
    lines += ["## Đếm kết quả", "", "| Kết quả | Số bản ghi |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in s["outcome_counts"].items()]
    lines += ["", "## Theo feature", "",
              "| # | Feature | Lớp dung sai | Pass | Fail | Review | Not evaluable | Max |Δ| | Max |Δ|/cho phép |",
              "|---:|---|---|---:|---:|---:|---:|---:|---:|"]
    for f in s["per_feature"]:
        mx = "—" if f["max_abs_error"] is None else f"{f['max_abs_error']:.3g}"
        rt = "—" if f["max_error_ratio"] is None else f"{f['max_error_ratio']:.3g}"
        lines.append(f"| {f['feature_index']} | `{f['feature_name']}` | {f['tolerance_class']} | {f['pass']} | {f['fail']} | "
                     f"{f['review']} | {f.get('not_evaluable', 0)} | {mx} | {rt} |")
    bad = result["rows"].loc[result["rows"].outcome.isin(FAIL_OUTCOMES)]
    if len(bad):
        lines += ["", "## 20 lỗi đầu tiên", "", "| Case | Endpoint | Feature | Kết quả | Chi tiết |", "|---|---:|---|---|---|"]
        for r in bad.head(20).itertuples(index=False):
            lines.append(f"| {r.case_id} | {r.endpoint_index} | `{r.feature_name}` | {r.outcome} | {r.detail} |")
    return "\n".join(lines) + "\n"


def run_comparison(repo_root: Path, suite: str, candidate_path: Path, metadata_path: Path | None = None,
                   out_dir: Path | None = None, title: str | None = None) -> dict:
    repo_root = Path(repo_root)
    expected, cases = load_golden(repo_root, suite)
    candidate = interchange.read_any(candidate_path)
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8")) if metadata_path else None
    result = compare_frames(expected, candidate, cases, metadata)
    metadata_warnings = validate_metadata(metadata, repo_root)
    # Thiếu metadata chỉ làm kết quả không thể quy cho C; metadata hiện diện nhưng
    # khai báo sai schema/manifest/producer phải làm hỏng kết quả parity.
    metadata_failures = [warning for warning in metadata_warnings if not warning.startswith("Không có metadata:")]
    if metadata_failures:
        summary = result["summary"]
        summary["outcome_counts"]["FAIL_METADATA"] = len(metadata_failures)
        summary["fail_records"] += len(metadata_failures)
        prefix = VERDICT_PREFIX.get(summary["producer_kind"], "UNATTRIBUTED")
        summary["verdict"] = f"{prefix}_FAIL"
        summary["metadata_failures"] = metadata_failures
    result["metadata_warnings"] = metadata_warnings
    result["summary"]["metadata_warnings"] = result["metadata_warnings"]
    result["summary"]["suite"] = suite
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        result["rows"].to_csv(out_dir / "comparison_rows.csv", index=False, lineterminator="\n")
        (out_dir / "comparison_summary.json").write_text(
            json.dumps(result["summary"], indent=1, ensure_ascii=False, default=_json_default) + "\n", encoding="utf-8")
        (out_dir / "comparison_report.md").write_text(markdown_report(result, title or f"So sánh parity — suite {suite}"), encoding="utf-8")
    return result


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="So sánh đầu ra feature C/C++ với golden Python (không tự tạo kết quả C).")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--suite", choices=["synthetic", "real"], default="synthetic")
    parser.add_argument("--candidate", type=Path, help="CSV hoặc JSONL theo ml/parity/fixtures/interchange_format.json")
    parser.add_argument("--metadata", type=Path, help="JSON metadata của producer (bắt buộc để được tính là parity C)")
    parser.add_argument("--out", type=Path, help="Thư mục ghi comparison_rows.csv / comparison_summary.json / comparison_report.md")
    parser.add_argument("--self-check", action="store_true",
                        help="So golden_vectors.jsonl với chính golden: kiểm tra harness (PYTHON_SELF_CONSISTENCY, không phải parity C)")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    if args.self_check:
        candidate = root / suite_root(args.suite) / "golden_vectors.jsonl"
        meta_path = (args.out or root / "ml/data/parity/runs/self_check") / "self_check.meta.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta = interchange.metadata_template()
        meta["producer"] = {"kind": "python_reference_self_consistency", "name": "golden_vectors.jsonl"}
        meta["golden_manifest_sha256"] = hashlib.sha256((root / MANIFEST).read_bytes()).hexdigest()
        meta_path.write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
        result = run_comparison(root, args.suite, candidate, meta_path, args.out, "Self-consistency Python (không phải parity C)")
    else:
        if args.candidate is None:
            parser.error("--candidate là bắt buộc (hoặc dùng --self-check).")
        result = run_comparison(root, args.suite, args.candidate, args.metadata, args.out)
    s = result["summary"]
    print(json.dumps({k: s[k] for k in ("verdict", "is_c_parity_evidence", "expected_records", "candidate_records",
                                        "outcome_counts", "missing_cases", "extra_cases", "metadata_warnings")},
                     indent=1, ensure_ascii=False))
    raise SystemExit(0 if not s["fail_records"] else 1)


if __name__ == "__main__":
    main()
