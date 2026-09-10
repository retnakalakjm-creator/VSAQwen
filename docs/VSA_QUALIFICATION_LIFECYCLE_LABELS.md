# VSA qualification lifecycle labels

PR #81 adds a production-safe label helper for persistent qualification state. PR #91 makes the persistent-bearish demand-challenge path more conservative by marking it as `conflicted` pending supersession instead of a direct invalidation.

The goal is to expose a clean lifecycle read for the existing scanner qualification without changing detector rules, scanner ranking, scanner scoring, persistence, or trade execution behavior.

## Why this exists

The standard basket audit chain showed that the highest-value production-facing problem is not broad Effort-vs-Result or absorption activation. It is stale or contradictory persistent qualification context.

The PR #90 casebook export narrowed the mixed-cluster lifecycle review to three casebook rows:

- LT.NS: `conflict_pending_supersession`.
- DRREDDY.NS: `supersession_rule_candidate`.
- GRASIM.NS: `conflict_pending_supersession`.

PR #91 implements the safest first production-facing lifecycle behavior from that casebook: when a persistent bearish qualification is challenged by fresh production demand/reversal evidence, the lifecycle status becomes `conflicted` and the reason says it is pending supersession. The helper does not flip the context bullish automatically.

## Labels

The helper emits these labels:

- `active`: persistent qualification has fresh same-side production VSA support.
- `conflicted`: persistent qualification has fresh same-side and opposing production VSA evidence, or a persistent bearish qualification is challenged by fresh production demand/reversal evidence and is pending supersession.
- `invalidated`: persistent qualification has fresh opposing production VSA evidence and no same-side support, except for the conservative persistent-bearish demand/reversal challenge path handled as `conflicted` pending supersession.
- `expired`: persistent qualification lacks fresh same-side production VSA confirmation.
- `needs_follow_through`: persistent qualification has an opposing challenge, but it comes from stale or fallback evidence and should not immediately flip the story.
- `unqualified`: no persistent bullish/bearish qualification exists.

## Bearish pending-supersession rule

A persistent bearish qualification is marked `conflicted` with `pending_supersession=True` when fresh, non-fallback production demand/reversal evidence challenges it.

Examples of qualifying challenge evidence:

- `stopping_volume`
- `demand_coming_in`
- `increasing_demand`
- `hidden_demand`
- `demand_drying_up`
- `no_supply`
- `spring`
- `test`
- `selling_climax`
- `shakeout`

This is intentionally conservative:

- It does not flip the qualification bullish automatically.
- It does not activate Effort-vs-Result, absorption, or high-volume reversal candidates.
- It does not mutate scanner state.
- It keeps stale/fallback opposing evidence on the existing `needs_follow_through` path.

## Production-safety rules

The helper:

- Reads existing scanner/candidate fields only.
- Does not load market data.
- Does not replay the scanner.
- Does not mutate scanner state.
- Does not persist anything.
- Does not change scanner scoring or ranking.
- Does not promote Effort-vs-Result, `absorption`, or high-volume reversal audit candidates into production evidence.
- Assumes callers have already used the completed-weekly-bar production path.

## Evidence direction set

The helper uses existing production VSA event codes only.

Bullish production VSA examples:

- `stopping_volume`
- `demand_coming_in`
- `increasing_demand`
- `hidden_demand`
- `no_supply`
- `spring`
- `test`
- `selling_climax`
- `shakeout`

Bearish production VSA examples:

- `buying_climax`
- `supply_coming_in`
- `increasing_supply`
- `hidden_supply`
- `supply_high_volume`
- `supply_wide_spread`
- `supply_absorption`
- `upthrust`
- `no_demand`

Audit-only candidates deliberately stay outside the production direction sets:

- `effort_gt_result`
- `result_gt_effort`
- `absorption`
- `audit_effort_gt_result_candidate`
- `audit_absorption_candidate`
- `audit_high_volume_reversal_candidate`

## Example use

```python
from qualification_lifecycle_labels import label_candidate_qualification_lifecycle

label = label_candidate_qualification_lifecycle(candidate)
print(label.status.value)
print(label.reason)
print(label.pending_supersession)
```

For LT.NS-style cases, a persistent bearish qualification with fresh `demand_coming_in` and no same-side bearish support now labels as:

```text
conflicted
```

The label result also sets:

```text
pending_supersession=True
```

This is still a lifecycle label, not a scanner ranking/scoring decision and not a trade action.

## Next step

After PR #91, the next production-safe review is to make the VSA Story wording explicitly explain `pending_supersession=True` when the API exposes it. Detector activation should remain separate and later.
