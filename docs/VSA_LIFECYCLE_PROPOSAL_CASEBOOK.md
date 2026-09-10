# VSA lifecycle proposal casebook export

This document describes the Milestone 6 audit-only lifecycle proposal casebook export.

The casebook export consumes output from `vsa_mixed_cluster_lifecycle_proposals.py`, such as:

```powershell
python scripts/vsa_mixed_cluster_lifecycle_proposals.py standard_basket_mixed_cluster_grades.json --json-output standard_basket_mixed_cluster_lifecycle_proposals.json --csv-output standard_basket_mixed_cluster_lifecycle_proposals.csv
```

It then creates compact manual-review rows for the lifecycle proposals that survived the mixed-cluster grading pass.

## Purpose

The lifecycle proposal output identifies persistent-bearish contexts where demand/reversal evidence challenges the active bearish qualification. This casebook export packages those proposals for chart review before any production lifecycle behavior changes.

The first standard-basket proposal output reduced the mixed-cluster set to three lifecycle candidates:

- `LT.NS`
- `DRREDDY.NS`
- `GRASIM.NS`

The casebook keeps those rows compact and reviewable while preserving the evidence required for manual confirmation.

## Command

```powershell
python scripts/vsa_lifecycle_proposal_casebook.py standard_basket_mixed_cluster_lifecycle_proposals.json --json-output standard_basket_lifecycle_casebook.json --csv-output standard_basket_lifecycle_casebook.csv
```

## Output fields

Each casebook row includes:

- `casebook_id`
- `symbol`
- `cluster_id`
- `case_type`
- `grade`
- `proposal_confidence`
- `proposed_transition`
- `recommended_casebook_action`
- `manual_review_status`
- `chart_review_status`
- `production_decision_status`
- `start_week`
- `end_week`
- `start_bar_index`
- `end_bar_index`
- `source_review_type`
- `source_priority_score`
- `demand_evidence_codes`
- `caution_evidence_codes`
- `opposing_evidence_codes`
- `event_families`
- `proposal_reasons`
- `manual_review_notes`
- `case_read`

## Case types

### `conflict_pending_supersession`

A persistent bearish qualification is challenged by demand/reversal evidence, but caution evidence remains. This should be reviewed as a possible conflicted bearish context rather than a direct bullish activation.

Typical proposed transition:

```text
propose_mark_bearish_conflicted_pending_supersession
```

Typical next audit step:

```text
chart_review_conflict_before_invalidation_or_supersession
```

### `supersession_rule_candidate`

A persistent bearish qualification is challenged by demand/reversal evidence and looks cleaner as a potential supersession case.

Typical proposed transition:

```text
propose_supersede_bearish_context_with_demand_review
```

Typical next audit step:

```text
chart_confirm_supersession_rule_candidate
```

### `manual_lifecycle_review`

Fallback case type for proposal transitions not yet mapped to a specific casebook workflow.

## Review status fields

The export intentionally initializes manual status fields without making any production decision:

```text
manual_review_status: unreviewed
chart_review_status: pending_chart_review
production_decision_status: not_proposed_for_production
manual_review_notes: ""
```

These fields make the CSV useful as a manual review tracker while keeping the repository logic audit-only.

## Guardrails

This helper and CLI are audit-only. They do not:

- load market data
- call providers
- replay scanners
- mutate scanner state
- persist output
- activate detectors
- change scoring or ranking
- change API or frontend behavior
- touch broker, order, account, position, funds, holdings, margin, credential, or position-sizing behavior

The output is not a production signal. It is a compact casebook for deciding which lifecycle transition rules deserve chart confirmation and later production design.
