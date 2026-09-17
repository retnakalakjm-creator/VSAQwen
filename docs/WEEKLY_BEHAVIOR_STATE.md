# ProVSA Weekly Behavior State

**Milestone:** WF2 — WeeklyBehaviorState Shadow Model  
**Status:** IN PROGRESS  
**Production authority:** None — read-only/shadow  
**Depends on:** WF0 legacy baseline + WF1 decision-gate audit

---

## 1. Purpose

WF2 introduces an immutable weekly behavior representation that describes what the completed weekly market was actually demonstrating without requiring a textbook VSA sequence.

The state is deliberately descriptive rather than prescriptive.

```text
existing point-in-time weekly evidence
        ↓
WeeklyBehaviorState
        ↓
organized behavioral evidence
        ↓
NO actionability / NO WeeklySetup / NO order semantics
```

The model does not replace `PatternQualification` in WF2. It runs in shadow beside the legacy path so later milestones can compare real-market behavior with the current production gate.

---

## 2. Core Principle

Real markets do not reliably print perfect named sequences.

WF2 therefore does not ask:

```text
Did NO SUPPLY + TEST + SPRING appear in the expected order?
```

It asks:

```text
What supply evidence exists?
What demand evidence exists?
What effort/result evidence exists?
Is absorption visible?
What structural progression is visible?
What professional pressure/strength context was already visible?
What directional observations are aligned or opposed to current structure?
What was knowable by this completed weekly bar?
```

Named VSA events remain evidence and provenance. They are not universal mandatory gates.

---

## 3. Source of Truth

WF2 does not create a second detector stack.

`WeeklyBehaviorStateBuilder` only organizes evidence and context already produced by the existing weekly engines.

Preferred projection path:

```text
ScannerCandidate
    ↓
WF1 WeeklyDecisionGateAuditRecord
    ↓
WF2 WeeklyBehaviorState
```

This preserves the existing causal trend, structure, evidence, campaign, professional scoring and scanner lineage.

WF2 does not rerun:

```text
SwingEngine
StructureFilter
TrendAnalyzer
EvidenceEngine
ProfessionalScoringEngine
PatternQualificationEngine
```

inside the behavior-state builder.

---

## 4. State Contents

The initial immutable state records:

```text
identity
    symbol
    week
    bar_index

structure
    trend_direction
    trend_state
    structural_pattern
    confirmed structural swing lineage

location context
    support_zone
    resistance_zone

existing professional context
    professional_strength
    professional_weakness
    professional_net_strength
    professional_net_pressure
    professional_confidence

point-in-time evidence
    current_evidence
    bounded recent_evidence

behavior groupings
    supply_evidence
    demand_evidence
    effort_result_evidence
    absorption_evidence
    progression_evidence

raw directional observations
    bullish_evidence
    bearish_evidence
    neutral_evidence

structural alignment view
    structural_reference_direction
    aligned_evidence
    opposing_evidence
```

The professional values are carried through from the existing WF1 audit/scanner result; WF2 does not recalculate or reweight them.

There is intentionally no new synthetic weekly confidence percentage in WF2.

---

## 5. Structural Alignment Is Not a Thesis

WF2 may label evidence as aligned/opposing relative to the already-established structural trend direction:

```text
TrendDirection.UP
→ bullish evidence = structurally aligned
→ bearish evidence = structurally opposing

TrendDirection.DOWN
→ bearish evidence = structurally aligned
→ bullish evidence = structurally opposing
```

For `RANGE` or `UNKNOWN`:

```text
structural_reference_direction = NEUTRAL
aligned_evidence = ()
opposing_evidence = ()
```

Bullish and bearish observations remain visible, but WF2 does not invent a directional campaign when structure has not established one.

This is important: **structural alignment is an observation, not a weekly thesis decision.** Thesis semantics belong to later WF3/WF4 work.

---

## 6. Evidence Grouping Rules

### Supply

Evidence whose category is `EvidenceCategory.SUPPLY`.

### Demand

Evidence whose category is `EvidenceCategory.DEMAND`.

### Effort / Result

Evidence with existing effort/result codes or `EFFORT` / `RESULT` categories, including:

```text
EFFORT_GT_RESULT
RESULT_GT_EFFORT
EFFORT_RESULT
```

This does not promote Effort/Result into production qualification.

### Absorption

The existing read-only `ABSORPTION` observation is exposed as its own behavior dimension.

WF2 does not reinterpret the legacy named `SUPPLY_ABSORPTION` scanner event as the read-only generic absorption detector.

### Structural progression

Existing events:

```text
STRUCTURAL_PROGRESSION_IMPROVING
STRUCTURAL_PROGRESSION_WEAKENING
```

remain visible as one behavior dimension rather than becoming the sole definition of campaign quality.

---

## 7. Point-in-Time Safety

WF1 supplies bounded recent evidence. WF2 still applies a defensive no-future filter.

When `bar_index = N`:

```text
current_evidence
→ only evidence with bar_index == N

recent_evidence
→ only evidence with bar_index <= N
```

Thus a replay/audit caller cannot accidentally insert bar `N+1` evidence into the behavior state for bar `N`.

The caller remains responsible for supplying a bounded recent window when using `WeeklyBehaviorStateBuilder.build(...)` directly. The preferred `from_audit(...)` path inherits WF1's bounded scanner lookback.

---

## 8. Safety Boundary

WF2 changes no production decision semantics.

```text
No detector changes
No evidence-weight changes
No PatternQualification changes
No named-VSA gate changes
No professional score changes
No ranking changes
No actionability changes
No WeeklySetup creation changes
No Weekly→Daily coordinator changes
No daily entry changes
No execution changes
No alerts or orders
```

`WeeklyBehaviorState.is_actionable` always returns `False`.

---

## 9. Why WF2 Does Not Yet Classify Campaign Evolution

WF2 intentionally stops at a point-in-time snapshot.

It does **not** yet decide whether an opposing observation is:

```text
normal reaction
minor contradiction
meaningful contradiction
campaign weakening
structural invalidation
```

Those are temporal/evolution semantics and belong to:

```text
WF3 — Weekly Behavior Evolution and Contradiction Semantics
```

Keeping WF2 descriptive prevents premature hard-coded campaign rules.

---

## 10. Manual Validation

Targeted validation:

```powershell
python -m pytest tests/test_weekly_behavior_state.py tests/test_weekly_decision_audit.py tests/test_weekly_legacy_decision_baseline.py -v
```

Regression validation:

```powershell
python -m pytest tests/test_scanner_full_resume_equivalence.py tests/test_production_scanner.py -v
python -m pytest tests -q
```

---

## 11. Next Step

After WF2 is manually validated and merged:

```text
WF3 — Weekly Behavior Evolution and Contradiction Semantics
```

WF3 will model how the behavior state evolves across completed weekly bars while preserving the principle that one contrary observation does not automatically reverse a multi-week campaign.
