# VSA Event Audit Runner

This document describes the Milestone 6 audit runner added for backend VSA event foundation work.

The audit runner is intentionally a decision-support and research tool. It does not change scanner scoring, ranking, production VSA rules, decision context persistence, journal persistence, broker integration, orders, accounts, funds, holdings, margins, credentials, or position sizing.

## Purpose

The runner gives us a fast way to inspect what the scanner would have known point-in-time across many symbols.

It is designed for questions such as:

- If the current week were 24 Feb 2025 on LT.NS, what events would the scanner know?
- What events fired in each following completed week?
- Did structural weakening later receive bearish follow-through?
- Did possible Stopping Volume, Spring, Shakeout, Absorption, Demand Coming In, or Effort vs Result events appear in the expected weeks?
- Which rows need manual chart review?

## API endpoint

```text
GET /api/vsa-audit/events
```

Query parameters:

| Parameter | Required | Meaning |
| --- | --- | --- |
| `symbols` | Yes | Comma, semicolon, or newline separated symbol list. |
| `start_week` | No | First replay week/date, inclusive. |
| `end_week` | No | Last replay week/date, inclusive. |
| `horizon_weeks` | No | Number of weeks to replay when `end_week` is omitted, or latest-window size. Default is 20. |
| `max_symbols` | No | Safety cap for one audit request. Default is 30. |

Example:

```text
http://127.0.0.1:8000/api/vsa-audit/events?symbols=LT.NS,SRF.NS,RELIANCE.NS&start_week=2025-02-24&horizon_weeks=20
```

LT.NS March 2026 case:

```text
http://127.0.0.1:8000/api/vsa-audit/events?symbols=LT.NS&start_week=2026-03-02&horizon_weeks=8
```

Latest 20 completed weekly bars for 30 symbols:

```text
http://127.0.0.1:8000/api/vsa-audit/events?symbols=LT.NS,SRF.NS,RELIANCE.NS&horizon_weeks=20&max_symbols=30
```

## Output shape

The endpoint returns one result per symbol.

Each replay row contains:

- `symbol`
- `replay_bar_index`
- `replay_week`
- `event_count`
- `target_event_codes`
- `scoring_event_codes`
- `qualifying_event_codes`
- `campaign_event_codes`
- `structural_event_codes`
- `vsa_event_codes`
- `qualification`
- `actionable`
- `used_fallback_evidence`
- `scoring_evidence_age`
- `net_pressure`
- `confidence`
- `audit_flags`
- `detector_diagnostics`
- `notes`

Important distinction:

- `target_event_codes` means events that fired on that replay week.
- `scoring_event_codes` means events the scanner is using for scoring, which may be earlier than the replay week.
- `qualifying_event_codes` means structural qualification evidence.
- `campaign_event_codes` means broader current context from the point-in-time scan.
- `structural_event_codes` separates structural progression events from normal VSA events.
- `vsa_event_codes` separates non-structural VSA events from structural events.
- `audit_flags` gives machine-readable review labels so the user can filter important exception rows quickly.
- `detector_diagnostics` gives audit-only review hints for high-volume reversal, absorption, spring/shakeout, and Effort-vs-Result candidates that may not have fired as production evidence.

This distinction is important for cases where old evidence is still contributing to the story.

## Audit flags

PR #71 added machine-readable flags to reduce manual review time.

Current flags:

| Flag | Meaning |
| --- | --- |
| `no_target_event` | No event fired on that replay week. |
| `fallback_scoring_evidence` | Scanner is scoring from earlier evidence instead of same-week evidence. |
| `stale_scoring_evidence` | Scoring evidence age exceeds the scanner's maximum actionable VSA age. |
| `actionable_audit_row` | Scanner marked the row actionable; manually review before production interpretation. |
| `structural_event_without_vsa_confirmation` | A structural progression event fired without same-week non-structural VSA confirmation. |
| `bullish_vsa_against_bearish_qualification` | Bullish VSA fired while qualification remained bearish. |
| `bearish_vsa_against_bullish_qualification` | Bearish VSA fired while qualification remained bullish. |
| `conflicting_target_vsa_pressure` | Bullish and bearish VSA fired on the same replay week. |
| `conflicting_scoring_vsa_pressure` | Bullish and bearish VSA both appeared in scoring evidence. |
| `qualification_without_current_evidence` | Persistent qualification remains even though no current target, scoring, or campaign evidence is present. |

These are audit labels only. They do not change production scanner scoring, ranking, qualification, or event detection.

## Detector diagnostics

PR #72 adds audit-only detector diagnostics. These diagnostics are deliberately weaker than production VSA rules. They identify bars that deserve review; they do not create evidence, change scanner behavior, change scoring, or activate disabled detectors.

Current diagnostics:

| Diagnostic | Meaning |
| --- | --- |
| `review_potential_stopping_volume` | High-volume down bar closed off the low, but `stopping_volume` did not fire on that replay week. |
| `review_potential_effort_gt_result` | Very-high-volume effort produced muted downside result, but `effort_gt_result` did not fire. |
| `review_potential_absorption` | High-volume bar in bearish context closed off the low or midpoint without same-week absorption/demand evidence. |
| `review_potential_spring_or_shakeout` | Bar interacted with recent support and recovered, but `spring`/`shakeout` did not fire. |
| `review_high_volume_reversal_without_bullish_event` | High-volume reversal-style bar appeared in bearish context without same-week bullish VSA evidence. |

Use `detector_diagnostics` together with `audit_flags` to filter rows for manual chart review. For example, on LT.NS March 2026, diagnostics should help isolate weeks where high volume and muted downside result suggest possible Effort-vs-Result, Stopping Volume, absorption, or Spring/Shakeout review even if production evidence did not fire.

## Implementation safeguards

The runner is built to avoid slow manual review and avoid accidental production behavior changes.

Current safeguards:

- The API loads completed weekly data once per symbol through the existing service/data path.
- Daily data loading continues to use the existing cache and incremental refresh behavior.
- Weekly replay uses completed weekly bars only.
- The audit function performs one bounded scanner pass up to the requested end week for each symbol.
- Detector diagnostics reuse the already-calculated metrics for each replay row; they do not trigger a second scanner pass.
- It emits compact rows, not full historical warehouses.
- It records per-symbol errors without aborting the whole batch.
- It does not persist scanner state, decision context, or decision journal entries.
- It does not enable or change any VSA detector.
- It does not change scanner scoring or ranking.
- It does not perform any broker, order, account, funds, holdings, margin, credential, or position-size action.

## What this does not solve yet

The audit runner, flags, and diagnostics provide the review surface. They do not yet add event outcome or invalidation logic.

Still pending:

- Outcome labels such as invalidated, absorbed, failed continuation, confirmed follow-through, and expired.
- Full detector failure diagnostics explaining each individual production detector gate.
- Effort vs Result production activation/calibration.
- Stopping Volume, Spring, Shakeout, Test, and Absorption strengthening.
- Standard 30+ stock audit basket.
- Export formats for longer offline review.

## Recommended manual review process

Use the runner to reduce chart-review time.

1. Run the audit for the target case and a basket of real symbols.
2. Sort/filter rows by important conditions:
   - `audit_flags` is not empty,
   - `detector_diagnostics` is not empty,
   - target event fired,
   - scoring evidence is stale,
   - structural event fired without non-structural VSA confirmation,
   - actionable row,
   - conflicting event families,
   - expected event missing.
3. Manually inspect only flagged/diagnostic exception rows on the chart.
4. Update `docs/MILESTONE_6_VSA_EVENT_FOUNDATION.md` with findings.
5. Only after multiple confirmed cases, change production detector logic.

## LT.NS cases to run first

### Feb-Mar 2025 structural weakness followed by rally

```text
/api/vsa-audit/events?symbols=LT.NS&start_week=2025-02-24&horizon_weeks=20
```

Questions:

- Did structural weakening fire on the expected confirmation week?
- Was there bearish follow-through?
- Did later demand/spring/recovery evidence appear?
- When should the old bearish structure stop contributing to the current story?

First audit findings:

- 24 Feb 2025: no target event, but older bearish supply evidence was still used for scoring and the row was actionable.
- 17 Mar 2025: `increasing_demand` and `demand_coming_in` fired while qualification remained `persistent_bearish`.
- 24 Mar 2025: `structural_progression_weakening` fired without same-week non-structural VSA confirmation.
- Demand evidence fired again later, but the bearish qualification remained.
- Some later rows had no target, scoring, or campaign evidence while qualification stayed `persistent_bearish`.

### Mar 2026 high-volume support / effort-vs-result / spring candidate

```text
/api/vsa-audit/events?symbols=LT.NS&start_week=2026-03-02&horizon_weeks=8
```

Questions:

- Did Stopping Volume fire around 02 Mar 2026?
- Did the high-volume bars around 09 Mar and 16 Mar show support/absorption behavior?
- Did Spring or Shakeout fire around 23 Mar 2026 only when point-in-time confirmation was available?
- Did the scanner miss Effort vs Result because production collection still needs calibration?

First audit findings:

- 02 Mar 2026: `increasing_supply` fired; `stopping_volume` did not fire.
- 09 Mar 2026: no target event fired; earlier `increasing_supply` remained scoring evidence.
- 16 Mar 2026: `structural_progression_weakening` fired; `effort_gt_result`, absorption, and stopping-volume style demand evidence did not fire.
- 23 Mar 2026: `demand_coming_in` fired; `spring` and `shakeout` did not fire.
- 06 Apr 2026: `increasing_demand` and `demand_coming_in` fired.
- 13 Apr and 20 Apr 2026: no target event fired, but old `increasing_supply` still appeared as scoring evidence with high age.

Second audit step:

- Re-run this case after PR #72 and filter rows where `detector_diagnostics` is not empty.
- Use those rows to decide whether Effort-vs-Result, Stopping Volume, Spring/Shakeout, or absorption rules are too strict.
