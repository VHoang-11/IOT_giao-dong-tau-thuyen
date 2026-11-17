# Labeling v2 Pilot Threshold Calibration

**Status:** candidate only; not approved/calibrated for the official 605-session dataset.
**Data:** deterministic G1 pilot; synthetic simulation only, not vessel evidence.

## Pilot plan

- Sessions: 60/30 Train / Validation.
- Seed base: `20261112`; unique session seeds and IDs are in the candidate JSON and compressed pilot file.
- Scenarios: S0, S0b, S1, S2, S3, H1; no Test-G1/Test-G2 sessions.
- Sea-state profile: `svmg-sea-state-candidate-v1` (candidate; sigma_w is equivalent-angle forcing, not wave height).
- Generator: `0.1.0`; sample rate 20.0 Hz, dt 0.05 s.
- Pilot trace is audit data (clean roll truth and generator metadata), not an ML feature dataset.

## Metrics surveyed

Roll-zero RMS, centered 60 s population std, signed 180 s mean, P95(abs roll),
60 s RMS trend slope, 180 s growth ratio, v2 class/phenotype shares, overlap, warm-up,
and event-relative detection latency were evaluated. Centered/std and slope/ratio windows
are highly correlated; windows are diagnostic, while candidate scores use session grouping.

## HIGH_ROLL threshold candidates

Candidate centered thresholds (degrees): `[6.75855361, 7.61215413, 8.40884426]`.
Train S0/S0b q99: `8.4088`°; Train post-transition S1/H1 q10: `4.0568`°.
Recommended pilot candidate: **8.4088°** centered std over 60 s.
Train thresholds include empirical background quantiles and a distribution-gap midpoint when available.
Validation ranks these candidates by session-level background/stress-exposure discrimination.
Scenario/event metadata defines those diagnostic exposure strata only; it is not a motion label.
Validation background false-session rate: 0.0%; S1/H1 exposure session detection: 100.0%.
Median detection latency among exposed sessions: 129.8250 s; S2 sessions with any crossing: 0.

## PERSISTENT_OFFSET validation

The approved 3° signed-mean threshold, 180 s trailing mean window and 120 s continuous duration
were evaluated unchanged. Label decisions use only roll samples; heel truth and event t0 appear only
in the evaluation details. S2 qualifying sessions: 5/5; S0b sessions with any persistent phenotype: 0/5; median S2 detection latency: 221.1000 s. These are pilot counts, not stable rate estimates.

## AMPLITUDE_GROWTH candidates

The Train-derived candidate set covers slope, ratio, AND/OR combinations and confirmation durations
of 10/30/60 s. These confirmation values are exploratory grid points, not approved constants.
The selection reference is an independent end-session measured RMS increase check; that reference is
used only to score sessions, never to label earlier timestamps. `h`, sea-state ID and scenario do not
enter the online labeler. Recommended candidate: `growth-04`.
Validation S3 measured-growth detection: 100.0%; S0/S0b session false-growth rate: 0.0%; median detection latency: 145.8250 s.

## Recommended candidate configuration

```json
{
  "calibration_status": "candidate",
  "growth_confirmation_s": 10.0,
  "growth_criterion": "slope",
  "growth_ratio_floor_deg": null,
  "growth_ratio_lag_s": 120.0,
  "growth_ratio_threshold": null,
  "growth_slope_threshold_deg_per_min": 1.769349623333755,
  "growth_window_s": 180.0,
  "high_roll_centered_threshold_deg": 8.40884426,
  "labeling_version": "v2",
  "persistent_offset_duration_s": 120.0,
  "persistent_offset_threshold_deg": 3.0,
  "persistent_offset_window_s": 180.0,
  "threshold_calibration_status": "candidate"
}
```

Validation class distribution (warm-up excluded):

| Class | Windows | Percent |
|---|---:|---:|
| NORMAL | 371455 | 64.49% |
| HIGH_ROLL | 84330 | 14.64% |
| PERSISTENT_OFFSET | 110590 | 19.20% |
| AMPLITUDE_GROWTH | 9595 | 1.67% |

Validation signal summary by scenario (session-level medians; degrees):

| Scenario | Mean roll | RMS about 0 | Centered RMS | P95 abs roll |
|---|---:|---:|---:|---:|
| S0 | 0.027 | 1.061 | 1.061 | 2.062 |
| S0b | 0.190 | 3.688 | 3.683 | 7.574 |
| S1 | -0.133 | 6.585 | 6.583 | 13.760 |
| S2 | 3.987 | 4.877 | 3.403 | 8.856 |
| S3 | 0.046 | 6.336 | 6.335 | 11.694 |
| H1 | 4.252 | 8.943 | 8.011 | 18.405 |

Validation per-scenario label outcome and offset/growth diagnostics are retained in the candidate JSON.
S3 observed end-session RMS-increase reference: 4/5 validation sessions.

Validation median event-relative latency (evaluation only): `{"amplitude_growth": 153.15000000000003, "high_roll": 125.0, "persistent_offset": 218.47500000000002}`.

## Interpretation and limitations

- The 60 sessions form the Train pilot used to derive threshold candidates; 30 Validation sessions rank candidates.
- Five Validation sessions per scenario are too few for stable rate estimates; a follow-up pilot of at least 30 Train and 20 Validation sessions per scenario is recommended before approval.
- Pilot windows overlap in time and are not independent observations. Rates are descriptive; no confidence claim is made from window counts.
- Scenario types represent excitation/offset exposure, not guaranteed observed labels. Failed or unexpected outcomes remain in the report.
- S2 may also show high centered oscillation; phenotype flags preserve overlap while the primary label follows approved priority.
- S3 excitation activation is metadata only. Observed growth is evaluated separately and may not occur.
- No Test-G1/Test-G2, official 605-session dataset, hardware measurement or vessel data were used.
- Candidate requires review of the false detection, latency and per-scenario outcomes before status can change to calibrated.

See `labeling_v2_candidate.json` for all thresholds, session IDs/seeds, candidate scores and per-session diagnostics.
