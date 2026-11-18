# SVMG Candidate Preprocessing Contract — Design Proposal

> **Integration update (18/11/2026):** M1 now implements the [versioned 23-feature contract](../../contracts/features.md). The 30-feature research pipeline and proposal history below remain reference material; they do not mean all 30 inputs are deployed.


> Design only. This document does not implement preprocessing or feature extraction. The active feature contract remains the 14 fields in [`contracts/features.md`](../../contracts/features.md) and [`core/include/svmg_core.h`](../../core/include/svmg_core.h). The proposed 30 candidates are specified in [`feature_specification_30.md`](feature_specification_30.md); availability evidence is in [`feature_availability_matrix.md`](feature_availability_matrix.md) and the [Real Dataset Audit](../audit/real_dataset_audit_report.md).

All choices below are proposals requiring team approval before dataset conversion, model training or C implementation.

## Proposed input record contract

Each raw sensor record should be represented as one source observation with:

| Field | Proposal |
|---|---|
| `session_time_us` | Signed 64-bit monotonic microseconds relative to the start of one session. It is strictly increasing for accepted samples. |
| `source_time` | Preserve original timestamp and encoding separately for auditability: Seafar epoch milliseconds; Southampton source seconds; Hohai sample index plus documented 50 Hz cadence because workbook has no timestamp. |
| `roll_deg`, `pitch_deg` | Canonical angles in degrees after approved sensor-to-body frame and sign mapping. |
| `gyro_x_rad_s`, `gyro_y_rad_s` | Canonical direct measured angular rates in rad/s after axis mapping. Do not synthesize these fields from angle derivatives. Hohai has no direct gyro. |
| `validity` | Per-signal finite/range/sensor validity bits and sample quality status. Invalid values remain invalid; never encode missing as zero. |
| `source_class` | `SENSOR` for real measured observations. A separate `SIMULATION` source is permitted only in simulation work; never mix it silently with these real datasets. |
| `session_id` | Opaque grouping key used for boundaries and train/validation grouping. It is metadata, not an ML input feature. |

Do not put `dataset_name`, source file path, run/sheet ID, session ID, date, wave test condition, or sample index in the 30-value model feature vector. Keep these in a parallel metadata/lineage record.

## Canonical units and frame

Propose roll/pitch in degrees, matching the existing feature document. Propose direct angular velocity in rad/s, matching `MotionSample.gx/gy/gz` in the current C header. Convert Seafar rate values recorded as rad/min to rad/s by division by 60; convert a verified Southampton degree/s rate by multiplying by `pi/180`. Apply conversions only after checking axis identity and sign. Hohai roll/pitch/yaw are documented in degrees; surge/sway/heave are meters. There is no Hohai gyro measurement.

**Frame/sign decisions are pending.** Establish one right-handed body frame and document sensor mounting offsets, positive roll/pitch rotations, and axis permutations for each source. A column called `Delta Angle X` is not automatically accepted as body-x rate solely from its name or units row. Seafar rate fields need provenance/calibration confirmation. Do not infer a direct gyro from numerical differentiation.

## Time representation and sample-rate handling

1. Convert source time into a per-session monotonic time axis. Preserve original values and conversion metadata in sidecar lineage.
2. Do not compare absolute timestamps between datasets or across different experimental runs.
3. Proposed offline common grid: 10 Hz because Seafar was audited at approximately 10 Hz. Hohai and Southampton are documented/measured at 50 Hz. Downsampling 50→10 Hz requires an explicitly chosen causal low-pass anti-alias filter before decimation; the filter and phase/delay convention require approval.
4. Do not upsample Seafar to 50 Hz and treat interpolated values as new measurements. An alternative 50 Hz contract may be preferable for deployment; compare period fidelity and model performance before selecting.
5. Estimate actual cadence from timestamps where available. A fixed 50 Hz Hohai cadence can be assigned from the supplied documentation, but missing timestamps prevent detection of dropped samples within a sheet.
6. Reject non-monotonic timestamps for the affected segment. Seafar duplicates must be resolved by an approved policy (reject affected windows or explicitly defined deduplication); never silently keep the first/last duplicate. Segment at gaps greater than 1.5 times nominal period as an audit starting rule, pending approval.

## Missing-value and invalid-window policy

- Missing, non-finite, sensor-fault, saturated or out-of-range observations remain invalid; do not fill with zero.
- Proposed minimum pointwise coverage is 95% of expected samples: at 10 Hz, at least 570 of 600 for 60 s and 1,710 of 1,800 for 180 s. Validate the threshold against source-specific noise/dropout and safety requirements before approval.
- No feature window may include samples across a detected gap or session boundary. Do not concatenate Seafar segments, Hohai sheets, Southampton runs, or IMU/Lasso records.
- For difference and zero-crossing features, never bridge a missing sample. Require a feature-specific minimum number of adjacent valid sample pairs/cycles.
- Quantile features may be computed over valid observations only if the approved coverage gate passes; retain the valid fraction outside the numeric feature vector.
- If any required signal/window fails a gate, mark that feature invalid with a reason code. Do not fabricate a numeric value to preserve a 30-element row.

## Window boundaries and warmup

Propose trailing window `(t-W,t]` on the canonical grid, session-local, with no future samples. Expected grid counts are 600 (60 s) and 1,800 (180 s) at 10 Hz. Three growth/persistence segments partition the 180 s window into oldest, middle and newest non-overlapping 60 s bins. `early` means oldest bin; `late` means newest bin.

Warmup before a complete valid 60 s window is 60 s; before 180 s features it is 180 s. At startup or after a gap/reset, restart warmup for that session segment. A short-window feature may become valid before long-window features; report per-feature validity rather than blocking the entire model row unless downstream model contract explicitly requires all fields.

For Hohai, the 50 Hz duration supports the window length by sample count (all 21 sheets exceed 180 s), but does not prove continuity. For Southampton, only Run 14 passes 180 s. A 180 s calculation must remain unavailable on other runs; no run concatenation.

## Causal computation and parity

Every candidate is intended to use only current and past samples. Apply identical window boundaries, units, missing-value rules, percentile algorithm (Type 7), variance denominator, zero-crossing interpolation and invalid behavior in Python and C. Use a shared set of golden vectors once implementation is authorized: constant signals, sinusoidal signals, offset signals, edge extrema, duplicate/gap samples, exact zeros, missing samples, and near-zero ratio denominators.

Proposed C numeric representation is `float32`, while offline reference calculations should use `float64`; define per-feature tolerances and compare edge cases before deployment. Use Welford or two-pass variance, protect ratios/period calculations against zero denominators, and clamp only documented round-off excursions. Avoid compiler-dependent undefined behavior and avoid silently returning zero on invalid input.

## Feature-row metadata, outside the ML vector

Store alongside (not inside) the feature vector:

- `feature_spec_version`, `preprocessing_version`, and `model_version`;
- `source_class` (`SENSOR`/`SIMULATION`), `session_id` and opaque source reference;
- window end time, window duration, target/effective sample rate and sample count;
- per-feature validity mask and concise invalid reason code;
- per-signal valid fraction, gap/duplicate flags, and unit/frame mapping version;
- sensor firmware/calibration/configuration version and quality diagnostics.

Dataset identifiers, run identifiers, wave condition and dates are lineage or grouping metadata. Exclude them from model input to prevent leakage and shortcuts.

## Open decisions

1. Approve 10 Hz versus 50 Hz canonical grid and causal anti-alias filter.
2. Approve axis/sign map and rate conversions per dataset/device.
3. Approve coverage, gap, duplicate, saturation and sensor-fault thresholds.
4. Approve invalidity representation between Python training rows and embedded inference.
5. Decide whether all 30 candidates are exploratory offline fields or whether a smaller subset will be considered for the existing ESP32 interface.

