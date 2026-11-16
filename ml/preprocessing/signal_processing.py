from __future__ import annotations

import math
from dataclasses import asdict

import numpy as np
import pandas as pd
from scipy.signal import butter, sosfilt, sosfilt_zi, welch

from .common import (clean_required_values, count_missing, deterministic_duplicate_policy,
                     estimate_sampling_rate, finite_stats, split_continuous_segments,
                     window_eligibility)
from .schemas import ProcessedSegment, RawSession


def lowpass_causal(values: np.ndarray, sampling_hz: float, cutoff_hz: float, order: int = 4) -> np.ndarray:
    """Áp dụng Butterworth thông thấp causal; khởi tạo trạng thái tại giá trị đầu."""
    values = np.asarray(values, dtype=np.float64)
    if not len(values):
        return values.copy()
    if not 0 < cutoff_hz < sampling_hz / 2:
        raise ValueError("Tần số cutoff phải nằm dưới Nyquist của tín hiệu nguồn.")
    sos = butter(order, cutoff_hz, btype="lowpass", fs=sampling_hz, output="sos")
    zi = sosfilt_zi(sos) * values[0]
    filtered, _ = sosfilt(sos, values, zi=zi)
    return filtered


def causal_previous_sample(source_times: np.ndarray, values: np.ndarray, target_times: np.ndarray):
    """Lấy mẫu trước gần nhất, không đọc giá trị có timestamp ở tương lai."""
    indexes = np.searchsorted(source_times, target_times, side="right") - 1
    valid = indexes >= 0
    safe = np.clip(indexes, 0, max(0, len(source_times) - 1))
    if len(source_times):
        age = target_times - source_times[safe]
        valid &= age >= -1e-12
    else:
        valid[:] = False
    output = np.full(len(target_times), np.nan, dtype=np.float64)
    if len(source_times):
        output[valid] = values[safe[valid]]
    return output, safe.astype(np.int64), valid


def process_session(session: RawSession, settings: dict, repository_root, output_root: str | None = None):
    """Làm sạch, phân đoạn, lọc causal và đưa một session lên lưới đích."""
    original_count = len(session.time_seconds)
    times, signals, duplicate_report = deterministic_duplicate_policy(
        session.time_seconds, session.signals, tolerance=float(settings.get("duplicate_tolerance", 0.0)))
    duplicate_removed = duplicate_report["duplicate_rows_removed"]
    # Exact duplicate rows are removed deterministically. Conflicting same-time groups
    # are removed in full; do not average measurements.
    ordered = RawSession(session.dataset_source, session.session_id, session.raw_reference,
        times, signals, session.required_signals, session.provenance, session.warnings, original_count)
    cleaned, invalid_dropped = clean_required_values(ordered)
    if len(cleaned.time_seconds) > 1 and np.any(np.diff(cleaned.time_seconds) <= 0):
        raise ValueError(f"Timestamp không tăng nghiêm ngặt sau xử lý trùng: {session.session_id}")

    fs, median_dt, jitter = estimate_sampling_rate(cleaned.time_seconds)
    if fs is None:
        raise ValueError(f"Không đủ timestamp hữu hạn để ước lượng Sampling Rate: {session.session_id}")
    boundaries, gap_report = split_continuous_segments(cleaned.time_seconds,
        float(settings.get("maximum_gap_factor", 1.5)))
    target_fs = float(settings["target_sampling_hz"])
    cutoff = float(settings["anti_alias_cutoff_hz"])
    order = int(settings["filter_order"])
    warmup = float(settings["filter_warmup_seconds"])
    min_duration = float(settings["minimum_segment_seconds"])
    output_segments = []
    dropped_warmup_target_samples = 0
    short_segments_skipped = 0
    rows_in_short_segments = 0
    per_segment = []
    signal_keys = list(cleaned.signals)

    for segment_number, (start, end) in enumerate(boundaries):
        seg_t = cleaned.time_seconds[start:end]
        seg_signals = {key: value[start:end] for key, value in cleaned.signals.items()}
        if len(seg_t) < 2 or seg_t[-1] - seg_t[0] < min_duration:
            short_segments_skipped += 1
            rows_in_short_segments += int(end - start)
            continue
        seg_fs, seg_dt, seg_jitter = estimate_sampling_rate(seg_t)
        if seg_fs is None:
            continue
        effective_fs = min(target_fs, seg_fs)  # no upsampling: no new measurements
        did_filter = seg_fs > target_fs * 1.05
        if did_filter and cutoff >= effective_fs / 2:
            raise ValueError("Anti-alias cutoff phải thấp hơn Nyquist của lưới đích.")
        target_count = int(math.floor((seg_t[-1] - seg_t[0]) * effective_fs + 1e-9)) + 1
        target_rel = np.arange(target_count, dtype=np.float64) / effective_fs
        target_global = seg_t[0] + target_rel
        indices = np.searchsorted(seg_t, target_global, side="right") - 1
        safe_indices = np.clip(indices, 0, len(seg_t) - 1)
        ages = target_global - seg_t[safe_indices]
        timing_valid = (indices >= 0) & (ages <= max(1.5 * seg_dt, 1.5 / effective_fs) + 1e-12)
        if did_filter:
            target_start = int(math.ceil(warmup * effective_fs - 1e-10))
            dropped_warmup_target_samples += min(target_start, len(target_rel))
            keep = (np.arange(len(target_rel)) >= target_start) & timing_valid
        else:
            keep = timing_valid
        if not np.any(keep):
            continue
        out_t = target_global[keep]
        out_indices = safe_indices[keep]
        output_signals = {}
        aligned = {}
        filtered_channels = []
        unfiltered_raw_channels = []
        for key in signal_keys:
            raw_values = seg_signals[key]
            selected = raw_values[out_indices].astype(np.float64, copy=True)
            processed = selected
            filtered_full = raw_values
            # Lọc mọi kênh liên tục đầy đủ trước khi giảm mẫu; giữ nguyên trường
            # hậu tố _raw vì chúng được lưu đúng như nguồn, chưa chuẩn hóa ngữ nghĩa.
            if did_filter and key.endswith("_raw"):
                unfiltered_raw_channels.append(key)
            elif did_filter and np.all(np.isfinite(raw_values)):
                filtered = lowpass_causal(raw_values, seg_fs, cutoff, order)
                filtered_full = filtered
                processed = filtered[out_indices]
                filtered_channels.append(key)
            output_signals[key] = processed
            aligned[key] = {"before": selected, "after": processed,
                            "raw_full": raw_values, "filtered_full": filtered_full}
        # Time is session-relative; the internal source timestamps are ordered seconds.
        frame = pd.DataFrame({"dataset_source": session.dataset_source,
            "session_id": session.session_id, "segment_id": f"segment_{segment_number:03d}",
            "time_seconds": out_t - cleaned.time_seconds[0], **output_signals})
        duration = float(out_t[-1] - out_t[0]) if len(out_t) > 1 else 0.0
        required_valid = np.ones(len(frame), dtype=bool)
        for key in session.required_signals:
            required_valid &= np.isfinite(frame[key].to_numpy(dtype=np.float64))
        valid_fraction = float(required_valid.mean()) if len(required_valid) else 0.0
        threshold = float(settings.get("valid_fraction_threshold", 0.95))
        eligibility = {}
        for window in (60, 180):
            expected = int(math.ceil(window * effective_fs))
            eligibility[f"{window}s"] = bool(duration >= window
                and len(frame) >= math.ceil(threshold * expected) and valid_fraction >= threshold)
        quality = {"input_segment_rows": int(end - start), "output_rows": int(len(frame)),
            "segment_duration_before_seconds": float(seg_t[-1] - seg_t[0]),
            "segment_duration_after_seconds": duration,
            "sampling_rate_before_hz": seg_fs, "sampling_rate_after_hz": effective_fs,
            "timestamp_jitter_median_ratio": seg_jitter, "filter_applied": bool(did_filter),
            "filter_warmup_seconds": warmup if did_filter else 0.0,
            "filter_warmup_target_samples_dropped": min(int(math.ceil(warmup * effective_fs)), len(target_rel)) if did_filter else 0,
            "valid_fraction_required_signals": valid_fraction,
            "window_eligibility": eligibility,
            "missing_after": count_missing(output_signals),
            "signal_statistics_before": {k: finite_stats(v["before"]) for k, v in aligned.items()},
            "signal_statistics_after": {k: finite_stats(v) for k, v in output_signals.items()}}
        provenance = {**session.provenance, "dataset_source": session.dataset_source,
            "session_id": session.session_id, "segment_id": frame["segment_id"].iloc[0],
            "raw_reference": session.raw_reference, "original_sampling_hz": fs,
            "target_sampling_hz_requested": target_fs, "target_sampling_hz_effective": effective_fs,
            "unit_conversions": session.provenance.get("unit_conversions", {}),
            "filter": {"method": "causal Butterworth SOS lowpass + previous-sample selection",
                "applied": bool(did_filter), "order": order if did_filter else None,
                "cutoff_hz": cutoff if did_filter else None, "initialization": "steady-state at first sample",
                "channels_filtered": filtered_channels,
                "raw_channels_preserved_without_filter": unfiltered_raw_channels,
                "warmup_seconds_dropped": warmup if did_filter else 0,
                "phase_delay": "causal phase delay retained; no future-looking compensation"},
            "timestamp_convention": "session-relative seconds; Hohai inferred from sample index",
            "warnings": session.warnings}
        output_segments.append(ProcessedSegment(session.dataset_source, session.session_id,
            frame["segment_id"].iloc[0], frame, provenance, quality, aligned))
        per_segment.append(quality)

    cleaned_duration = float(cleaned.time_seconds[-1] - cleaned.time_seconds[0]) if len(cleaned.time_seconds) > 1 else 0.0
    summary = {"dataset_source": session.dataset_source, "session_id": session.session_id,
        "raw_reference": session.raw_reference, "rows_before": int(original_count),
        "rows_after_duplicate_resolution": int(len(times)), "rows_after_required_validation": int(len(cleaned.time_seconds)),
        "rows_output": int(sum(len(part.frame) for part in output_segments)),
        "rows_removed_exact_duplicates": int(duplicate_report["identical_duplicate_rows_removed"]),
        "rows_removed_conflicting_duplicate_groups": int(duplicate_report["conflicting_rows_removed"]),
        "conflicting_timestamp_groups": int(duplicate_report["conflicting_timestamp_groups"]),
        "invalid_required_rows_removed": int(invalid_dropped), "input_reordered_rows": int(duplicate_report["reordered_rows"]),
        "short_segments_skipped": int(short_segments_skipped),
        "rows_removed_short_segments": int(rows_in_short_segments),
        "rows_removed_by_resampling_and_filter_warmup": int(max(0, len(cleaned.time_seconds) - rows_in_short_segments - sum(len(part.frame) for part in output_segments))),
        "input_duration_seconds": cleaned_duration, "input_sampling_hz": fs,
        "median_sample_interval_seconds": median_dt, "sampling_irregularity_median_ratio": jitter,
        "gap_count": int(gap_report["gap_count"]), "continuous_segments_detected": len(boundaries),
        "continuous_segments_output": len(output_segments), "warmup_target_samples_dropped": dropped_warmup_target_samples,
        "target_sampling_hz_requested": target_fs, "target_sampling_hz_effective": min(target_fs, fs),
        "eligible_60s_segments": sum(part.quality["window_eligibility"]["60s"] for part in output_segments),
        "eligible_180s_segments": sum(part.quality["window_eligibility"]["180s"] for part in output_segments),
        "duplicate_details": duplicate_report, "gap_details": gap_report,
        "warnings": session.warnings}
    return output_segments, summary


def frequency_power(values: np.ndarray, sampling_hz: float, low_hz: float, high_hz: float):
    values = np.asarray(values, dtype=np.float64)
    if len(values) < 32 or not np.all(np.isfinite(values)):
        return None
    freq, power = welch(values - np.mean(values), fs=sampling_hz,
                        nperseg=min(4096, len(values)), scaling="density")
    mask = (freq >= low_hz) & (freq < high_hz)
    return float(np.trapezoid(power[mask], freq[mask])) if np.count_nonzero(mask) >= 2 else None
