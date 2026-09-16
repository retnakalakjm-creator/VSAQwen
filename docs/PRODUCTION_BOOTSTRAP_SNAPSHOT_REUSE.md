# Production Bootstrap Snapshot Reuse

## Purpose

This Step 6 slice removes one duplicated transition replay from the production bootstrap/fallback path.

Before this change, first-run bootstrap and full-replay fallback performed two transition-backed passes over the same latest completed metrics window:

1. compute the latest production candidate;
2. rebuild the latest durable scanner snapshot.

After this change, `production_scanner._full_replay_candidate_and_snapshot(...)` still stays behind the `HistoricalScannerRunner` full-replay boundary. When that runner exposes a state-returning replay, production reuses the returned transition state to build the durable snapshot through `ScannerTransitionSnapshotAdapter.snapshot_from_transition_state(...)` instead of replaying the same bars a second time.

## Scope

This optimization applies only when production must use full replay:

- first-run bootstrap with no saved checkpoint;
- corrupt/stale/resume-failed checkpoint fallback when fallback is allowed.

Validated checkpoint resume remains on `ScannerTransitionResumeAdapter`. Snapshot refresh after a successful resume remains on `ScannerTransitionSnapshotAdapter.snapshot(...)`.

## Boundary rule

`production_scanner.py` must not import `scanner_transition` directly. The transition engine remains behind these adapter boundaries:

- `HistoricalScannerRunner` for full replay/bootstrap/fallback candidate evaluation;
- `ScannerTransitionResumeAdapter` for valid checkpoint resume;
- `ScannerTransitionSnapshotAdapter` for snapshot creation and refresh.

## Safety contract

The optimization must preserve:

- full production candidate signature parity against `ScannerEngine.scan_to_index(...)`;
- checkpoint fingerprint behavior;
- fallback diagnostic codes and messages;
- persisted snapshot identity and fingerprints;
- actionable wrapper shape.

## Non-goals

This slice does not change detector logic, VSA semantics, scoring, ranking, qualification, actionability, API response shape, frontend runtime, replay/manual-review behavior, HVR policy, trade plans, alerts, or orders.
