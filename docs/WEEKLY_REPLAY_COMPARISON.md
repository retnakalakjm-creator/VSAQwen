# ProVSA Weekly Legacy-vs-Shadow Replay Comparison

**Milestone:** WF5 — Legacy vs Behavior Replay Comparison  
**Status:** IN PROGRESS  
**Production authority:** None — replay/audit only  
**Depends on:** WF1 decision audit, WF2 behavior state, WF3 evolution, WF4 shadow thesis

---

## 1. Purpose

WF5 is the first layer that directly compares the current production weekly decision boundary with the new read-only behavior/thesis path.

The comparison is intentionally retrospective, but the decisions themselves remain point-in-time:

```text
completed weekly audit prefix
        ↓
WF2 WeeklyBehaviorState
        ↓
WF3 WeeklyBehaviorEvolution
        ↓
WF4 ShadowWeeklyThesis
        ↓
freeze decision for this week
        ↓
ONLY AFTERWARD attach forward outcome context
```

Future prices or future structural observations never participate in the weekly decision state.

---

## 2. Comparison Buckets

Every completed weekly bar is assigned to exactly one bucket:

```text
A. LEGACY YES / SHADOW YES
B. LEGACY YES / SHADOW NO
C. LEGACY NO  / SHADOW YES
D. LEGACY NO  / SHADOW NO
```

The implementation names are:

```text
LEGACY_YES_SHADOW_YES
LEGACY_YES_SHADOW_NO
LEGACY_NO_SHADOW_YES
LEGACY_NO_SHADOW_NO
```

Bucket C is important for measuring potentially missed or delayed campaigns.
Bucket B is equally important because it can expose a shadow model that is too restrictive, too unstable, or directionally inconsistent with the legacy path.

WF5 does not declare either path superior.

---

## 3. What Counts as Shadow YES

WF4 deliberately exposes several descriptive states:

```text
DEVELOPING
SUPPORTED
CHALLENGED
INVALIDATION_EVIDENCE
```

For the WF5 A/B/C/D taxonomy, **Shadow YES means only**:

```text
BULLISH_SUPPORTED
or
BEARISH_SUPPORTED
```

This is a comparison convention, not a production threshold.

Why:

- `DEVELOPING` has structural direction but no aligned behavioral support.
- `CHALLENGED` explicitly carries meaningful contradiction or campaign weakening.
- `INVALIDATION_EVIDENCE` is evidence against continuation of the existing thesis.
- `SUPPORTED` is the narrowest WF4 state that says directional structure and aligned behavior coexist without a stronger contradiction state.

WF5 does **not** claim that `SUPPORTED` is sufficient for production qualification. Historical replay in WF5/WF6 exists precisely to test whether that shadow state has useful decision value.

---

## 4. Direction Agreement

The report preserves whether the two paths agree on direction when both are YES:

```text
SAME
OPPOSITE
LEGACY_ONLY
SHADOW_ONLY
NEITHER
```

A YES/YES observation with opposite direction is therefore not hidden inside bucket A.

---

## 5. Forward Outcome Context

WF5 attaches direction-adjusted forward outcomes after each frozen decision.

Default horizons:

```text
5 weeks
10 weeks
15 weeks
```

For each horizon the report records:

```text
available weeks
whether the full horizon is complete
direction-adjusted close return
maximum favorable excursion (MFE)
maximum adverse excursion (MAE)
```

For a bullish thesis:

```text
positive return = price rose
MFE = highest favorable move above the signal close
MAE = deepest adverse move below the signal close
```

For a bearish thesis the calculation is direction-adjusted symmetrically:

```text
positive return = price fell
MFE = deepest favorable decline below the signal close
MAE = highest adverse rise above the signal close
```

MFE is floored at zero and MAE is capped at zero so their signs remain unambiguous.

A partial horizon remains visible with `complete=False`; missing future data is never silently treated as a complete outcome.

---

## 6. Structural Confirmation / Invalidation Outcome Context

For a frozen directional YES decision, WF5 also records the first later week showing:

```text
aligned structural progression confirmation
```

and the first later WF3 state showing:

```text
STRUCTURAL_INVALIDATION_EVIDENCE
```

These fields are retrospective outcome labels only. They do not mutate the historical decision.

Aligned structural confirmation uses the existing causal progression events:

```text
bullish  → STRUCTURAL_PROGRESSION_IMPROVING
bearish  → STRUCTURAL_PROGRESSION_WEAKENING
```

No new structure detector is introduced.

---

## 7. Timing Audit

WF5 emits a direction-scoped timing summary for bullish and bearish evidence inside the supplied replay window.

It records the first observed week for:

```text
opposing pressure reduction
aligned pressure emergence
supportive Effort/Result
absorption or rejection
first structural progression event
second structural progression event
third structural progression event
legacy qualification
legacy actionability
shadow SUPPORTED thesis
```

The current evidence mappings are explicit and auditable:

### Bullish pressure reduction

```text
SUPPLY_DRYING_UP
NO_SUPPLY
```

### Bearish pressure reduction

```text
DEMAND_DRYING_UP
NO_DEMAND
```

### Bullish aligned pressure emergence

```text
DEMAND_COMING_IN
INCREASING_DEMAND
HIDDEN_DEMAND
```

### Bearish aligned pressure emergence

```text
SUPPLY_COMING_IN
INCREASING_SUPPLY
HIDDEN_SUPPLY
```

### Rejection evidence

Bullish:

```text
STOPPING_VOLUME
SELLING_CLIMAX
SHAKEOUT
SPRING
TEST
```

Bearish:

```text
BUYING_CLIMAX
UPTHRUST
```

Absorption is taken from the existing read-only absorption evidence and must match the audited direction.

Effort/Result is taken from the existing read-only Effort/Result evidence and must match the audited direction.

These mappings are audit categories, not production promotion rules.

---

## 8. Lead / Lag Sign Convention

WF5 reports:

```text
shadow_supported_minus_legacy_actionable_weeks
```

Interpretation:

```text
negative → shadow support appeared earlier
zero     → same replay week
positive → shadow support appeared later
None     → one side never appeared inside the replay window
```

The value uses replay positions, so it measures completed weekly bars rather than calendar-day gaps.

---

## 9. Replay Window Scope

The timing summary is direction-scoped within the supplied replay window.

It does not yet automatically segment multiple separate bullish or bearish campaigns inside one long history. Therefore historical audit callers should use sensible campaign/replay windows when interpreting first-event timing.

Automatic campaign segmentation can be added later if WF5 analysis shows that it is necessary; it is not required to compare the existing decision boundary safely.

---

## 10. Causality Contract

For each replay position `N`:

```text
shadow decision at N
=
WF2/WF3/WF4 built only from audit states 0..N
```

Later audit states and later prices are unavailable to that decision.

The implementation first builds every shadow state causally from prefixes, freezes the legacy/shadow decision fields, and only then scans later data for outcome metrics.

A historical prefix must therefore produce the same decision state whether replay stops at that prefix or continues into the future.

---

## 11. Safety Boundary

WF5 changes no production semantics:

```text
No detector changes
No evidence-weight changes
No PatternQualification changes
No named-VSA gate changes
No scanner score changes
No ranking/actionability changes
No WeeklySetup changes
No Weekly→Daily changes
No daily-entry changes
No execution changes
No alerts/orders
```

`WeeklyReplayComparisonReport.is_actionable` always returns `False`.

---

## 12. Manual Validation

Targeted:

```powershell
python -m pytest tests/test_weekly_replay_comparison.py tests/test_shadow_weekly_thesis.py tests/test_weekly_behavior_evolution.py tests/test_weekly_behavior_state.py -v
```

Weekly audit/regression:

```powershell
python -m pytest tests/test_weekly_decision_audit.py tests/test_weekly_legacy_decision_baseline.py -v
python -m pytest tests/test_scanner_full_resume_equivalence.py tests/test_production_scanner.py -v
```

Full backend suite:

```powershell
python -m pytest tests -q
```

---

## 13. What WF5 Does Not Decide

WF5 does not decide whether to replace the legacy gate.

It creates the measurement layer required to answer questions such as:

```text
How often does shadow support appear before legacy actionability?
How often does it appear when legacy never acts?
What happens afterward in price and structure?
Does the shadow path create more adverse excursion?
Does the legacy path act while the behavior path is challenged?
Are disagreements concentrated in particular evidence regimes?
```

Those observations feed **WF6 — Evidence Promotion Audit** and only then the conditional WF7 production remediation decision.
