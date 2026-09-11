# Milestone 6A Expanded Rerun Audit Snapshot

This document records the expanded-basket rerun performed after PR #95 updated the Tata Motors symbols in the repeatable VSA audit baskets.

The purpose of this rerun was to confirm whether the basket-maintenance change altered the Milestone 6A audit conclusion before starting any new backend event-family work.

Project rule:

```text
foundation first, visualization second
```

## Rerun context

PR #95 changed the expanded basket by:

- replacing `TATAMOTORS.NS` with `TMPV.NS`;
- adding `TMCV.NS` for the commercial-vehicle listing;
- removing `IOC.NS` from the expanded additional-symbol list so the basket remains exactly 60 symbols.

The rerun used:

```text
timeframe = 1W
start_week = 2026-03-02
horizon_weeks = 8
basket = milestone6_expanded_india_large_mid_60
```

## Rerun artifacts

The reviewed artifact chain was:

```text
expanded_large_mid_basket_audit(1).json
expanded_large_mid_basket_review(1).json
expanded_large_mid_basket_triage(1).json
expanded_large_mid_basket_causality_v2(1).json
expanded_large_mid_basket_mixed_clusters(1).json
expanded_large_mid_basket_mixed_cluster_grades(1).json
expanded_large_mid_basket_lifecycle_proposals(1).json
```

## Basket validation

The rerun confirms the PR #95 basket maintenance worked.

```text
requested_symbols = 60
audit_results = 59
stale_symbol_absent = TATAMOTORS.NS
replacement_symbol_present = TMPV.NS
commercial_vehicle_symbol_requested = TMCV.NS
removed_symbol_absent = IOC.NS
```

`TMPV.NS` returned audit rows.

`TMCV.NS` was requested but skipped by provider/data-depth validation:

```text
TMCV.NS -> Only 209 daily bars found.
```

This is a data-depth issue for a newer listing, not a scanner logic issue.

## TMPV.NS effect

`TMPV.NS` produced 8 weekly replay rows for the audit window.

Its audit behavior included:

- no target event on most replay rows;
- one `increasing_supply` production event;
- one week with `increasing_demand` and `demand_coming_in`;
- one `review_potential_spring_or_shakeout` diagnostic;
- no high-priority downstream candidate rows.

Because `TMPV.NS` did not enter the downstream high-priority candidate set, it did not change triage, causality, mixed-cluster, grading, or lifecycle proposal conclusions.

## Candidate review summary

The expanded rerun produced the same high-priority candidate shape as the pre-PR #95 expanded audit.

```text
total_review_rows = 212
high_priority_rows = 212
medium_priority_rows = 0
```

Candidate family counts:

```text
audit_effort_gt_result_candidate = 86
audit_high_volume_reversal_candidate = 55
audit_absorption_candidate = 42
audit_qualification_conflict_candidate = 29
```

## Triage summary

The rerun triage still shows that detector activation is not the immediate next step.

```text
clean_candidate = 30
contradictory_production_evidence = 74
likely_noisy_diagnostic = 5
manual_chart_review = 23
overlapping_candidate_cluster = 51
qualification_lifecycle_issue = 29
```

Triage grades:

```text
A = 57
B = 53
C = 97
D = 5
```

The key point is that only a minority of candidate rows are clean. Most rows still require lifecycle, contradiction, manual chart, or overlapping-cluster review.

## Causality summary

Causality still shows mixed and invalidating evidence at a level that blocks broad detector activation.

```text
bullish = 199
bearish = 13
```

Outcome counts:

```text
follow_through_visible = 24
invalidated_by_later_evidence = 46
lifecycle_transition_review = 29
mixed_follow_through_conflict = 37
no_later_selected_audit_rows = 67
pending_insufficient_future_rows = 9
```

The conclusion is that high-volume reversal, absorption, and effort-vs-result candidates still need gating and lifecycle interpretation before production weighting.

## Mixed-cluster summary

The mixed-cluster stage produced:

```text
total_clusters = 16
total_mixed_rows = 37
max_gap_rows = 2
```

Event-family coverage across clusters:

```text
effort_vs_result = 13
absorption = 8
high_volume_reversal = 8
```

This confirms the major problem is still grouped mixed-event behavior, not a single isolated detector threshold.

## Mixed-cluster grading summary

The graded mixed clusters were:

```text
A = 8
B = 7
C = 1
total_graded_clusters = 16
```

Recommended action counts:

```text
review_detector_gates_before_activation = 8
review_lifecycle_invalidation_or_supersession = 6
review_supply_warning_against_active_bullish_context = 2
```

Review type counts:

```text
bearish_context_demand_reversal_cluster = 6
bullish_context_supply_warning_cluster = 2
unqualified_bidirectional_detector_conflict = 8
```

This keeps the next phase pointed at lifecycle and gate review, not broad detector activation.

## Lifecycle proposal summary

The lifecycle proposal stage produced 6 proposal rows.

Next audit step counts:

```text
chart_confirm_supersession_rule_candidate = 1
chart_review_conflict_before_invalidation_or_supersession = 5
```

Transition counts:

```text
propose_supersede_bearish_context_with_demand_review = 1
propose_mark_bearish_conflicted_pending_supersession = 5
```

Skipped cluster counts:

```text
detector_gate_review = 8
active_bullish_supply_warning_review = 2
```

## Lifecycle proposal rows

The high-value lifecycle proposal rows are:

| Symbol | Cluster | Grade | Proposed transition | Next audit step | Confidence |
| --- | --- | --- | --- | --- | --- |
| `LT.NS` | `LT.NS:234-237` | A | `propose_mark_bearish_conflicted_pending_supersession` | `chart_review_conflict_before_invalidation_or_supersession` | 100 |
| `DRREDDY.NS` | `DRREDDY.NS:236-238` | A | `propose_supersede_bearish_context_with_demand_review` | `chart_confirm_supersession_rule_candidate` | 100 |
| `GRASIM.NS` | `GRASIM.NS:233-233` | A | `propose_mark_bearish_conflicted_pending_supersession` | `chart_review_conflict_before_invalidation_or_supersession` | 100 |
| `AMBUJACEM.NS` | `AMBUJACEM.NS:235-235` | A | `propose_mark_bearish_conflicted_pending_supersession` | `chart_review_conflict_before_invalidation_or_supersession` | 88 |
| `GODREJCP.NS` | `GODREJCP.NS:238-238` | A | `propose_mark_bearish_conflicted_pending_supersession` | `chart_review_conflict_before_invalidation_or_supersession` | 86 |
| `BRITANNIA.NS` | `BRITANNIA.NS:238-238` | B | `propose_mark_bearish_conflicted_pending_supersession` | `chart_review_conflict_before_invalidation_or_supersession` | 76 |

`DRREDDY.NS` remains the strongest candidate for confirming a future supersession rule candidate, because it is the only proposal with:

```text
proposed_transition = propose_supersede_bearish_context_with_demand_review
next_audit_step = chart_confirm_supersession_rule_candidate
proposal_confidence = 100
```

## Decision after rerun

The PR #95 rerun did not change the Milestone 6A conclusion.

Do not broadly activate:

- Stopping Volume;
- Spring/Shakeout;
- Absorption;
- Effort-vs-Result;
- High Volume Reversal.

The next backend step should be lifecycle/supersession review first, especially around the DRREDDY.NS supersession candidate and the LT.NS conflicted-pending-supersession casebook behavior.

## Recommended next milestone split

After this snapshot, the project should split future work into separate phase docs instead of growing one Milestone 6 document indefinitely.

Suggested active foundation sequence:

```text
MILESTONE_6A_VSA_EVENT_FOUNDATION.md
MILESTONE_6A_EXPANDED_RERUN_AUDIT_SNAPSHOT.md
MILESTONE_6B_LIFECYCLE_SUPERSESSION_REVIEW.md
MILESTONE_6C_STOPPING_VOLUME_SPRING_SHAKEOUT.md
MILESTONE_6D_NEXT_BACKGROUND_EVENT_FOUNDATION.md
```

Visual replay remains deferred and should stay on hold until the backend foundation is mature enough to support trustworthy replay semantics:

```text
MILESTONE_6D_VISUAL_REPLAY_CASEBOOK.md -> deferred / holding area, not the next active phase
```

The project doctrine remains:

```text
foundation first, visualization second
```

After Milestone 6C, continue with the next background-event foundation instead of moving directly into visualization.

## Status

Milestone 6A remains complete after the PR #95 rerun.

The next production-safe backend work should not be event activation. It should be lifecycle supersession review using the saved proposal rows and chart confirmation.