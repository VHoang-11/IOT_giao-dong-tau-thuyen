from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


DATASETS = ("seafar", "hohai", "southampton")


def _matching_provenance(repo_root: Path, dataset: str, session: str, segment: str) -> tuple[dict, str]:
    for path in (repo_root / "ml/data/processed" / dataset).glob("**/provenance.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if str(payload.get("session_id")) == str(session) and str(payload.get("segment_id")) == str(segment):
            return payload, path.relative_to(repo_root).as_posix()
    raise FileNotFoundError(f"Thiếu provenance cho {dataset}/{session}/{segment}.")


def audit_label_evidence(repo_root: Path, queue_path: Path | None = None,
                         form_path: Path | None = None) -> dict:
    queue_path = queue_path or repo_root / "ml/data/labels/review_queue.csv"
    if not queue_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy review queue hiện hành: {queue_path}")
    queue = pd.read_csv(queue_path)
    required = {"dataset", "session", "segment", "window_start", "window_end", "suggested_label",
                "reviewer_decision", "reviewer_notes", "review_timestamp", "review_status"}
    if missing := required - set(queue.columns):
        raise ValueError(f"Review queue thiếu cột: {sorted(missing)}")
    forms = pd.read_csv(form_path) if form_path and form_path.is_file() else pd.DataFrame()
    effective = forms if not forms.empty else queue
    source_column = "dataset_source" if "dataset_source" in effective.columns else "dataset"
    has_decision = effective.get("reviewer_decision", pd.Series(dtype=object)).fillna("").astype(str).str.strip().ne("")
    reviewed_status = effective.get("review_status", pd.Series(dtype=object)).fillna("").isin(("ACCEPTED", "REJECTED", "NEEDS_DISCUSSION"))
    review_count = int((has_decision & reviewed_status).sum())
    review_sample_count = int(effective.loc[has_decision & reviewed_status,
        "review_sample_id"].nunique()) if "review_sample_id" in effective else review_count
    evidence_category = effective.get("evidence_category", pd.Series(index=effective.index, dtype=object))
    label_status = effective.get("label_status", pd.Series(index=effective.index, dtype=object))
    result = {"evidence_audit_version": "0.1.0", "queue_path": queue_path.relative_to(repo_root).as_posix(),
              "candidate_samples": int(len(queue)), "reviewed_decisions": review_count,
              "reviewed_samples": review_sample_count,
              "pending_or_unreviewed": int(len(queue) - min(len(queue), review_sample_count)),
              "verified_operational_hazard_labels": int((label_status.eq("VERIFIED") & evidence_category.eq("VERIFIED_OPERATIONAL_HAZARD")).sum()),
              "verified_normal_envelope_labels": int((label_status.eq("VERIFIED") & evidence_category.eq("VERIFIED_NORMAL_ENVELOPE")).sum()),
              "external_reference_labels": int(label_status.eq("VERIFIED").sum()),
              "human_reviewed_labels": int(label_status.eq("HUMAN_REVIEWED").sum()),
              "inter_reviewer_agreement": {"status": "NOT_CALCULATED", "reason_vi": "Chưa có ít nhất hai reviewer với quyết định chồng lặp thực tế."},
              "overlap_warning_vi": "Các cửa sổ 180 giây stride 10 giây chồng lấn xấp xỉ 94,4%; chúng không phải quan sát độc lập.",
              "datasets": {}}
    raw_references = {
        "seafar": ["ml/data/raw/seafar/cleaned_imu_gps_data.json", "ml/audit/real_dataset_audit_report.md"],
        "hohai": ["ml/data/raw/hohai/6-DOF ship motions Data.xlsx", "ml/data/raw/hohai/Data Description Example.pdf", "ml/audit/real_dataset_audit_report.md"],
        "southampton": ["ml/data/raw/southampton/Readme/README.txt", "ml/data/raw/southampton/Readme/KCS Test Plan June 2023.xlsx", "ml/audit/real_dataset_audit_report.md"],
    }
    for dataset in DATASETS:
        rows = queue.loc[queue.dataset.eq(dataset)]
        form_rows = effective.loc[effective[source_column].eq(dataset)]
        provenance = []
        for row in rows.itertuples(index=False):
            record, path = _matching_provenance(repo_root, dataset, row.session, row.segment)
            provenance.append((record, path))
        sessions = sorted(rows.session.astype(str).unique().tolist())
        metadata_by_session = {}
        for session in sessions:
            matching = [record for record, _ in provenance if str(record.get("session_id")) == session]
            if not matching:
                continue
            item = matching[0]
            if dataset == "southampton":
                metadata_by_session[session] = {"raw_run_id": item.get("raw_run_id"),
                    "wave_condition_test_plan_provenance": item.get("wave_condition_test_plan_provenance", []),
                    "metadata_is_provenance_only": True,
                    "metadata_reference": "ml/data/raw/southampton/Readme/KCS Test Plan June 2023.xlsx"}
            elif dataset == "hohai":
                metadata_by_session[session] = {"raw_sheet": item.get("raw_sheet"),
                    "original_sampling_hz": item.get("original_sampling_hz"),
                    "timestamp_source": item.get("timestamp_source"), "warnings": item.get("warnings", [])}
            else:
                metadata_by_session[session] = {"raw_reference": item.get("raw_reference"),
                    "timestamp_source": item.get("timestamp_source"),
                    "original_sampling_hz": item.get("original_sampling_hz"), "warnings": item.get("warnings", [])}
        class_counts = {label: int(form_rows.get("reviewer_decision", pd.Series(index=form_rows.index, dtype=object)).eq(label).sum())
                        for label in ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH", "REVIEW_REQUIRED", "UNLABELED")}
        result["datasets"][dataset] = {
            "pilot_samples": int(len(rows)), "independent_sessions": len(sessions), "session_ids": sessions,
            "samples_by_session": {str(key): int(value) for key, value in rows.groupby("session").size().items()},
            "reviewed_decisions": int((has_decision.loc[form_rows.index] & reviewed_status.loc[form_rows.index]).sum()),
            "reviewed_samples": int(form_rows.loc[form_rows.get("review_status", pd.Series(index=form_rows.index, dtype=object)).isin(("ACCEPTED", "REJECTED", "NEEDS_DISCUSSION")), "review_sample_id"].nunique()) if "review_sample_id" in form_rows else 0,
            "human_reviewed_labels": int(form_rows.get("label_status", pd.Series(index=form_rows.index, dtype=object)).eq("HUMAN_REVIEWED").sum()),
            "verified_operational_hazard_labels": int((form_rows.get("label_status", pd.Series(index=form_rows.index, dtype=object)).eq("VERIFIED") & form_rows.get("evidence_category", pd.Series(index=form_rows.index, dtype=object)).eq("VERIFIED_OPERATIONAL_HAZARD")).sum()),
            "verified_normal_envelope_labels": int((form_rows.get("label_status", pd.Series(index=form_rows.index, dtype=object)).eq("VERIFIED") & form_rows.get("evidence_category", pd.Series(index=form_rows.index, dtype=object)).eq("VERIFIED_NORMAL_ENVELOPE")).sum()),
            "external_reference_labels": int(form_rows.get("label_status", pd.Series(index=form_rows.index, dtype=object)).eq("VERIFIED").sum()),
            "class_decision_counts": class_counts,
            "ambiguous_samples": int(form_rows.get("review_status", pd.Series(index=form_rows.index, dtype=object)).eq("NEEDS_DISCUSSION").sum()),
            "overlapping_phenotype_samples": int(sum(len([v for v in json.loads(text).values() if v is True]) > 1
                for text in form_rows.get("phenotype_flags_json", pd.Series(dtype=str)).dropna().astype(str))),
            "sessions_with_experiment_context": int(sum(bool(x.get("wave_condition_test_plan_provenance")) or bool(x.get("raw_sheet")) for x in metadata_by_session.values())),
            "source_documentation": raw_references[dataset], "session_metadata": metadata_by_session,
        }
    result["evidence_conclusions"] = {
        "seafar": {"independent_operating_condition_annotations": 0,
                   "finding_vi": "JSON là telemetry theo thời gian; không thấy trường event/incident/operating-state độc lập. Một session tàu thật; offset gốc và lineage trục/rate cần lưu ý.",
                   "unsupported_claims_vi": ["Không thể gọi Roll offset khác 0 là hazard hoặc NORMAL.", "Không thể kết luận HIGH_ROLL/PERSISTENT_OFFSET/AMPLITUDE_GROWTH từ thống kê đơn lẻ." ]},
        "hohai": {"independent_operating_condition_annotations": 0,
                   "finding_vi": "Workbook có 21 sheet/session và tên sheet chứa thông tin berth/test/type; đây là định danh cấu hình thử nghiệm, không phải nhãn trạng thái an toàn. Nguồn là mô hình thử nghiệm, thời gian suy từ 50 Hz; không có timestamp/gyro đo trực tiếp.",
                   "unsupported_claims_vi": ["Không diễn giải hậu tố Type_A/B/C thành phenotype/hazard.", "Không tuyên bố dữ liệu mô hình đại diện trực tiếp cho tàu full-scale." ]},
        "southampton": {"independent_operating_condition_annotations": 0,
                        "finding_vi": "Test Plan mô tả điều kiện thử nghiệm theo Run ID; các giá trị wave frequency/amplitude chỉ là provenance. Run 14 có điều kiện trong metadata nhưng không kèm nhãn hazard hay event reference.",
                        "unsupported_claims_vi": ["Không suy hazard từ wave amplitude/frequency.", "Không coi Delta Angle là gyro canonical khi semantics/trục chưa xác nhận.", "Chỉ Run 14 có cửa sổ 180 giây; 4 mẫu pilot trong run này không phải 4 session độc lập." ]},
    }
    return result


def write_evidence_report(summary: dict, report_path: Path, json_path: Path) -> None:
    lines = ["# Kiểm kê bằng chứng nhãn và điều kiện vận hành", "",
             "## Kết luận", "",
             f"Review queue hiện có **{summary['candidate_samples']} mẫu** trên ba nguồn; đã tìm thấy **{summary['external_reference_labels']} nhãn external**, **{summary['human_reviewed_labels']} nhãn human-reviewed** và **{summary['verified_operational_hazard_labels']} nhãn hazard vận hành được xác minh**. Chưa có cơ sở tính inter-reviewer agreement. Đây là kết quả kiểm kê artifact/tài liệu hiện có, không phải kết luận các trạng thái vật lý không tồn tại.", "",
             "## Độ phủ bằng chứng theo nguồn và session", "",
             "| Nguồn | Mẫu pilot | Session độc lập | Session có metadata thử nghiệm | Quyết định reviewer | Mẫu đã review | Hazard reference | Normal envelope |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for dataset, item in summary["datasets"].items():
        lines.append(f"| {dataset.capitalize()} | {item['pilot_samples']} | {item['independent_sessions']} | {item['sessions_with_experiment_context']} | {item['reviewed_decisions']} | {item['reviewed_samples']} | {item['verified_operational_hazard_labels']:,} | {item['verified_normal_envelope_labels']:,} |")
    lines += ["", "Session được tính theo định danh nguồn, không theo số cửa sổ. Nhiều cửa sổ trong một session không tăng số phiên độc lập.", ""]
    for dataset, item in summary["datasets"].items():
        conclusion = summary["evidence_conclusions"][dataset]
        lines += [f"## {dataset.capitalize()}", "", conclusion["finding_vi"], "",
                  "| Session | Số mẫu trong pilot | Metadata thực nghiệm |", "|---|---:|---|"]
        for session, count in item["samples_by_session"].items():
            metadata = item["session_metadata"].get(session, {})
            if dataset == "hohai":
                rate = metadata.get("original_sampling_hz")
                rate_text = f"{float(rate):.3g} Hz (metadata)" if rate is not None else "Sampling Rate chưa rõ"
                description = f"sheet `{metadata.get('raw_sheet','')}`; {rate_text}; {metadata.get('timestamp_source')}"
            elif dataset == "southampton":
                conditions = metadata.get("wave_condition_test_plan_provenance", [])
                if conditions:
                    details = []
                    for condition in conditions:
                        details.append(f"run {condition.get('run_id')}, {condition.get('test_type')}, "
                            f"wave {float(condition['wave_frequency_hz']):.4f} Hz, "
                            f"biên độ {float(condition['wave_amplitude_m']):.5f} m (provenance)")
                    description = "; ".join(details)
                else:
                    description = "Không có điều kiện wave trong Test Plan cho run này"
            else:
                description = f"nguồn `{metadata.get('raw_reference','')}`; không có trường operating condition độc lập"
            lines.append(f"| `{session}` | {count} | {description} |")
        lines += ["", "**Các tuyên bố không được hỗ trợ:**", ""] + [f"- {claim}" for claim in conclusion["unsupported_claims_vi"]] + [""]
    lines += ["## Nguồn đã kiểm tra", ""]
    all_sources = sorted({path for item in summary["datasets"].values() for path in item["source_documentation"]})
    lines += [f"- `{path}`" for path in all_sources]
    lines += ["", "## Cảnh báo thiết kế", "", summary["overlap_warning_vi"],
              "Không có nhãn độc lập để xác nhận NORMAL, HIGH_ROLL, PERSISTENT_OFFSET hay AMPLITUDE_GROWTH. Điều kiện vật lý trong workbook/Test Plan không được chuyển thành target label. Xem [báo cáo feasibility trước đó](labeling_feasibility_report.md) để biết giới hạn window eligibility.", ""]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
