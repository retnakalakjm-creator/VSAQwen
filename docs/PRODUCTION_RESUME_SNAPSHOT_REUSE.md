# Production Resume Snapshot Reuse

## Purpose

This Step 6 slice removes the remaining duplicated transition replay from the
valid-checkpoint resume path.

Before this change, a valid checkpoint behind the latest completed bar performed:

1. `ScannerTransitionResumeAdapter.resume_latest(...)` to produce the latest
   candidate by resuming from the checkpoint;
2. `ScannerTransitionSnapshotAdapter.snapshot(...)` to replay to the same latest
   bar again and refresh the durable scanner snapshot.

After this change, production can use
`ScannerTransitionResumeAdapter.resume_latest_with_state(...)` to get both the
latest candidate and the transition state reached at the latest bar. It then
builds the refreshed snapshot through
`ScannerTransitionSnapshotAdapter.snapshot_from_transition_state(...)`.

## Scope

This applies only to validated checkpoints that are behind the latest completed
bar and need a snapshot refresh after successful resume.

The existing behavior is preserved for:

- first-run bootstrap and full-replay fallback, which continue to use the
  bootstrap/fallback reuse path;
- latest-valid checkpoints, which still skip snapshot refresh;
- older injected resume/snapshot test doubles that only expose
  `resume_latest(...)` and `snapshot(...)`.

## Safety contract

The optimization must preserve:

- full production candidate signature parity;
- checkpoint fingerprint validation;
- fallback diagnostic behavior;
- persisted snapshot identity and fingerprints;
- production adapter boundaries, including no direct `scanner_transition` import
  from `production_scanner.py`.

## Non-goals

This slice does not change detector logic, VSA semantics, scoring, ranking,
qualification, actionability, API response shape, frontend runtime,
replay/manual-review behavior, HVR policy, trade plans, alerts, or orders.
