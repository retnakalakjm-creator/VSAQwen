# M12 / L6 — NO_SUPPLY Environment Predicate Causal Replay

## Purpose

L5 identified one detector correction whose event impact cannot be inferred
from existing ledgers:

    NO_SUPPLY
    current requirement label: "Bullish Environment"
    current predicate:          ctx.is_bearish_environment()

The alternate semantic candidate is:

    ctx.is_bullish_environment()

L6 causally replays that alternate predicate on the canonical frozen daily
snapshots while preserving the current production detector unchanged.

L6 is read-only and non-actionable.

## Why replay is required

Canonical L3 records only bars that passed the current mandatory detector
contract. It therefore cannot reveal bars that would qualify under the
opposite environment predicate.

L6 reconstructs the point-in-time Metrics / Swing / Structure / Trend context
for each eligible target session and evaluates both environment predicates on
the same completed prefix.

## Source chain

L6 requires canonical L5 correction-design artifacts, the exact canonical L3
confirmation artifacts referenced by L5, and the exact frozen input snapshot
bundle.

It validates the L5 audit id, L5 -> L3 hashes, the replay-required NO_SUPPLY
candidate, snapshot manifest/basket, and the carried L1/L2 lineage.

## Replay path

    frozen completed daily prefix through D
      -> MetricsEngine
      -> SwingEngine
      -> StructureFilter
      -> TrendAnalyzer
      -> EvidenceEngine context construction only
      -> NO_SUPPLY contract evaluation

L6 does not run the full Evidence collector stack.

The current production _collect_no_supply() function is also evaluated on the
same context. Its emission must agree exactly with the audit reconstruction of
the current bearish-environment predicate.

## Safe raw-bar prefilter

NO_SUPPLY requires a bearish bar. Production direction semantics are exactly:

    close < open -> Direction.DOWN
    is_bearish_bar(bar) -> bar.direction == Direction.DOWN

Therefore L6 safely skips target sessions where close >= open before copying
the prefix or running Metrics/Swing/Trend.

For the remaining bearish targets, L6 runs the exact point-in-time
MetricsEngine first and reconstructs the target BarContext directly from those
metrics. It then checks the remaining mandatory bar predicates:

    Low Volume
    Narrow Spread

Only bars satisfying the complete common bar signature proceed to the expensive:

    SwingEngine
    StructureFilter
    TrendAnalyzer
    EvidenceEngine context construction

This second prefilter uses the same production metrics and the same production
bar predicates; it does not approximate classifications.

The summary exposes:

    evaluated_target_count
    replayed_bearish_target_count
    skipped_non_bearish_target_count
    common_signature_count
    trend_context_replay_count

where:

    evaluated = replayed_bearish + skipped_non_bearish
    trend_context_replay_count = common_signature_count

On the validated 3-symbol smoke before this optimization there were:

    8,846 bearish target prefixes
    354 common-signature prefixes

so the optimized path should still run Metrics on 8,846 bearish prefixes while
reducing full Swing/Structure/Trend context construction to 354 prefixes,
subject to the exact 73-event current-parity smoke gate.

## Logging

The existing TrendAnalyzer writes two INFO messages for every prefix. L6
workers suppress VSA INFO logs during the inner replay loop. The parent runner
still reports one progress line per completed symbol.

## Target-bar contract

Common bar signature:

    Bearish Bar
    Low Volume
    Narrow Spread

Current candidate:

    common signature AND bearish environment

Alternate candidate:

    common signature AND bullish environment

For every common-signature bar L6 also records the existing confirmations:

    Weak Spread
    Volume Decreasing
    Weak Selling Result

No confirmation gate is introduced.

## Critical current-parity hard gate

The optimized L6 replay is trusted only if its current candidate set exactly
reproduces canonical L3 NO_SUPPLY.

Canonical full-basket current baseline:

    777 events

Required full-run gate:

    failed_symbol_count                 = 0
    current_baseline_event_count        = 777
    current_replay_event_count          = 777
    current_identity_mismatch_count     = 0
    current_bar_index_mismatch_count    = 0
    current_alternate_overlap_count     = 0

The alternate event count is intentionally unknown before replay.

## Three-symbol smoke

Recommended first smoke:

    LT.NS
    SRF.NS
    ADANIPORTS.NS

Canonical L3 current counts:

    LT.NS             37
    SRF.NS            19
    ADANIPORTS.NS     17
    --------------------
    total             73

Smoke hard gate:

    requested_symbol_count              = 3
    succeeded_symbol_count              = 3
    failed_symbol_count                 = 0
    current_baseline_event_count        = 73
    current_replay_event_count          = 73
    current_identity_mismatch_count     = 0
    current_bar_index_mismatch_count    = 0
    current_alternate_overlap_count     = 0

The alternate count remains an observed result, not an expected invariant.

## Checkpoint / resume

Each successfully completed symbol is written immediately to:

    reports\daily-events\no-supply-environment-replay\
      milestone6_standard_india_large_cap_30_frozen_2026-09-18\
      checkpoints\SYMBOL.json

A checkpoint is reused only when its replay signature matches exactly. The
signature includes:

- checkpoint schema/replay-contract version;
- complete L6 source lineage;
- `--now`;
- `--min-target-index`.

Therefore a changed source chain, cutoff, replay time, or replay start invalidates
the old checkpoint automatically.

Resume is enabled by default. To force recomputation:

    --no-resume

The smoke rerun can therefore seed three reusable full-history checkpoints for:

    LT.NS
    SRF.NS
    ADANIPORTS.NS

A later 30-symbol run with the same canonical inputs reuses those checkpoints
and computes only the remaining symbols.

## Progress manifests

Every invocation writes a selection-specific progress manifest under:

    checkpoints\progress\selection-<digest>.json

It records:

- requested symbols;
- checkpoint-reused symbols;
- newly completed symbols;
- failed symbols;
- pending symbols;
- worker count;
- RUNNING / COMPLETE / PARTIAL / INTERRUPTED state.

Per-symbol checkpoint files, not the progress manifest, are the authoritative
resume source.

## Symbol sharding

Optional deterministic sharding is available with zero-based indices:

    --shard-index 0 --shard-count 3
    --shard-index 1 --shard-count 3
    --shard-index 2 --shard-count 3

Shards use the canonical basket order and select symbols by:

    basket_position % shard_count == shard_index

All shards share the same default checkpoint directory, while their report
outputs are isolated under:

    ...\shards\shard-01-of-03
    ...\shards\shard-02-of-03
    ...\shards\shard-03-of-03

After all shards finish, running the normal full 30-symbol command with resume
enabled assembles the complete canonical audit from those checkpoints without
recomputing completed symbols.

## Outputs

    daily_no_supply_environment_replay_summary.json
    daily_no_supply_environment_observations.csv
    daily_no_supply_environment_symbols.csv
    daily_no_supply_current_identity_mismatch.csv
    daily_no_supply_current_index_drift.csv
    daily_no_supply_environment_failures.csv

## Local validation

    python -m ruff check audit/daily_event_no_supply_environment_replay.py audit/daily_event_no_supply_environment_runner.py scripts/audit_daily_event_no_supply_environment_replay.py tests/test_daily_event_no_supply_environment_replay.py

    python -m pytest -q tests/test_daily_event_no_supply_environment_replay.py tests/test_daily_event_detector_correction_design.py tests/test_daily_event_confirmation_semantics.py

## Smoke command

    python scripts/audit_daily_event_no_supply_environment_replay.py --now 2026-09-18T16:00:00+05:30 --symbols LT.NS SRF.NS ADANIPORTS.NS --design-dir reports\daily-events\detector-correction-design\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --confirmation-dir reports\daily-events\confirmation-counterfactual\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --input-snapshot-dir reports\daily-events\input-snapshots\milestone6_standard_india_large_cap_30\2026-09-18 --workers 3

## Canonical full run

Only after smoke parity passes:

    python scripts/audit_daily_event_no_supply_environment_replay.py --now 2026-09-18T16:00:00+05:30 --design-dir reports\daily-events\detector-correction-design\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --confirmation-dir reports\daily-events\confirmation-counterfactual\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --input-snapshot-dir reports\daily-events\input-snapshots\milestone6_standard_india_large_cap_30\2026-09-18 --workers 4

The replay remains computationally substantial because Metrics/Swing/Structure/
Trend are still recomputed causally from each replayed historical prefix.
However, L6 avoids replaying non-bearish targets, does not run unrelated
detectors, and suppresses inner-loop INFO logging.

## Interpretation boundary

L6 answers which population NO_SUPPLY would produce if its environment
eligibility were bullish instead of bearish. It does not decide which
environment definition has better forward behavior; that is a later outcome
validation step.

## Safety

L6 changes no production NO_SUPPLY predicate, requirement label, confirmation
gate, evidence profile/weight, scoring/ranking, DailyBehavior mapping,
qualification/actionability, API behavior, alerts/orders, or production data
loading.