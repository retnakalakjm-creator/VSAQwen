# Step 6 Replay Reuse Closure

## Purpose

This document closes the Step 6 repeated-prefix replay/recomputation work after the production replay-reuse optimizations and measurement guards were merged.

The Step 6 goal was to reduce duplicate scanner replay work without changing scanner decisions, VSA evidence semantics, checkpoint behavior, production output shape, frontend/API behavior, trade plans, alerts, or orders.

## Completed inventory

| Area | Final boundary | Closure status |
| --- | --- | --- |
| Transition batch API | `ScannerTransitionEngine.scan_to_indices(...)` reuses one `ScanState` across strictly increasing target indices. | Complete. |
| Historical full scan | `HistoricalScannerRunner.scan(...)` consumes the transition batch API for the complete historical target range. | Complete. |
| Historical selected-target adapter | `HistoricalScannerRunner.scan_to_indices(...)` exposes sparse target reuse to historical/audit callers. | Complete. |
| VSA event audit | `build_vsa_event_audit(...)` uses selected-target scanning when available. | Complete. |
| Candidate audit | `run_symbol_candidate_audit(...)` and `run_historical_candidate_audit(...)` default to `HistoricalScannerRunner`. | Complete. |
| Production parity guard | `tests/test_production_suffix_reuse_parity_guard.py` freezes production candidate signatures before optimization. | Complete. |
| Production bootstrap/fallback snapshot reuse | Production uses the historical full-replay boundary and builds the durable snapshot from the already-replayed transition state. | Complete. |
| Production resume snapshot reuse | Production uses the resume adapter state-returning boundary and builds the refreshed snapshot from the already-resumed transition state. | Complete. |
| Production replay-reuse measurement guard | `tests/test_production_replay_reuse_measurement_guard.py` locks replay counts for bootstrap/fallback and behind-checkpoint resume. | Complete. |

## Final production replay shapes

Bootstrap or fallback with no usable checkpoint:

```text
HistoricalScannerRunner.scan_to_index_with_state(...)
-> latest candidate + transition state
-> ScannerTransitionSnapshotAdapter.snapshot_from_transition_state(...)
-> persisted ScannerState
```

Validated checkpoint behind the latest bar:

```text
ScannerTransitionResumeAdapter.resume_latest_with_state(...)
-> latest candidate + resumed transition state
-> ScannerTransitionSnapshotAdapter.snapshot_from_transition_state(...)
-> refreshed persisted ScannerState
```

Validated checkpoint already at the latest bar:

```text
ScannerTransitionResumeAdapter.resume_latest(...)
-> latest candidate
-> skip snapshot refresh
```

## Guardrails that must stay active

Keep these groups active during cleanup and future feature work. On Windows PowerShell, expand wildcard file groups through `Get-ChildItem` before passing them to pytest:

```powershell
python -m pytest tests/test_production_replay_reuse_measurement_guard.py -v
python -m pytest tests/test_production_resume_snapshot_reuse.py -v
python -m pytest tests/test_production_bootstrap_snapshot_reuse.py -v
python -m pytest tests/test_production_suffix_reuse_parity_guard.py -v
python -m pytest -v (Get-ChildItem tests -Filter "test_scanner_transition*.py").FullName
python -m pytest -v (Get-ChildItem tests -Filter "test_production*.py").FullName
```

The full safety gate remains:

```powershell
python -m pytest
cd frontend
npm run build
```

## Cleanup handoff

Step 6 core/audit/production replay reuse is closed. Cleanup before new trading logic is tracked in `docs/CLEANUP_MILESTONE_INVENTORY.md`.

The cleanup milestone should proceed in small slices:

1. classify protected versus cleanup-candidate tests and docs;
2. consolidate scattered Step 6 docs;
3. review compatibility fallbacks added for test doubles;
4. clean up merged branches when stable;
5. only then start the weekly VSA setup to daily-entry trigger bridge in shadow/read-only mode.

`tools/historical_validation.py` remains a low-priority manual tooling candidate. It is not part of the production Step 6 closure.

## Non-goals

This closure does not change detector rules, VSA evidence semantics, scoring, ranking, qualification, actionability, checkpoint policy, API response shape, frontend runtime, replay/manual-review behavior, HVR policy, trade plans, alerts, or orders.
