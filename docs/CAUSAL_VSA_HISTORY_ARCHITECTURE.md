# Causal VSA History Architecture

## Status

Production architecture correction.

This change does **not** alter any frozen VSA detector contract.

## Problem

Before this correction, `EvidenceEngine.collect()` and scanner fallback mixed two
different responsibilities.

`collect_supply()` walked recent background bars and emitted historical supply
events into the **current** `EvidenceResult`. Several of those historical bars
were evaluated with context belonging to the latest target bar.

In particular, `BUYING_CLIMAX` and `SUPPLY_COMING_IN` shared one
`CampaignSnapshot.from_context(ctx)` created from the latest context.

The scanner then searched backward inside that current `EvidenceResult` for a
fallback VSA bar.

This created two architecture defects:

1. **Retrospective reinterpretation** — an older supply bar could appear or
   disappear when later campaign/trend/structure context changed.
2. **Directional asymmetry** — supply collection injected historical bearish
   evidence, while demand collection was target-bar based. Historical bearish
   VSA could therefore participate in fallback in ways historical bullish VSA
   generally could not.

## Correct invariant

```text
EvidenceEngine snapshot
    = observations known on that target bar

Scanner chronological state
    = observations captured on their own target bars

Fallback scoring
    = latest causal VSA bar inside the scoring window
      and not before the structural qualification boundary
```

Detectors answer:

> What evidence is observable now?

Scanner state answers:

> What recent evidence was actually observed on prior bars?

Those responsibilities must not be collapsed.

## EvidenceEngine boundary

`collect_supply(ctx)` now evaluates only `ctx.current`.

It no longer loops through `ctx.bars` to manufacture historical supply
emissions inside the latest snapshot.

All existing supply detector functions and mandatory/confirmation semantics are
unchanged.

Therefore each detector is evaluated through the same point-in-time boundary as
the demand-side collectors.

## Scanner fallback boundary

The scanner retains a bounded causal VSA window.

Current policy remains:

```text
scoring lookback = 10 bars
max actionable VSA age = 3 bars
```

At each bar:

1. collect target-bar evidence;
2. extract meaningful non-read-only VSA evidence from that target bar;
3. append it to the causal recent-VSA window;
4. drop observations older than the configured 10-bar scoring lookback;
5. when the current bar has no qualifying VSA, select the latest causal VSA bar
   inside the window;
6. do not cross the earliest structural qualification boundary;
7. retain the existing 3-bar actionability freshness gate.

No fallback threshold changes are included.

## Durable state

`ScannerState` schema moves from v4 to v5 and persists the bounded VSA window
as `recent_vsa_events`.

Each persisted VSA event stores:

- stable bar identity;
- evidence code/category/direction;
- strength/weight/quality;
- observation/description;
- TEST/recovery indices for delayed-recognition provenance.

Old v4 checkpoints are intentionally rejected by schema validation and use the
existing safe full-replay fallback before a v5 checkpoint is written.

## Replay and transition parity

The same causal VSA window is carried by:

- legacy/full scanner replay;
- `ScannerTransitionEngine`;
- transition snapshots;
- transition resume;
- the compatibility `IncrementalScannerEngine` API.

The durable window is bounded, so state size does not grow with full history.

## Unchanged detector layer

This PR does not change:

- BUYING_CLIMAX semantics;
- SUPPLY_COMING_IN semantics;
- HIDDEN_SUPPLY semantics;
- INCREASING_SUPPLY semantics;
- SUPPLY_DRYING_UP semantics;
- UPTHRUST semantics;
- NO_DEMAND semantics;
- demand-side detector semantics;
- Spring/SHAKEOUT delayed-recognition semantics;
- detector weights or quality formulas.

The frozen 30-symbol target-bar emission ledger must therefore remain exactly
unchanged.

## Expected scanner-level effect

Scanner fallback can change because it now uses the actual chronological VSA
history rather than retrospectively reconstructed supply history.

Expected classes of change include:

- bullish fallback evidence becoming available symmetrically;
- stale retrospectively-created bearish fallback evidence disappearing;
- scoring evidence bar/code changing to the latest causal VSA observation;
- downstream professional score/confidence changing when fallback evidence
  changes;
- qualification/actionability changing only through the existing VSA
  confirmation/conflict/freshness rules.

Any detector target-bar emission drift is **not** expected and is a merge blocker.

## Validation boundary

Required before merge:

1. focused Ruff/pytest;
2. transition/full/resume/snapshot parity;
3. point-in-time invariance;
4. state v4 -> v5 safe replay migration;
5. frozen 30-symbol inventory 30/30;
6. exact target-bar emission-ledger equality versus the post-Spring M12 baseline;
7. explicit review of scanner-level fallback/actionability deltas.

This is an architecture correction, not a detector research reopening.
