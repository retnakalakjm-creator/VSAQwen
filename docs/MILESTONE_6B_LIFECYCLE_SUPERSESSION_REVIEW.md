# Milestone 6B: Lifecycle Supersession Review

Milestone 6B starts after the Milestone 6A event-foundation checkpoint and the post-PR #95 expanded-basket rerun.

The goal of this phase is to decide whether any chart-confirmed lifecycle supersession behavior should be promoted safely, without activating broad detector families prematurely.

Project doctrine:

```text
foundation first, visualization second
```

## Position in the roadmap

Milestone 6A completed the audit foundation:

- causality diagnostics;
- mixed-event labels;
- mixed-cluster grouping;
- mixed-cluster grading;
- lifecycle transition proposals;
- lifecycle casebook export;
- conflicted pending-supersession production behavior;
- expanded audit baskets;
- post-PR #95 Tata Motors symbol rerun.

Milestone 6B is the next foundation step.

Milestone 6C should remain the Stopping Volume -> Spring/Shakeout recovery-sequence phase.

Visual replay remains deferred and should not become the active next phase after 6C.

After Milestone 6C, the project should continue to the next background-event foundation before visualization.

## Why 6B exists

The expanded rerun showed that broad detector activation is still unsafe.

The audit pipeline produced meaningful candidate signal, but also many rows that still require lifecycle, contradiction, manual chart, or overlapping-cluster review.

The lifecycle proposal stage narrowed the safest next work to a small set of lifecycle cases instead of a broad detector-family rollout.

Therefore, 6B should review lifecycle supersession directly before touching Stopping Volume, Spring/Shakeout, Absorption, Effort-vs-Result, or High Volume Reversal production behavior.

## Current production-safe baseline

The current production lifecycle behavior supports this state:

```text
persistent_bearish + fresh demand/reversal evidence
  -> conflicted
  -> pending_supersession = true
```

This behavior is intentionally conservative.

It does not:

- flip the scanner bullish automatically;
- invalidate bearish context aggressively;
- treat audit-only diagnostics as production events;
- promote audit candidate families into scoring;
- change ranking or scanner output weight.

6B must preserve this baseline unless chart-confirmed evidence justifies a narrow extension.

## Primary 6B question

6B should answer one question:

```text
When should a conflicted persistent-bearish lifecycle become a chart-confirmed supersession review candidate?
```

This is different from asking whether a bullish detector should activate.

The question is lifecycle-first:

- Was the old bearish qualification still valid?
- Was fresh demand/reversal evidence strong enough to challenge it?
- Was remaining supply evidence weak enough to allow supersession review?
- Did later bars confirm demand follow-through?
- Did the case remain clean enough to avoid detector-gate noise?

## Source evidence from 6A rerun

The post-PR #95 expanded rerun preserved 6 lifecycle proposal rows.

Lifecycle next-step counts:

```text
chart_confirm_supersession_rule_candidate = 1
chart_review_conflict_before_invalidation_or_supersession = 5
```

Transition counts:

```text
propose_supersede_bearish_context_with_demand_review = 1
propose_mark_bearish_conflicted_pending_supersession = 5
```

This means 6B should not start broad.

It should start from the one strongest supersession candidate and compare it against the five conflicted-pending-supersession candidates.

## Primary case: DRREDDY.NS

DRREDDY.NS is the strongest 6B candidate.

Case details:

```text
symbol = DRREDDY.NS
cluster_id = DRREDDY.NS:236-238
grade = A
source_review_type = bearish_context_demand_reversal_cluster
proposed_transition = propose_supersede_bearish_context_with_demand_review
next_audit_step = chart_confirm_supersession_rule_candidate
proposal_confidence = 100
```

Evidence shape:

```text
qualification = persistent_bearish
demand/reversal evidence = increasing_demand, demand_coming_in
caution/opposing evidence = increasing_supply
event families = absorption, high_volume_reversal
```

Reason to review:

DRREDDY.NS has fresh demand/reversal evidence challenging a persistent bearish context, with multiple reversal/absorption families supporting lifecycle review.

Reason to stay conservative:

Supply evidence remains present, so this should not become an automatic bullish flip or broad detector activation.

## Anchor case: LT.NS

LT.NS remains the key conflicted-pending-supersession casebook example.

Case details:

```text
symbol = LT.NS
cluster_id = LT.NS:234-237
grade = A
source_review_type = bearish_context_demand_reversal_cluster
proposed_transition = propose_mark_bearish_conflicted_pending_supersession
next_audit_step = chart_review_conflict_before_invalidation_or_supersession
proposal_confidence = 100
```

Evidence shape:

```text
qualification = persistent_bearish
demand/reversal evidence = demand_coming_in, increasing_demand
caution/opposing evidence = structural_progression_weakening, increasing_supply
event families = absorption, effort_vs_result, high_volume_reversal
```

Reason to review:

LT.NS shows the exact behavior that PR #91 handled safely: fresh demand evidence challenges a bearish lifecycle state.

Reason to stay conservative:

Structural weakening and supply evidence remain in the same cluster window, so the correct behavior is conflicted pending supersession, not clean supersession.

## Comparison cases

The remaining proposal rows are useful controls.

| Symbol | Cluster | Grade | Proposed transition | Confidence | Role in 6B |
| --- | --- | --- | --- | --- | --- |
| `GRASIM.NS` | `GRASIM.NS:233-233` | A | `propose_mark_bearish_conflicted_pending_supersession` | 100 | Compare demand challenge with hidden-supply caution |
| `AMBUJACEM.NS` | `AMBUJACEM.NS:235-235` | A | `propose_mark_bearish_conflicted_pending_supersession` | 88 | Compare lower-confidence conflict case |
| `GODREJCP.NS` | `GODREJCP.NS:238-238` | A | `propose_mark_bearish_conflicted_pending_supersession` | 86 | Compare selling-climax demand challenge with structural caution |
| `BRITANNIA.NS` | `BRITANNIA.NS:238-238` | B | `propose_mark_bearish_conflicted_pending_supersession` | 76 | Lower-grade control case |

These cases should prevent DRREDDY.NS from being overfit into an unsafe rule.

## 6B review checklist

Before writing production code, review each case against this checklist:

1. Confirm the persistent bearish qualification was active before the demand/reversal evidence appeared.
2. Confirm the demand/reversal evidence is fresh and same-window, not stale fallback scoring evidence.
3. Confirm whether the demand evidence has follow-through on later bars.
4. Confirm whether opposing supply or structural weakening remains active.
5. Confirm whether the case is a lifecycle issue or only detector-gate noise.
6. Confirm that audit-only candidate families are not being treated as production events.
7. Confirm the proposed lifecycle change would not alter scanner ranking, scoring, provider calls, replay behavior, persistence, or frontend output unless explicitly scoped.

## 6B implementation rule

The first implementation PR in 6B should be narrow.

Allowed shape:

```text
chart-confirmed lifecycle supersession review marker
```

Disallowed shape:

```text
broad detector activation
automatic bullish flip
audit-only candidate promotion
scoring/ranking weight change
visual replay UI
```

If production behavior changes, it must be isolated to lifecycle labeling and covered by direct unit tests.

## Possible production-safe extension

A future 6B code PR may introduce a narrow lifecycle outcome such as:

```text
status = supersession_review
```

or another conservative name that clearly avoids implying a completed bullish flip.

The state should mean:

```text
persistent bearish context has a chart-confirmed demand/reversal challenge strong enough for supersession review, but the scanner has not automatically flipped bullish.
```

This is intentionally weaker than:

```text
superseded
bullish
invalidated
activated
```

Naming matters because the scanner must not imply more certainty than the audit supports.

## Test expectations for a future code PR

A later implementation PR should include tests for:

- DRREDDY-style supersession-review candidate;
- LT-style conflicted pending-supersession case remaining conflicted;
- stale or fallback demand evidence not becoming supersession review;
- supply/structural conflict blocking clean supersession;
- audit-only candidate codes remaining ignored by production lifecycle bias;
- unqualified rows not creating lifecycle supersession state;
- persistent bullish contexts remaining outside bearish supersession logic.

## Non-goals

6B does not activate:

- Stopping Volume;
- Spring/Shakeout;
- Absorption;
- Effort-vs-Result;
- High Volume Reversal.

6B does not build:

- TradingView-style replay bars;
- visual replay casebook UI;
- frontend chart annotation;
- replay scrubbing;
- provider-data loading changes.

## Transition to 6C

After 6B resolves lifecycle supersession review, Milestone 6C can start from a cleaner foundation and focus on:

```text
Stopping Volume -> Spring / Shakeout recovery sequence
```

6C should still follow the same rule:

```text
foundation first, visualization second
```

6C should not assume every high-volume reversal, absorption, or effort-vs-result candidate is production-ready.

It should use 6A/6B lifecycle and mixed-cluster lessons to gate event behavior safely.

## Visual replay holding area

`MILESTONE_6D_VISUAL_REPLAY_CASEBOOK.md` remains a deferred holding area.

Do not make visual replay the active next phase after 6C.

After 6C, continue with the next background-event foundation unless the backend event semantics are mature enough to support trustworthy replay.

## Current 6B status

6B starts as a foundation-review milestone.

The next safe step is to review DRREDDY.NS and LT.NS as lifecycle cases before adding any production behavior.

No scanner logic should change until the chart-confirmation criteria are written down and tested.