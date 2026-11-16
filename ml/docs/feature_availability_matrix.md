# Candidate Feature Availability Matrix

> This matrix evaluates the exact 30 candidate names in [`feature_specification_30.md`](feature_specification_30.md). It does not change the current 14-feature contract. Signal availability is separated from approval of a feature formula; formulas remain proposals.

Dataset evidence is from the [Real Dataset Audit report](../audit/real_dataset_audit_report.md) and [inventory](../audit/dataset_inventory.json).

## Status meanings

- **AVAILABLE**: required raw signal and enough audited session duration exist for at least one window. Scope limits are stated (for example, only Southampton Run 14 supports a 180 s window).
- **DERIVABLE_WITH_ASSUMPTIONS**: raw signal exists, but source quality, timing, units, axis semantics, resampling or the proposed algorithm requires confirmation.
- **UNAVAILABLE**: a required measured input is absent. Derivatives of angles do not count as measured gyro data.

Status describes data support, not final model approval. For example, `roll_period_est_180` remains `DERIVABLE_WITH_ASSUMPTIONS` because its estimator is pending even where roll samples exist.

## Source evidence and rationale codes

| Code | Evidence / limitation |
|---|---|
| S60 | Seafar has roll/pitch in degrees and ~10 Hz timestamps; duplicate timestamps and 17 detected gaps leave 7 continuous segments eligible for 60 s. A timestamp-aware, gap-safe window policy is required. |
| S180 | Seafar has 4 continuous segments eligible for 180 s, with the same duplicate/gap handling requirement. Never cross segment/session boundaries. |
| SG | Seafar has `roll_rate_rad_min` directly in the file; unit provenance/calibration and body-x mapping need confirmation. Convert units only under an approved contract. |
| H60 | Hohai provides roll/pitch; the supplied documentation metadata states 50 Hz and degrees; all 21 sheets have enough duration for 60 s. Workbook has no timestamps, so per-sample continuity/dropout cannot be verified. Each sheet remains a separate session. |
| H180 | Same Hohai evidence as H60; all 21 sheets have duration for 180 s by sample count and documented rate, but no timestamp-level gap check. |
| HG | Hohai contains no directly measured gyroscope columns. Angle differentiation is not a substitute. |
| T60 | Southampton has timestamped Roll/Pitch in degrees; all 47 IMU runs are at least 60 s and the audit found no timestamp gaps or missing values. Per-run boundaries remain hard boundaries. |
| T180 | Southampton has only one run (Run 14) long enough for 180 s. Long-window features are therefore available only for that session; do not stitch runs. |
| TG | Southampton has `Delta Angle X/Y`, whose units row says degree/s. Column naming and body-axis/sign/measurement semantics still need confirmation; status remains assumption-dependent. |
| ALG | Feature algorithm itself has unresolved choices (e.g. deadband, exact-zero handling, period estimator, trend definition), even when signal and time support exist. |

For Seafar, rates use the file's rad/min field; Southampton's rate unit row says degree/s. The unit and axis conversions must not be conflated. Hohai's documented units are roll/pitch/yaw degree and surge/sway/heave meter, but it has no gyro.

## Per-feature matrix

| ID | Feature | Window | Seafar | Hohai | Southampton | Rationale |
|---:|---|---:|---|---|---|---|
| 0 | `roll_rms_60` | 60 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S60; H60; T60 |
| 1 | `roll_std_60` | 60 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S60; H60; T60 |
| 2 | `roll_mean_60` | 60 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S60; H60; T60 |
| 3 | `roll_peak_to_peak_60` | 60 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S60; H60; T60 |
| 4 | `roll_abs_p95_60` | 60 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S60; H60; T60; exact quantile convention pending |
| 5 | `roll_abs_max_60` | 60 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S60; H60; T60 |
| 6 | `roll_iqr_60` | 60 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S60; H60; T60; exact quantile convention pending |
| 7 | `roll_diff_rms_60` | 60 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S60; H60; T60; do not bridge invalid adjacent samples; this is not gyro |
| 8 | `gyro_x_rms_60` | 60 s | DERIVABLE_WITH_ASSUMPTIONS | UNAVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | SG; HG; TG |
| 9 | `gyro_x_abs_p95_60` | 60 s | DERIVABLE_WITH_ASSUMPTIONS | UNAVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | SG; HG; TG; exact quantile convention pending |
| 10 | `gyro_x_std_60` | 60 s | DERIVABLE_WITH_ASSUMPTIONS | UNAVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | SG; HG; TG |
| 11 | `roll_mean_180` | 180 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S180; H180; T180 (Run 14 only) |
| 12 | `roll_median_180` | 180 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S180; H180; T180 (Run 14 only); quantile convention pending |
| 13 | `roll_mean_abs_180` | 180 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S180; H180; T180 (Run 14 only) |
| 14 | `roll_dominant_sign_ratio_180` | 180 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | S180; H180; T180; zero/deadband convention pending (`ALG`) |
| 15 | `roll_segment_mean_std_180` | 180 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S180; H180; T180 (Run 14 only); partition definition pending |
| 16 | `roll_mean_shift_180` | 180 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S180; H180; T180 (Run 14 only); first/last block choice pending |
| 17 | `roll_rms_early_60` | 180 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S180; H180; T180 (Run 14 only) |
| 18 | `roll_rms_late_60` | 180 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S180; H180; T180 (Run 14 only) |
| 19 | `roll_rms_ratio_180` | 180 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | S180; H180; T180; denominator epsilon pending (`ALG`) |
| 20 | `roll_rms_slope_180` | 180 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S180; H180; T180 (Run 14 only); slope unit/partition pending |
| 21 | `roll_rms_trend_r2_180` | 180 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | S180; H180; T180; three-point fit and constant-series behavior pending (`ALG`) |
| 22 | `roll_p95_trend_slope_180` | 180 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S180; H180; T180 (Run 14 only); quantile/trend method pending |
| 23 | `roll_period_est_180` | 180 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | S180; H180; T180; estimator/crossing behavior pending (`ALG`) |
| 24 | `roll_zero_crossings_180` | 180 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | S180; H180; T180; centering/exact-zero rules pending (`ALG`) |
| 25 | `roll_period_cv_180` | 180 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | S180; H180; T180; period estimator and minimum cycles pending (`ALG`) |
| 26 | `pitch_rms_60` | 60 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S60; H60; T60 |
| 27 | `pitch_std_60` | 60 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S60; H60; T60 |
| 28 | `pitch_peak_to_peak_60` | 60 s | DERIVABLE_WITH_ASSUMPTIONS | DERIVABLE_WITH_ASSUMPTIONS | AVAILABLE | S60; H60; T60 |
| 29 | `gyro_y_rms_60` | 60 s | DERIVABLE_WITH_ASSUMPTIONS | UNAVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | Seafar pitch-rate field/unit/mapping needs confirmation; HG; TG |

## Status totals across the 30 candidates

| Dataset | AVAILABLE | DERIVABLE_WITH_ASSUMPTIONS | UNAVAILABLE | Interpretation |
|---|---:|---:|---:|---|
| Seafar | 0 | 30 | 0 | Candidate signals appear in file; gap/duplicate handling, rate calibration and candidate definitions still require decisions. There are 7 audited uninterrupted 60 s segments and 4 180 s segments. |
| Hohai | 0 | 26 | 4 | Roll/pitch windows have documented 50 Hz and units, and 21 sheets have sufficient duration, but no timestamps to verify dropout. The four gyro candidates are unavailable because no measured gyro columns exist. |
| Southampton | 20 | 10 | 0 | 60 s angle and pitch features are supported across 47 runs. 180 s signal features are limited to Run 14. Rate, sign-ratio, ratio/trend-R² and period candidates remain assumption-dependent because semantics/algorithms need approval. |

Counts use a per-feature status, not a count of sessions or feature windows. `AVAILABLE` does not mean statistically validated or approved for the model. No run or sheet is concatenated to make a longer window.

