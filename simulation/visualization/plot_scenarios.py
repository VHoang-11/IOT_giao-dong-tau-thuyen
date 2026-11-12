"""Validate and plot SVMG scenarios without creating a training dataset.

Run with ``python -m simulation.visualization.plot_scenarios``. The default
sea-state profile is copied from the generator unit-test fixture and is only
an analysis fixture; it is not an official SS0--SS5 calibration.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import tempfile
from collections import Counter
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from simulation.generator.config import DatasetSplit, ScenarioCode, SimulationConfig
from simulation.generator.scenarios import ScenarioResult, ScenarioRunner


ANALYSIS_FIXTURE_PROFILE_DEG = {
    "SS0": 0.0,
    "SS1": 0.01,
    "SS2": 0.02,
    "SS3": 0.03,
    "SS4": 0.04,
    "SS5": 0.05,
}
LABEL_ORDER = ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH")
HIGH_ROLL_THRESHOLD_RAD = math.radians(6.0)
LABEL_NAME_TO_Y = {name: float(index) for index, name in enumerate(LABEL_ORDER)}


def parse_sea_state_profile(raw: Optional[str]) -> Tuple[Dict[str, float], bool]:
    """Parse a JSON profile in degrees; return profile and fixture-use flag."""
    if raw is None:
        return dict(ANALYSIS_FIXTURE_PROFILE_DEG), True
    try:
        profile = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("sea-state profile must be a JSON object") from exc
    required = {"SS0", "SS1", "SS2", "SS3", "SS4", "SS5"}
    if not isinstance(profile, dict) or set(profile) != required:
        raise ValueError("profile must define SS0 through SS5 exactly")
    normalized: Dict[str, float] = {}
    for state, value in profile.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("{} must be a numeric sigma in degrees".format(state))
        value = float(value)
        if not math.isfinite(value) or value < 0.0:
            raise ValueError("{} must be finite and non-negative".format(state))
        normalized[state] = value
    return normalized, False


def _rms(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return math.sqrt(sum(value * value for value in values) / len(values))


def _percentile(values: Sequence[float], percentile: float) -> Optional[float]:
    """Linearly interpolated percentile, implemented without third-party code."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _event(result: ScenarioResult) -> Mapping[str, Any]:
    return result.events[0] if result.events else {}


def _rolling_window_moments(values: Sequence[float], end_index: int,
                            window_samples: int) -> Tuple[float, float]:
    start = max(0, end_index - window_samples + 1)
    segment = values[start:end_index + 1]
    mean = sum(segment) / len(segment)
    centered_rms = math.sqrt(sum((value - mean) ** 2 for value in segment) / len(segment))
    return mean, centered_rms


def _s2_metrics(result: ScenarioResult) -> Dict[str, Any]:
    roll = result.true_roll_rad
    mean_rad = statistics.fmean(roll)
    rms_zero_rad = _rms(roll)
    rms_demeaned_rad = math.sqrt(statistics.pvariance(roll))
    p95_abs_rad = _percentile([abs(value) for value in roll], 0.95)
    event = _event(result)
    t0 = event.get("t0_s")
    heel_duration = (float(event["end_s"]) - float(t0)
                     if t0 is not None and "end_s" in event else 0.0)
    classified_indices = [index for index, label in enumerate(result.labels)
                          if label is not None]
    denominator = len(classified_indices)
    high_indices = [index for index in classified_indices
                    if result.labels[index] == "HIGH_ROLL"]
    persistent_count = sum(result.labels[index] == "PERSISTENT_OFFSET"
                           for index in classified_indices)

    # Diagnose the exact 60-second windows that triggered HIGH_ROLL. RMS in
    # scenarios.py is around zero. Centered RMS isolates oscillatory motion;
    # the remaining mean component is the static heel contribution.
    dt = float(result.metadata["dt_s"])
    window_samples = int(round(60.0 / dt)) + 1
    causes: Counter = Counter()
    for index in high_indices:
        mean_window, dynamic_rms = _rolling_window_moments(
            roll, index, window_samples)
        static_component = abs(mean_window)
        if dynamic_rms >= HIGH_ROLL_THRESHOLD_RAD and static_component < HIGH_ROLL_THRESHOLD_RAD:
            causes["A: oscillation-dominant"] += 1
        elif static_component >= HIGH_ROLL_THRESHOLD_RAD and dynamic_rms < HIGH_ROLL_THRESHOLD_RAD:
            causes["B: static-heel-dominant"] += 1
        else:
            causes["C: combined contribution"] += 1
    if not high_indices:
        predominant_cause = "No HIGH_ROLL windows"
    else:
        predominant_cause = causes.most_common(1)[0][0]

    return {
        "mean_roll_deg": math.degrees(mean_rad),
        "rms_about_zero_deg": math.degrees(rms_zero_rad or 0.0),
        "rms_demeaned_deg": math.degrees(rms_demeaned_rad),
        "p95_abs_roll_deg": math.degrees(p95_abs_rad or 0.0),
        "heel_duration_s": heel_duration,
        "high_roll_window_pct": 100.0 * len(high_indices) / denominator if denominator else 0.0,
        "persistent_offset_window_pct": 100.0 * persistent_count / denominator if denominator else 0.0,
        "high_roll_cause_windows": dict(causes),
        "predominant_high_roll_cause": predominant_cause,
    }


def _window_rms_between(result: ScenarioResult, start_s: float,
                        end_s: float) -> Optional[float]:
    values = [phi for timestamp, phi in zip(result.timestamps_s, result.true_roll_rad)
              if start_s <= timestamp < end_s]
    return _rms(values)


def _s3_metrics(result: ScenarioResult) -> Dict[str, Any]:
    event = _event(result)
    t0 = float(event["t0_s"])
    end = result.timestamps_s[-1] + float(result.metadata["dt_s"])
    before = _window_rms_between(result, max(0.0, t0 - 60.0), t0)
    early_end = min(t0 + 60.0, end)
    early = _window_rms_between(result, t0, early_end)
    late = _window_rms_between(result, max(t0, end - 60.0), end)
    return {
        "t0_s": t0,
        "h": event.get("h"),
        "Omega_rad_s": event.get("Omega_rad_s"),
        "rms_pre_60s_deg": None if before is None else math.degrees(before),
        "rms_first_post_60s_deg": None if early is None else math.degrees(early),
        "rms_last_post_60s_deg": None if late is None else math.degrees(late),
        "increased_from_first_to_last_post_window": (
            None if early is None or late is None else late > early
        ),
        "label_amplitude_growth_windows": sum(
            label == "AMPLITUDE_GROWTH" for label in result.labels
        ),
        "label_high_roll_windows": sum(label == "HIGH_ROLL" for label in result.labels),
        "possible_non_growth_reason": _s3_non_growth_reason(result, before, early, late),
    }


def _s3_non_growth_reason(result: ScenarioResult, before: Optional[float],
                          early: Optional[float], late: Optional[float]) -> str:
    if early is None or late is None:
        return "insufficient post-event interval"
    if late > early:
        return "observed late-window RMS increase"
    if early <= (before or 0.0):
        return "no early response above pre-event RMS; excitation may be weak or phase-sensitive"
    if "HIGH_ROLL" in result.labels:
        return "roll crossed HIGH_ROLL priority; AMPLITUDE_GROWTH is masked in those windows"
    return "no late-window increase; damping, stochastic phase, sampled T0/damping, or nonlinearity may dominate"


def _analyze_run(result: ScenarioResult) -> Dict[str, Any]:
    count = len(result.timestamps_s)
    finite = all(math.isfinite(value) for stream in (
        result.timestamps_s,
        result.true_roll_rad,
        result.true_roll_rate_rad_s,
        result.true_roll_acceleration_rad_s2,
        result.wave_excitation_rad,
        result.wave_sigma_rad,
    ) for value in stream)
    valid = (count == int(result.metadata["sample_count"]) and finite and
             len(result.imu_samples) == count and
             all(right > left for left, right in
                 zip(result.timestamps_s, result.timestamps_s[1:])) and
             all(sample.valid and sample.t == timestamp and
                 all(math.isfinite(value) for value in
                     (sample.ax, sample.ay, sample.az, sample.gx, sample.gy,
                      sample.gz, sample.t))
                 for sample, timestamp in zip(result.imu_samples, result.timestamps_s)))
    label_counts = Counter(label for label in result.labels if label is not None)
    classified = sum(label_counts.values())
    warmup = sum(label is None for label in result.labels)
    transition = sum(result.transition_flags)
    item: Dict[str, Any] = {
        "valid": valid,
        "classified_windows": classified,
        "warmup_windows": warmup,
        "transition_windows": transition,
        "label_counts": label_counts,
        "label_pct": {label: 100.0 * label_counts[label] / classified
                      if classified else 0.0 for label in LABEL_ORDER},
        "t0_s": _event(result).get("t0_s"),
        "expected_outcome_met": result.metadata["outcome_checks"].get("expected_outcome_met"),
    }
    if result.scenario_id is ScenarioCode.S2:
        item.update(_s2_metrics(result))
    if result.scenario_id is ScenarioCode.S3:
        item.update(_s3_metrics(result))
    return item


def _aggregate(scenario: ScenarioCode, results: Sequence[ScenarioResult],
               analyses: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    classified_counts: Counter = Counter()
    for analysis in analyses:
        classified_counts.update(analysis["label_counts"])
    classified_total = sum(classified_counts.values())
    total_warmup = sum(analysis["warmup_windows"] for analysis in analyses)
    total_transition = sum(analysis["transition_windows"] for analysis in analyses)
    total_windows = sum(len(result.labels) for result in results)
    return {
        "scenario": scenario.value,
        "sessions": len(results),
        "valid_sessions": sum(bool(item["valid"]) for item in analyses),
        "normal_pct": 100.0 * classified_counts["NORMAL"] / classified_total if classified_total else 0.0,
        "high_roll_pct": 100.0 * classified_counts["HIGH_ROLL"] / classified_total if classified_total else 0.0,
        "persistent_offset_pct": 100.0 * classified_counts["PERSISTENT_OFFSET"] / classified_total if classified_total else 0.0,
        "amplitude_growth_pct": 100.0 * classified_counts["AMPLITUDE_GROWTH"] / classified_total if classified_total else 0.0,
        "warmup_windows": total_warmup,
        "transition_windows": total_transition,
        "classified_windows": classified_total,
        "total_windows": total_windows,
        "failed_expected_outcomes": sum(
            item["expected_outcome_met"] is False for item in analyses
        ),
        "issues": _issues(scenario, analyses),
    }


def _issues(scenario: ScenarioCode, analyses: Sequence[Mapping[str, Any]]) -> str:
    messages: List[str] = []
    invalid = sum(not item["valid"] for item in analyses)
    if invalid:
        messages.append("{} invalid session(s)".format(invalid))
    failed = sum(item["expected_outcome_met"] is False for item in analyses)
    if failed:
        messages.append("{} nominal outcome miss(es)".format(failed))
    if scenario is ScenarioCode.S2:
        high = sum(item["label_counts"]["HIGH_ROLL"] > 0 for item in analyses)
        if high:
            messages.append("{} S2 session(s) include HIGH_ROLL priority".format(high))
    if scenario is ScenarioCode.S3:
        misses = sum(item["increased_from_first_to_last_post_window"] is False
                     for item in analyses)
        if misses:
            messages.append("{} session(s) lack measured RMS growth".format(misses))
    return "; ".join(messages) if messages else "none observed"


def _format_table(rows: Sequence[Mapping[str, Any]]) -> str:
    headers = ("Scenario", "Runs", "Valid", "NORMAL %", "HIGH %", "PERSIST %",
               "GROWTH %", "Warm-up", "Transition", "Issues")
    values = [[
        row["scenario"], str(row["sessions"]), str(row["valid_sessions"]),
        "{:.2f}".format(row["normal_pct"]), "{:.2f}".format(row["high_roll_pct"]),
        "{:.2f}".format(row["persistent_offset_pct"]),
        "{:.2f}".format(row["amplitude_growth_pct"]),
        str(row["warmup_windows"]), str(row["transition_windows"]), row["issues"],
    ] for row in rows]
    widths = [max(len(headers[i]), *(len(row[i]) for row in values)) for i in range(len(headers))]
    lines = [" | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))),
             "-+-".join("-" * width for width in widths)]
    lines.extend(" | ".join(value[i].ljust(widths[i]) for i in range(len(headers)))
                 for value in values)
    return "\n".join(lines)


def _high_roll_intervals(result: ScenarioResult) -> Iterable[Tuple[float, float]]:
    start: Optional[float] = None
    dt = float(result.metadata["dt_s"])
    for timestamp, label in zip(result.timestamps_s, result.labels):
        if label == "HIGH_ROLL" and start is None:
            start = timestamp
        elif label != "HIGH_ROLL" and start is not None:
            yield start, timestamp
            start = None
    if start is not None:
        yield start, result.timestamps_s[-1] + dt


def _plot_scenario(scenario: ScenarioCode, results: Sequence[ScenarioResult],
                   output_dir: str) -> Optional[str]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.lines import Line2D
        from matplotlib.patches import Patch
    except ImportError:
        return None

    figure, axes = plt.subplots(5, 1, figsize=(13, 14), sharex=True,
                                constrained_layout=True)
    for result_index, result in enumerate(results):
        # Thin only for display; all calculations above use every sample.
        stride = max(1, len(result.timestamps_s) // 5000)
        times = result.timestamps_s[::stride]
        color = "C{}".format(result_index % 10)
        alpha = 0.42 if len(results) > 1 else 0.9
        axes[0].plot(times, [math.degrees(v) for v in result.true_roll_rad[::stride]],
                     color=color, alpha=alpha, linewidth=0.8)
        axes[1].plot(times, [math.degrees(v) for v in result.true_roll_rate_rad_s[::stride]],
                     color=color, alpha=alpha, linewidth=0.8)
        axes[2].plot(times, [math.degrees(v) for v in result.wave_excitation_rad[::stride]],
                     color=color, alpha=alpha, linewidth=0.65)
        axes[2].plot(times, [math.degrees(v) for v in result.wave_sigma_rad[::stride]],
                     color=color, alpha=min(alpha + 0.2, 0.85), linestyle="--", linewidth=0.65)
        rms_times = result.timestamps_s[::stride]
        rms_values = [math.degrees(v) if v is not None else math.nan
                      for v in result.rolling_rms_roll_rad[::stride]]
        axes[3].plot(rms_times, rms_values, color=color, alpha=alpha, linewidth=0.8)
        label_values = [LABEL_NAME_TO_Y.get(value, math.nan) if value is not None else math.nan
                        for value in result.labels[::stride]]
        axes[4].step(times, label_values, where="post", color=color,
                     alpha=alpha, linewidth=0.8)

        event = _event(result)
        t0 = event.get("t0_s")
        if t0 is not None:
            for axis in axes:
                axis.axvline(t0, color="black", linestyle=":", linewidth=0.9, alpha=0.65)
                axis.axvspan(t0, min(t0 + 90.0, result.timestamps_s[-1]),
                             color="gold", alpha=0.035)
                if scenario is ScenarioCode.S2:
                    axis.axvline(t0 + 120.0, color="purple", linestyle="--",
                                 linewidth=0.8, alpha=0.6)
            for start, end in _high_roll_intervals(result):
                for axis in axes:
                    axis.axvspan(start, end, color="red", alpha=0.035)

    axes[0].set_ylabel("Roll (deg)")
    axes[1].set_ylabel("Roll rate (deg/s)")
    axes[2].set_ylabel("w(t), σw (deg equiv.)")
    axes[3].set_ylabel("60 s RMS (deg)")
    axes[4].set_ylabel("Label")
    axes[4].set_yticks(list(LABEL_NAME_TO_Y.values()), LABEL_ORDER)
    axes[4].set_xlabel("Time (s)")
    axes[2].legend(("w(t)", "σw profile"), loc="upper right")
    event_handles = [
        Line2D([0], [0], color="black", linestyle=":", label="t0"),
        Patch(facecolor="gold", alpha=0.2, label="90 s transition"),
        Patch(facecolor="red", alpha=0.2, label="HIGH_ROLL interval"),
    ]
    if scenario is ScenarioCode.S2:
        event_handles.append(Line2D([0], [0], color="purple", linestyle="--",
                                     label="PERSISTENT_OFFSET eligible (t0 + 120 s)"))
    figure.legend(handles=event_handles, loc="upper right", bbox_to_anchor=(0.99, 0.985),
                  ncol=2, fontsize="small")
    figure.suptitle("{} validation ({} seeded sessions)".format(scenario.value, len(results)))
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "scenario_{}.png".format(scenario.value))
    figure.savefig(path, dpi=130)
    plt.close(figure)
    return path


def _print_s2(analyses: Sequence[Mapping[str, Any]]) -> None:
    print("\nS2 diagnostics (roll degrees; label shares exclude warm-up):")
    print("seed | mean | RMS@0 | RMS demeaned | P95 | heel s | HIGH % | PERSIST % | cause")
    for item in analyses:
        print("{seed} | {mean_roll_deg:.2f} | {rms_about_zero_deg:.2f} | "
              "{rms_demeaned_deg:.2f} | {p95_abs_roll_deg:.2f} | "
              "{heel_duration_s:.1f} | {high_roll_window_pct:.1f} | "
              "{persistent_offset_window_pct:.1f} | {predominant_high_roll_cause}".format(**item))
        if item["high_roll_cause_windows"]:
            print("  triggering-window causes:", item["high_roll_cause_windows"])


def _print_s3(analyses: Sequence[Mapping[str, Any]]) -> None:
    increased = sum(item["increased_from_first_to_last_post_window"] is True
                    for item in analyses)
    print("\nS3 diagnostics (label rule and measured growth are separate):")
    print("seed | t0 | h | Omega rad/s | RMS pre | RMS first post | RMS last | grew? | label growth windows | note")
    for item in analyses:
        print("{seed} | {t0_s:.2f} | {h:.3f} | {Omega_rad_s:.4f} | "
              "{rms_pre_60s_deg:.3f} | {rms_first_post_60s_deg:.3f} | "
              "{rms_last_post_60s_deg:.3f} | {increased_from_first_to_last_post_window} | "
              "{label_amplitude_growth_windows} | {possible_non_growth_reason}".format(**item))
    print("Observed RMS increase: {}/{} sessions ({:.1f}%).".format(
        increased, len(analyses), 100.0 * increased / len(analyses) if analyses else 0.0))
    print("AMPLITUDE_GROWTH labels are assigned by parametric-excitation-active "
          "priority after HIGH_ROLL; they do not establish measured growth.")


def run_validation(*, sessions_per_scenario: int = 10, seed: int = 1000,
                   sea_state_sigma_deg: Optional[Mapping[str, float]] = None,
                   output_dir: Optional[str] = None, make_plots: bool = True
                   ) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]], List[str]]:
    """Run reproducible diagnostic sessions and return summaries, details, plots."""
    if isinstance(sessions_per_scenario, bool) or sessions_per_scenario < 1:
        raise ValueError("sessions_per_scenario must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 0xFFFFFFFF:
        raise ValueError("seed must be in [1, 2**32 - 1]")
    profile = dict(ANALYSIS_FIXTURE_PROFILE_DEG if sea_state_sigma_deg is None
                   else sea_state_sigma_deg)
    runner = ScenarioRunner(SimulationConfig(), sea_state_sigma_deg=profile)
    if output_dir is None:
        output_dir = os.path.join(tempfile.gettempdir(), "svmg_scenario_validation")

    all_results: Dict[ScenarioCode, List[ScenarioResult]] = {}
    all_analyses: Dict[str, List[Dict[str, Any]]] = {}
    summary_rows: List[Dict[str, Any]] = []
    plot_paths: List[str] = []
    for scenario_index, scenario in enumerate(ScenarioCode):
        results: List[ScenarioResult] = []
        analyses: List[Dict[str, Any]] = []
        for session_index in range(sessions_per_scenario):
            run_seed = seed + scenario_index * sessions_per_scenario + session_index
            if run_seed > 0xFFFFFFFF:
                run_seed = ((run_seed - 1) % 0xFFFFFFFF) + 1
            result = runner.generate(scenario, seed=run_seed,
                                     dataset_split=DatasetSplit.TRAIN)
            analysis = _analyze_run(result)
            analysis["seed"] = run_seed
            results.append(result)
            analyses.append(analysis)
        all_results[scenario] = results
        all_analyses[scenario.value] = analyses
        summary_rows.append(_aggregate(scenario, results, analyses))
        if make_plots:
            path = _plot_scenario(scenario, results, output_dir)
            if path is not None:
                plot_paths.append(path)
    if ScenarioCode.S2 in all_results:
        _print_s2(all_analyses[ScenarioCode.S2.value])
    _print_s3(all_analyses[ScenarioCode.S3.value])
    return summary_rows, all_analyses, plot_paths


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, default=10,
                        help="diagnostic sessions per scenario (recommended: 10-20)")
    parser.add_argument("--seed", type=int, default=1000,
                        help="first nonzero xorshift32 seed")
    parser.add_argument("--sea-state-profile", metavar="JSON", default=None,
                        help="SS0-SS5 sigma_w values in degrees as a JSON object; "
                             "default is a unit-test fixture, not official calibration")
    parser.add_argument("--output-dir", default=None,
                        help="PNG destination (default: system temp directory)")
    parser.add_argument("--no-plots", action="store_true",
                        help="run standard-library statistics only")
    args = parser.parse_args(argv)
    if args.sessions < 1 or args.seed < 1 or args.seed > 0xFFFFFFFF:
        parser.error("sessions must be positive and seed must be a nonzero uint32")
    try:
        profile, is_fixture = parse_sea_state_profile(args.sea_state_profile)
        summaries, _, plot_paths = run_validation(
            sessions_per_scenario=args.sessions,
            seed=args.seed,
            sea_state_sigma_deg=profile,
            output_dir=args.output_dir,
            make_plots=not args.no_plots,
        )
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))

    print("SVMG scenario validation (diagnostic only; no training dataset written)")
    print("profile source: {}".format(
        "unit-test analysis fixture (not official)" if is_fixture else "user supplied"))
    print("sea_state_sigma_deg:", json.dumps(profile, sort_keys=True))
    print("sessions/scenario: {}; base seed: {}".format(args.sessions, args.seed))
    print("label percentages use classified windows only; warm-up (None) is excluded.")
    print("transition count is an overlapping indicator, not a label class.")
    print("\nAggregate summary:\n" + _format_table(summaries))
    if plot_paths:
        print("\nPlots:")
        for path in plot_paths:
            print("  " + path)
    elif not args.no_plots:
        print("\nmatplotlib unavailable; plots skipped. Statistics completed with Python standard library.")
    print("\nS2 interpretation: label HIGH_ROLL uses 60-second RMS around zero. "
          "A means centered oscillation alone reaches 6 deg; B means static mean alone "
          "reaches 6 deg; C means both contribute or only combined RMS crosses 6 deg.")
    print("No label rule or generator parameter was modified by this tool.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
