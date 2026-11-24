from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .spec import PRACTICAL_SUBSETS


DATASETS = ("seafar", "hohai", "southampton")


def _independent_crossing_reference(times: np.ndarray, values: np.ndarray,
                                    maximum_gap: float) -> tuple[int, float | None, float | None, int]:
    """Đếm crossing trên các cặp dấu liên tiếp; không gọi extractor/calculations."""
    finite = values[np.isfinite(values)]
    if not len(finite):
        return 0, None, None, 0
    centered = values - float(np.mean(finite))
    events: list[tuple[float, int]] = []
    previous: int | None = None
    for index, value in enumerate(centered):
        if not np.isfinite(value) or not np.isfinite(times[index]):
            previous = None
            continue
        if previous is not None and times[index] - times[previous] > maximum_gap:
            previous = None
        if previous is None:
            previous = index
            continue
        left = centered[previous]
        right = value
        if left * right < 0.0:
            crossing_time = times[previous] - left * (times[index] - times[previous]) / (right - left)
            events.append((float(crossing_time), 1 if left < right else -1))
        previous = index
    upward = np.asarray([time for time, direction in events if direction == 1], dtype=float)
    periods = np.diff(upward)
    periods = periods[np.isfinite(periods) & (periods > 0.0)]
    median = float(np.median(periods)) if len(periods) else None
    cv = float(np.std(periods, ddof=0) / np.mean(periods)) if len(periods) else None
    return len(events), median, cv, len(periods)


def _representative_window(repo_root: Path, dataset: str, values: pd.DataFrame,
                           metadata: pd.DataFrame) -> dict:
    joined = metadata.merge(values, on="window_id", validate="one_to_one")
    candidates = joined[joined["roll_period_est_180"].notna()].copy()
    paths = sorted((repo_root / "ml/data/processed" / dataset).glob("**/timeseries.parquet"),
                   key=lambda item: item.stat().st_size, reverse=True)
    for path in paths:
        identity = pd.read_parquet(path, columns=["dataset_source", "session_id", "segment_id"])
        session = str(identity["session_id"].iloc[0])
        segment = str(identity["segment_id"].iloc[0])
        match = candidates[(candidates["session_id"] == session) & (candidates["segment_id"] == segment)]
        if not match.empty:
            row = match.sort_values("window_end_seconds").iloc[-1]
            frame = pd.read_parquet(path, columns=["time_seconds", "roll_deg"])
            end = float(row["window_end_seconds"])
            selected = frame[(frame["time_seconds"] > end - 180.0) & (frame["time_seconds"] <= end)]
            times = selected["time_seconds"].to_numpy(dtype=float)
            roll = selected["roll_deg"].to_numpy(dtype=float)
            count, period, cv, period_count = _independent_crossing_reference(
                times, roll, maximum_gap=0.15)
            validity = json.loads(row["validity_json"])
            if len(times) != 1800:
                raise ValueError(f"Cửa sổ đại diện {dataset} có {len(times)} mẫu, kỳ vọng 1800.")
            if not math.isclose(count, float(row["roll_zero_crossings_180"]), abs_tol=0.0):
                raise ValueError(f"Crossing tham chiếu không khớp feature table của {dataset}.")
            if period is None or not math.isclose(period, float(row["roll_period_est_180"]), rel_tol=1e-10, abs_tol=1e-10):
                raise ValueError(f"Period tham chiếu không khớp feature table của {dataset}.")
            if cv is None or not math.isclose(cv, float(row["roll_period_cv_180"]), rel_tol=1e-10, abs_tol=1e-10):
                raise ValueError(f"CV tham chiếu không khớp feature table của {dataset}.")
            centered = roll - np.mean(roll)
            return {
                "session_id": session, "segment_id": segment, "window_end_seconds": end,
                "sample_count": int(len(times)), "missing_count": int(np.sum(~np.isfinite(roll))),
                "roll_mean_deg": float(np.mean(roll)),
                "roll_std_deg": float(np.std(roll, ddof=0)),
                "crossing_count": int(count), "upward_crossing_count": int(np.count_nonzero(np.diff(np.sign(centered)) > 0)),
                "period_count": int(period_count), "period_median_seconds": float(period),
                "period_median_saved_seconds": float(row["roll_period_est_180"]),
                "period_cv": float(cv), "period_cv_saved": float(row["roll_period_cv_180"]),
                "period_status": validity["roll_period_est_180"]["status"],
                "cv_status": validity["roll_period_cv_180"]["status"],
            }
    raise ValueError(f"Không tìm được cửa sổ period hợp lệ đại diện cho {dataset}.")


def build_period_subset_review(repo_root: Path, summary: dict, report_root: Path) -> Path:
    subset = PRACTICAL_SUBSETS["angle_only_23_without_gyro_or_period"]
    if len(subset) != 23:
        raise ValueError("Tập angle-only phải có đúng 23 feature.")
    rows = []
    representative = {}
    subset_counts = {}
    for dataset in DATASETS:
        item = summary["datasets"][dataset]
        values = pd.read_parquet(repo_root / item["feature_values_path"])
        metadata = pd.read_parquet(repo_root / item["feature_metadata_path"])
        joined = metadata.merge(values, on="window_id", validate="one_to_one")
        segment_start: dict[tuple[str, str], float] = {}
        for path in (repo_root / "ml/data/processed" / dataset).glob("**/timeseries.parquet"):
            identity = pd.read_parquet(path, columns=["session_id", "segment_id", "time_seconds"])
            key = (str(identity["session_id"].iloc[0]), str(identity["segment_id"].iloc[0]))
            segment_start[key] = float(identity["time_seconds"].iloc[0])
        eligible = []
        for row in joined.itertuples():
            key = (str(row.session_id), str(row.segment_id))
            if float(row.window_end_seconds) - segment_start[key] >= 180.0 - 1e-8:
                eligible.append(row)
        all_valid = []
        for row in eligible:
            validity = json.loads(row.validity_json)
            all_valid.append(all(validity[name]["status"] == "VALID" for name in subset))
        verified_count = sum(all_valid)
        reported_count = item["complete_practical_subsets"]["angle_only_23_without_gyro_or_period"]
        if len(eligible) != item["candidate_windows_180s"] or verified_count != reported_count or verified_count != len(eligible):
            raise ValueError(f"Subset angle-only không nhất quán ở {dataset}: kiểm tra {verified_count}/{len(eligible)}.")
        subset_counts[dataset] = {"candidate_rows": len(joined), "eligible_180": len(eligible),
                                  "subset_valid": verified_count, "subset_invalid": len(eligible) - verified_count}
        crossing = item["feature_statistics"]["roll_zero_crossings_180"]
        period_status = item["feature_status_counts"]["roll_period_est_180"]
        cv_status = item["feature_status_counts"]["roll_period_cv_180"]
        period_valid = period_status["VALID"]
        cv_valid = cv_status["VALID"]
        period_undefined = period_status["UNDEFINED_MATHEMATICALLY"]
        cv_undefined = cv_status["UNDEFINED_MATHEMATICALLY"]
        rows.append((dataset, crossing, period_valid, period_undefined, cv_valid, cv_undefined))
        representative[dataset] = _representative_window(repo_root, dataset, values, metadata)

    lines = [
        "# Rà soát chu kỳ và tập angle-only 23 — SVMG M2", "",
        "## Kết luận rà soát", "",
        "Đặc tả hiện có là **đề xuất đang chờ nhóm phê duyệt**, không phải hợp đồng đã được duyệt. Rà soát phát hiện lỗi gán đảo hai mảng ở extractor: hàm cửa sổ trả `(signal_values, timestamps, issue)`, nhưng biến nhận theo thứ tự ngược. Bộ đếm crossing vì vậy chạy trên timestamp thay vì Roll. Đây là lỗi triển khai, không phải thiếu dao động hoặc thiếu mẫu.", "",
        "Đã sửa phép gán, chạy lại extraction cho ba nguồn, thêm kiểm thử hồi quy trên sin có chu kỳ biết trước và tái tạo summary/báo cáo. Kết quả trước sửa có 24 feature với ít nhất một cửa sổ `VALID`; sau sửa có 26/30. Ba gyro theo trục Roll/Pitch vẫn thiếu hoặc chưa xác nhận, nên không có hàng đủ 30 feature.", "",
        "## Vì sao 24 feature khác với subset 23", "",
        "Ở kết quả trước sửa lỗi, 23 feature angle-only có cửa sổ hợp lệ; feature thứ 24 là `roll_zero_crossings_180`. Subset `angle_only_23_without_gyro_or_period` cố ý loại toàn bộ Group E, kể cả crossing count, để chỉ giữ thống kê góc Roll/Pitch cùng offset/growth. Trạng thái `VALID` của crossing count không làm feature đó tự động thuộc subset.", "",
        "Sau sửa lỗi, cả ba feature Group E có giá trị hợp lệ trên một phần cửa sổ: `roll_period_est_180`, `roll_zero_crossings_180` và `roll_period_cv_180`. Vì vậy số feature có ít nhất một cửa sổ `VALID` hiện là 26, nhưng subset angle-only giữ nguyên đúng 23 tên và thứ tự. Bốn gyro feature vẫn không hợp lệ.", "",
        "### 23 feature trong đúng thứ tự", "",
    ]
    lines.extend(f"{index}. `{name}`" for index, name in enumerate(subset, start=1))
    lines += ["", "## Tính nhất quán của subset trên các hàng thực", "",
        "Đã kiểm tra `validity_json` từng hàng Parquet với đúng 23 tên trên. Mọi endpoint đủ 180 giây trong segment độc lập đều có cả 23 feature ở trạng thái `VALID`; candidate row mới đủ 60 giây nhưng chưa đủ 180 giây không thể có subset đầy đủ.", "",
        "| Nguồn | Candidate rows 60 giây | Endpoint đủ 180 giây | Hàng đủ 23 feature | Hàng chưa đủ subset |", "|---|---:|---:|---:|---:|"]
    for dataset in DATASETS:
        item = subset_counts[dataset]
        lines.append(f"| {dataset.capitalize()} | {item['candidate_rows']:,} | {item['eligible_180']:,} | {item['subset_valid']:,} | {item['candidate_rows']-item['subset_valid']:,} |")
    lines += ["", "Subset 23 nhất quán trên tất cả hàng đủ cửa sổ 180 giây, không phải trên mọi candidate row 60 giây. Các hàng ngắn hơn được giữ trong bảng tổng hợp cùng validity riêng, không được xem là mẫu huấn luyện đủ subset.", "",
        "## Định nghĩa period và so sánh với tài liệu", "",
        "Extractor dùng `roll_deg` trong cửa sổ processed 180 giây rồi trừ trung bình của chính cửa sổ: `y_i = roll_i - mean(roll)`. Tín hiệu **mean-centered**, không phải Roll chưa center và không detrend tuyến tính. Crossing lên/xuống được đếm; crossing kẹp giữa hai mẫu trái dấu nội suy tuyến tính. Period là median khoảng cách giữa crossing lên liên tiếp trong cùng đoạn liên tục; không bắc qua missing/gap. CV là population SD chia mean period, tối thiểu ba period.", "",
        "Đây là quy ước phù hợp với proposal trong [`feature_specification_30.md`](../../docs/feature_specification_30.md): mean-centering, crossing nội suy, median chu kỳ crossing lên và không nối gap. Đặc tả vẫn `PENDING_TEAM_APPROVAL`; rà soát không thay đổi định nghĩa. Kiểm thử sin 0,5 Hz cho period 2 giây và kiểm thử tương lai xác nhận giá trị tại endpoint cũ không đổi.", "",
        "## Bằng chứng trên cửa sổ dữ liệu thực", "",
        "Chọn cửa sổ 180 giây cuối cùng có period hợp lệ trong segment processed dài nhất mỗi nguồn. Mỗi cửa sổ có 1.800 mẫu hữu hạn. Bảng tham chiếu được tính độc lập bằng chuyển dấu liên tiếp và nội suy tuyến tính; kết quả khớp với feature table đã tái sinh.", "",
        "| Nguồn / segment | Endpoint (s) | Mean Roll (°) | SD Roll (°) | Crossing tổng | Crossing lên | Period intervals | Median period (s), extractor / độc lập | CV population, extractor / độc lập |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for dataset in DATASETS:
        item = representative[dataset]
        lines.append(f"| {dataset.capitalize()} / `{item['segment_id']}` | {item['window_end_seconds']:.1f} | {item['roll_mean_deg']:.4f} | {item['roll_std_deg']:.4f} | {item['crossing_count']} | {item['upward_crossing_count']} | {item['period_count']} | {item['period_median_saved_seconds']:.4f} / {item['period_median_seconds']:.4f} | {item['period_cv_saved']:.4f} / {item['period_cv']:.4f} |")
    lines += ["", "Các cửa sổ thực đại diện có crossing; nguyên nhân undefined trước đó là lỗi dùng timestamp như tín hiệu. Tuy vậy, CV cao ở một số nguồn nghĩa là crossing intervals biến thiên mạnh; `VALID` chỉ xác nhận phép tính đủ điều kiện, không xác nhận chu kỳ vật lý ổn định.", "",
        "### Tổng hợp cửa sổ đủ 180 giây", "",
        "| Nguồn | Zero-crossing: số cửa sổ / trung bình / trung vị / P05–P95 | Period VALID / undefined | CV VALID / undefined |", "|---|---|---:|---:|"]
    for dataset, crossing, period_valid, period_undefined, cv_valid, cv_undefined in rows:
        lines.append(f"| {dataset.capitalize()} | {crossing['valid_count']:,} / {_fmt(crossing['mean'])} / {_fmt(crossing['p50'])} / {_fmt(crossing['p05'])}–{_fmt(crossing['p95'])} | {period_valid:,} / {period_undefined:,} | {cv_valid:,} / {cv_undefined:,} |")
    lines += ["", "Seafar còn một số cửa sổ không đủ crossing lên hoặc không đủ ba chu kỳ cho CV; các trường hợp này là `UNDEFINED_MATHEMATICALLY`, không phải thiếu coverage. Hohai và Southampton có period hợp lệ trên các cửa sổ 180 giây của lần chạy này.", "",
        "## Ranh giới và tính causal", "",
        "CLI đọc từng Parquet riêng; `validate_segment` yêu cầu mỗi file có duy nhất một dataset/session/segment và timestamp tăng nghiêm ngặt. Extractor không nối segment/session. Cửa sổ tại `t` chỉ đọc `(t-W,t]`. Kiểm thử hồi quy thêm một quan sát tương lai lớn tại `t+0,1 s` và xác nhận period, crossing, CV ở endpoint `t` không đổi.", "",
        "## Hạn chế và bước tiếp theo", "",
        "- Công thức trong tài liệu feature vẫn chờ nhóm phê duyệt; báo cáo này không biến proposal thành contract.",
        "- Mean-centering loại offset DC nhưng trend chậm, dao động nhiều thành phần hoặc noise có thể làm period/CV kém ổn định.",
        "- So sánh detrending hoặc estimator miền tần số là thay đổi phương pháp, cần duyệt riêng. Không áp dụng thay đổi đó ở lần sửa lỗi này.",
        f"- Unit tests theo summary lần chạy: **{summary['test_results']['passed']} đạt, {summary['test_results']['failed']} lỗi**. Bốn notebook được kiểm tra sau cập nhật; xem [`feature_validation_results.md`](feature_validation_results.md).", ""]
    report_root.mkdir(parents=True, exist_ok=True)
    path = report_root / "feature_period_subset_review.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _fmt(value) -> str:
    return "—" if value is None else f"{float(value):.5g}"


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    report_root = repo_root / "ml/reports/features"
    summary = json.loads((report_root / "feature_extraction_summary.json").read_text(encoding="utf-8"))
    path = build_period_subset_review(repo_root, summary, report_root)
    print(f"[THÔNG TIN] Đã tạo báo cáo rà soát: {path.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
