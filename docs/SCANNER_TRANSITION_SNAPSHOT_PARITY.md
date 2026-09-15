# Scanner Transition Snapshot Parity

## Purpose

This document locks the Phase 4 snapshot guardrail before production snapshot refresh is migrated away from `IncrementalScannerEngine.snapshot(...)`.

PR #213 adds `ScannerTransitionSnapshotAdapter` as a non-production transition snapshot surface. Its job is to prove that the transition runner can build the same durable `ScannerState` contract that production currently persists.

## Current production state

After the earlier transition-runner slices:

- production full replay/bootstrap/fallback candidates use `HistoricalScannerRunner`;
- production valid checkpoint resume candidates use `ScannerTransitionResumeAdapter`;
- redundant snapshot refresh is skipped when a valid checkpoint is already at the latest bar;
- actual snapshot creation for missing, stale, behind, or refreshed checkpoints still uses `IncrementalScannerEngine.snapshot(...)`.

## What this guardrail verifies

The transition snapshot adapter is tested against `IncrementalScannerEngine.snapshot(...)` for multiple bounded replay checkpoints. The parity contract covers:

- schema version;
- symbol and timeframe identity;
- latest closed bar identity;
- active swing search state;
- active candidate swing state;
- confirmed swing state;
- structural progression event state;
- engine/config/data fingerprints.

The adapter also validates that generated fingerprints match the exact point-in-time metrics prefix ending at the snapshot bar.

## Non-goals

This PR does not wire production snapshot refresh to the transition snapshot adapter.

It also does not change detector logic, scoring, ranking, qualification, actionability, trade plans, alerts, orders, frontend behavior, replay behavior, or manual-review workflow.

## Next step after this PR

After CI proves snapshot parity, a later PR can route production snapshot refresh through `ScannerTransitionSnapshotAdapter`. That wiring should remain narrow and keep existing fallback diagnostics and checkpoint validation behavior intact.
