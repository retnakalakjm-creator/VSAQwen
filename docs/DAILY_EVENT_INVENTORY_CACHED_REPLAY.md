# Optimized Frozen Daily Evidence Replay

## Purpose

The original frozen daily-event inventory replay was causally correct but
computationally expensive.

For every target bar it rebuilt:

    MetricsEngine
    SwingEngine
    StructureFilter
    TrendAnalyzer
    EvidenceEngine

from bar zero through the current target.

That repeated-prefix design behaves approximately quadratically with history
length and becomes unnecessarily slow on the 30-symbol full-history basket.

This change adds a cached causal replay while preserving the legacy prefix
replay as the correctness oracle.

## Replay modes

Frozen inventory now supports:

    cached
    prefix

Default:

    cached

Legacy oracle:

    prefix

CLI:

    --replay-mode cached
    --replay-mode prefix

The production-data-loader path is unchanged.

## Cached replay design

For each symbol:

1. completed daily sessions are frozen exactly as before;
2. MetricsEngine runs once over the completed history;
3. SwingEngine runs once;
4. StructureFilter runs once;
5. each target bar receives only:
   - metrics through that target;
   - swings whose confirmation_index is already visible;
   - structural swings whose confirmation_index is already visible;
   - trend derived from that causal structural prefix;
6. EvidenceEngine receives the same point-in-time prefix contract as the legacy
   evaluator;
7. only target-bar evidence is retained.

## Why full-history metrics are safe

MetricsEngine calculations are based on:

    previous-bar shifts
    trailing rolling statistics
    historical percentile ranks
    current-bar classifications

No future suffix is intentionally used.

This assumption is not accepted on faith: exact replay parity against the
canonical prefix inventory is a required merge gate.

## Swing causality

SwingEngine is sequential.

A swing becomes eligible at target bar T only when:

    confirmation_index <= T

Future-confirmed swings are not exposed to the target evaluation.

## Structural causality

StructureFilter documents that a confirmed swing's professional evaluation uses
only that swing and earlier point-in-time history.

The cached replay computes the full structural ledger once, then exposes only
the confirmation-visible prefix at each target.

If the structural output is not ordered by confirmation index, the cached
producer fails closed.

## Trend caching

TrendAnalyzer derives its state from structural swing classification.

Therefore trend is recomputed only when the causal structural prefix length
changes.

Between structural confirmations the same TrendResult is reused.

This removes repeated identical trend work without changing visible state.

## EvidenceEngine boundary

EvidenceEngine itself is not rewritten.

For each target it still receives:

    metrics[: target + 1]
    causal trend
    causal structural swings

Supply, demand, spring, effort/result, and structural progression collectors
continue to run through the normal production EvidenceEngine path.

## Spring copy removal

The old Spring collector performed:

    metrics.iloc[: current + 1].copy()

even though all Spring detection and validation helpers are read-only.

The copy is removed:

    metrics.iloc[: current + 1]

This preserves the same point-in-time view while avoiding another full-prefix
memory copy on every target bar.

## Parallelism

The existing frozen replay runner still:

    schedules longest histories first
    uses up to 4 worker processes
    restores requested symbol order
    reports symbol-level completion

The optimization is therefore:

    cached per-symbol replay
    +
    existing multi-process orchestration

rather than merely parallelizing the old quadratic prefix calculation.

## Legacy oracle remains available

The original producer:

    produce_offline_daily_evidence

is unchanged and remains the prefix-replay correctness oracle.

The new producer is:

    produce_offline_daily_evidence_cached

The frozen runner can explicitly select either mode.

## Unit parity

A focused pytest compares cached and prefix archives exactly:

    symbol
    completed sessions
    source fingerprint
    target observations
    full Evidence tuples

The cached path must not merely reproduce event codes; all Evidence fields must
match.

## Canonical full-basket parity

The strongest merge gate compares a new cached inventory against the already
existing canonical legacy-prefix inventory.

Reference:

    reports\daily-events\inventory\
      milestone6_standard_india_large_cap_30_frozen_2026-09-18

Candidate:

    reports\daily-events\inventory\
      milestone6_standard_india_large_cap_30_frozen_2026-09-18_cached

The parity audit compares:

    summary
    inventory rows
    complete emission ledger
    duplicate ledger

Required:

    summary_equal = true
    inventory_equal = true
    emissions_equal = true
    duplicates_equal = true
    exact_match = true

    inventory_row_symmetric_difference_count = 0
    emission_row_symmetric_difference_count = 0
    duplicate_row_symmetric_difference_count = 0

The parity command exits non-zero if exact_match is false.

## Local validation

Run:

    python -m ruff check audit/offline_daily_evidence.py audit/daily_event_inventory_runner.py audit/daily_event_inventory_replay_parity.py scripts/audit_daily_event_inventory.py scripts/audit_daily_event_inventory_replay_parity.py evidence/spring.py tests/test_offline_daily_evidence.py tests/test_daily_event_inventory_runner.py tests/test_daily_event_inventory_replay_parity.py

Then:

    python -m pytest -q tests/test_offline_daily_evidence.py tests/test_daily_event_inventory_runner.py tests/test_daily_event_inventory_replay_parity.py tests/test_spring.py tests/test_spring_interactions.py

## Canonical cached replay

Run:

    python scripts/audit_daily_event_inventory.py --input-snapshot-dir reports\daily-events\input-snapshots\milestone6_standard_india_large_cap_30\2026-09-18 --now 2026-09-18T16:00:00+05:30 --workers 4 --replay-mode cached --output-dir reports\daily-events\inventory\milestone6_standard_india_large_cap_30_frozen_2026-09-18_cached

The canonical output should retain:

    requested_symbol_count = 30
    succeeded_symbol_count = 30
    failed_symbol_count = 0
    evaluated_bar_count = 198382

The remaining inventory counts must match the legacy reference exactly.

## Canonical parity gate

Run:

    python scripts/audit_daily_event_inventory_replay_parity.py --reference-dir reports\daily-events\inventory\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --candidate-dir reports\daily-events\inventory\milestone6_standard_india_large_cap_30_frozen_2026-09-18_cached --output-dir reports\daily-events\inventory-replay-parity\2026-09-18

Required:

    exact_match = true

## After merge

PR #348 can merge/rebase main and run its post-change inventory with:

    --replay-mode cached

The existing production-impact audit remains unchanged.

The optimization does not change:

    detector semantics
    Evidence weights
    scoring
    DailyBehavior
    weekly logic
    actionability
    alerts
    orders
    market data

It changes only how the audit replay reaches the same causal evidence ledger.
