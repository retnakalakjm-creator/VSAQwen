# VSA qualification transition proposal

PR #80 adds an audit-only transition proposal layer after the PR #79 qualification lifecycle audit.

The purpose is to turn lifecycle review statuses into explicit proposed actions before any production scanner, story, scoring, or UI behavior is changed.

## Why this exists

The standard basket audit showed that the major issue is not broad Effort-vs-Result activation yet. The clearest next issue is persistent qualification lifecycle handling:

- Bearish qualification sometimes remains active after bullish demand evidence appears.
- Bullish qualification sometimes remains active after bearish supply evidence appears.
- Some rows contain mixed bullish and bearish evidence and should not immediately flip direction.
- Some rows need later completed-bar follow-through before the qualification changes.

The transition proposal layer keeps this behavior reviewable and deterministic while still avoiding production behavior changes.

## Input

The helper accepts any of these saved JSON files:

- Raw `/api/vsa-audit/events` output.
- Candidate-event JSON from `scripts/vsa_audit_candidate_events.py`.
- Batch-review JSON from `scripts/vsa_audit_batch_review.py`.
- Triage JSON from `scripts/vsa_audit_candidate_triage.py`.
- Qualification lifecycle JSON from `scripts/vsa_qualification_lifecycle_audit.py`.

The normal Milestone 6 input is:

```powershell
standard_basket_qualification_lifecycle.json
```

## Command

```powershell
python scripts/vsa_qualification_transition_proposal.py standard_basket_qualification_lifecycle.json --json-output standard_basket_qualification_transitions.json --csv-output standard_basket_qualification_transitions.csv
```

To include active/supported qualification rows as a baseline:

```powershell
python scripts/vsa_qualification_transition_proposal.py standard_basket_qualification_lifecycle.json --include-active --json-output standard_basket_qualification_transitions_with_active.json --csv-output standard_basket_qualification_transitions_with_active.csv
```

## Proposed actions

The output uses these proposed actions:

| Lifecycle status | Proposed action | Meaning |
| --- | --- | --- |
| `invalidated_review` | `invalidate_qualification` | Current VSA evidence opposes the persistent qualification and has no same-side support on the reviewed bar. |
| `conflicted` | `mark_conflicted` | Evidence is mixed or contradictory; the story should separate mixed context from persistent qualification state. |
| `expired_review` | `expire_qualification` | Fresh same-side evidence is absent and the persistent qualification may be stale. |
| `needs_follow_through` | `wait_for_follow_through` | Opposing evidence challenges the qualification, but later completed bars should confirm before invalidation. |
| `active` | `keep_active` | Included only with `--include-active`; the qualification still has same-side support. |

## Output fields

Each proposal row includes:

- `symbol`.
- `replay_week`.
- `replay_bar_index`.
- `qualification` and `qualification_side`.
- `current_vsa_bias`.
- `lifecycle_status`.
- `proposed_action`.
- `proposal_grade`.
- `proposal_score`.
- `proposal_confidence`.
- `supporting_event_codes`.
- `opposing_event_codes`.
- `target_event_codes`.
- `scoring_event_codes`.
- `candidate_families` and `candidate_codes`.
- `source_audit_flags`.
- `source_lifecycle_reason`.
- `proposal_reason`.
- `guardrails`.
- `recommended_action`.

The summary also includes:

- `action_counts`.
- `status_counts`.
- `grade_counts`.
- `confidence_counts`.
- `qualification_counts`.
- `symbol_counts`.
- `week_counts`.
- `transition_focus`.
- `top_transition_symbols`.

## Guardrails

This layer is audit/export-only.

It does not:

- Load market data.
- Call providers.
- Replay the scanner.
- Activate detectors.
- Change production scanner scoring or ranking.
- Change API endpoint behavior.
- Change frontend behavior.
- Persist results.
- Add broker, order, account, funds, holdings, margin, credential, or position-sizing behavior.

It also explicitly keeps Effort-vs-Result, absorption, and high-volume reversal as review context only. Those detector families must not be activated as production evidence in this PR.

## How to use the output

Start with `transition_focus`:

1. Review `invalidate_qualification` rows first.
2. Review `mark_conflicted` rows second.
3. Review `expire_qualification` rows third.
4. Keep `wait_for_follow_through` rows as observation candidates.
5. Use `keep_active` only as a baseline if `--include-active` was requested.

For LT.NS, the important expected behavior is that persistent bearish qualification should be proposed for invalidation review when completed weekly demand evidence appears with no same-side bearish support.

## Next design step

After the proposal output is reviewed, the next production-safe design PR should define how the scanner/story layer will represent qualification state transitions, still without broker or trading actions.

Likely design states:

- active.
- conflicted.
- invalidated.
- expired.
- pending follow-through.

A later implementation PR can then apply those labels to decision context/story output without changing order/account behavior.
