# Scanner Rolling State Inventory

**Roadmap:** M2 / PR-B1 — Explicit Rolling State Inventory  
**Priority:** P0  
**Status:** Proposed contract  
**Production behavior change:** None

## Purpose

This document defines the causal state ProVSA must carry from one completed weekly bar to the next before the scanner is refactored into a genuinely bounded rolling transition engine.

It is intentionally an inventory and design contract only. It does not change scanner, scoring, qualification, evidence, trend, actionability, ranking, execution, or persistence behavior.

The M1 equivalence contract remains the safety gate for every later M2 change:

```text
FULL(0 ... N)
==
FULL(0 ... K)
→ SNAPSHOT(K)
→ RESUME(K+1 ... N)
```

---

## 1. Current State of the Scanner

ProVSA already has two related state representations.

### Durable `ScannerState`

The persisted production checkpoint currently carries:

```text
schema_version
symbol
timeframe
last_closed_bar
search_state
candidate
confirmed_swings
structural_events
engine_fingerprint
config_fingerprint
data_fingerprint
```

This is already sufficient to resume causal swing detection safely and to reject incompatible checkpoints.

### Transition `ScanState`

The transition runner currently carries:

```text
last_bar_index
history: tuple[EvidenceResult, ...]
```

`history` contains structural evidence snapshots used by qualification.

This preserves current semantics, but it is not the desired long-term rolling state because the history tuple grows and the resume adapter reconstructs an `EvidenceResult` context from the checkpoint prefix.

---

## 2. Current Resume Dependencies

The present resume path depends on more than the persisted state explicitly models.

### Swing detection

`SwingEngine.calculate_from_state()` requires:

```text
last closed bar identity
search state
active swing candidate
all retained confirmed swings
current metrics containing the referenced bar identities
```

The active candidate must retain:

```text
bar identity
type
price
```

The search state must retain the current swing-search phase so the next bar continues the same causal process rather than restarting swing detection.

### Trend reconstruction

`IncrementalTrendAnalyzer` currently restores the swing engine, then rebuilds:

```text
structural swing filtering
classified swings
trend structure
trend state / direction / strength / confidence
```

from current metrics plus restored confirmed swings.

Therefore the current production state is incremental for raw swing detection but not yet fully incremental for trend/structure evaluation.

### Structural progression

Professional progression currently operates on structural swing professional scores.

The algorithm needs at most the two most recent comparison windows. Today:

```text
window = min(5, len(scores) // 2)
```

so the current calculation needs at most the latest 10 structural swing scores to reproduce progression.

The present implementation may rebuild/re-filter more history than this bounded progression calculation itself requires.

### Qualification

`PatternQualificationEngine` only consumes two structural event types:

```text
STRUCTURAL_PROGRESSION_IMPROVING
STRUCTURAL_PROGRESSION_WEAKENING
```

The current qualification rule requires:

```text
minimum qualifying events = 3
minimum event spacing      = 4 bars
```

A later opposing structural event invalidates the preceding same-direction sequence.

Therefore qualification does **not** require arbitrary historical `EvidenceResult` snapshots. The minimum causal information can be represented directly as structural event state.

### Current VSA scoring / actionability

For the current target bar, `ScannerEngine` needs:

```text
current EvidenceResult
current TrendResult
qualification result/history
recent meaningful VSA evidence within SCORING_LOOKBACK_BARS
MAX_ACTIONABLE_VSA_AGE semantics
signal-bar anomaly state
```

The target candidate also exposes campaign and read-only evidence for diagnostics/API output. That output requirement must not be confused with state needed to make the *next* bar decision.

---

## 3. Target Rolling State Categories

The desired rolling state should be explicit, causal, serializable where required, and bounded wherever the algorithm permits.

### 3.1 Swing State — REQUIRED

Already represented well by the durable checkpoint.

```text
SwingState
├── search_state
├── active_candidate
│   ├── bar_key
│   ├── type
│   └── price
└── confirmed_swings
```

**Decision:** retain existing durable swing state for M2. Do not redesign it in PR-B2.

**Open optimization question:** whether all confirmed swings must remain persisted indefinitely. Do not truncate them until trend/structure equivalence proves a safe bound.

---

### 3.2 Structural / Trend State — REQUIRED, NOT YET FIRST-CLASS

The next transition ultimately needs enough information to avoid re-running full structural filtering/trend creation.

Proposed conceptual state:

```text
TrendStateSnapshot
├── trend_direction
├── trend_state
├── trend_strength
├── trend_confidence
├── recent classified structural swings
└── recent structural swing evaluations
```

**Decision for M2:** do not persist a cached `TrendResult` blindly. First identify the minimal inputs required to update it causally.

A cached output is not a replacement for causal state.

---

### 3.3 Structural Progression State — REQUIRED, BOUNDED

Current progression calculation only needs the most recent professional structural swing scores used by its two comparison windows.

Target representation:

```text
StructuralProgressionState
├── recent_structural_scores   # bounded; currently max 10 required
├── current_progression
├── current_difference
└── last_emitted_event_identity
```

`last_emitted_event_identity` prevents the same structural progression event from being emitted repeatedly when no new structural swing has been confirmed.

**Bound:** with the current progression algorithm, retain no more than the latest 10 relevant structural professional scores for progression itself.

If the progression algorithm changes, this bound must be versioned/fingerprinted.

---

### 3.4 Qualification State — REQUIRED, BOUNDED

This is the highest-priority state extraction for PR-B2 because it removes the current need to synthesize historical `EvidenceResult` objects solely for qualification.

Proposed representation:

```text
QualificationState
├── latest_opposing_event
├── recent_bullish_events
└── recent_bearish_events
```

Each retained event must preserve at least:

```text
bar_index or stable bar identity
code
direction
```

For current rules, only enough events to determine the latest valid sequence are required.

Safe initial implementation may retain a small bounded deque larger than the theoretical minimum, for example the most recent structural progression events, while equivalence tests establish the final bound.

**Important:** qualification remains event-based. Do not convert structural progression into a permanently bullish/bearish flag.

---

### 3.5 Recent Structural Event State — REQUIRED

The persisted `ScannerState.structural_events` already represents causal structural event history.

The future transition engine should update this state when a new structural event is emitted instead of rediscovering the complete event sequence from all structural swing prefixes.

Target behavior:

```text
new structural swing confirmed
        ↓
update progression
        ↓
if progression event is new
        ↓
emit one StructuralEventState
        ↓
update QualificationState
```

No historical prefix scan should be required merely to rediscover events already observed.

---

### 3.6 Recent VSA / Evidence Sequence State — REQUIRED FOR TRUE BOUNDED STEP

The current scanner searches recent evidence using:

```text
SCORING_LOOKBACK_BARS = 10
MAX_ACTIONABLE_VSA_AGE = 3
```

Future rolling state should retain only the recent evidence needed for:

```text
freshness
current directional confirmation
conflict detection
fallback scoring evidence
future multi-bar VSA sequences
```

Conceptual form:

```text
EvidenceSequenceState
├── recent_scoring_evidence_by_bar
├── latest_bullish_vsa
├── latest_bearish_vsa
└── read_only_recent_evidence   # only if required by output/replay contracts
```

**Initial bound:** at least `SCORING_LOOKBACK_BARS + 1` completed bars of relevant evidence, unless tests prove a smaller/larger causal window.

Read-only evidence must remain excluded from scoring/actionability even when retained in state.

---

### 3.7 Rolling Metric State — REQUIRED LATER

The current transition `BarFeatures` still carries a full point-in-time DataFrame prefix and recomputes trend/evidence from it.

A true bounded transition eventually needs rolling metric inputs such as:

```text
volume windows
spread windows
ATR/range windows
relative volume/spread statistics
percentile/threshold windows required by detectors
```

This is not the first M2 refactor because detector metric dependencies are wider than qualification state.

Target concept:

```text
RollingMetricState
├── required rolling windows
├── current derived metrics
└── detector-specific bounded statistics
```

**Decision:** inventory detector metric requirements before replacing DataFrame-prefix `BarFeatures`.

---

### 3.8 Execution State — NOT PART OF WEEKLY SCANNER ROLLING STATE YET

The current weekly scanner distinguishes:

```text
signal bar
execution bar
execution pending / available
```

These values are derived from the current metrics sequence and candidate.

Do not introduce order/fill state into M2. Daily execution state belongs to the later Daily Entry Engine milestone.

---

## 4. State Needed for Decision vs State Needed for Explanation

A key architectural rule for M2 is to separate these two concerns.

### Needed to make the next decision

Persist/retain only causal inputs such as:

```text
swing continuation state
bounded structural progression state
bounded qualification state
bounded recent scoring evidence
rolling metric windows
algorithm/version fingerprints
```

### Needed to explain/replay a past decision

May include richer output such as:

```text
full target-bar evidence
campaign evidence
read-only evidence
human-readable reasons
professional scoring breakdown
```

These may be recomputed for audit/replay or stored in an audit record. They should not force the production transition state to grow without bound.

---

## 5. Proposed Future State Composition

This is a conceptual target, not an implementation mandate for PR-B2.

```text
ScannerRollingState
├── identity
│   ├── symbol
│   ├── timeframe
│   ├── last_closed_bar
│   └── engine/config/data fingerprints
│
├── swing_state
│   ├── search_state
│   ├── candidate
│   └── confirmed_swings
│
├── structure_state
│   ├── recent structural/classified swings
│   └── current structural/trend summary
│
├── progression_state
│   ├── recent professional structural scores
│   ├── progression
│   └── last emitted event
│
├── qualification_state
│   └── bounded progression-event sequence
│
├── evidence_state
│   └── bounded recent scoring evidence
│
└── metric_state
    └── bounded detector/rolling metric windows
```

---

## 6. What Must Not Be Persisted Merely for Convenience

Avoid turning the checkpoint into a serialized copy of the application.

Do not persist without a demonstrated causal requirement:

```text
entire Metrics DataFrame
all historical EvidenceResult snapshots
all historical target candidates
all historical professional scoring results
API presentation objects
frontend/replay UI state
logger/diagnostic state
```

If a later algorithm genuinely needs older information, add the minimal causal representation and update the state fingerprint/schema deliberately.

---

## 7. State Mutation Rules

Every future rolling-state change should follow these rules:

1. State is derived only from information available through the completed current bar.
2. No future bar can alter the historical state that would have existed at that earlier point in time, except when source history itself is revised and the checkpoint is invalidated.
3. One input bar causes at most one ordered state transition.
4. Structural events are emitted only when a new causal structural condition becomes known.
5. Opposing structural events invalidate qualification sequences according to existing rules.
6. Read-only evidence remains read-only unless a separate validated promotion changes policy.
7. State schema/config/data fingerprint changes must cause safe incompatibility rather than silent reuse.
8. M1 full-vs-resume equivalence remains mandatory after every state extraction.

---

## 8. Refactor Order Derived From This Inventory

### PR-B2 — First-Class Qualification State

Extract qualification from growing/synthetic `EvidenceResult` history.

Scope:

```text
new bounded QualificationState
incremental structural-event ingestion
qualification result from state
adapter compatibility with current ScannerEngine
M1 equivalence remains green
```

Do **not** change VSA scoring or trend calculation in the same PR.

### PR-B3 — First-Class Progression/Event State

Replace repeated historical structural-event discovery with incremental event emission.

Scope:

```text
bounded recent structural professional scores
incremental progression calculation
one-time event emission
persist/resume event state
M1 equivalence remains green
```

### PR-B4 — Canonical Rolling `step()` Consolidation

Move historical, production, replay, and audit toward the same state transition primitive.

The first B4 version may still depend on precomputed bar features, but qualification and progression should no longer reconstruct arbitrary history.

### Later M7 work

Only after M2 correctness is stable:

```text
replace DataFrame-prefix features with bounded/precomputed features
remove repeated metric/trend/evidence prefix work
benchmark scaling
```

---

## 9. Explicit Non-Goals of M2 / PR-B1

PR-B1 does not:

- change `ScannerState` schema
- alter the transition engine
- change qualification rules
- change structural progression rules
- change VSA scoring
- change actionability
- change ranking
- change evidence promotion status
- change signal/execution semantics
- add daily entry logic
- optimize Pandas

It exists to prevent later refactors from persisting the wrong information or mixing unrelated changes.

---

## 10. Acceptance Criteria

PR-B1 is complete when:

- the current durable and transition state responsibilities are documented;
- every current next-bar dependency is assigned to a state category;
- bounded state candidates are identified where current algorithms permit a clear bound;
- decision state is explicitly separated from explanation/audit output;
- the next refactor boundary is identified as first-class qualification state;
- no production Python code changes;
- no scanner behavior changes.

---

## Decision Summary

The immediate architectural conclusion is:

```text
PR-B2 should NOT attempt to make all of ProVSA incremental at once.

First remove qualification's dependency on synthetic/growing
EvidenceResult history by introducing explicit bounded qualification state.
```

That is the smallest next step with the clearest correctness boundary and the strongest protection from the M1 equivalence contract.
