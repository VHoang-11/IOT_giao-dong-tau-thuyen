from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .agreement import inter_reviewer_agreement
from .evidence_audit import audit_label_evidence
from .pilot import prepare_annotation_pilot
from .pilot_decisions import (build_decision_summary, decision_template, load_decisions,
                              materialize_decisions)
from .pilot_reports import create_coverage_figure, write_pilot_reports


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _summarize_review(forms: pd.DataFrame, decisions: pd.DataFrame) -> dict:
    form_reviewed = forms.loc[forms.review_status.isin(("ACCEPTED", "REJECTED", "NEEDS_DISCUSSION"))
                              & forms.reviewer_decision.ne("")]
    form_accepted = form_reviewed.loc[form_reviewed.review_status.eq("ACCEPTED")]
    ledger_materialized = materialize_decisions(forms, decisions)
    ledger_reviewed = ledger_materialized.loc[ledger_materialized.review_status.isin(
        ("ACCEPTED", "REJECTED", "NEEDS_DISCUSSION")) & ledger_materialized.reviewer_decision.ne("")]
    ledger_accepted = ledger_reviewed.loc[ledger_reviewed.review_status.eq("ACCEPTED")]
    decision_source = ledger_accepted if not ledger_accepted.empty else form_accepted
    if "session_id" not in decision_source:
        decision_source = decision_source.merge(forms[["review_sample_id", "session_id"]], on="review_sample_id", how="left")
    classes = ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH", "REVIEW_REQUIRED", "UNLABELED")
    class_counts = {name: int(decision_source.reviewer_decision.eq(name).sum()) for name in classes}
    class_counts["UNLABELED"] = max(class_counts["UNLABELED"], int(forms.label_status.eq("UNLABELED").sum()))
    verified_by_class, human_by_class, proxy_by_class, verified_sessions = {}, {}, {}, {}
    for name in classes:
        if not decision_source.empty and "evidence_category" in decision_source:
            hazard_rows = decision_source.loc[decision_source.reviewer_decision.eq(name)
                & decision_source.evidence_category.eq("VERIFIED_OPERATIONAL_HAZARD")]
            normal_rows = decision_source.loc[decision_source.reviewer_decision.eq(name)
                & decision_source.evidence_category.eq("VERIFIED_NORMAL_ENVELOPE")]
            verified_rows = normal_rows if name == "NORMAL" else hazard_rows
            human_rows = decision_source.loc[decision_source.reviewer_decision.eq(name)
                & decision_source.evidence_category.eq("OBSERVED_MOTION_PHENOTYPE")]
            proxy_rows = decision_source.loc[decision_source.reviewer_decision.eq(name)
                & decision_source.evidence_category.eq("PROXY_RULE")]
        else:
            verified_rows = human_rows = proxy_rows = pd.DataFrame()
            hazard_rows = normal_rows = pd.DataFrame()
        verified_by_class[name] = int(len(verified_rows))
        human_by_class[name] = int(len(human_rows))
        proxy_by_class[name] = int(len(proxy_rows))
        verified_sessions[name] = int(verified_rows.session_id.nunique()) if len(verified_rows) else 0
    agreement = inter_reviewer_agreement(decisions)
    ledger_rows = len(ledger_reviewed)
    reviewed_count = max(int(len(form_reviewed)), ledger_rows)
    return {"reviewed_decisions": reviewed_count,
        "human_reviewed_labels": sum(human_by_class.get(x, 0) for x in classes),
        "verified_operational_hazard_labels": int(sum(1 for _, row in decision_source.iterrows()
            if row.get("evidence_category") == "VERIFIED_OPERATIONAL_HAZARD")),
        "verified_normal_envelope_labels": int(sum(1 for _, row in decision_source.iterrows()
            if row.get("evidence_category") == "VERIFIED_NORMAL_ENVELOPE")),
        "external_reference_labels": int(sum(1 for _, row in decision_source.iterrows()
            if row.get("label_status") == "VERIFIED")),
        "proxy_labels": sum(proxy_by_class.get(x, 0) for x in classes),
        "unlabeled_or_pending": int(forms.label_status.eq("UNLABELED").sum()),
        "ambiguous_samples": int(forms.review_status.eq("NEEDS_DISCUSSION").sum()),
        "overlapping_phenotype_samples": int(sum(sum(v is True for v in json.loads(text).values()) > 1
            for text in forms.phenotype_flags_json)),
        "class_counts": class_counts, "verified_by_class": verified_by_class,
        "human_reviewed_by_class": human_by_class, "proxy_by_class": proxy_by_class,
        "verified_sessions_by_class": verified_sessions,
        "reviewer_agreement": agreement}


def _run_tests(repo_root: Path) -> dict:
    command = [sys.executable, "-m", "pytest", "ml/labeling/tests", "ml/features/tests",
               "ml/preprocessing/tests", "ml/audit", "-q"]
    proc = subprocess.run(command, cwd=repo_root, text=True, capture_output=True)
    output = (proc.stdout + proc.stderr).strip()
    last = output.splitlines()[-1] if output else "Không có output kiểm thử."
    passed = int(last.split(" passed")[0].split()[-1]) if " passed" in last else 0
    return {"command": "python -m pytest ml/labeling/tests ml/features/tests ml/preprocessing/tests ml/audit -q",
            "exit_code": int(proc.returncode), "passed": passed,
            "failed": 0 if proc.returncode == 0 else 1, "result_summary": last}


def run_pilot(repo_root: Path, queue_path: Path | None = None, context_seconds: float = 180.0,
              dpi: int = 100) -> dict:
    repo_root = repo_root.resolve()
    queue_path = queue_path or repo_root / "ml/data/labels/review_queue.csv"
    output_root = repo_root / "ml/data/labels/annotation_pilot"
    report_root = repo_root / "ml/reports/labeling"
    form_path = output_root / "annotation_pilot.csv"
    decision_path = output_root / "review_decisions.csv"
    started = time.perf_counter()

    forms, form_summary = prepare_annotation_pilot(repo_root, queue_path, output_root,
        context_seconds=context_seconds, dpi=dpi, existing_form_path=form_path if form_path.exists() else None)
    output_root.mkdir(parents=True, exist_ok=True)
    forms.to_csv(form_path, index=False)
    if not decision_path.exists():
        decision_template().to_csv(decision_path, index=False)
    decisions = load_decisions(decision_path, set(forms.review_sample_id))
    review_stats = _summarize_review(forms, decisions)
    audit = audit_label_evidence(repo_root, queue_path, form_path)
    # The reviewer ledger is authoritative for multi-reviewer agreement; absent entries, retain form-derived status.
    if not decisions.empty:
        audit["reviewed_decisions"] = int((decisions.review_status.isin(("ACCEPTED", "REJECTED", "NEEDS_DISCUSSION"))
                                           & decisions.reviewer_decision.ne("")).sum())
        processed_ledger = decisions.loc[decisions.review_status.isin(("ACCEPTED", "REJECTED", "NEEDS_DISCUSSION"))
                                        & decisions.reviewer_decision.ne("")]
        audit["reviewed_samples"] = int(processed_ledger.review_sample_id.nunique())
        audit["pending_or_unreviewed"] = int(len(forms) - min(len(forms), audit["reviewed_samples"]))
        audit["human_reviewed_labels"] = review_stats["human_reviewed_labels"]
        audit["verified_operational_hazard_labels"] = review_stats["verified_operational_hazard_labels"]
        audit["verified_normal_envelope_labels"] = review_stats["verified_normal_envelope_labels"]
        audit["external_reference_labels"] = review_stats["external_reference_labels"]
        audit["inter_reviewer_agreement"] = review_stats["reviewer_agreement"]
        ledger_rows = materialize_decisions(forms, decisions)
        for dataset, item in audit["datasets"].items():
            subset = ledger_rows.loc[ledger_rows.dataset_source.eq(dataset)]
            item["reviewed_decisions"] = int(len(subset))
            item["reviewed_samples"] = int(subset.review_sample_id.nunique())
            accepted = subset.loc[subset.review_status.eq("ACCEPTED")]
            item["class_decision_counts"] = {label: int(accepted.reviewer_decision.eq(label).sum())
                for label in ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH", "REVIEW_REQUIRED", "UNLABELED")}
            item["human_reviewed_labels"] = int(subset.label_status.eq("HUMAN_REVIEWED").sum())
            item["verified_operational_hazard_labels"] = int((subset.label_status.eq("VERIFIED")
                & subset.evidence_category.eq("VERIFIED_OPERATIONAL_HAZARD")).sum())
            item["verified_normal_envelope_labels"] = int((subset.label_status.eq("VERIFIED")
                & subset.evidence_category.eq("VERIFIED_NORMAL_ENVELOPE")).sum())
            item["external_reference_labels"] = int(subset.label_status.eq("VERIFIED").sum())

    coverage_figure = output_root / "figures" / "evidence_coverage.png"
    create_coverage_figure(forms, coverage_figure, dpi)
    test_results = _run_tests(repo_root)
    summary = {**form_summary, **review_stats,
        "pilot_version": "0.1.0", "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "repository_root": ".", "queue_path": queue_path.relative_to(repo_root).as_posix(),
        "annotation_form_path": form_path.relative_to(repo_root).as_posix(),
        "review_decision_ledger_path": decision_path.relative_to(repo_root).as_posix(),
        "diagnostic_figure_path": coverage_figure.relative_to(repo_root).as_posix(),
        "source_evidence_summary_path": "ml/reports/labeling/label_evidence_summary.json",
        "evidence_audit": audit, "test_results": test_results,
        "environment": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__},
        "elapsed_seconds": time.perf_counter() - started,
        "scope_note_vi": "Chỉ annotation pilot; không gán tự động ground truth, không train và không sửa feature/raw/preprocessing artifacts."}
    _write_json(output_root / "annotation_pilot_summary.json", summary)
    _write_json(output_root / "label_evidence_audit.json", audit)
    write_pilot_reports(repo_root, audit, forms, summary,
                        {"agreement": review_stats["reviewer_agreement"]}, report_root, coverage_figure)
    print(f"[THÔNG TIN] Đã chuẩn bị {len(forms)} hồ sơ annotation; quyết định reviewer thực tế: {summary['reviewed_decisions']}.")
    print(f"[THÔNG TIN] Báo cáo evidence: {report_root / 'label_evidence_report.md'}")
    print(test_results["result_summary"])
    if test_results["exit_code"] != 0:
        raise RuntimeError("Kiểm thử liên quan thất bại; xem output ở trên.")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Chuẩn bị hồ sơ Label Evidence & Annotation Pilot.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--queue", type=Path, default=None)
    parser.add_argument("--context-seconds", type=float, default=180.0)
    parser.add_argument("--dpi", type=int, default=100)
    args = parser.parse_args()
    queue = args.queue
    if queue is not None and not queue.is_absolute():
        queue = args.repo_root / queue
    run_pilot(args.repo_root, queue, args.context_seconds, args.dpi)


if __name__ == "__main__":
    main()
