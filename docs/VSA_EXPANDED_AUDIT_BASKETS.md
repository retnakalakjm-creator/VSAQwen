# VSA Expanded Audit Baskets

PR #94 adds wider, repeatable audit baskets before the next backend VSA event change.

## Reason

The original 30-symbol basket is useful as a stable regression baseline, but it is too narrow to decide whether new VSA event behavior is consistent across different stocks.

Before changing Stopping Volume, Spring/Shakeout, Absorption, or Effort-vs-Result production behavior, the audit process should test both:

- the original 30-symbol largecap baseline; and
- a broader largecap plus midcap basket.

This follows the project rule:

```text
foundation first, visualization second
```

## Tata Motors symbol maintenance

PR #95 updates the audit baskets for the Tata Motors demerger/listing symbol changes:

- `TATAMOTORS.NS` is replaced with `TMPV.NS`.
- `TMCV.NS` is added to the expanded 60-symbol basket.
- `IOC.NS` is removed from the expanded additional-symbol list so the expanded basket remains exactly 60 symbols.

This is basket maintenance only. It does not change scanner logic, event detectors, scoring, ranking, API behavior, frontend behavior, replay behavior, or persistence.

## Available baskets

### `milestone6_standard_india_large_cap_30`

The original 30-symbol basket.

Use this for:

- regression checks;
- comparing future PRs with earlier PR #77 to PR #93 outputs;
- ensuring the LT.NS, RELIANCE.NS, DRREDDY.NS, GRASIM.NS, and other known casebook symbols stay stable.

Default output prefix:

```text
standard_basket
```

### `milestone6_expanded_india_large_mid_60`

A 60-symbol expanded basket.

It keeps the original 30 symbols as the first 30 entries, then adds another 30 liquid largecap / selected midcap symbols.

Use this for:

- consistency checks before backend event activation;
- broader false-positive detection;
- validating whether a detector works beyond the original basket;
- comparing largecap behavior with selected midcap behavior.

Default output prefix:

```text
expanded_large_mid_basket
```

### `milestone6_midcap_focus_30`

A separate 30-symbol midcap-focused basket.

Use this for:

- noise and false-positive review;
- stress-testing high-volume event diagnostics;
- checking whether midcap volume/spread behavior causes unstable VSA labels.

Default output prefix:

```text
midcap_focus_basket
```

## CLI usage

Print the default original basket:

```powershell
python scripts/vsa_standard_audit_basket.py
```

Print machine-readable JSON for the default basket:

```powershell
python scripts/vsa_standard_audit_basket.py --json
```

Print the expanded basket workflow:

```powershell
python scripts/vsa_standard_audit_basket.py --basket milestone6_expanded_india_large_mid_60
```

Print the midcap-focused basket workflow:

```powershell
python scripts/vsa_standard_audit_basket.py --basket milestone6_midcap_focus_30
```

## Suggested next audit workflow

Run the expanded 60-symbol basket after pulling the latest main:

```powershell
python scripts/vsa_standard_audit_basket.py --basket milestone6_expanded_india_large_mid_60 --json
```

Then use the printed `commands.save_audit`, `commands.candidate_events`, and `commands.batch_review` values.

Expected output file names:

```text
expanded_large_mid_basket_audit.json
expanded_large_mid_basket_candidate_events_high.json
expanded_large_mid_basket_review.json
expanded_large_mid_basket_review.csv
```

After that, continue the downstream Milestone 6 workflow as needed:

```powershell
python scripts/vsa_audit_candidate_triage.py expanded_large_mid_basket_review.json --json-output expanded_large_mid_basket_triage.json --csv-output expanded_large_mid_basket_triage.csv
python scripts/vsa_event_causality_diagnostics.py expanded_large_mid_basket_triage.json --json-output expanded_large_mid_basket_causality_v2.json --csv-output expanded_large_mid_basket_causality_v2.csv
python scripts/vsa_mixed_event_cluster_review.py expanded_large_mid_basket_causality_v2.json --json-output expanded_large_mid_basket_mixed_clusters.json --csv-output expanded_large_mid_basket_mixed_clusters.csv
python scripts/vsa_mixed_cluster_grading.py expanded_large_mid_basket_mixed_clusters.json --json-output expanded_large_mid_basket_mixed_cluster_grades.json --csv-output expanded_large_mid_basket_mixed_cluster_grades.csv
python scripts/vsa_mixed_cluster_lifecycle_proposals.py expanded_large_mid_basket_mixed_cluster_grades.json --json-output expanded_large_mid_basket_lifecycle_proposals.json --csv-output expanded_large_mid_basket_lifecycle_proposals.csv
```

## Scope

This is a basket-definition and command-helper change only.

It does not:

- fetch market data;
- call providers;
- replay the scanner by itself;
- change scanner state;
- activate detectors;
- change Stopping Volume, Spring/Shakeout, Absorption, Effort-vs-Result, or High Volume Reversal behavior;
- change scoring or ranking;
- change API behavior;
- change frontend behavior;
- change persistence.

## Next backend event after expanded audit

After running the expanded basket and reviewing consistency, the next backend event foundation remains:

```text
Stopping Volume -> Spring / Shakeout recovery sequence
```

Do not activate the event broadly until the expanded basket shows consistent behavior and acceptable false-positive levels.
