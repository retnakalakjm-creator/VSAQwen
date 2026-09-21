# M12 / L9 — NO_SUPPLY Confirmation-Stratified Matched Outcomes

## Purpose

L8 showed that the NO_SUPPLY common signature underperformed nearby matched
bearish controls in both trend environments.

L9 asks whether that weakness is caused by the current detector treating its
confirmations as non-gating.

L9 performs no new market-data, Metrics, Swing, Structure, Trend, or detector
replay.

It reuses:

1. canonical L6 confirmation observations;
2. canonical L8 matched controls;
3. canonical L8 matched pair outcomes.

L9 remains audit-only and non-actionable.

## Source populations

Canonical L8 target populations:

    CURRENT / DOWN targets      777
    ALTERNATE / UP targets    1,732
    total targets             2,509

Canonical L6 common-signature population:

    3,584

Only the 2,509 targets that belong to one of the two L6 environment candidates
are analyzed in L9.

## Confirmation contract

Production NO_SUPPLY currently exposes three confirmations:

    Weak Spread
    Volume Decreasing
    Weak Selling Result

L6 established that Weak Spread is redundant with mandatory Narrow Spread.

L9 therefore hard-validates:

    Weak Spread passed on every one of the 2,509 targets

If that invariant is violated, L9 stops.

The two meaningful confirmations are:

    Volume Decreasing
    Weak Selling Result

## Mutually exclusive strata

Every target is assigned to exactly one stratum:

    NEITHER
        Volume Decreasing = false
        Weak Selling Result = false

    VOLUME_ONLY
        Volume Decreasing = true
        Weak Selling Result = false

    WEAK_RESULT_ONLY
        Volume Decreasing = false
        Weak Selling Result = true

    BOTH
        Volume Decreasing = true
        Weak Selling Result = true

Within each environment cohort, these four strata must partition the source
target count exactly.

## Projected gate candidates

L9 also evaluates the three practical confirmation gates directly:

    VOLUME_DECREASING
        VOLUME_ONLY + BOTH

    WEAK_SELLING_RESULT
        WEAK_RESULT_ONLY + BOTH

    BOTH
        BOTH only

These gate projections are descriptive counterfactual slices of the existing
matched outcome ledger.

They do not change production emission behavior.

## Lineage

L9 binds to exact hashes for:

- L8 summary;
- L8 controls;
- L8 pair outcomes;
- L8 censoring summary;
- L8 outcome summary;
- L6 summary;
- L6 observations;
- inherited L7 summary/outcomes;
- frozen snapshot manifest.

L9 also validates:

    requested symbols = 30
    L8 source targets = 2,509
    CURRENT targets = 777
    ALTERNATE targets = 1,732
    matched targets = 2,509
    unmatched targets = 0
    match rate = 1.0
    pair outcome rows = 12,539
    L6 common signature count = 3,584

Every L8 target must map to exactly one L6 confirmation observation with the
same:

    symbol
    session
    bar index
    trend direction
    environment candidate identity

## Outcome semantics

L9 reuses L8's paired sign convention:

    TARGET - CONTROL

Positive return delta means the NO_SUPPLY common-signature target had a higher
forward return than its same-symbol, same-environment matched bearish control.

Positive MAE delta means less adverse excursion because MAE values are <= 0.

Default horizons:

    1
    3
    5
    10
    20

L9 does not recalculate censoring or price-discontinuity status.

It reuses each L8 pair's:

    clean_pair

flag exactly.

## Outcome summaries

For every non-empty cohort/stratum/horizon and cohort/gate/horizon L9 reports:

    source target count
    complete pair count
    clean pair count
    symbol count
    clean symbol count

    raw mean paired return delta
    raw median paired return delta
    raw positive-close-rate delta
    raw mean paired MFE delta
    raw mean paired MAE delta

    clean mean paired return delta
    clean median paired return delta
    clean positive-close-rate delta
    clean mean paired MFE delta
    clean mean paired MAE delta

    clean symbol-normalized return delta
    clean positive / negative / zero return-symbol counts
    clean symbol-normalized positive-close-rate delta
    clean symbol-normalized MFE delta
    clean symbol-normalized MAE delta

A segment with source targets but zero clean pairs remains visible in the count
ledger but is omitted from outcome summaries rather than emitting NaN clean
statistics.

## Count ledgers

The stratum-count ledger is mutually exclusive.

Expected row count:

    2 cohorts x 4 strata = 8

The gate-count ledger is intentionally overlapping.

Expected row count:

    2 cohorts x 3 gates = 6

The number of targets passing a meaningful confirmation is measured by L9 and
is not predeclared.

## Expected fixed invariants

    requested_symbol_count             30
    source_target_count              2509
    current_source_target_count        777
    alternate_source_target_count     1732
    weak_spread_target_count          2509
    horizon_count                        5
    horizons                      1,3,5,10,20
    stratum_count_row_count              8
    gate_count_row_count                 6
    is_actionable                     false

Stratum/gate target counts and outcome-row counts are measured results.

## Outputs

    daily_no_supply_confirmation_strata_summary.json
    daily_no_supply_confirmation_targets.csv
    daily_no_supply_confirmation_stratum_counts.csv
    daily_no_supply_confirmation_gate_counts.csv
    daily_no_supply_confirmation_stratum_outcomes.csv
    daily_no_supply_confirmation_gate_outcomes.csv
    daily_no_supply_confirmation_stratum_symbol_outcomes.csv
    daily_no_supply_confirmation_gate_symbol_outcomes.csv

## Performance

L9 performs only:

    CSV/JSON loading
    exact lineage validation
    target-to-confirmation identity join
    group aggregation

No multiprocessing or checkpoints are required.

## Local validation

    python -m ruff check audit/daily_event_no_supply_confirmation_strata.py scripts/audit_daily_event_no_supply_confirmation_strata.py tests/test_daily_event_no_supply_confirmation_strata.py

    python -m pytest -q tests/test_daily_event_no_supply_confirmation_strata.py tests/test_daily_event_no_supply_matched_environment.py

## Canonical run

    python scripts/audit_daily_event_no_supply_confirmation_strata.py --matched-dir reports\daily-events\no-supply-matched-environment\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --replay-dir reports\daily-events\no-supply-environment-replay\milestone6_standard_india_large_cap_30_frozen_2026-09-18

## Interpretation

The key question is not whether a confirmation subset merely has positive raw
returns.

The stronger question is:

    does the confirmation-defined subset show positive matched lift
    versus same-symbol, same-environment bearish controls?

Evidence is more persuasive when:

- clean event-weighted return delta is positive;
- clean symbol-normalized return delta is positive;
- positive-close-rate delta is positive;
- MFE/MAE behavior is not materially contradictory;
- the direction is reasonably broad across symbols;
- the target population is large enough to be credible.

No single L9 result automatically becomes a production gate.

## Safety

L9 changes no:

- NO_SUPPLY mandatory requirements;
- environment predicate;
- confirmation gating;
- evidence weights;
- scoring/ranking;
- DailyBehavior;
- qualification/actionability;
- API behavior;
- alerts/orders;
- production data loading.
