# Labeling v2 Independent Threshold Validation

## Scope and frozen candidate

Independent G1 confirmation only: 60 new sessions, 10 per scenario. All were generated through the `Validation` parameter domain; no Test-G1/Test-G2 split was used. Candidate thresholds were loaded unchanged from `labeling_v2_candidate.json`. The candidate and pilot artifact hashes are recorded in the companion JSON. `calibration_status` remains `candidate`; this report does not approve or calibrate thresholds.

The labeler consumes only the current and past clean roll samples. Scenario/event metadata is retained only as audit/exposure information for stratified evaluation. Scenario exposure, observed motion, phenotype flags, and final priority labels are reported separately. No labels produced by this candidate are treated as independent ground truth.

## Exact candidate settings

```json
{
  "growth_confirmation_s": 10.0,
  "growth_criterion": "slope",
  "growth_ratio_floor_deg": null,
  "growth_ratio_lag_s": 120.0,
  "growth_ratio_threshold": null,
  "growth_slope_threshold_deg_per_min": 1.769349623333755,
  "growth_window_s": 180.0,
  "high_roll_centered_threshold_deg": 8.40884426,
  "persistent_offset_duration_s": 120.0,
  "persistent_offset_threshold_deg": 3.0,
  "persistent_offset_window_s": 180.0,
  "threshold_calibration_status": "candidate"
}
```

Growth uses `slope` only. The JSON has `growth_ratio_threshold: null` and `growth_ratio_floor_deg: null`, so ratio is computed as a diagnostic by the labeler where available but does not participate in the selected growth predicate. No combined growth condition was inferred.

## Scenario results

| Scenario | Valid / 10 | NORMAL % | HIGH_ROLL % | PERSISTENT_OFFSET % | AMPLITUDE_GROWTH % | Warm-up windows | Transition windows | Overlap windows | Diagnostic outcome met | Latency median / P90 / P95 (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S0 | 10 / 10 | 100.00 | 0.00 | 0.00 | 0.00 | 48010 | 0 | 0 | 10 / 10 | — / — / — |
| S0b | 10 / 10 | 98.72 | 0.62 | 0.00 | 0.66 | 48010 | 18000 | 1054 | 8 / 10 | — / — / — |
| S1 | 10 / 10 | 57.30 | 36.24 | 0.00 | 6.46 | 48010 | 18000 | 26317 | 10 / 10 | 145.22 / 253.25 / 279.10 |
| S2 | 10 / 10 | 26.28 | 0.00 | 72.75 | 0.97 | 48010 | 18000 | 0 | 10 / 10 | 223.78 / 252.91 / 266.20 |
| S3 | 10 / 10 | 63.82 | 33.46 | 0.00 | 2.72 | 48010 | 18000 | 11598 | 8 / 10 | 126.65 / 384.53 / 570.29 |
| H1 | 10 / 10 | 39.47 | 41.59 | 16.65 | 2.30 | 48010 | 18000 | 52186 | 10 / 10 | 260.30 / 680.00 / 762.35 |

### Control false triggers

Session-level triggers are counted if the phenotype flag occurred at any time, including the pre-event period. S0/S0b are diagnostic controls; a trigger is not automatically proof of a false physical label.

| Phenotype | Triggered S0/S0b sessions | Controls |
|---|---:|---:|
| high_roll | 1 | 20 |
| persistent_offset | 0 | 20 |
| observed_amplitude_growth | 2 | 20 |

Per-control breakdown:

| Scenario | Sessions | HIGH_ROLL | PERSISTENT_OFFSET | AMPLITUDE_GROWTH |
|---|---:|---:|---:|---:|
| S0 | 10 | 0 | 0 | 0 |
| S0b | 10 | 1 | 0 | 2 |

## Comparison with pilot Validation

Class shares exclude warm-up/unknown samples. Confirmation detections use observed phenotype flags at or after event `t0`; H1 requires both HIGH_ROLL and PERSISTENT_OFFSET. Pilot latency is recomputed from the previous candidate JSON's first-phenotype times and is uncertain at n=5.

| Scenario | Pilot N/H/P/G (%) | Confirmation N/H/P/G (%) | Pilot primary detections | Confirmation primary detections | Pilot latency median / P90 / P95 (s) | Confirmation latency median / P90 / P95 (s) |
|---|---|---|---:|---:|---:|---:|
| S0 | 100.0/0.0/0.0/0.0 | 100.0/0.0/0.0/0.0 | 0 / 5 | 0 / 10 | — / — / — | — / — / — |
| S0b | 100.0/0.0/0.0/0.0 | 98.7/0.6/0.0/0.7 | 0 / 5 | 0 / 10 | — / — / — | — / — / — |
| S1 | 64.6/31.8/0.0/3.6 | 57.3/36.2/0.0/6.5 | 5 / 5 | 10 / 10 | 125.0 / 532.5 / 601.8 | 145.2 / 253.2 / 279.1 |
| S2 | 26.1/0.0/73.9/0.0 | 26.3/0.0/72.8/1.0 | 5 / 5 | 10 / 10 | 221.1 / 230.0 / 230.6 | 223.8 / 252.9 / 266.2 |
| S3 | 78.6/16.7/0.0/4.7 | 63.8/33.5/0.0/2.7 | 5 / 5 | 9 / 10 | 129.5 / 337.6 / 338.2 | 126.6 / 384.5 / 570.3 |
| H1 | 17.6/39.3/41.4/1.7 | 39.5/41.6/16.6/2.3 | 4 / 5 | 10 / 10 | 231.6 / 255.6 / 257.4 | 260.3 / 680.0 / 762.3 |

## Outcome and exposure interpretation

- S1 detection is the observed HIGH_ROLL phenotype after event `t0`; S2 detection is the observed PERSISTENT_OFFSET phenotype after `t0`; S3 reports the causal growth phenotype separately from the generator's end-of-session RMS movement reference; H1's combined diagnostic requires both high-roll and persistent-offset phenotypes after `t0`.
- `t0`, event type, sea state, and parametric forcing are evaluation/audit metadata only. They do not activate a label. Transition flags are reported as evaluation metadata and do not affect classification.
- The S3 movement reference is an end-of-session comparison supplied by the generator and is retrospective evaluation only. It is not used to assign any earlier label and is not an independent real-vessel ground truth.
- S3: movement-reference positives 9/10; post-event growth phenotype 9/10; both conditions together 8/10. These are distinct descriptive checks, not labels used as their own ground truth.
- Per-session successes and misses, exposure metadata, sampled parameters, and label/phenotype counts are in the companion JSON. No roll traces are stored.

## Pilot comparison notes

The prior calibration report's Validation cohort has only five sessions per scenario. Differences are descriptive: sample sizes and pilot/confirmation seed sets differ, and scenario exposure is not physical ground truth.

## Limitations and recommendation

This confirmation is small (10 per scenario), generated by the same G1 simulator and candidate sea-state profile, and does not establish performance on vessels or on G2. S0/S0b phenotype triggers are useful false-trigger diagnostics; S2/H1 overlap reflects the priority labeler potentially masking one phenotype in the single class label. The H1 combined outcome requires both observable phenotypes, while the final class follows the configured priority.

Do not mark the thresholds calibrated from this run. These results are not sufficient to lock the thresholds: S0b produced false phenotype triggers, the S3 growth movement-reference agreement was 8/10, and phenotype overlap is substantial in S1/S3/H1. The recommendation is to return to calibration review using Train/Validation evidence only, preserve these confirmation results without tuning to them, and run a fresh confirmation only after any candidate changes are approved. Test-G1/Test-G2 remain untouched.

### Sessions not meeting the diagnostic outcome

S3's diagnostic outcome requires both the retrospective movement-reference increase and a post-event growth phenotype; S0/S0b require no abnormal phenotype trigger; S1/S2 require their primary phenotype; H1 requires both high-roll and persistent-offset phenotypes.

| Scenario | Session ID | Diagnostic note | Observed motion / event details |
|---|---|---|---|
| S0b | `confirm-v2-s0b-01-0135295d` | no abnormal phenotype trigger | mean 0.13°, centered RMS 3.27°, P95 |roll| 6.53°; event {"end_s": 335.45, "expected_label": "NORMAL", "heel_offset_deg": 3.102154560154304, "t0_s": 277.25, "type": "temporary_heel_offset"} |
| S0b | `confirm-v2-s0b-02-0135295e` | no abnormal phenotype trigger | mean 0.25°, centered RMS 4.61°, P95 |roll| 9.19°; event {"end_s": 365.75, "expected_label": "NORMAL", "heel_offset_deg": 5.213558068033308, "t0_s": 277.3, "type": "temporary_heel_offset"} |
| S3 | `confirm-v2-s3-04-0135297e` | observed growth reference and growth phenotype assessed separately | mean -0.05°, centered RMS 4.04°, P95 |roll| 8.41°; event {"Omega_rad_s": 0.5307540274037242, "end_s": 1200.0, "expected_label": "AMPLITUDE_GROWTH", "h": 0.2963866643840447, "t0_s": 276.85, "type": "parametric_excitation"} |
| S3 | `confirm-v2-s3-09-01352983` | observed growth reference and growth phenotype assessed separately | mean -0.07°, centered RMS 5.72°, P95 |roll| 11.42°; event {"Omega_rad_s": 0.49259575510079606, "end_s": 1200.0, "expected_label": "AMPLITUDE_GROWTH", "h": 0.31518838030751795, "t0_s": 274.35, "type": "parametric_excitation"} |

## Reproducibility

The companion JSON stores all 60 session IDs/seeds, G1 generator/config versions, sampled parameters, event metadata for audit, output hashes of the frozen candidate and previous pilot trace, and compact per-session outcome/label summaries. Full traces were not written.
