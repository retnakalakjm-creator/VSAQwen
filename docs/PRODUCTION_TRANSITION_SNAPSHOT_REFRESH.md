# Production Transition Snapshot Refresh

## Purpose

PR #214 routes production scanner snapshot refresh through `ScannerTransitionSnapshotAdapter` after PR #213 established durable `ScannerState` parity with `IncrementalScannerEngine.snapshot(...)`.

## Production path after this change

- full replay/bootstrap/fallback candidates use `HistoricalScannerRunner`;
- valid checkpoint resume candidates use `ScannerTransitionResumeAdapter`;
- snapshot creation/refresh uses `ScannerTransitionSnapshotAdapter`;
- a fingerprint-valid checkpoint already at the latest metrics bar still skips redundant snapshot refresh.

## Refresh contract

Production refreshes the transition-built snapshot when:

- no checkpoint exists;
- a checkpoint fails engine/config/data fingerprint validation;
- a valid checkpoint is behind the latest completed bar;
- transition resume fails and production falls back to full replay.

Production does not rebuild the snapshot when a loaded checkpoint is fingerprint-valid, already represents the latest completed metrics bar, and transition resume succeeds.

The persisted state keeps the existing schema, symbol/timeframe identity, swing state, structural events, and engine/config/data fingerprints established by the snapshot parity guardrail.

## Boundaries

This migration changes only the production snapshot-refresh implementation boundary. It does not change:

- detector rules or VSA evidence semantics;
- scoring, ranking, qualification, or actionability;
- trade plans, alerts, or orders;
- API or frontend behavior;
- replay/manual-review behavior;
- HVR, stopping-volume, or climactic-action logic.

## Regression coverage

`tests/test_production_resume_transition_wiring.py` verifies refresh behavior for missing, stale, behind, and resume-failed checkpoints and verifies that an already-current valid checkpoint still skips redundant refresh.

`tests/test_scanner_transition_snapshot_parity.py` continues to prove the transition snapshot contract matches the legacy incremental snapshot contract while asserting that production is now wired to the transition snapshot adapter.
