# VSA Audit Candidate Events

This document describes the Milestone 6 audit-only candidate-event layer.

It is intentionally separate from production VSA evidence. Candidate events are review objects built from `/api/vsa-audit/events` output after the scanner has already produced normal target/scoring/campaign/qualifying evidence.

They do not change scanner scoring, ranking, detector rules, API analysis behavior, decision-context persistence, journal persistence, frontend behavior, broker integration, orders, accounts, funds, holdings, margins, credentials, or position sizing.

## Why this exists

PR #70 added point-in-time VSA audit rows.

PR #71 added audit flags.

PR #72 added detector diagnostics.

PR #73 added a compact calibration summary helper.

PR #74 added a CLI so saved audit files such as `LT_New.txt` can be summarized locally.

The next problem is that diagnostics are still just labels. For detector calibration we need structured candidate objects that say:

- what candidate event should be reviewed,
- which diagnostic or audit flag produced it,
- whether current production evidence already confirmed it,
- what family it belongs to,
- whether it is high or medium priority,
- and why it was selected.

## Main helper

```python
from vsa_audit_candidate_events import build_audit_candidate_event_summary

summary = build_audit_candidate_event_summary(audit_json)
```

Input can be:

- the full JSON returned by `/api/vsa-audit/events`,
- a list of symbol result dictionaries,
- or a flat list of audit row dictionaries.

Output contains:

- `rows`,
- `candidate_counts`,
- `family_counts`,
- `priority_counts`,
- `symbol_counts`,
- `audit_only: true`.

## CLI usage

After saving audit output, run:

```powershell
python scripts/vsa_audit_candidate_events.py LT_New.txt
```

Write the candidate-event summary to a file:

```powershell
python scripts/vsa_audit_candidate_events.py LT_New.txt --output LT_candidate_events.json
```

Show only high-priority candidate events:

```powershell
python scripts/vsa_audit_candidate_events.py LT_New.txt --min-priority high --output LT_candidate_events_high.json
```

## Candidate event codes

The helper currently emits:

- `audit_effort_gt_result_candidate`
- `audit_absorption_candidate`
- `audit_stopping_volume_candidate`
- `audit_spring_shakeout_candidate`
- `audit_high_volume_reversal_candidate`
- `audit_qualification_conflict_candidate`
- `audit_stale_evidence_candidate`

These are audit candidates only. They are not production `EvidenceCode` values.

## Candidate fields

Each row includes:

- `symbol`
- `replay_week`
- `replay_bar_index`
- `candidate_code`
- `candidate_family`
- `direction`
- `priority`
- `production_status`
- `source_diagnostics`
- `source_audit_flags`
- `target_event_codes`
- `scoring_event_codes`
- `qualification`
- `reason`
- `audit_only`

## Production-status guardrail

The helper checks whether the related production event already fired in `target_event_codes`.

For example:

- `audit_effort_gt_result_candidate` is suppressed if `effort_gt_result` already fired.
- `audit_absorption_candidate` is suppressed if `absorption` already fired.
- `audit_stopping_volume_candidate` is suppressed if `stopping_volume` already fired.
- `audit_spring_shakeout_candidate` is suppressed if `spring` or `shakeout` already fired.

This keeps the output focused on likely misses and review cases.

## LT.NS March 2026 usage

Use the same audit file produced from:

```text
/api/vsa-audit/events?symbols=LT.NS&start_week=2026-03-02&horizon_weeks=8
```

Then run:

```powershell
python scripts/vsa_audit_candidate_events.py LT_New.txt --output LT_candidate_events.json
```

Expected high-value rows should include:

- 02 Mar 2026: Effort-vs-Result / absorption / Stopping Volume / high-volume reversal candidates.
- 16 Mar 2026: Effort-vs-Result candidate.
- 23 Mar 2026: Effort-vs-Result / Spring-Shakeout / qualification-conflict candidates.
- 06 Apr 2026: qualification-conflict candidate if demand remains against bearish qualification.
- 13 Apr 2026: absorption / high-volume reversal / stale-evidence review candidates.

## Review workflow

1. Run `/api/vsa-audit/events` for one symbol or basket.
2. Save the JSON response.
3. Run `scripts/vsa_audit_candidate_events.py`.
4. Review high-priority candidate events first.
5. Only after reviewing false positives, decide whether a candidate family should become:
   - audit-only candidate evidence,
   - low-weight production evidence,
   - or fully wired production detector evidence.

## Guardrail

Candidate events are deliberately a bridge between diagnostics and production detector work. They make calibration review more structured without changing live scanner behavior.
