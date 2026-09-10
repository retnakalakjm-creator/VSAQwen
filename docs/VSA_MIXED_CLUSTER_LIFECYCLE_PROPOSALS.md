# VSA Mixed-Cluster Lifecycle Proposals

This document describes the audit-only mixed-cluster lifecycle proposal helper for Milestone 6.

## Purpose

The helper consumes graded mixed-cluster output and extracts only the clusters that are lifecycle candidates.

The primary case is:

> Persistent bearish qualification is challenged by demand/reversal evidence, while some supply or structure caution may still remain.

This is the LT.NS / DRREDDY.NS / GRASIM.NS pattern surfaced by the standard-basket mixed-cluster grading pass.

## Inputs

The helper accepts saved JSON from `vsa_mixed_cluster_grading.py`, including files such as:

```powershell
standard_basket_mixed_cluster_grades.json
```

It expects a top-level `rows` list, but also accepts a top-level `clusters` list or a direct list of row dictionaries.

## Outputs

The output is audit-only and contains lifecycle proposal rows with:

- `proposed_transition`
- `proposal_confidence`
- `next_audit_step`
- `demand_evidence_codes`
- `opposing_evidence_codes`
- `caution_evidence_codes`
- `proposal_reasons`
- `proposal_read`

## Transition labels

### `propose_mark_bearish_conflicted_pending_supersession`

Use this when persistent bearish qualification is challenged by demand/reversal evidence, but supply or bearish structure caution remains in the same cluster.

This is intentionally conservative. The old bearish qualification should not be presented as cleanly active, but the new demand evidence should also not be activated blindly as a bullish reversal.

### `propose_invalidate_bearish_qualification`

Use this when persistent bearish qualification is challenged by demand/reversal evidence and no supply/structure caution remains in the graded cluster.

This still requires chart confirmation before production behavior changes.

### `propose_supersede_bearish_context_with_demand_review`

Use this when persistent bearish qualification is challenged by strong demand evidence across multiple reversal/absorption families, without bearish structure caution.

This is a candidate for casebook review before any future production supersession rule.

## Skipped clusters

Non-lifecycle mixed clusters are summarized separately as skipped counts:

- `detector_gate_review`
- `active_bullish_supply_warning_review`
- `other_mixed_cluster_review`

This keeps detector-gate problems separate from lifecycle-invalidation work.

## Guardrails

This helper is audit-only. It does not:

- load market data
- call providers
- replay the scanner
- mutate scanner state
- persist output
- activate detectors
- change scanner scoring/ranking
- change API or frontend behavior
- add broker/order/account/position behavior

## CLI

```powershell
python scripts/vsa_mixed_cluster_lifecycle_proposals.py standard_basket_mixed_cluster_grades.json --json-output standard_basket_mixed_cluster_lifecycle_proposals.json --csv-output standard_basket_mixed_cluster_lifecycle_proposals.csv
```

## How to use the result

Use the lifecycle proposal JSON to focus manual review on clusters where an old persistent bearish qualification may need to be invalidated, marked conflicted, or superseded by newer demand evidence.

Do not use this output to activate Effort-vs-Result, Absorption, or High Volume Reversal detectors directly. Detector-gate clusters should continue through the separate detector-gate audit path.
