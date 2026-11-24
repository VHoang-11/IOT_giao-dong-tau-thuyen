from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .calculations import (diff_rms, dominant_sign_ratio, interquartile_range,
                          linear_r_squared, linear_slope, population_std,
                          period_values, rms, type7_quantile)
from .spec import FEATURE_NAMES, VALIDITY_STATUSES, WINDOW_SECONDS

REQUIRED_COLUMNS = (
    "dataset_source", "session_id", "segment_id", "time_seconds", "roll_deg",
    "pitch_deg", "gyro_x_rad_s", "gyro_y_rad_s",
)


class FeatureInputError(ValueError):
    """Lỗi schema hoặc metadata của một segment processed."""


@dataclass(frozen=True)
class FeatureResult:
    value: float | None
    status: str
    reason_code: str | None = None
    explanation_vi: str | None = None
    valid_samples: int | None = None

    def __post_init__(self):
        if self.status not in VALIDITY_STATUSES:
            raise ValueError(f"Trạng thái validity không hợp lệ: {self.status}")
        if self.status != "VALID" and self.value is not None:
            raise ValueError("Feature không hợp lệ phải có giá trị null.")


def _valid(value: float, count: int | None = None) -> FeatureResult:
    if not math.isfinite(float(value)):
        return _undefined("NON_FINITE_RESULT", "Kết quả số học không hữu hạn.", count)
    return FeatureResult(float(value), "VALID", valid_samples=count)


def _undefined(code: str, message: str, count: int | None = None) -> FeatureResult:
    return FeatureResult(None, "UNDEFINED_MATHEMATICALLY", code, message, count)


def _source_unavailable(status: str) -> FeatureResult:
    explanations = {
        "MISSING_SOURCE_SIGNAL": "Nguồn không có tín hiệu gyro đo trực tiếp.",
        "UNVERIFIED_SIGNAL_MAPPING": "Có trường rate nhưng mapping trục/đơn vị chưa được xác nhận.",
    }
    if status not in explanations:
        raise ValueError(f"Trạng thái nguồn gyro không hợp lệ: {status}")
    return FeatureResult(None, status, status, explanations[status])


def _invalid_window(code: str, message: str, count: int | None = None) -> FeatureResult:
    return FeatureResult(None, "INVALID_INPUT", code, message, count)


def _window_slice(times: np.ndarray, values: np.ndarray, end: float, width: float,
                  nominal_dt: float, minimum_fraction: float, segment_start: float,
                  input_rate_valid: bool, maximum_gap_factor: float) -> tuple[np.ndarray, np.ndarray, FeatureResult | None]:
    if end - segment_start < width - 1e-8:
        return np.array([]), np.array([]), FeatureResult(
            None, "INSUFFICIENT_WINDOW", "WINDOW_HISTORY_SHORT",
            f"Chưa có đủ {width:g} giây lịch sử trong segment.")
    lower = end - width
    left = int(np.searchsorted(times, lower, side="right"))
    right = int(np.searchsorted(times, end, side="right"))
    wt = times[left:right]
    wx = values[left:right]
    expected = int(round(width / nominal_dt))
    minimum = int(math.ceil(minimum_fraction * expected))
    if not input_rate_valid:
        return wx, wt, _invalid_window("SAMPLING_RATE_MISMATCH", "Sampling Rate của segment không khớp cấu hình.", len(wx))
    if len(wt) > 1 and np.any(np.diff(wt) > maximum_gap_factor * nominal_dt + 1e-8):
        return wx, wt, _invalid_window("TIMESTAMP_GAP", "Cửa sổ chứa khoảng thời gian lớn hơn 1,5 chu kỳ danh định.", len(wx))
    if len(wt) < minimum or len(wt) > expected + 1:
        return wx, wt, _invalid_window("TIME_SAMPLE_COVERAGE", "Số timestamp trong cửa sổ không đạt ngưỡng coverage.", len(wx))
    finite_count = int(np.isfinite(wx).sum())
    if finite_count < minimum:
        return wx, wt, _invalid_window("SIGNAL_VALID_COVERAGE", "Số mẫu hữu hạn của tín hiệu dưới 95% cửa sổ.", finite_count)
    return wx, wt, None


def _block(times: np.ndarray, values: np.ndarray, lower: float, upper: float,
           nominal_dt: float, minimum_fraction: float, maximum_gap_factor: float) -> tuple[np.ndarray, np.ndarray, bool]:
    left = int(np.searchsorted(times, lower, side="right"))
    right = int(np.searchsorted(times, upper, side="right"))
    block_t = times[left:right]
    block_x = values[left:right]
    expected = int(round(60.0 / nominal_dt))
    minimum = int(math.ceil(minimum_fraction * expected))
    valid = len(block_t) >= minimum and int(np.isfinite(block_x).sum()) >= minimum
    if len(block_t) > 1 and np.any(np.diff(block_t) > maximum_gap_factor * nominal_dt + 1e-8):
        valid = False
    return block_t, block_x, bool(valid)


def validate_segment(frame: pd.DataFrame, expected_dataset: str | None = None) -> tuple[str, str, str, np.ndarray]:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise FeatureInputError(f"Thiếu cột bắt buộc: {missing}")
    if frame.empty:
        raise FeatureInputError("Segment Parquet rỗng.")
    identity = {}
    for column in ("dataset_source", "session_id", "segment_id"):
        values = frame[column].dropna().astype(str).unique()
        if len(values) != 1:
            raise FeatureInputError(f"Cột metadata {column} phải có đúng một giá trị trong segment.")
        identity[column] = values[0]
    if expected_dataset and identity["dataset_source"] != expected_dataset:
        raise FeatureInputError("dataset_source trong Parquet không khớp thư mục nguồn.")
    times = pd.to_numeric(frame["time_seconds"], errors="coerce").to_numpy(dtype=np.float64)
    if not np.all(np.isfinite(times)):
        raise FeatureInputError("time_seconds chứa missing hoặc giá trị không hữu hạn.")
    if len(times) > 1 and np.any(np.diff(times) <= 0.0):
        raise FeatureInputError("time_seconds phải tăng nghiêm ngặt; không tự sắp xếp segment.")
    return identity["dataset_source"], identity["session_id"], identity["segment_id"], times


def extract_segment(frame: pd.DataFrame, provenance: dict, settings: dict,
                    expected_dataset: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Tính feature theo từng segment; metadata/validity nằm ở bảng riêng."""
    dataset, session, segment, times = validate_segment(frame, expected_dataset)
    fs = float(settings["target_sampling_hz"])
    dt = 1.0 / fs
    stride = float(settings["window_stride_seconds"])
    if stride <= 0 or not math.isclose(stride * fs, round(stride * fs), abs_tol=1e-8):
        raise ValueError("window_stride_seconds phải là số nguyên bội của chu kỳ lấy mẫu.")
    target_fs = provenance.get("target_sampling_hz_effective")
    measured_dt = float(np.median(np.diff(times))) if len(times) > 1 else math.nan
    rate_valid = (target_fs is not None and math.isclose(float(target_fs), fs, rel_tol=1e-6)
                  and math.isfinite(measured_dt) and math.isclose(measured_dt, dt, rel_tol=0.01, abs_tol=1e-7))

    signals = {}
    for name in ("roll_deg", "pitch_deg", "gyro_x_rad_s", "gyro_y_rad_s"):
        signals[name] = pd.to_numeric(frame[name], errors="coerce").to_numpy(dtype=np.float64)

    if len(times) < 2:
        return _empty_tables(), _empty_metadata(), _empty_summary(dataset, session, segment, rate_valid)
    start = float(times[0])
    first_endpoint_index = int(math.ceil(60.0 * fs - 1e-9))
    stride_samples = int(round(stride * fs))
    endpoint_indexes = np.arange(first_endpoint_index, len(times), stride_samples, dtype=np.int64)
    nominal_rows: list[dict] = []
    metadata_rows: list[dict] = []
    gyro_status = settings["source_gyro_status"].get(dataset, "MISSING_SOURCE_SIGNAL")
    epsilon = float(settings["numeric_zero_epsilon_deg"])
    r2_tolerance = float(settings["r_squared_zero_tolerance"])
    fraction = float(settings["minimum_valid_fraction"])
    maximum_gap_factor = float(settings.get("maximum_gap_factor", 1.5))

    for endpoint_index in endpoint_indexes:
        end = float(times[endpoint_index])
        windows: dict[tuple[str, int], tuple[np.ndarray, np.ndarray, FeatureResult | None]] = {}
        for signal in ("roll_deg", "pitch_deg", "gyro_x_rad_s", "gyro_y_rad_s"):
            for width in (60, 180):
                windows[(signal, width)] = _window_slice(
                    times, signals[signal], end, float(width), dt, fraction, start, rate_valid,
                    maximum_gap_factor)
        results: dict[str, FeatureResult] = {}

        def get_window(signal: str, width: int) -> tuple[np.ndarray, np.ndarray, FeatureResult | None]:
            return windows[(signal, width)]

        def base(signal: str, width: int, feature_name: str) -> tuple[np.ndarray, np.ndarray] | FeatureResult:
            x, t, issue = get_window(signal, width)
            if signal in {"gyro_x_rad_s", "gyro_y_rad_s"}:
                if gyro_status != "VALID":
                    return _source_unavailable(gyro_status)
            if issue is not None:
                return issue
            finite = np.isfinite(x)
            return x[finite], t[finite]

        def assign(name: str, signal: str, width: int, function):
            data = base(signal, width, name)
            if isinstance(data, FeatureResult):
                results[name] = data
                return
            x, _ = data
            results[name] = _valid(function(x), len(x))

        assign("roll_rms_60", "roll_deg", 60, rms)
        assign("roll_std_60", "roll_deg", 60, population_std)
        assign("roll_mean_60", "roll_deg", 60, lambda x: math.fsum(float(v) for v in x) / len(x))
        assign("roll_peak_to_peak_60", "roll_deg", 60, lambda x: float(np.max(x) - np.min(x)))
        assign("roll_abs_p95_60", "roll_deg", 60, lambda x: type7_quantile(np.abs(x), 0.95))
        assign("roll_abs_max_60", "roll_deg", 60, lambda x: float(np.max(np.abs(x))))
        assign("roll_iqr_60", "roll_deg", 60, interquartile_range)

        x, t, issue = get_window("roll_deg", 60)
        if issue is not None:
            results["roll_diff_rms_60"] = issue
        else:
            expected_pairs = int(round(60 * fs)) - 1
            minimum_pairs = int(math.ceil(fraction * expected_pairs))
            value, pair_count = diff_rms(x, t, dt, minimum_pairs)
            results["roll_diff_rms_60"] = (_valid(value, pair_count) if math.isfinite(value)
                else _invalid_window("ADJACENT_PAIR_COVERAGE", "Không đủ cặp mẫu liên tiếp đúng chu kỳ; không nội suy qua missing/gap.", pair_count))

        assign("gyro_x_rms_60", "gyro_x_rad_s", 60, rms)
        assign("gyro_x_abs_p95_60", "gyro_x_rad_s", 60, lambda x: type7_quantile(np.abs(x), 0.95))
        assign("gyro_x_std_60", "gyro_x_rad_s", 60, population_std)

        assign("roll_mean_180", "roll_deg", 180, lambda x: math.fsum(float(v) for v in x) / len(x))
        assign("roll_median_180", "roll_deg", 180, lambda x: type7_quantile(x, 0.50))
        assign("roll_mean_abs_180", "roll_deg", 180, lambda x: math.fsum(abs(float(v)) for v in x) / len(x))
        assign("roll_dominant_sign_ratio_180", "roll_deg", 180, dominant_sign_ratio)

        # _window_slice trả về (signal_values, timestamps, issue); giữ đúng thứ tự này.
        roll_x, roll_t, long_issue = get_window("roll_deg", 180)
        if long_issue is not None:
            for name in ("roll_segment_mean_std_180", "roll_mean_shift_180", "roll_rms_early_60",
                         "roll_rms_late_60", "roll_rms_ratio_180", "roll_rms_slope_180",
                         "roll_rms_trend_r2_180", "roll_p95_trend_slope_180"):
                results[name] = long_issue
        else:
            block_results = []
            for block in range(3):
                upper = end - (2 - block) * 60.0
                lower = upper - 60.0
                block_t, block_x, block_ok = _block(times, signals["roll_deg"], lower, upper, dt, fraction, maximum_gap_factor)
                finite_x = block_x[np.isfinite(block_x)]
                block_results.append((block_t, finite_x, block_ok))
            if not all(item[2] for item in block_results):
                bad = _invalid_window("SEGMENT_BLOCK_COVERAGE", "Ít nhất một block 60 giây không đạt coverage.")
                for name in ("roll_segment_mean_std_180", "roll_mean_shift_180", "roll_rms_early_60",
                             "roll_rms_late_60", "roll_rms_ratio_180", "roll_rms_slope_180",
                             "roll_rms_trend_r2_180", "roll_p95_trend_slope_180"):
                    results[name] = bad
            else:
                block_means = np.array([math.fsum(map(float, item[1])) / len(item[1]) for item in block_results])
                block_rms = np.array([rms(item[1]) for item in block_results])
                block_p95 = np.array([type7_quantile(np.abs(item[1]), 0.95) for item in block_results])
                centers = np.array([30.0, 90.0, 150.0])
                results["roll_segment_mean_std_180"] = _valid(population_std(block_means), 3)
                results["roll_mean_shift_180"] = _valid(float(block_means[2] - block_means[0]), len(block_results[0][1]) + len(block_results[2][1]))
                results["roll_rms_early_60"] = _valid(float(block_rms[0]), len(block_results[0][1]))
                results["roll_rms_late_60"] = _valid(float(block_rms[2]), len(block_results[2][1]))
                if block_rms[0] <= epsilon:
                    results["roll_rms_ratio_180"] = _undefined("EARLY_RMS_AT_OR_BELOW_EPSILON", "RMS block sớm không lớn hơn epsilon số học cấu hình; nhóm cần duyệt epsilon.", len(block_results[0][1]))
                else:
                    results["roll_rms_ratio_180"] = _valid(float(block_rms[2] / block_rms[0]), len(block_results[0][1]) + len(block_results[2][1]))
                results["roll_rms_slope_180"] = _valid(linear_slope(centers, block_rms) * 60.0, 3)
                trend_r2 = linear_r_squared(centers, block_rms, r2_tolerance)
                results["roll_rms_trend_r2_180"] = (_valid(trend_r2, 3) if math.isfinite(trend_r2)
                    else _undefined("CONSTANT_RMS_TREND", "SST của ba RMS block bằng hoặc dưới tolerance; R² không xác định.", 3))
                results["roll_p95_trend_slope_180"] = _valid(linear_slope(centers, block_p95) * 60.0, 3)

        if long_issue is not None:
            for name in ("roll_period_est_180", "roll_zero_crossings_180", "roll_period_cv_180"):
                results[name] = long_issue
        else:
            finite_roll = roll_x[np.isfinite(roll_x)]
            if len(finite_roll) < int(math.ceil(fraction * round(180 * fs))):
                issue180 = _invalid_window("ROLL_VALID_COVERAGE", "Roll trong cửa sổ 180 giây không đạt coverage.", len(finite_roll))
                for name in ("roll_period_est_180", "roll_zero_crossings_180", "roll_period_cv_180"):
                    results[name] = issue180
            else:
                periods, crossing_count = period_values(roll_t, roll_x, dt, maximum_gap_factor)
                results["roll_zero_crossings_180"] = _valid(float(crossing_count), len(finite_roll))
                upward_count = len(periods) + 1 if len(periods) else 0
                if upward_count < int(settings["period_minimum_upward_crossings"]):
                    results["roll_period_est_180"] = _undefined("INSUFFICIENT_UPWARD_CROSSINGS", "Cần ít nhất 3 crossing lên (2 chu kỳ) để ước lượng median period.", crossing_count)
                else:
                    results["roll_period_est_180"] = _valid(type7_quantile(periods, 0.50), crossing_count)
                if len(periods) < int(settings["period_cv_minimum_periods"]):
                    results["roll_period_cv_180"] = _undefined("INSUFFICIENT_PERIODS_FOR_CV", "Cần ít nhất 3 chu kỳ hoàn chỉnh (4 crossing lên) để tính CV.", crossing_count)
                else:
                    mean_period = math.fsum(map(float, periods)) / len(periods)
                    if mean_period <= 0.0:
                        results["roll_period_cv_180"] = _undefined("NON_POSITIVE_MEAN_PERIOD", "Mean period không dương.", len(periods))
                    else:
                        results["roll_period_cv_180"] = _valid(population_std(periods) / mean_period, len(periods))

        assign("pitch_rms_60", "pitch_deg", 60, rms)
        assign("pitch_std_60", "pitch_deg", 60, population_std)
        assign("pitch_peak_to_peak_60", "pitch_deg", 60, lambda x: float(np.max(x) - np.min(x)))
        assign("gyro_y_rms_60", "gyro_y_rad_s", 60, rms)

        missing = set(FEATURE_NAMES) - set(results)
        if missing:
            raise RuntimeError(f"Extractor chưa gán validity cho: {sorted(missing)}")
        if any(result.status not in VALIDITY_STATUSES for result in results.values()):
            raise RuntimeError("Extractor trả trạng thái validity ngoài contract.")
        window_id = f"{dataset}|{session}|{segment}|{end:.6f}"
        values = {name: results[name].value for name in FEATURE_NAMES}
        nominal_rows.append({"window_id": window_id, **values})
        validity = {name: asdict(results[name]) for name in FEATURE_NAMES}
        complete = all(results[name].status == "VALID" for name in FEATURE_NAMES)
        metadata_rows.append({
            "window_id": window_id, "dataset_source": dataset, "session_id": session,
            "segment_id": segment, "window_end_seconds": end,
            "feature_spec_version": "candidate-30-v1",
            "feature_extractor_version": "0.1.0",
            "preprocessing_version": provenance.get("preprocessing_version"),
            "preprocessing_configuration_sha256": provenance.get("configuration_sha256"),
            "source_metadata_json": json.dumps(provenance, ensure_ascii=False, sort_keys=True),
            "validity_json": json.dumps(validity, ensure_ascii=False, sort_keys=True),
            "complete_30_feature_row": complete,
        })

    value_frame = pd.DataFrame(nominal_rows, columns=["window_id", *FEATURE_NAMES])
    metadata_frame = pd.DataFrame(metadata_rows)
    summary = summarize_segment(dataset, session, segment, value_frame, metadata_frame, times, start, fs)
    return value_frame, metadata_frame, summary


def _empty_tables() -> pd.DataFrame:
    return pd.DataFrame(columns=["window_id", *FEATURE_NAMES])


def _empty_metadata() -> pd.DataFrame:
    return pd.DataFrame(columns=["window_id", "dataset_source", "session_id", "segment_id", "window_end_seconds", "validity_json"])


def _empty_summary(dataset: str, session: str, segment: str, rate_valid: bool) -> dict:
    return {"dataset_source": dataset, "session_id": session, "segment_id": segment,
            "candidate_windows_60s": 0, "candidate_windows_180s": 0,
            "rows_with_any_valid_feature": 0, "complete_30_feature_rows": 0,
            "invalid_input_rows": 0, "sampling_rate_valid": rate_valid}


def summarize_segment(dataset: str, session: str, segment: str, value_frame: pd.DataFrame,
                      metadata_frame: pd.DataFrame, times: np.ndarray, start: float, fs: float) -> dict:
    validity_rows = [json.loads(item) for item in metadata_frame.get("validity_json", [])]
    status_counts = {name: {status: 0 for status in VALIDITY_STATUSES} for name in FEATURE_NAMES}
    for validity in validity_rows:
        for name in FEATURE_NAMES:
            status_counts[name][validity[name]["status"]] += 1
    any_valid = sum(any(validity[name]["status"] == "VALID" for name in FEATURE_NAMES) for validity in validity_rows)
    invalid_rows = sum(any(validity[name]["status"] == "INVALID_INPUT" for name in FEATURE_NAMES) for validity in validity_rows)
    summary = {
        "dataset_source": dataset, "session_id": session, "segment_id": segment,
        "input_rows": int(len(times)), "segment_duration_seconds": float(times[-1] - times[0]) if len(times) > 1 else 0.0,
        "candidate_windows_60s": int(len(value_frame)),
        "candidate_windows_180s": int(sum(end - start >= 180.0 - 1e-8 for end in metadata_frame.get("window_end_seconds", []))),
        "rows_with_any_valid_feature": int(any_valid),
        "complete_30_feature_rows": int(metadata_frame.get("complete_30_feature_row", pd.Series(dtype=bool)).sum()),
        "invalid_input_rows": int(invalid_rows),
        "feature_status_counts": status_counts,
        "feature_statistics": {},
    }
    for name in FEATURE_NAMES:
        values = pd.to_numeric(value_frame.get(name, pd.Series(dtype=float)), errors="coerce").to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        if len(values):
            summary["feature_statistics"][name] = {
                "valid_count": int(len(values)), "mean": float(np.mean(values)),
                "std_population": float(np.std(values, ddof=0)), "min": float(np.min(values)),
                "max": float(np.max(values)), "p05": float(np.quantile(values, .05, method="linear")),
                "p50": float(np.quantile(values, .50, method="linear")),
                "p95": float(np.quantile(values, .95, method="linear")),
            }
        else:
            summary["feature_statistics"][name] = {"valid_count": 0, "mean": None, "std_population": None,
                "min": None, "max": None, "p05": None, "p50": None, "p95": None}
    return summary
