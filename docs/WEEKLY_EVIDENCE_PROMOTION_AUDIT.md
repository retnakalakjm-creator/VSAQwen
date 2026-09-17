# ProVSA Weekly Evidence Promotion Audit

**Milestone:** WF6 — Evidence Promotion Audit  
**Status:** IN PROGRESS  
**Production authority:** None — read-only/audit only  
**Depends on:** WF1–WF5

---

## 1. Purpose

WF6 does **not** promote any new weekly evidence into production.

It adds a reproducible audit layer for asking whether evidence that is currently
read-only, weakly used, or compressed by the legacy gate provides incremental
decision value when evaluated on point-in-time weekly replay.

The candidates are audited independently:

```text
Effort / Result
Absorption
location / support-resistance
campaign context
professional swing progression
rejection behavior
named VSA events by regime
```

The output is descriptive evidence for later WF7 decisions. It is not a new
qualification engine.

---

## 2. Non-Negotiable Rule

No evidence is promoted because it sounds correct in VSA theory.

WF6 records observable cohort differences only:

```text
candidate present
vs
candidate absent
```

using direction-adjusted forward outcomes and later structural observations.

There is deliberately no automatic label such as:

```text
PROMOTE
REJECT
PASS
FAIL
GOOD
BAD
```

and no arbitrary score or confidence threshold.

WF7 may only change production semantics after the historical audit is reviewed
for timing, adverse excursion, missed-campaign recovery, false positives, and
robustness across symbols/time/regimes.

---

## 3. Point-in-Time Candidate Observation

Each WF6 observation is frozen from the WF1 audit record for one completed
weekly bar.

For a directional structural reference:

```text
current completed week
        ↓
freeze candidate evidence presence
        ↓
attach future price / structural outcomes afterward
```

Future price, future evidence, future swings, and future structural events never
feed back into candidate detection.

Current-bar evidence is used for event-like candidates so an old observation is
not repeatedly counted merely because it remains in the bounded recent window.

The exception is **campaign context**, where the question is explicitly whether
aligned evidence already existed on prior completed bars inside the bounded WF1
recent window. Current-bar evidence is excluded from that prior-context count.

---

## 4. Candidate Semantics

### Effort / Result

Present when fresh current weekly Effort/Result evidence is directionally aligned
with the established WF3 structural reference.

The audit recognizes the existing Effort/Result codes/categories. It does not
create a new Effort/Result detector.

### Absorption

Present when fresh current `ABSORPTION` evidence is aligned with the reference
direction.

It remains read-only.

### Location / Support-Resistance

For a bullish reference, the relevant existing weekly **support** zone is used.
For a bearish reference, the relevant existing weekly **resistance** zone is
used.

WF6 records:

```text
zone unavailable
below zone
inside zone
above zone
absolute distance to nearest zone edge as % of current close
```

`inside zone` is the only default binary location-presence observation. WF6 does
not invent a universal “within X%” rule.

Optional proximity thresholds may be supplied by the audit caller for
**sensitivity analysis**. For example, callers can compare 0.5%, 1%, 2%, etc.
without any of those thresholds becoming production policy.

Directional proximity is conservative:

```text
bullish support context:
    inside support OR above support within caller threshold
    price below support is not treated as supportive proximity

bearish resistance context:
    inside resistance OR below resistance within caller threshold
    price above resistance is not treated as supportive proximity
```

### Campaign Context

Present when the bounded recent WF1 history contains prior aligned evidence from
an earlier completed week.

This is a persistence/context observation, not a vote count and not a campaign
score.

### Professional Swing Progression

WF6 reuses the existing direction-aware structural progression event:

```text
bullish reference → STRUCTURAL_PROGRESSION_IMPROVING
bearish reference → STRUCTURAL_PROGRESSION_WEAKENING
```

It does not recalculate professional swing quality independently. This preserves
the existing structural engine as the source of truth.

### Rejection Behavior

WF6 reuses the existing directional rejection event vocabulary already used by
the WF5 timing audit.

Bullish examples include stopping volume, selling climax, shakeout, spring and
test. Bearish rejection uses buying climax and upthrust.

These remain observations rather than mandatory textbook sequences.

### Named VSA by Regime

Every named code currently recognized by the legacy scanner directional VSA gate
is audited independently.

A `NO_SUPPLY` result is therefore not merged into the same statistic as a
`SPRING`, and bullish/bearish sides remain separate.

Each candidate can also be stratified by the existing weekly regime tuple:

```text
TrendDirection
TrendState
StructuralPattern
```

This allows a named event to be useful in one regime and weak in another without
inventing a universal event weight.

---

## 5. Outcome Metrics

WF6 reuses the same direction-adjusted interpretation as WF5.

Default horizons are:

```text
5 weeks
10 weeks
15 weeks
```

Callers can request other positive horizons for audit experiments.

For each complete horizon, cohort summaries include:

```text
mean directional close return
median directional close return
mean maximum favorable excursion (MFE)
mean maximum adverse excursion (MAE)
```

Only **complete** horizons enter these aggregate return/MFE/MAE statistics.
Incomplete tail observations remain counted as observations but do not pollute a
full-horizon average.

For bearish references, returns and excursion are direction adjusted, so a price
decline in the thesis direction is positive.

MAE remains zero or negative; a positive present-minus-absent MAE delta means the
candidate cohort experienced less adverse excursion on average.

---

## 6. Structural Outcome Context

For every frozen directional observation, WF6 also records which later structural
outcome occurs first:

```text
CONFIRMED_FIRST
INVALIDATED_FIRST
SAME_BAR
NEITHER
```

Confirmation means a later aligned structural progression event.

Invalidation means later WF3 `STRUCTURAL_INVALIDATION_EVIDENCE` while the same
reference direction is still the thesis being evaluated.

This context is attached after the candidate observation is frozen and does not
change historical state.

---

## 7. Legacy/Shadow Disagreement Context

Each WF6 observation retains the corresponding WF5 comparison bucket:

```text
Legacy YES / Shadow YES
Legacy YES / Shadow NO
Legacy NO  / Shadow YES
Legacy NO  / Shadow NO
```

It also retains the legacy gate blockers.

This is important because incremental value is not only forward return. A useful
candidate may, for example, repeatedly appear in Bucket C before later structural
confirmation, or may be common in Bucket B cases that later invalidate.

WF6 does not decide whether those patterns are strong enough for promotion.

---

## 8. Robustness Support

### Time split

The caller may supply `out_of_sample_start_bar_index` separately for each symbol.

WF6 then reports:

```text
ALL
IN_SAMPLE
OUT_OF_SAMPLE
```

cohorts without inventing the split point itself.

Without a supplied split, observations are marked `UNSPLIT`.

### Leave-one-symbol-out

When two or more symbols are supplied, WF6 produces descriptive leave-one-symbol-
out comparisons for each candidate/direction/horizon:

```text
held-out symbol candidate delta
vs
all other symbols candidate delta
```

No automatic consistency threshold is imposed.

### Regime stratification

Candidate summaries are emitted both overall and for each observed
TrendDirection/TrendState/StructuralPattern regime.

### Sensitivity

Forward horizons provide natural timing sensitivity, and caller-supplied location
distance thresholds provide location sensitivity without freezing a production
cutoff.

---

## 9. What a Candidate Summary Means

For one candidate, direction, horizon, time partition, and optional regime, WF6
produces two descriptive cohorts:

```text
PRESENT
ABSENT
```

Each cohort includes:

```text
observation count
complete-horizon count
mean / median directional close return
mean MFE
mean MAE
first structural confirmation count
first structural invalidation count
neither count
WF5 A/B/C/D bucket counts
```

WF6 then reports simple:

```text
present metric - absent metric
```

deltas.

A positive return delta is not, by itself, a promotion decision. Sample size,
regime stability, out-of-sample behavior, symbol robustness, adverse excursion,
and causal plausibility still need review.

---

## 10. Safety Boundary

WF6 changes no production semantics.

```text
No detector changes
No evidence-weight changes
No PatternQualification changes
No legacy named-VSA gate changes
No scanner score/rank/actionability changes
No WeeklySetup changes
No Weekly→Daily changes
No daily-entry changes
No execution changes
No alerts/orders
```

`WeeklyEvidencePromotionAuditReport.is_actionable` always returns `False`.

---

## 11. Manual Validation

Targeted:

```powershell
python -m pytest tests/test_weekly_evidence_promotion_audit.py tests/test_weekly_replay_comparison.py tests/test_shadow_weekly_thesis.py -v
```

Weekly foundation regressions:

```powershell
python -m pytest tests/test_weekly_behavior_evolution.py tests/test_weekly_behavior_state.py tests/test_weekly_decision_audit.py tests/test_weekly_legacy_decision_baseline.py -v
```

Scanner regressions:

```powershell
python -m pytest tests/test_scanner_full_resume_equivalence.py tests/test_production_scanner.py -v
```

Full backend suite:

```powershell
python -m pytest tests -q
```

---

## 12. Next Step

After WF6 is manually validated and merged, run the audit on broad historical
symbol/time datasets and inspect robustness before deciding whether WF7 should
change any production weekly qualification semantics.

Possible WF7 outcomes remain data-driven:

```text
keep legacy qualification unchanged
retain structural persistence but allow validated earlier behavior
replace the hard named-event confirmation with validated behavior confirmation
replace binary opposing-event rejection with validated contradiction semantics
keep currently read-only evidence read-only because it adds no robust value
```

WF6 itself chooses none of these outcomes.
