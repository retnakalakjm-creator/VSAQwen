# Progression Directional Forward-Outcome Audit

## Purpose

K15 tests the question K14 cannot answer from same-bar context alone:

    Do production progression labels have future weekly directional value?

A bearish progression event inside an uptrend may be a valid early-warning
signal even when it is opposed to current trend. K15 therefore measures forward
outcomes before any semantic redesign is considered.

## Causal execution contract

K15 reuses the existing analysis-only forward-outcome helper:

    event known on completed weekly bar N
    → no same-bar scoring
    → execution modeled at weekly bar N+1 close
    → evaluate 1 / 3 / 5 / 10 / 15 weekly bars after execution

Bullish progression uses long-side favorable returns.

Bearish progression uses short-side favorable returns.

The audit records:

- raw return;
- direction-adjusted favorable return;
- MFE;
- MAE;
- complete/incomplete horizon status.

## Cohorts

Outcomes are summarized by:

- all events;
- event direction;
- trend alignment: aligned / opposed / neutral / unknown;
- structural-pattern alignment: aligned / opposed / ambiguous.

This directly tests whether trend-opposed events behave like useful reversal
warnings or merely carry non-directional swing-quality information.

## Frozen K14 event input

K15 does not rerun HistoricalScannerRunner.

It consumes the already-validated K14 artifacts:

    progression_directionality_events.csv
    progression_directionality_symbols.csv

For every requested symbol, the K14 symbol event_count must exactly match the
loaded event rows. Duplicate event identities fail closed.

The event bar index and week are then validated against the completed weekly
price history before any outcome is computed.

This avoids repeating the expensive full historical scanner replay solely to
rediscover events that K14 already froze and validated.

## Cache stability

Existing market-data cache is treated as frozen for K15 unless --refresh is
explicitly supplied.

This prevents a long audit from incrementally refreshing different symbols at
different wall-clock times merely because their cache files crossed the normal
15-minute live-scan freshness threshold.

## Basket

The CLI reuses the existing standard VSA basket and supports staged
--max-symbols runs.

## CLI

Full standard basket:

    python scripts/audit_progression_directional_outcomes.py --now 2026-09-18T16:00:00+05:30

By default the K14 input directory is:

    reports/daily-behavior-sequences/progression-directionality/<BASKET>

Use --directionality-dir only when the validated K14 artifacts live elsewhere.

Staged first five symbols:

    python scripts/audit_progression_directional_outcomes.py --now 2026-09-18T16:00:00+05:30 --max-symbols 5

## Outputs

- progression_directional_outcomes_summary.json
- progression_directional_outcome_observations.csv
- progression_directional_outcome_cohorts.csv
- progression_directional_outcome_failures.csv

## Safety

Read-only and explicitly non-actionable.

K15 does not change progression scoring, evidence direction, qualification,
scanner actionability, WeeklySetup materialization, coordinator behavior, daily
signals, alerts, execution, or orders.
