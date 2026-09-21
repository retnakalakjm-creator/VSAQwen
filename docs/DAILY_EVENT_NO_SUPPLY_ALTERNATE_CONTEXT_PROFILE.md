# M12 / L12 — ALTERNATE/UP Context Profile

## Purpose

L11 established an asymmetry in the fixed `WEAK_RESULT_ONLY` candidate:

    CURRENT / DOWN
        early favorable excursion (MFE) is broadly durable across eras

    ALTERNATE / UP
        early MFE is positive in older eras
        but reverses in 2023-2026

L12 asks:

    what production-derived context is different in the failing
    ALTERNATE 2023-2026 population?

L12 is descriptive and audit-only.

It does not create a new production filter.

## Plain-English goal

Suppose the same bar pattern worked before 2023 but stopped working recently.

There are two broad possibilities:

1. the pattern itself stopped working randomly; or
2. the surrounding market state changed.

L12 looks only at context ProVSA already knows how to compute at the signal bar.

Example:

    older ALTERNATE signals:
        mostly HEALTHY / IMPROVING trends

    2023-2026 ALTERNATE signals:
        mostly CORRECTING / STABLE trends

If the second state also has weaker matched MFE across the full ALTERNATE
history, that becomes a concrete hypothesis for later validation.

It is still not a production rule.

## Fixed source population

L12 uses the canonical L11 `WEAK_RESULT_ONLY` target ledger.

Only ALTERNATE / UP is profiled because L11 identified the temporal failure
there.

Canonical counts:

    ALTERNATE total              305

    prior history through 2022   263
    2023-2026                     42

The 2023-2026 population spans 24 symbols in L11.

## Candidate semantics remain fixed

Every target must still satisfy:

    WEAK_RESULT_ONLY

which means:

    weak_selling_result = true
    volume_decreasing   = false

Source semantics:

    is_weak_close(bar)
    AND NOT volume_decreasing(bar, previous)

with mandatory NO_SUPPLY requirements still including:

    Bearish Bar
    Low Volume
    Narrow Spread

L12 does not redefine the candidate.

## Exact point-in-time context replay

For each of the 305 ALTERNATE targets L12:

1. loads the canonical frozen daily snapshot;
2. applies the same NSE session filtering as L6/L7/L8;
3. validates the exact target bar index;
4. passes only the completed prefix through:
   - MetricsEngine
   - SwingEngine
   - StructureFilter
   - TrendAnalyzer
5. extracts predeclared context from the target bar.

Future bars are never used to build context.

The replay also hard-validates that every ALTERNATE target still resolves to:

    trend direction = UP

## Predeclared continuous context

L12 intentionally uses a small fixed feature set already computed by ProVSA:

    trend_strength
    trend_confidence

    spread_ratio
    spread_percentile

    volume_ratio
    volume_percentile

    close_ratio
    price_change_pct

    raw_volume_vs_previous_ratio
    volume_class_delta

The raw-volume ratio is:

    current raw volume / previous raw volume

It is descriptive only.

Production `volume_decreasing` does NOT compare this raw ratio.
It compares the ordinal `VolumeClass` stored in `BarContext.volume`.

Therefore the candidate requires:

    current VolumeClass ordinal
        >= previous VolumeClass ordinal

and `volume_class_delta` records that ordinal difference.

L12 does not add arbitrary indicators such as RSI, MACD, or optimized moving
averages.

## Predeclared categorical context

L12 compares:

    trend_state
    structural_pattern
    close_position
    volume_class
    volume_class_relation
    volume_class
    previous_volume_class
    volume_class_relation
    spread_class

These are all existing ProVSA semantic states.

### Trend state

Possible production states include:

    DEVELOPING
    HEALTHY
    CORRECTING
    EXHAUSTED
    REVERSING
    UNKNOWN

### Structural pattern

Existing production structural interpretation:

    UNKNOWN
    IMPROVING
    STABLE
    WEAKENING
    BREAKING

### Close position

The candidate already requires `is_weak_close`, so the relevant states should
remain within:

    LOWER
    ON_LOW

The split between those two may still differ by era.

### Volume-class relation

The actual production confirmation semantics are categorical:

    volume_decreasing(current, previous)
        -> current.volume < previous.volume

where both values are `VolumeClass` enums.

For a WEAK_RESULT_ONLY target, L12 hard-validates:

    current VolumeClass >= previous VolumeClass

and records:

    SAME_CLASS
    HIGHER_CLASS

This is distinct from raw-volume increase/decrease.

## Continuous shift output

For every continuous feature L12 compares:

    prior history through 2022
    vs
    2023-2026

and reports:

    prior count
    latest count

    prior mean
    latest mean
    latest - prior mean

    prior median
    latest median
    latest - prior median

    pooled standard deviation
    standardized mean difference

The standardized mean difference is descriptive only.

It is used to compare shifts measured on different numeric scales.

No threshold such as:

    |SMD| > X

is used to create an automatic production filter.

## Categorical shift output

For every categorical state L12 reports:

    prior count / rate
    latest count / rate
    latest - prior rate

Example:

    HEALTHY
        prior rate   55%
        latest rate  20%
        delta       -35 percentage points

This would identify a major state-distribution change.

Again, it is descriptive.

## Context/outcome cross-check

A state can differ between eras without explaining performance.

Therefore L12 performs one additional cross-check.

Across the complete ALTERNATE 305-event history, it groups existing clean L8
matched outcomes by:

    trend_state
    structural_pattern
    close_position

for:

    H1
    H3
    H5

and reports:

    source target count
    clean pair count
    symbol count

    event-weighted return delta
    symbol-normalized return delta

    event-weighted MFE delta
    symbol-normalized MFE delta

This lets us ask:

    Did a state become more common in 2023-2026?

and separately:

    Is that same state historically associated with weaker MFE?

Both observations are needed before the state becomes a serious hypothesis.

## Important interpretation boundary

L12 does not prove that a shifted state caused the 2023-2026 failure.

For example:

    CORRECTING becomes more common recently
    and CORRECTING has weaker MFE historically

would be useful evidence.

But it still could be correlated with:

- volatility;
- sector composition;
- market-wide regime;
- trend maturity;
- another unmeasured state.

L12 identifies candidate explanatory context.

It does not select or promote a production gate.

## Source lineage

L12 binds to exact hashes for:

- L11 summary;
- L11 candidate targets;
- L11 era outcomes;
- L11 temporal consistency;
- L8 pair outcomes;
- frozen input snapshot manifest.

It also validates the canonical snapshot basket, period, and cutoff.

## Expected fixed invariants

    requested_symbol_count          30
    alternate_target_count         305
    prior_target_count             263
    latest_target_count             42
    context_row_count              305

    continuous_shift_row_count      10

    outcome horizons                1,3,5
    is_actionable                  false

The categorical-shift and context-outcome row counts are measured because only
states actually present in the candidate population are emitted.

## Outputs

    daily_no_supply_alternate_context_summary.json
    daily_no_supply_alternate_contexts.csv
    daily_no_supply_alternate_continuous_shifts.csv
    daily_no_supply_alternate_categorical_shifts.csv
    daily_no_supply_alternate_context_outcomes.csv

## Local validation

    python -m ruff check audit/daily_event_no_supply_weak_result_robustness.py audit/daily_event_no_supply_alternate_context_profile.py scripts/audit_daily_event_no_supply_alternate_context_profile.py tests/test_daily_event_no_supply_weak_result_robustness.py tests/test_daily_event_no_supply_alternate_context_profile.py

    python -m pytest -q tests/test_daily_event_no_supply_weak_result_robustness.py tests/test_daily_event_no_supply_alternate_context_profile.py tests/test_daily_event_no_supply_temporal_stability.py

## Canonical run

    python scripts/audit_daily_event_no_supply_alternate_context_profile.py --temporal-dir reports\daily-events\no-supply-temporal-stability\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --matched-dir reports\daily-events\no-supply-matched-environment\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --input-snapshot-dir reports\daily-events\input-snapshots\milestone6_standard_india_large_cap_30\2026-09-18

## What to inspect first

After the run, inspect in this order:

1. largest continuous context shifts;
2. largest categorical state-rate shifts;
3. whether shifted `trend_state` / `structural_pattern` levels also show
   weak or negative H1/H3/H5 MFE across the full ALTERNATE history;
4. whether the finding has enough event and symbol coverage.

A plausible explanatory hypothesis should satisfy both:

    state changed materially in 2023-2026

and

    state is associated with weaker early MFE historically

before any follow-up conditional replay is justified.

## Safety

L12 changes no:

- NO_SUPPLY requirements;
- environment predicate;
- confirmation labels;
- confirmation gates;
- trend logic;
- evidence weights;
- scoring/ranking;
- DailyBehavior;
- qualification/actionability;
- API behavior;
- alerts/orders;
- production data loading.
