# ProVSA Weekly Behavior Evolution

**Milestone:** WF3 — Weekly Behavior Evolution and Contradiction Semantics  
**Status:** IN PROGRESS  
**Production authority:** None — read-only/shadow  
**Depends on:** WF2 `WeeklyBehaviorState`

---

## 1. Purpose

WF3 adds a causal evolution layer over the immutable WF2 weekly behavior snapshots.

WF2 answers:

```text
What behavior was visible by this completed weekly bar?
```

WF3 adds:

```text
How is that behavior changing relative to the most recently established
structural direction?
```

It remains read-only. It does not create a `WeeklySetup`, replace
`PatternQualification`, or change production actionability.

---

## 2. Core Principle

One contrary weekly observation must not automatically reverse a multi-week
campaign.

The evolution layer therefore distinguishes:

```text
NONE
MINOR
MEANINGFUL
CAMPAIGN_WEAKENING
STRUCTURAL_INVALIDATION_EVIDENCE
```

These are descriptive audit states, not trade commands.

---

## 3. Reference Direction

WF3 compares the current completed week with the most recent directional
structural reference that was already established before it.

```text
prior UP structure + current bearish evidence
→ opposition to bullish reference

prior DOWN structure + current bullish evidence
→ opposition to bearish reference
```

If there is no prior directional structure, the current directional structure is
used only as the initial observation reference.

If both prior and current structure are non-directional (`RANGE` / `UNKNOWN`),
WF3 does not invent a bullish or bearish campaign.

A later structural direction flip is kept visible as explicit invalidation
evidence rather than silently rewriting the prior week.

---

## 4. Current-Bar Evidence Only for Evolution

WF2 carries both current and bounded recent evidence. WF3 deliberately uses
`current_evidence` when deciding whether opposition occurred on a particular
week.

This prevents one old observation from being counted repeatedly just because it
remains inside the recent lookback window.

```text
old bearish evidence still in recent window
+
current bullish/aligned week
→ current opposition = false
```

`consecutive_opposing_weeks` therefore measures consecutive completed weekly
bars that each produced fresh opposing evidence.

---

## 5. Contradiction Semantics

### NONE

No fresh current opposition and no structural weakening/invalidation evidence.

### MINOR

Fresh opposing evidence appears on the current bar, while:

```text
structure remains directionally aligned
professional net pressure does not oppose the reference
no stronger structural weakening condition is present
```

This is intentionally compatible with a normal reaction inside a broader
campaign. It does not reverse anything.

### MEANINGFUL

Fresh opposition is present and either:

```text
opposition also occurred on the immediately preceding completed week
or
professional net pressure opposes the established structural reference
```

The two-week persistence distinction is an audit semantic, not an actionability
threshold. WF5/WF6 replay must determine whether it has useful decision value.

### CAMPAIGN_WEAKENING

Existing structural/trend machinery is already showing deterioration relative
to the established reference direction.

Examples include:

```text
TrendState.EXHAUSTED
TrendState.REVERSING
fresh opposing structural progression
StructuralPattern.BREAKING
```

Structural pattern interpretation is directional:

```text
bullish reference:
    StructuralPattern.WEAKENING opposes the campaign

bearish reference:
    StructuralPattern.IMPROVING opposes the campaign

StructuralPattern.BREAKING:
    mixed structural break evidence for either directional reference
```

Therefore a healthy bearish campaign is not incorrectly labelled weakening just
because its structural pattern is `WEAKENING`; in a bearish reference that
pattern is directionally aligned.

WF3 exposes deterioration without deciding that the campaign has already
reversed.

### STRUCTURAL_INVALIDATION_EVIDENCE

Used only when stronger existing structural information is visible, currently:

```text
established structural direction flips to the opposite side
or
TrendState.REVERSING + fresh opposing structural progression
```

This is still evidence, not a production setup lifecycle mutation. WF4/WF7 will
decide how validated thesis/invalidation semantics should use it.

---

## 6. Why Professional Pressure Is Supporting Context

WF3 carries the WF2 professional net-pressure observation.

For a bullish structural reference:

```text
net pressure < 0
→ professional pressure opposes the reference
```

For a bearish structural reference:

```text
net pressure > 0
→ professional pressure opposes the reference
```

Professional pressure alone does not create a contradiction state when no fresh
opposing current evidence exists. This keeps the evolution model conservative
and provenance-driven.

---

## 7. No Arbitrary Campaign Score

WF3 does not introduce:

```text
weighted contradiction score
confidence percentage
bullish/bearish vote count
fixed campaign expiry
entry threshold
ranking
```

The only persistence count is the directly observable number of consecutive
completed weekly bars with fresh opposition. Later replay will determine whether
this distinction is useful.

---

## 8. Safety Boundary

WF3 changes no production semantics.

```text
No detector changes
No evidence-weight changes
No PatternQualification changes
No scanner actionability changes
No ranking changes
No WeeklySetup changes
No Weekly→Daily coordinator changes
No daily entry changes
No execution changes
No alerts or orders
```

`WeeklyBehaviorEvolution.is_actionable` always returns `False`.

---

## 9. Manual Validation

Targeted:

```powershell
python -m pytest tests/test_weekly_behavior_evolution.py tests/test_weekly_behavior_state.py tests/test_weekly_decision_audit.py -v
```

Regression:

```powershell
python -m pytest tests/test_weekly_legacy_decision_baseline.py tests/test_scanner_full_resume_equivalence.py tests/test_production_scanner.py -v
python -m pytest tests -q
```

---

## 10. Next Step

After WF3 is manually validated and merged:

```text
WF4 — Shadow Weekly Thesis Builder
```

WF4 will consume WF2 behavior plus WF3 evolution/contradiction state to build a
read-only weekly thesis in parallel with the legacy qualification path.
