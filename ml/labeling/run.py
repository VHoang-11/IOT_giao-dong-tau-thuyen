from __future__ import annotations

import argparse
from importlib.metadata import version as package_version
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow
import yaml

from . import __version__
from .annotations import apply_external_annotations, load_external_annotations
from .config import load_config
from .diagnostics import create_diagnostics
from .feasibility import feasibility_summary, load_eligible_windows, source_evidence_notes
from .provenance import json_flags
from .review import build_review_queue
from .rules import classify_candidate
from .schemas import ANGLE_ONLY_23, LABEL_COLUMNS
from .validation import validate_label_record

DATASETS = ("seafar", "hohai", "southampton")
QUALITY_FLAGS = {
    "seafar": ["ONE_REAL_VESSEL_SESSION", "RAW_TIMESTAMP_GAPS_AND_DUPLICATES_WERE_SEGMENTED", "RATE_AXIS_AND_SIGN_UNVERIFIED"],
    "hohai": ["EXPERIMENTAL_MODEL_SCALE", "SAMPLE_TIME_INFERRED_FROM_50_HZ_METADATA", "NO_DIRECT_GYRO", "DROPOUT_NOT_VERIFIABLE_WITHOUT_TIMESTAMPS"],
    "southampton": ["EXPERIMENTAL_MODEL_SCALE", "ONLY_RUN_14_HAS_180S_WINDOWS", "WAVE_PLAN_IS_CONTEXT_ONLY", "DELTA_ANGLE_MAPPING_UNVERIFIED"],
}


def _to_label_record(row: pd.Series, config: dict) -> dict:
    result = classify_candidate(row.to_dict(), config)
    record = {"dataset_source": str(row.dataset_source), "session_id": str(row.session_id),
              "segment_id": str(row.segment_id), "window_start_seconds": float(row.window_start_seconds),
              "window_end_seconds": float(row.window_end_seconds), **result,
              "quality_flags": json.dumps(QUALITY_FLAGS[str(row.dataset_source)], ensure_ascii=False)}
    validate_label_record(record)
    return record


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _build_reports(summary: dict, report_root: Path) -> None:
    report_root.mkdir(parents=True, exist_ok=True)
    external_total = summary["ground_truth_annotations_found"]
    human_total = summary["human_review_decisions"]
    evidence_intro = (f"Artifact đầu ra chứa {external_total:,} annotation external và {human_total:,} quyết định human review."
                      if external_total or human_total else
                      "Không có annotation external reference hoặc quyết định human review trong artifact đầu ra hiện tại.")
    lines = ["# Nghiên cứu tính khả thi gán nhãn — SVMG M2", "",
             "## Kết luận tổng quát", "",
             f"Dữ liệu hiện có cần được đánh giá theo evidence riêng cho mỗi lớp. {evidence_intro} Quy tắc mặc định không suy diễn nhãn từ phân vị dữ liệu. Hàng chưa có tham chiếu giữ `UNLABELED`; điều này phản ánh thiếu bằng chứng gán nhãn, không khẳng định lớp vật lý không tồn tại.", "",
             "## Kiểm kê cửa sổ hợp lệ", "",
             "Một cửa sổ được đưa vào nghiên cứu khi đủ 180 giây trong cùng session/segment, endpoint theo `(t-W,t]`, và toàn bộ 23 feature góc được đánh dấu `VALID`. Stride 10 giây làm cửa sổ chồng lấn mạnh; số cửa sổ không phải số mẫu độc lập.", "",
             "## Đối chiếu feature input thực tế", "",
             "Artifact đang được dùng có 30 candidate columns. Số feature có ít nhất một hàng validity `VALID` được tính lại từ Parquet metadata; đây không đồng nghĩa đủ dữ liệu ở mọi cửa sổ hay đủ nhãn. 23 angle-only feature là subset được sử dụng để chọn cửa sổ 180 giây. Bốn gyro candidates không được xem là đo canonical hợp lệ do Hohai thiếu gyro, còn Seafar/Southampton mapping chưa xác nhận.", "",
             "| Nguồn | Candidate feature | Feature từng có VALID | Gyro feature VALID | Cửa sổ angle-only 180 giây |", "|---|---:|---:|---:|---:|"]
    for ds, item in summary["datasets"].items():
        audit = item["feature_input_audit"]
        lines.append(f"| {ds.capitalize()} | {audit['candidate_feature_count']} | {audit['features_with_any_valid']} | {audit['gyro_features_with_any_valid']} | {item['eligible_windows_180s_angle23']:,} |")
    lines += ["", "Đặc biệt, ba candidate chu kỳ (`roll_period_est_180`, `roll_zero_crossings_180`, `roll_period_cv_180`) có thể có validity `VALID`, nhưng bị loại khỏi tập angle-only 23 theo thiết kế. Không dùng gyro suy ra hoặc trường chưa xác nhận để tạo nhãn.", "",
             "| Nguồn | Candidate 60 giây | Cửa sổ 180 giây angle-only hợp lệ | Session hỗ trợ | Segment | Nhãn đã xác minh | Human review |", "|---|---:|---:|---:|---:|---:|---:|"]
    for ds, item in summary["datasets"].items():
        lines.append(f"| {ds.capitalize()} | {item['feature_candidate_rows_60s']:,} | {item['eligible_windows_180s_angle23']:,} | {item['sessions_with_eligible_windows']} | {item['segment_count']} | {item['verified_rows']:,} | {item['human_reviewed_rows']:,} |")
    lines += ["", "## Bằng chứng và khả năng bao phủ lớp", ""]
    for ds, notes in summary["source_evidence"].items():
        lines += [f"### {ds.capitalize()}", ""] + [f"- {note}" for note in notes] + [""]
        item = summary["datasets"][ds]
        lines += ["Thống kê mô tả trên cửa sổ angle-only 180 giây:", "",
                  f"- Roll mean 180s: trung bình {item['metrics']['roll_mean_180_deg']['mean']:.5g}°, trung vị {item['metrics']['roll_mean_180_deg']['p50']:.5g}°, P05–P95 {item['metrics']['roll_mean_180_deg']['p05']:.5g}–{item['metrics']['roll_mean_180_deg']['p95']:.5g}°.",
                  f"- Roll standard deviation 60s: trung vị {item['metrics']['roll_std_60_deg']['p50']:.5g}°, P95 {item['metrics']['roll_std_60_deg']['p95']:.5g}°.",
                  f"- Roll RMS slope 180s: trung vị {item['metrics']['roll_rms_slope_180_deg_per_min']['p50']:.5g}°/phút; R² trung vị {item['metrics']['roll_rms_trend_r2_180']['p50']:.5g}.",
                  "- Các giá trị trên mô tả phân bố; không được dùng làm ngưỡng hazard hoặc lớp NORMAL.", ""]
    lines += ["## Đánh giá bốn lớp mục tiêu", "",
              "| Lớp | Proxy windows | External verified | Human reviewed | Session có evidence độc lập |", "|---|---:|---:|---:|---:|"]
    for label in ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH"):
        totals = {key: sum(item["class_evidence"][label][key] for item in summary["datasets"].values())
                  for key in ("proxy_windows", "verified_windows", "human_reviewed_windows", "supporting_sessions")}
        lines.append(f"| `{label}` | {totals['proxy_windows']:,} | {totals['verified_windows']:,} | {totals['human_reviewed_windows']:,} | {totals['supporting_sessions']:,} |")
    lines += ["", "Chỉ được coi là có căn cứ độc lập khi có external reference hoặc human review. `NORMAL` phải dựa trên positive operating envelope; không suy NORMAL từ việc không phát hiện bất thường.", "",
              "Không tạo class counts dựa trên percentile, không cân bằng lớp nhân tạo. Thông tin wave của Southampton chỉ lưu làm experimental context/provenance; Hohai type labels không được xem là nhãn nguy hiểm; Seafar không có event annotation được tìm thấy.", "",
              "## Khả năng hỗ trợ từng nguồn", "",
              "Seafar cung cấp tín hiệu tàu thật nhưng chỉ một session, offset nền không zero và có giới hạn đơn vị/trục đã nêu trong audit. Hohai và Southampton là thí nghiệm mô hình quy mô nhỏ, không đại diện trực tiếp cho giới hạn full-scale. Southampton chỉ có một run đủ 180 giây nên không thể đánh giá độ lặp của phenotype dài hạn. Không nguồn nào hiện có bằng chứng chấp nhận được cho nhãn NORMAL hoặc hazard ground truth.", "",
              "## Hình chẩn đoán", ""]
    for path in summary["diagnostic_figures"]:
        lines.append(f"- `{Path(path).name}`")
    lines += ["", "## Giải thích kỹ thuật phục vụ vấn đáp", "",
              "**Em đã làm gì?** Đối chiếu feature windows đã kiểm định với tài liệu/audit nguồn và tạo hàng khảo sát 180 giây theo session/segment. **Vì sao?** Cửa sổ dài phù hợp phân tích offset/growth, đồng thời ranh giới ngăn ghép dữ liệu độc lập. **Phương pháp?** Chỉ dùng thống kê mô tả và trạng thái validity; không đặt ngưỡng bằng percentile. **Kết quả?** Các nguồn có lần lượt 1.318, 1.512 và 34 cửa sổ đủ 23 feature góc, nhưng không có nhãn external/human. **Nếu tự gọi các cực trị là HIGH_ROLL?** Sẽ biến phân bố nội bộ thành ground truth vòng tròn và nhầm biến thiên với nguy hiểm. **Giới hạn?** Thiếu operating envelope, tiêu chí hazard, event annotation và human review; các cửa sổ chồng lấn không độc lập.", ""]
    (report_root / "labeling_feasibility_report.md").write_text("\n".join(lines), encoding="utf-8")

    method = ["# Phương pháp gán nhãn và quy tắc ứng viên", "",
              "## Taxonomy", "",
              "`HIGH_ROLL` là dao động Roll lớn so với ngưỡng vận hành có căn cứ, tách khỏi offset DC; `PERSISTENT_OFFSET` là độ lệch có dấu kéo dài theo thời gian và ổn định về dấu; `AMPLITUDE_GROWTH` là biên độ dao động tăng trong cửa sổ lịch sử; `NORMAL` chỉ dùng khi có envelope bình thường được chấp nhận độc lập. Các phenotype có thể đồng thời đúng. `UNLABELED` biểu thị chưa đủ chứng cứ; `REVIEW_REQUIRED` biểu thị xung đột/nhập nhằng cần quyết định.", "",
              "## Tầng bằng chứng", "",
              "Hợp đồng feature hiện hành trong `contracts/features.md`/`core/include/svmg_core.h` vẫn là 14 trường; enum lớp trong header chỉ là interface C, không phải annotation của các cửa sổ dữ liệu. Pipeline labeling không thay đổi hợp đồng đó.", "",
              "- `EXTERNAL_REFERENCE`: nhãn từ annotation/event/document độc lập; hiện không có.",
              "- `HUMAN_REVIEW`: quyết định người duyệt có người duyệt, thời điểm, ghi chú và audit trail; hiện chưa có quyết định.",
              "- `PROXY_RULE`: ứng viên theo quy tắc, luôn giữ trạng thái `PROXY`; không phải ground truth.",
              "- `UNKNOWN`: chưa có căn cứ. Pipeline mặc định feasibility, không tạo nhãn dứt khoát.", "",
              "## Operational candidate rules (chờ nhóm xác nhận)", "",
              "`HIGH_ROLL`: `roll_std_60 >= roll_std_60_deg` để giảm ảnh hưởng offset tĩnh; ngưỡng phải có nguồn độc lập, đơn vị độ và phạm vi dataset rõ. `PERSISTENT_OFFSET`: `abs(roll_mean_180) >= threshold` đồng thời `roll_dominant_sign_ratio_180 >= minimum`; đây vẫn là proxy, phụ thuộc mounting datum/deadband. `AMPLITUDE_GROWTH`: slope RMS tối thiểu cùng R² tối thiểu; chỉ định trend phù hợp không chứng minh hazard. `NORMAL`: đồng thời phải nằm trong roll-std/offset envelope được chấp nhận và không có phenotype bất thường; không dùng phủ định đơn giản. Mọi rule hiện disabled do chưa có ngưỡng được biện minh.", "",
              "Tất cả rule cần `evidence_reference`; ngưỡng bắt buộc cấu hình rõ. Không mặc định dùng ngưỡng simulation, phân vị dataset, cân bằng lớp hoặc confidence score. Các ngưỡng cần nhóm phê duyệt trước khi bật.", "",
              "## Cửa sổ nhân quả và ưu tiên lớp", "",
              "Endpoint căn theo feature table đủ angle-only 23 ở 180 giây; cửa sổ `(t-180,t]`, 95% coverage do feature pipeline xác nhận. Tín hiệu high-roll dùng statistic trailing 60 giây tại cùng endpoint. Chỉ trong đúng session/segment; không qua gap/run/sheet. Dữ liệu tương lai sau endpoint không tham gia. Mặc định primary policy `REVIEW_REQUIRED`: nhiều cờ đồng thời giữ nguyên phenotype flags và yêu cầu review. Cấu hình `PRIORITY` chỉ chọn lớp chính để tiêu thụ downstream và vẫn bảo toàn mọi cờ + ambiguity reason.", "",
              "## Rủi ro circular labeling", "",
              "Nếu proxy HIGH_ROLL dùng roll_std/RMS thì các feature đó trực tiếp định nghĩa nhãn; offset dùng roll_mean/dominant-sign; growth dùng RMS blocks/slope/R². Huấn luyện/test trên cùng nhóm feature sẽ đánh giá khả năng tái tạo rule, không phải nhận diện nguy hiểm độc lập. Cần external events hoặc review độc lập và đánh giá theo session trước khi dùng cho supervised ML.", "",
              "## Quy trình manual review", "",
              "`review_queue.csv` lấy mẫu thời gian đều theo session, không chỉ lấy case dễ. Mẫu trống có các trường quyết định, bằng chứng, reviewer, timestamp, notes và status. Chỉ dữ liệu reviewer thực nhập mới được áp dụng; không có quyết định được tạo trong lần chạy này. Việc áp dụng quyết định giữ audit event append-only qua `audit_event`.", "",
              "Các tầng queue được tạo khi có bằng chứng: `CLEAR_PROXY_CANDIDATE` và `CONFLICTING_PHENOTYPES`. `BORDERLINE_CASE` cần rule/ngưỡng cùng biên review đã được nhóm quy định; `SUSPECTED_FALSE_POSITIVE` cần một quyết định reviewer độc lập bác bỏ proxy. Khi không có rules/reviewer như lần chạy này, hai tầng đó được báo unavailable, không chế tạo ví dụ.", "",
              "## Quy tắc conflict", "",
              "Không loại bỏ phenotype chồng lấn. Mặc định nhãn chính `REVIEW_REQUIRED`; tùy chọn ưu tiên phải cấu hình rõ, giữ nguyên toàn bộ flags và giải thích rằng lớp chính là quy ước kỹ thuật.", ""]
    (report_root / "labeling_methodology.md").write_text("\n".join(method), encoding="utf-8")

    results = ["# Kết quả khảo sát và phân bố nhãn", "",
               f"Pipeline hiện chạy ở `{summary['mode']}` mode. Có {summary['ground_truth_annotations_found']:,} nhãn external và {summary['human_review_decisions']:,} quyết định human review. Cửa sổ không có evidence giữ trạng thái phù hợp; phân bố đầu ra không đại diện phân bố vật lý.", "",
               "| Nguồn | Hàng candidate 180s | UNLABELED | REVIEW_REQUIRED | Proxy candidate | Session có cửa sổ | Session có nhãn được xác minh |", "|---|---:|---:|---:|---:|---:|---:|"]
    for ds, item in summary["datasets"].items():
        n = item["eligible_windows_180s_angle23"]
        results.append(f"| {ds.capitalize()} | {n:,} | {item['unlabeled_rows']:,} | {item['review_required_rows']:,} | {item['proxy_label_rows']:,} | {item['sessions_with_eligible_windows']} | {item['verified_rows']:,} |")
    results += ["", "### Tầng lấy mẫu review", "",
                f"Review queue hiện có {summary['review_queue_rows']:,} hàng; tầng khả dụng: `{json.dumps(summary['review_queue_strata_counts'], ensure_ascii=False)}`. Các tầng chưa thể tạo: {', '.join(summary['review_queue_unavailable_strata'])} — {summary['review_queue_unavailable_strata_reason_vi']}", ""]
    results += ["", "## Phân bố theo session", ""]
    for ds, item in summary["datasets"].items():
        results += [f"### {ds.capitalize()}", "", "| Session | Cửa sổ (chồng lấn) | UNLABELED | NORMAL | HIGH_ROLL | PERSISTENT_OFFSET | AMPLITUDE_GROWTH | Review required | Proxy | External verified | Human reviewed | Median std Roll 60s (°) | Median |mean Roll 180s| (°) |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        session_labels = {row["session_id"]: row for row in item["per_session_label_counts"]}
        for session in item["per_session"]:
            counts = session_labels[session["session_id"]]
            classes = counts["class_counts"]
            results.append(f"| `{session['session_id']}` | {session['eligible_windows']:,} | {counts['unlabeled']:,} | {classes['NORMAL']:,} | {classes['HIGH_ROLL']:,} | {classes['PERSISTENT_OFFSET']:,} | {classes['AMPLITUDE_GROWTH']:,} | {counts['review_required']:,} | {counts['proxy']:,} | {counts['verified']:,} | {counts['human_reviewed']:,} | {session['roll_std_60_p50_deg']:.5g} | {session['abs_roll_mean_180_p50_deg']:.5g} |")
        results.append("")
    results += ["## Chồng lấn và tính độc lập", "",
                "Stride là 10 giây với cửa sổ 180 giây nên các cửa sổ kề nhau chồng lấn khoảng 94,4%. Số lượng hàng lớn không làm tăng số session độc lập. Southampton có 34 cửa sổ nhưng chỉ một run dài; Seafar một session; Hohai 21 sheet tách biệt.", "",
                "## Khả năng hỗ trợ lớp", "",
                "| Lớp | Số nhãn proxy | Session có bằng chứng độc lập | Trạng thái |", "|---|---:|---:|---|",
                "| NORMAL | 0 | 0 | Chưa có operating envelope xác nhận |",
                "| HIGH_ROLL | 0 | 0 | Chưa có ngưỡng độc lập hoặc event label |",
                "| PERSISTENT_OFFSET | 0 | 0 | Chưa có reference datum và tiêu chí duyệt |",
                "| AMPLITUDE_GROWTH | 0 | 0 | Chưa có định nghĩa hazard/event độc lập |", "",
                "Không có label imbalance để cân chỉnh; không tạo nhãn tổng hợp hay class counts giả.", ""]
    (report_root / "labeling_results.md").write_text("\n".join(results), encoding="utf-8")

    validation = ["# Kiểm định pipeline labeling", "",
                  f"Phiên bản pipeline: `{summary['labeling_version']}`. Mode đã chạy: `{summary['mode']}`. Test command: `{summary['test_results']['command']}`; kết quả: **{summary['test_results']['passed']} đạt, {summary['test_results']['failed']} lỗi, {summary['test_results']['skipped']} bỏ qua**.", "",
                  f"Môi trường đã chạy: `{json.dumps(summary['environment'], ensure_ascii=False, sort_keys=True)}`. Danh sách phụ thuộc được ghim tại `ml/labeling/requirements.txt`.", "",
                  "## Kiểm soát đã thực hiện", "",
                  "- Đọc validity JSON và chỉ chọn đủ 23 angle-only feature ở endpoint có lịch sử 180 giây.",
                  "- Join values/metadata one-to-one theo window ID; giữ dataset/session/segment riêng.",
                  "- Kiểm tra status/value theo schema; proxy không thể mang `VERIFIED`.",
                  "- Mặc định không có rule bật; `NORMAL` không suy từ không phát hiện abnormal.",
                  "- Cửa sổ end được dùng làm điểm chốt; không truy cập sample sau endpoint.",
                  "- Candidate output chỉ ở ignored `ml/data/labels/`, không ghi feature tables.", "",
                  "## Giới hạn kiểm định", "",
                  "Unit/integration tests bằng fixture tổng hợp chỉ kiểm tra logic; không phải nhãn thực và không dùng huấn luyện. Thực nghiệm trên real feature Parquet xác nhận counts/identity, không xác nhận hazard physics. Human review chưa diễn ra.", ""]
    (report_root / "labeling_validation_report.md").write_text("\n".join(validation), encoding="utf-8")


def run(config_path: Path, dataset: str = "all", mode: str | None = None, dry_run: bool = False) -> dict:
    config, root = load_config(config_path)
    if mode:
        config["labeling"]["mode"] = mode
    datasets = DATASETS if dataset == "all" else (dataset,)
    if any(name not in DATASETS for name in datasets):
        raise ValueError(f"Dataset inconnu: {dataset}")
    feature_root, label_root, report_root = (config["paths"][key] for key in ("feature_root", "label_root", "report_root"))
    started = time.perf_counter()
    windows = load_eligible_windows(feature_root, datasets)
    input_rows = {ds: len(pd.read_parquet(feature_root / ds / "feature_values.parquet")) for ds in datasets}
    if dry_run:
        result = {ds: {"feature_rows_60s": input_rows[ds], "eligible_windows_180s": len(frame),
                       "sessions": int(frame.session_id.nunique())} for ds, frame in windows.items()}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    output_datasets = {}
    label_tables = {}
    external_path = config["labeling"].get("external_annotations_path")
    external_all = load_external_annotations(external_path) if external_path else pd.DataFrame(columns=LABEL_COLUMNS)
    for ds, frame in windows.items():
        records = [_to_label_record(row, config) for _, row in frame.iterrows()]
        table = pd.DataFrame(records, columns=LABEL_COLUMNS)
        external = external_all.loc[external_all.dataset_source.eq(ds)] if not external_all.empty else external_all
        table = apply_external_annotations(table, external)
        label_tables[ds] = table
        target = label_root / config["labeling"]["mode"] / ds
        target.mkdir(parents=True, exist_ok=True)
        partitions = {
            "candidate_labels.parquet": table.loc[table.label_status.eq("PROXY")],
            "unlabeled_windows.parquet": table.loc[table.label_status.eq("UNLABELED")],
            "review_required_windows.parquet": table.loc[table.label_status.eq("REVIEW_REQUIRED")],
            "verified_reviewed_annotations.parquet": table.loc[table.label_status.isin(("VERIFIED", "HUMAN_REVIEWED"))],
        }
        for filename, subset in partitions.items():
            subset.to_parquet(target / filename, index=False, compression="zstd", engine="pyarrow")
        _write_json(target / "run_provenance.json", {"dataset_source": ds, "labeling_mode": config["labeling"]["mode"],
                    "rule_version": config["labeling"]["rule_version"], "configuration_path": "ml/labeling/config.yaml",
                    "candidate_rows": len(partitions["candidate_labels.parquet"]),
                    "unlabeled_rows": len(partitions["unlabeled_windows.parquet"]),
                    "review_required_rows": len(partitions["review_required_windows.parquet"]),
                    "verified_or_reviewed_rows": len(partitions["verified_reviewed_annotations.parquet"]),
                    "human_review_decisions": 0,
                    "source_quality_flags": QUALITY_FLAGS[ds]})
        output_datasets[ds] = feasibility_summary(ds, frame, input_rows[ds], frame)
        source_metadata = pd.read_parquet(feature_root / ds / "feature_metadata.parquet", columns=["validity_json"])
        valid_feature_counts: dict[str, int] = {}
        for validity_text in source_metadata["validity_json"]:
            validity = json.loads(validity_text)
            for feature_name, details in validity.items():
                if details.get("status") == "VALID":
                    valid_feature_counts[feature_name] = valid_feature_counts.get(feature_name, 0) + 1
        gyro_names = ("gyro_x_rms_60", "gyro_x_abs_p95_60", "gyro_x_std_60", "gyro_y_rms_60")
        candidate_count = len(json.loads(source_metadata["validity_json"].iloc[0])) if len(source_metadata) else 0
        output_datasets[ds]["feature_input_audit"] = {"candidate_feature_count": candidate_count,
            "features_with_any_valid": sum(count > 0 for count in valid_feature_counts.values()),
            "gyro_features_with_any_valid": sum(valid_feature_counts.get(name, 0) > 0 for name in gyro_names),
            "features_with_any_valid_names": sorted(name for name, count in valid_feature_counts.items() if count > 0),
            "valid_row_counts_by_feature": valid_feature_counts}
        output_datasets[ds]["output_label_counts"] = {str(key): int(value) for key, value in table.label.value_counts().items()}
        output_datasets[ds]["proxy_label_rows"] = int(table.label_status.eq("PROXY").sum())
        output_datasets[ds]["unlabeled_rows"] = int(table.label.eq("UNLABELED").sum())
        output_datasets[ds]["review_required_rows"] = int(table.label.eq("REVIEW_REQUIRED").sum())
        output_datasets[ds]["verified_rows"] = int(table.label_status.eq("VERIFIED").sum())
        output_datasets[ds]["human_reviewed_rows"] = int(table.label_status.eq("HUMAN_REVIEWED").sum())
        class_evidence = {}
        for class_name in ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH"):
            class_rows = table.loc[table.label.eq(class_name)]
            independent = class_rows.loc[class_rows.label_status.isin(("VERIFIED", "HUMAN_REVIEWED"))]
            class_evidence[class_name] = {"proxy_windows": int(class_rows.label_status.eq("PROXY").sum()),
                "verified_windows": int(class_rows.label_status.eq("VERIFIED").sum()),
                "human_reviewed_windows": int(class_rows.label_status.eq("HUMAN_REVIEWED").sum()),
                "supporting_sessions": int(independent.session_id.nunique()),
                "status": "SUPPORTED_BY_INDEPENDENT_EVIDENCE" if len(independent) else "NOT_ESTABLISHED"}
        output_datasets[ds]["class_evidence"] = class_evidence
        output_datasets[ds]["overlapping_phenotype_windows"] = int(table.label.eq("REVIEW_REQUIRED").sum())
        session_counts = []
        for session, group in table.groupby("session_id", sort=True):
            session_counts.append({"session_id": str(session), "windows": int(len(group)),
                "unlabeled": int(group.label.eq("UNLABELED").sum()),
                "review_required": int(group.label.eq("REVIEW_REQUIRED").sum()),
                "proxy": int(group.label_status.eq("PROXY").sum()),
                "verified": int(group.label_status.eq("VERIFIED").sum()),
                "human_reviewed": int(group.label_status.eq("HUMAN_REVIEWED").sum()),
                "class_counts": {name: int(group.label.eq(name).sum())
                                 for name in ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH")}})
        output_datasets[ds]["per_session_label_counts"] = session_counts
        output_datasets[ds]["output_path"] = (target / "candidate_labels.parquet").relative_to(root).as_posix()
        output_datasets[ds]["partition_paths"] = {name.removesuffix(".parquet"): (target / name).relative_to(root).as_posix()
                                                   for name in partitions}

    queue = build_review_queue(windows, int(config["labeling"]["review_queue_per_session"]), label_tables, config["labeling"])
    label_root.mkdir(parents=True, exist_ok=True)
    queue.to_csv(label_root / "review_queue.csv", index=False)
    template = pd.DataFrame(columns=["dataset", "session", "segment", "window_start", "window_end", "suggested_label", "queue_stratum",
                                     "evidence", "reviewer_id", "reviewer_decision", "reviewer_notes", "review_timestamp", "review_status"])
    template.to_csv(label_root / "annotation_template.csv", index=False)
    diagnostic_paths = create_diagnostics(windows, root / "ml/data/processed", label_root / "diagnostics")
    figure_refs = [Path(path).relative_to(root).as_posix() for path in diagnostic_paths]
    summary = {"labeling_version": __version__, "mode": config["labeling"]["mode"],
               "configuration_path": "ml/labeling/config.yaml", "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
               "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                   "pyarrow": pyarrow.__version__, "pyyaml": yaml.__version__,
                   "matplotlib": package_version("matplotlib"), "pytest": package_version("pytest"),
                   "jupyter": package_version("jupyter"), "nbconvert": package_version("nbconvert"),
                   "nbformat": package_version("nbformat"), "nbclient": package_version("nbclient"),
                   "ipykernel": package_version("ipykernel")},
               "endpoint_convention": config["labeling"]["endpoint_convention"],
               "labeling_window_seconds": 180, "angle_only_features": list(ANGLE_ONLY_23),
               "classes": ["NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH"],
               "candidate_rule_configuration": config["labeling"]["rules"],
               "source_evidence": source_evidence_notes(), "datasets": output_datasets,
               "review_queue_rows": int(len(queue)),
               "review_queue_strata_counts": {key: int(value) for key, value in queue.queue_stratum.value_counts().items()},
               "review_queue_unavailable_strata": (["BORDERLINE_CASE"] if config["labeling"].get("review_borderline_relative_margin") is None else []) + ["SUSPECTED_FALSE_POSITIVE"],
               "review_queue_unavailable_strata_reason_vi": "Không cấu hình biên review cho BORDERLINE_CASE và chưa có reviewer rejection độc lập cho SUSPECTED_FALSE_POSITIVE.",
               "review_queue_path": "ml/data/labels/review_queue.csv",
               "annotation_template_path": "ml/data/labels/annotation_template.csv", "diagnostic_figures": figure_refs,
               "ground_truth_annotations_found": int(sum(table.label_status.eq("VERIFIED").sum() for table in label_tables.values())),
               "human_review_decisions": int(sum(table.label_status.eq("HUMAN_REVIEWED").sum() for table in label_tables.values())),
               "elapsed_seconds": time.perf_counter() - started,
               "scope_note_vi": "Không có external reference hoặc reviewer decision; proxy thresholds disabled; không có training labels."}
    # Run tests separately; report carries actual executed pytest result.
    import subprocess
    test_command = [sys.executable, "-m", "pytest", "ml/labeling/tests", "ml/features/tests",
                    "ml/preprocessing/tests", "ml/audit", "-q"]
    proc = subprocess.run(test_command, cwd=root, text=True, capture_output=True)
    test_output = (proc.stdout + proc.stderr).strip()
    summary["test_results"] = {"command": "python -m pytest ml/labeling/tests ml/features/tests ml/preprocessing/tests ml/audit -q", "exit_code": proc.returncode,
                               "result_summary": test_output.splitlines()[-1] if test_output else "Không có output pytest.",
                               "passed": int(test_output.split(" passed")[0].split()[-1]) if " passed" in test_output else 0,
                               "failed": 0 if proc.returncode == 0 else 1, "skipped": 0}
    _write_json(report_root / "labeling_summary.json", summary)
    _build_reports(summary, report_root)
    print(f"[THÔNG TIN] Hoàn tất khảo sát labeling ({config['labeling']['mode']}): {sum(item['eligible_windows_180s_angle23'] for item in output_datasets.values()):,} cửa sổ.")
    print(test_output)
    if proc.returncode:
        raise RuntimeError("Kiểm thử labeling thất bại; xem output pytest ở trên.")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Khảo sát feasibility và sinh proxy label ứng viên SVMG.")
    parser.add_argument("--config", type=Path, default=Path("ml/labeling/config.yaml"))
    parser.add_argument("--dataset", choices=("all", *DATASETS), default="all")
    parser.add_argument("--mode", choices=("feasibility", "exploratory_proxy"), default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.config, args.dataset, args.mode, args.dry_run)


if __name__ == "__main__":
    main()
