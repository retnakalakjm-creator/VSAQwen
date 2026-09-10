# VSA Audit Candidate Batch Review

This is a Milestone 6 audit/calibration surface.

It converts saved VSA audit output or saved candidate-event output into compact JSON and CSV review files for basket-level manual review.

## Why this exists

After PR #75, a single audit output can be converted into structured audit-only candidate events. That works for a single case such as `LT.NS`, but before changing production detector rules we need to know whether the same candidate logic is clean or noisy across a larger stock basket.

The batch review script helps answer:

- Which symbols have the most high-priority candidate rows?
- Which candidate families appear most often?
- Are Effort-vs-Result and absorption candidates clustered in only one stock, or repeated across the basket?
- Which rows deserve chart review before production scoring changes?

## Scope guard

This surface is intentionally audit-only.

It does not:

- Download market data.
- Call providers.
- Replay the scanner.
- Persist scanner state.
- Write decision context or journal entries.
- Change production detector rules.
- Change scanner scoring or ranking.
- Change API behavior.
- Change frontend behavior.
- Add broker, order, account, funds, holdings, margin, credential, or position-sizing behavior.

## Input

The script accepts either:

1. Full `/api/vsa-audit/events` JSON.
2. Candidate-event JSON produced by `scripts/vsa_audit_candidate_events.py`.
3. A flat list of audit rows or candidate-event rows.

Save a multi-symbol audit output first, for example:

```powershell
# Start backend separately, then save the browser/API output to basket_audit.json.
http://127.0.0.1:8000/api/vsa-audit/events?symbols=LT.NS,SRF.NS,RELIANCE.NS&start_week=2026-03-02&horizon_weeks=8&max_symbols=30
```

## Command

Generate both JSON and CSV review files:

```powershell
python scripts/vsa_audit_batch_review.py basket_audit.json --min-priority high --json-output basket_candidate_review.json --csv-output basket_candidate_review.csv
```

The same command can also consume candidate-event JSON:

```powershell
python scripts/vsa_audit_candidate_events.py basket_audit.json --output basket_candidate_events.json
python scripts/vsa_audit_batch_review.py basket_candidate_events.json --min-priority high --json-output basket_candidate_review.json --csv-output basket_candidate_review.csv
```

## JSON output

The JSON output includes:

- `audit_only`.
- `source_candidate_rows`.
- `total_review_rows`.
- `high_priority_rows`.
- `medium_priority_rows`.
- `symbols_with_candidates`.
- `candidate_counts`.
- `family_counts`.
- `priority_counts`.
- `symbol_counts`.
- `week_counts`.
- `top_review_symbols`.
- `review_focus`.
- `rows`.

`top_review_symbols` ranks symbols by high-priority candidate count first, then total candidate count.

`review_focus` groups rows by candidate code so we can quickly see whether Effort-vs-Result, absorption, high-volume reversal, or lifecycle conflicts dominate the basket.

## CSV output

The CSV output is designed for spreadsheet/manual chart review.

Columns:

- `symbol`.
- `replay_week`.
- `replay_bar_index`.
- `candidate_family`.
- `candidate_code`.
- `priority`.
- `direction`.
- `qualification`.
- `production_status`.
- `target_event_codes`.
- `scoring_event_codes`.
- `source_diagnostics`.
- `source_audit_flags`.
- `reason`.

List fields are pipe-separated so they remain compact in one spreadsheet cell.

## Review workflow

Recommended basket workflow:

1. Run `/api/vsa-audit/events` for the selected basket and horizon.
2. Generate high-priority batch review JSON/CSV.
3. Sort the CSV by `symbol`, `replay_week`, and `candidate_family`.
4. Inspect only high-priority rows first.
5. Record false positives and clean examples in the Milestone 6 casebook.
6. Only then decide whether any audit candidate family should become production evidence.

## Interpretation

Candidate rows are not confirmed VSA events.

They mean:

```text
The audit layer found a bar or context that deserves review before detector/scoring changes.
```

They do not mean:

```text
The scanner has confirmed a trade signal or production event.
```

This distinction is important. The goal of PR #76 is to reduce manual review time without prematurely changing scanner behavior.
