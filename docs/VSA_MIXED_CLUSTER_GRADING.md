# VSA Mixed-Cluster Grading

This document describes the audit-only mixed-cluster grading helper for Milestone 6.

## Purpose

`vsa_mixed_cluster_grading.py` consumes grouped mixed-event cluster output from `vsa_mixed_event_cluster_review.py` and assigns each cluster:

- a review type
- a grade
- a priority score
- a recommended next audit action
- concise grading reasons

The goal is to decide which mixed clusters are lifecycle candidates, which are supply/demand warning clusters, and which are detector-gate conflicts before any production detector activation or scanner weighting change.

## Input

The expected input is JSON with a top-level `clusters` list, such as:

```powershell
python scripts/vsa_mixed_event_cluster_review.py standard_basket_causality_v2.json --json-output standard_basket_mixed_clusters.json --csv-output standard_basket_mixed_clusters.csv
```

Then grade it:

```powershell
python scripts/vsa_mixed_cluster_grading.py standard_basket_mixed_clusters.json --json-output standard_basket_mixed_cluster_grades.json --csv-output standard_basket_mixed_cluster_grades.csv
```

## Review types

The helper currently emits these review types:

- `bearish_context_demand_reversal_cluster`
  - A persistent bearish qualification is being challenged by demand/reversal evidence.
  - This is the LT-style review bucket.
  - Next action: review lifecycle invalidation or supersession.

- `bullish_context_supply_warning_cluster`
  - A persistent bullish qualification has supply/structure warning evidence inside the mixed cluster.
  - Next action: review the supply warning against the active bullish context.

- `unqualified_bidirectional_detector_conflict`
  - No active qualification exists, but the cluster contains both demand/reversal and supply/structure evidence.
  - Next action: inspect detector gates before activation.

- `same_week_multi_family_conflict`
  - Multiple candidate families fire on the same completed bar.
  - Next action: review same-week grouping before weighting.

- `multi_week_multi_family_conflict`
  - The cluster spans multiple rows or families but does not fit a stronger lifecycle bucket.
  - Next action: review the sequence before weighting a single family.

- `manual_mixed_cluster_review`
  - Fallback bucket for clusters that do not match stronger rules.

## Grades

Grades are based on a deterministic priority score:

- `A` — highest-priority review candidate.
- `B` — useful but less decisive review candidate.
- `C` — lower-priority/manual casebook review.

The score rewards:

- persistent qualification involvement
- bearish-context demand reversal cases
- bullish-context supply warnings
- multiple event families
- larger row count
- structure evidence
- contradictory production evidence buckets
- multi-week span

## Guardrails

This helper is audit-only. It does not:

- load market data
- call providers
- replay the scanner
- mutate scanner state
- persist output
- activate detectors
- change scanner scoring/ranking
- change API behavior
- change frontend behavior
- add broker/order/account/position behavior

It only transforms saved audit JSON into a compact review plan.

## Intended use

Use this after generating mixed clusters:

```powershell
python scripts/vsa_mixed_cluster_grading.py standard_basket_mixed_clusters.json --json-output standard_basket_mixed_cluster_grades.json --csv-output standard_basket_mixed_cluster_grades.csv
```

Then review Grade-A clusters first. The key question is not whether a single detector fired, but whether the whole cluster should become:

- a lifecycle invalidation case
- a supply warning case
- a detector-gate calibration case
- a chart casebook example

Production scanner behavior should only change after repeated audit evidence supports a specific rule.
