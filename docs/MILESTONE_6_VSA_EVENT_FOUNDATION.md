# Milestone 6: Backend VSA Event Foundation

This document is the living planning and audit record for Milestone 6.

Milestone 6 shifts priority from frontend polish to the backend VSA event foundation. The goal is to make VSA detection, event timing, event outcome, invalidation, and chart interpretation concrete, testable, point-in-time safe, and fast enough to run across a basket of real symbols without long manual review sessions.

## Operating principle

We should not manually spend long hours inspecting 30 stocks one by one. We already have an optimized pipeline with incremental refresh. Milestone 6 should reuse that pipeline to run automated VSA event audits quickly, then reserve manual chart review only for exceptions, misses, contradictions, and high-value case studies.

Every Milestone 6 PR should update this document when it adds a new finding, new test case, new event weakness, or new TODO.

## Current observations from recent review

### 1. Backend VSA events are now the top priority

The frontend Bar-by-Bar and Trade Plan work is useful, but it should not become the main focus now. The scanner needs a stronger backend foundation first.

Priority is now:

1. Backend VSA event replay and audit foundation.
2. Strengthen and calibrate existing VSA events.
3. Add missing or underused VSA events.
4. Add event lifecycle, follow-through, invalidation, and absorption logic.
5. Only then return to scanner ranking and frontend refinement.

### 2. We need point-in-time replay, not hindsight-only review

When we inspect a completed chart, it is easy to explain the move after seeing the full future. That is dangerous for a scanner.

Milestone 6 must answer questions like:

- If the current week were 24 Feb 2025, what would the scanner know?
- What events would fire in each following completed week?
- Did the later bars validate, invalidate, absorb, or contradict the original event?
- Did an old bearish or bullish event remain active after the market disproved it?

### 3. LT.NS Feb-Mar 2025 case: structural weakness was not enough

Observed chart case:

- LT.NS formed a lower-low swing around 24 Feb 2025.
- Structural Progression Weakening was confirmed around 24 Mar 2025.
- Price later rallied strongly.

Interpretation:

- The system may have correctly detected structural weakness at that point.
- But lower low is not automatically bearish in VSA.
- A lower low can become a spring, shakeout, selling-climax recovery, or absorbed supply event if downside follow-through fails and demand returns.
- The missing layer is event lifecycle and outcome status.

Required future behavior:

- Structural weakness should start as pending or active only until follow-through is evaluated.
- If price does not continue lower and later reclaims structure, the event should be marked as invalidated, absorbed, or failed bearish continuation.
- The UI/story should distinguish swing formed date from confirmation/story date.

### 4. Swing formed date vs confirmation date must be clear

Observed UI confusion:

- Clicking a story event dated 24 Mar 2025 may navigate to a structural swing whose actual pivot formed on 24 Feb 2025.
- This is not necessarily a data error.
- Structural swings often form first and are confirmed later.

Required future display:

- Swing formed: date of the pivot bar.
- Confirmed in story: date when the swing/event became known.
- On chart: optionally mark the pivot bar with the swing marker and the confirmation/story bar with a separate vertical shade.

### 5. LT.NS Mar 2026 case: effort versus result must be audited

Observed chart case:

- 02 Mar 2026: possible Stopping Volume candidate.
- 09 Mar 2026: very-high-volume follow-up support or absorption candidate.
- 16 Mar 2026: ultra-high-volume bar where spread/result should be inspected carefully.
- 23 Mar 2026: possible Spring / recovery interaction.

Key concern:

- This sequence appears to show effort versus result and possible absorption.
- The scanner must be tested to see whether it fires Stopping Volume, Spring, Shakeout, Absorption, Demand Coming In, and Effort vs Result correctly in the correct weeks.
- Effort-vs-result should not be added or activated blindly. It must be calibrated across many symbols and false-positive cases.

### 6. Current known implementation gap: Effort vs Result

Known backend status to verify and track:

- Effort vs Result evidence codes exist.
- The effort collector exists.
- Production evidence collection has not been fully using the effort collector in the main evidence flow.

Milestone 6 should inspect this before changing live scanner behavior.

## What Milestone 6 must inspect and test

### Event families

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

### Event quality checks

For each event family, inspect:

- True positives.
- False positives.
- Missed expected events.
- Event timing: signal bar, test bar, recovery bar, confirmation bar.
- Whether event timing is point-in-time safe.
- Whether follow-through is required.
- Whether the event should expire.
- Whether later price action invalidates or absorbs it.
- Whether current story overweights old evidence.
- Whether volume class, spread class, close position, and structure context are too strict or too loose.

### Outcome and lifecycle statuses to design

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

## Automated audit runner requirements

The next implementation should avoid a slow manual backtest process.

Required behavior:

- Use existing optimized/incremental data pipeline where possible.
- Accept a symbol list, as-of/start week, optional end week, and replay horizon.
- Replay only completed weekly bars.
- Run point-in-time event detection week by week.
- Emit compact rows, not huge historical warehouses.
- Flag only important exceptions for manual chart review.

Suggested output columns:

- Symbol.
- Replay week.
- Events fired.
- Event family.
- Direction.
- Strength.
- Quality.
- Role: campaign, qualifying, scoring, structural, outcome.
- Signal bar date.
- Test/recovery/confirmation date where applicable.
- Follow-through status.
- Outcome label.
- Notes / detector diagnostics.

Exception flags:

- Missed expected event.
- High-confidence event failed.
- Event invalidated within N weeks.
- Conflicting bullish and bearish evidence.
- Structural event without follow-through.
- Potential spring/shakeout/stopping-volume candidate.
- Potential effort-vs-result candidate.

## Real-stock casebook

Keep adding cases here as we discover them.

### LT.NS: Feb-Mar 2025 structural weakness followed by rally

Purpose:

- Test structural progression weakening lifecycle.
- Verify formed date versus confirmation date.
- Check if bearish structural event later becomes invalidated or absorbed.

Questions:

- Was structural weakness correctly detected point-in-time?
- Was bearish follow-through actually confirmed?
- When should the event stop contributing bearish weight?
- Did later demand/spring/recovery evidence override it correctly?

### LT.NS: Mar 2026 high-volume support / effort-vs-result / spring candidate

Purpose:

- Test Stopping Volume.
- Test Effort vs Result.
- Test absorption / support behavior after very-high and ultra-high volume.
- Test Spring or Shakeout recovery logic.

Weeks to inspect:

- 02 Mar 2026.
- 09 Mar 2026.
- 16 Mar 2026.
- 23 Mar 2026.

Questions:

- Did Stopping Volume fire?
- Did Effort Greater Than Result fire?
- Did Spring or Shakeout fire only when point-in-time confirmation was available?
- Did the scanner identify absorption rather than only bearish supply?

## Proposed Milestone 6 PR sequence

### PR #69: Milestone 6 planning document

Create this living document and establish the backend VSA foundation roadmap.

### PR #70: Automated VSA event audit runner

Backend-only audit runner that uses existing optimized/incremental pipeline and creates compact event replay output for many symbols.

No production scanner behavior changes yet.

### PR #71: Effort vs Result audit and calibration

Use the audit runner to inspect effort-vs-result candidates across many symbols. Only then decide whether and how to wire effort collection into production.

### PR #72: Stopping Volume, Spring, Shakeout, and Test strengthening

Audit and strengthen the high-value reversal/absorption family.

### PR #73: Event lifecycle and invalidation logic

Add follow-through, failed continuation, absorption, invalidation, and expiry labels to story events.

### PR #74+: Story weighting and scanner ranking refinement

Only after the VSA event foundation is stronger, update story weighting, ranking, and frontend presentation.

## Current TODO list

- [ ] Build automated multi-symbol event replay/audit runner.
- [ ] Reuse existing optimized/incremental pipeline; avoid slow manual 30-stock chart review.
- [ ] Define standard 30+ stock audit basket.
- [ ] Add LT.NS Feb-Mar 2025 as a structural weakening invalidation case.
- [ ] Add LT.NS Mar 2026 as Stopping Volume / Effort vs Result / Spring case.
- [ ] Inspect whether Effort vs Result is currently absent from production evidence collection.
- [ ] Audit Stopping Volume strictness across real examples.
- [ ] Audit Spring support-touch/test/confirmation strictness across real examples.
- [ ] Audit Shakeout and Selling Climax separation.
- [ ] Add detector diagnostics explaining why each event fired or failed.
- [ ] Add formed-date vs confirmation-date fields for structural/story events.
- [ ] Design outcome labels without changing scanner scoring prematurely.
- [ ] Add compact casebook results as findings are confirmed.
- [ ] Keep this document updated with every Milestone 6 PR.

## Completed / decision log

- PR #66 added backend weekly Bar-by-Bar professional readings.
- PR #67 added analysis-only trade-planning layer.
- PR #68 wired Bar-by-Bar and Trade Plan into the frontend.
- After reviewing LT.NS examples, priority shifted to backend VSA event reliability.
- Decision: automated audit first, scanner behavior changes later.
- Decision: no long manual 30-stock chart review; use optimized pipeline and inspect only flagged exceptions.

## Update rule for future work

Whenever a new VSA issue or chart observation appears, update this document with:

1. Symbol and week/date range.
2. What the chart appears to show.
3. What the scanner currently fired or missed.
4. Whether the issue is detection, timing, strength, lifecycle, UI labeling, or story weighting.
5. Follow-up PR or TODO.
6. Final status after implementation/testing.

This document is part of the Milestone 6 working memory and should remain current until the VSA event foundation is mature.
