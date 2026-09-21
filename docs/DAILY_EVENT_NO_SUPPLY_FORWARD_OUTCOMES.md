# M12 / L7 — NO_SUPPLY Forward Outcome Comparison

## Purpose

L6 established two disjoint, canonical NO_SUPPLY candidate populations on the
same frozen 30-symbol history:

    CURRENT bearish-environment cohort      777
    ALTERNATE bullish-environment cohort  1,732

L7 compares what happened after those already-fixed event sessions.

L7 is audit-only, non-actionable, and does not change the production
NO_SUPPLY predicate.

## Important interpretation boundary

The two cohorts differ by trend environment by construction:

    CURRENT   -> bearish environment
    ALTERNATE -> bullish environment

Therefore any outcome difference is descriptive evidence about the populations,
not a causal estimate of the environment predicate itself.

In particular, L7 does not establish:

- that one predicate causes better outcomes;
- that NO_SUPPLY adds predictive value beyond the surrounding trend;
- that one cohort should immediately replace production logic.

A later matched/conditional study would be required to estimate incremental
pattern value beyond environment.

## Source chain

L7 consumes:

1. canonical L6 summary;
2. canonical L6 observation ledger;
3. the exact frozen OHLCV snapshot bundle used by L6.

It validates:

- L6 audit id and non-actionable status;
- 30 requested / 30 succeeded / zero failures;
- zero L6 current identity drift;
- zero L6 bar-index drift;
- zero current/alternate overlap;
- L6 population partition closes;
- current replay still equals canonical current baseline;
- exact snapshot audit id, manifest hash, basket, period, and cutoff;
- every L6 event session exists in the frozen snapshot;
- the raw snapshot is filtered through the same default NSE session rules used by canonical L6;
- every L6 event bar index matches its position in that L6-equivalent session frame.

L7 fingerprints:

- exact L6 summary;
- exact L6 observations;
- exact frozen snapshot manifest;

and carries the inherited L1/L2/L3/L5 lineage.

## Cohorts

Only the two candidate populations are outcome-tested:

    CURRENT_BEARISH_ENVIRONMENT
    ALTERNATE_BULLISH_ENVIRONMENT

The 1,075 L6 common-signature bars in neither environment are not treated as a
candidate cohort in L7.

## Forward horizons

Default completed-session horizons:

    1
    3
    5
    10
    20

The event session itself is never included in the future window. Forward horizons are counted on the same default NSE-calendar session sequence used by canonical L6, not on unfiltered raw snapshot rows.

For an event on session D and horizon H:

    event close = close[D]
    horizon close = close[D + H]
    future excursion window = sessions D+1 ... D+H

## Outcome metrics

For each complete event/horizon pair L7 records:

### Forward close return

    (close[D+H] / close[D] - 1) * 100

### Maximum favorable excursion (MFE)

    max future high relative to event close

MFE is floored at 0%. If price never trades above the event close, MFE is 0.

### Maximum adverse excursion (MAE)

    min future low relative to event close

MAE is capped at 0%. If price never trades below the event close, MAE is 0.

### Positive close

    close[D+H] > close[D]

No threshold is converted into an actionable success/failure rule.

### Price-discontinuity screening

Raw historical snapshots can contain corporate-action adjustment boundaries,
special historical data discontinuities, or isolated extreme OHLC spikes that
can dominate mean return/MFE statistics.

L7 therefore measures, for every event/horizon window, the maximum absolute
single-session move of event-or-future OHLC relative to the previous session
close.

Canonical threshold:

    0.35 = 35%

An event/horizon is flagged when any event-or-future:

    open
    high
    low
    close

moves by at least 35% from the previous session close.

The flag is descriptive:

    price_discontinuity_in_event_or_window

and the exact maximum move is retained as:

    max_single_session_price_move_pct

Raw outcomes are never deleted or overwritten.

L7 reports both:

    raw comparison
    clean-window comparison

where clean-window statistics exclude only flagged event/horizon rows.

This is preferable to silently winsorizing returns because the underlying
discontinuity remains visible and countable in the audit ledger.

The threshold mirrors the existing ProVSA default 35% price-gap anomaly scale,
but the L7 screen is deliberately broader for outcome integrity because an
extreme high/low spike can contaminate MFE/MAE even when the session close later
normalizes.

## Censoring

An event is included for horizon H only when all H future completed sessions are
present in the frozen snapshot.

Near-cutoff events are explicitly censored rather than evaluated on shorter
partial windows.

For every cohort/horizon L7 records:

    source_event_count
    complete_event_count
    censored_event_count
    censoring_rate
    complete_symbol_count

and requires:

    complete + censored = source

## Event-weighted summaries

For each cohort and horizon:

    event count
    symbol count
    mean forward close return
    median forward close return
    25th / 75th percentile return
    positive-close count/rate
    mean / median MFE
    mean / median MAE

## Symbol-normalized comparison

Event frequency differs by symbol, so a high-frequency symbol can dominate the
raw event-weighted mean.

L7 therefore also computes a per-symbol summary first and then averages symbol
means with equal symbol weight.

The comparison ledger includes both:

    event-weighted outcome difference
    symbol-normalized outcome difference

This is still descriptive, but it makes symbol concentration visible rather
than silently embedding it in the headline comparison.

The same comparison ledger also includes clean-window versions of:

    event count
    mean / median return
    positive-close rate
    mean MFE / MAE
    symbol-normalized mean return
    symbol-normalized positive-close rate

The separate data-quality summary records, per cohort/horizon:

    complete_event_count
    clean_event_count
    price_discontinuity_event_count
    price_discontinuity_rate
    clean_symbol_count

## Expected canonical source invariants

    requested_symbol_count          30
    source_event_count            2509
    current_source_event_count     777
    alternate_source_event_count  1732
    horizon_count                    5
    horizons                   1,3,5,10,20
    cohort_summary_row_count        10
    comparison_row_count             5
    censoring_row_count             10
    data_quality_row_count          10
    price_discontinuity_ratio      0.35
    is_actionable                 false

The exact outcome-row count is intentionally not predetermined because events
near the 2026-09-18 snapshot cutoff will be censored at longer horizons.

## Outputs

    daily_no_supply_forward_outcome_summary.json
    daily_no_supply_forward_event_outcomes.csv
    daily_no_supply_forward_cohort_summary.csv
    daily_no_supply_forward_symbol_summary.csv
    daily_no_supply_forward_cohort_comparison.csv
    daily_no_supply_forward_censoring_summary.csv
    daily_no_supply_forward_data_quality_summary.csv

## Performance

L7 does not replay Metrics, Swing, Structure, Trend, or Evidence.

Each frozen symbol snapshot is loaded once. Raw rows are first filtered through the same default NSE session rules used by canonical L6. Event sessions are then mapped to those L6-equivalent positions and future OHLC windows are sliced on that filtered session sequence.

The complexity is therefore proportional to the number of events and selected
horizons rather than historical prefix replay.

## Local validation

    python -m ruff check audit/daily_event_no_supply_forward_outcomes.py scripts/audit_daily_event_no_supply_forward_outcomes.py tests/test_daily_event_no_supply_forward_outcomes.py

    python -m pytest -q tests/test_daily_event_no_supply_forward_outcomes.py tests/test_daily_event_no_supply_environment_replay.py

## Canonical run

    python scripts/audit_daily_event_no_supply_forward_outcomes.py --replay-dir reports\daily-events\no-supply-environment-replay\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --input-snapshot-dir reports\daily-events\input-snapshots\milestone6_standard_india_large_cap_30\2026-09-18

## Safety

L7 changes no:

- production NO_SUPPLY requirements;
- production environment predicate;
- confirmation gate;
- evidence profile or weight;
- scoring/ranking;
- qualification/actionability;
- API behavior;
- alerts/orders;
- market-data loading.
