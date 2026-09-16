# ProVSA Shadow Weekly Thesis

**Milestone:** WF4 — Shadow Weekly Thesis Builder  
**Status:** IN PROGRESS  
**Production authority:** None — read-only/shadow  
**Depends on:** WF2 `WeeklyBehaviorState` + WF3 `WeeklyBehaviorEvolution`

---

## 1. Purpose

WF4 is the first layer that turns the descriptive weekly behavior work into a
first-class directional thesis object.

It remains entirely parallel to the legacy production path.

```text
WF2 WeeklyBehaviorState
        +
WF3 WeeklyBehaviorEvolution
        ↓
ShadowWeeklyThesis
        ↓
replay / audit / comparison only
```

WF4 does **not** replace `PatternQualification`, does not create a production
`WeeklySetup`, and does not alter scanner actionability.

---

## 2. Core Principle

The thesis must describe the campaign demonstrated by real market evidence,
not require a perfect textbook VSA sequence.

Named observations remain evidence and provenance. The builder does not require
combinations such as:

```text
SPRING + TEST + NO SUPPLY
```

or any other fixed textbook recipe.

It consumes the behavior already observed by the existing engines and asks:

```text
Is there an established structural direction?
Is bounded recent evidence aligned with that direction?
Is the campaign merely experiencing a minor contrary observation?
Is opposition meaningful or is structure weakening?
Is there stronger structural invalidation evidence?
```

---

## 3. Shadow Thesis States

WF4 intentionally uses descriptive states rather than a score.

```text
NO_THESIS

BULLISH_DEVELOPING
BULLISH_SUPPORTED
BULLISH_CHALLENGED
BULLISH_INVALIDATION_EVIDENCE

BEARISH_DEVELOPING
BEARISH_SUPPORTED
BEARISH_CHALLENGED
BEARISH_INVALIDATION_EVIDENCE
```

These names are shadow/audit semantics. WF5 replay determines whether they are
useful enough to influence later production remediation.

### NO_THESIS

No directional structural reference exists. RANGE/UNKNOWN structure is not
forced into a bullish or bearish thesis merely because one directional VSA
observation exists.

### DEVELOPING

A directional structural reference exists, but no aligned observation is visible
inside the bounded recent behavior window.

This is not an actionable setup. It only records that structure provides a
directional campaign reference while behavioral support is currently absent.

### SUPPORTED

At least one already-observed bounded recent evidence item is aligned with the
structural reference and WF3 has not identified meaningful campaign weakening or
structural invalidation evidence.

This is deliberately not called "qualified" or "actionable". WF4 does not yet
claim that one aligned event is sufficient to trade.

A single `MINOR` contradiction may coexist with `SUPPORTED`. The contradiction
remains visible, but one contrary week does not automatically demote or reverse
a broader supported campaign.

### CHALLENGED

WF3 reports either:

```text
MEANINGFUL
or
CAMPAIGN_WEAKENING
```

The original thesis direction is preserved so replay can measure what happened
when an established campaign became challenged.

### INVALIDATION_EVIDENCE

WF3 reports `STRUCTURAL_INVALIDATION_EVIDENCE`.

Importantly, the object still describes the **old thesis being invalidated**.
It does not silently flip into a new opposite thesis on the same completed week.

Example:

```text
prior bullish structural reference
        ↓
current structure flips bearish
        ↓
BULLISH_INVALIDATION_EVIDENCE
```

A later completed week can establish and support the new bearish reference
through the ordinary causal evolution path.

---

## 4. Thesis Basis / Provenance

Every state carries an explicit non-numeric basis:

```text
NO_DIRECTIONAL_REFERENCE
DIRECTIONAL_REFERENCE_ONLY
ALIGNED_BEHAVIOR_PRESENT
MEANINGFUL_CONTRADICTION
CAMPAIGN_WEAKENING
STRUCTURAL_INVALIDATION_EVIDENCE
```

This lets WF5 compare legacy qualification against the exact reason the shadow
thesis had its state without parsing free-text explanations or reconstructing
logic later.

---

## 5. Evidence Provenance

WF4 does not rerun VSA detectors and does not manufacture new observations.

It preserves:

```text
supporting_evidence
opposing_evidence
current_supporting_evidence
current_opposing_evidence
```

relative to the WF3 structural reference direction.

This distinction matters when structure flips. The current WF2 behavior may
already describe the newly bearish structure, while the WF4 object for that
same week must still show that the previously bullish thesis received
invalidation evidence.

The thesis therefore follows the WF3 reference direction rather than silently
relabeling evidence around the new structural direction.

---

## 6. Structural and Professional Context

WF4 carries through existing point-in-time context for later replay:

```text
trend_direction
trend_state
structural_pattern
current_structural_direction
support_zone
resistance_zone
professional_strength
professional_weakness
professional_net_strength
professional_net_pressure
professional_confidence
```

These are observations/provenance only. WF4 introduces no new weighted formula
or confidence percentage.

---

## 7. No Arbitrary Score or Vote

WF4 deliberately does not implement logic such as:

```text
4 bullish dimensions = bullish thesis
score > 70 = established
2 contradictions = invalid
```

The only persistence/contradiction semantics are those already exposed by WF3,
and they remain shadow semantics pending replay validation.

WF4 adds no:

```text
synthetic thesis score
new evidence weight
fixed expiry
ranking
entry threshold
position sizing
order semantics
```

---

## 8. Production Safety Boundary

WF4 changes no production behavior.

```text
No detector changes
No evidence-weight changes
No PatternQualification changes
No legacy named-VSA gate changes
No scanner scoring changes
No ranking changes
No scanner actionability changes
No WeeklySetup creation/lifecycle changes
No Weekly→Daily coordinator changes
No daily behavior changes
No daily trigger changes
No execution changes
No alerts or orders
```

`ShadowWeeklyThesis.is_actionable` always returns `False`.

---

## 9. Manual Validation

Targeted:

```powershell
python -m pytest tests/test_shadow_weekly_thesis.py tests/test_weekly_behavior_evolution.py tests/test_weekly_behavior_state.py -v
```

Weekly foundation regressions:

```powershell
python -m pytest tests/test_weekly_decision_audit.py tests/test_weekly_legacy_decision_baseline.py -v
python -m pytest tests/test_scanner_full_resume_equivalence.py tests/test_production_scanner.py -v
```

Full backend:

```powershell
python -m pytest tests -q
```

---

## 10. Next Step

After WF4 is manually validated and merged:

```text
WF5 — Legacy vs Behavior Replay Comparison
```

WF5 will compare the legacy weekly decision path with the shadow thesis path and
measure timing, missed/extra campaigns, forward outcomes, MFE/MAE and structural
confirmation/invalidation before any production qualification is changed.
