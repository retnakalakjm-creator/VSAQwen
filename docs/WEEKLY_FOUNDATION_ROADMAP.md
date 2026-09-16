# ProVSA Weekly Foundation Roadmap

**Status:** Active / Current Priority  
**Priority:** P0/P1 — strengthen weekly foundation before continuing later architecture/performance work  
**Primary product direction:** Weekly timeframe establishes market campaign/background/direction; daily timeframe provides entry timing.  
**Current milestone:** WF2 — WeeklyBehaviorState Shadow Model — IN PROGRESS  
**Created:** 2026-09-16

### Current progress

```text
WF0 — Baseline Freeze and Safety Contract         VALIDATED / MERGED PR #264
WF1 — Weekly Decision-Gate Audit                  VALIDATED / MERGED PR #265
WF2 — WeeklyBehaviorState Shadow Model            IN PROGRESS
WF3+                                                NOT STARTED / BLOCKED BY SEQUENCE
```

---

## 1. Why This Roadmap Exists

ProVSA's weekly side already contains strong market-structure, trend, VSA evidence, professional-scoring, campaign, and causal replay machinery. The current weakness is not the lower-level sensing layer. The weakness is the final weekly decision boundary, where rich evidence is compressed through a relatively narrow structural qualification and named-VSA confirmation gate.

The weekly foundation must therefore be strengthened before more optimization or downstream promotion work continues.

The goal is **not** to rewrite weekly ProVSA. The goal is to preserve the validated foundation and replace only the parts that prevent the system from reasoning from real market behavior.

Core statement:

```text
Weekly foundation: KEEP and strengthen.
Weekly decision semantics: AUDIT, shadow, validate, then promote.
Daily work completed so far: PRESERVE.
Later roadmap work: RESUME only after weekly foundation gate passes.
```

---

## 2. Product Contract

The intended multi-timeframe relationship remains:

```text
WEEKLY
    determines background / campaign / direction / structural context

DAILY
    determines timing / confirmation / execution opportunity
```

The weekly side must answer:

```text
What campaign is developing?
Which side has control?
Is that control improving, weakening, or being challenged?
Is the market behavior consistent with accumulation, distribution,
continuation, correction, rejection, absorption, or structural failure?
```

The daily side must answer:

```text
Is there a defensible timing opportunity now,
using only completed daily evidence that was knowable at that point in time?
```

Daily evidence must never silently redefine the weekly campaign.

---

## 3. Non-Negotiable Principles

### 3.1 Real-market evidence over textbook pattern dependency

Real markets do not reliably create perfect textbook sequences.

Named VSA events such as:

```text
NO SUPPLY
TEST
SPRING
SHAKEOUT
STOPPING VOLUME
DEMAND COMING IN
INCREASING DEMAND
SELLING CLIMAX
UPTHRUST
NO DEMAND
ABSORPTION
```

remain useful evidence, but no single named event should automatically become a universal mandatory weekly gate unless historical validation proves that requirement is necessary.

The system should reason from the behavior expressed by evidence.

### 3.2 Preserve causality

All weekly reasoning must remain point-in-time.

```text
No future weekly bar
No future swing confirmation
No future structural event
No future evidence
No future daily information
```

may influence a historical weekly state.

### 3.3 Preserve the signal/execution distinction

Weekly setup formation, daily signal observation, and next-session execution remain separate concepts.

### 3.4 Audit before production promotion

New weekly behavior semantics must first be read-only/shadow.

```text
detect
→ expose
→ replay
→ compare
→ validate
→ promote only if justified
```

### 3.5 Do not create duplicate engines

Do not build a second trend engine, second swing engine, second BOS/CHOCH system, or generic indicator-voting framework.

Existing structural machinery is the source of truth unless a concrete defect is proven.

### 3.6 One opposing bar is not automatically a campaign reversal

Weekly campaign logic must distinguish between:

```text
minor contradiction
meaningful contradiction
campaign weakening
structural invalidation
```

without assuming that every opposing weekly VSA event invalidates the thesis.

### 3.7 Structural failure remains important

Moving away from rigid named-pattern gates does not mean weakening structural invalidation.

Confirmed structural failure, failed support/resistance behavior, persistent opposing pressure, or materially deteriorating professional swing quality may still invalidate a thesis when historically validated.

---

## 4. Existing Weekly Components to Preserve

The following are considered part of the strong foundation and should not be rewritten without evidence of a defect.

| Component | Decision |
|---|---|
| Daily-to-weekly aggregation | KEEP |
| Completed-week guardrail | KEEP |
| MetricsEngine | KEEP |
| SwingEngine | KEEP |
| confirmed swing semantics | KEEP |
| StructureFilter | KEEP |
| structural swing professional scoring | KEEP |
| HH / HL / LH / LL classification | KEEP |
| TrendDirection | KEEP |
| TrendState | KEEP |
| structural pattern detection | KEEP |
| structural progression events | KEEP |
| Supply evidence collectors | KEEP |
| Demand evidence collectors | KEEP |
| Spring / shakeout / other named detectors | KEEP as evidence |
| Campaign context | KEEP |
| Effort / Result | KEEP; continue audit |
| Absorption | KEEP; continue audit |
| ProfessionalScoringEngine | KEEP core behavior |
| Evidence provenance | KEEP |
| calibrated evidence weights | KEEP initially |
| Weekly structural support/resistance zones | KEEP |
| full-vs-resume equivalence contract | KEEP |
| canonical transition/replay path | KEEP |
| Weekly→Daily causal coordinator | KEEP |
| Daily behavior/replay work from M6 | KEEP |

---

## 5. Current Weekly Weaknesses to Address

### 5.1 Structural qualification is too narrow

The current qualification layer is driven by repeated structural progression events and can require a specific persistence sequence before a weekly thesis becomes qualified.

That protects against noise, but it can also delay recognition of a real campaign when other evidence is already strong.

The roadmap must determine empirically whether the current persistence requirement is:

```text
appropriately conservative
or
materially late / incomplete
```

### 5.2 Final directional-VSA confirmation is too discrete

The scanner currently reduces recent weekly VSA evidence into named bullish/bearish code sets and can require a directional named confirmation while rejecting opposing named evidence.

The risk is that rich evidence such as:

```text
absorption
reduced downside result
improving effort/result
support holding
professional swing improvement
campaign strength
```

may be visible but still fail the final actionability gate because a specific named code did not fire.

### 5.3 Read-only evidence is visible but underused by design

Effort/Result, Absorption, and some other evidence are intentionally read-only for production safety.

That governance remains correct, but the new weekly audit must measure whether these observations add material predictive or decision value before any promotion.

### 5.4 WeeklySetup is tightly coupled to the current qualification enum

The existing `WeeklySetup` domain model expects persistent bullish/bearish qualification.

If shadow testing proves that a valid weekly thesis can emerge from a broader behavior state before legacy persistent qualification, the model may eventually need a more general qualification/thesis representation.

That change must happen late in this roadmap, not first.

### 5.5 Event-specific exceptions can accumulate into another rule engine

Existing event-specific scoring gates were introduced for concrete reasons and should not be removed casually.

However, future remediation should prefer:

```text
regime-conditioned evidence quality
```

over an ever-growing collection of ad-hoc event-specific exceptions.

---

## 6. Target Weekly Architecture

Target concept:

```text
                 COMPLETED WEEKLY OHLCV
                           │
                           ▼
                      MetricsEngine
                           │
             ┌─────────────┴─────────────┐
             │                           │
             ▼                           ▼
      Trend / Structure             VSA Evidence
             │                           │
             │        ┌──────────────────┤
             │        │                  │
             ▼        ▼                  ▼
      Swing quality  Supply/Demand   Effort/Result
             │                           │
             ├──────────────┬────────────┤
             │              │            │
             ▼              ▼            ▼
       Progression       Absorption    Rejection
             │              │            │
             └──────────────┼────────────┘
                            ▼
                 WEEKLY BEHAVIOR STATE
                            │
                ┌───────────┴───────────┐
                │                       │
                ▼                       ▼
        aligned campaign         contradictions
                │                       │
                └───────────┬───────────┘
                            ▼
                    WEEKLY THESIS
                            │
                            ▼
                      WeeklySetup
                            │
                            ▼
                    DAILY ENTRY ENGINE
```

The key change is:

```text
Current tendency:
Named/structural events → qualification

Target:
All point-in-time weekly evidence
→ behavior state
→ campaign interpretation
→ thesis qualification
```

Named events remain evidence and provenance, not universal mandatory gates.

---

## 7. Proposed Weekly Behavior Dimensions

The first shadow model should describe behavior, not assign arbitrary scores.

Candidate dimensions:

```text
SUPPLY_PRESSURE_PRESENT
SUPPLY_PRESSURE_RECEDING
SUPPLY_PRESSURE_EXPANDING

DEMAND_PRESSURE_PRESENT
DEMAND_PRESSURE_RECEDING
DEMAND_PRESSURE_EXPANDING

EFFORT_RESULT_SUPPORTIVE
EFFORT_RESULT_CONTRADICTORY

ABSORPTION_PRESENT
REJECTION_PRESENT

STRUCTURAL_DIRECTION_ALIGNED
STRUCTURAL_DIRECTION_OPPOSED
STRUCTURAL_QUALITY_IMPROVING
STRUCTURAL_QUALITY_WEAKENING

CAMPAIGN_PERSISTENCE_PRESENT
CONTINUATION_ACCEPTANCE_PRESENT

LOCATION_SUPPORTIVE
LOCATION_OPPOSED

CONTRADICTION_MINOR
CONTRADICTION_MEANINGFUL
STRUCTURAL_INVALIDATION_EVIDENCE
```

Exact names are not frozen by this roadmap. They must map to existing domain evidence cleanly and remain auditable.

Do **not** introduce a synthetic confidence percentage in the first shadow model.

---

# WF0 — Baseline Freeze and Safety Contract

**Priority:** P0  
**Status:** VALIDATED / MERGED PR #264

## Objective

Freeze the current weekly production semantics as the legacy baseline before changing qualification behavior.

### Work

- Capture the current weekly candidate/qualification outputs in deterministic replay fixtures.
- Preserve existing full-vs-resume equivalence.
- Record current weekly qualification, actionability, scoring evidence, and reason codes for representative replay windows.
- Make legacy output directly comparable with later shadow output.
- Do not change production qualification.

### Definition of Done

```text
Same input weekly history
→ same legacy output before/after shadow instrumentation
```

and the baseline is reproducible in tests/audit.

### Suggested PR

**PR-WF0 — Freeze weekly legacy decision baseline**

---

# WF1 — Weekly Decision-Gate Audit

**Priority:** P0  
**Status:** VALIDATED / MERGED PR #265

## Objective

Measure where the current qualification/actionability boundary discards or delays otherwise useful weekly evidence.

### Audit record per weekly bar

Capture at minimum:

```text
symbol
week
trend direction
trend state
structural pattern
structural swing lineage
structural progression events
legacy qualification
legacy qualification reason
legacy actionable state
legacy scoring evidence
legacy scoring evidence age
all current evidence
all recent evidence within bounded window
read-only effort/result evidence
read-only absorption evidence
support/resistance location
campaign observations
professional strength/weakness/pressure/confidence
```

### Explicit audit questions

Identify cases where:

```text
1. Behavior looked directionally coherent but persistent qualification never formed.
2. Persistent qualification formed materially after behavior was already visible.
3. Persistent qualification existed but named-VSA confirmation was absent.
4. One opposing named event rejected an otherwise coherent campaign.
5. Effort/Result supported the thesis but was excluded from confirmation.
6. Absorption supported the thesis but was excluded from confirmation.
7. Legacy qualification fired although broader behavior was contradictory.
8. Structural invalidation happened before the legacy gate recognized the change.
```

### Output

Read-only audit/reporting only.

### Suggested PR

**PR-WF1 — Add weekly decision-gate audit output**

---

# WF2 — WeeklyBehaviorState Shadow Model

**Priority:** P0/P1  
**Status:** IN PROGRESS

## Objective

Create a first-class immutable weekly behavior state assembled from existing point-in-time evidence.

### Candidate model

Conceptually:

```python
WeeklyBehaviorState:
    week
    structural_context
    trend_context
    supply_evidence
    demand_evidence
    effort_result_evidence
    absorption_evidence
    rejection_evidence
    progression_evidence
    campaign_evidence
    location_context
    aligned_evidence
    opposing_evidence
    provenance
```

Exact implementation may differ after repository inspection.

### Rules

- Shadow/read-only only.
- No actionability.
- No ranking.
- No order or alert semantics.
- No arbitrary numerical score.
- Reuse existing evidence; do not re-detect the same concept independently.
- Preserve source bar/week and evidence provenance.
- Bounded point-in-time context only.

### Definition of Done

For any historical week, the state answers:

```text
What behavior was visible by this completed week?
```

without using future data.

### Suggested PR

**PR-WF2 — Add read-only WeeklyBehaviorState**

---

# WF3 — Weekly Behavior Evolution and Contradiction Semantics

**Priority:** P1  
**Status:** PLANNED

## Objective

Model how weekly campaign evidence evolves across bars without treating every opposing event as an immediate reversal.

### Required distinctions

At minimum distinguish conceptually between:

```text
normal reaction / minor contradiction
meaningful contradiction
campaign weakening
structural invalidation evidence
```

### Requirements

- One contrary bar must not automatically reverse a multi-week campaign.
- Repeated or strengthening contrary evidence must remain visible.
- Confirmed structural failure must be able to dominate weaker supportive evidence.
- Campaign evidence must remain causal and replayable.
- Do not encode a fixed expiry duration here.

### Suggested PR

**PR-WF3 — Add weekly behavior evolution/contradiction state**

---

# WF4 — Shadow Weekly Thesis Builder

**Priority:** P1  
**Status:** PLANNED

## Objective

Build a read-only weekly thesis in parallel with the legacy qualification path.

Conceptually:

```text
WeeklyBehaviorState
        +
structural context
        +
location context
        +
contradiction state
        ↓
ShadowWeeklyThesis
```

Possible thesis states may include concepts such as:

```text
NO_THESIS
BULLISH_DEVELOPING
BULLISH_ESTABLISHED
BULLISH_WEAKENING
BEARISH_DEVELOPING
BEARISH_ESTABLISHED
BEARISH_WEAKENING
INVALIDATED
```

Names are provisional. Do not freeze them until replay evidence shows they are useful.

### Important

This is **not** yet a replacement for `PatternQualification` and does not create a production `WeeklySetup`.

### Suggested PR

**PR-WF4 — Add shadow weekly thesis builder**

---

# WF5 — Legacy vs Behavior Replay Comparison

**Priority:** P0/P1  
**Status:** PLANNED

## Objective

Compare the legacy weekly decision path against the shadow behavior/thesis path on point-in-time historical data.

### Required comparison buckets

```text
A. Legacy YES / Behavior YES
B. Legacy YES / Behavior NO
C. Legacy NO  / Behavior YES
D. Legacy NO  / Behavior NO
```

Bucket C is especially important because it identifies potential missed campaigns caused by rigid legacy gates.

Bucket B is equally important because it identifies cases where the proposed behavior model may be too permissive.

### Timing audit

For relevant directional campaigns record:

```text
first supply reduction week
first demand emergence week
first supportive effort/result week
first absorption/rejection week
first structural quality improvement week
first structural progression event
second structural progression event
third structural progression event
legacy qualification week
shadow thesis week
```

### Outcome audit

Measure at minimum:

```text
5-week forward result
10-week forward result
15-week forward result
maximum favorable excursion
maximum adverse excursion
subsequent structural confirmation
subsequent structural invalidation
bars/weeks of lead or lag vs legacy qualification
```

Evaluation must be point-in-time and must not tune thresholds on the same outcome set without holdout/robustness checks.

### Suggested PR

**PR-WF5 — Add legacy-vs-behavior weekly replay audit**

---

# WF6 — Evidence Promotion Audit

**Priority:** P1  
**Status:** PLANNED

## Objective

Determine whether currently read-only or weakly used evidence should influence weekly thesis formation.

Evaluate independently:

```text
Effort / Result
Absorption
location / support-resistance proximity
campaign context
professional swing quality progression
rejection behavior
named VSA events by regime
```

### Promotion rule

No evidence is promoted simply because it is intuitively appealing.

Promotion requires evidence of incremental decision value such as:

```text
better timing
fewer false legacy qualifications
recovery of valid missed campaigns
improved robustness across symbols/time periods
acceptable adverse excursion
```

### Required robustness

Prefer:

```text
out-of-sample time split
leave-one-symbol-out checks
regime stratification
sensitivity analysis
```

where dataset size permits.

### Suggested PR

**PR-WF6 — Audit weekly evidence promotion candidates**

---

# WF7 — Production Qualification Remediation

**Priority:** P0/P1  
**Status:** BLOCKED ON WF5/WF6 EVIDENCE

## Objective

Only after shadow comparison proves value, replace or generalize the overly rigid weekly qualification boundary incrementally.

### Possible outcomes

The audit may prove one of several things:

```text
1. Legacy qualification is already appropriately conservative.
   → keep it, improve observability only.

2. Legacy qualification is useful but late.
   → retain structural persistence as one strong factor,
      allow validated behavior state to qualify earlier.

3. Named-VSA confirmation gate causes avoidable misses.
   → replace hard named-event requirement with validated behavior confirmation.

4. Opposing-event rejection is too binary.
   → use contradiction state rather than any-opposing-event invalidation.

5. Read-only evidence adds no robust value.
   → keep it read-only.
```

The production change must be driven by the observed result, not by a predetermined desired architecture.

### Safety

- Small PRs only.
- Preserve legacy replay snapshots for comparison.
- Update full-vs-resume equivalence tests.
- Do not mix qualification redesign with performance refactoring.

### Suggested PRs

Depending on audit result:

```text
PR-WF7A — Generalize weekly qualification input
PR-WF7B — Replace named-VSA hard gate with validated behavior gate
PR-WF7C — Add validated contradiction/invalidation policy
```

Not all PRs are automatically required.

---

# WF8 — WeeklySetup Domain Generalization

**Priority:** P1  
**Status:** BLOCKED ON WF7

## Objective

Generalize `WeeklySetup` only if the validated production thesis can no longer be represented correctly by the current `PatternQualification` coupling.

### Possible direction

Conceptually move from:

```text
WeeklySetup
    requires PERSISTENT_BULLISH / PERSISTENT_BEARISH
```

into something closer to:

```text
WeeklySetup
    carries validated weekly thesis identity
    + qualification provenance
    + supporting evidence
    + contradictions
    + structural/location context
```

Do not break existing setup identity or coordinator causality without migration tests.

### Suggested PR

**PR-WF8 — Generalize WeeklySetup qualification provenance**

---

# WF9 — Weekly→Daily Reintegration

**Priority:** P0/P1  
**Status:** BLOCKED ON WF7/WF8

## Objective

Feed the validated weekly thesis into the existing Weekly→Daily causal coordinator and daily shadow/replay engine without weakening causality.

### Invariants

```text
weekly context visible to daily session D
=
latest completed and causally available validated weekly thesis
```

- Monday–Thursday cannot see the same week's Friday close.
- Daily opposing evidence does not silently reverse the weekly thesis.
- Terminal weekly lifecycle remains explicit.
- Daily signal still requires completed daily evidence.
- Daily execution still uses exact next-session semantics.

### Compatibility

Preserve the already completed M6 daily behavior work. Adapt the weekly input boundary rather than rebuilding the daily engine.

### Suggested PR

**PR-WF9 — Integrate validated weekly thesis with daily coordinator**

---

# WF10 — Weekly Foundation Release Gate

**Priority:** P0  
**Status:** BLOCKED ON PRIOR WEEKLY MILESTONES

## Objective

Declare the weekly foundation strong enough to resume the previous architecture roadmap.

### Required release gates

#### Gate 1 — Causality

- no future weekly evidence leaks
- no future structural confirmation leaks
- full-vs-resume equivalence preserved
- replay truncation produces identical state as full-history prefix

#### Gate 2 — Behavioral validity

- shadow behavior dimensions have explicit evidence provenance
- no mandatory textbook-pattern dependency unless validated
- contradiction semantics do not flip campaigns on one arbitrary opposing bar
- structural invalidation remains enforceable

#### Gate 3 — Historical evidence

- legacy-vs-behavior comparison completed
- timing lead/lag measured
- MFE/MAE measured
- results checked across symbols/time periods where possible
- promotions supported by evidence, not intuition

#### Gate 4 — Domain integrity

- WeeklySetup representation matches the validated thesis model
- Weekly→Daily coordinator remains causal
- daily shadow/replay behavior remains unchanged except for the intended weekly input semantics

#### Gate 5 — Regression safety

- targeted weekly tests pass
- scanner equivalence tests pass
- production scanner tests pass
- daily coordinator/replay tests pass
- full backend suite passes

When all applicable gates pass, mark weekly foundation:

```text
VALIDATED
```

and resume the previous roadmap.

---

## 8. Recommended PR Order

| Order | PR | Purpose | Production behavior? |
|---:|---|---|---|
| 1 | WF0 | Freeze legacy weekly decision baseline | No |
| 2 | WF1 | Decision-gate audit output | No |
| 3 | WF2 | WeeklyBehaviorState shadow model | No |
| 4 | WF3 | Behavior evolution / contradiction semantics | No |
| 5 | WF4 | Shadow weekly thesis builder | No |
| 6 | WF5 | Legacy-vs-behavior replay comparison | No |
| 7 | WF6 | Evidence promotion audit | No |
| 8 | WF7A/B/C as justified | Production qualification remediation | Yes, incremental |
| 9 | WF8 if required | WeeklySetup generalization | Yes, domain migration |
| 10 | WF9 | Weekly→Daily reintegration | Yes, integration boundary |
| 11 | WF10 | Release gate / validation | No new semantics |

The production sequence after WF6 is intentionally conditional. The audit determines what must actually be changed.

---

## 9. What We Must Not Do

Do not replace current qualification with a simplistic vote such as:

```text
4 bullish observations = bullish setup
```

Do not create a generic weighted-indicator soup.

Do not duplicate trend or structure logic.

Do not promote Effort/Result or Absorption without replay evidence.

Do not remove the current persistence rule before quantifying its delay and false-positive/false-negative tradeoff.

Do not weaken confirmed structural invalidation merely to make the system earlier.

Do not tune against a small set of favorite symbols and encode symbol-specific fixes.

Do not mix the weekly semantic remediation with performance optimization.

Do not change daily entry semantics while validating weekly foundation unless required by a proven interface mismatch.

---

## 10. Historical Audit Dataset Guidance

Use multiple market conditions and symbols where data is available.

The audit set should contain examples of:

```text
clean accumulation
messy accumulation
reaccumulation
healthy markup
normal correction within markup
distribution
redistribution
persistent markdown
failed bullish campaigns
failed bearish campaigns
range-bound markets
high-volatility shock periods
corporate-action/data-anomaly periods
```

Avoid judging architecture from one visually attractive setup.

Use the same point-in-time data and causal transition semantics used by replay/production.

---

## 11. Key Metrics for Weekly Foundation Validation

The weekly remediation should be evaluated using both correctness and market-behavior metrics.

### Correctness

```text
full-vs-resume parity
historical prefix parity
no-look-ahead violations
state reproducibility
setup identity stability
```

### Recognition quality

```text
legacy qualification rate
shadow thesis rate
legacy YES / behavior NO rate
legacy NO / behavior YES rate
weeks of lead/lag
subsequent structural confirmation rate
subsequent invalidation rate
```

### Outcome context

```text
5 / 10 / 15-week forward return
MFE
MAE
time to favorable excursion
time to invalidation
```

### Decision-value questions

```text
Did the new model recover campaigns the legacy gate missed?
Did it become too permissive?
Did it recognize valid campaigns earlier?
Did earlier recognition materially increase adverse excursion?
Did contradiction handling reduce unnecessary invalidations?
Did promoted evidence add value across symbols, not just in-sample?
```

---

## 12. Relationship to the Existing ProVSA Architecture Roadmap

The existing `docs/PROVSA_ARCHITECTURE_ROADMAP.md` remains the canonical broad architecture roadmap.

This document becomes the **current focused remediation track** before later roadmap milestones continue.

Current sequencing is therefore:

```text
M1–M6 completed work
        ↓
WEEKLY FOUNDATION ROADMAP (this document)
        ↓
WF10 validated
        ↓
resume existing architecture roadmap
        ↓
M7 Performance Consolidation
        ↓
M8 Module Boundary / Python Quality
        ↓
M9 State / Cache / Operational Robustness
        ↓
M10 CI Modernization
```

The completed daily behavior and replay work is not discarded. It remains available and should be reconnected to the stronger validated weekly thesis after weekly remediation.

---

## 13. Definition of a Strong Weekly Foundation

The weekly foundation is considered strong when ProVSA can, causally and reproducibly, describe the market using:

```text
structure
trend state
supply behavior
demand behavior
effort vs result
absorption/rejection
professional swing quality
campaign persistence
location
contradiction/invalidation
```

without requiring a perfect textbook sequence, while still refusing weak or contradictory campaigns when evidence is insufficient.

The desired end state is:

```text
WEEKLY
    does not ask:
        "Did the textbook setup print?"

    asks:
        "What is the market actually demonstrating,
         how persistent is it,
         where is it occurring,
         and what evidence would invalidate that interpretation?"

DAILY
    then asks:
        "Is there a causal, low-risk timing opportunity
         consistent with that weekly thesis?"
```

That is the foundation ProVSA should establish before later optimization and production-expansion work continues.