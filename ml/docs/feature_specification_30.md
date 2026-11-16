# SVMG 30 Candidate Feature Specification

> **Status: design proposal only.** The repository's current production-facing feature definition remains the 14-field contract in [`contracts/features.md`](../../contracts/features.md) and `FeatureVector` in [`core/include/svmg_core.h`](../../core/include/svmg_core.h). This document records the exact 30 candidate names supplied for evaluation; it does not approve, implement, or replace the existing contract.

The data limitations referenced below are recorded in the [Real Dataset Audit](../audit/real_dataset_audit_report.md) and its [inventory](../audit/dataset_inventory.json). Every proposed formula and every unresolved convention is `PENDING_TEAM_APPROVAL`.

## Proposed shared conventions

These conventions make the candidate definitions testable and comparable. They are proposals, not established project behavior.

| Item | Proposed definition | Status |
|---|---|---|
| Canonical sample rate | 10 Hz for cross-dataset offline comparison, aligned with Seafar's observed ~10 Hz. Downsample 50 Hz sources only after a causal anti-alias filter. Evaluate a 50 Hz alternative for period fidelity and target MCU RAM before adoption. | `PENDING_TEAM_APPROVAL` |
| Windows | Trailing, session-local windows of 60 s or 180 s. For feature time `t`, use samples whose assigned timestamps are in `(t-W, t]`; no window may cross a session/run boundary. At 10 Hz, target counts are 600 and 1,800 samples respectively. | `PENDING_TEAM_APPROVAL` |
| Validity | Require at least `ceil(0.95 * N_expected)` finite, quality-valid samples (570/600 or 1,710/1,800). No zero fill. No bridging a missing interval for difference/crossing features. A gap over 1.5 times nominal period invalidates the window; short missing samples may be omitted only for pointwise statistics. | `PENDING_TEAM_APPROVAL` |
| Standard deviation | Population standard deviation: `sqrt(sum((x_i - mean)^2) / n)`. A sample estimator with `n-1` is intentionally not mixed in. Use a numerically stable two-pass or Welford implementation. | `PENDING_TEAM_APPROVAL` |
| Percentiles | Type-7 linear interpolation. Sort ascending values `z[0..n-1]`; for quantile `p`, let `h=(n-1)p`, `j=floor(h)`, `g=h-j`; return `z[j] + g*(z[min(j+1,n-1)]-z[j])`. Absolute percentiles first transform each sample to `abs(x_i)`. | `PENDING_TEAM_APPROVAL` |
| Units | Roll/pitch: degrees. Direct body angular rate: rad/s, matching the current C `MotionSample.gx/gy/gz` convention. `roll_diff_rms_60`: degrees/sample at the canonical rate (not an angular velocity). | `PENDING_TEAM_APPROVAL` |
| Invalid output | A candidate that fails its minimum count, has a required zero denominator, has insufficient crossings/periods, or spans an invalid gap is undefined. Keep a validity/status mask outside the numeric feature vector; never substitute zero. | `PENDING_TEAM_APPROVAL` |

The proposed 95% rule is for pointwise statistics. Features that depend on adjacency or crossing times additionally require enough valid adjacent pairs at nominal cadence and may be invalid even when pointwise coverage is at least 95%.

## Feature index and definition register

IDs are zero-based and follow the supplied order exactly. The `#` column is the corresponding one-based position. Each formula below is a candidate mathematical definition requiring approval.

### Group A — Roll Amplitude (60 s)

Let `x_i` be canonical roll samples in degrees, `n` the valid sample count, and `W=60 s`.

| ID / # | Exact feature name | Meaning, input and proposed formula | Units; minimum; method | Invalid / missing; causal; ESP32 cost |
|---:|---|---|---|---|
| 0 / 1 | `roll_rms_60` | Roll amplitude including any offset: `sqrt(sum(x_i^2)/n)`. | Input deg; output deg; `n>=570`; population RMS. | Invalid below coverage/gap rule; omit only allowed isolated missing points. Causal trailing window. O(N) naive / O(1) sum-of-squares state; numeric stability needs bounded/scaled accumulation. `PENDING_TEAM_APPROVAL`. |
| 1 / 2 | `roll_std_60` | Short-term spread around the window mean: population `sqrt(sum((x_i-mean(x))^2)/n)`. | deg → deg; `n>=570`; population, denominator `n`. | Same coverage rule; no fill. Causal. O(N) recompute or O(1) stable rolling moments with periodic rebase. `PENDING_TEAM_APPROVAL`. |
| 2 / 3 | `roll_mean_60` | Signed short-term roll offset: `sum(x_i)/n`. | deg → deg; `n>=570`; arithmetic mean. | Same coverage rule; no fill. Causal. O(N) naive / O(1) rolling sum. `PENDING_TEAM_APPROVAL`. |
| 3 / 4 | `roll_peak_to_peak_60` | Total observed angular excursion: `max(x_i)-min(x_i)`. | deg → deg; `n>=570`; extrema, no estimator. | Invalid if coverage fails; missing samples can hide extrema, so mark result invalid when data-quality policy rejects the window. Causal. O(N) naive / O(1) monotonic deques (up to window size). `PENDING_TEAM_APPROVAL`. |
| 4 / 5 | `roll_abs_p95_60` | High absolute roll amplitude: Type-7 `Q_0.95(abs(x))`. | deg → deg; `n>=570`; Type-7 quantile. | Invalid if coverage fails. Causal. Exact rolling quantile needs O(N) ring plus O(N) scratch/order-statistic structure; higher RAM/CPU than moments. `PENDING_TEAM_APPROVAL`. |
| 5 / 6 | `roll_abs_max_60` | Largest observed absolute roll: `max(abs(x_i))`. | deg → deg; `n>=570`; maximum. | Same as peak-to-peak. Causal. O(N) naive / O(1) monotonic deque. `PENDING_TEAM_APPROVAL`. |
| 6 / 7 | `roll_iqr_60` | Robust central spread: `Q_0.75(x)-Q_0.25(x)` using Type-7 quantiles on signed roll samples. | deg → deg; `n>=570`; Type-7. | Invalid if coverage fails. Causal. Exact rolling quantiles require O(N) buffer/scratch and more CPU. `PENDING_TEAM_APPROVAL`. |
| 7 / 8 | `roll_diff_rms_60` | RMS of consecutive first differences: `sqrt(sum((x_i-x_{i-1})^2)/m)` over `m` valid adjacent pairs separated by one nominal 10 Hz interval. | deg/sample → deg/sample; `m>=ceil(0.95*(N-1))`; population RMS of differences. | Do not bridge missing samples or gaps; invalid if pair count fails. Causal. O(N) naive / O(1) sum-of-squares and previous sample. `PENDING_TEAM_APPROVAL`; not gyro rate. |

### Group B — Roll Angular Velocity (60 s)

Let `g_i` be **directly measured** body-axis roll rate after an approved axis mapping and conversion to rad/s. Differentiated roll angle is not a measured gyroscope signal and does not satisfy this input contract.

| ID / # | Exact feature name | Meaning, input and proposed formula | Units; minimum; method | Invalid / missing; causal; ESP32 cost |
|---:|---|---|---|---|
| 8 / 9 | `gyro_x_rms_60` | Measured angular-rate magnitude: `sqrt(sum(g_i^2)/n)`. | rad/s → rad/s; `n>=570`; population RMS. | Invalid if direct gyro or approved x-axis mapping absent, or coverage fails. No derived-angle substitution. Causal. O(N) naive / O(1) rolling sum of squares. `PENDING_TEAM_APPROVAL`. |
| 9 / 10 | `gyro_x_abs_p95_60` | Type-7 `Q_0.95(abs(g))`. | rad/s → rad/s; `n>=570`; Type-7 quantile. | Same direct gyro requirement. Causal. O(N) ring and scratch for exact quantile. `PENDING_TEAM_APPROVAL`. |
| 10 / 11 | `gyro_x_std_60` | Population spread of direct roll-axis rate: `sqrt(sum((g_i-mean(g))^2)/n)`. | rad/s → rad/s; `n>=570`; population standard deviation. | Same direct gyro requirement. Causal. O(N) naive / O(1) stable rolling moments. `PENDING_TEAM_APPROVAL`. |

### Group C — Persistent Offset (180 s)

Let `x_i` be roll in degrees in the trailing 180 s. For segmented definitions, split the window into three consecutive, non-overlapping, half-open 60 s intervals from oldest to newest; each interval must independently meet its minimum valid sample count.

| ID / # | Exact feature name | Meaning, input and proposed formula | Units; minimum; method | Invalid / missing; causal; ESP32 cost |
|---:|---|---|---|---|
| 11 / 12 | `roll_mean_180` | Long-term signed offset: `sum(x_i)/n`. | deg → deg; `n>=1710`; arithmetic mean. | Invalid if coverage fails; no fill. Causal. O(N) naive / O(1) rolling sum. `PENDING_TEAM_APPROVAL`. |
| 12 / 13 | `roll_median_180` | Robust center: Type-7 `Q_0.50(x)`. | deg → deg; `n>=1710`; Type-7. | Invalid if coverage fails. Causal. Exact rolling quantile uses O(N) ring/scratch and O(N log N) sort if recomputed. `PENDING_TEAM_APPROVAL`. |
| 13 / 14 | `roll_mean_abs_180` | Mean absolute lean magnitude: `sum(abs(x_i))/n`. | deg → deg; `n>=1710`; arithmetic mean. | Invalid if coverage fails. Causal. O(N) naive / O(1) rolling sum of absolute values. `PENDING_TEAM_APPROVAL`. |
| 14 / 15 | `roll_dominant_sign_ratio_180` | Share of non-zero samples with the more frequent sign: `max(n_pos,n_neg)/(n_pos+n_neg)`, where `n_pos=#(x_i>0)`, `n_neg=#(x_i<0)`. Exact zeros are excluded from denominator. | dimensionless `[0,1]`; `n>=1710` and at least one non-zero sample; counts. | Undefined if all values are exactly zero; an engineering deadband would change the definition and is pending separately. Invalid if coverage fails. Causal. O(N) naive / O(1) rolling sign counts plus ring to expire signs. `PENDING_TEAM_APPROVAL`. |
| 15 / 16 | `roll_segment_mean_std_180` | Within-window drift across three 60 s blocks: calculate block means `m_1,m_2,m_3`; output population SD `sqrt(sum((m_j-mean(m))^2)/3)`. | deg → deg; each block `>=570`; population SD over exactly three means. | Invalid if any block fails coverage. Causal. O(N) naive / O(1) per-block sums and rolling segment state. `PENDING_TEAM_APPROVAL`. |
| 16 / 17 | `roll_mean_shift_180` | Net change in mean lean: `mean(last 60 s)-mean(first 60 s)`. The middle block is not used. | deg → deg; first and last block each `>=570`; arithmetic means. | Invalid if either block fails. Causal. O(N) naive / O(1) rolling sums with block boundaries. `PENDING_TEAM_APPROVAL`. |

### Group D — Amplitude Growth (180 s)

Use the same oldest-to-newest three non-overlapping 60 s blocks. Let their RMS values be `r_1,r_2,r_3`, with block-center times `u=[30,90,150]` seconds from the 180 s window start.

| ID / # | Exact feature name | Meaning, input and proposed formula | Units; minimum; method | Invalid / missing; causal; ESP32 cost |
|---:|---|---|---|---|
| 17 / 18 | `roll_rms_early_60` | RMS in the oldest block: `r_1=sqrt(mean(x^2))`. | deg → deg; first block `>=570`; population RMS. | Invalid if first block coverage fails. Causal. O(N) naive / O(1) rolling sum-of-squares. `PENDING_TEAM_APPROVAL`. |
| 18 / 19 | `roll_rms_late_60` | RMS in the newest block: `r_3=sqrt(mean(x^2))`. | deg → deg; last block `>=570`; population RMS. | Invalid if last block coverage fails. Causal. O(N) naive / O(1) rolling sum-of-squares. `PENDING_TEAM_APPROVAL`. |
| 19 / 20 | `roll_rms_ratio_180` | Relative late-vs-early amplitude: `r_3/r_1`. | dimensionless; first/last blocks `>=570`. | Undefined if `r_1<=epsilon_rms`; epsilon must be specified in degrees from sensor noise/resolution. Causal. O(1) after block RMS. `PENDING_TEAM_APPROVAL`. |
| 20 / 21 | `roll_rms_slope_180` | Linear least-squares slope through `(u_j,r_j)`, `j=1..3`: `sum((u_j-u_bar)(r_j-r_bar))/sum((u_j-u_bar)^2)`. | deg/s if `u` uses seconds; proposed output deg/min by multiplying by 60; `>=570` per block. | Invalid if any block fails or time centers are not strictly increasing. Causal. O(1) after block RMS. `PENDING_TEAM_APPROVAL`; denominator and reported time unit must be frozen. |
| 21 / 22 | `roll_rms_trend_r2_180` | Goodness of linear fit to the same three points: `1-SSE/SST`, where `SSE=sum((r_j-(a+b*u_j))^2)` and `SST=sum((r_j-r_bar)^2)`. | dimensionless; `>=570` per block. | Undefined if `SST=0`; proposed clamp only for floating roundoff to `[0,1]`, not to hide bad fits. Causal. O(1) after block RMS. `PENDING_TEAM_APPROVAL`; only three points make this a coarse trend score. |
| 22 / 23 | `roll_p95_trend_slope_180` | Compute Type-7 `Q_0.95(abs(x))` separately in each 60 s block; regress those three values on `[30,90,150]` as above. | deg/s, proposed report deg/min (`slope*60`); `>=570` per block. | Invalid if a block fails; quantile algorithm is Type-7. Causal. O(N) exact quantiles and O(1) regression, with O(N) scratch. `PENDING_TEAM_APPROVAL`. |

### Group E — Oscillation Period (180 s)

Proposal: center samples by the current window mean, `y_i=x_i-mean(x)`, then find sign transitions in chronological order. For a transition bracketed by adjacent valid samples `(t_a,y_a)` and `(t_b,y_b)` with opposite non-zero signs, estimate crossing time by linear interpolation `t_z=t_a-y_a*(t_b-t_a)/(y_b-y_a)`. A run of exact-zero samples counts as one crossing at the midpoint of the first and last zero timestamps only when the nearest valid non-zero values on both sides have opposite signs and no missing/gap interval is involved; same-sign values on both sides count no crossing. Do not bridge gaps. This detector is a candidate convention and can be sensitive to noise and multi-frequency motion.

| ID / # | Exact feature name | Meaning, input and proposed formula | Units; minimum; method | Invalid / missing; causal; ESP32 cost |
|---:|---|---|---|---|
| 23 / 24 | `roll_period_est_180` | Median interval between consecutive **upward** interpolated zero crossings; require at least 3 upward crossings (2 complete periods). | seconds; 180 s; median of Type-7 period quantiles (`Q_0.50`). | Undefined below crossing count, when crossing pairs span missing/gapped samples, or if mean-centering is rejected. Causal trailing window. O(N) scan; storing crossing times O(K), or stream interval state plus O(K) scratch for exact median. `PENDING_TEAM_APPROVAL`. |
| 24 / 25 | `roll_zero_crossings_180` | Count all interpolated sign transitions (upward and downward) of `y_i` in 180 s under the detector above. Count is not normalized by duration. | count; 180 s; integer accumulation. | A window with no transitions yields 0 if otherwise valid; invalid coverage/gaps yield undefined. Causal. O(N) scan / O(1) state. `PENDING_TEAM_APPROVAL`; mean-centering and exact-zero handling require approval. |
| 25 / 26 | `roll_period_cv_180` | For upward crossing times, form successive periods `P_k=t_{k+1}-t_k`; output population `SD(P_k)/mean(P_k)`. Require at least 3 periods (4 upward crossings). | dimensionless; 180 s; population SD over period estimates. | Undefined with fewer than 3 periods or non-positive mean period; invalid if adjacency/gap rules fail. Causal. O(N) scan plus O(K) interval storage/scratch for exact population CV. `PENDING_TEAM_APPROVAL`. |

### Group F — Pitch (60 s)

Let `p_i` be pitch in degrees. Direct gyro y input means directly measured body-axis pitch angular velocity in rad/s after approved sensor-to-body mapping.

| ID / # | Exact feature name | Meaning, input and proposed formula | Units; minimum; method | Invalid / missing; causal; ESP32 cost |
|---:|---|---|---|---|
| 26 / 27 | `pitch_rms_60` | Pitch amplitude including offset: `sqrt(sum(p_i^2)/n)`. | deg → deg; `n>=570`; population RMS. | Invalid if coverage/gap fails; no fill. Causal. O(N) naive / O(1) rolling sum of squares. `PENDING_TEAM_APPROVAL`. |
| 27 / 28 | `pitch_std_60` | Population spread: `sqrt(sum((p_i-mean(p))^2)/n)`. | deg → deg; `n>=570`; denominator `n`. | Invalid if coverage fails. Causal. O(N) naive / O(1) stable rolling moments. `PENDING_TEAM_APPROVAL`. |
| 28 / 29 | `pitch_peak_to_peak_60` | Excursion `max(p_i)-min(p_i)`. | deg → deg; `n>=570`; extrema. | Invalid if coverage fails; missing samples may hide extrema. Causal. O(N) naive / O(1) monotonic deques. `PENDING_TEAM_APPROVAL`. |
| 29 / 30 | `gyro_y_rms_60` | RMS magnitude of directly measured body pitch angular rate: `sqrt(sum(g_y_i^2)/n)`. | rad/s → rad/s; `n>=570`; population RMS. | Invalid if direct gyro y or approved axis mapping absent. Do not differentiate pitch as a substitute. Causal. O(N) naive / O(1) rolling sum-of-squares. `PENDING_TEAM_APPROVAL`. |

## Pending decisions before implementation

1. Approve canonical rate units and body-axis/sign transformation for each source/sensor.
2. Approve 10 Hz canonical resampling versus retaining 50 Hz, including anti-alias filter and period bandwidth requirements.
3. Approve 95% valid coverage, gap threshold and whether candidate validity is feature-specific or window-wide.
4. Approve exact-zero/deadband behavior for sign features; no deadband is silently assumed here.
5. Approve mean-centering, crossing interpolation, minimum cycle count, period median and CV estimator.
6. Approve three 60 s partitions, first-vs-last mean shift, ratio denominator/epsilon, trend time unit and three-point R² behavior.
7. Select a tested subset before adding any field to the 14-feature C contract. Candidate count 30 is not an ESP32 deployment decision.

## Embedded compatibility estimate (proposal)

At a proposed 10 Hz grid, a 180 s ring holds 1,800 values per channel. Four float32 channels (`roll`, `pitch`, direct gyro x/y) require about **28.8 kB** (`4 * 1,800 * 4`), before validity metadata, alignment, stack, allocator and other firmware use. One reusable 1,800-float scratch array for exact quantiles adds **7.2 kB**; a 1,800-entry float crossing/period workspace adds at most another **7.2 kB** if exact order statistics are retained. If per-sample 64-bit timestamps are stored, add **14.4 kB**. At 50 Hz the equivalent four-channel ring is **144 kB**, with 36 kB for one 9,000-float scratch array. The 30 float32 output values themselves need only **120 bytes**, plus validity bits, but buffer/workspace dominates.

Constant-memory candidates (means, RMS, population std, extrema, adjacent difference and segment moments) are suitable for rolling accumulators/deques. Exact rolling Type-7 percentiles/IQR and exact median period require scratch/order-statistic work; recomputing/sorting all values at every 10 Hz tick may be wasteful. A candidate implementation should benchmark a one-second feature update cadence and an efficient rolling quantile strategy on the actual ESP32 target. These estimates do not prove fit: available internal RAM, Wi-Fi/MQTT load, stack high-water mark, target clock and compiler must be measured. Float32 parity needs golden-vector tolerances against a float64 Python reference.

