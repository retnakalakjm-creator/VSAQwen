# Full Scanner State Dependency Audit

**Status:** Engineering boundary definition  
**Date:** 2026-09-01  
**Purpose:** Define the causal information required for a true full-scanner incremental continuation before adding production persistence.

## 1. Current validated baseline

Two earlier validation stages are complete:

- Swing checkpoint continuation: 30 symbols × 3 checkpoints = 90/90 equivalent.
- Existing production-path baseline: historical `scan_to_index()` and latest-bar `scan_actionable()` were brought to semantic agreement on the tested checkpoints.

These results do not yet prove full incremental scanner continuation.

## 2. Current production pipeline

```text
metrics
  ↓
SwingEngine
  ↓
StructureFilter / structural swings
  ↓
TrendAnalyzer
  ↓
EvidenceEngine
  ↓
PatternQualificationEngine
  ↓
ProfessionalScoringEngine
  ↓
ScannerCandidate
  ↓
actionability / ranking
```

## 3. Causal state versus derived output

The incremental boundary must persist enough causal information to reproduce the production information boundary. Final scores, final qualification flags, and ranking outputs must remain derived outputs.

### Persist / retain

#### A. Swing continuation state

Already implemented and validated:

- symbol;
- timeframe;
- last closed bar identity;
- search state;
- active candidate identity/type/price;
- retained confirmed swing identities.

The current explicit structural dependency is `STRUCTURE_LOOKBACK = 20` confirmed swings.

#### B. Structural progression event history

`PatternQualificationEngine` does not qualify from the current evidence snapshot alone. It consumes chronological `EvidenceResult` history and extracts:

- `STRUCTURAL_PROGRESSION_IMPROVING` events;
- `STRUCTURAL_PROGRESSION_WEAKENING` events;
- their bar identity/index;
- direction;
- chronological order.

Therefore the incremental state must retain or deterministically reconstruct the structural progression event history that predates the checkpoint and remains relevant after it.

The persisted form should be an event record, not a serialized `ScannerCandidate` and not an outcome-derived label.

### Recompute

#### C. Trend

The trend result is derived from:

- confirmed swings;
- structurally significant swings;
- swing labels;
- recency-weighted label counts;
- trend state rules.

The dependency is causal structural history, not the previous numeric trend score. The current explicit requirements are:

- `TREND_RECENT_SWINGS = 8` for direction/state context;
- `TREND_STATE_LOOKBACK = 4` for state detection.

#### D. Structural swing scoring / filtering

`StructureFilter` recomputes professional structural swing values from metric arrays and swing history. It performs batched Smart Money scoring and structure scoring from the retained confirmed swing set.

This should be recomputed from reopened metrics and retained swing history rather than persisted as authoritative output.

#### E. VSA evidence

Evidence is point-in-time output from the current metrics/context. It must be rebuilt for new bars and any bars affected by the boundary.

The state must not persist a final evidence aggregate as authoritative truth. It may retain the causal event history needed by qualification where the engine has no cheaper equivalent reconstruction path.

#### F. Professional scoring

Professional scores are derived from current trend and scoring evidence. Current scanner configuration includes:

- `SCORING_LOOKBACK_BARS = 10`;
- `MAX_ACTIONABLE_VSA_AGE = 3`.

Scores therefore belong on the recomputation side of the boundary.

#### G. Qualification and actionability

Qualification is derived from chronological structural events plus current scoring evidence. It must be recomputed at the target bar.

Actionability is also derived and must never be persisted as causal state.

## 4. Required future continuation envelope

Conceptually:

```text
FullScannerState
├── schema_version
├── symbol
├── timeframe
├── last_closed_bar
├── swing_state
│   ├── search_state
│   ├── candidate
│   └── retained confirmed swings
├── structural_event_history
│   └── prior structural progression events still relevant to qualification
└── state_metadata
```

Notably absent:

```text
professional_score
qualification_flag
actionable_flag
ranking
final ScannerCandidate
```

Those are derived outputs.

## 5. Boundary reconstruction model

The intended future continuation path is:

```text
persisted causal state
        +
metric seed / reopened boundary data
        +
new closed bars
        ↓
reconstruct structural swings
        ↓
rebuild current trend
        ↓
rebuild current VSA evidence
        ↓
append new structural progression events
        ↓
recompute qualification
        ↓
recompute professional score
        ↓
produce final ScannerCandidate
```

The prefix must not be silently discarded when a downstream detector requires chronological event history.

## 6. Important implementation constraint

A naive continuation implementation could still be incorrect even if SwingEngine state restoration is correct.

Specifically:

```text
Swing state restored correctly
        ≠
full scanner state restored correctly
```

The missing information is the chronological structural evidence required by qualification.

## 7. Efficiency requirement

The first continuation implementation should optimize by reducing work to:

```text
retained causal state
+
boundary seed
+
new bars
```

It should **not** recreate every historical prefix from bar 20 onward as `scan()` currently does.

However, semantic equivalence must be established before aggressive optimization. Any optimized implementation must produce the same production information boundary as the deterministic reference path.

## 8. Full equivalence comparison

The eventual full-scanner equivalence harness must compare, at each checkpoint:

### Structural

- confirmed swing identities;
- active candidate;
- confirmation boundary;
- structural swing selection;
- swing labels;
- trend direction;
- trend state;
- trend strength;
- trend confidence.

### Evidence

- target-bar evidence;
- relevant campaign evidence;
- chronological structural progression events;
- scoring evidence and freshness.

### Decision

- professional score components;
- net pressure;
- net strength;
- qualification;
- qualification evidence;
- actionability;
- final candidate identity;
- ranking order when multiple candidates exist.

## 9. Current implementation decision

Do **not** add a serialized full scanner output to `ScannerState`.

Do **not** treat historical outcomes as state.

Do **not** introduce a hard-coded bar safety window yet.

The next implementation slice should add the minimum structural-event continuation state and a true `ScannerEngine` checkpoint/resume harness that uses that state. Only after that passes on representative symbols should the retained history and seed windows be optimized further.
