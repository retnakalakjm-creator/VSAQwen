# VSA Mixed-Event Cluster Review

This document describes the audit-only grouped mixed-event cluster review helper.

## Purpose

The causality diagnostics layer can identify rows where later same-symbol evidence contains both same-side follow-through and opposing evidence. Those rows receive:

```text
mixed_follow_through_conflict
```

A single symbol/week can produce several mixed rows from related candidate families such as Effort vs Result, absorption, and high-volume reversal. Reviewing those rows individually can exaggerate the number of cases and hide the real sequence.

The mixed-event cluster review groups nearby same-symbol mixed rows into one compact sequence so we can inspect the actual VSA story once.

## Inputs

The helper accepts saved JSON from the causality diagnostics output, usually:

```powershell
python scripts/vsa_event_causality_diagnostics.py standard_basket_triage.json --json-output standard_basket_causality_v2.json --csv-output standard_basket_causality_v2.csv
```

It then consumes the generated `standard_basket_causality_v2.json`.

## Grouping rule

Rows are grouped when they are:

- same symbol
- `outcome_label == mixed_follow_through_conflict`
- within `max_gap_rows` replay bars of the previous mixed row for that symbol

Default gap:

```text
max_gap_rows = 2
```

This keeps nearby LT-style clusters together while avoiding one very long symbol-level bucket.

## Output

Each cluster includes:

- symbol
- start/end week
- start/end replay bar index
- source row count
- candidate event families
- candidate event codes
- qualifications
- source buckets
- supporting event codes
- opposing event codes
- future lifecycle actions
- compact causal read
- recommended action

The recommended action is intentionally conservative:

```text
review_grouped_mixed_cluster_before_rule_change
```

## CLI

```powershell
python scripts/vsa_mixed_event_cluster_review.py standard_basket_causality_v2.json --json-output standard_basket_mixed_clusters.json --csv-output standard_basket_mixed_clusters.csv
```

Optional grouping gap:

```powershell
python scripts/vsa_mixed_event_cluster_review.py standard_basket_causality_v2.json --max-gap-rows 2 --json-output standard_basket_mixed_clusters.json --csv-output standard_basket_mixed_clusters.csv
```

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

It only groups already-saved causality rows.

## How to use the result

Use the cluster JSON to choose manual review cases. Use the CSV to review one grouped sequence at a time.

For each cluster, ask:

- Is this one coherent VSA sequence or unrelated nearby events?
- Is the apparent demand actually absorption, spring/shakeout, or continuation?
- Is opposing supply/structure stronger than demand follow-through?
- Should lifecycle invalidation/conflict handle the case before adding detector weight?
- Does the cluster reveal a missing production-safe event lifecycle rule?

Do not activate Effort vs Result, absorption, or high-volume reversal detectors from this output alone. First confirm repeated, coherent chart behavior across grouped clusters.
