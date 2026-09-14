# Effort/Result Production Integration Plan

## Purpose

This milestone document restores the intended roadmap after the visual replay detour.

The project has already invested significant backend/audit work into Effort/Result semantics. The next production-facing milestone should use that work by integrating Effort/Result into the production scanner path as read-only evidence first.

This document is intentionally a planning checkpoint. It does not change detectors, scanner logic, scoring, ranking, actionability, APIs, frontend behavior, persistence, alerts, or orders.

## Roadmap correction

The correct near-term roadmap is:

1. Document Effort/Result production integration scope and boundaries.
2. Integrate Effort/Result into the production scanner output as read-only evidence.
3. Validate production-path emissions and evidence shape through tests/audits.
4. Continue with pending detector families, especially Absorption and High Volume Reversal.
5. Decide scoring/ranking/actionability impact only after production evidence quality is trusted.

The visual replay/manual review work remains useful as a future reviewer aid, but it is not the main roadmap track now.

## Current architecture reference

The current architecture already separates production-integrated events, provisional events, and audit-only candidates.

Important current-state facts from the architecture document:

- The active executable workflow remains the Python command-line scanner.
- Evidence aggregation is event-oriented and grouped by `(bar_index, direction)`.
- Professional scoring combines trend, supply, demand, effort, strength, weakness, and confidence.
- `evidence/effort.py` contains effort-result analysis, but engine invocation is currently disabled.
- `ABSORPTION` has completed analysis-only audit work but has no production collector, engine collection path, or registry entry.

This plan follows that pattern: move Effort/Result forward in a controlled production path without changing scoring/ranking first.

## Milestone state

| Area | Current state | Target next state |
| --- | --- | --- |
| Effort/Result detector semantics | Audited/tested through backend and replay-adjacent audit work | Production scanner evidence, read-only |
| Effort/Result replay work | Dev-only/offline/manual-review helper | Deferred; not part of production integration |
| Historical replay engine | Explicitly on hold | No work unless specifically requested |
| Absorption | Audit-complete/provisional, not production-collected | Next detector-family priority after Effort/Result evidence integration |
| High Volume Reversal | Pending detector-family priority | Address after Effort/Result and Absorption roadmap steps |
| Scoring/ranking/actionability | Must remain unchanged by first Effort/Result integration | Future decision only after evidence quality passes |

## Production integration definition

For this milestone, "production integration" means:

- Effort/Result events are emitted or attached through the production scanner/evidence path.
- The scanner/API output can expose Effort/Result observations as evidence.
- Each observation identifies the evaluated symbol, timeframe, bar index/date, event type, and supporting metrics.
- Existing scoring, ranking, actionability, qualification, alerts, and order behavior remain unchanged.

It does not mean Effort/Result immediately becomes a scoring driver.

## Read-only evidence-first boundary

The first implementation PR must be evidence-only.

Allowed:

- connect existing Effort/Result analysis to the production evidence/scanner output path;
- expose Effort/Result event details as diagnostic/read-only evidence;
- add production-path tests for emission shape and safety boundaries;
- preserve point-in-time semantics and no-lookahead behavior;
- add guardrails that prevent replay fixtures/routes from being used by production scanner logic.

Not allowed:

- score mutation;
- ranking mutation;
- actionability mutation;
- alerting or order changes;
- automatic production promotion from replay/manual-review artifacts;
- frontend replay expansion;
- historical replay engine work;
- LT-only production logic.

## Required evidence shape

Each production Effort/Result observation should provide enough information to explain the event without relying on replay UI state.

At minimum, the evidence should include:

- symbol;
- timeframe;
- event type;
- event date or source bar timestamp;
- bar index where available;
- direction or bias where applicable;
- current bar open/high/low/close/volume where available;
- spread/result metric used by the detector;
- volume/effort metric used by the detector;
- prior-bar comparison summary where applicable;
- whether follow-through/confirmation is required;
- whether the observation is trigger evidence or post-event confirmation evidence;
- explicit no-lookahead guarantee for the trigger calculation.

## Event family scope for first integration

The first production integration should stay focused on Effort/Result and its immediate labels.

Candidate labels include, where already supported by existing backend work:

- `RESULT_GREATER_THAN_EFFORT`;
- `EFFORT_WITHOUT_RESULT`;
- `SUPPLY_PRESSURE`;
- `DEMAND_ABSORPTION`;
- related effort/result divergence labels already produced by the backend.

The implementation should not invent new detector semantics in the integration PR. It should connect existing behavior safely and observably.

## Relationship to structural events

Structural events remain important, but the Effort/Result production step should not rewrite structural logic.

The integration may reference structural context if it already exists in the scanner/evidence path, but it should not introduce new structural scoring, structural reclassification, or structural event promotion in the first implementation.

A later generic backend timing/evidence audit can validate VSA and structural events together.

## Absorption and High Volume Reversal roadmap position

Absorption and High Volume Reversal remain backend roadmap priorities.

They should not be lost behind replay work.

Recommended order after this document:

1. Effort/Result production evidence integration.
2. Absorption production-path planning/collector work.
3. High Volume Reversal production-path planning/collector work.
4. Generic event timing/evidence audit across all active/provisional detector families.
5. Separate scoring/ranking/actionability decisions only after evidence quality is proven.

## Validation requirements for implementation PR

The next implementation PR should include tests proving:

- Effort/Result evidence appears in production scanner/evidence output when detector conditions exist;
- existing detector behavior is reused rather than duplicated;
- no replay fixture or replay route module is imported into production scanner logic;
- score/rank/actionability outputs are unchanged except for the additional read-only evidence field;
- no alert/order behavior is introduced;
- event timestamps/bar identifiers are included in emitted evidence;
- no future bar is required to emit the trigger observation.

## Data-alignment caution

The LT manual visual review exposed a mismatch between an external TradingView weekly close and a ProVSA replay/checklist value for a displayed 2025-02-24 context.

That finding does not block read-only Effort/Result production evidence integration by itself, because replay fixtures are not the production scanner source of truth.

However, it does reinforce the need for production evidence to carry the exact source bar values used by the backend. If a user sees an Effort/Result event in scanner output, the backend should make clear which bar and values caused that event.

## What PR #191 should do

The next PR after this document should be:

`Integrate Effort/Result as production read-only scanner evidence`

Expected scope:

- production backend/evidence path only;
- no replay UI work;
- no historical replay engine work;
- no score/rank/actionability change;
- no Absorption or High Volume Reversal implementation yet;
- tests proving read-only safety and production-path evidence emission.

## What should not happen next

The next work should not:

- continue expanding visual replay infrastructure;
- start historical replay engine work;
- skip Effort/Result production evidence integration;
- jump directly into scoring/ranking/actionability changes;
- start Absorption or High Volume Reversal before Effort/Result production evidence is connected;
- add LT-only production behavior;
- treat replay/manual-review fixtures as production source data.

## Decision

Effort/Result should now move from backend/audit readiness toward production scanner visibility as read-only evidence.

Replay remains deferred. Historical replay remains on hold. Absorption and High Volume Reversal remain the next backend detector-family priorities after Effort/Result production evidence integration.