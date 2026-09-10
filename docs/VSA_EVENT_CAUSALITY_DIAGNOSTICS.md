# VSA Event Causality Diagnostics

This document describes the audit-only VSA event causality diagnostics helper.

## Purpose

The helper reviews already-generated VSA audit outputs and asks a narrow sequence question:

> After an event or candidate appeared, did later same-symbol audit rows support it, contradict it, leave it unresolved, mix support with contradiction, or convert it into a lifecycle/context review?

This is designed for Milestone 6 backend VSA-event foundation work. It helps inspect event follow-through, invalidation, supersession, mixed-event clusters, stale-context behavior, and incomplete review windows before any production detector or scanner-scoring change.

## Inputs

The helper accepts saved JSON from existing audit layers, including:

- VSA event audit output
- candidate-event output
- candidate triage output
- qualification lifecycle output
- qualification transition proposal output
- batch review output containing a top-level `rows` list
- API-style audit output containing nested `results[].rows`

`.txt` files containing JSON are accepted by the CLI.

## Output labels

Each review row receives one audit-only `outcome_label`:

- `follow_through_visible` — later same-symbol audit rows contain same-side VSA evidence and no later opposing/invalidation evidence inside the selected review window.
- `mixed_follow_through_conflict` — later same-symbol audit rows contain both same-side support and opposing VSA evidence or invalidating lifecycle actions. These rows are not clean invalidations and must be reviewed as mixed clusters.
- `invalidated_by_later_evidence` — later same-symbol rows contain opposing VSA evidence or invalidating lifecycle actions without same-side support.
- `no_follow_through_visible` — the review window is complete but no same-side support appears.
- `no_later_selected_audit_rows` — the saved input has no later selected same-symbol rows, so the helper cannot honestly call the event pending or failed. Rerun with a wider/base audit file before interpreting it.
- `pending_insufficient_future_rows` — later same-symbol rows exist, but not enough rows are available to fill the requested review horizon and no support/opposition has appeared yet.
- `lifecycle_transition_review` — the row is a qualification lifecycle/transition action, not a direct price-event outcome.
- `context_only_review` — the row has no clear bullish/bearish event direction.

## Why mixed labels matter

Earlier causality output treated any later opposition as `invalidated_by_later_evidence`, even when same-side support also appeared inside the review window. LT.NS showed this clearly: bullish reversal/absorption candidates could have later `demand_coming_in` and `increasing_demand`, while also having later `structural_progression_weakening` or `increasing_supply`.

Those rows should not be treated as clean detector failures or clean detector confirmations. They are mixed-event clusters and should be reviewed before production activation, decay, or lifecycle rules are changed.

## Guardrails

This helper is audit-only. It does not:

- load market data
- call data providers
- replay the scanner
- mutate scanner state
- persist output
- activate detectors
- change scanner scoring/ranking
- change API or frontend behavior
- add broker/order/account/position behavior

It only summarizes already-saved audit rows.

## CLI

```powershell
python scripts/vsa_event_causality_diagnostics.py standard_basket_triage.json --json-output standard_basket_causality.json --csv-output standard_basket_causality.csv
```

Optional horizon:

```powershell
python scripts/vsa_event_causality_diagnostics.py standard_basket_triage.json --review-horizon-rows 8 --json-output standard_basket_causality.json --csv-output standard_basket_causality.csv
```

## How to use the result

Use the JSON first to identify symbols/events with:

- `mixed_follow_through_conflict`
- `invalidated_by_later_evidence`
- `no_follow_through_visible`
- `no_later_selected_audit_rows`
- `lifecycle_transition_review`

Then use the CSV for manual chart review. Production scanner behavior should only be changed after repeated audit evidence supports a specific rule.
