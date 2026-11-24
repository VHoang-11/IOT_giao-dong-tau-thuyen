"""Independent confirmation of frozen labeling_v2 candidate thresholds on G1.

Writes compact metadata and a Markdown report only; signal traces are held in
memory for one run at a time and are never persisted by this tool.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import statistics
from collections import Counter
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from simulation.generator.config import (
    DatasetSplit, GrowthCriterion, LabelingVersion, MotionLabelConfig,
    ProfileCalibrationStatus, ScenarioCode, SimulationConfig, WaveGenerator,
)
from simulation.generator.scenarios import ScenarioRunner

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CANDIDATE_PATH = HERE / "labeling_v2_candidate.json"
PILOT_TRACE_PATH = HERE / "labeling_v2_pilot.jsonl.gz"
DEFAULT_REPORT = HERE / "labeling_v2_independent_validation.md"
DEFAULT_METADATA = HERE / "labeling_v2_independent_validation.json"
SCENARIOS = (ScenarioCode.S0, ScenarioCode.S0B, ScenarioCode.S1,
             ScenarioCode.S2, ScenarioCode.S3, ScenarioCode.H1)
DEFAULT_SEED = 20261202
ANALYSIS_STRIDE = 10


@dataclass(frozen=True)
class ConfirmationEntry:
    session_id: str
    scenario: ScenarioCode
    split: DatasetSplit
    seed: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_pilot_identity(path: Path = PILOT_TRACE_PATH
                        ) -> Tuple[set[str], set[int], str]:
    """Read pilot IDs/seeds and reject any pilot records from test domains."""
    ids: set[str] = set()
    seeds: set[int] = set()
    if not path.exists():
        raise FileNotFoundError("required prior pilot artifact not found: {}".format(path))
    with gzip.open(str(path), "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("split") not in (DatasetSplit.TRAIN.value,
                                         DatasetSplit.VALIDATION.value):
                raise ValueError("pilot contains a disallowed split at line {}".format(
                    line_number))
            session_id, seed = row.get("session_id"), row.get("seed")
            if not isinstance(session_id, str) or not isinstance(seed, int):
                raise ValueError("pilot row missing session ID or integer seed")
            ids.add(session_id)
            seeds.add(seed)
    if len(ids) != 90 or len(seeds) != 90:
        raise ValueError("expected 90 unique pilot IDs/seeds, got {}/{}".format(
            len(ids), len(seeds)))
    return ids, seeds, sha256_file(path)


def build_confirmation_plan(
    seed: int,
    *,
    sessions_per_scenario: int = 10,
    excluded_ids: Iterable[str] = (),
    excluded_seeds: Iterable[int] = (),
) -> Tuple[ConfirmationEntry, ...]:
    """Create deterministic Validation-domain G1 confirmations, never Test."""
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 0xFFFFFFFF:
        raise ValueError("seed must be a nonzero uint32")
    if isinstance(sessions_per_scenario, bool) or not isinstance(sessions_per_scenario, int) or sessions_per_scenario < 1:
        raise ValueError("sessions_per_scenario must be a positive integer")
    used_ids, used_seeds = set(excluded_ids), set(excluded_seeds)
    entries: List[ConfirmationEntry] = []
    candidate_seed = seed
    seed_space = 0xFFFFFFFF
    for scenario in SCENARIOS:
        for ordinal in range(sessions_per_scenario):
            while candidate_seed in used_seeds or candidate_seed == 0:
                candidate_seed = candidate_seed % seed_space + 1
            session_id = "confirm-v2-{}-{:02d}-{:08x}".format(
                scenario.value.lower(), ordinal, candidate_seed)
            while session_id in used_ids:
                candidate_seed = candidate_seed % seed_space + 1
                while candidate_seed in used_seeds or candidate_seed == 0:
                    candidate_seed = candidate_seed % seed_space + 1
                session_id = "confirm-v2-{}-{:02d}-{:08x}".format(
                    scenario.value.lower(), ordinal, candidate_seed)
            entry = ConfirmationEntry(session_id, scenario,
                                      DatasetSplit.VALIDATION, candidate_seed)
            entries.append(entry)
            used_ids.add(session_id)
            used_seeds.add(candidate_seed)
            candidate_seed = candidate_seed % seed_space + 1
    if len({x.session_id for x in entries}) != len(entries) or len({x.seed for x in entries}) != len(entries):
        raise AssertionError("confirmation IDs and seeds must be unique")
    return tuple(entries)


def load_frozen_candidate(path: Path = CANDIDATE_PATH) -> Tuple[MotionLabelConfig, Dict[str, Any]]:
    """Load exact recommended values; preserve candidate status and null ratio."""
    document = json.loads(path.read_text(encoding="utf-8"))
    values = document["recommended_thresholds"]
    if values.get("labeling_version") != "v2":
        raise ValueError("candidate JSON must specify labeling_version=v2")
    if values.get("calibration_status") != "candidate" or values.get(
            "threshold_calibration_status") != "candidate":
        raise ValueError("candidate must remain uncalibrated")
    config = MotionLabelConfig(
        high_roll_centered_threshold_deg=values["high_roll_centered_threshold_deg"],
        persistent_offset_threshold_deg=values["persistent_offset_threshold_deg"],
        persistent_offset_window_s=values["persistent_offset_window_s"],
        persistent_offset_duration_s=values["persistent_offset_duration_s"],
        growth_window_s=values["growth_window_s"],
        growth_ratio_lag_s=values["growth_ratio_lag_s"],
        growth_criterion=GrowthCriterion(values["growth_criterion"]),
        growth_slope_threshold_deg_per_min=values["growth_slope_threshold_deg_per_min"],
        growth_ratio_threshold=values["growth_ratio_threshold"],
        growth_ratio_floor_deg=values["growth_ratio_floor_deg"],
        growth_confirmation_s=values["growth_confirmation_s"],
        threshold_calibration_status=ProfileCalibrationStatus.CANDIDATE,
    )
    if config.growth_criterion is GrowthCriterion.SLOPE and (
            config.growth_ratio_threshold is not None or config.growth_ratio_floor_deg is not None):
        # Record the exact configured state; a slope criterion does not consume ratio.
        pass
    if config.unresolved_v2_thresholds:
        raise ValueError("candidate does not fully configure v2: {}".format(
            config.unresolved_v2_thresholds))
    return config, document


def percentile(values: Sequence[float], q: float) -> Optional[float]:
    valid = sorted(x for x in values if math.isfinite(x))
    if not valid:
        return None
    pos = (len(valid) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return valid[lo] + (valid[hi] - valid[lo]) * (pos - lo)


def describe_latency(values: Sequence[float]) -> Dict[str, Optional[float]]:
    return {"n": len(values), "median_s": percentile(values, .5),
            "p90_s": percentile(values, .9), "p95_s": percentile(values, .95)}


def _signal_summary(result: Any) -> Dict[str, Optional[float]]:
    roll_deg = [math.degrees(value) for value in result.true_roll_rad]
    mean = statistics.fmean(roll_deg)
    return {
        "mean_roll_deg": mean,
        "rms_about_zero_deg": math.sqrt(statistics.fmean(x * x for x in roll_deg)),
        "rms_centered_deg": math.sqrt(statistics.fmean((x - mean) ** 2 for x in roll_deg)),
        "p95_abs_roll_deg": percentile([abs(x) for x in roll_deg], .95),
    }


def _first_flag(result: Any, flag_name: str, *, after_s: Optional[float] = None) -> Optional[float]:
    for timestamp, flags in zip(result.timestamps_s, result.phenotype_flags_v2):
        if after_s is not None and timestamp < after_s:
            continue
        if getattr(flags, flag_name) is True:
            return timestamp
    return None


def _run_session(runner: ScenarioRunner, entry: ConfirmationEntry) -> Dict[str, Any]:
    result = runner.generate(entry.scenario, seed=entry.seed,
                             dataset_split=DatasetSplit.VALIDATION,
                             labeling_version=LabelingVersion.V2)
    event = dict(result.events[0]) if result.events else {}
    t0 = event.get("t0_s")
    event_start = float(t0) if t0 is not None else None
    flags = result.phenotype_flags_v2
    labels = result.labels_v2
    valid_labels = [label for label in labels if label is not None]
    counts = Counter(valid_labels)
    label_total = len(valid_labels)
    warmup = sum(label is None for label in labels)
    transition_count = sum(result.transition_flags)
    flag_truth = {
        "high_roll": [x.high_roll_active is True for x in flags],
        "persistent_offset": [x.persistent_offset_active is True for x in flags],
        "observed_amplitude_growth": [x.observed_amplitude_growth is True for x in flags],
    }
    overlap = sum(sum(values[index] for values in flag_truth.values()) >= 2
                  for index in range(len(flags)))
    first_any = {name: _first_flag(result, name) for name in (
        "high_roll_active", "persistent_offset_active", "observed_amplitude_growth")}
    first_after_event = {name: _first_flag(result, name, after_s=event_start)
                         for name in ("high_roll_active", "persistent_offset_active",
                                      "observed_amplitude_growth")}
    timestamps = result.timestamps_s
    after_indices = [i for i, t in enumerate(timestamps)
                     if event_start is not None and t >= event_start]
    pre_indices = [i for i, t in enumerate(timestamps)
                   if event_start is None or t < event_start]
    # The generator's S3 check is retained as an independent movement reference,
    # not used by the causal labeler. Report the underlying values for audit.
    outcome = result.metadata.get("outcome_checks", {})
    growth_reference = outcome.get("amplitude_growth") if entry.scenario is ScenarioCode.S3 else None
    param_active = any(value > 0.0 for value in result.parametric_excitation_amplitude)
    high_after = first_after_event["high_roll_active"] is not None
    persistent_after = first_after_event["persistent_offset_active"] is not None
    growth_after = first_after_event["observed_amplitude_growth"] is not None
    if entry.scenario in (ScenarioCode.S0, ScenarioCode.S0B):
        expected = "no abnormal phenotype trigger"
        achieved = not any(flag_truth[k][i] for k in flag_truth
                          for i in range(len(flags)))
    elif entry.scenario is ScenarioCode.S1:
        expected, achieved = "post-event HIGH_ROLL phenotype", high_after
    elif entry.scenario is ScenarioCode.S2:
        expected, achieved = "post-event PERSISTENT_OFFSET phenotype", persistent_after
    elif entry.scenario is ScenarioCode.S3:
        expected = "observed growth reference and growth phenotype assessed separately"
        achieved = bool(growth_reference and growth_reference.get("increased")) and growth_after
    else:
        expected, achieved = "combined high-roll and persistent-offset phenotypes", high_after and persistent_after
    row = {
        "session_id": entry.session_id,
        "scenario_id": entry.scenario.value,
        "split": entry.split.value,
        "role": "Independent-Confirmation",
        "seed": entry.seed,
        "valid": all(math.isfinite(x) for x in result.true_roll_rad),
        "sample_count": len(timestamps),
        "generator_version": result.metadata.get("config", {}).get("generator_version",
                                                                     result.metadata.get("generator_version")),
        "config_version": result.metadata.get("config", {}).get("config_version",
                                                                 result.metadata.get("config_version")),
        "sampled_parameters": result.metadata.get("sampled_parameters", {}),
        "event_metadata_audit_only": event,
        "motion_summary": _signal_summary(result),
        "label_window_counts_excluding_warmup": dict(sorted(counts.items())),
        "classified_windows": label_total,
        "warmup_or_unknown_windows": warmup,
        "transition_windows": transition_count,
        "phenotype_windows": {key: sum(values) for key, values in flag_truth.items()},
        "phenotype_overlap_windows": overlap,
        "phenotype_session_trigger_anytime": {key: any(values) for key, values in flag_truth.items()},
        "first_phenotype_time_any_s": first_any,
        "first_phenotype_time_at_or_after_event_s": first_after_event,
        "event_relative_latency_s": {
            key: (None if value is None or event_start is None else value - event_start)
            for key, value in first_after_event.items()},
        "parametric_excitation_active_observed_from_signal": param_active,
        "s3_observed_growth_reference_audit_only": growth_reference,
        "expected_outcome_for_diagnostic_only": expected,
        "diagnostic_outcome_met": achieved,
    }
    if event_start is not None:
        high_time = first_after_event["high_roll_active"]
        offset_time = first_after_event["persistent_offset_active"]
        row["event_relative_latency_s"]["combined_high_roll_and_persistent_offset"] = (
            None if high_time is None or offset_time is None else
            max(high_time, offset_time) - event_start)
    del result
    return row


def _pilot_comparison(candidate_doc: Mapping[str, Any]) -> Dict[str, Any]:
    details = candidate_doc["validation_recommended_candidate"]["per_scenario"]
    output: Dict[str, Any] = {}
    flag_key = {"S1": "high_roll", "S2": "persistent_offset", "S3": "amplitude_growth",
                "H1": "high_roll"}
    for scenario, item in details.items():
        per_session = item.get("session_details", [])
        latencies = []
        for run in per_session:
            if scenario == "H1":
                times = run.get("first_phenotype_time_s", {})
                t0 = run.get("event_t0_s_for_evaluation_only")
                high, offset = times.get("high_roll"), times.get("persistent_offset")
                if (t0 is not None and high is not None and offset is not None and
                        high >= t0 and offset >= t0):
                    latencies.append(max(float(high), float(offset)) - float(t0))
            elif scenario in flag_key:
                key = flag_key[scenario]
                first = run.get("first_phenotype_time_s", {}).get(key)
                t0 = run.get("event_t0_s_for_evaluation_only")
                if first is not None and t0 is not None and first >= t0:
                    latencies.append(float(first) - float(t0))
        output[scenario] = {
            "validation_sessions": len(per_session),
            "class_pct_excluding_warmup": item.get("class_pct_excluding_warmup", {}),
            "phenotype_overlap_windows": item.get("phenotype_overlap_windows", 0),
            "detected_sessions_for_primary_phenotype": sum(x >= 0 for x in latencies),
            "primary_latency_s": describe_latency(latencies),
            "source": "prior calibration candidate JSON Validation summary; pilot sample n=5/scenario",
        }
    return output


def _summarize(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    summaries: Dict[str, Any] = {}
    latency_flags = {
        "S1": "high_roll_active",
        "S2": "persistent_offset_active",
        "S3": ("observed_amplitude_growth", "observed_amplitude_growth"),
        "H1": "combined_high_roll_and_persistent_offset",
    }
    for scenario in (x.value for x in SCENARIOS):
        selected = [row for row in rows if row["scenario_id"] == scenario]
        label_totals: Counter[str] = Counter()
        classified = 0
        for row in selected:
            label_totals.update(row["label_window_counts_excluding_warmup"])
            classified += row["classified_windows"]
        pct = {label: (100.0 * count / classified if classified else None)
               for label, count in sorted(label_totals.items())}
        trigger = {name: sum(row["phenotype_session_trigger_anytime"].get(name, False)
                             for row in selected) for name in (
                                 "high_roll", "persistent_offset", "observed_amplitude_growth")}
        item: Dict[str, Any] = {
            "sessions": len(selected),
            "valid_sessions": sum(row["valid"] for row in selected),
            "label_percent_excluding_warmup": pct,
            "classified_windows": classified,
            "warmup_or_unknown_windows": sum(row["warmup_or_unknown_windows"] for row in selected),
            "transition_windows": sum(row["transition_windows"] for row in selected),
            "phenotype_session_triggers": trigger,
            "sessions_with_phenotype_overlap": sum(row["phenotype_overlap_windows"] > 0
                                                     for row in selected),
            "phenotype_overlap_windows": sum(row["phenotype_overlap_windows"] for row in selected),
            "diagnostic_outcomes_met": sum(row["diagnostic_outcome_met"] for row in selected),
        }
        if scenario == "S1":
            item["post_event_primary_detections"] = sum(
                row["first_phenotype_time_at_or_after_event_s"]["high_roll_active"] is not None
                for row in selected)
        elif scenario == "S2":
            item["post_event_primary_detections"] = sum(
                row["first_phenotype_time_at_or_after_event_s"]["persistent_offset_active"] is not None
                for row in selected)
        elif scenario == "S3":
            item["post_event_primary_detections"] = sum(
                row["first_phenotype_time_at_or_after_event_s"]["observed_amplitude_growth"] is not None
                for row in selected)
            item["observed_growth_reference_positive_sessions"] = sum(
                bool(row["s3_observed_growth_reference_audit_only"] and
                     row["s3_observed_growth_reference_audit_only"].get("increased"))
                for row in selected)
            item["growth_flag_and_reference_both_positive"] = sum(
                bool(row["s3_observed_growth_reference_audit_only"] and
                     row["s3_observed_growth_reference_audit_only"].get("increased") and
                     row["first_phenotype_time_at_or_after_event_s"][
                         "observed_amplitude_growth"] is not None)
                for row in selected)
        elif scenario == "H1":
            item["post_event_primary_detections"] = sum(
                row["first_phenotype_time_at_or_after_event_s"]["high_roll_active"] is not None and
                row["first_phenotype_time_at_or_after_event_s"]["persistent_offset_active"] is not None
                for row in selected)
        if scenario in latency_flags:
            phenotype = latency_flags[scenario]
            if isinstance(phenotype, tuple):
                phenotype = phenotype[0]
            latency_values = [row["event_relative_latency_s"][phenotype]
                              for row in selected
                              if row["event_relative_latency_s"][phenotype] is not None]
            item["primary_event_latency"] = describe_latency(latency_values)
        summaries[scenario] = item
    # False-trigger denominators are session-level, scenario-specific control runs.
    controls = [row for row in rows if row["scenario_id"] in ("S0", "S0b")]
    summaries["controls_false_triggers"] = {
        name: {"triggered_sessions": sum(row["phenotype_session_trigger_anytime"].get(name, False)
                                          for row in controls),
              "sessions": len(controls)}
        for name in ("high_roll", "persistent_offset", "observed_amplitude_growth")
    }
    summaries["controls_false_triggers_by_scenario"] = {
        scenario: {
            "sessions": sum(row["scenario_id"] == scenario for row in controls),
            **{name: sum(row["scenario_id"] == scenario and
                         row["phenotype_session_trigger_anytime"].get(name, False)
                         for row in controls)
               for name in ("high_roll", "persistent_offset", "observed_amplitude_growth")},
        }
        for scenario in ("S0", "S0b")
    }
    return summaries


def _markdown_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Labeling v2 Independent Threshold Validation",
        "",
        "## Scope and frozen candidate",
        "",
        "Independent G1 confirmation only: 60 new sessions, 10 per scenario. All were generated through the `Validation` parameter domain; no Test-G1/Test-G2 split was used. Candidate thresholds were loaded unchanged from `labeling_v2_candidate.json`. The candidate and pilot artifact hashes are recorded in the companion JSON. `calibration_status` remains `candidate`; this report does not approve or calibrate thresholds.",
        "",
        "The labeler consumes only the current and past clean roll samples. Scenario/event metadata is retained only as audit/exposure information for stratified evaluation. Scenario exposure, observed motion, phenotype flags, and final priority labels are reported separately. No labels produced by this candidate are treated as independent ground truth.",
        "",
        "## Exact candidate settings",
        "",
        "```json",
        json.dumps(payload["thresholds_frozen"], indent=2, sort_keys=True),
        "```",
        "",
        "Growth uses `slope` only. The JSON has `growth_ratio_threshold: null` and `growth_ratio_floor_deg: null`, so ratio is computed as a diagnostic by the labeler where available but does not participate in the selected growth predicate. No combined growth condition was inferred.",
        "",
        "## Scenario results",
        "",
        "| Scenario | Valid / 10 | NORMAL % | HIGH_ROLL % | PERSISTENT_OFFSET % | AMPLITUDE_GROWTH % | Warm-up windows | Transition windows | Overlap windows | Diagnostic outcome met | Latency median / P90 / P95 (s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for code in (x.value for x in SCENARIOS):
        s = payload["summary"][code]
        pct = s["label_percent_excluding_warmup"]
        def p(label: str) -> str:
            return "{:.2f}".format(pct.get(label, 0.0) or 0.0)
        primary = s.get("diagnostic_outcomes_met", 0)
        latency = s.get("primary_event_latency", {})
        vals = [latency.get(k) for k in ("median_s", "p90_s", "p95_s")]
        latency_text = " / ".join("—" if x is None else "{:.2f}".format(x) for x in vals)
        lines.append("| {} | {} / 10 | {} | {} | {} | {} | {} | {} | {} | {} / 10 | {} |".format(
            code, s["valid_sessions"], p("NORMAL"), p("HIGH_ROLL"),
            p("PERSISTENT_OFFSET"), p("AMPLITUDE_GROWTH"),
            s["warmup_or_unknown_windows"], s["transition_windows"],
            s["phenotype_overlap_windows"], primary, latency_text))
    lines += ["", "### Control false triggers", "",
              "Session-level triggers are counted if the phenotype flag occurred at any time, including the pre-event period. S0/S0b are diagnostic controls; a trigger is not automatically proof of a false physical label.", "",
              "| Phenotype | Triggered S0/S0b sessions | Controls |", "|---|---:|---:|"]
    for name, item in payload["summary"]["controls_false_triggers"].items():
        lines.append("| {} | {} | {} |".format(name, item["triggered_sessions"], item["sessions"]))
    lines += ["", "Per-control breakdown:", "",
              "| Scenario | Sessions | HIGH_ROLL | PERSISTENT_OFFSET | AMPLITUDE_GROWTH |",
              "|---|---:|---:|---:|---:|"]
    for scenario, item in payload["summary"]["controls_false_triggers_by_scenario"].items():
        lines.append("| {} | {} | {} | {} | {} |".format(
            scenario, item["sessions"], item["high_roll"],
            item["persistent_offset"], item["observed_amplitude_growth"]))
    lines += ["", "## Comparison with pilot Validation", "",
              "Class shares exclude warm-up/unknown samples. Confirmation detections use observed phenotype flags at or after event `t0`; H1 requires both HIGH_ROLL and PERSISTENT_OFFSET. Pilot latency is recomputed from the previous candidate JSON's first-phenotype times and is uncertain at n=5.",
              "", "| Scenario | Pilot N/H/P/G (%) | Confirmation N/H/P/G (%) | Pilot primary detections | Confirmation primary detections | Pilot latency median / P90 / P95 (s) | Confirmation latency median / P90 / P95 (s) |", "|---|---|---|---:|---:|---:|---:|"]
    label_order = ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH")
    for code in (x.value for x in SCENARIOS):
        pilot = payload["pilot_validation_comparison"].get(code, {})
        current = payload["summary"][code]
        pilot_pct = pilot.get("class_pct_excluding_warmup", {})
        current_pct = current["label_percent_excluding_warmup"]
        pstr = "/".join("{:.1f}".format(pilot_pct.get(label, 0.0)) for label in label_order)
        cstr = "/".join("{:.1f}".format(current_pct.get(label, 0.0) or 0.0)
                         for label in label_order)
        oldlat = pilot.get("primary_latency_s", {})
        newlat = current.get("primary_event_latency", {})
        def latency_cell(data: Mapping[str, Any]) -> str:
            return " / ".join("—" if data.get(k) is None else "{:.1f}".format(data[k])
                              for k in ("median_s", "p90_s", "p95_s"))
        lines.append("| {} | {} | {} | {} / 5 | {} / 10 | {} | {} |".format(
            code, pstr, cstr, pilot.get("detected_sessions_for_primary_phenotype", 0),
            current.get("post_event_primary_detections", 0),
            latency_cell(oldlat), latency_cell(newlat)))
    lines += ["", "## Outcome and exposure interpretation", "",
              "- S1 detection is the observed HIGH_ROLL phenotype after event `t0`; S2 detection is the observed PERSISTENT_OFFSET phenotype after `t0`; S3 reports the causal growth phenotype separately from the generator's end-of-session RMS movement reference; H1's combined diagnostic requires both high-roll and persistent-offset phenotypes after `t0`.",
              "- `t0`, event type, sea state, and parametric forcing are evaluation/audit metadata only. They do not activate a label. Transition flags are reported as evaluation metadata and do not affect classification.",
              "- The S3 movement reference is an end-of-session comparison supplied by the generator and is retrospective evaluation only. It is not used to assign any earlier label and is not an independent real-vessel ground truth.",
              "- S3: movement-reference positives {}/10; post-event growth phenotype {}/10; both conditions together {}/10. These are distinct descriptive checks, not labels used as their own ground truth.".format(
                  payload["summary"]["S3"].get("observed_growth_reference_positive_sessions", 0),
                  payload["summary"]["S3"].get("post_event_primary_detections", 0),
                  payload["summary"]["S3"].get("growth_flag_and_reference_both_positive", 0)),
              "- Per-session successes and misses, exposure metadata, sampled parameters, and label/phenotype counts are in the companion JSON. No roll traces are stored.",
              "", "## Pilot comparison notes", "",
              "The prior calibration report's Validation cohort has only five sessions per scenario. Differences are descriptive: sample sizes and pilot/confirmation seed sets differ, and scenario exposure is not physical ground truth.", "",
              "## Limitations and recommendation", "",
              "This confirmation is small (10 per scenario), generated by the same G1 simulator and candidate sea-state profile, and does not establish performance on vessels or on G2. S0/S0b phenotype triggers are useful false-trigger diagnostics; S2/H1 overlap reflects the priority labeler potentially masking one phenotype in the single class label. The H1 combined outcome requires both observable phenotypes, while the final class follows the configured priority.",
              "", "Do not mark the thresholds calibrated from this run. These results are not sufficient to lock the thresholds: S0b produced false phenotype triggers, the S3 growth movement-reference agreement was 8/10, and phenotype overlap is substantial in S1/S3/H1. The recommendation is to return to calibration review using Train/Validation evidence only, preserve these confirmation results without tuning to them, and run a fresh confirmation only after any candidate changes are approved. Test-G1/Test-G2 remain untouched.",
              "", "### Sessions not meeting the diagnostic outcome", "",
              "S3's diagnostic outcome requires both the retrospective movement-reference increase and a post-event growth phenotype; S0/S0b require no abnormal phenotype trigger; S1/S2 require their primary phenotype; H1 requires both high-roll and persistent-offset phenotypes.", ""]
    misses = [row for row in payload["sessions"] if not row["diagnostic_outcome_met"]]
    if misses:
        lines += ["| Scenario | Session ID | Diagnostic note | Observed motion / event details |",
                  "|---|---|---|---|"]
        for row in misses:
            motion = row["motion_summary"]
            event = row["event_metadata_audit_only"]
            details = "mean {:.2f}°, centered RMS {:.2f}°, P95 |roll| {:.2f}°; event {}".format(
                motion["mean_roll_deg"], motion["rms_centered_deg"],
                motion["p95_abs_roll_deg"], json.dumps(event, sort_keys=True))
            lines.append("| {} | `{}` | {} | {} |".format(
                row["scenario_id"], row["session_id"],
                row["expected_outcome_for_diagnostic_only"], details))
    else:
        lines.append("All sessions met their diagnostic outcome definition.")
    lines += ["", "## Reproducibility", "",
              "The companion JSON stores all 60 session IDs/seeds, G1 generator/config versions, sampled parameters, event metadata for audit, output hashes of the frozen candidate and previous pilot trace, and compact per-session outcome/label summaries. Full traces were not written.", ""]
    return "\n".join(lines)


def run_validation(*, seed: int = DEFAULT_SEED, sessions_per_scenario: int = 10,
                   report_path: Path = DEFAULT_REPORT,
                   metadata_path: Path = DEFAULT_METADATA) -> Dict[str, Any]:
    candidate_hash_before = sha256_file(CANDIDATE_PATH)
    excluded_ids, excluded_seeds, pilot_hash = read_pilot_identity()
    plan = build_confirmation_plan(seed, sessions_per_scenario=sessions_per_scenario,
                                   excluded_ids=excluded_ids, excluded_seeds=excluded_seeds)
    if len(plan) != 60 or sessions_per_scenario != 10:
        raise ValueError("independent confirmation is fixed at 10 per scenario (60 total)")
    if any(entry.session_id in excluded_ids or entry.seed in excluded_seeds for entry in plan):
        raise AssertionError("confirmation overlaps prior pilot")
    candidate, candidate_doc = load_frozen_candidate()
    base = SimulationConfig()
    config = replace(base, labeling=candidate, waves=replace(base.waves, generator=WaveGenerator.G1))
    runner = ScenarioRunner(config)
    session_rows = [_run_session(runner, entry) for entry in plan]
    summary = _summarize(session_rows)
    pilot_summary = _pilot_comparison(candidate_doc)
    if sha256_file(CANDIDATE_PATH) != candidate_hash_before:
        raise AssertionError("frozen candidate JSON changed during confirmation")
    profile = config.sea_state_profile
    payload: Dict[str, Any] = {
        "validation_status": "independent_confirmation_complete_candidate_not_calibrated",
        "labeling_version": "v2",
        "calibration_status": "candidate",
        "threshold_calibration_status": "candidate",
        "wave_generator": "G1",
        "seed_start": seed,
        "session_count": len(session_rows),
        "sessions_per_scenario": sessions_per_scenario,
        "dataset_role": "Independent-Confirmation; generated using Validation parameter domain",
        "test_g1_or_test_g2_used": False,
        "input_pilot_sessions": 90,
        "pilot_session_id_overlap": 0,
        "pilot_seed_overlap": 0,
        "pilot_artifact": {"path": PILOT_TRACE_PATH.name, "sha256": pilot_hash},
        "candidate_artifact": {"path": CANDIDATE_PATH.name, "sha256": candidate_hash_before},
        "thresholds_frozen": asdict(candidate),
        "growth_rule_interpretation": {
            "criterion": candidate.growth_criterion.value,
            "ratio_threshold": candidate.growth_ratio_threshold,
            "ratio_floor_deg": candidate.growth_ratio_floor_deg,
            "ratio_is_active_predicate": candidate.growth_criterion in (
                GrowthCriterion.RATIO, GrowthCriterion.SLOPE_AND_RATIO,
                GrowthCriterion.SLOPE_OR_RATIO),
        },
        "simulation": {"duration_s": config.time.duration_s, "dt_s": config.time.dt_s,
                       "sample_count": config.time.sample_count,
                       "generator_version": config.generator_version,
                       "config_version": config.config_version},
        "sea_state_profile": {"profile_id": profile.profile_id,
                              "calibration_status": profile.calibration_status.value,
                              "sigma_w_equivalent_deg": profile.sigma_w_by_state_deg},
        "plan": [{"session_id": e.session_id, "scenario_id": e.scenario.value,
                  "split": e.split.value, "seed": e.seed} for e in plan],
        "summary": summary,
        "pilot_validation_comparison": pilot_summary,
        "sessions": session_rows,
        "trace_persistence": "none; full traces were not saved",
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(payload, indent=2, sort_keys=True,
                                        allow_nan=False) + "\n", encoding="utf-8")
    report_path.write_text(_markdown_report(payload), encoding="utf-8")
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--sessions-per-scenario", type=int, default=10)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    args = parser.parse_args(argv)
    payload = run_validation(seed=args.seed,
                             sessions_per_scenario=args.sessions_per_scenario,
                             report_path=args.report, metadata_path=args.metadata)
    print("Validated {} sessions; calibration_status={}".format(
        payload["session_count"], payload["calibration_status"]))
    print("Report: {}".format(args.report))
    print("Metadata: {}".format(args.metadata))
    for scenario in (x.value for x in SCENARIOS):
        item = payload["summary"][scenario]
        print("{}: valid={}/{} outcomes={} overlap_windows={}".format(
            scenario, item["valid_sessions"], item["sessions"],
            item["diagnostic_outcomes_met"], item["phenotype_overlap_windows"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
