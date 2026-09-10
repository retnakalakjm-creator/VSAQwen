# VSA qualification lifecycle labels

PR #81 adds a production-safe label helper for persistent qualification state.

The goal is to expose a clean lifecycle read for the existing scanner qualification without changing detector rules, scanner ranking, scanner scoring, API behavior, frontend behavior, persistence, or broker/account/order behavior.

## Why this exists

The standard basket audit chain showed that the highest-value production-facing problem is not broad Effort-vs-Result or absorption activation. It is stale or contradictory persistent qualification context.

The PR #80 transition output proposed:

- `invalidate_qualification`: 12 rows.
- `mark_conflicted`: 3 rows.
- `expire_qualification`: 1 row.
- `wait_for_follow_through`: 3 rows.

PR #81 turns that into a small deterministic helper that can label production scanner candidates using already-computed evidence.

## Labels

The helper emits these labels:

- `active`: persistent qualification has fresh same-side production VSA support.
- `conflicted`: persistent qualification has fresh same-side and opposing production VSA evidence in the same scoring context.
- `invalidated`: persistent qualification has fresh opposing production VSA evidence and no same-side support.
- `expired`: persistent qualification lacks fresh same-side production VSA confirmation.
- `needs_follow_through`: persistent qualification has an opposing challenge, but it comes from stale or fallback evidence and should not immediately flip the story.
- `unqualified`: no persistent bullish/bearish qualification exists.

## Production-safety rules

The helper:

- Reads existing scanner/candidate fields only.
- Does not load market data.
- Does not replay the scanner.
- Does not mutate scanner state.
- Does not persist anything.
- Does not change scanner scoring or ranking.
- Does not change API or frontend behavior in this PR.
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
```

For LT.NS-style cases, a persistent bearish qualification with fresh `demand_coming_in` and no same-side bearish support should label as:

```text
invalidated
```

This is still a label, not a ranking/scoring/order decision.

## Next step

After PR #81, a later PR can wire this label into the API decision context or frontend story panel, after verifying that the label remains consistent with the production scanner path.
