# Scanner Architecture Roadmap

## Purpose

This document records the agreed ProVSA scanner-architecture roadmap so future work does not drift into unrelated refactors, premature detector promotion, or replay/manual-review work.

The goal is not to rewrite ProVSA. The current VSA/trading domain model should be preserved. The main improvement area is the execution architecture around the scanner: state identity, full-vs-resume equivalence, fallback diagnostics, and eventually one deterministic transition engine shared by production, audit, and replay.

## Current decision

The next scanner-architecture work should start with correctness guardrails, not a large refactor.

Priority order:

1. Add full-scan versus snapshot-plus-resume equivalence contract tests.
2. Harden scanner-state identity with engine/config/data fingerprints.
3. Improve fallback diagnostics so rebuilds do not silently hide defects.
4. Move gradually toward one deterministic `step(state, bar, features)` transition engine.
5. Remove repeated prefix recomputation only after correctness guardrails are in place.
6. Add modernization tooling only after the scanner behavior is protected.

## Non-goals for this roadmap slice

The following are explicitly out of scope unless separately approved:

- No rewrite of ProVSA.
- No scoring/ranking/actionability changes.
- No trade-plan, alert, or order promotion.
- No detector promotion from read-only evidence into primary evidence.
- No new HVR, stopping-action, or climactic-action implementation until the rule is separately studied and validated.
- No manual-review workflow work.
- No historical replay engine work.
- No frontend feature work except when needed to display already-validated backend evidence.
- No symbol-specific hardcoding.

## Why this order matters

ProVSA now has several scanner execution paths, including historical scanning, incremental scanning, production scanning, audit scanning, and future replay ambitions. The risk is not only performance. The bigger risk is silent divergence: two routes producing different candidates, evidence, qualification, score, or actionability for the same market history.

Before simplifying the architecture, the system needs CI tests that prove the existing routes remain semantically equivalent.

## Phase 1: Full-vs-resume equivalence contract

### Objective

Create regression tests proving this invariant:

```text
FULL(0 … N)

must equal

FULL(0 … K)
    → SNAPSHOT(K)
    → RESUME(K+1 … N)
```

The comparison should be semantic, not just object identity.

### Compare at least

- confirmed swings
- current candidate swing
- structural events
- qualification state/result
- scoring evidence
- read-only evidence neutrality
- actionability
- ranking score
- signal-bar identity
- execution-bar availability

### Required behavior

- No scanner behavior changes in this phase.
- Tests should use generic synthetic fixtures first.
- No symbol-specific fixtures unless used later as regression examples.
- Any mismatch should fail loudly.

### Suggested PR

```text
PR #200
Add scanner full-vs-resume equivalence contract tests
```

## Phase 2: ScannerState identity hardening

### Objective

A persisted scanner checkpoint should only be reused when it is semantically compatible with the current engine, config, symbol/timeframe, and data history.

### Add to state compatibility

- `engine_version`
- `config_fingerprint`
- `data_prefix_fingerprint`
- existing `schema_version`
- existing `symbol`
- existing `timeframe`
- existing `last_closed_bar`

### Expected outcomes

- Config changes should invalidate old scanner state.
- Historical OHLCV revisions before the checkpoint should invalidate old scanner state.
- Truncated/corrupt state should be quarantined or rebuilt with a clear diagnostic.
- Invalid state should not silently disappear without trace.

### Suggested PR

```text
PR #201
Add scanner state compatibility fingerprints
```

## Phase 3: Fallback diagnostics

### Objective

Production fallback should keep the app available but should not hide correctness defects.

### Distinguish fallback reasons

- `CHECKPOINT_MISSING`
- `CHECKPOINT_STALE`
- `CHECKPOINT_CONFIG_MISMATCH`
- `CHECKPOINT_DATA_MISMATCH`
- `CHECKPOINT_CORRUPT`
- `ENGINE_DIVERGENCE`

### Expected outcomes

- Normal bootstrap remains quiet.
- Controlled rebuilds are recorded.
- Corruption is visible.
- Engine divergence becomes a hard diagnostic event, not a silent fallback.

### Suggested PR

```text
PR #202
Surface scanner checkpoint fallback diagnostics
```

## Phase 4: Single deterministic transition engine

### Objective

Move toward one canonical scanner transition primitive:

```python
step(
    state: ScanState,
    bar: MarketBar,
    features: BarFeatures,
) -> tuple[ScanState, BarEvaluation]
```

Historical scan, production scan, audit, and future replay should all call the same transition logic. Only the runner should differ.

### Target shape

```text
MarketDataSource
    ↓
DataNormalizer
    ↓
FeaturePipeline
    ↓
step(state, bar, features)
    ↓
Production / Audit / Replay runners
```

### Constraint

Do not start this phase until Phase 1 equivalence tests exist. The equivalence suite is the safety net for the refactor.

## Phase 5: Remove repeated prefix recomputation

### Objective

Reduce historical and audit scanning from repeated prefix recomputation toward linear scanning.

### Direction

- Precompute vectorizable base features once.
- Step through feature rows with carried state.
- Emit structural events when transitions occur.
- Avoid repeatedly rebuilding DataFrame prefixes inside hot loops.
- Avoid repeatedly recomputing full trend/swing history just to snapshot state.

### Constraint

Performance work must not weaken point-in-time/no-lookahead behavior.

## Phase 6: Modernization after guardrails

Potential improvements after the scanner behavior is protected:

- `Protocol` interfaces for state store, market data source, and scanner clock.
- Domain-specific exception hierarchy for state and fallback errors.
- Ruff formatting/linting.
- Pyright or mypy type checking.
- Hypothesis property-based tests for scanner state-machine equivalence.
- SQLite/WAL only if concurrency, state history, or transactional requirements justify it.

Avoid a pandas-to-Polars rewrite until repeated recomputation has been removed and profiling shows DataFrame operations are still the bottleneck.

## Detector policy during architecture work

Current read-only detector policy remains:

- Effort/Result read-only evidence stays active.
- Absorption read-only evidence stays active.
- High Volume Reversal stays on hold.
- No experimental detector becomes primary scoring/actionability evidence without separate validation.

A single bar is not enough to define reversal. HVR, stopping action, and climactic action require separate study and validated multi-bar rules before implementation.

## Acceptance rule for future work

Before starting any scanner-architecture PR, confirm which phase it belongs to.

If a proposed change does not clearly belong to one of the phases above, it should be treated as a separate roadmap item and not mixed into this architecture track.
