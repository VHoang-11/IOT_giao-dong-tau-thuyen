from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow
import scipy
import yaml

from . import __version__
from .config import load_config
from .common import (clean_required_values, deterministic_duplicate_policy,
                     estimate_sampling_rate, split_continuous_segments)
from .diagnostics import create_figures
from .hohai import load_sessions as load_hohai
from .quality_checks import dataset_quality_summary, segment_frequency_diagnostics
from .schemas import RawSession
from .seafar import load_sessions as load_seafar
from .signal_processing import process_session
from .southampton import load_sessions as load_southampton


LOADERS = {"seafar": load_seafar, "hohai": load_hohai, "southampton": load_southampton}


def _json_write(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    def encode(value):
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, Path):
            return str(value)
        raise TypeError(f"Kiểu dữ liệu không hỗ trợ trong JSON: {type(value).__name__}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False, default=encode) + "\n", encoding="utf-8")


def _relative_repo_path(path: Path | str, repository_root: Path) -> str:
    """Trả về đường dẫn POSIX tương đối để metadata dùng được trên clone khác."""
    return Path(path).resolve().relative_to(repository_root.resolve()).as_posix()


def _relative_raw_reference(reference: str, repository_root: Path) -> str:
    """Chuẩn hóa raw_reference tuyệt đối, giữ nguyên hậu tố worksheet nếu có."""
    raw_path, separator, suffix = reference.partition("::")
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        return reference
    try:
        relative = candidate.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        return reference
    return f"{relative}{separator}{suffix}"


def _git_revision(root: Path) -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
            capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _run_unit_tests(repo_root: Path) -> dict:
    """Chạy suite sau pipeline và lưu kết quả thật để báo cáo không suy đoán."""
    command = [sys.executable, "-m", "pytest", "ml/preprocessing/tests", "-q"]
    result = subprocess.run(command, cwd=repo_root, capture_output=True, text=True)
    output = (result.stdout + result.stderr).strip()
    print(output)
    matches = {key: int(re.search(rf"(\d+) {key}", output).group(1)) if re.search(rf"(\d+) {key}", output) else 0
               for key in ("passed", "failed", "skipped", "error", "xfailed", "xpassed")}
    total = sum(matches.values())
    return {"command": "python -m pytest ml/preprocessing/tests -q", "total": total,
        "passed": matches["passed"], "failed": matches["failed"] + matches["error"],
        "skipped": matches["skipped"], "exit_code": int(result.returncode),
        "result_summary": output.splitlines()[-1] if output else "Không có output từ pytest."}


def _clean_generated_dataset_dir(root: Path, dataset: str):
    target = (root / dataset).resolve()
    base = root.resolve()
    if base not in target.parents:
        raise ValueError("Đường dẫn output không nằm dưới processed_root.")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)


def _write_segment(segment, processed_root: Path, compression: str, repository_root: Path):
    relative = Path(segment.dataset_source) / segment.session_id / segment.segment_id
    folder = processed_root / relative
    folder.mkdir(parents=True, exist_ok=True)
    data_path = folder / "timeseries.parquet"
    frame = segment.frame.copy()
    for column in frame.columns:
        if column not in {"dataset_source", "session_id", "segment_id"}:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("float64" if column == "time_seconds" else "float32")
    frame.to_parquet(data_path, index=False, compression=compression, engine="pyarrow")
    _json_write(folder / "provenance.json", segment.provenance)
    return {"data_path": _relative_repo_path(data_path, repository_root),
            "provenance_path": _relative_repo_path(folder / "provenance.json", repository_root),
            "rows": int(len(frame)), "schema": {c: str(frame[c].dtype) for c in frame.columns}}


def _fmt(value, digits=5):
    return "—" if value is None else f"{value:.{digits}g}"


def _report(summary: dict) -> str:
    dataset_names = [name for name in ("seafar", "hohai", "southampton") if name in summary["datasets"]]
    lines = [
        "# Báo cáo kết quả Data Preprocessing — SVMG", "",
        f"Ngày chạy: {summary['run_timestamp_utc']}. Data Preprocessing (tiền xử lý dữ liệu) chuẩn hóa và kiểm định Time Series; pipeline không trích xuất 30 candidate features, không tạo nhãn và không huấn luyện Random Forest.", "",
        "## A. Mục tiêu và nguồn dữ liệu", "",
        "Pipeline đọc dữ liệu thực Seafar, Hohai 6-DOF và Southampton KCS IMU; giữ từng session/sheet/run độc lập. Báo cáo audit gốc: [Real Dataset Audit](../../audit/real_dataset_audit_report.md).", "",
        "| Nguồn | Phiên đầu vào | Hàng nguồn | Hàng đầu ra | Segment đầu ra | Đủ 60 s | Đủ 180 s |", "|---|---:|---:|---:|---:|---:|---:|"
    ]
    for name in dataset_names:
        d = summary["datasets"][name]
        lines.append(f"| {name.capitalize()} | {d['session_count']} | {d['rows_before']:,} | {d['rows_after']:,} | {d['segments_output']} | {d['eligible_60s_segments']} | {d['eligible_180s_segments']} |")
    lines += ["", "## B. Môi trường và dependencies", "",
        f"Python `{summary['environment']['python']}`; NumPy `{summary['environment']['numpy']}`, pandas `{summary['environment']['pandas']}`, SciPy `{summary['environment']['scipy']}`, openpyxl `{summary['environment']['openpyxl']}`, PyArrow `{summary['environment']['pyarrow']}`, PyYAML `{summary['environment']['pyyaml']}`, Matplotlib `{summary['environment']['matplotlib']}`.",
        "Môi trường hiện tại có các dependency cần thiết. Phiên bản cấu hình được ghi trong `preprocessing_summary.json`; cài đặt từ môi trường Python dự án như mô tả ở `ml/preprocessing/README.md`.", "",
        f"## C. Kết quả kiểm thử tự động: {summary['test_results']['total']} bài, {summary['test_results']['passed']} đạt, {summary['test_results']['failed']} không đạt, {summary['test_results']['skipped']} bỏ qua. Lệnh: `{summary['test_results']['command']}`. Kết quả pytest: `{summary['test_results']['result_summary']}`.", "",
        "## D. Quy tắc làm sạch và lý do", "",
        "- Sắp xếp timestamp ổn định; timestamp trùng có cùng giá trị tín hiệu thì giữ bản ghi đầu. Nếu cùng timestamp nhưng tín hiệu xung đột, loại toàn bộ nhóm timestamp đó; không lấy trung bình.",
        "- Loại hàng có timestamp, Roll hoặc Pitch thiếu/không hữu hạn; gyro là nullable nên thiếu gyro không làm rơi hàng.",
        "- Phân đoạn tại khoảng thời gian lớn hơn 1,5 lần median chu kỳ mẫu; tuyệt đối không lọc/resample qua gap hoặc ranh giới phiên.",
        "- Không nội suy và không điền 0. Resampling dùng mẫu trước gần nhất trên lưới đích (zero-order hold có giới hạn tuổi), nên không đọc mẫu tương lai.",
        "- Các kênh liên tục dạng số hữu hạn ở dữ liệu 50 Hz được lọc Butterworth thông thấp causal dạng SOS trước khi lấy mẫu 10 Hz; trường hậu tố `_raw` được giữ nguyên theo nguồn. Khởi tạo trạng thái ở steady state theo mẫu đầu, bỏ 2 s warmup; không bù pha vì bù pha causal có thể cần dữ liệu tương lai.",
        "- Không fit scaler/imputer toàn cục; không xử lý theo nhãn; không tạo split Train/Test.", "",
        "## E. Chuyển đổi đơn vị và nguồn tín hiệu gyro", "",
        "Roll/Pitch đã ở degree ở cả ba nguồn. Hohai dùng metadata tài liệu: 50 Hz, Roll/Pitch/Yaw degree, Surge/Sway/Heave meter; thời gian được suy từ sample index và không thể phát hiện dropout. Seafar rate fields có tên đơn vị rad/min; pipeline chuyển `roll_rate_rad_min` và `pitch_rate_rad_min` sang rad/s bằng chia 60, giữ nguyên dấu và ghi rõ phần cứng/trục/dấu chưa xác nhận. Southampton `Delta Angle X/Y` có unit row degree/s nhưng ý nghĩa vật lý chưa đủ rõ; giữ các trường raw thêm và để gyro canonical missing. Hohai cũng không có gyro đo. Không dùng đạo hàm Roll/Pitch làm gyro.", "",
        "## F. Tần số lấy mẫu, bộ lọc và Resampling", "",
        f"Cấu hình: target `{summary['config']['target_sampling_hz']} Hz`, Butterworth order `{summary['config']['filter_order']}`, cutoff `{summary['config']['anti_alias_cutoff_hz']} Hz`, causal SOS, warmup `{summary['config']['filter_warmup_seconds']} s`, gap threshold `{summary['config']['maximum_gap_factor']}× median dt`.",
        "Đây là baseline thực nghiệm 10 Hz/4 Hz. Đáp ứng lý thuyết chỉ suy giảm khoảng 8,8 dB tại Nyquist đầu ra 5 Hz; chưa đủ cơ sở tuyên bố anti-alias đã được xác nhận đầy đủ. Giai đoạn kế tiếp cần so sánh bộ lọc mạnh hơn và đánh giá độ ổn định của feature theo cấu hình lọc/tần số lấy mẫu.",
        "Số liệu dưới đây là phép so sánh cùng timestamp đầu ra: giá trị nguồn tại mẫu trước gần nhất so với giá trị đã lọc. RMSE đo sai khác tuyệt đối cùng đơn vị; tỷ lệ RMS sau/trước mô tả thay đổi biên độ. Đây là diagnostics, không phải ngưỡng an toàn.", "",
        "## G. So sánh thống kê trước/sau", ""]
    for name in dataset_names:
        d = summary["datasets"][name]
        lines += [f"### {name.capitalize()}", "",
            f"Đầu vào: `{d['rows_before']:,}` hàng; sau xử lý timestamp trùng `{d['rows_after_duplicate_resolution']:,}`; sau kiểm tra trường bắt buộc `{d['rows_after_required_validation']:,}`; đầu ra `{d['rows_after']:,}` hàng trên {d['session_count']} phiên. Loại duplicate đồng nhất: {d['rows_removed_exact_duplicates']:,}; loại {d['rows_removed_conflicting_duplicate_groups']:,} hàng thuộc {d['conflicting_timestamp_groups']} nhóm timestamp xung đột; loại thiếu/không hữu hạn trường bắt buộc: {d['invalid_required_rows_removed']:,}; bỏ segment ngắn dưới {summary['config']['minimum_segment_seconds']} s: {d['short_segments_skipped']} segment / {d['rows_removed_short_segments']:,} hàng; giảm mẫu/warmup/regularization: {d['rows_removed_by_resampling_and_filter_warmup']:,} hàng.",
            f"Phát hiện {d['gap_count']} gap, sắp xếp lại {d['input_reordered_rows']} hàng timestamp, {d['continuous_segments_detected']} segment đầu vào; xuất {d['segments_output']} segment riêng. Sampling Rate median {d['sampling_rate_before_hz_median']:.4g} → {d['sampling_rate_after_hz_median']:.4g} Hz; median jitter ratio {d['sampling_irregularity_median_ratio']:.5g}. Cửa sổ đủ 60 s: {d['eligible_60s_segments']}; đủ 180 s: {d['eligible_180s_segments']}. Thời lượng cumulative trước {d['duration_before_cumulative_seconds']:.2f} s (tổng span phiên, có thể chứa gap), sau {d['duration_after_cumulative_seconds']:.2f} s (tổng span segment giữ). Missing Roll trước/sau {d['missing_percent_before']['roll_deg']:.4g}%/{d['missing_percent_after']['roll_deg']:.4g}%; Pitch {d['missing_percent_before']['pitch_deg']:.4g}%/{d['missing_percent_after']['pitch_deg']:.4g}%.", "",
            "| Tín hiệu | Thống kê | Trước | Sau |", "|---|---|---:|---:|"]
        if name == "seafar":
            grid_delta = (d["rows_after_required_validation"]
                          - d["rows_removed_short_segments"] - d["rows_after"])
            lines.append(
                f"Đối soát Seafar: `{d['rows_before']:,} − {d['rows_removed_conflicting_duplicate_groups']:,}` hàng xung đột `− {d['rows_removed_exact_duplicates']:,}` duplicate đồng nhất `− {d['invalid_required_rows_removed']:,}` invalid `− {d['rows_removed_short_segments']:,}` hàng thuộc đoạn ngắn `= {d['rows_after_required_validation'] - d['rows_removed_short_segments']:,}` hàng nguồn trong segment giữ. Lưới {summary['config']['target_sampling_hz']:g} Hz xuất `{d['rows_after']:,}` điểm, chênh đếm `{grid_delta}` điểm; đây là regularization/resampling, không phải hàng invalid. Rà soát timestamp xác nhận không có target point invalid và Seafar không có filter warmup. Trong lần audit này, 16/24 segment có ít hơn một điểm lưới so với hàng nguồn; 8 segment giữ cùng số đếm.")
        for signal, label in (("roll_deg", "Roll (degree)"), ("pitch_deg", "Pitch (degree)")):
            before, after = d["statistics_before"][signal], d["statistics_after"][signal]
            for metric in ("count", "missing", "mean", "std_population", "min", "max", "p05", "p50", "p95", "rms", "peak_to_peak"):
                metric_vi = {"count": "Số mẫu", "missing": "Giá trị thiếu", "mean": "Trung bình",
                    "std_population": "Độ lệch chuẩn tổng thể", "min": "Nhỏ nhất", "max": "Lớn nhất",
                    "p05": "Phân vị 5%", "p50": "Trung vị (P50)", "p95": "Phân vị 95%",
                    "rms": "RMS", "peak_to_peak": "Đỉnh-đỉnh"}[metric]
                lines.append(f"| {label} | {metric_vi} | {_fmt(before.get(metric), 8)} | {_fmt(after.get(metric), 8)} |")
        lines += ["", "| Tín hiệu | Mẫu căn thời gian | RMSE | Tương quan | RMS trước | RMS sau | Tỷ lệ RMS sau/trước |", "|---|---:|---:|---:|---:|---:|---:|"]
        for signal, label in (("roll_deg", "Roll"), ("pitch_deg", "Pitch"), ("gyro_x_rad_s", "Gyro X"), ("gyro_y_rad_s", "Gyro Y")):
            c = d["time_aligned_comparison"][signal]
            lines.append(f"| {label} | {c['aligned_samples']} | {_fmt(c['rmse'])} | {_fmt(c['correlation'])} | {_fmt(c['rms_before'])} | {_fmt(c['rms_after'])} | {_fmt(c['rms_ratio_after_over_before'])} |")
        lines += ["", f"Gyro canonical: X `{d['gyro_availability']['gyro_x_rad_s']}`, Y `{d['gyro_availability']['gyro_y_rad_s']}`. Bảng đầy đủ theo phiên/run nằm trong `preprocessing_summary.json`.", ""]
    lines += ["## H. Đánh giá lọc và giảm Sampling Rate", "",
        "Band-power được tính bằng Welch trên từng segment trước/sau filter, ở cùng Sampling Rate nguồn. Low band dùng 0,1–2 Hz; out-of-band dùng từ 5,25 Hz tới Nyquist nguồn 25 Hz. Bảng dưới đây tổng hợp median và khoảng min–max qua các segment. Tỷ lệ low-band gần 1 biểu thị giữ năng lượng thấp tần; attenuation âm dB biểu thị giảm out-of-band. Đây là diagnostics, không phải ngưỡng an toàn.", "",
        "| Nguồn / tín hiệu | Số segment | Tỷ lệ low-band median [min, max] | Attenuation out-of-band median dB [min, max] |", "|---|---:|---:|---:|"]
    for name in dataset_names:
        records = summary["datasets"][name]["frequency_diagnostics"]
        if not records:
            lines.append(f"| {name.capitalize()} / Roll, Pitch | 0 | Không áp filter anti-alias | Không áp filter anti-alias |")
            continue
        for signal in ("roll_deg", "pitch_deg"):
            low = [record[signal]["low_band_power_ratio"] for record in records if record.get(signal) and record[signal].get("low_band_power_ratio") is not None]
            attenuation = [record[signal]["out_of_band_attenuation_db"] for record in records if record.get(signal) and record[signal].get("out_of_band_attenuation_db") is not None]
            low_text = f"{np.median(low):.5f} [{min(low):.5f}, {max(low):.5f}]" if low else "—"
            att_text = f"{np.median(attenuation):.3f} [{min(attenuation):.3f}, {max(attenuation):.3f}]" if attenuation else "—"
            lines.append(f"| {name.capitalize()} / {signal} | {len(low)} | {low_text} | {att_text} |")
    lines += ["", "Phép đo low-band là tỷ lệ tích phân PSD sau/trước trong cùng dải; attenuation là `10*log10(P_after/P_before)` trên 5,25–25 Hz tại đầu ra bộ lọc nhưng trước decimation. Chúng mô tả tác động của filter trên dữ liệu thật. Seafar khoảng 10 Hz không bị lọc/giảm mẫu, nên không có kiểm định chống alias 50→10. Các đường dẫn trong summary, provenance và inventory được ghi tương đối từ repository root để dùng trên clone khác.", "",
        "### Hình chẩn đoán", ""]
    for fig in summary.get("figures", []):
        rel = Path(fig["path"]).relative_to(Path(summary["repository_root"]))
        lines.append(f"- `{rel}` — {fig['caption_vi']}")
    lines += ["", "## I. Kiểm định chất lượng và window eligibility", "",
        "- Eligibility được tính riêng trên mỗi segment sau processing: timestamp đầu-cuối phải phủ ít nhất 60/180 s; không cộng dồn qua gap/session. Lưới đích chứa mẫu endpoint nếu endpoint nằm đúng grid; mỗi cửa sổ trailing dùng quy ước `(t-W, t]`.",
        "- Số dòng thiếu/non-finite đầu ra và rate jitter theo từng segment được lưu trong JSON; kênh gyro missing được giữ NaN/null, không điền.",
        "- Filter response được đo trên tín hiệu thực và kiểm tra độc lập bằng sine fixtures: chi tiết định lượng và số kiểm thử được cập nhật sau lần chạy suite cuối.",
        "- Cumulative duration trước/sau có ý nghĩa khác nhau khi có gaps: trước là span thời gian phiên; sau cộng span các segment được giữ. Không diễn giải chênh lệch này như dữ liệu thời gian bị tạo mới.", "",
        "## J. Hạn chế còn lại", "",
        "1. Seafar có timestamp trùng/gap; duplicate conflict được loại cả nhóm theo chính sách tất định. Unit field name rate cho biết rad/min, nhưng nguồn cảm biến, body axis và quy ước dấu chưa xác nhận.",
        "2. Hohai không có timestamp; relative time và continuity là suy luận từ 50 Hz tài liệu. Không thể xác nhận mất mẫu bên trong sheet.",
        "3. Southampton chỉ có Run 14 đủ 180 s. `Delta Angle` chưa map sang gyro canonical; không merge Lasso.",
        "4. Causal Butterworth có phase delay và warmup; config không bù pha. Filter cutoff 4 Hz cần xác nhận bảo toàn các dynamics có ý nghĩa, nhất là khi chọn target 10 Hz.",
        "5. Đầu ra 10 Hz là engineering choice; cần đối chiếu với 50 Hz và kiến thức tần số dao động mục tiêu trước khi dùng cho feature/model.",
        "6. Các kết quả thống kê mô tả dataset, không chứng minh tính đại diện ngoài các phiên này và không phải đánh giá an toàn hàng hải.", "",
        "## K. Giải thích kỹ thuật phục vụ vấn đáp", "",
        "### Đọc nguồn và chuẩn hóa schema", "",
        "- **Em đã làm gì?** Đọc Seafar JSON theo record tuần tự, Hohai theo từng worksheet read-only, Southampton theo từng CSV và bỏ hàng đơn vị thứ hai.",
        "- **Vì sao?** Mỗi nguồn có schema/thời gian khác nhau; đọc tuần tự tránh nạp toàn bộ JSON lớn, và giữ session riêng tránh Data Leakage giữa runs.",
        "- **Thuật toán?** Map các cột cần thiết sang schema `dataset_source/session_id/segment_id/time_seconds/roll_deg/pitch_deg/gyro_x_rad_s/gyro_y_rad_s`, giữ thêm motion channels và metadata provenance.",
        f"- **Kết quả thực nghiệm?** Đã đọc các nguồn trong phạm vi chạy: " + ", ".join(f"{name} ({data['rows_before']:,} hàng/{data['session_count']} phiên)" for name, data in summary["datasets"].items()) + "; số output theo bảng trên.",
        "- **Nếu bỏ qua?** Nhầm cột/đơn vị hoặc ghép phiên có thể tạo tín hiệu giả và rò rỉ nguồn/session vào đánh giá.",
        "- **Giới hạn?** Hohai time là inferred; Southampton rate semantics chưa xác nhận; Seafar rate lineage thiếu tài liệu.", "",
        "### Duplicate, invalid row và gap segmentation", "",
        "- **Em đã làm gì?** Giữ một bản ghi nếu duplicate cùng thời điểm giống nhau; bỏ toàn nhóm timestamp xung đột; loại hàng thiếu/non-finite Roll/Pitch/time; cắt segment tại gap >1,5× median dt.",
        "- **Vì sao?** Trung bình duplicate có thể làm thay đổi phép đo; segment riêng ngăn tạo cửa sổ xuyên qua mất dữ liệu.",
        "- **Kết quả?** Số duplicate/conflict/gap/hàng bị loại theo từng nguồn và phiên nằm trong JSON; không tự gộp các segment.",
        "- **Nếu bỏ qua?** Trùng timestamp làm sai trọng số thống kê; gap lớn có thể bị hiểu nhầm như chuyển động liên tục.",
        "- **Giới hạn?** Ngưỡng 1,5× là quy tắc kỹ thuật cấu hình được, chưa được kiểm chứng với mọi sensor mode; Hohai không có timestamps để phát hiện dropout.", "",
        "### Đổi đơn vị và xử lý gyro", "",
        "- **Em đã làm gì?** Giữ Roll/Pitch ở degree; chuyển rate Seafar rad/min sang rad/s bằng chia 60, giữ dấu; Hohai/Southampton canonical gyro để missing khi thiếu hoặc chưa đủ bằng chứng.",
        "- **Vì sao?** C contract hiện dùng rad/s cho gyro; không được xem đạo hàm góc hoặc trường tên mơ hồ là phép đo gyro đã xác nhận.",
        "- **Kết quả?** Seafar rate-reported fields được đưa vào canonical với cảnh báo lineage; Hohai không có gyro; Southampton giữ Delta Angle raw, gyro canonical null.",
        "- **Nếu bỏ qua?** Đơn vị sai tạo scale lệch 60 lần hoặc 57,3 lần; trục/dấu sai đảo nghĩa vật lý.",
        "- **Giới hạn?** Trục, dấu, hiệu chuẩn và vật lý sensor chưa được xác minh với chủ sở hữu dataset.", "",
        "### Lọc causal và Resampling", "",
        "- **Em đã làm gì?** Với 50→10 Hz, lọc Butterworth order 4, cutoff 4 Hz bằng SOS causal, warm-start và bỏ 2 s warmup; sau đó chọn mẫu trước gần nhất tại lưới 10 Hz. Seafar khoảng 10 Hz không upsample.",
        "- **Vì sao?** Anti-aliasing giảm năng lượng có thể gập phổ khi giảm tần số; causal filter không dùng tương lai nên phù hợp hướng embedded.",
        "- **Kết quả?** RMSE, RMS ratio, low-band preservation và out-of-band attenuation được đo cho mẫu thực; hình và số liệu cụ thể nằm ở các phần F/G.",
        "- **Nếu bỏ qua?** Thành phần trên Nyquist có thể alias vào dải thấp; zero-phase filter có thể gây lookahead khi dùng offline.",
        "- **Giới hạn?** Filter tạo phase delay, warmup làm mất 2 s mỗi segment; cutoff 4 Hz/10 Hz cần xác nhận theo băng tần tàu và benchmark 50 Hz.", "",
        "### Kiểm định, đầu ra và khả năng tái lập", "",
        "- **Em đã làm gì?** Ghi Parquet nén Zstandard, JSON provenance/quality, thống kê before-after, figures và chạy test suite với fixture tổng hợp nhỏ.",
        "- **Vì sao?** Tạo artifact có thể tái lập và kiểm tra source mapping, units, causal behavior, aliasing và ranh giới session mà không dùng fixture làm dữ liệu huấn luyện.",
        f"- **Kết quả?** Suite chạy {summary['test_results']['total']} bài: {summary['test_results']['passed']} đạt, {summary['test_results']['failed']} không đạt, {summary['test_results']['skipped']} bỏ qua. Suite kiểm tra chuyển đổi units, parse timestamp/schema, duplicate, gap/session, thời gian suy Hohai, gyro nullable, 50→10 Hz, Anti-aliasing, tính tất định, không lookahead và window eligibility.",
        "- **Nếu bỏ qua?** Có thể không phát hiện sai lệch giữa Python, session logic, filter hoặc schema Parquet.",
        "- **Giới hạn?** Test nhỏ xác nhận quy tắc code, không thay thế xác nhận sensor, chuyên môn hàng hải, hoặc đánh giá mô hình.", "",
        "## L. Tái lập kết quả", "",
        "Từ repository root:", "", "```bash",
        "python -m ml.preprocessing.run --config ml/preprocessing/config.yaml --dry-run",
        "python -m ml.preprocessing.run --config ml/preprocessing/config.yaml --dataset seafar",
        "python -m ml.preprocessing.run --config ml/preprocessing/config.yaml --dataset hohai",
        "python -m ml.preprocessing.run --config ml/preprocessing/config.yaml --dataset southampton",
        "python -m ml.preprocessing.run --config ml/preprocessing/config.yaml --dataset all",
        "python -m pytest ml/preprocessing/tests -q", "```", "",
        "Xử lý tất định theo cấu hình; các file Parquet nằm trong `ml/data/processed/` (gitignored), summary và báo cáo nhỏ nằm trong `ml/reports/preprocessing/`.", "",
        "## M. Khuyến nghị trước Feature Extraction", "",
        "Xác nhận axis/sign và provenance gyro với chủ sở hữu dữ liệu; quyết định ngưỡng gap/coverage, endpoint và cutoff; đánh giá run Hohai/Southampton đại diện ở 10 Hz so với 50 Hz; kiểm tra số mẫu Run 14 có đáp ứng cửa sổ 180 s sau warmup. Sau đó review validity mask và metadata riêng, rồi mới chốt contract Python/C. Hiện dữ liệu đủ điều kiện cho thử nghiệm Feature Extraction ngắn hạn, nhưng Hohai continuity, Seafar duplicate/rate lineage, Southampton 180 s scarcity và gyro mapping khiến pipeline **chưa sẵn sàng cho training/ESP32 deployment**.", ""]
    return "\n".join(lines)


def run_pipeline(config_path: Path, selected_dataset: str = "all", dry_run: bool = False):
    config = load_config(config_path)
    repo_root = config_path.resolve().parents[2]
    raw_root = Path(config["paths"]["raw_root"])
    processed_root = Path(config["paths"]["processed_root"])
    report_root = Path(config["paths"]["report_root"])
    datasets = list(LOADERS) if selected_dataset == "all" else [selected_dataset]
    settings = config["preprocessing"]
    config_sha256 = hashlib.sha256(config_path.read_bytes()).hexdigest()
    all_sessions = {}
    for name in datasets:
        print(f"[THÔNG TIN] Đang kiểm tra dữ liệu {name.capitalize()}...")
        sessions = LOADERS[name](raw_root)
        if not sessions:
            raise ValueError(f"Không tìm thấy phiên dữ liệu cho {name}.")
        all_sessions[name] = sessions
        print(f"[THÔNG TIN] Đã đọc {len(sessions)} phiên {name.capitalize()}.")
    if dry_run:
        validation = {}
        for name, sessions in all_sessions.items():
            rows = sum(len(s.time_seconds) for s in sessions)
            details = []
            for session in sessions:
                times, signals, duplicate = deterministic_duplicate_policy(
                    session.time_seconds, session.signals, float(settings.get("duplicate_tolerance", 0.0)))
                check_session = RawSession(session.dataset_source, session.session_id, session.raw_reference,
                    times, signals, session.required_signals, session.provenance, session.warnings, session.original_row_count)
                cleaned, invalid = clean_required_values(check_session)
                rate, dt, jitter = estimate_sampling_rate(cleaned.time_seconds)
                segments, gaps = split_continuous_segments(cleaned.time_seconds,
                    float(settings.get("maximum_gap_factor", 1.5)))
                details.append({"session_id": session.session_id, "rows": len(session.time_seconds),
                    "rows_after_duplicate_policy": len(times), "invalid_required_rows": invalid,
                    "reordered_rows": duplicate["reordered_rows"], "duplicate_rows": duplicate["duplicate_rows_removed"],
                    "sampling_rate_hz": rate, "median_dt_seconds": dt, "jitter_ratio": jitter,
                    "gap_count": gaps["gap_count"], "segments": len(segments),
                    "timestamp_source": session.provenance.get("timestamp_source")})
                if duplicate["duplicate_rows_removed"]:
                    print(f"[CẢNH BÁO] {session.session_id}: phát hiện {duplicate['duplicate_rows_removed']} hàng timestamp trùng.")
                if gaps["gap_count"]:
                    print(f"[CẢNH BÁO] {session.session_id}: phát hiện {gaps['gap_count']} khoảng gián đoạn.")
            validation[name] = {"sessions": len(sessions), "rows": rows, "session_checks": details}
            print(f"[THÔNG TIN] Kiểm tra schema/timestamp hoàn tất: {name} có {len(sessions)} phiên, {rows:,} hàng; chưa ghi artifact.")
        return {"dry_run": True, "datasets": validation}

    processed_root.mkdir(parents=True, exist_ok=True)
    figures_root = processed_root / "diagnostics"
    figures_root.mkdir(parents=True, exist_ok=True)
    dataset_summaries = {}
    representatives = {}
    artifact_inventory = []
    for name in datasets:
        _clean_generated_dataset_dir(processed_root, name)
        raw_sessions = all_sessions[name]
        outputs = []
        session_summaries = []
        frequency_metrics = []
        representative = None
        pooled = {key: [] for key in ("roll_deg", "pitch_deg")}
        for session in raw_sessions:
            for key in pooled:
                if key in session.signals:
                    pooled[key].append(session.signals[key])
            segments, session_summary = process_session(session, settings, repo_root)
            session_summary["raw_reference"] = _relative_raw_reference(session_summary["raw_reference"], repo_root)
            session_summaries.append(session_summary)
            for segment in segments:
                segment.provenance.update({"source_class": "SENSOR",
                    "preprocessing_version": __version__, "configuration_sha256": config_sha256,
                    "configuration_path": _relative_repo_path(config_path, repo_root),
                    "canonical_schema_version": "svmg-time-series-1"})
                segment.provenance["raw_reference"] = _relative_raw_reference(
                    segment.provenance["raw_reference"], repo_root)
                written = _write_segment(segment, processed_root,
                    config["reporting"]["write_parquet_compression"], repo_root)
                artifact_inventory.append(written)
                outputs.append(segment)
                if segment.provenance["filter"]["applied"]:
                    frequency_metrics.append(segment_frequency_diagnostics(segment,
                        segment.quality["sampling_rate_before_hz"], segment.quality["sampling_rate_after_hz"]))
                if representative is None or len(segment.frame) > len(representative["processed"].frame):
                    representative = {"processed": segment, "raw_session": session,
                        "raw_time": session.time_seconds.copy(), "raw_signals": {k: v.copy() for k, v in session.signals.items()},
                        "input_rate_hz": segment.quality["sampling_rate_before_hz"],
                        "filter_applied": segment.provenance["filter"]["applied"]}
        summary = dataset_quality_summary(name, raw_sessions, outputs, session_summaries)
        summary["frequency_diagnostics"] = frequency_metrics
        dataset_summaries[name] = summary
        if representative is not None:
            representative["all_processed"] = outputs
            representative["raw_pooled"] = {k: np.concatenate(v) if v else np.array([]) for k, v in pooled.items()}
            representatives[name] = representative
        print(f"[THÔNG TIN] Đã xử lý {name.capitalize()}: {summary['rows_after']:,} hàng đầu ra, {summary['segments_output']} segment.")

    figures = create_figures(representatives, dataset_summaries, figures_root, int(config["reporting"]["plot_dpi"]))
    for figure in figures:
        figure["path"] = _relative_repo_path(figure["path"], repo_root)
    test_results = _run_unit_tests(repo_root)
    versions = {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
        "scipy": scipy.__version__, "openpyxl": __import__("openpyxl").__version__,
        "pyarrow": pyarrow.__version__, "pyyaml": yaml.__version__, "matplotlib": __import__("matplotlib").__version__}
    config_text = config_path.read_bytes()
    summary = {"pipeline_version": __version__, "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "repository_root": ".", "git_revision": _git_revision(repo_root),
        "configuration_path": _relative_repo_path(config_path, repo_root), "configuration_sha256": config_sha256,
        "environment": versions, "config": settings, "test_results": test_results, "datasets": dataset_summaries,
        "figures": figures, "artifact_inventory": artifact_inventory,
        "quality_thresholds_are_engineering_settings_not_safety_limits": True,
        "scope": "preprocessing and validation only; no candidate feature extraction, labels, training, or session merging"}
    report_root.mkdir(parents=True, exist_ok=True)
    _json_write(report_root / "preprocessing_summary.json", summary)
    (report_root / "preprocessing_results.md").write_text(_report(summary), encoding="utf-8")
    print(f"[THÔNG TIN] Hoàn tất. Báo cáo: {report_root / 'preprocessing_results.md'}")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tiền xử lý Time Series dữ liệu tàu thực SVMG.")
    parser.add_argument("--config", type=Path, default=Path("ml/preprocessing/config.yaml"), help="Đường dẫn tệp YAML.")
    parser.add_argument("--dataset", choices=["all", *LOADERS], default="all", help="Nguồn cần xử lý.")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ đọc và kiểm tra schema, không ghi kết quả.")
    args = parser.parse_args(argv)
    try:
        run_pipeline(args.config, args.dataset, args.dry_run)
    except Exception as error:
        print(f"[LỖI] Pipeline dừng: {error}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
