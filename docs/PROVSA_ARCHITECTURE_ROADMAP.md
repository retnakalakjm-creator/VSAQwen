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
**Status:** VALIDATED

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

**Status:** MERGED + MANUALLY VALIDATED  
**PRs:** #287, #288

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

Second cut: introduce semantic transition/resume/persisted-state exception types
as subclasses of the existing ValueError contract:

```text
ScannerTransitionError
├── ScannerTransitionSequenceError
└── ScannerTransitionStateMismatchError

ScannerResumeError
├── ScannerResumeMetricsError
├── ScannerResumeCheckpointMissingError
└── ScannerResumeCheckpointBeyondMetricsError

ScannerStateError
├── ScannerStateCorruptError
├── ScannerStateSchemaError
└── ScannerStateIdentityError
```

Existing callers that catch `ValueError` remain compatible. This cut does not
change fallback codes, replay policy, or recovery behavior; more granular runtime
telemetry belongs in M9.

---

# M9 — State, Cache & Operational Robustness

**Priority:** P2  
**Status:** VALIDATED

Planned work:

```text
recovery telemetry
checkpoint failure classification
state concurrency policy
cache/metadata generation consistency
corporate-action/history-revision policy
```

### PR-I1 — Recovery Telemetry + Persistence Hardening

**Status:** MERGED + MANUALLY VALIDATED  
**PRs:** #289, #290, #291

First cut: preserve the existing human-readable `fallback_diagnostics` channel
while adding structured `ScannerRecoveryEvent` telemetry.

Each fallback event records:

```text
code
phase (LOAD_VALIDATE or RESUME)
reason
symbol
timeframe
exception_type
fallback_used
```

The event's rendered message must remain byte-for-byte equivalent to the existing
diagnostic string so current operators/consumers do not break.

This cut does not change fallback codes, fallback eligibility, scanner decisions,
or persisted-state schema.

Second cut: classify atomic checkpoint write failures as
`ScannerStateWriteError` (an `OSError` subtype) and emit a structured
`PERSIST` recovery event before re-raising. Failed writes remain fail-closed:
they do not return a candidate as if persistence succeeded, do not emit a fake
full-replay fallback diagnostic, preserve the last good checkpoint, and clean up
temporary files.

Third cut: production checkpoint persistence uses a per-checkpoint cross-process
OS file lock plus revision compare-and-swap. The production scanner carries the
exact persisted-byte revision it loaded and saves only if that revision is still
current.

This prevents:

```text
process A loads checkpoint K
process B advances and persists checkpoint K+1
process A finishes later
→ A must not overwrite K+1 with stale state
```

A conflict raises `ScannerStateConflictError`, emits
`PERSIST / CHECKPOINT_WRITE_CONFLICT` structured telemetry, preserves the newer
checkpoint, and fails closed. Plain `ScannerStateStore.save()` remains available
for explicit unconditional writes while serializing writers through the same
cross-process lock.

---

### PR-I2 — Cache / Metadata Generation Consistency

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #292

Daily cache data and the metadata sidecar are separate filesystem artifacts.
I2 makes that relationship observable and serializes same-symbol writers without
turning metadata into a scanner gate.

New cache metadata writes include a `generation_id` derived from the exact
finalized data-file SHA-256. Same-symbol data/metadata commits are protected by a
cross-process lock. `inspect_cache_generation()` reports whether the sidecar and
current cache file belong to the same generation.

Version-1 metadata remains readable and is reported as legacy/unverified until the
next cache rewrite.

Safety boundary:

```text
generation mismatch
→ operational diagnostic / repair signal
!=
market-data invalidation
!=
scanner decision input
```

---

### PR-I3 — Historical Revision / Corporate-Action Audit Policy

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #293

Routine production refresh remains incremental, so provider corrections older than
the recent merge window require an explicit audit path.

I3 adds a read-only raw-history comparison:

```text
current usable cache
        +
fresh provider production-history download
(auto_adjust=False)
        ↓
overlapping daily identity + OHLCV comparison
        ↓
MATCH / REVISION_DETECTED / NO_CACHE / NO_OVERLAP
```

The audit reports changed dates and columns plus appended provider rows. It does
not mutate cache data or metadata.

Policy boundary:

```text
REVISION_DETECTED
!=
CORPORATE_ACTION_CONFIRMED
```

OHLCV changes alone cannot distinguish a split/dividend/bonus/merger from an
exchange/provider correction. Corporate-action attribution therefore requires a
separate authoritative event source if later needed.

If revised history is explicitly rebuilt later, the existing ScannerState data
fingerprint remains the downstream safety gate: old checkpoints are rejected and
the existing replay fallback rebuilds state.

---

# M10 — Modernization & CI Quality Gates

**Priority:** P2  
**Status:** VALIDATED

Candidate tooling:

```text
Ruff
Pyright or mypy
pytest-cov
Hypothesis
typing.Protocol boundaries
```

### PR-J1 — Ruff / Type / Coverage Gates

**Status:** MERGED + MANUALLY VALIDATED  
**PRs:** #294, #295, #296, #297

J1 is staged to avoid a repository-wide non-semantic rewrite.

First cut:

- install Python CI tooling from `requirements-ci.txt`,
- gate active production/test code with high-signal Ruff correctness rules only,
- run the existing pytest suite with a measured core coverage report,
- do not enforce an arbitrary coverage percentage before observing the baseline,
- do not enable repository-wide static typing before stable public boundaries are
  inventoried.

See `docs/PYTHON_QUALITY_GATES.md`.

Validated first-cut baseline on Windows / Python 3.13.15:

```text
Ruff: all checks passed
pytest: 1018 passed, 1 skipped
coverage: 74% (5500 statements / 1437 missed)
```

Second J1 cut (#295) validated strict mypy on the stable public/domain boundary
modules `scanner_exceptions.py`, `scanner_recovery.py`, `scanner_policy.py`,
and `weekly_setup.py`.

Third J1 cut (#296) validated the strict island expansion to the non-pandas
weekly→daily domain handoff:

```text
weekly_setup_materializer.py
daily_behavior.py
daily_entry.py
```

Pandas/session/replay infrastructure remains outside strict typing.

Final J1 cut promotes a conservative 70% aggregate core-package coverage floor
against the validated 74% baseline. The margin is deliberate: protect against
large regressions without freezing legitimate refactors or pretending that low
coverage in individual modules is solved by the aggregate percentage.

---

# M11 — Daily Evidence Enrichment & Sequence Audit

**Priority:** P1  
**Status:** IN PROGRESS

Objective: enrich shadow daily evidence without creating a new production trigger,
score, ranking rule, or mandatory textbook sequence.

### PR-K1 — Read-Only Daily Behavior Sequence Audit

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #298

The existing DailyBehaviorSnapshot aggregates supported dimensions inside a bounded
recent window. K1 adds a separate temporal audit that preserves the exact bars on
which those already-supported dimensions appeared.

```text
bounded evidence window
        ↓
existing per-bar DailyBehavior mapping
        ↓
ordered sparse behavior steps
        ↓
first / last / repeated occurrence audit
```

K1 does not introduce a preferred sequence. An observed order such as opposing
pressure receding → aligned pressure emerging remains descriptive only.

Safety boundary:

```text
sequence observation
!=
sequence score
!=
entry trigger
!=
production actionability
```

See `docs/DAILY_BEHAVIOR_SEQUENCE_AUDIT.md`.

### PR-K2 — Daily Behavior Sequence Outcome Study

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #299

K2 reuses the existing analysis-only `audit.outcomes` next-bar execution
contract to measure fresh K1 sequence observations without changing production.

Causal rule:

```text
fresh sequence observed on bar N
        ↓
execution starts on bar N + 1
        ↓
forward horizon / MFE / MAE
```

A bounded sequence is scored only when at least one supported sequence step is
present on its current `end_bar_index`. If the latest supported step is older
than the target bar, K2 emits no outcome observation for that stale snapshot.
This prevents retrospectively scoring returns that began before the sequence was
known at the requested target.

Exact sequence cohorts use relative offsets from the signal bar, preserving order
and spacing while avoiding calendar/index identity leakage.

Latest observations with no next bar are retained with unavailable outcomes.
Descriptive return summaries use fully completed horizons only.

Safety boundary:

```text
sequence outcome statistics
!=
sequence ranking
!=
trigger promotion
!=
production actionability
```

See `docs/DAILY_BEHAVIOR_SEQUENCE_OUTCOME_STUDY.md`.

### PR-K3 — Reproducible Multi-Symbol Daily Sequence Historical Runner

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #300

K3 runs K1/K2 across explicit prepared point-in-time research inputs without
inventing a second daily evidence detector or reconstructing weekly setup
visibility.

Prepared input boundary:

```text
symbol
completed daily close/high/low history
point-in-time weekly direction assignments by daily bar
point-in-time daily Evidence
```

Each prepared symbol input is fingerprinted over the exact fields consumed by the
study. Optional expected fingerprints can gate reruns.

Universe policy is fail-fast by default. Explicit per-symbol continuation writes
an exact failure ledger so a broad study cannot silently shrink its universe.

Outputs include:

- study summary;
- input fingerprint manifest;
- failure ledger;
- per-bar sequence records;
- causal K2 outcomes;
- exact-signature descriptive summaries.

Safety boundary:

```text
reproducible historical study
!=
daily evidence detector
!=
sequence promotion
!=
production actionability
```

See `docs/DAILY_BEHAVIOR_SEQUENCE_HISTORICAL_RUNNER.md`.

### PR-K4 — Frozen Prepared Daily Sequence Dataset Contract

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #301

K4 makes the K3 prepared-input boundary portable without fabricating a real daily
dataset from weekly artifacts.

Frozen datasets carry:

```text
mandatory source provenance
1D price/evidence timeframe identity
daily close/high/low bars
point-in-time weekly direction assignments
full Evidence records
embedded K3 fingerprints
```

The writer recomputes retained fingerprints before writing. The loader rebuilds
the K3 inputs, recomputes fingerprints, and fails closed if price, direction, or
evidence content has been changed.

A loaded dataset can then run through K3 with its retained fingerprints as the
expected baseline.

Current real-data boundary:

```text
available saved weekly audit artifacts
!=
genuine point-in-time daily evidence dataset
```

K4 therefore defines the interchange/readiness contract only. A real frozen case
must wait for a genuine daily-evidence export or reviewed daily casebook.

See `docs/DAILY_BEHAVIOR_SEQUENCE_DATASET_CONTRACT.md`.

### PR-K5 — Offline Point-in-Time Daily Evidence Producer

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #302

K5 provides the genuine daily-evidence source required by K4 without introducing
a competing detector.

For each completed daily target bar, K5 reuses the existing ProVSA stack:

```text
raw completed daily prefix
→ MetricsEngine
→ SwingEngine
→ StructureFilter
→ TrendAnalyzer
→ EvidenceEngine
→ current-target Evidence only
```

The future suffix is never passed into the stack. Metrics are recomputed from
each raw prefix in this first research cut so the no-look-ahead boundary is
explicit.

The legacy `Evidence.week_beginning` field carries the exact daily session
identity inside this audit path; that compatibility field name does not make the
evidence weekly.

K5 fingerprints the exact completed raw OHLCV source and keeps all outputs
explicitly non-actionable.

It does not run ScannerEngine qualification/ranking/actionability and does not
infer the weekly direction needed by K3/K4.

See `docs/OFFLINE_DAILY_EVIDENCE_PRODUCER.md`.

### PR-K6 — Causal Weekly-Direction Assignment Exporter

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #303

K6 supplies the remaining point-in-time input required by K4/K3 without deriving
weekly direction from daily prices.

For each completed daily bar:

```text
WeeklySetup history
→ WeeklyDailyCoordinator
→ causally visible setup
→ emit direction only when setup is ARMED
→ K3-compatible bar-indexed direction assignment
```

The same-week Friday setup cannot leak into Monday-Friday bars from its own signal
week. Visibility starts on the next valid exchange session according to the
existing TradingCalendar.

K6 fingerprints the exact completed-session identities plus the relevant setup
identity/direction/status/availability inputs. Outputs remain explicitly
non-actionable.

See `docs/CAUSAL_WEEKLY_DIRECTION_ASSIGNMENTS.md`.

### PR-K7 — K5 + K6 Frozen K4 Dataset Composer

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #304

K7 composes the validated daily research producers into the existing K4
interchange boundary:

```text
completed daily OHLCV
├── K5 point-in-time daily Evidence
└── K6 causal ARMED weekly direction
          ↓
DailyBehaviorSequenceStudyInput
          ↓
K4 frozen dataset
```

K5 and K6 independently receive the same daily source, now boundary, and trading
calendar. Their retained completed-session identities must match exactly before
K7 freezes the input; any mismatch fails closed.

The K4 source metadata retains both K5 and K6 source fingerprints. K7 remains
analysis-only and does not alter production qualification, scoring, F3,
actionability, alerts, or orders.

The repository does not fabricate a real-data fixture. After K7 validation, the
first genuine case will be generated from actual daily market history plus
historical production-weekly WeeklySetup outputs.

See `docs/DAILY_BEHAVIOR_SEQUENCE_PREPARATION.md`.

### PR-K8 — Genuine Real-Market Frozen Case Generator

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #305

K8 derives historical WeeklySetup objects only through the existing production
weekly path:

```text
actual daily market history
→ completed daily sessions
→ daily_to_weekly
→ completed_weekly_only
→ MetricsEngine
→ HistoricalScannerRunner
→ production ScannerCandidate
→ materialize_production_weekly_setup
→ WeeklySetup history
```

That WeeklySetup history is passed into K7, which continues to own K5/K6/K4
composition.

K8 fingerprints the exact completed weekly OHLCV consumed by the production
weekly scanner path and adds that fingerprint to the frozen dataset provenance.

If the selected history contains no actionable persistent production weekly
setup, K8 fails closed instead of fabricating one.

See `docs/GENUINE_DAILY_SEQUENCE_CASE.md`.

### PR-K9 — Frozen K4 → K3/K2/K1 Study Runner

**Status:** MERGED + MANUALLY VALIDATED  
**PR:** #306

K9 loads an already-frozen K4 dataset, verifies its embedded fingerprint, passes
the unchanged prepared inputs and fingerprints into K3, and writes the existing
K3 study bundle.

```text
frozen K4 JSON
→ K4 fingerprint verification
→ K3 historical runner
→ K1 sequence audit + K2 outcomes
→ existing JSON/CSV review bundle
```

K9 does not recompute K5 Evidence, K6 weekly directions, or K8 production-weekly
authority. It adds no ranking or actionability.

The CLI also reports bullish/bearish weekly-direction assignment counts as a
diagnostic. It does not rebalance or reinterpret them.

See `docs/FROZEN_DAILY_SEQUENCE_STUDY.md`.

### PR-K10 — Production Weekly Authority Audit Ledger

**Status:** IN PROGRESS

K10 explains the first LT.NS real-study asymmetry without changing weekly
qualification or coordinator behavior.

It separates:

```text
production WeeklySetup rows created
!=
WeeklySetup selected as daily authority
```

For every production-authorized setup, K10 records direction, signal week,
completion/availability timing, and the exact daily-session span where the
existing coordinator selected it.

The summary independently reports setup direction counts and daily assignment
direction counts. This allows the LT 37-setup / 463-all-bearish result to be
localized to production qualification versus coordinator authority timing.

See `docs/WEEKLY_AUTHORITY_AUDIT.md`.


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
| 19 | PR-H2 / #287-#288 | P2 | Domain exceptions/policy boundaries | VALIDATED |
| 20 | PR-I1 / #289-#291 | P2 | Recovery telemetry/persistence hardening | VALIDATED |
| 21 | PR-I2 / #292 | P2 | Cache/metadata generation consistency | VALIDATED |
| 22 | PR-I3 / #293 | P2 | Historical revision/corporate-action audit policy | VALIDATED |
| 23 | PR-J1 / #294-#297 | P2 | Ruff/type/coverage gates | VALIDATED |
| 24 | PR-K1 / #298 | P1 | Read-only daily behavior sequence audit | VALIDATED |
| 25 | PR-K2 / #299 | P1 | Analysis-only daily behavior sequence outcome study | VALIDATED |
| 26 | PR-K3 / #300 | P1 | Reproducible multi-symbol daily sequence historical runner | VALIDATED |
| 27 | PR-K4 / #301 | P1 | Frozen prepared daily sequence dataset contract | VALIDATED |
| 28 | PR-K5 / #302 | P1 | Offline point-in-time daily evidence producer using existing VSA stack | VALIDATED |
| 29 | PR-K6 / #303 | P1 | Causal weekly-direction assignments from WeeklySetup/Coordinator | VALIDATED |
| 30 | PR-K7 / #304 | P1 | Compose K5 Evidence + K6 directions into frozen K4 dataset | VALIDATED |
| 31 | PR-K8 / #305 | P1 | Generate genuine frozen K4 case from production weekly authority + real daily history | VALIDATED |
| 32 | PR-K9 / #306 | P1 | Run frozen K4 through unchanged K3/K2/K1 and write review bundle | VALIDATED |
| 33 | PR-K10 | P1 | Audit production weekly setup directions versus causal daily authority spans | IN PROGRESS |

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
| 2026-09-18 | #287 | M8 | VALIDATED | Scanner freshness, actionability, ranking, and execution rules extracted into explicit behavior-preserving policy objects. |
| 2026-09-18 | #288 | M8 | VALIDATED | Semantic transition/resume/persisted-state exceptions merged with ValueError compatibility and unchanged production fallback behavior. |
| 2026-09-18 | #289 | M9 | VALIDATED | Structured LOAD_VALIDATE/RESUME recovery telemetry merged alongside unchanged legacy fallback diagnostics. |
| 2026-09-18 | #290 | M9 | VALIDATED | Atomic persistence write failures are observable through PERSIST telemetry and fail closed while preserving last-good state. |
| 2026-09-18 | #291 | M9 | VALIDATED | Cross-process checkpoint lock + revision CAS prevents stale production writers from replacing newer state. |
| 2026-09-18 | #292 | M9 | VALIDATED | Cache metadata is bound to exact file generations; same-symbol cache/metadata writes are serialized and mismatch remains diagnostic-only. |
| 2026-09-18 | #293 | M9 | VALIDATED | Read-only raw-history revision audit detects older provider corrections without mutating cache or inferring corporate-action cause. |
| 2026-09-18 | #294 | M10 | VALIDATED | Ruff correctness gate passes; full suite 1018 passed / 1 skipped; measured core coverage baseline is 74% on Windows Python 3.13.15. |
| 2026-09-18 | #295 | M10 | VALIDATED | Strict mypy gate validated for scanner exceptions/recovery/policy and WeeklySetup public domain boundaries. |
| 2026-09-18 | #296 | M10 | VALIDATED | Strict mypy expanded to WeeklySetup materialization plus daily behavior/entry domain with no runtime changes. |
| 2026-09-18 | #297 | M10 | VALIDATED | 70% aggregate core coverage floor validated at 73.87%; full suite 1018 passed / 1 skipped. |
| 2026-09-18 | #298 | M11 | VALIDATED | Read-only daily behavior sequence audit preserves temporal ordering without changing F3 trigger/replay behavior. |
| 2026-09-18 | #299 | M11 | VALIDATED | Causal next-bar outcomes attach only to fresh current-bar sequence observations; study remains descriptive and non-actionable. |
| 2026-09-18 | #300 | M11 | VALIDATED | Reproducible multi-symbol K1/K2 runner validated with fingerprints, failure ledger, and stable research artifacts. |
| 2026-09-18 | #301 | M11 | VALIDATED | Frozen 1D sequence-study dataset contract validates provenance/timeframe/schema and fails closed on fingerprint mismatch. |
| 2026-09-18 | #302 | M11 | VALIDATED | Offline point-in-time daily Evidence producer manually validated locally after merge; hosted CI unavailable due usage limits. |
| 2026-09-18 | #303 | M11 | VALIDATED | Causal weekly-direction exporter manually validated locally and merged; same-week leakage remains blocked and output stays non-actionable. |
| 2026-09-18 | #304 | M11 | VALIDATED | K5/K6 composer manually validated locally and merged; exact completed-session alignment and K4 round-trip gates passed. |
| 2026-09-18 | #305 | M11 | VALIDATED | Real-market generator manually validated and merged; LT.NS produced 1246 daily bars, 37 production-weekly setups, 463 weekly-direction assignments, and a frozen non-actionable K4 dataset. |
| 2026-09-18 | #306 | M11 | VALIDATED | First frozen LT.NS study completed with the original K4 fingerprint, 463 records, 65 fresh sequences, 325 horizon observations, 85 signature summaries, and zero symbol failures. |
| 2026-09-18 | PR-K10 | M11 | IN PROGRESS | Explain LT.NS weekly-authority asymmetry by comparing production WeeklySetup direction history with exact daily coordinator selection spans. |

---

# 7. Current Next Action

## NEXT: PR-K10 — Production Weekly Authority Audit Ledger

Checklist:

- [x] Mark #306 / K9 validated and merged from the successful frozen LT study bundle.
- [x] Preserve the original LT K4 fingerprint and non-actionable study boundary.
- [x] Reuse K8 production weekly setup derivation unchanged.
- [x] Reuse K6 causal coordinator assignments unchanged.
- [x] Separate production setup direction counts from daily assignment direction counts.
- [x] Record setup signal week, completion session, and first available daily session.
- [x] Record selected daily count plus first/last selected session per setup.
- [x] Preserve production-weekly and K6 source fingerprints in the audit summary.
- [x] Add a read-only CLI for LT.NS.
- [x] Add deterministic bullish→bearish and all-bearish audit tests.
- [x] Keep all output explicitly non-actionable.
- [x] Add K10 module/CLI to Ruff.
- [ ] Run focused K10 + K8 + K6 tests locally.
- [ ] Run Ruff locally.
- [ ] Run K10 against LT.NS at the same 2026-09-18 cutoff.
- [ ] Compare setup_direction_counts with assignment_direction_counts.
- [ ] Inspect which setup first became selected on 2024-11-11.
- [ ] Determine whether any bullish production WeeklySetup exists among the 37 rows.
- [ ] Merge after manual validation.
- [ ] Only then decide whether to broaden real frozen studies to multiple symbols or investigate production-weekly asymmetry further.

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
**Current milestone:** M11 — Daily Evidence Enrichment & Sequence Audit  
**Current PR:** PR-K10 — Production Weekly Authority Audit Ledger
