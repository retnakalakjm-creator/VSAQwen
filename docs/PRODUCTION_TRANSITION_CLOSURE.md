# Production Transition Migration Closure

## Purpose

PR #215 closes the production scanner transition migration after PR #214 routed snapshot creation and refresh through `ScannerTransitionSnapshotAdapter`.

This is a guardrail-only closure slice. It records the final production boundaries and adds regression tests that fail if `production_scanner.py` regains a direct legacy incremental-engine dependency.

## Final production transition boundaries

- Full replay/bootstrap/fallback candidate evaluation: `production_scanner._full_replay_candidate(...)` uses `HistoricalScannerRunner`, which delegates to `ScannerTransitionEngine`.
- Validated checkpoint resume: `production_scanner.scan_latest_candidate_production(...)` uses `ScannerTransitionResumeAdapter` for a saved `ScannerState` whose engine/config/data fingerprints match the current runtime and metrics prefix.
- Snapshot creation and refresh: `production_scanner._snapshot_latest(...)` uses `ScannerTransitionSnapshotAdapter` to build and persist the latest durable `ScannerState`.
- Redundant refresh skip: a fingerprint-valid checkpoint already at the latest completed bar still resumes through the transition boundary and skips a snapshot rebuild.

`IncrementalScannerEngine is no longer a production_scanner dependency`. It may remain in parity tests as the legacy oracle for transition equivalence, but not as a production scanner import or direct production execution path.

## Guardrails added in this slice

`tests/test_production_transition_closure_guardrails.py` verifies that:

- `production_scanner.py` does not import `incremental_scanner` or reference `IncrementalScannerEngine`;
- production full replay, resume, and snapshot refresh all use transition-backed boundaries;
- transition adapter docstrings no longer describe the old pre-production guardrail phase;
- this closure document records the production boundaries and non-goals.

The existing behavioral tests remain responsible for proving output parity and checkpoint behavior:

- `tests/test_production_resume_transition_wiring.py` covers missing, stale, behind, current, and resume-failed checkpoint paths.
- `tests/test_scanner_transition_snapshot_parity.py` keeps legacy incremental-vs-transition snapshot parity coverage.

## Non-goals

- No detector logic changes.
- No VSA evidence semantic changes.
- No scoring, ranking, qualification, or actionability changes.
- No trade-plan, alert, or order behavior changes.
- No frontend, API, replay/manual-review, HVR, stopping-volume, or climactic-action changes.

## Next safe work after closure

With production full replay, resume, and snapshot refresh behind transition boundaries, the next safe roadmap area is performance work to reduce repeated prefix recomputation. That work should still be staged behind parity tests and must preserve the same scanner candidates, evidence, checkpoint fingerprints, fallback diagnostics, and production behavior.
