# VSA audit candidate triage

PR #78 adds an audit-only triage layer for VSA candidate-event review rows.

The previous batch review step answers: which symbols, weeks, and candidate families deserve review?

The triage step answers: which rows are cleaner calibration candidates, which are overlapping clusters, which are contradicted by current production evidence, and which are qualification lifecycle problems?

## Why this exists

The standard 30-symbol March-April 2026 basket produced a broad high-priority candidate queue:

- 134 high-priority review rows.
- 48 Effort-vs-Result candidates.
- 38 high-volume reversal candidates.
- 33 absorption candidates.
- 15 qualification lifecycle candidates.

That is too broad to activate directly in production. The next safe step is to grade the review rows before changing detector rules.

## Command

Run this after generating `standard_basket_review.json`:

```powershell
python scripts/vsa_audit_candidate_triage.py standard_basket_review.json --json-output standard_basket_triage.json --csv-output standard_basket_triage.csv
```

The command also accepts saved `/api/vsa-audit/events` JSON, candidate-event JSON, or batch-review JSON:

```powershell
python scripts/vsa_audit_candidate_triage.py standard_basket_audit.json --min-priority high --json-output standard_basket_triage.json --csv-output standard_basket_triage.csv
```

## Triage buckets

### `qualification_lifecycle_issue`

Rows where current VSA evidence conflicts with an active qualification state.

Examples:

- Bullish VSA appears while qualification is still `persistent_bearish`.
- Bearish VSA appears while qualification is still `persistent_bullish`.

These should be prioritized because they point to stale context, expiry, or invalidation behavior rather than one isolated detector rule.

### `overlapping_candidate_cluster`

Rows where multiple candidate families appear on the same symbol and week.

Example cluster:

- Effort-vs-Result candidate.
- Absorption candidate.
- High-volume reversal candidate.

These should be reviewed together on the chart. Activating one detector alone may be misleading if the real issue is a broader high-volume support / reversal cluster.

### `contradictory_production_evidence`

Rows where the candidate is a bullish reversal review but production evidence is still bearish.

Examples:

- Candidate says Effort-vs-Result / absorption review.
- Same row still has `hidden_supply`, `increasing_supply`, `supply_coming_in`, `buying_climax`, `upthrust`, or `no_demand`.

These need detector-gate inspection before production activation.

### `clean_candidate`

Rows where the candidate has no immediate contradiction from production evidence.

These are the best calibration candidates after manual chart confirmation.

### `likely_noisy_diagnostic`

Rows where a bullish reversal candidate appears while the qualification is already bullish and production evidence is not bearish.

These may be continuation or redundant diagnostics rather than true reversal events.

### `manual_chart_review`

Rows where the available compact audit context is insufficient or mixed.

## Output shape

The JSON output contains:

- `bucket_counts`.
- `grade_counts`.
- `top_triage_symbols`.
- `triage_focus`.
- flat triage `rows` with cluster metadata.

Each row includes:

- original symbol/week/candidate fields.
- `triage_bucket`.
- `triage_grade`.
- `triage_score`.
- `cluster_size`.
- sibling candidate families for the same symbol/week.
- same-week candidate codes.
- target/scoring evidence context.
- triage reasons.
- recommended action.

## Scope

This is audit/export only.

It does not:

- Load market data.
- Call providers.
- Replay the scanner.
- Persist scanner state or decision context.
- Activate VSA detectors.
- Change scanner scoring or ranking.
- Change API behavior.
- Change frontend behavior.
- Add broker, order, account, funds, holdings, margin, credential, or position-sizing behavior.

## Next use

Use `standard_basket_triage.json` and `standard_basket_triage.csv` to decide which family should be worked on first:

1. Qualification lifecycle invalidation if lifecycle rows remain concentrated and clear.
2. Detector gate diagnostics for contradictory production evidence.
3. Effort-vs-Result / absorption calibration only after clean candidates are separated from noisy and clustered rows.
