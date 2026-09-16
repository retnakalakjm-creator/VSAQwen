# ProVSA Architecture Remediation Roadmap

**Status:** Active / Living Document  
**Primary product direction:** Weekly-timeframe VSA background/qualification followed by daily-timeframe entry timing.  
**Update policy:** Update this document whenever a roadmap PR is started, merged, validated, superseded, or materially redesigned.  
**Last updated:** 2026-09-16

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
**Status:** IN PROGRESS

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

**Status:** IN PROGRESS

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

**Status:** PLANNED

PR-F3 must consume validated behavior evidence; it must not revert to a single-pattern mandatory trigger.

Before trigger promotion, audit should measure for each armed weekly setup:

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

Trigger logic remains read-only/shadow until evidence supports promotion.

Execution invariant remains:

```text
signal bar != execution bar
```

---

# M7 — Performance Consolidation

**Priority:** P1  
**Status:** PLANNED

Work:

- precompute vectorizable features once
- reduce hot-loop DataFrame prefix copies
- emit events incrementally
- benchmark full replay and one-new-bar update
- optimize algorithms before Polars/Numba

### PR-G1 — Feature Precomputation / Hot-Loop Reduction

**Status:** PLANNED

### PR-G2 — Incremental Benchmark & Cleanup

**Status:** PLANNED

---

# M8 — Module Boundary & Python Quality Cleanup

**Priority:** P2  
**Status:** PLANNED

### PR-H1 — Public Professional-Scoring Batch API

Remove cross-module reliance on private scorer members.

### PR-H2 — Domain Exceptions / Policy Boundaries

Separate concepts such as:

```text
QualificationPolicy
FreshnessPolicy
ActionabilityPolicy
RankingPolicy
ExecutionPolicy
```

and introduce semantic recovery/transition exceptions.

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
| 13 | PR-F2 | P1 | Behavior-based daily VSA entry evidence | IN PROGRESS |
| 14 | PR-F3 | P1 | Next-session daily trigger/replay output | PLANNED |
| 15 | PR-G1 | P1 | Feature precompute/hot-loop reduction | PLANNED |
| 16 | PR-G2 | P1 | Benchmark/cleanup | PLANNED |
| 17 | PR-H1 | P2 | Public professional-scoring batch API | PLANNED |
| 18 | PR-H2 | P2 | Domain exceptions/policy boundaries | PLANNED |
| 19 | PR-I1 | P2 | Recovery telemetry/persistence hardening | PLANNED |
| 20 | PR-J1 | P2 | Ruff/type/coverage gates | PLANNED |

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
| 2026-09-16 | PR-F2 | M6 | IN PROGRESS | Reframed from NO SUPPLY/TEST sequence to behavior-based daily VSA evidence. |

---

# 7. Current Next Action

## NEXT: PR-F2 — Behavior-Based Daily VSA Entry Evidence

Checklist:

- [x] Keep weekly direction authoritative.
- [x] Define direction-relative behavior dimensions.
- [x] Treat NO SUPPLY / TEST as evidence, not mandatory gates.
- [x] Use bounded recent evidence only.
- [x] Exclude future evidence.
- [x] Keep output read-only/non-actionable.
- [ ] Run focused F2 tests.
- [ ] Run full backend suite.
- [ ] Merge after manual validation.
- [ ] Update roadmap status to VALIDATED after merge.

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
**Current milestone:** M6 — Daily Entry Shadow Engine  
**Current PR:** PR-F2 — Behavior-Based Daily VSA Entry Evidence
