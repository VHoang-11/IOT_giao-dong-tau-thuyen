from __future__ import annotations

from pathlib import Path

from .spec import FEATURE_GROUPS, FEATURE_NAMES, PRACTICAL_SUBSETS, WINDOW_SECONDS


FEATURE_FORMULAS = (
    ("RMS góc Roll 60 giây, kể cả offset", "sqrt(mean(roll²))", "độ"),
    ("Độ lệch chuẩn tổng thể Roll 60 giây", "sqrt(mean((roll-mean(roll))²))", "độ"),
    ("Trung bình có dấu Roll 60 giây", "mean(roll)", "độ"),
    ("Biên độ đỉnh-đỉnh Roll", "max(roll)-min(roll)", "độ"),
    ("Phân vị Type-7 95% của |Roll|", "Q0.95(|roll|), Type-7", "độ"),
    ("Cực đại |Roll|", "max(|roll|)", "độ"),
    ("Khoảng tứ phân vị Roll", "Q0.75(roll)-Q0.25(roll), Type-7", "độ"),
    ("RMS sai phân Roll liên tiếp", "sqrt(mean((x[i]-x[i-1])²)) trên cặp đúng chu kỳ", "độ/mẫu"),
    ("RMS gyro trục x", "sqrt(mean(gx²))", "rad/s"),
    ("Phân vị Type-7 95% của |gyro x|", "Q0.95(|gx|), Type-7", "rad/s"),
    ("Độ lệch chuẩn tổng thể gyro x", "sqrt(mean((gx-mean(gx))²))", "rad/s"),
    ("Trung bình Roll 180 giây", "mean(roll)", "độ"),
    ("Trung vị Roll Type-7", "Q0.50(roll), Type-7", "độ"),
    ("Trung bình |Roll|", "mean(|roll|)", "độ"),
    ("Tỷ lệ dấu trội", "max(n_pos,n_neg)/(n_pos+n_neg); bỏ mẫu đúng 0", "không thứ nguyên"),
    ("Độ lệch chuẩn population của ba mean block", "SD0(mean_1,mean_2,mean_3)", "độ"),
    ("Dịch chuyển mean", "mean(block_muộn)-mean(block_sớm)", "độ"),
    ("RMS block Roll sớm", "sqrt(mean(roll²)) trên block đầu 60 giây", "độ"),
    ("RMS block Roll muộn", "sqrt(mean(roll²)) trên block cuối 60 giây", "độ"),
    ("Tỷ số RMS muộn/sớm", "RMS_muộn/RMS_sớm; epsilon số học 1e-9 độ", "không thứ nguyên"),
    ("Độ dốc hồi quy tuyến tính RMS", "OLS qua tâm [30,90,150] giây; slope × 60", "độ/phút"),
    ("R² hồi quy ba RMS block", "1-SSE/SST; undefined nếu SST dưới tolerance", "không thứ nguyên"),
    ("Độ dốc phân vị |Roll| 95%", "OLS Q0.95(|roll|) ba block; slope × 60", "độ/phút"),
    ("Chu kỳ dao động ước lượng", "median khoảng cách crossing lên; mean-center; nội suy tuyến tính", "giây"),
    ("Số zero crossing", "đếm crossing lên và xuống của roll-mean(window)", "lần/180 giây"),
    ("CV chu kỳ", "SD0(periods)/mean(periods); cần ít nhất 3 period", "không thứ nguyên"),
    ("RMS Pitch", "sqrt(mean(pitch²))", "độ"),
    ("Độ lệch chuẩn tổng thể Pitch", "sqrt(mean((pitch-mean(pitch))²))", "độ"),
    ("Biên độ đỉnh-đỉnh Pitch", "max(pitch)-min(pitch)", "độ"),
    ("RMS gyro trục y", "sqrt(mean(gy²))", "rad/s"),
)


def _fmt(value, precision=5):
    if value is None:
        return "—"
    return f"{value:.{precision}g}" if isinstance(value, (float, int)) else str(value)


def build_reports(summary: dict, report_root: Path) -> None:
    report_root.mkdir(parents=True, exist_ok=True)
    main = [
        "# Kết quả Feature Extraction — SVMG M2", "",
        f"Thời điểm chạy UTC: {summary['run_timestamp_utc']}. Triển khai này đánh giá đúng 30 candidate feature; không thay đổi contract 14 feature hiện hành, không tạo nhãn và không huấn luyện Random Forest.", "",
        "## 1. Mục tiêu và dữ liệu đầu vào", "",
        "Extractor đọc Parquet đã tiền xử lý trong `ml/data/processed/`, mỗi file là một segment độc lập. Không nối session, sheet hoặc run. Provenance và danh tính nguồn nằm trong metadata riêng, không thuộc vector ML. Chất lượng nguồn và các giới hạn dữ liệu gốc được ghi trong [Real Dataset Audit](../../audit/real_dataset_audit_report.md); tình trạng availability ban đầu nằm trong [ma trận khả dụng](../../docs/feature_availability_matrix.md).", "",
        "| Nguồn | Segment | Candidate rows (cửa sổ 60 giây) | Endpoint có đủ 180 giây | Có ít nhất một feature VALID | Đủ cả 30 feature | Hàng có INVALID_INPUT | Thời gian xử lý (s) | Peak Python memory (MB) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    validation = [
        "# Kiểm định Feature Extraction — SVMG M2", "",
        "## Phạm vi và kết quả kiểm thử", "",
        f"Lệnh kiểm thử: `{summary['test_results']['command']}`. Kết quả thực tế: **{summary['test_results']['passed']} đạt, {summary['test_results']['failed']} lỗi, {summary['test_results']['skipped']} bỏ qua** (`{summary['test_results']['result_summary']}`).", "",
        "Unit tests dùng fixture nhỏ có nghiệm phân tích được; fixture tổng hợp không được đưa vào feature tables hoặc dùng làm dữ liệu huấn luyện.", "",
        "| Nhóm kiểm thử | Nội dung đã kiểm chứng | Kết quả |", "|---|---|---|",
        "| Công thức cơ bản | RMS, population SD, mean, P2P, Type-7 percentile/IQR, max abs | Xem kết quả pytest |",
        "| Trend | OLS slope, population R² và trường hợp SST=0 | Xem kết quả pytest |",
        "| Chu kỳ | Zero crossing nội suy, period median, CV và thiếu chu kỳ | Xem kết quả pytest |",
        "| Cửa sổ | `(t-W,t]`, đúng 60/180 giây, stride, thiếu duration | Xem kết quả pytest |",
        "| Tính causal | Kết quả tại endpoint không đổi khi nối thêm dữ liệu tương lai | Xem kết quả pytest |",
        "| Schema/validity | Thứ tự 30 cột, validity từng feature, missing gyro và mapping chưa xác nhận | Xem kết quả pytest |",
        "| Hồi quy lỗi period | Cửa sổ sin 0,5 Hz, chu kỳ biết trước 2 giây; kiểm tra Roll và timestamp không bị đảo | Xem kết quả pytest |",
        "| Tập angle-only 23 | Đúng tên/thứ tự; kiểm tra đủ 23 trạng thái VALID trên cửa sổ 180 giây đủ điều kiện | Xem kết quả pytest |",
        "| Tính causal | Nối thêm quan sát tương lai không làm đổi giá trị period tại endpoint cũ | Xem kết quả pytest |", "",
        "## Kiểm định dữ liệu thực", "",
        "Kết quả theo nguồn và số lượng status từng feature nằm trong `feature_extraction_summary.json`. Mỗi Parquet values có metadata companion với `validity_json`; feature không hợp lệ được null, không điền 0.", "",
        "## Giới hạn xác nhận", "",
        "Unit test không xác nhận tính đại diện hàng hải, hiệu chuẩn cảm biến, validity của nhãn hay chất lượng phân loại. Thử nghiệm filter stability chỉ so sánh cùng cửa sổ thời gian và cùng định nghĩa feature.",
        "",
        "Rà soát period phát hiện lỗi gán đảo mảng Roll và timestamp; extractor đã sửa, chạy lại trên dữ liệu thực và bổ sung test hồi quy. Bằng chứng cửa sổ đại diện, tính sẵn có của tập 23 feature và giới hạn dao động được ghi trong [báo cáo rà soát chu kỳ và tập angle-only](feature_period_subset_review.md).",
    ]
    for dataset, item in summary["datasets"].items():
        main.append(f"| {dataset.capitalize()} | {item['segments']} | {item['candidate_windows_60s']:,} | {item['candidate_windows_180s']:,} | {item['rows_with_any_valid_feature']:,} | {item['complete_30_feature_rows']:,} | {item['invalid_input_rows']:,} | {_fmt(item['elapsed_seconds'],4)} | {_fmt(item['peak_traced_python_memory_mb'],4)} |")
        validation.append(f"### {dataset.capitalize()}")
        validation.append("")
        validation.append(f"Candidate rows: {item['candidate_windows_60s']:,}; complete 30-feature rows: {item['complete_30_feature_rows']:,}; invalid-input rows: {item['invalid_input_rows']:,}.")
        validation.append("")
        validation.append("| Feature | VALID | MISSING_SOURCE_SIGNAL | INSUFFICIENT_WINDOW | INVALID_INPUT | UNDEFINED_MATHEMATICALLY | UNVERIFIED_SIGNAL_MAPPING |")
        validation.append("|---|---:|---:|---:|---:|---:|---:|")
        for feature, counts in item["feature_status_counts"].items():
            validation.append(f"| `{feature}` | {counts['VALID']} | {counts['MISSING_SOURCE_SIGNAL']} | {counts['INSUFFICIENT_WINDOW']} | {counts['INVALID_INPUT']} | {counts['UNDEFINED_MATHEMATICALLY']} | {counts['UNVERIFIED_SIGNAL_MAPPING']} |")
        validation.append("")

    main += ["", "## 2. Thứ tự, công thức vận hành và đơn vị", "",
        "ID dưới đây là zero-based; # là thứ tự one-based. Công thức theo đúng proposal trong `ml/docs/feature_specification_30.md`; lựa chọn vận hành đang ở trạng thái `PENDING_TEAM_APPROVAL`, không thay đổi 14-feature contract.", "",
        "| ID / # | Feature | Cửa sổ | Công thức vận hành | Đơn vị |", "|---:|---|---:|---|---|"]
    for index, (name, definition) in enumerate(zip(FEATURE_NAMES, FEATURE_FORMULAS)):
        meaning, formula, output_unit = definition
        main.append(f"| {index} / {index+1} | `{name}` | {WINDOW_SECONDS[name]} s | {formula} — {meaning} | {output_unit} |")
    main += ["", "### Quy ước cửa sổ và validity", "",
        "- Cửa sổ trailing chọn mẫu `(t-W,t]`; endpoint đầu tiên xuất hiện khi segment đã có đủ 60 giây, sau đó cách nhau 10 giây. Các feature 180 giây ở cùng endpoint có `INSUFFICIENT_WINDOW` đến khi đủ lịch sử.",
        "- Coverage tối thiểu 95%: 570/600 mẫu trong cửa sổ 60 giây; 1.710/1.800 trong cửa sổ 180 giây. Cửa sổ có timestamp gap lớn hơn 1,5 chu kỳ danh định nhận `INVALID_INPUT`.",
        "- Percentile/IQR dùng Type-7; độ lệch chuẩn dùng population (`ddof=0`). Sai phân không nối qua missing/gap.",
        "- Ba block dài 60 giây lần lượt `(t-180,t-120]`, `(t-120,t-60]`, `(t-60,t]`; hồi quy dùng tâm block 30/90/150 giây và xuất slope theo độ/phút.",
        "- Zero crossing dùng `roll-mean(window)`, crossing giữa hai mẫu được nội suy tuyến tính. Period là median chu kỳ từ crossing lên; period cần 3 crossing lên, CV cần 3 chu kỳ. Mẫu đúng 0 bị loại khỏi tỷ lệ sign; chuỗi toàn 0 làm feature sign undefined.",
        "- Epsilon tỷ số RMS là 1e-9 độ, chỉ là guard số học cấu hình được, không suy ra từ sensor noise. R² undefined nếu SST không vượt tolerance. Hai lựa chọn này vẫn chờ nhóm duyệt.", "",
        "## 3. Tổ chức bảng và metadata", "",
        "Mỗi dataset có `feature_values.parquet` chứa `window_id` rồi 30 cột feature đúng thứ tự; `feature_metadata.parquet` riêng chứa nguồn/session/segment/end time, validity từng feature, provenance và version. Metadata không được đưa vào feature vector.", "",
        "| Nguồn | Candidate rows | Complete 30 | Roll-only 60 (8) | Roll+Pitch 60 (11) | Offset+growth 180 (12) | Angle-only (23) |", "|---|---:|---:|---:|---:|---:|---:|"]
    for dataset, item in summary["datasets"].items():
        subset = item["complete_practical_subsets"]
        main.append(f"| {dataset.capitalize()} | {item['candidate_windows_60s']:,} | {item['complete_30_feature_rows']:,} | {subset['roll_only_60']:,} | {subset['roll_pitch_angle_60']:,} | {subset['offset_and_growth_180']:,} | {subset['angle_only_23_without_gyro_or_period']:,} |")
    main += ["", "## 4. Availability và thống kê thực nghiệm", "",
        "`VALID` chỉ nói phép tính có đủ dữ liệu và toán học xác định, không đồng nghĩa công thức/mapping đã được phê duyệt. Gyro Seafar và Southampton được đánh dấu `UNVERIFIED_SIGNAL_MAPPING`; Hohai gyro là `MISSING_SOURCE_SIGNAL`.", ""]
    for dataset, item in summary["datasets"].items():
        main += [f"### {dataset.capitalize()}", "",
            f"Đọc {item['segments']} segment processed. Có {item['candidate_windows_60s']:,} endpoint/candidate rows 60 giây, {item['candidate_windows_180s']:,} endpoint đủ lịch sử 180 giây; {item['complete_30_feature_rows']:,} row đủ 30 feature. Rows có ít nhất một feature valid: {item['rows_with_any_valid_feature']:,}; rows chứa invalid input: {item['invalid_input_rows']:,}.", "",
            "| Feature | VALID | MISSING | INSUFFICIENT | INVALID | UNDEFINED | UNVERIFIED | Mean | SD population | P05 | P50 | P95 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for feature, counts in item["feature_status_counts"].items():
            stats = item["feature_statistics"][feature]
            main.append(f"| `{feature}` | {counts['VALID']} | {counts['MISSING_SOURCE_SIGNAL']} | {counts['INSUFFICIENT_WINDOW']} | {counts['INVALID_INPUT']} | {counts['UNDEFINED_MATHEMATICALLY']} | {counts['UNVERIFIED_SIGNAL_MAPPING']} | {_fmt(stats['mean'])} | {_fmt(stats['std_population'])} | {_fmt(stats['p05'])} | {_fmt(stats['p50'])} | {_fmt(stats['p95'])} |")
        main.append("")

    main += ["## 5. Rà soát chu kỳ và tập angle-only", "",
        "Kết quả ban đầu ghi nhận 24 feature có cửa sổ VALID: 23 feature angle-only cộng với `roll_zero_crossings_180`. Tập angle-only loại toàn bộ Group E theo thiết kế. Rà soát cuối tìm thấy và sửa lỗi đảo thứ tự tín hiệu/timestamp; sau tái trích xuất có 26 feature đạt VALID trên ít nhất một cửa sổ. Chi tiết 23 tên theo thứ tự, kiểm tra từng hàng, cửa sổ thực đại diện và phép đối chiếu độc lập nằm trong [báo cáo rà soát chu kỳ và tập angle-only](feature_period_subset_review.md).", "",
        "Period dùng Roll trừ trung bình của cùng cửa sổ, không detrend; đây là proposal trong đặc tả còn chờ phê duyệt. Các giá trị period nay tính được ở phần lớn cửa sổ đủ 180 giây, nhưng CV cao ở một số nguồn cần đánh giá ổn định trước khi labeling.", "",
        "## 6. Độ ổn định theo preprocessing/filter", "",
        "Baseline production vẫn là 10 Hz / Butterworth bậc 4 cutoff 4 Hz. So sánh bên dưới tái xử lý một segment raw đại diện với cutoff thay thế cấu hình 3 Hz, không ghi đè baseline; chỉ ghép endpoint trùng nhau và feature `VALID` ở cả hai cấu hình.", ""]
    stability = summary.get("filter_stability", {})
    for dataset, item in stability.items():
        main.append(f"### {dataset.capitalize()}")
        main.append("")
        if item.get("status") != "COMPARED":
            main.append(item.get("reason_vi", "Không áp dụng so sánh filter cho nguồn này."))
            main.append("")
            continue
        main.append(f"Phiên/segment đại diện: `{item['representative_session_id']}` / `{item['representative_segment_id']}`; endpoint căn thời gian chung: {item['matched_windows']}.")
        main.append("")
        main.append("| Feature | Cửa sổ chung VALID | Mean |Δ| | Max |Δ| | Mean relative diff (%) | Tương quan | Mean normalized |")
        main.append("|---|---:|---:|---:|---:|---:|---:|")
        for feature, metrics in item["features"].items():
            main.append(f"| `{feature}` | {metrics['matched_valid_windows']} | {_fmt(metrics['mean_absolute_difference'])} | {_fmt(metrics['max_absolute_difference'])} | {_fmt(metrics['mean_relative_difference_percent'])} | {_fmt(metrics['correlation'])} | {_fmt(metrics['mean_normalized_absolute_difference'])} |")
        main.append("")
    main += ["Đây là sensitivity analysis trên segment đại diện, không phải bằng chứng cutoff nào tối ưu. Giai đoạn kế tiếp nên thử filter mạnh hơn/alternative Sampling Rate và so độ ổn định feature trên nhiều session, đồng thời cân nhắc attenuation gần Nyquist của baseline hiện hành.", "",
        "## 7. Kiểm thử và tính tái lập", "",
        f"Lệnh: `python -m ml.features.run --config ml/features/config.yaml --dataset all`; tests: `{summary['test_results']['result_summary']}`. Python `{summary['environment']['python']}`; NumPy `{summary['environment']['numpy']}`, pandas `{summary['environment']['pandas']}`, PyArrow `{summary['environment']['pyarrow']}`, SciPy `{summary['environment']['scipy']}`.",
        "Raw/processed data phải có sẵn tại các đường dẫn trong README preprocessing; `ml/data/features/` bị gitignore. Các bảng feature có thể tái tạo từ CLI, notebook chỉ đọc feature outputs/summary.", "",
        "## 8. Hạn chế và sẵn sàng labeling", "",
        "Không có row đầy đủ 30 feature vì gyro canonical không được xác nhận hoặc không có ở ba nguồn. Hohai không đo gyro; Southampton Delta Angle không được xem là gyro; Seafar rate mapping còn cần xác nhận. Sau khi sửa lỗi gán đảo tín hiệu/timestamp, các feature chu kỳ có giá trị VALID trên phần lớn cửa sổ 180 giây; Seafar vẫn có một số cửa sổ thiếu crossing/period. Xem [rà soát chu kỳ và tập angle-only](feature_period_subset_review.md).",
        "Bảng feature có validity riêng từng feature nên có thể bắt đầu chuẩn bị quy trình labeling có kiểm soát, nhưng chưa nên labeling tự động/huấn luyện cho đến khi nhóm duyệt công thức, mapping gyro và tiêu chí filter. Không chia các cửa sổ của cùng session qua train/test ngẫu nhiên.", "",
        "## 9. Giải thích kỹ thuật phục vụ vấn đáp", "",
        "**Em đã làm gì?** Trích xuất mỗi endpoint causal 10 giây từ Parquet theo segment. **Vì sao?** Tạo đặc trưng có timestamp và giữ ranh giới thử nghiệm. **Phương pháp?** Thống kê population, quantile Type-7, ba block 60 giây, hồi quy OLS và crossing nội suy. **Kết quả?** Xem bảng counts/availability/statistics thực ở trên. **Nếu bỏ qua validity?** Missing gyro hoặc cửa sổ thiếu dài có thể bị nhầm thành số 0/hợp lệ. **Giới hạn?** Các định nghĩa đang là proposal vận hành, period nhạy với noise/filter và gyro mapping chưa xác nhận.", ""]
    (report_root / "feature_extraction_results.md").write_text("\n".join(main), encoding="utf-8")
    (report_root / "feature_validation_results.md").write_text("\n".join(validation), encoding="utf-8")
    from .review import build_period_subset_review
    repo_root = report_root.resolve().parents[2]
    build_period_subset_review(repo_root, summary, report_root)
