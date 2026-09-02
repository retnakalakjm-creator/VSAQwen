# ProVSA Scanner State Design

**Status:** Active engineering specification  
**Purpose:** Define the causal state and persistence contract required for production incremental scanning.

## 1. Current runtime facts

The active structural incremental path is:

```text
Yahoo Finance daily data
        ↓
local CSV cache
        ↓
daily_to_weekly()
        ↓
MetricsEngine.calculate()
        ↓
IncrementalStructurePipeline / IncrementalTrendAnalyzer
        ↓
ScannerState resume
```

The broader production scanner still has a full-history path for evidence, scoring, qualification, and ranking. Incremental structural equivalence has already been validated; persistent end-to-end production scanning remains the next boundary.

## 2. Validated incremental capabilities

The repository already contains and tests:

- deterministic prefix/full-history swing equivalence;
- in-memory swing continuation from `ScannerState`;
- serialized `ScannerState` round-trip;
- incremental structural replay using a metric seed window;
- stable bar identities for candidate and confirmed swings.

The current work therefore extends an existing incremental implementation rather than creating one from scratch.

## 3. Canonical state contract

`ScannerState` is the causal continuation envelope.

```text
ScannerState v3
├── schema_version
├── symbol
├── timeframe
├── last_closed_bar
├── search_state
├── candidate
│   ├── bar_key
│   ├── type
│   └── price
├── confirmed_swings
└── structural_events
```

The canonical schema version is defined once as `SCANNER_STATE_SCHEMA_VERSION = 3` and is used by `SwingEngine.snapshot_state()` and the higher-level incremental scanner.

Stable bar identities are used instead of relying on local dataframe integer positions because incremental datasets may be truncated and rebuilt.

## 4. State persistence

`ScannerStateStore` now provides the first persistence boundary.

Current contract:

- one JSON state file per symbol/timeframe;
- schema-version validation on save and load;
- symbol/timeframe identity validation on load;
- deterministic JSON serialization;
- atomic replacement using a temporary file and `os.replace()`;
- explicit delete operation;
- persisted state directory is local-only and ignored by Git.

The state store persists **causal state**, not final scanner outputs.

## 5. State dependency classification

### A. Must persist

The following state is required to resume structural processing:

- active swing-search state;
- active candidate identity/type/price;
- confirmed swing identities needed by downstream structure;
- last finalized closed-bar identity;
- causal structural progression events currently required by incremental qualification reconstruction.

### B. Recalculate from a safety window

The following must be rebuilt from retained bars rather than blindly trusted as immutable:

- swing confirmations near the boundary;
- recent structural swings;
- trend classifications/state;
- recent VSA evidence;
- professional scores for affected recent swings;
- qualification/actionability.

## 6. Confirmed-swing retention

Current explicit dependencies remain:

```text
STRUCTURE_LOOKBACK   = 20 confirmed swings
TREND_RECENT_SWINGS   = 8 confirmed swings
TREND_STATE_LOOKBACK  = 4 confirmed swings
```

These are history dependencies, not a direct bar-count safety window.

`ScannerState` currently retains the swing identities supplied by the active engine. A future bounded-retention change must be justified by downstream dependency analysis and incremental equivalence tests.

## 7. Metric seed and replay window

`LOOKBACK_PERIOD = 20` is the current rolling metric dependency.

The current replay seed is:

```text
METRIC_REPLAY_SEED_BARS = LOOKBACK_PERIOD * 2
```

`incremental_replay_window()` retains every persisted state identity and prepends the metric seed before the earliest required state identity.

This is currently the **safe replay implementation**, not yet the empirically proven minimum.

## 8. Boundary semantics

The production boundary is the last finalized closed weekly bar.

The state contract must never silently treat an unfinished weekly candle as finalized structural history.

Candidate and confirmation identities therefore remain tied to weekly bar keys, while local indices are reconstructed from the current replay dataframe.

## 9. Structural progression state

`structural_events` preserves causal structural progression observations that may need to survive the incremental boundary.

They are rehydrated into `Evidence` only when required for the resumed decision path. Outcome-derived labels are not persisted as decision truth.

## 10. Incremental equivalence contract

Incremental processing is acceptable only when:

```text
full-history rebuild
        ==
incremental rebuild from persisted state + replay window + suffix
```

The comparison must cover at least:

- confirmed swings;
- candidate/confirmation boundary;
- swing labels;
- trend direction/state/strength/confidence;
- structural swing selection;
- VSA evidence;
- professional scores;
- qualification/actionability;
- final scanner decisions.

Structural equivalence is already validated for the current implementation. The remaining work is to extend the same contract through the full production decision path.

## 11. Safety-window derivation

Do not hard-code an arbitrary bar count as the final production invariant.

The current design uses the causal identities in state plus a metric seed. The next validation step is to measure the minimum replay window that preserves equivalence under adversarial boundary placement.

Test boundaries should include:

- active candidate not yet confirmed;
- reversal detected near the boundary;
- confirmation maturation spanning the boundary;
- recent structural progression changes;
- evidence freshness transitions;
- production suppression gates near the boundary.

The result should produce an explicit minimum safe replay window and a documented reason for every component.

## 12. Persistence safety requirements

Persistence must fail closed rather than silently inventing state.

Required behaviors:

- reject unsupported schema versions;
- reject symbol/timeframe identity mismatch;
- reject malformed JSON/state payloads;
- reject missing state identities during replay reconstruction;
- write atomically so an interrupted save does not replace a valid previous state with a partial file.

## 13. Current implementation boundary

Persistence is now implemented as a **state storage primitive**, but it is not yet wired into the live scanner loop.

The next code slice should therefore be:

```text
load persisted state
        ↓
acquire recent closed bars
        ↓
construct safe replay window
        ↓
resume structural state
        ↓
rebuild production evidence/scoring
        ↓
evaluate candidate
        ↓
save new state atomically
```

That orchestration must be added only after end-to-end equivalence is proven.

## 14. Production decision-state rule

The persisted state must reproduce the **production information boundary**, not merely reproduce a numeric score.

A valid state is therefore one that lets the scanner reconstruct all causal information required for:

- event identity and direction;
- event freshness/age;
- confirmation state;
- professional score inputs;
- suppression-gate inputs;
- qualification/actionability.

This remains consistent with the project's real-market VSA principle: preserve meaningful imperfect evidence and its context rather than serializing outcome-derived conclusions.

## 15. Current production decision-state contract

The production scoring milestone now freezes four event-specific policies that must be reproducible at an incremental boundary:

| Event | Production state requirement |
| --- | --- |
| `DEMAND_COMING_IN` | Preserve/reconstruct emitted runtime weight `0.38` and the existing `UP + CORRECTING` suppression condition. |
| `INCREASING_DEMAND` | Preserve/reconstruct confirmation-only semantics and the `UP + HEALTHY` sole-bullish actionability gate. |
| `DEMAND_DRYING_UP` | Do not reconstruct it as production evidence; it remains research-only and is not emitted by the production path. |
| `ABSORPTION` | Preserve/reconstruct production connectivity while retaining runtime scoring weight `0.00`; research-only counterfactual penalties must not leak into production state. |

These are decision-layer constraints, not persisted output fields. The incremental engine should reconstruct them from causal state and current production configuration rather than serializing final decisions as authoritative state.

## 16. Regression status

The current production scoring policy is regression-safe under the full repository suite:

```text
python -m pytest -q
210 passed
```

The 210-test result validates the current policy boundary. It does not establish the final bar safety window; that remains an empirical responsibility of the incremental equivalence harness.

## 17. Current engineering boundary

The production scoring/ranking milestone is complete without authorizing a scoring promotion. The next incremental-state work should therefore focus on preserving causal reproducibility of the validated decision path while avoiding unnecessary persistence of derived outputs.
