# ProVSA Architecture Remediation Roadmap

**Status:** Active / Living Document  
**Primary product direction:** Weekly-timeframe VSA background/qualification followed by daily-timeframe entry timing.  
**Update policy:** Update this document whenever a roadmap PR is started, merged, validated, superseded, or materially redesigned.  
**Last updated:** 2026-09-18

---

## 1. Architectural Principles

The remediation must improve ProVSA without replacing validated domain logic with simplified textbook rules.

Core invariants:

- Preserve point-in-time / no-look-ahead behavior.
- Preserve the distinction between signal bar and execution bar.
- Preserve existing weekly trend and market-structure machinery.
- Preserve structural progression as event-based evidence.
- Preserve immutable/slotted domain and state models where practical.
- Keep provisional evidence read-only until historical validation supports promotion.
- Historical replay, production scanning, audit, and visual replay should converge on one causal transition path.
- Weekly analysis determines background, qualification, campaign direction, and structural context.
- Daily analysis determines entry timing only.
- Do not introduce duplicate trend/structure engines where existing ProVSA logic can be reused.
- Optimize algorithms before changing dataframe libraries or adding low-level acceleration.

### Real-Market Evidence Principle

**Real markets will not reliably create textbook scenarios.**

Therefore ProVSA must evaluate the behavior expressed by evidence rather than require one named VSA pattern to appear exactly.

Named events such as:

```text
NO SUPPLY
TEST
STOPPING VOLUME
SHAKEOUT
SPRING
DEMAND COMING IN
ABSORPTION
UPTHRUST
NO DEMAND
```

are evidence contributors, not mandatory entry gates.

The daily engine should ask behavioral questions such as:

```text
Is opposing pressure receding?
Is aligned pressure emerging?
Is the opposing move being rejected?
Is effort producing result in the weekly direction?
Is absorption present?
Is structure improving/aligned?
Is continuation behavior present?
```

A stock may rally without a textbook NO SUPPLY or TEST. That is not, by itself, a model failure. The system should recognize alternative real-market evidence when it exists, and should still be allowed to return NO ENTRY when price moves without a sufficiently defined low-risk entry condition.

---

## 2. Priority Definitions

| Priority | Meaning |
|---|---|
| **P0** | Correctness / causal integrity. Complete before expanding production behavior. |
| **P1** | High-value architecture required for the weekly→daily product. |
| **P2** | Maintainability, robustness, observability, modernization. |
| **P3** | Optional/later optimization or infrastructure evolution. |

Status values:

```text
PLANNED
IN PROGRESS
MERGED
VALIDATED
DEFERRED
SUPERSEDED
```

---

# M1 — Scanner Equivalence Safety Contract

**Priority:** P0  
**Status:** VALIDATED

Fundamental invariant:

```text
FULL(0 ... N)
==
FULL(0 ... K) → SNAPSHOT(K) → RESUME(K+1 ... N)
```

Compare trend, swings, candidate state, structural events, qualification, evidence, actionability, ranking, signal identity, execution availability, and persisted transition state.

### PR-A — Full-vs-Resume Equivalence Contract

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #246

---

# M2 — True Rolling Scanner State

**Priority:** P0  
**Status:** VALIDATED

Objective: move scanner behavior toward bounded causal state and one transition path.

### PR-B1 — Rolling-State Inventory

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #247

### PR-B2 — First-Class Qualification State

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #250

### PR-B3 — First-Class Structural/Progression Event State

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #251

### PR-B4 — Canonical State-Driven Transition Path

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #252

---

# M3 — Daily-Bar Completion & Trading Calendar

**Priority:** P0  
**Status:** VALIDATED

Objective: prevent incomplete daily candles from entering daily VSA logic and establish deterministic exchange-session semantics.

### PR-C1 — NSE Trading Calendar Abstraction

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #253

### PR-C2 — `completed_daily_only()`

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #255

### PR-C3 — Next-Session Execution Semantics

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #256

Invariant:

```text
daily signal session
→ TradingCalendar.next_session(signal)
→ execution is available only on that exact expected session
```

---

# M4 — Weekly→Daily Causal Coordinator

**Priority:** P0  
**Status:** VALIDATED

Target relationship:

```text
WEEKLY = background / qualification / direction
DAILY  = timing / confirmation / execution opportunity
```

For any daily bar `D`:

```text
weekly_context(D)
=
latest weekly setup fully knowable before D became actionable
```

No Monday–Thursday daily bar may consume information created from the Friday close of the same week.

### PR-D1 — `WeeklySetup` Domain Model

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #257

Lifecycle:

```text
ARMED
├── TRIGGERED
├── INVALIDATED
└── EXPIRED
```

### PR-D2 — Point-in-Time Weekly→Daily Coordinator

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #258

---

# M5 — Weekly Support / Resistance Zones

**Priority:** P1  
**Status:** VALIDATED

Objective: provide objective weekly location context without changing production qualification or actionability.

### PR-E1 — Read-Only Weekly Structural Zones

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #259

Current first implementation derives support/resistance from confirmed non-failed structural swings using point-in-time confirmation rules.

Future expansion may include:

```text
support/resistance flips
stopping-volume zones
selling/buying climax zones
spring/shakeout/upthrust zones
range edges
volatility-normalized proximity
zone quality/provenance
```

---

# M6 — Daily Entry Shadow Engine

**Priority:** P1  
**Status:** VALIDATED

## Objective

Create a separate daily-entry domain layer. Do not run the weekly scanner unchanged on daily data.

Weekly owns the thesis. Daily observes whether real-market behavior is supporting, opposing, delaying, or confirming that thesis.

### PR-F1 — Daily Entry Engine, Shadow Mode

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #260

Current shadow output:

```text
NO_WEEKLY_SETUP
WEEKLY_SETUP_NOT_ARMED
OBSERVING
```

Daily evidence is grouped as aligned, opposing, or neutral. Shadow results are explicitly non-actionable.

## PR-F2 — Behavior-Based Daily VSA Entry Evidence

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #261

### Design Principle

PR-F2 supersedes the earlier narrow plan of requiring a NO SUPPLY / TEST sequence.

**Superseded idea:**

```text
weekly bullish
+ NO SUPPLY / TEST
= entry candidate
```

**Current design:**

```text
armed weekly thesis
        ↓
recent point-in-time daily evidence
        ↓
behavior dimensions
        ↓
shadow observation only
```

Initial direction-relative behavior dimensions:

```text
OPPOSING_PRESSURE_RECEDING
ALIGNED_PRESSURE_EMERGING
REJECTION_OF_OPPOSING_MOVE
EFFORT_RESULT_ALIGNMENT
ABSORPTION
STRUCTURAL_ALIGNMENT
CONTINUATION_ALIGNMENT
```

Examples for a bullish weekly setup:

```text
NO SUPPLY / TEST / SUPPLY DRYING UP
→ opposing supply pressure receding

DEMAND COMING IN / INCREASING DEMAND / HIDDEN DEMAND
→ aligned demand emerging

STOPPING VOLUME / SELLING CLIMAX / SHAKEOUT / SPRING
→ downside rejection

RESULT > EFFORT or aligned EFFORT/RESULT evidence
→ effort-result alignment

ABSORPTION / SUPPLY ABSORPTION
→ absorption

STRUCTURAL PROGRESSION IMPROVING
→ structural alignment

STRONG UPTREND / REACCUMULATION / MARKUP evidence
→ continuation alignment
```

Bearish setups use symmetric supply/demand behavior where supported by existing evidence codes.

### Causal Requirements

- Use a bounded recent daily evidence window.
- Admit no evidence after the current daily bar.
- Do not turn opposing daily evidence into a weekly reversal.
- Do not require any one named textbook pattern.
- Do not create scores, ranking, triggers, orders, or actionability in PR-F2.
- Preserve evidence provenance for replay/audit.

### Definition of Done

- Daily behavior can be recognized without NO SUPPLY or TEST firing.
- Textbook events still contribute evidence when present.
- Future evidence cannot leak into a historical daily snapshot.
- Bearish and bullish weekly directions are handled direction-relatively.
- Shadow behavior output remains non-actionable.
- Full backend suite remains unchanged semantically outside this new shadow layer.

## PR-F3 — Next-Session Daily Trigger / Replay Output

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #262

PR-F3 consumes the validated behavior evidence from F2; it must not revert to a single-pattern mandatory trigger.

### Shadow Signal Rule

A bounded behavior snapshot can contain useful context from prior daily bars. F3 therefore distinguishes:

```text
recent behavior context
!=
fresh signal evidence
```

A replay signal is emitted only when at least one supported behavior dimension receives evidence on the current completed daily bar. Older lookback evidence remains explanatory context but cannot repeatedly re-fire the same signal on every later bar.

This is deliberately behavior-based rather than pattern-count based:

```text
armed weekly thesis
+
fresh aligned behavior evidence on current completed daily bar
→ shadow signal observed
→ exact TradingCalendar.next_session(signal)
→ pending or next-session-available replay state
```

No minimum count of named VSA patterns is required. No confidence score or production actionability is introduced.

### Replay States

```text
NO_ARMED_WEEKLY_SETUP
NO_NEW_BEHAVIOR
PENDING_NEXT_SESSION
NEXT_SESSION_AVAILABLE
```

### Causal / Safety Requirements

- Weekly setup must still be ARMED.
- Behavior direction must match the visible weekly setup direction.
- Behavior bar identity must match the daily session in the causal coordinator.
- Prior lookback evidence cannot re-emit a fresh signal by itself.
- Future evidence is already excluded by F2.
- Execution session must come from the trading calendar.
- Missing expected next-session data remains pending; never skip silently to a later bar.
- Signal bar and execution bar remain different.
- Replay output remains explicitly non-actionable.
- No price, order, alert, ranking, or production scanner behavior is introduced.

Before production trigger promotion, audit should measure for each armed weekly setup:

```text
which behavior dimensions appeared
which appeared first
bars from weekly setup to behavior confirmation
5/10/15-session forward outcome
maximum favorable excursion
maximum adverse excursion
how often price rallied/fell without a recognized behavior trigger
how often behavior appeared but failed
```

Execution invariant remains:

```text
signal bar != execution bar
```


## PR-F4 — End-to-End Weekly→Daily Shadow Pipeline

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #281

PR-F4 composes the already-validated boundaries without introducing a new
decision rule:

```text
authoritative production ScannerCandidate
        ↓
WeeklySetup materializer
        ↓
completed_daily_only()
        ↓
WeeklyDailyCoordinator
        ↓
DailyEntryEngine behavior snapshot
        ↓
DailyTriggerReplayOutput
```

The pipeline must prove, in one composition, that:

- a same-week daily bar cannot consume the Friday weekly setup,
- an actionable production candidate can become an ARMED WeeklySetup,
- non-actionable weekly candidates cannot create positive daily behavior,
- incomplete daily bars are removed before daily evaluation,
- future daily evidence cannot leak backward,
- bullish and bearish weekly directions remain symmetric,
- exact next-session timing remains pending when the expected bar is incomplete,
- all composed output remains shadow-only and non-actionable.

This orchestration accepts daily evidence that is already indexed to the completed
daily-bar sequence. It does not run the weekly scanner unchanged on daily data and
does not introduce a new daily evidence detector.

---

# M7 — Performance Consolidation

**Priority:** P1  
**Status:** VALIDATED

Work:

- precompute vectorizable features once
- reduce hot-loop DataFrame prefix copies
- emit events incrementally
- benchmark full replay and one-new-bar update
- optimize algorithms before Polars/Numba

### PR-G1 — Feature Precomputation / Hot-Loop Reduction

**Status:** VALIDATED  
**PRs:** #282, #283, #284

First safe cut: transition replay prefixes use shallow DataFrame copies so
per-bar replay does not duplicate the underlying metric column buffers.

Second safe cut: transition state now carries the existing causal SwingEngine
checkpoint. Full historical replay performs one initial swing discovery and then
uses `SwingEngine.calculate_from_state()` for subsequent bars. Production resume
seeds this state directly from the durable ScannerState, and snapshot generation
reuses the same transition swing state instead of replaying swings again.

Candidate, resume, and snapshot semantics remain protected by the existing parity
suite.

Third safe cut: confirmed structural/professional swing evaluations are now cached
inside transient transition state. Bars with no newly confirmed swing reuse the
cached structural set. When a new swing appears, only a bounded
`STRUCTURE_LOOKBACK + 1` window is rescored, preserving the existing scoring
implementation and exact point-in-time semantics.

Durable ScannerState intentionally does not persist professional structural
evaluations; the first bar after resume rebuilds them once, then transition reuse
continues.

### PR-G2 — Incremental Benchmark & Cleanup

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #285

G2 adds a deterministic, network-free benchmark for the exact causal path
optimized in G1. It measures legacy full replay, optimized transition full replay,
in-memory one-new-bar update, and durable one-new-bar resume. Candidate parity is
checked before timing is accepted; pytest does not enforce machine-dependent
latency thresholds.

The retained 192-bar / 7-repeat local measurement on 2026-09-18 showed:

- legacy full replay median: **1386.595 ms**
- transition full replay median: **1330.784 ms**
- in-memory one-new-bar median: **6.228 ms**
- durable one-new-bar resume median: **7.672 ms**
- full replay speedup: **1.042x** (~4.0% lower median wall time)
- one-new-bar vs legacy full replay: **222.653x**

Conclusion: the rolling/new-bar path achieved a material performance improvement.
Full historical replay improved only modestly and should not be described as a
large replay-speed optimization. Any further full-replay work should be a
separate measured task rather than extending G1 by assumption.

---

# M8 — Module Boundary & Python Quality Cleanup

**Priority:** P2  
**Status:** IN PROGRESS

### PR-H1 — Public Professional-Scoring Batch API

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #286

Replace cross-module access to `ProfessionalScorer` private arrays, scorers,
weights, and raw Smart Money batch values with a public position-aligned batch
contract.

The public batch must preserve:

- exact pre-H1 batched production StructureFilter semantics,
- lazy Smart Money component materialization,
- current StructureFilter thresholds and grading,
- existing batched hot-path performance.

During H1 validation, a pre-existing scalar-vs-batch discrepancy was exposed:
`ProfessionalScorer.score()` and the production batched StructureFilter path do
not build identical volume/spread history snapshots. H1 does not change or
reconcile that behavior. The compatibility gate therefore targets the actual
pre-H1 production batched path exactly; scalar/batch semantic reconciliation, if
desired, requires a separate evidence-backed change.

Benchmark tooling should also use public scoring boundaries where practical.

### PR-H2 — Domain Exceptions / Policy Boundaries

**Status:** IN PROGRESS

H2 is split into behavior-preserving cuts.

First cut: extract the scanner decision rules that already exist into named
policies while preserving the current ScannerCandidate/ScannerEngine public
surface:

```text
PatternQualificationEngine   → existing qualification authority
VSAFreshnessPolicy           → scoring window / maximum actionable VSA age
CandidateActionabilityPolicy → qualification + confidence + anomaly gate
CandidateRankingPolicy       → directional conviction ranking
CandidateExecutionPolicy     → next-bar availability/pending semantics
```

The existing ScannerEngine constants and candidate properties remain compatibility
facades. No threshold or decision rule changes in this extraction.

A later H2 cut may introduce semantic transition/recovery exception types after
the policy boundary is validated.

---

# M9 — State, Cache & Operational Robustness

**Priority:** P2  
**Status:** PLANNED

Planned work:

```text
recovery telemetry
checkpoint failure classification
state concurrency policy
cache/metadata generation consistency
corporate-action/history-revision policy
```

### PR-I1 — Recovery Telemetry + Persistence Hardening

**Status:** PLANNED

---

# M10 — Modernization & CI Quality Gates

**Priority:** P2  
**Status:** PLANNED

Candidate tooling:

```text
Ruff
Pyright or mypy
pytest-cov
Hypothesis
typing.Protocol boundaries
```

### PR-J1 — Ruff / Type / Coverage Gates

**Status:** PLANNED

---

# 3. Later Evidence Roadmap

Introduce additional evidence one at a time, read-only first:

1. richer daily VSA multi-bar behavior
2. relative strength vs market and sector
3. ATR / volatility normalization
4. anchored VWAP
5. daily structure confirmation using existing ProVSA structure machinery
6. volume-profile / auction-location context
7. market and sector context
8. Hilega Milega as read-only momentum confirmation
9. richer daily Effort/Result and Absorption evidence
10. Wyckoff campaign-phase inference only if it adds information beyond current VSA/structure
11. meta-labeling only after enough validated historical setup data exists

Avoid:

- duplicate generic trend engines
- duplicate BOS/CHOCH systems
- arbitrary indicator voting
- arbitrary confidence percentages
- hard-coded textbook-pattern gates

---

# 4. Recommended PR Sequence

| Sequence | PR | Priority | Purpose | Status |
|---:|---|---|---|---|
| 1 | PR-A / #246 | P0 | Full-vs-resume equivalence contract | VALIDATED |
| 2 | PR-B1 / #247 | P0 | Rolling-state inventory | VALIDATED |
| 3 | PR-B2 / #250 | P0 | First-class qualification state | VALIDATED |
| 4 | PR-B3 / #251 | P0 | First-class progression/event state | VALIDATED |
| 5 | PR-B4 / #252 | P0 | Canonical transition path | VALIDATED |
| 6 | PR-C1 / #253 | P0 | NSE trading calendar | VALIDATED |
| 7 | PR-C2 / #255 | P0 | Completed daily bars | VALIDATED |
| 8 | PR-C3 / #256 | P0 | Next-session execution semantics | VALIDATED |
| 9 | PR-D1 / #257 | P0 | WeeklySetup model/state | VALIDATED |
| 10 | PR-D2 / #258 | P0 | Weekly→daily causal coordinator | VALIDATED |
| 11 | PR-E1 / #259 | P1 | Weekly structural zones, read-only | VALIDATED |
| 12 | PR-F1 / #260 | P1 | Daily Entry Engine shadow | VALIDATED |
| 13 | PR-F2 / #261 | P1 | Behavior-based daily VSA entry evidence | VALIDATED |
| 14 | PR-F3 / #262 | P1 | Next-session daily trigger/replay output | VALIDATED |
| 15 | PR-F4 / #281 | P1 | End-to-end weekly→daily shadow pipeline | VALIDATED |
| 16 | PR-G1 / #282-#284 | P1 | Feature precompute/hot-loop reduction | VALIDATED |
| 17 | PR-G2 / #285 | P1 | Benchmark/cleanup | VALIDATED |
| 18 | PR-H1 / #286 | P2 | Public professional-scoring batch API | VALIDATED |
| 19 | PR-H2 | P2 | Domain exceptions/policy boundaries | IN PROGRESS |
| 20 | PR-I1 | P2 | Recovery telemetry/persistence hardening | PLANNED |
| 21 | PR-J1 | P2 | Ruff/type/coverage gates | PLANNED |

---

# 5. Release Gates

## Gate A — Scanner Refactor Safety

Core scanner refactors must preserve full-vs-resume equivalence.

## Gate B — Daily Analysis Safety

Before enabling daily signals:

- completed daily-bar gate validated
- trading-calendar semantics validated
- weekly→daily causality validated

## Gate C — Daily Entry Promotion

Before production recommendations:

- shadow/replay results collected
- no same-bar execution leakage
- behavior evidence audited historically
- setup invalidation semantics defined
- outcome methodology defined
- evidence remains read-only until promotion is justified

## Gate D — Performance Refactor

Every optimization must satisfy:

```text
same semantics
+
measurable benchmark improvement
```

---

# 6. Progress Log

| Date | PR | Milestone | Status | Result / Notes |
|---|---|---|---|---|
| 2026-09-16 | #246 | M1 | VALIDATED | Full-vs-resume equivalence contract merged; manual validation passed. |
| 2026-09-16 | #247 | M2 | VALIDATED | Rolling-state inventory merged. |
| 2026-09-16 | #250 | M2 | VALIDATED | First-class qualification state merged. |
| 2026-09-16 | #251 | M2 | VALIDATED | Structural event/progression state merged. |
| 2026-09-16 | #252 | M2 | VALIDATED | State-driven canonical transition path merged. |
| 2026-09-16 | #253 | M3 | VALIDATED | NSE trading calendar merged. |
| 2026-09-16 | #255 | M3 | VALIDATED | Completed-daily guard merged. |
| 2026-09-16 | #256 | M3 | VALIDATED | Next-session semantics merged. |
| 2026-09-16 | #257 | M4 | VALIDATED | WeeklySetup model/lifecycle merged. |
| 2026-09-16 | #258 | M4 | VALIDATED | Weekly→daily causal coordinator merged. |
| 2026-09-16 | #259 | M5 | VALIDATED | Read-only structural zones merged. |
| 2026-09-16 | #260 | M6 | VALIDATED | Shadow DailyEntryEngine merged. |
| 2026-09-16 | #261 | M6 | VALIDATED | Behavior-based daily VSA evidence merged; textbook patterns remain contributors, not gates. |
| 2026-09-16 | #262 | M6 | VALIDATED | Behavior-based fresh-signal identity and exact next-session replay output merged; focused replay tests revalidated with PR #280. |
| 2026-09-18 | #281 | M6 | VALIDATED | End-to-end production-weekly → shadow-daily composition merged and manually validated; daily output remains non-actionable. |
| 2026-09-18 | #282 | M7 | VALIDATED | Transition prefixes use shallow copies; metric column buffers are no longer duplicated per replay bar. |
| 2026-09-18 | #283 | M7 | VALIDATED | Causal SwingEngine state is reused across transition bars, production resume, and snapshot creation. |
| 2026-09-18 | #284 | M7 | VALIDATED | Stable structural swing evaluations are cached; only bounded history is rescored on new swing confirmation. |
| 2026-09-18 | #285 | M7 | VALIDATED | Deterministic benchmark retained: full replay 1.042x faster; one-new-bar update 6.228 ms / 222.653x vs legacy full replay; durable resume 7.672 ms. |
| 2026-09-18 | #286 | M8 | VALIDATED | StructureFilter now consumes the public lazy ProfessionalScorer batch API while preserving exact pre-H1 batched production semantics. |
| 2026-09-18 | PR-H2 | M8 | IN PROGRESS | Extract scanner freshness, actionability, ranking, and execution rules into explicit behavior-preserving policy objects. |

---

# 7. Current Next Action

## NEXT: PR-H2 — Scanner Policy Boundaries

Checklist:

- [x] Keep PatternQualificationEngine as the existing qualification authority.
- [x] Extract VSA freshness limits into an explicit policy.
- [x] Extract final candidate actionability into an explicit policy.
- [x] Extract directional ranking semantics into an explicit policy.
- [x] Extract execution availability/pending messaging into an explicit policy.
- [x] Preserve ScannerEngine constants and ScannerCandidate properties as compatibility facades.
- [x] Reuse the same freshness policy in legacy and state-driven evaluation.
- [x] Add direct policy boundary tests.
- [ ] Run scanner decision/freshness/ranking/execution tests.
- [ ] Run transition/resume/incremental equivalence tests.
- [ ] Confirm candidate signatures are unchanged.
- [ ] Merge after manual validation.
- [ ] Then evaluate semantic transition/recovery exception extraction as the remaining H2 cut.

---

# 8. Long-Term Target Architecture

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
                         behavior evidence
                                    │
                                    ▼
                      Shadow Trigger / Replay
                                    │
                                    ▼
                         Next-Session Execution
```

The weekly scanner remains responsible for background, structure, qualification, and direction.

The daily engine remains responsible for real-market entry evidence, location, confirmation, and execution timing.

---

# 9. Success Criteria

ProVSA should ultimately demonstrate:

1. Historical replay and production resume are semantically equivalent.
2. New-bar processing uses bounded causal state.
3. Weekly and daily timeframes synchronize without look-ahead.
4. Incomplete daily bars cannot affect decisions.
5. Weekly trend/structure remains authoritative background.
6. Daily entry is a separate domain layer.
7. Daily entry logic recognizes real-market behavior rather than demanding textbook pictures.
8. Named VSA patterns remain explainable evidence contributors.
9. Every promoted evidence source has replay/audit support.
10. Performance improvements preserve semantics.
11. Persistence/recovery failures are observable.
12. Signal and execution remain causally separated.
13. Confidence is calibrated from historical outcomes rather than arbitrary pattern counts.

---

**Document owner:** ProVSA project  
**Current milestone:** M8 — Module Boundary & Python Quality Cleanup  
**Current PR:** PR-H2 — Scanner Policy Boundaries
