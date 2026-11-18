from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .evidence_audit import write_evidence_report


def create_coverage_figure(forms: pd.DataFrame, output_path: Path, dpi: int = 120) -> None:
    datasets = list(dict.fromkeys(forms.dataset_source.tolist()))
    counts = [int(forms.dataset_source.eq(ds).sum()) for ds in datasets]
    sessions = [int(forms.loc[forms.dataset_source.eq(ds), "session_id"].nunique()) for ds in datasets]
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.unicode_minus": False, "font.size": 9})
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    bars = ax.bar([name.capitalize() for name in datasets], counts, color=["#2563eb", "#ea580c", "#059669"][:len(datasets)])
    for bar, session_count in zip(bars, sessions):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f"{int(bar.get_height())} mẫu\n{session_count} phiên",
                ha="center", va="bottom", fontsize=8)
    ax.set_title("Độ phủ mẫu pilot theo nguồn")
    ax.set_ylabel("Số cửa sổ review (chồng lấn)")
    ax.set_xlabel("Nguồn dữ liệu")
    ax.grid(axis="y", alpha=.2)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)


def write_pilot_reports(repo_root: Path, evidence_summary: dict, forms: pd.DataFrame,
                        pilot_summary: dict, decision_summary: dict, report_root: Path,
                        coverage_figure_path: Path) -> None:
    report_root.mkdir(parents=True, exist_ok=True)
    report_figure_dir = report_root / "figures"
    report_figure_dir.mkdir(parents=True, exist_ok=True)
    write_evidence_report(evidence_summary, report_root / "label_evidence_report.md",
                          report_root / "label_evidence_summary.json")
    figure_ref = coverage_figure_path.relative_to(repo_root).as_posix()
    lines = ["# Báo cáo Annotation Pilot", "",
             "## Mục tiêu và trạng thái thực hiện", "",
             f"Pilot chuẩn bị **{pilot_summary['pilot_samples']} mẫu** từ review queue có sẵn; không tự gán nhãn. Có **{pilot_summary['reviewed_decisions']} quyết định đã cung cấp**, **{pilot_summary['human_reviewed_labels']} nhãn HUMAN_REVIEWED**, **{pilot_summary['verified_operational_hazard_labels']} nhãn hazard vận hành VERIFIED**, **{pilot_summary['proxy_labels']} proxy** và **{pilot_summary['unlabeled_or_pending']} mẫu chưa gán nhãn**. Không có quyết định nào được tạo bởi script.", "",
             "## Độ phủ pilot", "",
             "| Nguồn | Mẫu | Session độc lập | Quyết định reviewer | HUMAN_REVIEWED | VERIFIED hazard | Normal envelope | UNLABELED | Median bối cảnh trước cửa sổ |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for ds, item in pilot_summary["datasets"].items():
        normal_envelope = int((forms.loc[forms.dataset_source.eq(ds), "label_status"].eq("VERIFIED")
            & forms.loc[forms.dataset_source.eq(ds), "evidence_category"].eq("VERIFIED_NORMAL_ENVELOPE")).sum())
        lines.append(f"| {ds.capitalize()} | {item['samples']} | {item['sessions']} | {item['reviewed_decisions']} | {item['human_reviewed']} | {item['verified_hazard']} | {normal_envelope} | {item['unlabeled']} | {item['median_context_coverage_fraction']:.1%} coverage |")
    lines += ["", f"![Độ phủ pilot theo nguồn]({figure_ref})", "",
              "### Độ phủ theo session", ""]
    for ds, group in forms.groupby("dataset_source", sort=True):
        lines += [f"#### {ds.capitalize()}", "", "| Session | Mẫu | Đã review | Chưa review | Quyết định ACCEPTED theo lớp |", "|---|---:|---:|---:|---|"]
        for session, subset in group.groupby("session_id", sort=True):
            reviewed = int(subset.review_status.isin(("ACCEPTED", "REJECTED", "NEEDS_DISCUSSION")).sum())
            accepted = subset.loc[subset.review_status.eq("ACCEPTED"), "reviewer_decision"].value_counts().sort_index()
            class_coverage = ", ".join(f"{label}: {count}" for label, count in accepted.items()) or "Chưa có bằng chứng lớp"
            lines.append(f"| `{session}` | {len(subset)} | {reviewed} | {len(subset)-reviewed} | {class_coverage} |")
        lines.append("")
    lines += ["## Hồ sơ từng mẫu", "",
              "CSV tại `ml/data/labels/annotation_pilot/annotation_pilot.csv` có một dòng cho mỗi mẫu: dataset/session/segment, window start/end, context trước cửa sổ, `plot_path`, metadata thử nghiệm, quality flags, bằng chứng cho quyết định, reviewer, quyết định, phenotype flags, ghi chú, thời điểm và review status. Trường reviewer/evidence được để trống hoặc UNVERIFIED cho đến khi có người điền thực tế.", "",
              "Hình cho toàn bộ 92 mẫu được tạo trong `ml/data/labels/annotation_pilot/figures/`; mỗi hình thể hiện Roll/Pitch ở vùng lịch sử trước cửa sổ (nếu có) và cửa sổ 180 giây được tô màu. Bối cảnh không vượt ngược qua đầu session/segment; mẫu đầu có thể không có history trước đó. Cột `context_coverage_fraction` ghi rõ độ phủ đo được.", "",
              "### Một số hình đại diện", ""]
    for ds, group in forms.groupby("dataset_source", sort=True):
        candidate = group.sort_values("context_coverage_fraction", ascending=False).iloc[0]
        report_figure = report_figure_dir / f"pilot_{ds}.png"
        shutil.copyfile(repo_root / candidate.plot_path, report_figure)
        lines.append(f"- {ds.capitalize()}, `{candidate.review_sample_id}`: độ phủ context {candidate.context_coverage_fraction:.1%}.\n\n  ![Roll và Pitch thực tế của {ds.capitalize()}](figures/{report_figure.name})")
    lines += ["", "## Metadata và cảnh báo chất lượng", "",
              "- Seafar: dữ liệu tàu thật, một session; duplicate/gaps đã tách segment. Rate-axis/sign chưa xác nhận và offset nền không phải bằng chứng hazard.",
              "- Hohai: mỗi workbook sheet là session thử nghiệm riêng; tên `Berth`/`Type` là metadata thí nghiệm. Thời gian suy từ 50 Hz và dropout không thể kiểm tra từ workbook.",
              "- Southampton: bốn mẫu pilot thuộc Run 14. Test Plan ghi điều kiện thử nghiệm `R1`, wave frequency khoảng 0,7976 Hz, amplitude khoảng 0,01927 m; đây chỉ là provenance, không phải hazard label. Delta Angle chưa map sang gyro canonical.",
              "- Quality flags theo từng mẫu lấy từ feature validity/provenance hiện hữu; các trường không VALID không bị che đi.", "",
              "## Kết quả review và đa nhãn", "",
              f"Quyết định thực tế: {pilot_summary['reviewed_decisions']}; mẫu ambiguous: {pilot_summary['ambiguous_samples']}; mẫu có nhiều phenotype flags: {pilot_summary['overlapping_phenotype_samples']}. Phân bố decision counts: `{json.dumps(pilot_summary['class_counts'], ensure_ascii=False, sort_keys=True)}`.", "",
              "Inter-reviewer agreement: "]
    if decision_summary["agreement"]["status"] == "NOT_CALCULATED":
        lines[-1] += f"chưa tính — {decision_summary['agreement']['reason_vi']}"
    else:
        lines[-1] += f"đã tính trên quyết định ACCEPTED ghép cặp. Chi tiết: `{json.dumps(decision_summary['agreement'], ensure_ascii=False, sort_keys=True)}`."
    lines += ["", "Không diễn giải đồng thuận của reviewer thành độ chính xác hazard. Người xem tín hiệu chỉ có thể ghi `OBSERVED_MOTION_PHENOTYPE`; để ghi `VERIFIED_OPERATIONAL_HAZARD` cần external evidence riêng. `NORMAL` yêu cầu `VERIFIED_NORMAL_ENVELOPE` có reference vận hành được chấp nhận.", "",
              "## Kiểm thử và kiểm chứng", "",
              f"Bài kiểm thử tự động gần nhất: **{pilot_summary['test_results']['result_summary']}**; exit code `{pilot_summary['test_results']['exit_code']}`. Lệnh: `python -m pytest ml/labeling/tests ml/features/tests ml/preprocessing/tests ml/audit -q`. Kiểm thử kiểm tra schema, chống thăng cấp nhãn chưa review, provenance, identity/window matching, ranh giới session, revision audit và tính tái lập; fixture tổng hợp chỉ dùng trong unit test.", "",
              "## Chống bias và leakage", "",
              "Mỗi hình chỉ có tín hiệu Roll/Pitch, ranh giới cửa sổ và metadata; không vẽ ngưỡng phân lớp. `queue_suggested_label` được giữ như thông tin kiểm toán, nhưng người review nên đánh giá tín hiệu trước khi xem trường này. Cửa sổ 180 giây stride 10 giây chồng lấn khoảng 94,4%; các hàng cùng session không độc lập. Mọi split downstream phải group theo session/run/sheet, không chia random theo cửa sổ.", "",
              "## Giải thích kỹ thuật phục vụ vấn đáp", "",
              "**Em đã làm gì?** Đóng gói 92 mẫu có sẵn thành form có khóa ổn định, signal plot, lịch sử trước cửa sổ, provenance và quality flags. **Vì sao?** Người review cần xem tín hiệu trong bối cảnh mà vẫn giữ ranh giới session/segment. **Phương pháp?** Ghép chính xác theo session/segment/window endpoint và chỉ đọc Parquet processed; hình thể hiện `(t-180,t]` cùng context trước cửa sổ. **Kết quả thực tế?** Từng mẫu có PNG và CSV form; quyết định thực tế được đếm từ form/ledger. **Nếu coi wave hoặc góc lớn là nhãn?** Sẽ suy diễn hazard từ điều kiện/đại lượng chuyển động mà không có reference vận hành. **Giới hạn?** Context có thể thiếu ở đầu segment; hình thị giác không thay thế xác nhận sự kiện hoặc chuyên gia vận hành.", ""]
    (report_root / "annotation_pilot_report.md").write_text("\n".join(lines), encoding="utf-8")

    readiness = ["# Đánh giá sẵn sàng cho supervised training", "",
                 "## Kết luận", "",
                 f"**Chưa đủ nhãn độc lập để huấn luyện supervised bốn lớp.** Hiện có {pilot_summary['verified_operational_hazard_labels']} nhãn hazard VERIFIED, {pilot_summary['human_reviewed_labels']} quan sát HUMAN_REVIEWED và {pilot_summary['reviewed_decisions']} quyết định reviewer thực tế trong pilot.", "",
                 "| Lớp | VERIFIED evidence | HUMAN_REVIEWED phenotype | Proxy | Session có reference vận hành độc lập |", "|---|---:|---:|---:|---:|"]
    for label in ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH"):
        lines_class = pilot_summary["class_counts"]
        verified = pilot_summary["verified_by_class"].get(label, 0)
        human = pilot_summary["human_reviewed_by_class"].get(label, 0)
        proxy = pilot_summary["proxy_by_class"].get(label, 0)
        sessions = pilot_summary["verified_sessions_by_class"].get(label, 0)
        readiness.append(f"| `{label}` | {verified} | {human} | {proxy} | {sessions} |")
    readiness += ["", "Human-reviewed phenotype là evidence về chuyển động quan sát được; không tự xác nhận tình trạng nguy hiểm. Các class count không chứng minh lớp vật lý vắng mặt.", "",
                  "## Rủi ro phương pháp", "",
                  "1. **Ít phiên độc lập:** Seafar 1 session, Hohai 21 session mô hình, Southampton 1 run 180 giây. 92 mẫu là cửa sổ chọn review, không phải 92 điều kiện độc lập.",
                  "2. **Overlap leakage:** stride 10 giây trên cửa sổ 180 giây tương đương khoảng 94,4% overlap giữa cửa sổ kề. Split ngẫu nhiên sẽ rò rỉ gần như cùng tín hiệu giữa train/test.",
                  "3. **Circular labeling:** nếu proxy dựa trên roll std/mean/RMS slope rồi model học các feature đó, kết quả chỉ cho thấy model tái tạo rule.",
                  "4. **Khác scale:** Hohai/Southampton là mô hình thử nghiệm; không gộp chung với tàu thật như một ngưỡng hazard phổ quát.",
                  "5. **NORMAL chưa có envelope:** thiếu baseline/operating envelope được chấp nhận; không suy NORMAL từ không phát hiện bất thường.",
                  "6. **Reliability:** chưa có hai reviewer đánh giá cùng sample; không báo agreement/kappa giả.", "",
                  "## Điều kiện trước khi training", "",
                  "- Thu thập external event/hazard annotations với timestamp, vessel/scale, operating state và nguồn xác minh.",
                  "- Xây dựng operating envelope dương tính cho NORMAL theo từng nguồn/phạm vi tàu; có người phụ trách phê duyệt.",
                  "- Đánh giá pilot mù tối thiểu bởi hai reviewer trên một tập con chồng lặp; báo agreement riêng cho primary decision và phenotype flags.",
                  "- Chốt cách phân biệt observed phenotype với verified operational hazard; xử lý các trường hợp nhiều cờ bằng `REVIEW_REQUIRED` hoặc chính sách đã được duyệt.",
                  "- Định nghĩa split theo session/run/vessel; không chia cửa sổ overlap ngẫu nhiên.",
                  "- Đánh giá subgroup và source-scale riêng; không đưa dataset/session identity vào feature vector.",
                  "- Giữ test độc lập với rule/feature đã dùng để gán proxy; không trình bày rule agreement là safety validation.", "",
                  "## Lựa chọn bước tiếp theo", "",
                  "1. **Khuyến nghị chính — additional data acquisition:** thu thập tàu thật có operational event logs và được chuyên gia xác nhận; đồng thời thu thập các giai đoạn hoạt động bình thường có envelope rõ.",
                  "2. **Reduced-scope study:** đánh giá chất lượng quan sát phenotype Roll/Pitch trên pilot, chưa gọi hazard classification và chưa khái quát giữa scale.",
                  "3. **Proxy-label proof of concept (chỉ nếu cần minh họa kỹ thuật):** rule/threshold phải có version và nguồn, split theo session, báo kết quả là agreement với proxy và nêu circularity; không dùng làm bằng chứng an toàn.", "",
                  "## Giải thích kỹ thuật phục vụ vấn đáp", "",
                  "**Vì sao chưa train?** Không có nhãn operational hazard hoặc NORMAL independently verified. **Vì sao không dùng 92 hàng như 92 mẫu độc lập?** Chúng chồng lấn thời gian và tập trung trong 23 session nguồn. **Có thể làm gì thay thế?** Mở rộng thu thập có event reference; hoặc giới hạn bài toán thành quan sát phenotype có reviewer và không tuyên bố hazard. **Giới hạn?** Mọi kết luận chỉ thuộc các nguồn và session hiện có; chưa kiểm chứng tính đại diện vận hành.", ""]
    (report_root / "training_readiness_assessment.md").write_text("\n".join(readiness), encoding="utf-8")
