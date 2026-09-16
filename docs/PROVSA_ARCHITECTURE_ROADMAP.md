# ProVSA Architecture Remediation Roadmap

**Status:** Active / Living Document  
**Purpose:** Master implementation roadmap for the architectural and code-quality remediation of ProVSA.  
**Primary product direction:** Weekly-timeframe VSA analysis and stock qualification, followed by daily-timeframe VSA entry timing.  
**Update policy:** Update this document as each PR is started, merged, validated, or superseded.

---

## 1. Roadmap Principles

The remediation should improve ProVSA without rewriting the validated VSA domain logic.

The following principles are architectural invariants:

- Preserve point-in-time / no-look-ahead behavior.
- Preserve the distinction between the signal bar and the execution bar.
- Preserve the existing weekly trend and market-structure machinery.
- Preserve structural progression as event-based evidence.
- Preserve immutable/slotted domain and state models where practical.
- Preserve audit-first promotion of experimental VSA evidence.
- Keep provisional evidence read-only until historical validation supports promotion.
- Historical replay, production scanning, audit, and visual replay should converge on one causal transition engine.
- Weekly analysis determines background/direction; daily analysis determines entry timing.
- Do not introduce duplicate trend/structure engines where existing ProVSA logic can be reused.
- Optimize algorithms before changing dataframe libraries or adding low-level acceleration.

---

## 2. Priority Definitions

| Priority | Meaning |
|---|---|
| **P0** | Correctness / causal-integrity issue. Complete before expanding production behavior. |
| **P1** | High-value architectural or performance work required for the weekly→daily system. |
| **P2** | Maintainability, observability, robustness, or modernization improvement. |
| **P3** | Optional/later optimization or infrastructure evolution. |

Status values used in this roadmap:

- `PLANNED`
- `IN PROGRESS`
- `MERGED`
- `VALIDATED`
- `DEFERRED`
- `SUPERSEDED`

---

# Milestone M1 — Scanner Equivalence Safety Contract

**Priority:** P0  
**Status:** PLANNED  
**Production behavior change:** None  
**Dependency:** None

## Objective

Establish a formal invariant that a full historical scan and a checkpoint/resume scan produce semantically identical results.

The fundamental contract is:

```text
FULL(0 ... N)

must equal

FULL(0 ... K)
→ SNAPSHOT(K)
→ RESUME(K+1 ... N)
```

for every valid checkpoint `K`.

## Work

### PR-A — Full-vs-Resume Equivalence Contract

Add deterministic equivalence tests covering:

- trend state
- confirmed swings
- candidate swing
- structural events
- structural progression
- qualification
- scoring evidence
- VSA direction/evidence
- actionability
- ranking score
- signal-bar identity
- execution availability / execution-bar identity
- persisted state required for the next transition

Test multiple checkpoint locations including:

- earliest valid checkpoint
- middle of history
- immediately before a structural transition
- immediately after a structural transition
- immediately before the final bar
- final resumable checkpoint

### Property-Based Coverage

Introduce Hypothesis, preferably initially as a test-only dependency.

Generate histories containing:

- flat markets
- repeated highs/lows
- gaps
- large-spread bars
- zero-volume bars where valid
- rapid candidate reversals
- minimal warm-up histories
- alternating trends
- NaNs / invalid input where validation should reject them
- duplicate timestamps
- revised historical candles
- configuration/state incompatibility scenarios

## Definition of Done

- Full and resumed scans are semantically equivalent across deterministic fixtures.
- Property-based tests exercise arbitrary checkpoint positions.
- A divergence produces a precise test failure identifying the mismatching state/evaluation field.
- CI blocks merge if the equivalence contract fails.
- No production scanner behavior is intentionally changed.

## Merge Gate

**Do not begin deep transition-state refactoring until M1 is merged and green.**

---

# Milestone M2 — True Rolling Scanner State

**Priority:** P0  
**Status:** PLANNED  
**Dependency:** M1

## Objective

Finish the transition from historical reconstruction to a genuinely causal incremental state machine.

Target primitive:

```python
step(previous_state, new_bar_features) -> (new_state, evaluation)
```

The cost of processing a new bar should not grow materially with the entire historical length.

## Current Architectural Risk

The transition abstraction exists, but parts of snapshot/resume still reconstruct historical context. This creates:

- unnecessary historical recomputation
- hidden coupling between resume logic and qualification internals
- risk that future qualification/evidence changes make FULL and RESUME disagree

## Work

### PR-B1 — Explicit Rolling State Inventory

Document exactly what the next bar requires.

Candidate state categories:

```text
TrendState
SwingState
CandidateSwingState
StructuralProgressionState
QualificationState
EvidenceSequenceState
RecentStructuralEventState
RollingMetricState
```

Do not persist arbitrary history merely because existing APIs expect it.

### PR-B2 — First-Class Qualification State

Remove dependence on synthesizing historical `EvidenceResult` objects solely to satisfy qualification.

Persist bounded information explicitly required by qualification.

### PR-B3 — First-Class Progression / Event State

Structural events should be emitted as transitions occur rather than repeatedly reconstructed from historical prefixes where possible.

### PR-B4 — Canonical `step()` Path

Historical replay:

```text
initial state
→ step(bar 1)
→ step(bar 2)
→ ...
→ step(bar N)
```

Production:

```text
load state
→ step(new completed bar)
→ save state
```

Replay UI:

```text
current replay state
→ step(next bar)
```

All three must use the same domain transition behavior.

## Definition of Done

- Incremental decisions no longer depend on synthetic historical reconstruction.
- New-bar processing consumes bounded causal state.
- Historical and resumed paths remain equivalent under M1.
- Snapshot cost is no longer dominated by recomputing the full historical prefix.
- Existing weekly production behavior remains semantically unchanged.

---

# Milestone M3 — Daily-Bar Completion & Trading Calendar

**Priority:** P0  
**Status:** PLANNED  
**Dependency:** M1; can overlap with later parts of M2 if isolated safely

## Objective

Prevent unfinished daily candles from entering daily VSA analysis and establish correct exchange-session semantics before daily entries become actionable.

## Risk

A current-session daily candle can contain valid OHLCV values while its final:

- close
- volume
- spread
- close position

are still unknown.

NaN checking alone is therefore insufficient.

## Work

### PR-C1 — Trading Calendar Abstraction

Introduce an exchange-session abstraction responsible for:

- NSE trading days
- weekends
- holidays
- session close
- next tradable session
- completed-session determination

Avoid scattering hard-coded weekday/time checks across domain code.

### PR-C2 — `completed_daily_only()`

Add the daily equivalent of the existing weekly completion guard.

Requirements:

- forming daily candle excluded
- completed session accepted
- holidays/weekends handled
- deterministic tests with injected clock/calendar
- no dependence on workstation wall-clock inside domain logic

### PR-C3 — Next-Session Semantics

Provide a canonical function for:

```text
daily signal date
→ next eligible execution session
```

This will later be used by the Daily Entry Engine.

## Definition of Done

- An unfinished NSE daily bar can never become a completed VSA signal.
- Holiday/weekend cases are tested.
- Time is injectable/testable.
- Daily signal→execution-session behavior is deterministic.

## Release Gate

**Daily actionability must not be enabled before M3 is validated.**

---

# Milestone M4 — Weekly→Daily Causal Coordinator

**Priority:** P0  
**Status:** PLANNED  
**Dependency:** M1 + M3; preferably M2 substantially complete

## Objective

Create the explicit multi-timeframe causal boundary for ProVSA's primary product goal:

```text
WEEKLY = background / qualification / direction
DAILY  = entry timing
```

## Target Flow

```text
                    DAILY OHLCV
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
     completed weekly bars   completed daily bars
              │                     │
              ▼                     │
       existing ProVSA              │
 trend / structure / VSA            │
              │                     │
              ▼                     │
         WeeklySetup                │
              │                     │
              └──────────┬──────────┘
                         ▼
               MTF Causal Coordinator
                         │
                         ▼
                  DailyEntryEngine
```

## Causality Rule

For any daily bar `D`:

```text
weekly_context(D)
=
latest weekly setup that was fully knowable
before D became actionable
```

A weekly signal derived from a Friday close must not influence Monday–Thursday bars from that same week during replay/backtesting.

## Work

### PR-D1 — `WeeklySetup` Domain Model

Suggested fields:

```text
setup_id
symbol
direction
signal_week
trend_state
structural_progression
qualification
weekly_vsa_direction
weekly_confidence / strength context
qualifying_evidence
support_zone
resistance_zone
invalidation_level
created_at
status
```

Suggested lifecycle:

```text
ARMED
TRIGGERED
INVALIDATED
EXPIRED
```

Do not hard-code arbitrary expiry behavior until historical evidence supports it.

### PR-D2 — Point-in-Time MTF Coordinator

Map each completed daily session to only the weekly state legally available at that time.

Test:

- ordinary weeks
- holidays
- shortened trading weeks
- week boundaries
- replay start in the middle of a week
- missing data
- revised weekly history

## Definition of Done

- No weekly look-ahead is possible in daily replay.
- Weekly context is reproducible at every historical daily bar.
- Existing weekly trend states remain authoritative; no duplicate trend classifier is introduced.
- MTF coordination is independently testable.

---

# Milestone M5 — Weekly Support / Demand & Resistance / Supply Zones

**Priority:** P1  
**Status:** PLANNED  
**Dependency:** M4

## Objective

Add objective entry location to the strong weekly VSA background.

ProVSA should identify zones, not arbitrary exact lines.

Potential inputs:

### Support / Demand

- confirmed weekly swing lows
- previous resistance turned support
- stopping-volume areas
- selling-climax areas
- spring/shakeout areas
- high-volume demand areas
- validated range lows

### Resistance / Supply

- confirmed weekly swing highs
- previous support turned resistance
- buying-climax areas
- upthrust areas
- validated range highs

## Read-Only Outputs

```text
nearest_support_zone
nearest_resistance_zone
distance_to_support_pct
distance_to_support_atr
distance_to_resistance_pct
upside_room_pct
range_position
support_quality
resistance_quality
```

## Rules

- Start read-only/shadow.
- Do not immediately alter weekly qualification.
- Normalize proximity using volatility/ATR where appropriate.
- Preserve source evidence for every zone so the UI/audit can explain why it exists.

## Definition of Done

- Zone calculation is deterministic and point-in-time safe.
- No future swing is used to create a historical support zone prematurely.
- Every zone has provenance.
- Replay can display the zone that existed at that historical point.

---

# Milestone M6 — Daily Entry Shadow Engine

**Priority:** P1  
**Status:** PLANNED  
**Dependency:** M3 + M4 + preferably M5

## Objective

Create a separate daily-entry engine rather than running the weekly scanner unchanged on daily bars.

Weekly decides:

```text
LONG / SHORT / NEUTRAL / NO SETUP
```

Daily decides:

```text
WAIT / SETUP / CONFIRMED / TRIGGERED
```

## Initial Bullish Entry Model

Start with one narrow model:

```text
weekly bullish setup
+
price at/near valid weekly support
+
daily reaction
+
NO SUPPLY and/or TEST
+
next-session trigger
```

Do not add every VSA pattern at once.

## Suggested `DailyEntryCandidate`

```text
symbol
weekly_setup_id
weekly_direction
weekly_signal_week

daily_signal_date
trigger_type
trigger_evidence
confirmation_evidence

entry_status

signal_high
signal_low
trigger_price
invalidation_price

execution_session
```

## Entry State Machine

```text
WAIT
  ↓
SETUP
  ↓
CONFIRMED
  ↓
TRIGGERED
```

with exits to:

```text
INVALIDATED
EXPIRED
```

where justified.

## Execution Rule

Preserve:

```text
signal bar ≠ execution bar
```

Example:

```text
Wednesday:
daily TEST known after close

Thursday or next eligible session:
trigger may execute
```

## Definition of Done

- Daily entry remains read-only/shadow initially.
- Weekly direction cannot be reversed merely by a single daily opposing indicator.
- No same-bar execution leakage.
- Replay demonstrates exact signal and next-session trigger behavior.
- Historical outcome collection is possible.

---

# Milestone M7 — Performance Consolidation

**Priority:** P1  
**Status:** PLANNED  
**Dependency:** M2

## Objective

Reduce algorithmic cost before considering alternative dataframe engines or JIT acceleration.

## Work

### Precompute Vectorizable Features Once

Examples:

```text
average volume
average spread
ATR
relative volume
relative spread
close location
bar direction
rolling percentiles
```

Historical replay should consume prepared features instead of repeatedly copying/recalculating growing DataFrame prefixes.

### Remove Hot-Loop DataFrame Copies

Audit repeated:

```python
df.iloc[:end].copy()
```

and retain copies only where ownership/isolation actually requires them.

### Emit Events Incrementally

Where practical:

```text
transition occurs
→ emit structural event
→ persist bounded event state
```

instead of:

```text
reconstruct prefixes
→ rediscover historical events
```

### Benchmark Before/After

Measure at minimum:

- one symbol / typical weekly history
- one symbol / long history
- representative multi-symbol universe
- full historical replay
- incremental one-new-bar update
- snapshot/save cost

## Definition of Done

- Benchmarks are reproducible.
- Full replay approaches linear scaling in bar count for the transition path.
- Normal incremental update cost is bounded by new data + rolling state.
- No correctness regression under M1.

## Explicit Non-Goals

Do **not** make these the first optimization:

- pandas→Polars rewrite
- Numba everywhere
- multiprocessing before state concurrency semantics are ready

---

# Milestone M8 — Module Boundary & Python Quality Cleanup

**Priority:** P2  
**Status:** PLANNED  
**Dependency:** Can proceed incrementally after M1

## Objective

Improve maintainability without changing trading semantics.

## Work

### Public Professional-Scoring Batch API

Remove architectural dependence on private members such as conceptual:

```python
scorer._metric_arrays(...)
scorer._structure
scorer._smart_money
scorer._professional_*_weight
```

Expose a stable public prepared-scoring interface.

Possible design:

```text
PreparedProfessionalScoringContext
```

or:

```python
ProfessionalScorer.prepare_batch(...)
```

### Explicit Policy Boundaries

Gradually separate scanner policies:

```text
QualificationPolicy
FreshnessPolicy
ActionabilityPolicy
RankingPolicy
ExecutionPolicy
```

Avoid merely splitting large classes into arbitrary smaller files.

### Domain Exceptions

Introduce semantic exception types such as:

```text
ScannerStateError
CheckpointMissing
CheckpointStale
CheckpointConfigMismatch
CheckpointDataMismatch
CheckpointCorrupt
TransitionDivergence
```

### Profiling Boundary

Avoid making development profiling instrumentation a hard domain dependency.

## Definition of Done

- No cross-module reliance on private scorer internals.
- Domain failures have meaningful types.
- Scanner orchestration responsibilities are clearer.
- No intended trading-behavior change.

---

# Milestone M9 — State, Cache & Operational Robustness

**Priority:** P2  
**Status:** PLANNED  
**Dependency:** M2 recommended

## Objective

Make recovery observable and persistence safe as ProVSA scales.

## Work

### Recovery Telemetry

Classify and count fallback reasons:

```text
checkpoint missing
checkpoint stale
config mismatch
history/data mismatch
corrupt checkpoint
transition divergence
```

A successful full-replay fallback must not silently hide repeated incremental failures.

### State Concurrency Policy

Document the current invariant:

```text
one writer per symbol/timeframe
```

If/when concurrent workers are introduced, add:

- per-key locking, or
- generation/CAS semantics, or
- transactional persistence

Do not add distributed locking before concurrency exists.

### Cache/Metadata Generation Consistency

Consider a generation/manifest mechanism so market-data cache and metadata sidecar cannot describe different committed generations after a crash.

### Corporate-Action Policy

Document and test how ProVSA handles:

- splits
- dividends
- provider historical revisions
- adjusted vs raw historical prices

Historical revisions affecting scanner semantics must invalidate incompatible checkpoints.

## Definition of Done

- Recovery reason is visible/diagnosable.
- Persistence assumptions are documented.
- Historical data revisions have a defined state-invalidation policy.
- Cache generation mismatch is either prevented or safely detected.

---

# Milestone M10 — Modernization & CI Quality Gates

**Priority:** P2  
**Status:** PLANNED  
**Dependency:** Can be introduced gradually

## Objective

Modernize where it improves correctness and maintainability rather than for novelty.

## Recommended Tooling

### Ruff

Use for:

- formatting
- linting
- import cleanup
- selected modernization rules

Roll out incrementally.

### Pyright or mypy

Increase type safety around:

- scanner state
- transition interfaces
- domain models
- provider boundaries
- MTF coordinator

### pytest-cov

Track coverage, with special attention to causal state-machine paths rather than chasing an arbitrary percentage.

### Hypothesis

Primary use:

- transition equivalence
- state-machine invariants
- edge-case generation

### `typing.Protocol`

Good candidates:

```text
MarketDataProvider
ScannerStateStore
TradingCalendar
Clock
```

### Pydantic v2 or msgspec

Consider only at external boundaries:

- configuration
- API models
- checkpoint validation
- external payloads

Keep lightweight frozen/slotted dataclasses inside hot domain paths.

## Deferred Modernization

### SQLite + WAL

Consider only when requirements justify:

- multiple writers
- checkpoint history
- transactional multi-object state
- replay snapshot querying
- richer audit persistence

### Polars / Numba

Evaluate only after M7 profiling proves a remaining bottleneck.

## Definition of Done

- New/changed code passes agreed lint/type gates.
- CI includes transition property tests.
- Modernization does not introduce unnecessary hot-loop overhead.
- Legacy strictness is raised gradually rather than through a disruptive cleanup PR.

---

# 3. Weekly→Daily Product Extension — Later Evidence Roadmap

These are **not architectural prerequisites** for the first daily-entry engine. They should be introduced one at a time as read-only evidence and promoted only after outcome validation.

Recommended order:

1. Daily VSA multi-bar sequences
2. Relative strength vs market and sector
3. ATR / volatility normalization
4. Anchored VWAP
5. Daily structure confirmation using existing ProVSA swing/structure concepts
6. Volume Profile / auction-location context
7. Market and sector context
8. Hilega Milega as read-only momentum confirmation
9. Daily Effort/Result and Absorption evidence
10. Wyckoff campaign-phase inference only if it adds information beyond existing ProVSA trend/structure/VSA
11. Meta-labeling only after sufficient validated historical setup data exists

## Avoid Duplicate Logic

Do not introduce:

- another generic stock trend classifier
- a second competing market-structure engine
- an SMC BOS/CHOCH subsystem if existing ProVSA swings can express the required daily confirmation
- arbitrary indicator voting
- confidence percentages without empirical calibration

---

# 4. Recommended PR Sequence

| Sequence | PR | Priority | Purpose | Status |
|---:|---|---|---|---|
| 1 | **PR-A** | P0 | Full-vs-resume equivalence contract | PLANNED |
| 2 | **PR-B1** | P0 | Rolling-state inventory | PLANNED |
| 3 | **PR-B2** | P0 | First-class qualification state | PLANNED |
| 4 | **PR-B3** | P0 | First-class progression/event state | PLANNED |
| 5 | **PR-B4** | P0 | Canonical transition `step()` path | PLANNED |
| 6 | **PR-C1** | P0 | NSE trading-calendar abstraction | PLANNED |
| 7 | **PR-C2** | P0 | `completed_daily_only()` | PLANNED |
| 8 | **PR-C3** | P0 | Next-session execution semantics | PLANNED |
| 9 | **PR-D1** | P0 | `WeeklySetup` model/state | PLANNED |
| 10 | **PR-D2** | P0 | Weekly→daily point-in-time coordinator | PLANNED |
| 11 | **PR-E1** | P1 | Weekly support/resistance zones, read-only | PLANNED |
| 12 | **PR-F1** | P1 | Daily Entry Engine, shadow mode | PLANNED |
| 13 | **PR-F2** | P1 | NO SUPPLY / TEST entry sequence | PLANNED |
| 14 | **PR-F3** | P1 | Next-session daily trigger/replay output | PLANNED |
| 15 | **PR-G1** | P1 | Feature precomputation / hot-loop reduction | PLANNED |
| 16 | **PR-G2** | P1 | Incremental performance benchmark & cleanup | PLANNED |
| 17 | **PR-H1** | P2 | Public professional-scoring batch API | PLANNED |
| 18 | **PR-H2** | P2 | Domain exceptions / policy boundaries | PLANNED |
| 19 | **PR-I1** | P2 | Recovery telemetry + persistence hardening | PLANNED |
| 20 | **PR-J1** | P2 | Ruff/type/coverage CI gates | PLANNED |

The sequence can be adjusted when a PR exposes a dependency, but P0 causal-correctness gates should not be bypassed.

---

# 5. Finding-to-Fix Matrix

| Audit Finding | Priority | Milestone |
|---|---|---|
| Full and resumed execution paths can theoretically diverge | P0 | M1 |
| Transition still reconstructs historical context | P0 | M2 |
| Resume behavior is coupled to current qualification-history needs | P0 | M2 |
| Daily unfinished candle could become future VSA input | P0 | M3 |
| Weekly→daily point-in-time coordinator absent | P0 | M4 |
| Weekly setup is transient rather than persistent MTF context | P0 | M4 |
| Daily entry requires location context | P1 | M5 |
| Daily entry should be separate from weekly scanner semantics | P1 | M6 |
| Repeated historical calculations/copies remain | P1 | M7 |
| Structure filter depends on scorer private internals | P2 | M8 |
| Scanner carries several policy responsibilities | P2 | M8 |
| Generic exceptions lack domain meaning | P2 | M8 |
| Full-replay fallback can hide incremental failure frequency | P2 | M9 |
| Same-key concurrent state writes can last-write-win | P2/P3 | M9 |
| Cache + metadata are not one atomic generation | P2 | M9 |
| Corporate-action/history-revision policy needs formalization | P2 | M9 |
| Lint/type/property-testing gates can be strengthened | P2 | M10 |
| Polars/Numba/database changes are premature without evidence | P3 | M10 / Deferred |

---

# 6. Release Gates

## Gate A — Scanner Refactor Safety

Before modifying core incremental semantics:

- M1 equivalence tests green
- deterministic fixtures green
- no unexplained production-result changes

## Gate B — Daily Analysis Safety

Before enabling daily VSA signals:

- completed daily-bar gate validated
- trading-calendar tests green
- weekly→daily causality tests green

## Gate C — Daily Entry Shadow

Before showing daily entries as production recommendations:

- shadow/replay results collected
- no same-bar execution leakage
- setup invalidation semantics defined
- historical outcome methodology defined
- evidence remains read-only until validated

## Gate D — Performance Refactor

Every performance optimization must pass:

```text
same semantics
+
measurable benchmark improvement
```

No optimization is accepted solely because it is theoretically faster.

---

# 7. Progress Log

Update this table after each meaningful merge.

| Date | PR | Milestone | Status | Result / Notes |
|---|---|---|---|---|
| 2026-09-16 | — | Roadmap | CREATED | Architecture remediation roadmap established from current `main` audit. |

---

# 8. Current Next Action

## NEXT: PR-A — Full-vs-Resume Equivalence Contract

**Priority:** P0  
**Type:** Test-only  
**Production behavior change:** None

### Goal

Prove that the existing scanner's full-history path and checkpoint/resume path produce the same semantic result before changing the transition architecture.

### Initial Checklist

- [ ] Identify canonical comparison fields.
- [ ] Build deterministic full-vs-resume test helper.
- [ ] Test multiple checkpoint positions.
- [ ] Include structural transition boundaries.
- [ ] Include qualification/evidence/actionability comparisons.
- [ ] Add state comparison diagnostics.
- [ ] Add property-based coverage if dependency policy permits in the same PR.
- [ ] Run backend test suite.
- [ ] Confirm zero intended production behavior changes.
- [ ] Merge only when CI passes.
- [ ] Update this roadmap to `MERGED`.
- [ ] After post-merge validation, update to `VALIDATED`.

---

# 9. Long-Term Target Architecture

```text
                         ONE CAUSAL CORE

             Historical ─┐
             Production ─┼──► Transition Engine
             Replay ─────┤          │
             Audit ──────┘          │
                                    ▼
                              WeeklySetup
                                    │
                                    ▼
                         MTF Causal Coordinator
                                    │
                                    ▼
                            DailyEntryEngine
                                    │
                                    ▼
                         Next-Session Execution
```

The transition engine should be the single source of truth for ProVSA's causal market-state evolution.

The weekly scanner should remain responsible for background, structure, qualification and direction.

The daily engine should remain responsible for location, VSA entry sequence, confirmation and execution timing.

---

# 10. Architectural Success Criteria

The remediation is successful when ProVSA can demonstrate all of the following:

1. Historical replay and production resume are semantically identical.
2. New-bar processing uses bounded causal state rather than rebuilding full history.
3. Weekly and daily timeframes are synchronized without look-ahead.
4. Incomplete daily bars cannot influence VSA decisions.
5. Existing weekly trend/structure logic remains the authoritative background model.
6. Daily entry logic is a separate domain layer rather than a duplicate scanner.
7. Every promoted evidence source has replay/audit evidence supporting its use.
8. Performance improvements are benchmarked and do not alter semantics.
9. Persistence/recovery failures are observable rather than silently hidden.
10. CI protects causal invariants, typing and code quality.
11. ProVSA can eventually replay the exact same logic used in production.
12. Confidence is ultimately calibrated from historical outcomes rather than arbitrary indicator counts.

---

**Document owner:** ProVSA project  
**Last updated:** 2026-09-16  
**Next milestone:** M1 — Scanner Equivalence Safety Contract
