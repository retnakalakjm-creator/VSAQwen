# Progression Symbol-Normalized Drift Baseline Audit

## Purpose

K18 asks whether K15's directional outcome asymmetry contains information beyond
ordinary symbol drift.

K15 showed bullish progression labels performed positively while bearish labels
performed negatively in their own favored direction. That can be caused by:

- genuine progression-specific directional information;
- the ordinary long-run upward drift of equities;
- both.

K18 measures incremental lift without changing progression semantics.

## Frozen input

K18 consumes the validated K15 artifacts:

    progression_directional_outcomes_summary.json
    progression_directional_outcome_observations.csv

It does not rerun the scanner.

The frozen K15 event week is the stable event locator. The original K15
event_bar_index is retained as provenance only because row indices can shift when
another machine has a longer or revised local history.

Each event is resolved by exact event_week in the local completed-weekly series.
Its forward outcome is then recomputed from that same local weekly history used
for the drift controls. The frozen K15 favorable return is retained alongside the
recomputed value so provider-history revisions remain visible.

## Control definition

For each symbol, direction, and horizon:

    same symbol
    + same directional side
    + same horizon
    + non-progression weekly signal bars only
    + from the first event of that direction through the fixed audit cutoff

Progression-event bars of either direction are excluded from controls.

Every control uses the same causal contract:

    signal week N
    -> execution at N+1 close
    -> requested forward weekly horizon

Only complete control outcomes enter the baseline.

## Lift

For each locally recomputed complete event outcome:

    lift =
        recomputed event favorable return
        - same-symbol / same-side / same-horizon control mean

K18 reports both:

- event-weighted lift;
- equal-weighted per-symbol mean lift.

The second view prevents high-event symbols from dominating the conclusion.

Using the fixed cutoff rather than the last event preserves usable controls for
symbols with only one or a few progression events.

## Outputs

- progression_drift_baseline_summary.json
- progression_drift_baselines.csv
- progression_drift_event_lift.csv
- progression_drift_lift_cohorts.csv
- progression_drift_baseline_failures.csv

## CLI

    python scripts/audit_progression_drift_baseline.py --now 2026-09-18T16:00:00+05:30

Existing market-data cache remains frozen unless --refresh is explicitly supplied.

This makes K18 portable across machines whose cached histories begin at different
dates while keeping each event/control comparison on one internally consistent
local price history.

## Safety

Read-only and non-actionable.

K18 does not change progression scoring, progression direction, qualification,
scanner actionability, WeeklySetup materialization, daily coordination, alerts,
execution, or orders.
