# Visual Replay Findings and Backend Quality Pivot

## Purpose

This document records the current decision point after the dev-only visual replay work and the first manual LT review attempt.

The main conclusion is that replay tooling is useful as a reviewer aid, but the project priority now moves back to backend correctness: VSA events and structural events must fire on the correct bar, with correct source data, correct timing, and explainable evidence.

## Current status of visual replay work

The recent visual replay work produced a guarded, dev-only, offline review workflow. Its purpose is manual inspection and evidence capture, not production activation.

The completed replay/audit package includes:

- a dev-only Effort/Result visual replay route reference;
- offline replay fixtures for selected LT cases;
- manual visual evidence draft/export support;
- visual replay evidence compilation;
- casebook/reviewer-summary style reports;
- shadow/manual review gates and handoff adapters;
- a final LT visual replay manual review template.

This work is intentionally bounded:

- no live market data fetch is authorized by the replay workflow;
- no scanner state mutation is authorized;
- no production signal persistence is authorized;
- no production API or frontend activation is authorized;
- no detector activation, scoring, ranking, actionability, alerting, or order behavior is authorized;
- any production-facing change still requires a separate production PR after validation.

## Manual review finding

During the manual visual review setup, an important data-alignment issue was observed.

For the LT weekly candle beginning `2025-02-24`, the external TradingView screenshot showed:

- open: `3289.7`
- high: `3325.5`
- low: `3141.0`
- close: `3163.9`

However, the ProVSA replay/checklist view showed a different close value for the same displayed date/context, including a close value of `3378.4` in the review UI.

This creates a blocker for accepting that case as reviewed/pass. It may indicate one or more of the following:

- fixture/source data mismatch;
- adjusted versus unadjusted price mismatch;
- weekly candle boundary mismatch;
- event-date mapping mismatch;
- replay fixture generation mismatch;
- UI checklist field using the wrong bar or wrong label;
- source-provider differences that are not clearly documented.

The immediate lesson is that visual replay can reveal data and timing issues, but replay evidence cannot be trusted until backend source-bar alignment is auditable.

## Historical replay engine is on hold

A full TradingView-style historical replay engine is explicitly out of scope for now.

The project does not prioritize building a general replay engine that can pick any historical start date, reconstruct scanner state as-of that date, and step forward through time for all symbols.

That capability may be useful later, but it is the lowest priority at this stage and should not be worked on unless explicitly requested.

## Backend quality pivot

The new high-priority direction is backend VSA and structural event quality.

This does not mean replacing existing detectors. The existing detectors remain the source of event generation.

The next layer should make detector output observable, auditable, and safer to trust.

For every emitted VSA or structural event, the backend should be able to explain:

- which symbol was evaluated;
- which timeframe was evaluated;
- which exact bar fired the event;
- the event date and source bar timestamp;
- the open, high, low, close, volume, and derived spread/result values used by the detector;
- which previous bars were compared;
- which detector rules passed;
- which detector rules failed or were not applicable;
- whether confirmation/follow-through was required;
- whether any future bar was used;
- whether the event can be reproduced from the supplied source bars.

The desired outcome is not simply more events. The desired outcome is correctly timed, reproducible, explainable events.

## Generic scope

The backend audit work must be generic, not LT-specific.

LT may remain a useful sample case because it exposed the data mismatch, but the quality layer should work for any symbol, event type, and supported timeframe.

Generic coverage should include, at minimum:

- VSA effort/result events;
- supply pressure and demand absorption events;
- no-demand and no-supply style events where supported;
- selling climax / stopping volume style events where supported;
- structural weakness and structural strength events;
- follow-through and confirmation events;
- event-date and source-bar alignment checks;
- no-lookahead checks;
- evidence completeness checks.

## What the next coding work should achieve

The next coding work should add a generic backend event timing/evidence audit, not another replay feature.

A useful first implementation should produce a report that can answer these questions for each emitted event:

1. Did the event fire on the expected bar?
2. Does the event bar's OHLCV match the backend source bars?
3. Is the displayed event date the same bar the detector used?
4. Were derived values, such as spread, volume ratio, effort, result, and close location, computed from the same bar?
5. Did the detector use only current and prior bars at the time of the event?
6. Is there enough evidence to understand why the event fired?
7. Are follow-through or confirmation fields clearly separated from the event trigger itself?
8. Are any mismatches reported as blockers rather than silently accepted?

## What should not happen next

The next work should not:

- build a historical replay engine;
- expand the replay UI;
- add more replay gates without solving backend evidence quality;
- create LT-only backend logic;
- mark visual review cases as pass when source-bar alignment is unresolved;
- make production scanner/scoring/ranking/actionability changes without a separate validated PR.

## Recommended next PR

The recommended next coding PR is:

`Add generic backend event timing audit`

That PR should focus on the backend/audit layer and should be able to flag data-alignment problems like the LT 2025 close mismatch without relying on manual UI inspection.

The audit should be generic enough to run against multiple symbols and event families while preserving detector behavior unchanged until evidence supports a controlled improvement.
