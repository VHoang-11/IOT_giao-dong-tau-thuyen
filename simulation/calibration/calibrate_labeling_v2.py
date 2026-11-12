"""Calibrate candidate labeling_v2 thresholds on reproducible G1 pilot runs.

The tool writes a compressed, non-official pilot trace plus a calibration
report and candidate JSON. Scenario/event metadata is used only to stratify
validation diagnostics; the online labeler receives roll samples only.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import statistics
import sys
from dataclasses import dataclass, replace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from simulation.generator.config import (
    DatasetSplit,
    GrowthCriterion,
    LabelingVersion,
    MotionLabelConfig,
    ProfileCalibrationStatus,
    ScenarioCode,
    SimulationConfig,
    WaveGenerator,
)
from simulation.generator.scenarios import CausalMotionLabelerV2, ScenarioResult, ScenarioRunner


SCENARIO_ORDER = tuple(ScenarioCode)
DEFAULT_TRAIN_PER_SCENARIO = 10
DEFAULT_VALIDATION_PER_SCENARIO = 5
_ANALYSIS_STRIDE = 10  # match the 2 Hz analysis output from 20 Hz simulation
_HIGH_PERCENTILES = (0.95, 0.98, 0.99)
_GROWTH_CONFIRMATION_GRID_S = (10.0, 30.0, 60.0)  # exploratory candidates only


@dataclass(frozen=True)
class PilotPlanEntry:
    session_id: str
    scenario: ScenarioCode
    split: DatasetSplit
    seed: int


@dataclass(frozen=True)
class PilotTrace:
    plan: PilotPlanEntry
    dt_s: float
    duration_s: float
    true_roll_rad: Tuple[float, ...]
    event: Mapping[str, Any]
    sampled_parameters: Mapping[str, Any]
    outcome_checks: Mapping[str, Any]
    generator_version: str
    config_version: str


def build_pilot_plan(
    seed: int,
    *,
    train_per_scenario: int = DEFAULT_TRAIN_PER_SCENARIO,
    validation_per_scenario: int = DEFAULT_VALIDATION_PER_SCENARIO,
) -> Tuple[PilotPlanEntry, ...]:
    """Create a deterministic, unique Train/Validation-only session plan."""
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 0xFFFFFFFF:
        raise ValueError("seed must be a nonzero uint32")
    for name, count in (("train_per_scenario", train_per_scenario),
                        ("validation_per_scenario", validation_per_scenario)):
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError("{} must be a positive integer".format(name))

    plan: List[PilotPlanEntry] = []
    ordinal = 0
    seed_span = 0xFFFFFFFF
    for scenario in SCENARIO_ORDER:
        for split, count in ((DatasetSplit.TRAIN, train_per_scenario),
                             (DatasetSplit.VALIDATION, validation_per_scenario)):
            for split_index in range(count):
                run_seed = ((seed - 1 + ordinal) % seed_span) + 1
                session_id = "pilot-{}-{}-{:03d}-{:08x}".format(
                    split.value.lower().replace("-", ""),
                    scenario.value.lower(), split_index, run_seed)
                plan.append(PilotPlanEntry(session_id, scenario, split, run_seed))
                ordinal += 1
    if len({entry.session_id for entry in plan}) != len(plan):
        raise AssertionError("pilot session IDs must be unique")
    if len({entry.seed for entry in plan}) != len(plan):
        raise AssertionError("pilot seeds must be unique")
    return tuple(plan)


def _generate_pilot(config: SimulationConfig,
                    plan: Sequence[PilotPlanEntry]) -> List[PilotTrace]:
    if config.waves.generator is not WaveGenerator.G1:
        raise ValueError("threshold calibration pilot must use G1")
    runner = ScenarioRunner(config)
    traces: List[PilotTrace] = []
    for entry in plan:
        result = runner.generate(
            entry.scenario,
            seed=entry.seed,
            dataset_split=entry.split,
            labeling_version=LabelingVersion.V1,
        )
        traces.append(PilotTrace(
            plan=entry,
            dt_s=config.time.dt_s,
            duration_s=config.time.duration_s,
            true_roll_rad=result.true_roll_rad,
            event=dict(result.events[0]) if result.events else {},
            sampled_parameters=dict(result.metadata["sampled_parameters"]),
            outcome_checks=dict(result.metadata["outcome_checks"]),
            generator_version=config.generator_version,
            config_version=config.config_version,
        ))
        del result
    return traces


def _event(trace: PilotTrace) -> Mapping[str, Any]:
    return trace.event


def _percentile(values: Sequence[float], percentile: float) -> Optional[float]:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    position = (len(clean) - 1) * percentile
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    fraction = position - lower
    return clean[lower] * (1.0 - fraction) + clean[upper] * fraction


def _quantile_candidate(values: Sequence[float], percentile: float,
                        *, minimum: float = 0.0) -> Optional[float]:
    candidate = _percentile([value for value in values if value >= minimum], percentile)
    if candidate is None:
        return None
    return max(minimum, candidate)


def _baseline_metrics(trace: PilotTrace, base: SimulationConfig
                      ) -> List[Dict[str, Optional[float]]]:
    """Compute causal v2 metrics once; no scenario/source fields enter labeler."""
    metric_config = MotionLabelConfig(
        high_roll_centered_threshold_deg=1.0e9,
        persistent_offset_threshold_deg=base.labeling.persistent_offset_threshold_deg,
        persistent_offset_window_s=base.labeling.persistent_offset_window_s,
        persistent_offset_duration_s=base.labeling.persistent_offset_duration_s,
        growth_window_s=base.labeling.growth_window_s,
        growth_ratio_lag_s=base.labeling.growth_ratio_lag_s,
        growth_criterion=GrowthCriterion.SLOPE,
        growth_slope_threshold_deg_per_min=1.0e9,
        growth_confirmation_s=1.0e9,
        threshold_calibration_status=ProfileCalibrationStatus.CANDIDATE,
    )
    metric_config_sim = replace(base, labeling=metric_config)
    labeler = CausalMotionLabelerV2(metric_config_sim)
    stride = _ANALYSIS_STRIDE
    metrics = []
    for index, phi in enumerate(trace.true_roll_rad):
        step = labeler.step(index * trace.dt_s, phi)
        if index % stride:
            continue
        item = step.metrics
        metrics.append({
            "time_s": index * trace.dt_s,
            "centered_rms_deg": (None if item.rms_centered_60_rad is None else
                                 math.degrees(item.rms_centered_60_rad)),
            "mean_180_deg": (None if item.mean_roll_180_rad is None else
                             math.degrees(item.mean_roll_180_rad)),
            "slope_deg_per_min": item.rms_trend_slope_deg_per_min,
            "growth_ratio": item.growth_ratio_180,
        })
    return metrics


def _exposure_window(trace: PilotTrace, timestamp_s: float) -> bool:
    """Use event metadata only to define a diagnostic exposure stratum."""
    event = _event(trace)
    t0 = event.get("t0_s")
    if t0 is None:
        return False
    end = event.get("end_s", trace.duration_s)
    return float(t0) + 90.0 <= timestamp_s <= float(end)


def _collect_metric_rows(traces: Sequence[PilotTrace], base: SimulationConfig
                         ) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for trace in traces:
        event = _event(trace)
        for metric in _baseline_metrics(trace, base):
            rows.append({
                **metric,
                "session_id": trace.plan.session_id,
                "scenario": trace.plan.scenario.value,
                "split": trace.plan.split.value,
                "exposure_window": _exposure_window(trace, float(metric["time_s"])),
                "event_t0_s": event.get("t0_s"),
                "event_end_s": event.get("end_s"),
            })
    return rows


def _high_candidates(train_rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    quiet = [float(row["centered_rms_deg"]) for row in train_rows
             if row["scenario"] in (ScenarioCode.S0.value, ScenarioCode.S0B.value)
             and row["centered_rms_deg"] is not None]
    stress = [float(row["centered_rms_deg"]) for row in train_rows
              if row["scenario"] in (ScenarioCode.S1.value, ScenarioCode.H1.value)
              and row["exposure_window"] and row["centered_rms_deg"] is not None]
    candidates = []
    quantile_values = {}
    for percentile in _HIGH_PERCENTILES:
        value = _percentile(quiet, percentile)
        if value is not None:
            quantile_values["quiet_p{:g}".format(percentile * 100)] = value
            candidates.append(value)
    quiet_p99 = _percentile(quiet, 0.99)
    stress_p10 = _percentile(stress, 0.10)
    gap_midpoint = None
    if quiet_p99 is not None and stress_p10 is not None and stress_p10 > quiet_p99:
        gap_midpoint = (quiet_p99 + stress_p10) / 2.0
        candidates.append(gap_midpoint)
    candidates = sorted({round(value, 8) for value in candidates if value > 0.0})
    return {
        "threshold_candidates_deg": candidates,
        "train_quiet_count": len(quiet),
        "train_stress_exposure_count": len(stress),
        "train_quiet_p99_deg": quiet_p99,
        "train_stress_p10_deg": stress_p10,
        "separation_gap_midpoint_deg": gap_midpoint,
        "train_quantiles_deg": quantile_values,
        "reference_definition": (
            "S0/S0b background and post-transition S1/H1 exposure strata; "
            "scenario/event metadata only defines diagnostic cohorts, not labels"),
    }


def _candidate_high_metrics(rows: Sequence[Mapping[str, Any]], threshold: float
                            ) -> Dict[str, Any]:
    quiet = [row for row in rows if row["scenario"] in
             (ScenarioCode.S0.value, ScenarioCode.S0B.value)
             and row["centered_rms_deg"] is not None]
    stress = [row for row in rows if row["scenario"] in
              (ScenarioCode.S1.value, ScenarioCode.H1.value)
              and row["exposure_window"] and row["centered_rms_deg"] is not None]
    false_rate = (sum(float(row["centered_rms_deg"]) >= threshold for row in quiet)
                  / len(quiet) if quiet else None)
    exposure_rate = (sum(float(row["centered_rms_deg"]) >= threshold for row in stress)
                     / len(stress) if stress else None)
    grouped: Dict[str, List[Mapping[str, Any]]] = {}
    for row in rows:
        if row["centered_rms_deg"] is not None:
            grouped.setdefault(str(row["session_id"]), []).append(row)
    quiet_sessions = [session for session in grouped.values()
                      if session[0]["scenario"] in (ScenarioCode.S0.value,
                                                     ScenarioCode.S0B.value)]
    exposure_sessions = [
        [row for row in session if row["exposure_window"]]
        for session in grouped.values()
        if session[0]["scenario"] in (ScenarioCode.S1.value, ScenarioCode.H1.value)
    ]
    exposure_sessions = [session for session in exposure_sessions if session]
    false_session_rate = (
        sum(any(float(row["centered_rms_deg"]) >= threshold for row in session)
            for session in quiet_sessions) / len(quiet_sessions)
        if quiet_sessions else None)
    detected_sessions = [session for session in exposure_sessions
                         if any(float(row["centered_rms_deg"]) >= threshold
                                for row in session)]
    exposure_session_rate = (len(detected_sessions) / len(exposure_sessions)
                              if exposure_sessions else None)
    balanced_score = (
        None if false_session_rate is None or exposure_session_rate is None else
        ((1.0 - false_session_rate) + exposure_session_rate) / 2.0)
    latencies = []
    for session in detected_sessions:
        t0 = session[0]["event_t0_s"]
        if t0 is None:
            continue
        first = next((row for row in session
                      if row["exposure_window"] and
                      float(row["centered_rms_deg"]) >= threshold), None)
        if first is not None:
            latencies.append(float(first["time_s"]) - float(t0))
    by_scenario = {}
    for scenario in SCENARIO_ORDER:
        subset = [row for row in rows if row["scenario"] == scenario.value
                  and row["centered_rms_deg"] is not None]
        by_scenario[scenario.value] = {
            "windows": len(subset),
            "fraction_centered_std_over_threshold": (
                sum(float(row["centered_rms_deg"]) >= threshold for row in subset)
                / len(subset) if subset else None),
            "sessions": len({row["session_id"] for row in subset}),
            "sessions_with_any_threshold_crossing": sum(
                any(float(row["centered_rms_deg"]) >= threshold for row in grouped[sid])
                for sid in {row["session_id"] for row in subset}),
        }
    return {
        "threshold_deg": threshold,
        "validation_background_false_rate_S0_S0b": false_rate,
        "validation_stress_exposure_detection_rate_S1_H1": exposure_rate,
        "validation_background_false_session_rate_S0_S0b": false_session_rate,
        "validation_stress_exposure_session_detection_rate_S1_H1": exposure_session_rate,
        "stress_exposure_median_detection_latency_s": (
            statistics.median(latencies) if latencies else None),
        "S2_sessions_with_high_roll_threshold_crossing":
            by_scenario[ScenarioCode.S2.value]["sessions_with_any_threshold_crossing"],
        "exposure_stratum_balanced_score": balanced_score,
        "by_scenario": by_scenario,
    }


def _growth_candidate_specs(train_rows: Sequence[Mapping[str, Any]],
                            high_threshold_deg: float
                            ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    controls = [row for row in train_rows if row["scenario"] in
                (ScenarioCode.S0.value, ScenarioCode.S0B.value)]
    s3 = [row for row in train_rows if row["scenario"] == ScenarioCode.S3.value
          and row["exposure_window"]]
    control_slopes = [float(row["slope_deg_per_min"]) for row in controls
                      if row["slope_deg_per_min"] is not None and
                      float(row["slope_deg_per_min"]) > 0.0]
    control_ratios = [float(row["growth_ratio"]) for row in controls
                      if row["growth_ratio"] is not None and
                      float(row["growth_ratio"]) > 1.0]
    s3_slopes = [float(row["slope_deg_per_min"]) for row in s3
                 if row["slope_deg_per_min"] is not None and
                 float(row["slope_deg_per_min"]) > 0.0]
    s3_ratios = [float(row["growth_ratio"]) for row in s3
                 if row["growth_ratio"] is not None and
                 float(row["growth_ratio"]) > 1.0]
    positive_rms = [float(row["centered_rms_deg"]) for row in train_rows
                    if row["centered_rms_deg"] is not None and
                    float(row["centered_rms_deg"]) > 0.0]
    slope_q95 = _percentile(control_slopes, 0.95)
    slope_q99 = _percentile(control_slopes, 0.99)
    ratio_q95 = _percentile(control_ratios, 0.95)
    ratio_q99 = _percentile(control_ratios, 0.99)
    floor = _percentile(positive_rms, 0.05)
    if floor is None or floor <= 0:
        floor = 1.0e-9
    # Threshold points are empirical control quantiles. Confirmation durations
    # are a small exploratory grid, not approved operational constants.
    specs: List[Dict[str, Any]] = []
    for criterion, slope, ratio in (
        (GrowthCriterion.SLOPE, slope_q95, None),
        (GrowthCriterion.SLOPE, slope_q99, None),
        (GrowthCriterion.RATIO, None, ratio_q95),
        (GrowthCriterion.RATIO, None, ratio_q99),
        (GrowthCriterion.SLOPE_AND_RATIO, slope_q95, ratio_q95),
        (GrowthCriterion.SLOPE_OR_RATIO, slope_q99, ratio_q99),
    ):
        if criterion in (GrowthCriterion.SLOPE, GrowthCriterion.SLOPE_AND_RATIO,
                         GrowthCriterion.SLOPE_OR_RATIO) and slope is None:
            continue
        if criterion in (GrowthCriterion.RATIO, GrowthCriterion.SLOPE_AND_RATIO,
                         GrowthCriterion.SLOPE_OR_RATIO) and ratio is None:
            continue
        for confirmation_s in _GROWTH_CONFIRMATION_GRID_S:
            specs.append({
                "growth_criterion": criterion,
                "growth_slope_threshold_deg_per_min": slope,
                "growth_ratio_threshold": ratio,
                "growth_ratio_floor_deg": floor,
                "growth_confirmation_s": confirmation_s,
                "high_roll_centered_threshold_deg": high_threshold_deg,
                "persistent_offset_threshold_deg": 3.0,
                "persistent_offset_window_s": 180.0,
                "persistent_offset_duration_s": 120.0,
                "growth_window_s": 180.0,
                "growth_ratio_lag_s": 120.0,
                "threshold_calibration_status": ProfileCalibrationStatus.CANDIDATE,
            })
    info = {
        "train_control_positive_slope_p95_deg_per_min": slope_q95,
        "train_control_positive_slope_p99_deg_per_min": slope_q99,
        "train_control_growth_ratio_p95": ratio_q95,
        "train_control_growth_ratio_p99": ratio_q99,
        "train_s3_post_transition_positive_slope_p50_deg_per_min":
            _percentile(s3_slopes, 0.50),
        "train_s3_post_transition_growth_ratio_p50": _percentile(s3_ratios, 0.50),
        "growth_ratio_floor_deg_p05_train_centered_rms": floor,
        "confirmation_grid_s": list(_GROWTH_CONFIRMATION_GRID_S),
    }
    return specs, info


def _apply_labeler(trace: PilotTrace, base: SimulationConfig,
                   labeling: MotionLabelConfig
                   ) -> Tuple[List[Optional[str]], List[Any]]:
    configured = replace(base, labeling=labeling)
    labeler = CausalMotionLabelerV2(configured)
    labels = []
    steps = []
    for index, phi in enumerate(trace.true_roll_rad):
        step = labeler.step(index * base.time.dt_s, phi)
        labels.append(step.label)
        steps.append(step)
    return labels, steps


def _session_growth_score(trace: PilotTrace, labels: Sequence[Optional[str]]) -> Dict[str, Any]:
    event = _event(trace)
    t0 = event.get("t0_s")
    growth_indices = [index for index, label in enumerate(labels)
                      if label == "AMPLITUDE_GROWTH"]
    pre_event_indices = ([index for index in growth_indices
                          if index * trace.dt_s < float(t0)] if t0 is not None else [])
    event_indices = ([index for index in growth_indices
                      if index * trace.dt_s >= float(t0)] if t0 is not None
                     else growth_indices)
    onset = None if not event_indices else event_indices[0] * trace.dt_s
    measured = trace.outcome_checks.get("amplitude_growth", {})
    return {
        "session_id": trace.plan.session_id,
        "scenario": trace.plan.scenario.value,
        "split": trace.plan.split.value,
        "observed_end_session_rms_increase_reference": measured.get("increased"),
        "growth_label_any": bool(event_indices),
        "pre_event_growth_windows": len(pre_event_indices),
        "first_growth_label_time_s": onset,
        "latency_from_t0_s": (None if onset is None or t0 is None else onset - float(t0)),
        "growth_windows": len(growth_indices),
    }


def _evaluate_growth_specs(
    specs: Sequence[Mapping[str, Any]],
    traces: Sequence[PilotTrace],
    base: SimulationConfig,
) -> List[Dict[str, Any]]:
    validation = [trace for trace in traces
                  if trace.plan.split is DatasetSplit.VALIDATION]
    results = []
    for candidate_index, spec in enumerate(specs):
        labeling = MotionLabelConfig(**dict(spec))
        session_scores = []
        for trace in validation:
            labels, _ = _apply_labeler(trace, base, labeling)
            session_scores.append(_session_growth_score(trace, labels))
        growth_positives = [item for item in session_scores
                            if item["scenario"] == ScenarioCode.S3.value and
                            item["observed_end_session_rms_increase_reference"] is True]
        controls = [item for item in session_scores if item["scenario"] in
                    (ScenarioCode.S0.value, ScenarioCode.S0B.value)]
        sensitivity = (sum(item["growth_label_any"] for item in growth_positives)
                       / len(growth_positives) if growth_positives else None)
        false_rate = (sum(item["growth_label_any"] for item in controls)
                      / len(controls) if controls else None)
        score = (None if sensitivity is None or false_rate is None else
                 (sensitivity + (1.0 - false_rate)) / 2.0)
        detected_latencies = [item["latency_from_t0_s"] for item in growth_positives
                              if item["latency_from_t0_s"] is not None]
        results.append({
            "candidate_id": "growth-{:02d}".format(candidate_index + 1),
            "thresholds": {
                key: (value.value if isinstance(value, GrowthCriterion) else value)
                for key, value in spec.items()
            },
            "validation_S3_measured_growth_sessions": len(growth_positives),
            "validation_S3_growth_detection_rate": sensitivity,
            "validation_S0_S0b_session_false_growth_rate": false_rate,
            "validation_exposure_stratum_balanced_score": score,
            "median_growth_detection_latency_s": (
                statistics.median(detected_latencies) if detected_latencies else None),
            "sessions": session_scores,
        })
    return results


def _choose_growth_candidate(results: Sequence[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    eligible = [item for item in results
                if item["validation_exposure_stratum_balanced_score"] is not None]
    if not eligible:
        return None
    # Deterministic tie break favors lower control false rate, then shorter
    # latency. This is a pilot ranking rule, not an approved operating target.
    return max(eligible, key=lambda item: (
        float(item["validation_exposure_stratum_balanced_score"]),
        -float(item["validation_S0_S0b_session_false_growth_rate"]),
        -float(item["median_growth_detection_latency_s"] or float("inf")),
    ))


def _evaluate_recommended_labels(
    traces: Sequence[PilotTrace], base: SimulationConfig,
    candidate: MotionLabelConfig,
) -> Dict[str, Any]:
    validation = [trace for trace in traces
                  if trace.plan.split is DatasetSplit.VALIDATION]
    per_scenario: Dict[str, Any] = {}
    all_latency: Dict[str, List[float]] = {"high_roll": [], "persistent_offset": [],
                                           "amplitude_growth": []}
    overlap_sessions = []
    all_labels = []
    v2_signal_stats = []
    for scenario in SCENARIO_ORDER:
        subset = [trace for trace in validation if trace.plan.scenario is scenario]
        class_counts = {label: 0 for label in
                        ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH")}
        classified_windows = 0
        phenotype_counts = {"high_roll": 0, "persistent_offset": 0,
                            "observed_amplitude_growth": 0}
        phenotype_overlap_windows = 0
        session_summary = []
        for trace in subset:
            labels, steps = _apply_labeler(trace, base, candidate)
            valid_labels = [label for label in labels if label is not None]
            classified_windows += len(valid_labels)
            for label in valid_labels:
                class_counts[label] += 1
            for step in steps:
                flags = step.flags
                phenotype_counts["high_roll"] += bool(flags.high_roll_active)
                phenotype_counts["persistent_offset"] += bool(flags.persistent_offset_active)
                phenotype_counts["observed_amplitude_growth"] += bool(
                    flags.observed_amplitude_growth)
                active = sum(value is True for value in (
                    flags.high_roll_active, flags.persistent_offset_active,
                    flags.observed_amplitude_growth))
                phenotype_overlap_windows += active > 1
            event = _event(trace)
            t0 = event.get("t0_s")
            firsts = {}
            for phenotype, flag_name in (
                ("high_roll", "high_roll_active"),
                ("persistent_offset", "persistent_offset_active"),
                ("amplitude_growth", "observed_amplitude_growth"),
            ):
                index = next((idx for idx, step in enumerate(steps)
                              if getattr(step.flags, flag_name) is True), None)
                first_time = None if index is None else index * trace.dt_s
                firsts[phenotype] = first_time
                if first_time is not None and t0 is not None:
                    all_latency[phenotype].append(first_time - float(t0))
            if sum(v is not None for v in firsts.values()) > 1:
                overlap_sessions.append(trace.plan.session_id)
            session_summary.append({
                "session_id": trace.plan.session_id,
                "seed": trace.plan.seed,
                "valid": all(math.isfinite(value) for value in trace.true_roll_rad),
                "classified_windows": len(valid_labels),
                "warmup_windows": len(labels) - len(valid_labels),
                "transition_windows": (
                    max(0, min(len(labels), int(math.ceil(
                        max(0.0, float(t0) + 90.0 - float(t0)) / trace.dt_s))))
                    if t0 is not None else 0),
                "class_counts": {label: valid_labels.count(label) for label in class_counts},
                "first_phenotype_time_s": firsts,
                "event_t0_s_for_evaluation_only": t0,
                "event": dict(event),
                "observed_rms_increase_reference": trace.outcome_checks.get(
                    "amplitude_growth", {}).get("increased"),
                "signal_summary": _trace_signal_summary(trace),
            })
            v2_signal_stats.append(session_summary[-1]["signal_summary"] | {
                "scenario": scenario.value,
            })
            all_labels.extend(valid_labels)
        per_scenario[scenario.value] = {
            "sessions": len(subset),
            "valid_sessions": sum(item["valid"] for item in session_summary),
            "classified_windows": classified_windows,
            "class_counts": class_counts,
            "class_pct_excluding_warmup": {
                key: 100.0 * value / classified_windows if classified_windows else 0.0
                for key, value in class_counts.items()
            },
            "phenotype_true_windows": phenotype_counts,
            "phenotype_overlap_windows": phenotype_overlap_windows,
            "session_details": session_summary,
        }
    total = len(all_labels)
    return {
        "validation_label_windows": total,
        "validation_label_distribution": {
            label: {
                "count": all_labels.count(label),
                "pct": 100.0 * all_labels.count(label) / total if total else 0.0,
            }
            for label in ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH")
        },
        "per_scenario": per_scenario,
        "signal_summary_by_scenario": _signal_summary_by_scenario(v2_signal_stats),
        "phenotype_overlap_session_ids": overlap_sessions,
        "median_event_relative_detection_latency_s": {
            key: statistics.median(values) if values else None
            for key, values in all_latency.items()
        },
        "latency_is_evaluation_only": True,
        "event_metadata_used_for_label_generation": False,
    }


def _trace_signal_summary(trace: PilotTrace) -> Dict[str, Optional[float]]:
    values = trace.true_roll_rad
    mean = statistics.fmean(values) if values else 0.0
    rms_zero = math.sqrt(math.fsum(value * value for value in values) / len(values)) if values else 0.0
    centered_rms = statistics.pstdev(values) if values else 0.0
    p95_abs = _percentile([abs(value) for value in values], 0.95)
    return {
        "mean_roll_deg": math.degrees(mean),
        "rms_about_zero_deg": math.degrees(rms_zero),
        "session_centered_rms_deg": math.degrees(centered_rms),
        "p95_abs_roll_deg": None if p95_abs is None else math.degrees(p95_abs),
    }


def _signal_summary_by_scenario(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    output = {}
    for scenario in SCENARIO_ORDER:
        subset = [row for row in rows if row["scenario"] == scenario.value]
        output[scenario.value] = {
            metric: {
                "median": _percentile([float(row[metric]) for row in subset
                                       if row[metric] is not None], 0.50),
                "p95": _percentile([float(row[metric]) for row in subset
                                    if row[metric] is not None], 0.95),
            }
            for metric in ("mean_roll_deg", "rms_about_zero_deg",
                           "session_centered_rms_deg", "p95_abs_roll_deg")
        }
    return output


def _write_pilot_gzip(path: str, traces: Sequence[PilotTrace], dt_s: float) -> None:
    """Persist truth and forcing provenance for pilot audit/replay, not ML input."""
    with gzip.open(path, "wt", encoding="utf-8") as output:
        for trace in traces:
            record = {
                "session_id": trace.plan.session_id,
                "scenario_id": trace.plan.scenario.value,
                "split": trace.plan.split.value,
                "seed": trace.plan.seed,
                "generator_version": trace.generator_version,
                "config_version": trace.config_version,
                "dt_s": dt_s,
                "sample_count": len(trace.true_roll_rad),
                "true_roll_rad": list(trace.true_roll_rad),
                "events_audit_only": [dict(trace.event)] if trace.event else [],
                "sampled_parameters": dict(trace.sampled_parameters),
                "signal_source": "clean simulator roll; calibration labels consume roll only",
            }
            output.write(json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n")


def _format_pct(value: Optional[float]) -> str:
    return "n/a" if value is None else "{:.1f}%".format(value * 100.0)


def _render_report(payload: Mapping[str, Any]) -> str:
    high = payload["high_roll_calibration"]
    growth = payload["growth_calibration"]
    chosen_growth = growth["recommended_candidate"]
    validation = payload["validation_recommended_candidate"]
    lines = [
        "# Labeling v2 Pilot Threshold Calibration",
        "",
        "**Status:** candidate only; not approved/calibrated for the official 605-session dataset.",
        "**Data:** deterministic G1 pilot; synthetic simulation only, not vessel evidence.",
        "",
        "## Pilot plan",
        "",
        "- Sessions: {}/{} Train / Validation.".format(
            payload["pilot"]["train_sessions"], payload["pilot"]["validation_sessions"]),
        "- Seed base: `{}`; unique session seeds and IDs are in the candidate JSON and compressed pilot file.".format(
            payload["pilot"]["base_seed"]),
        "- Scenarios: S0, S0b, S1, S2, S3, H1; no Test-G1/Test-G2 sessions.",
        "- Sea-state profile: `{}` (candidate; sigma_w is equivalent-angle forcing, not wave height).".format(
            payload["sea_state_profile"]["profile_id"]),
        "- Generator: `{}`; sample rate {} Hz, dt {} s.".format(
            payload["generator_version"], payload["simulation"]["sample_rate_hz"],
            payload["simulation"]["dt_s"]),
        "- Pilot trace is audit data (clean roll truth and generator metadata), not an ML feature dataset.",
        "",
        "## Metrics surveyed",
        "",
        "Roll-zero RMS, centered 60 s population std, signed 180 s mean, P95(abs roll),",
        "60 s RMS trend slope, 180 s growth ratio, v2 class/phenotype shares, overlap, warm-up,",
        "and event-relative detection latency were evaluated. Centered/std and slope/ratio windows",
        "are highly correlated; windows are diagnostic, while candidate scores use session grouping.",
        "",
        "## HIGH_ROLL threshold candidates",
        "",
        "Candidate centered thresholds (degrees): `{}`.".format(
            high["threshold_candidates_deg"]),
        "Train S0/S0b q99: `{}`°; Train post-transition S1/H1 q10: `{}`°.".format(
            _fmt(high["train_quiet_p99_deg"]), _fmt(high["train_stress_p10_deg"])),
        "Recommended pilot candidate: **{:.4f}°** centered std over 60 s.".format(
            high["recommended_threshold_deg"]),
        "Train thresholds include empirical background quantiles and a distribution-gap midpoint when available.",
        "Validation ranks these candidates by session-level background/stress-exposure discrimination.",
        "Scenario/event metadata defines those diagnostic exposure strata only; it is not a motion label.",
        "Validation background false-session rate: {}; S1/H1 exposure session detection: {}.".format(
            _format_pct(high["recommended_validation"]["validation_background_false_session_rate_S0_S0b"]),
            _format_pct(high["recommended_validation"]["validation_stress_exposure_session_detection_rate_S1_H1"])),
        "Median detection latency among exposed sessions: {} s; S2 sessions with any crossing: {}.".format(
            _fmt(high["recommended_validation"]["stress_exposure_median_detection_latency_s"]),
            high["recommended_validation"]["S2_sessions_with_high_roll_threshold_crossing"]),
        "",
        "## PERSISTENT_OFFSET validation",
        "",
        "The approved 3° signed-mean threshold, 180 s trailing mean window and 120 s continuous duration",
        "were evaluated unchanged. Label decisions use only roll samples; heel truth and event t0 appear only",
        "in the evaluation details. S2 qualifying sessions: {}/{}; S0b sessions with any persistent phenotype: {}/{}; "
        "median S2 detection latency: {} s. These are pilot counts, not stable rate estimates.".format(
            payload["persistent_offset_validation"]["s2_detected_sessions"],
            payload["persistent_offset_validation"]["s2_sessions"],
            payload["persistent_offset_validation"]["s0b_false_sessions"],
            payload["persistent_offset_validation"]["s0b_sessions"],
            _fmt(payload["persistent_offset_validation"]["s2_median_latency_s"])),
        "",
        "## AMPLITUDE_GROWTH candidates",
        "",
        "The Train-derived candidate set covers slope, ratio, AND/OR combinations and confirmation durations",
        "of 10/30/60 s. These confirmation values are exploratory grid points, not approved constants.",
        "The selection reference is an independent end-session measured RMS increase check; that reference is",
        "used only to score sessions, never to label earlier timestamps. `h`, sea-state ID and scenario do not",
        "enter the online labeler. Recommended candidate: `{}`.".format(
            "none" if chosen_growth is None else chosen_growth["candidate_id"]),
        "Validation S3 measured-growth detection: {}; S0/S0b session false-growth rate: {}; median detection latency: {} s.".format(
            "n/a" if chosen_growth is None else _format_pct(
                chosen_growth["validation_S3_growth_detection_rate"]),
            "n/a" if chosen_growth is None else _format_pct(
                chosen_growth["validation_S0_S0b_session_false_growth_rate"]),
            "n/a" if chosen_growth is None else _fmt(
                chosen_growth["median_growth_detection_latency_s"])),
        "",
        "## Recommended candidate configuration",
        "",
        "```json",
        json.dumps(payload["recommended_thresholds"], indent=2, sort_keys=True),
        "```",
        "",
        "Validation class distribution (warm-up excluded):",
        "",
        "| Class | Windows | Percent |",
        "|---|---:|---:|",
    ]
    for label, item in validation["validation_label_distribution"].items():
        lines.append("| {} | {} | {:.2f}% |".format(label, item["count"], item["pct"]))
    lines.extend([
        "",
        "Validation signal summary by scenario (session-level medians; degrees):",
        "",
        "| Scenario | Mean roll | RMS about 0 | Centered RMS | P95 abs roll |",
        "|---|---:|---:|---:|---:|",
    ])
    for scenario, summary in validation.get("signal_summary_by_scenario", {}).items():
        lines.append("| {} | {:.3f} | {:.3f} | {:.3f} | {:.3f} |".format(
            scenario,
            summary["mean_roll_deg"]["median"],
            summary["rms_about_zero_deg"]["median"],
            summary["session_centered_rms_deg"]["median"],
            summary["p95_abs_roll_deg"]["median"],
        ))
    lines.extend([
        "",
        "Validation per-scenario label outcome and offset/growth diagnostics are retained in the candidate JSON.",
        "S3 observed end-session RMS-increase reference: {}/{} validation sessions.".format(
            0 if chosen_growth is None else
            chosen_growth["validation_S3_measured_growth_sessions"],
            sum(1 for item in validation.get("per_scenario", {}).get("S3", {}).get(
                "session_details", []))),
    ])
    lines.extend([
        "",
        "Validation median event-relative latency (evaluation only): `{}`.".format(
            json.dumps(validation["median_event_relative_detection_latency_s"], sort_keys=True)),
        "",
        "## Interpretation and limitations",
        "",
        "- The 60 sessions form the Train pilot used to derive threshold candidates; 30 Validation sessions rank candidates.",
        "- Five Validation sessions per scenario are too few for stable rate estimates; a follow-up pilot of at least 30 Train and 20 Validation sessions per scenario is recommended before approval.",
        "- Pilot windows overlap in time and are not independent observations. Rates are descriptive; no confidence claim is made from window counts.",
        "- Scenario types represent excitation/offset exposure, not guaranteed observed labels. Failed or unexpected outcomes remain in the report.",
        "- S2 may also show high centered oscillation; phenotype flags preserve overlap while the primary label follows approved priority.",
        "- S3 excitation activation is metadata only. Observed growth is evaluated separately and may not occur.",
        "- No Test-G1/Test-G2, official 605-session dataset, hardware measurement or vessel data were used.",
        "- Candidate requires review of the false detection, latency and per-scenario outcomes before status can change to calibrated.",
        "",
        "See `labeling_v2_candidate.json` for all thresholds, session IDs/seeds, candidate scores and per-session diagnostics.",
        "",
    ])
    return "\n".join(lines)


def _fmt(value: Optional[float]) -> str:
    return "n/a" if value is None else "{:.4f}".format(value)


def run_calibration(*, seed: int, output_dir: str,
                    train_per_scenario: int = DEFAULT_TRAIN_PER_SCENARIO,
                    validation_per_scenario: int = DEFAULT_VALIDATION_PER_SCENARIO
                    ) -> Dict[str, Any]:
    """Generate the pilot, rank candidate thresholds, and write artifacts."""
    os.makedirs(output_dir, exist_ok=True)
    base = SimulationConfig()
    if base.waves.generator is not WaveGenerator.G1:
        raise ValueError("pilot calibration must use G1")
    plan = build_pilot_plan(
        seed, train_per_scenario=train_per_scenario,
        validation_per_scenario=validation_per_scenario)
    traces = _generate_pilot(base, plan)
    train_traces = [trace for trace in traces if trace.plan.split is DatasetSplit.TRAIN]
    validation_traces = [trace for trace in traces
                         if trace.plan.split is DatasetSplit.VALIDATION]
    train_rows = _collect_metric_rows(train_traces, base)
    validation_rows = _collect_metric_rows(validation_traces, base)

    high_survey = _high_candidates(train_rows)
    if not high_survey["threshold_candidates_deg"]:
        raise RuntimeError("pilot did not produce finite HIGH_ROLL threshold candidates")
    high_validation = [_candidate_high_metrics(validation_rows, value)
                       for value in high_survey["threshold_candidates_deg"]]
    high_recommended = max(high_validation, key=lambda item: (
        -1.0 if item["exposure_stratum_balanced_score"] is None else
        item["exposure_stratum_balanced_score"],
        -1.0 if item["validation_background_false_rate_S0_S0b"] is None else
        -item["validation_background_false_rate_S0_S0b"],
        item["threshold_deg"],
    ))
    high_survey["validation_candidates"] = high_validation
    high_survey["recommended_threshold_deg"] = high_recommended["threshold_deg"]
    high_survey["recommended_validation"] = high_recommended

    growth_specs, growth_train_info = _growth_candidate_specs(
        train_rows, high_survey["recommended_threshold_deg"])
    growth_validation = _evaluate_growth_specs(growth_specs, traces, base)
    growth_recommended = _choose_growth_candidate(growth_validation)

    recommended_thresholds: Dict[str, Any] = {
        "labeling_version": "v2",
        "calibration_status": "candidate",
        "high_roll_centered_threshold_deg": high_survey["recommended_threshold_deg"],
        "persistent_offset_threshold_deg": 3.0,
        "persistent_offset_window_s": 180.0,
        "persistent_offset_duration_s": 120.0,
    }
    if growth_recommended is not None:
        selected_growth_thresholds = dict(growth_recommended["thresholds"])
        selected_criterion = GrowthCriterion(selected_growth_thresholds["growth_criterion"])
        if selected_criterion not in (GrowthCriterion.SLOPE_AND_RATIO,
                                      GrowthCriterion.SLOPE_OR_RATIO,
                                      GrowthCriterion.RATIO):
            selected_growth_thresholds["growth_ratio_threshold"] = None
            selected_growth_thresholds["growth_ratio_floor_deg"] = None
        if selected_criterion not in (GrowthCriterion.SLOPE_AND_RATIO,
                                      GrowthCriterion.SLOPE_OR_RATIO,
                                      GrowthCriterion.SLOPE):
            selected_growth_thresholds["growth_slope_threshold_deg_per_min"] = None
        recommended_thresholds.update(selected_growth_thresholds)
    else:
        recommended_thresholds.update({
            "growth_criterion": None,
            "growth_slope_threshold_deg_per_min": None,
            "growth_ratio_threshold": None,
            "growth_ratio_floor_deg": None,
            "growth_confirmation_s": None,
            "growth_window_s": 180.0,
            "growth_ratio_lag_s": 120.0,
        })

    candidate_config = dict(recommended_thresholds)
    candidate_config.pop("labeling_version", None)
    candidate_config.pop("calibration_status", None)
    if candidate_config.get("growth_criterion") is not None:
        candidate_config["growth_criterion"] = GrowthCriterion(
            candidate_config["growth_criterion"])
        candidate_config["threshold_calibration_status"] = ProfileCalibrationStatus.CANDIDATE
        candidate_label_config = MotionLabelConfig(**candidate_config)
        validation_labels = _evaluate_recommended_labels(traces, base, candidate_label_config)
    else:
        validation_labels = {"validation_label_distribution": {}, "per_scenario": {},
                             "median_event_relative_detection_latency_s": {},
                             "phenotype_overlap_session_ids": []}

    s2_details = validation_labels.get("per_scenario", {}).get("S2", {}).get(
        "session_details", [])
    s2_latencies = [
        item["first_phenotype_time_s"]["persistent_offset"] -
        float(item["event_t0_s_for_evaluation_only"])
        for item in s2_details
        if item["first_phenotype_time_s"]["persistent_offset"] is not None and
        item["event_t0_s_for_evaluation_only"] is not None
    ]
    s0b_details = validation_labels.get("per_scenario", {}).get("S0b", {}).get(
        "session_details", [])
    s0b_false_sessions = sum(
        item["first_phenotype_time_s"]["persistent_offset"] is not None
        for item in s0b_details)

    session_payload = [{
        "session_id": entry.session_id,
        "scenario_id": entry.scenario.value,
        "split": entry.split.value,
        "seed": entry.seed,
    } for entry in plan]
    pilot_path = os.path.join(output_dir, "labeling_v2_pilot.jsonl.gz")
    _write_pilot_gzip(pilot_path, traces, base.time.dt_s)
    with open(pilot_path, "rb") as pilot_file:
        pilot_sha256 = hashlib.sha256(pilot_file.read()).hexdigest()
    candidate_path = os.path.join(output_dir, "labeling_v2_candidate.json")
    report_path = os.path.join(output_dir, "labeling_v2_calibration_report.md")

    payload: Dict[str, Any] = {
        "labeling_version": "v2",
        "calibration_status": "candidate",
        "threshold_candidates": {
            "high_roll_centered_deg": high_survey["threshold_candidates_deg"],
            "amplitude_growth": growth_specs,
        },
        "recommended_thresholds": recommended_thresholds,
        "selection_method": {
            "train": "derive HIGH_ROLL and growth thresholds from empirical Train pilot distributions",
            "validation": (
                "rank candidates using balanced discrimination of background/stress exposure strata "
                "for HIGH_ROLL and session sensitivity/false-growth tradeoff for AMPLITUDE_GROWTH; "
                "session-level measured RMS increase is an independent evaluation reference"),
            "scenario_id_is_not_motion_ground_truth": True,
            "event_metadata_used_only_for_stratification_and_latency_audit": True,
            "test_g1_test_g2_used": False,
            "window_overlap_inference": "descriptive only; no window independence assumption",
        },
        "pilot": {
            "base_seed": seed,
            "train_per_scenario": train_per_scenario,
            "validation_per_scenario": validation_per_scenario,
            "train_sessions": len(train_traces),
            "validation_sessions": len(validation_traces),
            "total_sessions": len(traces),
            "session_plan": session_payload,
            "raw_pilot_path": os.path.basename(pilot_path),
            "raw_pilot_sha256": pilot_sha256,
        },
        "generator_version": base.generator_version,
        "config_version": base.config_version,
        "wave_generator": "G1",
        "sea_state_profile": {
            "profile_id": base.sea_state_profile.profile_id,
            "calibration_status": base.sea_state_profile.calibration_status.value,
            "sigma_w_by_state_deg_equivalent":
                base.sea_state_profile.sigma_w_by_state_deg,
            "units": "degree-equivalent angular forcing sigma, not physical wave height",
        },
        "simulation": {
            "duration_s": base.time.duration_s,
            "dt_s": base.time.dt_s,
            "sample_rate_hz": base.time.sample_rate_hz,
            "output_rate_hz": base.time.output_rate_hz,
        },
        "high_roll_calibration": high_survey,
        "persistent_offset_validation": {
            "threshold_deg_signed_mean_magnitude": 3.0,
            "mean_window_s": 180.0,
            "minimum_duration_s": 120.0,
            "uses_roll_only_for_labeling": True,
            "evaluation_uses_event_metadata_only_for_latency": True,
            "s2_sessions": len(s2_details),
            "s2_detected_sessions": len(s2_latencies),
            "s2_median_latency_s": statistics.median(s2_latencies)
                if s2_latencies else None,
            "s0b_sessions": len(s0b_details),
            "s0b_false_sessions": s0b_false_sessions,
            "false_and_detection_by_scenario": {
                scenario: {
                    "sessions": stats["sessions"],
                    "persistent_windows": stats["phenotype_true_windows"]["persistent_offset"],
                    "persistent_label_windows": stats["class_counts"]["PERSISTENT_OFFSET"],
                    "class_counts": stats["class_counts"],
                    "details": stats["session_details"],
                }
                for scenario, stats in validation_labels.get("per_scenario", {}).items()
            },
        },
        "growth_calibration": {
            "train_metric_summary": growth_train_info,
            "candidate_count": len(growth_specs),
            "validation_candidates": growth_validation,
            "recommended_candidate": growth_recommended,
            "evaluation_reference": (
                "ScenarioResult independent end-session measured RMS increase; used only for "
                "session-level Validation scoring and never to label past samples"),
        },
        "validation_recommended_candidate": validation_labels,
        "output_files": {
            "candidate_json": os.path.basename(candidate_path),
            "report_markdown": os.path.basename(report_path),
            "pilot_trace_gzip": os.path.basename(pilot_path),
        },
        "limitations": [
            "Synthetic G1 pilot does not establish real-vessel performance.",
            "All thresholds remain candidate pending human review and group approval.",
            "Exposure strata are diagnostic context, not absolute movement labels.",
            "Pilot window rates are descriptive because adjacent windows overlap.",
            "No Test-G1/Test-G2 sessions or official 605-session dataset were used.",
        ],
    }
    with open(candidate_path, "w", encoding="utf-8") as output:
        json.dump(payload, output, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")
    with open(report_path, "w", encoding="utf-8") as output:
        output.write(_render_report(payload))
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20261112,
                        help="base nonzero uint32 seed for deterministic pilot sessions")
    parser.add_argument("--train-per-scenario", type=int,
                        default=DEFAULT_TRAIN_PER_SCENARIO,
                        help="Train pilot sessions per scenario (default 10)")
    parser.add_argument("--validation-per-scenario", type=int,
                        default=DEFAULT_VALIDATION_PER_SCENARIO,
                        help="Validation pilot sessions per scenario (default 5)")
    parser.add_argument("--output-dir", default=os.path.dirname(__file__),
                        help="directory for report, candidate JSON and compressed pilot traces")
    args = parser.parse_args(argv)
    try:
        result = run_calibration(
            seed=args.seed,
            output_dir=args.output_dir,
            train_per_scenario=args.train_per_scenario,
            validation_per_scenario=args.validation_per_scenario,
        )
    except (TypeError, ValueError, RuntimeError, OSError) as exc:
        parser.error(str(exc))
    print("Generated {} G1 pilot sessions (Train {}, Validation {}).".format(
        result["pilot"]["total_sessions"], result["pilot"]["train_sessions"],
        result["pilot"]["validation_sessions"]))
    print("Calibration status:", result["calibration_status"])
    print("Recommended thresholds:", json.dumps(result["recommended_thresholds"], sort_keys=True))
    print("Outputs:", os.path.abspath(args.output_dir))
    print("No official dataset or Test-G1/Test-G2 data was created or used.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
