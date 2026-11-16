from __future__ import annotations

import numpy as np

from .common import finite_stats
from .signal_processing import frequency_power

SIGNALS = ("roll_deg", "pitch_deg", "gyro_x_rad_s", "gyro_y_rad_s")


def aligned_comparison(aligned: dict[str, dict[str, np.ndarray]]) -> dict:
    result = {}
    for name, pair in aligned.items():
        before = np.asarray(pair["before"], dtype=np.float64)
        after = np.asarray(pair["after"], dtype=np.float64)
        valid = np.isfinite(before) & np.isfinite(after)
        before, after = before[valid], after[valid]
        if not len(before):
            result[name] = {"aligned_samples": 0, "rmse": None, "correlation": None,
                             "rms_before": None, "rms_after": None, "rms_ratio_after_over_before": None}
            continue
        rms_before = float(np.sqrt(np.mean(before ** 2)))
        rms_after = float(np.sqrt(np.mean(after ** 2)))
        corr = float(np.corrcoef(before, after)[0, 1]) if len(before) > 1 and np.std(before) and np.std(after) else None
        result[name] = {"aligned_samples": int(len(before)),
            "rmse": float(np.sqrt(np.mean((after - before) ** 2))), "correlation": corr,
            "rms_before": rms_before, "rms_after": rms_after,
            "rms_ratio_after_over_before": rms_after / rms_before if rms_before > 0 else None,
            "peak_to_peak_before": float(np.ptp(before)), "peak_to_peak_after": float(np.ptp(after))}
    return result


def segment_frequency_diagnostics(segment, sampling_rate_before: float, sampling_rate_after: float) -> dict:
    metrics = {}
    for name in ("roll_deg", "pitch_deg"):
        pair = segment.aligned.get(name)
        if pair is None:
            continue
        raw_full = pair["raw_full"]
        filtered_full = pair["filtered_full"]
        if sampling_rate_before > sampling_rate_after * 1.05:
            nyquist = sampling_rate_after / 2
            bands = {"low_frequency_before_power": (0.1, min(2.0, nyquist - 0.2)),
                     "low_frequency_after_filter_power": (0.1, min(2.0, nyquist - 0.2)),
                     "out_of_band_before_filter_power": (nyquist + 0.25, sampling_rate_before / 2)}
            low_before = frequency_power(raw_full, sampling_rate_before, *bands["low_frequency_before_power"])
            low_after = frequency_power(filtered_full, sampling_rate_before, *bands["low_frequency_after_filter_power"])
            out_before = frequency_power(raw_full, sampling_rate_before, *bands["out_of_band_before_filter_power"])
            out_after = frequency_power(filtered_full, sampling_rate_before, *bands["out_of_band_before_filter_power"])
            metrics[name] = {"source_rate_hz": sampling_rate_before, "target_rate_hz": sampling_rate_after,
                "low_band_hz": list(bands["low_frequency_before_power"]),
                "out_of_band_hz": list(bands["out_of_band_before_filter_power"]),
                "low_band_power_before": low_before, "low_band_power_after_filter": low_after,
                "low_band_power_ratio": low_after / low_before if low_before and low_after is not None else None,
                "out_of_band_power_before": out_before, "out_of_band_power_after_filter": out_after,
                "out_of_band_attenuation_db": (10 * np.log10(out_after / out_before)
                    if out_before and out_after is not None and out_after > 0 else None),
                "interpretation": "Welch band-power ratio before/after causal filter at original sample rate; not a safety threshold."}
        else:
            metrics[name] = {"source_rate_hz": sampling_rate_before, "target_rate_hz": sampling_rate_after,
                "low_band_power_ratio": None, "out_of_band_attenuation_db": None,
                "interpretation": "Không downsample; không áp anti-alias filter."}
    return metrics


def dataset_quality_summary(dataset: str, sessions: list, segments: list, session_summaries: list) -> dict:
    before_values = {name: [] for name in SIGNALS}
    after_values = {name: [] for name in SIGNALS}
    aligned_values = {name: {"before": [], "after": []} for name in SIGNALS}
    for session in sessions:
        for name in SIGNALS:
            if name in session.signals:
                before_values[name].append(session.signals[name])
    for segment in segments:
        for name in SIGNALS:
            if name not in segment.frame:
                continue
            after_values[name].append(segment.frame[name].to_numpy(dtype=np.float64))
            if name in segment.aligned:
                aligned_values[name]["before"].append(segment.aligned[name]["before"])
                aligned_values[name]["after"].append(segment.aligned[name]["after"])
    before_stats = {name: finite_stats(np.concatenate(arrays) if arrays else np.array([]))
                    for name, arrays in before_values.items()}
    after_stats = {name: finite_stats(np.concatenate(arrays) if arrays else np.array([]))
                   for name, arrays in after_values.items()}
    comparison = {}
    for name in SIGNALS:
        pre = np.concatenate(aligned_values[name]["before"]) if aligned_values[name]["before"] else np.array([])
        post = np.concatenate(aligned_values[name]["after"]) if aligned_values[name]["after"] else np.array([])
        comparison[name] = aligned_comparison({name: {"before": pre, "after": post}})[name]
    return {"dataset_source": dataset, "session_count": len(sessions), "segments_output": len(segments),
        "rows_before": int(sum(s.original_row_count for s in sessions)),
        "rows_after_duplicate_resolution": int(sum(s["rows_after_duplicate_resolution"] for s in session_summaries)),
        "rows_after_required_validation": int(sum(s["rows_after_required_validation"] for s in session_summaries)),
        "rows_after": int(sum(len(seg.frame) for seg in segments)),
        "rows_removed_exact_duplicates": int(sum(s["rows_removed_exact_duplicates"] for s in session_summaries)),
        "rows_removed_conflicting_duplicate_groups": int(sum(s["rows_removed_conflicting_duplicate_groups"] for s in session_summaries)),
        "conflicting_timestamp_groups": int(sum(s["conflicting_timestamp_groups"] for s in session_summaries)),
        "invalid_required_rows_removed": int(sum(s["invalid_required_rows_removed"] for s in session_summaries)),
        "input_reordered_rows": int(sum(s["input_reordered_rows"] for s in session_summaries)),
        "short_segments_skipped": int(sum(s["short_segments_skipped"] for s in session_summaries)),
        "rows_removed_short_segments": int(sum(s["rows_removed_short_segments"] for s in session_summaries)),
        "rows_removed_by_resampling_and_filter_warmup": int(sum(s["rows_removed_by_resampling_and_filter_warmup"] for s in session_summaries)),
        "gap_count": int(sum(s["gap_count"] for s in session_summaries)),
        "continuous_segments_detected": int(sum(s["continuous_segments_detected"] for s in session_summaries)),
        "warmup_target_samples_dropped": int(sum(s["warmup_target_samples_dropped"] for s in session_summaries)),
        "eligible_60s_segments": int(sum(s["eligible_60s_segments"] for s in session_summaries)),
        "eligible_180s_segments": int(sum(s["eligible_180s_segments"] for s in session_summaries)),
        "duration_before_cumulative_seconds": float(sum(s["input_duration_seconds"] for s in session_summaries)),
        "duration_after_cumulative_seconds": float(sum(seg.quality["segment_duration_after_seconds"] for seg in segments)),
        "sampling_rate_before_hz_median": float(np.median([s["input_sampling_hz"] for s in session_summaries if s["input_sampling_hz"]])) if session_summaries else None,
        "sampling_rate_after_hz_median": float(np.median([s["target_sampling_hz_effective"] for s in session_summaries if s["target_sampling_hz_effective"]])) if session_summaries else None,
        "sampling_irregularity_median_ratio": float(np.median([s["sampling_irregularity_median_ratio"] for s in session_summaries])) if session_summaries else None,
        "missing_percent_before": {name: before_stats[name]["missing"] / max(1, before_stats[name]["count"] + before_stats[name]["missing"]) * 100 for name in SIGNALS},
        "missing_percent_after": {name: after_stats[name]["missing"] / max(1, after_stats[name]["count"] + after_stats[name]["missing"]) * 100 for name in SIGNALS},
        "statistics_before": before_stats, "statistics_after": after_stats,
        "time_aligned_comparison": comparison,
        "gyro_availability": {name: "AVAILABLE" if after_stats[name]["count"] else "UNAVAILABLE" for name in ("gyro_x_rad_s", "gyro_y_rad_s")},
        "session_summaries": session_summaries}
