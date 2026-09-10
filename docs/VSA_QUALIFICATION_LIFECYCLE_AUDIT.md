# VSA Qualification Lifecycle Audit

PR #79 adds an audit-only qualification lifecycle review layer.

It is designed for the problem found during Milestone 6 review: a persistent bullish or bearish qualification can remain active even when newer VSA evidence contradicts it. The LT.NS March 2026 case is the key example: bearish qualification stayed active while demand evidence appeared later in the sequence.

## Purpose

The qualification lifecycle audit answers:

- Is the current persistent qualification still supported by fresh VSA evidence?
- Is current VSA evidence directly opposing the active qualification?
- Is the qualification mixed/conflicted rather than cleanly invalidated?
- Is the qualification stale or unsupported by current evidence?
- Should we wait for follow-through before invalidating the context?

This is not a production scanner change. It is an audit/export layer used before detector or scoring changes.

## Input

The CLI can consume saved JSON from any of these earlier Milestone 6 outputs:

- `/api/vsa-audit/events` audit JSON.
- `vsa_audit_candidate_events.py` candidate-event JSON.
- `vsa_audit_batch_review.py` batch-review JSON.
- `vsa_audit_candidate_triage.py` triage JSON.

For the standard basket flow, use the PR #78 triage file:

```powershell
python scripts/vsa_qualification_lifecycle_audit.py standard_basket_triage.json --json-output standard_basket_qualification_lifecycle.json --csv-output standard_basket_qualification_lifecycle.csv
```

To include rows where the qualification appears currently active/supported, add:

```powershell
--include-active
```

The default excludes active rows so the output stays focused on review-needed lifecycle issues.

## Output fields

Each row is grouped by symbol/week before classification, so a same-week qualification conflict plus sibling Effort-vs-Result candidate appears as one lifecycle review row.

Important fields:

- `symbol`.
- `replay_week`.
- `qualification`.
- `qualification_side`.
- `current_vsa_bias`.
- `lifecycle_status`.
- `severity_grade`.
- `severity_score`.
- `source_row_count`.
- `candidate_families`.
- `candidate_codes`.
- `triage_buckets`.
- `supporting_event_codes`.
- `opposing_event_codes`.
- `source_audit_flags`.
- `recommended_action`.
- `reason`.

## Lifecycle statuses

### `invalidated_review`

The qualification has opposing current VSA evidence and no same-side supporting VSA evidence in the reviewed bar.

Example pattern:

- `persistent_bearish` qualification.
- Current target/scoring evidence includes `increasing_demand` or `demand_coming_in`.
- No same-week bearish VSA support remains.

This is a review label only. It does not invalidate production state.

### `conflicted`

The qualification is opposed by current evidence, but the same row also has mixed evidence. This should not immediately flip the context. It needs separation between active qualification, mixed evidence, and detector scoring.

Example pattern:

- `persistent_bullish` qualification.
- Same week contains bearish evidence such as `increasing_supply` and bullish evidence such as `stopping_volume` or `selling_climax`.

### `expired_review`

The qualification appears stale or unsupported by fresh evidence.

Example triggers:

- `qualification_without_current_evidence`.
- `stale_scoring_evidence`.
- `structural_event_without_vsa_confirmation` with no current evidence support.

### `needs_follow_through`

A candidate challenges the active qualification, but the evidence is not strong enough to mark the qualification as invalidated even in audit.

This is useful when Effort-vs-Result, absorption, or high-volume reversal candidates appear but still need later confirmation.

### `active`

The qualification is still supported by current same-side evidence.

This status is only included when `--include-active` is used.

## Recommended workflow

After PR #78:

```powershell
python scripts/vsa_audit_candidate_triage.py standard_basket_review.json --json-output standard_basket_triage.json --csv-output standard_basket_triage.csv
```

Then run PR #79:

```powershell
python scripts/vsa_qualification_lifecycle_audit.py standard_basket_triage.json --json-output standard_basket_qualification_lifecycle.json --csv-output standard_basket_qualification_lifecycle.csv
```

Review the JSON first. Use the CSV for spreadsheet filtering by:

- `lifecycle_status`.
- `severity_grade`.
- `symbol`.
- `opposing_event_codes`.
- `supporting_event_codes`.

## Scope guard

This module is audit/export only.

It does not:

- Load market data.
- Call providers.
- Replay the scanner.
- Activate detectors.
- Change scanner scoring or ranking.
- Change API endpoint behavior.
- Change frontend behavior.
- Persist scanner state or decision context.
- Add broker, order, account, funds, holdings, margin, credential, or position-sizing behavior.

## Why this comes before production detector changes

The 30-symbol basket produced many Effort-vs-Result, absorption, and high-volume reversal candidates. That means broad production activation could be noisy.

Qualification lifecycle issues are narrower. They fix the story/context problem first: old bullish or bearish qualification should not dominate the reading after fresh opposing VSA evidence appears.

This PR does not implement production invalidation yet. It produces the review table needed to design that safely.
