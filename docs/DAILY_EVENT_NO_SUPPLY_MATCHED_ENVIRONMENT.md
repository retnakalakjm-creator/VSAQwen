# M12 / L8 — NO_SUPPLY Matched Same-Environment Outcomes

## Purpose

L7 showed that comparing the current and alternate NO_SUPPLY populations is
confounded by trend direction:

    CURRENT   -> DOWN environment
    ALTERNATE -> UP environment

L8 therefore holds trend direction constant.

For every canonical L6 target, L8 finds a nearby control bar that is:

- the same symbol;
- the same trend direction;
- a bearish bar;
- not an L6 NO_SUPPLY common-signature bar;
- within a bounded completed-session distance;
- not reused for another target.

L8 then compares forward outcomes pair by pair.

L8 is audit-only and non-actionable.

## What L8 estimates

The L6 common signature is:

    Bearish Bar
    Low Volume
    Narrow Spread

Because L8 controls are bearish bars without that common signature, the paired
comparison estimates the descriptive incremental association of:

    Low Volume + Narrow Spread

on a bearish bar after conditioning on:

    symbol
    trend direction
    temporal proximity

It does not isolate Low Volume and Narrow Spread separately.

## What L8 does not establish

L8 is not a causal treatment estimate.

Residual differences can remain in:

- trend state;
- volatility;
- campaign/background state;
- price level;
- market regime;
- other evidence active on the same bar.

A positive or negative matched delta is evidence for further semantic review,
not a production rule by itself.

## Canonical source chain

L8 consumes:

1. canonical L7 summary;
2. canonical L7 event-outcome ledger;
3. canonical L7 cohort-comparison ledger;
4. canonical L7 data-quality ledger;
5. canonical L6 summary;
6. canonical L6 observation ledger;
7. the canonical frozen daily input bundle.

It validates exact L7 -> L6 lineage and snapshot manifest identity.

Expected full source populations:

    common-signature bars          3,584
    target bars                    2,509
    CURRENT / DOWN targets           777
    ALTERNATE / UP targets         1,732

The 1,075 RANGE/UNKNOWN common-signature bars remain excluded from the target
population because they are not part of either L6 environment candidate.

## Control contract

For a target T, candidate controls are searched in increasing absolute session
distance:

    distance 1
    distance 2
    ...
    distance 60

At equal distance, the prior session is considered before the later session.

Default maximum distance:

    60 completed sessions

A candidate is eligible only when:

    candidate index >= canonical daily replay minimum index
    raw close < raw open
    candidate session is not any L6 common-signature session
    candidate has not already been used
    replayed trend direction == target trend direction

Controls are 1:1 and without replacement within each symbol.

The matching rule deliberately does not require Low Volume or Narrow Spread,
because matching on those attributes would remove the pattern whose incremental
association L8 is trying to measure.

## Exact environment replay

Candidate environment is not inferred from nearby target events.

For each candidate that must be checked, L8 reconstructs the exact causal
prefix:

    frozen L6-equivalent daily prefix
      -> MetricsEngine
      -> SwingEngine
      -> StructureFilter
      -> TrendAnalyzer

and reads:

    trend.structure.direction

This is exactly the environment dimension used by:

    BackgroundContext.is_bearish_environment()
    BackgroundContext.is_bullish_environment()

Candidate directions are memoized inside each symbol so repeated candidate
checks do not replay the same prefix twice.

## Checkpoint / resume

Per-symbol control discovery is checkpointed atomically.

The checkpoint signature includes:

- complete L6/L7/snapshot lineage;
- matching contract version;
- max match distance;
- minimum replay target index.

Resume is enabled by default.

A changed lineage or matching configuration invalidates old checkpoints.

## Target outcomes

L8 does not recalculate target outcomes.

It reuses the exact canonical L7 target outcome rows, preserving:

- 1 / 3 / 5 / 10 / 20 session horizons;
- L6-equivalent calendar filtering;
- cutoff censoring;
- 35% price-discontinuity screening.

## Control outcomes

Control outcomes use the same definitions as L7:

    forward close return
    MFE
    MAE
    positive close
    max single-session OHLC move

Control windows use the same 35% discontinuity threshold.

A matched pair is clean only when:

    target window is clean
    AND
    control window is clean

Raw pair outcomes are still retained.

## Paired deltas

The sign convention is always:

    TARGET - CONTROL

Therefore:

    positive return delta
        target common-signature bar had higher forward return

    positive positive-close-rate delta
        target common-signature bars closed positive more often

    positive MFE delta
        target common-signature bars achieved more favorable excursion

    positive MAE delta
        target common-signature bars had less adverse excursion
        because MAE values are <= 0

## Summary views

For each environment cohort and horizon L8 reports:

### Raw paired view

    target mean return
    control mean return
    paired mean / median return delta
    target/control positive-close rate
    positive-close-rate delta
    target/control MFE and MAE
    paired MFE / MAE delta

### Clean paired view

The same measures after removing only pairs where either target or control
window crosses a flagged price discontinuity.

### Symbol-normalized clean view

L8 first computes each symbol's mean paired delta and then averages symbols
equally for:

    return delta
    positive-close-rate delta
    MFE delta
    MAE delta

## Match quality

Per symbol:

    source target count
    matched target count
    unmatched target count
    candidate environment replay count
    environment cache hit count
    used control count

Canonical interpretation should consider:

    overall match rate
    cohort-specific match rate
    match distance distribution
    per-symbol coverage

before interpreting outcome deltas.

## Three-symbol smoke

Recommended first smoke:

    LT.NS
    SRF.NS
    ADANIPORTS.NS

Known source counts from canonical L6:

    CURRENT targets       73
    ALTERNATE targets    167
    total targets        240
    common signature     354

The matched count is intentionally unknown before L8 runs.

## Expected full source invariants

    requested_symbol_count           30
    source_target_count            2509
    current_source_target_count      777
    alternate_source_target_count   1732
    common_signature_count          3584
    horizon_count                      5
    horizons                    1,3,5,10,20
    max_match_distance_sessions       60
    price_discontinuity_ratio        0.35
    is_actionable                   false

Matched/unmatched counts and pair-outcome row counts are measured results, not
predeclared expectations.

## Outputs

    daily_no_supply_matched_summary.json
    daily_no_supply_matched_controls.csv
    daily_no_supply_matched_unmatched.csv
    daily_no_supply_matched_symbols.csv
    daily_no_supply_matched_pair_outcomes.csv
    daily_no_supply_matched_censoring.csv
    daily_no_supply_matched_outcome_summary.csv
    daily_no_supply_matched_symbol_outcomes.csv

## Local validation

    python -m ruff check audit/daily_event_no_supply_matched_environment.py audit/daily_event_no_supply_matched_runner.py scripts/audit_daily_event_no_supply_matched_environment.py tests/test_daily_event_no_supply_matched_environment.py

    python -m pytest -q tests/test_daily_event_no_supply_matched_environment.py tests/test_daily_event_no_supply_forward_outcomes.py

## Smoke command

    python scripts/audit_daily_event_no_supply_matched_environment.py --symbols LT.NS SRF.NS ADANIPORTS.NS --forward-dir reports\daily-events\no-supply-forward-outcomes\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --replay-dir reports\daily-events\no-supply-environment-replay\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --input-snapshot-dir reports\daily-events\input-snapshots\milestone6_standard_india_large_cap_30\2026-09-18 --workers 3

## Canonical full run

Only after smoke validation:

    python scripts/audit_daily_event_no_supply_matched_environment.py --forward-dir reports\daily-events\no-supply-forward-outcomes\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --replay-dir reports\daily-events\no-supply-environment-replay\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --input-snapshot-dir reports\daily-events\input-snapshots\milestone6_standard_india_large_cap_30\2026-09-18 --workers 4

## Safety

L8 changes no:

- production NO_SUPPLY predicate;
- production requirement label;
- confirmation gate;
- detector weights;
- scoring/ranking;
- DailyBehavior mapping;
- qualification/actionability;
- API behavior;
- alerts/orders;
- production data loading.
