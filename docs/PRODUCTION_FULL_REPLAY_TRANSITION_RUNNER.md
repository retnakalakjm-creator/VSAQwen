# Production Full Replay Transition Runner

## Purpose

This document records the first controlled production-wiring slice in Phase 4 of the scanner architecture roadmap.

The goal is to route only the production full-replay candidate path through `HistoricalScannerRunner`, while keeping the valid persisted-checkpoint resume path on `IncrementalScannerEngine`.

## What changed

`production_scanner.py` now uses `HistoricalScannerRunner().scan_to_index(...)` when production needs a full point-in-time replay candidate:

- first-run bootstrap when no checkpoint exists
- stale engine/config/data checkpoint fallback when fallback is allowed
- corrupt checkpoint fallback when fallback is allowed
- resume/runtime divergence fallback when fallback is allowed

The durable checkpoint is still refreshed through `IncrementalScannerEngine().snapshot(...)` after the candidate is produced.

## What did not change

This slice does not change:

- valid checkpoint resume behavior
- scanner-state fingerprint validation
- fallback diagnostic codes or messages
- detector logic
- scoring, ranking, qualification, or actionability
- trade-plan, alert, or order behavior
- frontend behavior
- replay/manual-review behavior
- symbol-specific behavior

## Why this is the first production slice

The full-replay path is the safest production path to move first because it already matches the transition runner through prior parity coverage. It also leaves the harder stateful resume path unchanged.

The production scanner still has two execution modes:

```text
valid checkpoint
    -> IncrementalScannerEngine.resume_latest(...)

missing/stale/corrupt/divergent checkpoint
    -> HistoricalScannerRunner.scan_to_index(...)
```

## Guardrails

Regression coverage verifies that:

- first-run bootstrap uses `HistoricalScannerRunner`
- stale-checkpoint fallback uses `HistoricalScannerRunner`
- valid checkpoint resume does not use the full-replay transition runner
- transition-runner production full replay remains semantically equal to the legacy scanner output
- shadow parity helpers continue to compare current production output against an independently computed transition result

## Next safe step

After this slice is stable, the next production-wiring step can move a narrower piece of resume behavior toward the transition engine, but only with parity tests proving the result remains identical.

Do not remove repeated prefix recomputation until production wiring and equivalence remain stable.
