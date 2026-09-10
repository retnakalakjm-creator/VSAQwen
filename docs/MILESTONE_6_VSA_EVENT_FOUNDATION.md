# Milestone 6: Backend VSA Event Foundation

This document is the living planning, audit, and decision record for Milestone 6.

Milestone 6 shifts priority from frontend polish to the backend VSA event foundation. The goal is to make VSA detection, event timing, event outcome, invalidation, and chart interpretation concrete, testable, point-in-time safe, and fast enough to run across a basket of real symbols without long manual review sessions.

## Operating principle

We should not manually spend long hours inspecting 30 stocks one by one. We already have an optimized pipeline with incremental refresh. Milestone 6 should reuse that pipeline to run automated VSA event audits quickly, then reserve manual chart review only for exceptions, misses, contradictions, and high-value case studies.

Every Milestone 6 PR should update this document when it adds a new finding, new test case, new event weakness, new audit surface, or new TODO.

## Current priority

1. Backend VSA event replay and audit foundation.
2. Strengthen and calibrate existing VSA events.
3. Add missing or underused VSA events.
4. Add event lifecycle, follow-through, invalidation, and absorption logic.
5. Only then return to scanner ranking and frontend refinement.

## Key observations from review

### Point-in-time replay is required

When we inspect a completed chart, it is easy to explain the move after seeing the full future. That is dangerous for a scanner.

Milestone 6 must answer questions like:

- If the current week were 24 Feb 2025, what would the scanner know?
- What events would fire in each following completed week?
- Did later bars validate, invalidate, absorb, or contradict the original event?
- Did an old bearish or bullish event remain active after the market disproved it?

### LT.NS Feb-Mar 2025: structural weakness was not enough

Observed chart case:

- LT.NS formed a lower-low swing around 24 Feb 2025.
- Structural Progression Weakening was confirmed around 24 Mar 2025.
- Price later rallied strongly.

Interpretation:

- The system may have correctly detected structural weakness at that point.
- But a lower low is not automatically bearish in VSA.
- A lower low can become a spring, shakeout, selling-climax recovery, or absorbed supply event if downside follow-through fails and demand returns.
- The missing layer is event lifecycle and outcome status.

Required future behavior:

- Structural weakness should start as pending or active only until follow-through is evaluated.
- If price does not continue lower and later reclaims structure, the event should be marked as invalidated, absorbed, or failed bearish continuation.
- The UI/story should distinguish swing formed date from confirmation/story date.

### Swing formed date vs confirmation date must be clear

Observed UI confusion:

- Clicking a story event dated 24 Mar 2025 may navigate to a structural swing whose actual pivot formed on 24 Feb 2025.
- This is not necessarily a data error.
- Structural swings often form first and are confirmed later.

Required future display:

- Swing formed: date of the pivot bar.
- Confirmed in story: date when the swing/event became known.
- On chart: optionally mark the pivot bar with the swing marker and the confirmation/story bar with a separate vertical shade.

### LT.NS Mar 2026: effort versus result must be audited

Observed chart case:

- 02 Mar 2026: possible Stopping Volume candidate.
- 09 Mar 2026: very-high-volume follow-up support or absorption candidate.
- 16 Mar 2026: ultra-high-volume bar where spread/result should be inspected carefully.
- 23 Mar 2026: possible Spring / recovery interaction.

Key concern:

- This sequence appears to show effort versus result and possible absorption.
- The scanner must be tested to see whether it fires Stopping Volume, Spring, Shakeout, Absorption, Demand Coming In, and Effort vs Result correctly in the correct weeks.
- Effort-vs-result should not be added or activated blindly. It must be calibrated across many symbols and false-positive cases.

### First basket review finding

The first small basket review covered LT.NS, RELIANCE.NS, and SRF.NS. It showed that Effort-vs-Result candidates are not isolated to LT.NS. RELIANCE.NS and SRF.NS also surfaced high-priority candidate rows.

Milestone implication:

- A single LT.NS case is not enough to change production detectors.
- Future detector changes must be checked against a fixed basket baseline.
- PR #77 defines the standard 30-symbol audit basket for that purpose.

### Standard basket triage finding

The standard 30-symbol review produced 134 high-priority candidate rows. PR #78 separated them into useful triage buckets:

- 15 qualification lifecycle issues.
- 12 clean candidates.
- 33 overlapping candidate clusters.
- 58 contradictory production-evidence rows.
- 12 manual chart-review rows.
- 4 likely noisy diagnostics.

Milestone implication:

- Broad Effort-vs-Result, absorption, and high-volume reversal activation is still too risky.
- Qualification lifecycle is the cleanest next backend target because it fixes stale or contradictory persistent context instead of adding broad detector weight.

### Qualification lifecycle audit finding

The qualification lifecycle audit reduced 134 triage rows to 19 lifecycle review rows:

- 12 `invalidated_review` rows.
- 3 `conflicted` rows.
- 1 `expired_review` row.
- 3 `needs_follow_through` rows.

Important LT.NS rows:

- 23 Mar 2026: `persistent_bearish` plus `demand_coming_in`.
- 06 Apr 2026: `persistent_bearish` plus `increasing_demand` and `demand_coming_in`.

Milestone implication:

- The next production-safe design should propose explicit qualification transitions before modifying scanner/story behavior.
- Proposed transitions should include `keep_active`, `mark_conflicted`, `invalidate_qualification`, `expire_qualification`, and `wait_for_follow_through`.

## Event families to inspect

Core event families to inspect, strengthen, or add:

- Stopping Volume.
- Selling Climax.
- Shakeout.
- Spring.
- Test.
- No Supply.
- No Demand.
- Demand Coming In.
- Increasing Demand.
- Increasing Supply.
- Supply Coming In.
- Hidden Demand.
- Hidden Supply.
- Supply Absorption.
- Effort Greater Than Result.
- Result Greater Than Effort.
- Buying Climax.
- Upthrust.
- Structural Progression Improving.
- Structural Progression Weakening.

For each event family, inspect true positives, false positives, missed expected events, event timing, point-in-time safety, follow-through, expiry, invalidation, absorption, and whether volume/spread/close/structure gates are too strict or too loose.

## Outcome and lifecycle statuses to design

Candidate statuses:

- Candidate.
- Pending follow-through.
- Active.
- Confirmed follow-through.
- Invalidated.
- Absorbed.
- Failed bearish continuation.
- Failed bullish continuation.
- Expired.
- Needs manual review.

These should be analysis labels only. They must not trigger broker, order, account, funds, holdings, margin, credential, or position-size behavior.

## Implemented Milestone 6 audit surfaces

### PR #70: VSA event audit runner

Implemented behavior:

- `GET /api/vsa-audit/events`.
- Accepts comma, semicolon, or newline separated symbols.
- Supports `start_week`, `end_week`, `horizon_weeks`, and `max_symbols`.
- Loads completed weekly data once per symbol through the existing service/data path.
- Keeps the data path aligned with the existing cache and incremental refresh behavior.
- Performs one bounded scanner pass up to the requested end week for each symbol.
- Returns compact point-in-time rows for target/scoring/qualifying/campaign event codes.
- Separates structural progression events from non-structural VSA events.
- Records per-symbol errors without failing the whole batch.
- Does not persist scanner state, decision context, or decision journal entries.
- Does not change production scanner scoring, ranking, event rules, frontend behavior, or broker/account scope.

### PR #71: audit flags and LT.NS casebook update

Audit flags introduced:

- `no_target_event`.
- `fallback_scoring_evidence`.
- `stale_scoring_evidence`.
- `actionable_audit_row`.
- `structural_event_without_vsa_confirmation`.
- `bullish_vsa_against_bearish_qualification`.
- `bearish_vsa_against_bullish_qualification`.
- `conflicting_target_vsa_pressure`.
- `conflicting_scoring_vsa_pressure`.
- `qualification_without_current_evidence`.

These flags do not change scanner behavior. They only label audit rows that need inspection.

### PR #72: audit-only detector diagnostics

Detector diagnostics introduced:

- `review_potential_stopping_volume`.
- `review_potential_effort_gt_result`.
- `review_potential_absorption`.
- `review_potential_spring_or_shakeout`.
- `review_high_volume_reversal_without_bullish_event`.

These diagnostics are intentionally weaker than production VSA evidence rules. They are review hints only. They do not create evidence, do not activate disabled detectors, do not change production scanner scoring/ranking, and do not change frontend behavior.

### PR #73: Effort and absorption calibration summary

PR #73 added a calibration summary helper that turns audit rows into a compact review queue for Effort-vs-Result, absorption, high-volume reversal, Stopping Volume, Spring/Shakeout, qualification conflicts, and stale evidence.

This remains audit/calibration-only and does not change production scanner behavior.

### PR #74: VSA audit calibration CLI

PR #74 added a CLI for saved audit JSON files.

Example:

```powershell
python scripts/vsa_audit_calibration_summary.py LT_New.txt --output LT_calibration_summary.json
```

This lets local audit output be converted into calibration summaries without adding API or frontend behavior.

### PR #75: VSA audit candidate events

PR #75 added structured audit-only candidate event objects and a CLI.

Candidate families include:

- `audit_effort_gt_result_candidate`.
- `audit_absorption_candidate`.
- `audit_stopping_volume_candidate`.
- `audit_spring_shakeout_candidate`.
- `audit_high_volume_reversal_candidate`.
- `audit_qualification_conflict_candidate`.
- `audit_stale_evidence_candidate`.

Example:

```powershell
python scripts/vsa_audit_candidate_events.py LT_New.txt --min-priority high --output LT_candidate_events_high.json
```

The LT.NS run produced high-priority Effort-vs-Result, absorption, high-volume reversal, and qualification-lifecycle candidates. These are not production events; they are structured review candidates.

### PR #76: candidate-event basket batch review/export

PR #76 added a batch review/export layer for the candidate-event output.

Purpose:

- Run the audit/candidate flow over a basket.
- Produce compact JSON and CSV review files.
- Rank symbols by high-priority candidate counts.
- Group candidate families so Effort-vs-Result, absorption, high-volume reversal, and lifecycle conflicts can be reviewed quickly.
- Avoid changing production detector/scanner behavior before false positives are checked across multiple stocks.

Example:

```powershell
python scripts/vsa_audit_batch_review.py basket_audit.json --min-priority high --json-output basket_candidate_review.json --csv-output basket_candidate_review.csv
```

Scope remains audit/export-only. No market-data load, scanner replay, scoring/ranking change, detector activation, API behavior change, frontend behavior change, persistence change, or broker/account/order behavior is added.

### PR #77: standard 30-symbol VSA audit basket

PR #77 defines a repeatable 30-symbol basket and command helper.

Basket name:

```text
milestone6_standard_india_large_cap_30
```

Default audit window:

```text
start_week=2026-03-02
horizon_weeks=8
max_symbols=30
```

Purpose:

- Make basket-level VSA audits repeatable.
- Avoid changing production detector rules based on only LT.NS.
- Give every future Effort-vs-Result, absorption, high-volume reversal, and lifecycle change the same baseline.

Example:

```powershell
python scripts/vsa_standard_audit_basket.py
```

Scope remains configuration/command-helper only. It does not load market data, replay the scanner, alter detectors, change scoring/ranking, change API/frontend behavior, persist results, or add broker/account/order behavior.

### PR #78: candidate-event triage grading

PR #78 added audit-only triage over candidate-event rows.

Triage buckets:

- `qualification_lifecycle_issue`.
- `overlapping_candidate_cluster`.
- `contradictory_production_evidence`.
- `clean_candidate`.
- `likely_noisy_diagnostic`.
- `manual_chart_review`.

Example:

```powershell
python scripts/vsa_audit_candidate_triage.py standard_basket_review.json --json-output standard_basket_triage.json --csv-output standard_basket_triage.csv
```

The standard basket output showed that broad candidate rows need further separation before production activation.

### PR #79: qualification lifecycle audit export

PR #79 added audit-only lifecycle review for persistent bullish/bearish qualifications.

Lifecycle statuses:

- `invalidated_review`.
- `conflicted`.
- `expired_review`.
- `needs_follow_through`.
- `active` with `--include-active`.

Example:

```powershell
python scripts/vsa_qualification_lifecycle_audit.py standard_basket_triage.json --json-output standard_basket_qualification_lifecycle.json --csv-output standard_basket_qualification_lifecycle.csv
```

The standard basket lifecycle output reduced 134 triage rows into 19 qualification lifecycle rows. This made qualification invalidation/expiry the highest-value next target.

### PR #80: qualification transition proposal

PR #80 proposes audit-only qualification state transitions from PR #79 lifecycle rows.

Proposed actions:

- `keep_active`.
- `mark_conflicted`.
- `invalidate_qualification`.
- `expire_qualification`.
- `wait_for_follow_through`.

Example:

```powershell
python scripts/vsa_qualification_transition_proposal.py standard_basket_qualification_lifecycle.json --json-output standard_basket_qualification_transitions.json --csv-output standard_basket_qualification_transitions.csv
```

Scope remains audit/export-only. No market-data load, scanner replay, detector activation, production scoring/ranking change, API behavior change, frontend behavior change, persistence change, or broker/account/order behavior is added.

## Real-stock casebook

Keep adding cases here as we discover them.

### LT.NS: Feb-Mar 2025 structural weakness followed by rally

Purpose:

- Test structural progression weakening lifecycle.
- Verify formed date versus confirmation date.
- Check if bearish structural event later becomes invalidated or absorbed.

Audit command:

```text
/api/vsa-audit/events?symbols=LT.NS&start_week=2025-02-24&horizon_weeks=20
```

Confirmed audit findings from the first run:

- The audit covered 20 replay weeks from 24 Feb 2025 to 07 Jul 2025 with no per-symbol errors.
- On 24 Feb 2025, no target event fired, but the scanner was actionable and still using older bearish supply scoring evidence with `structural_progression_weakening` as qualifying evidence.
- On 17 Mar 2025, `increasing_demand` and `demand_coming_in` fired while the qualification remained `persistent_bearish`.
- On 24 Mar 2025, `structural_progression_weakening` fired as the target structural event, but no same-week non-structural VSA confirmation fired.
- Demand evidence appeared again later, including 07 Apr, 05 May, and 23 Jun 2025.
- By late May through July, several rows had no target, scoring, or campaign events, but qualification still remained `persistent_bearish`.

Milestone implication:

- Structural weakening detection may be valid point-in-time, but the system needs lifecycle / invalidation / absorption handling.
- Bearish qualification should not continue to dominate after demand appears and fresh bearish evidence disappears.

### LT.NS: Mar 2026 high-volume support / effort-vs-result / spring candidate

Purpose:

- Test Stopping Volume.
- Test Effort vs Result.
- Test absorption / support behavior after very-high and ultra-high volume.
- Test Spring or Shakeout recovery logic.

Audit command:

```text
/api/vsa-audit/events?symbols=LT.NS&start_week=2026-03-02&horizon_weeks=8
```

Confirmed audit findings from the first run:

- The audit covered 8 replay weeks from 02 Mar 2026 to 20 Apr 2026 with no per-symbol errors.
- On 02 Mar 2026, the target event was `increasing_supply`; `stopping_volume` did not fire.
- On 09 Mar 2026, no target event fired and the scanner reused earlier `increasing_supply` scoring evidence.
- On 16 Mar 2026, `structural_progression_weakening` fired, but `effort_gt_result`, absorption, and stopping-volume style demand evidence did not fire.
- On 23 Mar 2026, `demand_coming_in` fired, but `spring` and `shakeout` did not fire.
- On 06 Apr 2026, `increasing_demand` and `demand_coming_in` fired.
- On 13 Apr and 20 Apr 2026, no target event fired but older `increasing_supply` still appeared as scoring evidence with high age.

Confirmed candidate-event findings:

- 02 Mar 2026 produced Effort-vs-Result, absorption, and high-volume reversal candidates while production still had `increasing_supply` and `persistent_bearish` qualification.
- 16 Mar 2026 produced a high-priority Effort-vs-Result candidate while production fired only structural weakening.
- 23 Mar 2026 produced an Effort-vs-Result candidate and a qualification conflict while production saw `demand_coming_in` but remained `persistent_bearish`.
- 06 Apr 2026 produced a qualification lifecycle conflict while production fired `increasing_demand` and `demand_coming_in` but remained bearish.
- 13 Apr 2026 produced absorption and high-volume reversal candidates even though no target event fired.

Confirmed lifecycle findings:

- 23 Mar 2026: `persistent_bearish` with `demand_coming_in` was classified as `invalidated_review`.
- 06 Apr 2026: `persistent_bearish` with `increasing_demand` and `demand_coming_in` was classified as `invalidated_review`.

Milestone implication:

- The scanner currently identifies supply pressure but does not yet properly label the later high-volume effort-vs-result / absorption / spring-like sequence.
- Effort vs Result, Stopping Volume, Spring, Shakeout, Absorption, and qualification lifecycle need targeted diagnostics and calibration across a wider basket before production behavior changes.
- Qualification invalidation/expiry should be designed before broad detector activation.

### First small basket run: LT.NS, RELIANCE.NS, SRF.NS

Uploaded batch review output showed:

- 23 high-priority review rows.
- 11 Effort-vs-Result candidates.
- 5 absorption candidates.
- 5 high-volume reversal candidates.
- 2 qualification-lifecycle conflict candidates.
- LT.NS and RELIANCE.NS tied as the top review symbols with 10 high-priority rows each.
- SRF.NS had 3 high-priority Effort-vs-Result rows.

Milestone implication:

- The Effort-vs-Result issue is not isolated to LT.NS.
- A fixed 30-symbol basket is required before production detector changes.

### Standard basket lifecycle run

Uploaded standard basket lifecycle output showed:

- 19 total lifecycle review rows.
- 12 `invalidated_review` rows.
- 3 `conflicted` rows.
- 1 `expired_review` row.
- 3 `needs_follow_through` rows.
- 15 Grade-A rows and 4 Grade-B rows.

Top symbols included HDFCBANK.NS, MARUTI.NS, ICICIBANK.NS, LT.NS, POWERGRID.NS, TATASTEEL.NS, and TCS.NS.

Milestone implication:

- Qualification state transitions should be designed explicitly before production story/scanner behavior changes.
- The transition proposal helper in PR #80 is the final audit-only step before designing production labels.

## Proposed Milestone 6 PR sequence

Completed:

- PR #69: Milestone 6 living planning document.
- PR #70: Automated VSA event audit runner.
- PR #71: Audit flags and LT.NS casebook findings.
- PR #72: Audit-only detector diagnostics.
- PR #73: Effort and absorption calibration summary.
- PR #74: VSA audit calibration CLI.
- PR #75: VSA audit candidate events.
- PR #76: Candidate-event basket batch review/export.
- PR #77: Standard 30-symbol VSA audit basket.
- PR #78: Candidate-event triage grading.
- PR #79: Qualification lifecycle audit export.

Current:

- PR #80: Qualification transition proposal.

Next likely steps:

- Run transition proposals on the standard basket lifecycle output.
- Review `invalidate_qualification`, `mark_conflicted`, `expire_qualification`, and `wait_for_follow_through` counts.
- Design production-safe qualification state labels for decision context/story output.
- Only after qualification lifecycle is safe, revisit Effort-vs-Result, absorption, high-volume reversal, Stopping Volume, Spring, and Shakeout detector gates.

## Current TODO list

- [x] Create Milestone 6 living planning document.
- [x] Build first automated multi-symbol event replay/audit runner surface.
- [x] Reuse existing optimized/incremental data loading; avoid slow manual 30-stock chart review.
- [x] Run LT.NS Feb-Mar 2025 audit and record findings.
- [x] Run LT.NS Mar 2026 audit and record findings.
- [x] Add audit flags so exception rows can be filtered quickly.
- [x] Add first detector diagnostics explaining why high-volume reversal rows deserve review.
- [x] Add calibration summary helper.
- [x] Add calibration CLI for saved audit output.
- [x] Add structured audit-only candidate events.
- [x] Add candidate-event batch review/export surface.
- [x] Define standard 30-symbol audit basket.
- [x] Run candidate-event batch review across the standard basket.
- [x] Add candidate-event triage grading.
- [x] Add qualification lifecycle audit export.
- [ ] Add qualification transition proposal output.
- [ ] Inspect whether Effort vs Result is currently absent from production evidence collection.
- [ ] Audit Stopping Volume strictness across real examples.
- [ ] Audit Spring support-touch/test/confirmation strictness across real examples.
- [ ] Audit Shakeout and Selling Climax separation.
- [ ] Add full detector gate diagnostics explaining why each production event fired or failed.
- [ ] Add formed-date vs confirmation-date fields for structural/story events.
- [ ] Design production-safe qualification state labels.
- [ ] Design outcome labels without changing scanner scoring prematurely.
- [ ] Add compact casebook results as findings are confirmed.
- [ ] Keep this document updated with every Milestone 6 PR.

## Completed / decision log

- PR #66 added backend weekly Bar-by-Bar professional readings.
- PR #67 added analysis-only trade-planning layer.
- PR #68 wired Bar-by-Bar and Trade Plan into the frontend.
- PR #69 created and merged this Milestone 6 living document.
- PR #70 added and merged the first automated audit runner surface.
- PR #71 added and merged audit flags and first LT.NS audit findings.
- PR #72 added and merged audit-only detector diagnostics for high-volume reversal review.
- PR #73 added and merged the Effort/absorption calibration summary helper.
- PR #74 added and merged the saved-output calibration CLI.
- PR #75 added and merged structured audit-only candidate events.
- PR #76 added and merged candidate-event basket batch review/export.
- PR #77 added and merged the standard 30-symbol VSA audit basket.
- PR #78 added and merged candidate-event triage grading.
- PR #79 added and merged qualification lifecycle audit export.
- After reviewing LT.NS examples, priority shifted to backend VSA event reliability.
- Decision: automated audit first, scanner behavior changes later.
- Decision: no long manual 30-stock chart review; use optimized pipeline and inspect only flagged exceptions.
- Decision: keep audit/calibration PRs behavior-safe; production detector changes come later after basket evidence is available.
- Decision: qualification lifecycle should be fixed before broad Effort-vs-Result, absorption, or high-volume reversal activation.

## Update rule for future work

Whenever a new VSA issue or chart observation appears, update this document with:

1. Symbol and week/date range.
2. What the chart appears to show.
3. What the scanner currently fired or missed.
4. Whether the issue is detection, timing, strength, lifecycle, UI labeling, or story weighting.
5. Follow-up PR or TODO.
6. Final status after implementation/testing.

This document is part of the Milestone 6 working memory and should remain current until the VSA event foundation is mature.
