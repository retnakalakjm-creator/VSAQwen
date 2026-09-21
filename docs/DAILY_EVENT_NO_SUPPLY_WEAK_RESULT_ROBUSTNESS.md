# M12 / L10 — NO_SUPPLY WEAK_RESULT_ONLY Robustness and Semantics

## Purpose

L9 isolated one confirmation stratum with materially different matched behavior:

    WEAK_RESULT_ONLY

Canonical population:

    CURRENT / DOWN      122
    ALTERNATE / UP      305
    total               427
    symbols              30

L10 does not change production behavior.

It asks two questions:

1. Is the observed matched lift robust to symbol-level dependence and single-symbol influence?
2. What does the source predicate actually mean, independent of the human-facing confirmation label?

## Candidate contract

The L9 stratum is:

    Weak Selling Result = true
    Volume Decreasing   = false

Production source semantics are:

    Weak Selling Result
        -> is_weak_close(bar)

    is_weak_close(bar)
        -> close_position in {LOWER, ON_LOW}

    Volume Decreasing
        -> current.volume < previous.volume

Here `BarContext.volume` is a `VolumeClass` enum, not raw volume.

Therefore:

    NOT Volume Decreasing
        -> current VolumeClass ordinal
           >= previous VolumeClass ordinal

The mandatory NO_SUPPLY requirements still include:

    Bearish Bar
    Low Volume
    Narrow Spread

So the empirical L10 candidate is more precisely described as:

    bearish bar
    AND low volume relative to the production volume baseline
    AND narrow spread
    AND close in LOWER or ON_LOW position
    AND current volume classification is not lower than
        the previous bar's volume classification

This must not be interpreted as a raw-volume comparison.

For example, the current raw volume may be lower than the previous bar while
both bars still classify into the same volume bucket, or while the current bar
has a higher ordinal volume class because classifications are based on the
production rolling/percentile context.

## Why the label needs care

The source label:

    Weak Selling Result

does not compute an effort/result relation.

It computes:

    is_weak_close(bar)

That is a close-position predicate.

L10 therefore reports source semantics directly and does not treat the label as
a validated conceptual definition.

## Source lineage

L10 consumes:

1. canonical L9 summary;
2. canonical L9 target ledger;
3. canonical L9 stratum counts;
4. canonical L9 stratum outcomes;
5. canonical L9 stratum symbol outcomes;
6. canonical L8 summary;
7. canonical L8 matched pair outcomes.

It validates exact L9 -> L8 lineage hashes.

Canonical hard gates:

    L9 source targets                 2,509
    Weak Spread passed               2,509
    L8 matched targets               2,509
    L8 unmatched targets                 0
    L8 pair outcome rows            12,539

Candidate hard gates:

    WEAK_RESULT_ONLY total              427
    CURRENT / DOWN                      122
    ALTERNATE / UP                      305
    symbols                              30

Every candidate pair row must preserve the target's:

    symbol
    session
    cohort
    trend direction
    bar index

## Clean-pair semantics

L10 reuses L8's existing:

    clean_pair

flag exactly.

No price-discontinuity calculation is recomputed.

For each cohort and horizon, only clean pairs enter:

- robustness summaries;
- bootstrap distributions;
- leave-one-symbol-out estimates.

Raw candidate identities remain unchanged.

## Estimands

L10 reports two estimands separately.

### EVENT_WEIGHTED

All clean candidate/control pairs contribute equally.

A symbol with more candidate events therefore has more weight.

### SYMBOL_NORMALIZED

L10 first computes each symbol's mean paired delta and then averages symbols
equally.

This protects interpretation from event-frequency concentration.

Neither estimand replaces the other.

Agreement between them is stronger evidence than either alone.

## Metrics

The paired sign convention remains:

    TARGET - CONTROL

L10 bootstraps four metrics:

    PAIRED_RETURN_DELTA_PCT
    POSITIVE_CLOSE_RATE_DELTA
    PAIRED_MFE_DELTA_PCT
    PAIRED_MAE_DELTA_PCT

For MAE, positive remains favorable because MAE values are <= 0:

    positive paired MAE delta
        -> candidate target had less adverse excursion than control

## Symbol-clustered bootstrap

Default:

    iterations = 10,000
    seed       = 20260921

For each:

    cohort
    horizon

L10 treats each symbol as one resampling cluster.

A bootstrap replicate:

1. samples 30 symbols with replacement;
2. includes all clean candidate/control pairs belonging to each sampled symbol;
3. preserves within-symbol event dependence;
4. computes EVENT_WEIGHTED and SYMBOL_NORMALIZED estimands separately.

L10 reports:

    observed value
    bootstrap mean
    2.5th percentile
    97.5th percentile
    bootstrap_fraction_gt_zero
    bootstrap_fraction_lt_zero
    ci_excludes_zero

The fraction-above-zero fields are bootstrap resampling diagnostics.

They are not Bayesian posterior probabilities.

## Bootstrap limitations

Symbol clustering addresses dependence among events from the same symbol.

It does not fully model:

- dependence across symbols from the same market regime;
- time-series autocorrelation shared across the basket;
- selection uncertainty from discovering WEAK_RESULT_ONLY in L9;
- multiple-horizon / multiple-metric multiplicity;
- unmatched latent state such as volatility or campaign context.

Therefore a 95% interval excluding zero is evidence of robustness within this
audit design, not proof of a production edge.

## Leave-one-symbol-out robustness

For each cohort/horizon L10 also recomputes return lift after removing one
symbol at a time.

It reports:

    full return delta
    minimum leave-one-out delta
    symbol producing minimum
    maximum leave-one-out delta
    symbol producing maximum
    largest absolute shift
    symbol producing largest shift
    positive / negative / zero leave-one-out counts

for both:

    EVENT_WEIGHTED
    SYMBOL_NORMALIZED

A candidate whose sign flips after removing one symbol is less robust than one
whose sign remains stable across all 30 removals.

## Direct semantic truth table

L10 imports the production functions directly.

For:

    is_weak_close

it evaluates every ClosePosition:

    ON_LOW
    LOWER
    MIDDLE
    UPPER
    ON_HIGH

Expected truth:

    ON_LOW    true
    LOWER     true
    MIDDLE    false
    UPPER     false
    ON_HIGH   false

For:

    NOT volume_decreasing

using previous VolumeClass = VERY_LOW:

    current ULTRA_LOW    false
    current VERY_LOW     true
    current LOW          true

This validates the production VolumeClass ordinal comparison. It does not
assert anything about raw-volume equality or increase.

Any source-level semantic drift causes L10 to fail.

## Expected fixed output counts

With default horizons:

    requested_symbol_count              30
    candidate_target_count             427
    current_candidate_target_count     122
    alternate_candidate_target_count   305
    horizon_count                        5
    robustness_row_count                10

Bootstrap rows:

    2 cohorts
    x 5 horizons
    x 4 metrics
    x 2 estimands
    = 80

Leave-one-symbol-out rows:

    2 cohorts
    x 5 horizons
    x 2 estimands
    = 20

Semantic rows:

    5 close-position states
    + 3 volume-relation states
    = 8

    is_actionable = false

## Outputs

    daily_no_supply_weak_result_robustness_summary.json
    daily_no_supply_weak_result_candidate_targets.csv
    daily_no_supply_weak_result_robustness.csv
    daily_no_supply_weak_result_cluster_bootstrap.csv
    daily_no_supply_weak_result_leave_one_symbol_out.csv
    daily_no_supply_weak_result_semantics.csv

## Local validation

    python -m ruff check audit/daily_event_no_supply_weak_result_robustness.py scripts/audit_daily_event_no_supply_weak_result_robustness.py tests/test_daily_event_no_supply_weak_result_robustness.py

    python -m pytest -q tests/test_daily_event_no_supply_weak_result_robustness.py tests/test_daily_event_no_supply_confirmation_strata.py

## Canonical run

    python scripts/audit_daily_event_no_supply_weak_result_robustness.py --confirmation-dir reports\daily-events\no-supply-confirmation-strata\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --matched-dir reports\daily-events\no-supply-matched-environment\milestone6_standard_india_large_cap_30_frozen_2026-09-18

## Interpretation

The most persuasive robustness pattern would be:

- event-weighted return lift > 0;
- symbol-normalized return lift > 0;
- 95% symbol-clustered intervals mostly or fully above zero;
- high bootstrap fraction above zero;
- leave-one-symbol-out return sign remains positive;
- MFE supports the return result;
- MAE is not materially adverse;
- behavior is not isolated to only one environment or horizon.

A mixed result should remain research evidence.

## Safety

L10 changes no:

- NO_SUPPLY production requirements;
- environment predicate;
- confirmation labels;
- confirmation gating;
- evidence weights;
- scoring/ranking;
- DailyBehavior;
- qualification/actionability;
- API behavior;
- alerts/orders;
- production data loading.
