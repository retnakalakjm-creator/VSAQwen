# Effort vs Result and Absorption Calibration

This document describes the Milestone 6 audit-only calibration helper added after the first LT.NS high-volume reversal review.

The calibration helper does not change production scanner scoring, ranking, evidence collection, detector rules, decision context persistence, journal persistence, broker integration, orders, accounts, funds, holdings, margins, credentials, or position sizing.

## Why this exists

PR #70 gave us point-in-time audit rows.

PR #71 added `audit_flags` so exception rows are easy to filter.

PR #72 added `detector_diagnostics` so likely high-volume reversal, absorption, Stopping Volume, Spring/Shakeout, and Effort-vs-Result candidates can be reviewed without pretending they are confirmed evidence.

This calibration helper is the next step: it converts audit output into a compact review queue for detector calibration.

## Main helper

```python
from vsa_audit_calibration import build_effort_absorption_calibration_summary

summary = build_effort_absorption_calibration_summary(audit_json)
```

Input can be:

- the full JSON returned by `/api/vsa-audit/events`,
- a list of symbol result dictionaries,
- or a flat list of audit row dictionaries.

Output contains:

- `rows`: selected calibration review rows,
- `priority_counts`,
- `diagnostic_counts`,
- `tag_counts`,
- `symbol_counts`,
- `audit_only: true`.

## Selected rows

Rows are selected when they contain Effort/Absorption/high-volume reversal diagnostics or important context-mismatch audit flags.

Selected diagnostics include:

- `review_potential_effort_gt_result`,
- `review_potential_absorption`,
- `review_high_volume_reversal_without_bullish_event`,
- `review_potential_stopping_volume`,
- `review_potential_spring_or_shakeout`.

Selected context flags include:

- `bullish_vsa_against_bearish_qualification`,
- `bearish_vsa_against_bullish_qualification`,
- `structural_event_without_vsa_confirmation`,
- `stale_scoring_evidence`.

## Calibration tags

The helper emits tags that can be used for sorting and review:

- `effort_gt_result_candidate`,
- `absorption_candidate`,
- `missing_bullish_reversal_event`,
- `stopping_volume_candidate`,
- `spring_shakeout_candidate`,
- `qualification_conflict`,
- `stale_evidence_review`,
- `not_confirmed_by_current_detector`.

## Priority rules

Rows are marked `high` priority when diagnostics suggest Effort-vs-Result, absorption, or high-volume reversal behavior but no expected production event fired.

Rows are also marked `high` priority when bullish VSA conflicts with bearish qualification, or bearish VSA conflicts with bullish qualification.

Other selected rows are marked `medium` priority.

## How to use for LT.NS March 2026

1. Run the audit endpoint:

```text
/api/vsa-audit/events?symbols=LT.NS&start_week=2026-03-02&horizon_weeks=8
```

2. Save the JSON response.

3. Feed the JSON into `build_effort_absorption_calibration_summary`.

4. Review high-priority rows first.

For the known LT.NS March 2026 case, the important rows are expected around:

- 02 Mar 2026: Stopping Volume / Effort-vs-Result / Absorption candidate.
- 16 Mar 2026: Effort-vs-Result candidate.
- 23 Mar 2026: Spring/Shakeout and qualification-conflict candidate.
- 06 Apr 2026: bullish demand against bearish qualification candidate.

## Guardrail

This helper creates a review queue, not evidence. It is deliberately separate from production detector activation.

Production detector changes should come only after reviewing a wider symbol basket and false-positive set.
