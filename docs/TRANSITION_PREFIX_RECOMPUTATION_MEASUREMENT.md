# Transition Prefix Recomputation and Replay Reuse Closure

## Purpose

This note records the Step 6 repeated-prefix replay/recomputation outcome.

The original measurement target was repeated independent replay work: callers could ask for nearby target bars and rebuild the same earlier point-in-time prefixes multiple times. Step 6 introduced safe suffix-reuse boundaries, migrated historical/audit consumers first, then optimized the production bootstrap/fallback and behind-checkpoint resume snapshot paths behind parity and measurement guards.

The work is now closed for core transition, historical, audit, and production latest-candidate paths.

## Final architecture

`ScannerTransitionEngine.scan_to_indices(metrics, target_indices)` remains the central batch API. It accepts a strictly increasing target sequence, reuses one `ScanState`, evaluates bars sequentially, and records candidates only at requested targets.

`HistoricalScannerRunner` is the named historical boundary. It exposes:

- `scan(...)` for complete historical candidate sequences;
- `scan_to_indices(...)` for sparse selected-target scans;
- `scan_to_index_with_state(...)` for production bootstrap/fallback snapshot reuse while keeping `production_scanner.py` away from direct `scanner_transition` imports.

`ScannerTransitionResumeAdapter` is the named production resume boundary. It exposes `resume_latest_with_state(...)` so a valid checkpoint behind the latest bar can produce both the latest candidate and the resumed transition state.

`ScannerTransitionSnapshotAdapter.snapshot_from_transition_state(...)` is the durable snapshot reuse boundary. It builds the persisted `ScannerState` from an already-replayed transition state instead of forcing another transition replay.

## Closed migration inventory

| Area | Final boundary | Status |
| --- | --- | --- |
| `ScannerTransitionEngine.scan_to_indices(...)` | Reuses one transition `ScanState` for strictly increasing target indices. | Complete. |
| `HistoricalScannerRunner.scan(...)` | Calls `ScannerTransitionEngine.scan_to_indices(...)` for the complete historical target range. | Complete. |
| `HistoricalScannerRunner.scan_to_indices(...)` | Exposes the selected-target batch boundary for historical and audit callers. | Complete. |
| `build_vsa_event_audit(...)` | Resolves the replay window once, bounds metrics at `end_index`, and calls `scan_to_indices(...)` when available. | Complete. |
| `audit.runner.run_symbol_candidate_audit(...)` and `run_historical_candidate_audit(...)` | Default to `HistoricalScannerRunner` through `scanner_factory`. | Complete. |
| `production_scanner.scan_latest_candidate_production(...)` bootstrap/fallback | Uses `HistoricalScannerRunner.scan_to_index_with_state(...)` plus `ScannerTransitionSnapshotAdapter.snapshot_from_transition_state(...)`. | Complete. |
| `production_scanner.scan_latest_candidate_production(...)` valid behind-checkpoint resume | Uses `ScannerTransitionResumeAdapter.resume_latest_with_state(...)` plus `ScannerTransitionSnapshotAdapter.snapshot_from_transition_state(...)`. | Complete. |
| Production replay-reuse measurement guard | `tests/test_production_replay_reuse_measurement_guard.py` locks replay counts for bootstrap/fallback and behind-checkpoint resume. | Complete. |
| Production candidate parity guard | `tests/test_production_suffix_reuse_parity_guard.py` freezes candidate signatures across production replay/reuse changes. | Complete. |

## Final production replay shapes

Bootstrap or corrupt/stale checkpoint fallback:

```text
one full transition replay
-> latest candidate
-> snapshot from the same transition state
```

Valid checkpoint behind the latest bar:

```text
one stateful transition resume
-> latest candidate
-> snapshot from the same resumed transition state
```

Valid checkpoint already at the latest bar:

```text
one latest-candidate evaluation
-> no snapshot refresh
```

## Guardrails to keep

The following tests are now core safety coverage and should not be archived during the cleanup milestone:

```powershell
pytest tests/test_production_replay_reuse_measurement_guard.py -v
pytest tests/test_production_resume_snapshot_reuse.py -v
pytest tests/test_production_bootstrap_snapshot_reuse.py -v
pytest tests/test_production_suffix_reuse_parity_guard.py -v
pytest tests/test_scanner_transition*.py -v
pytest tests/test_production*.py -v
```

The full safety validation remains:

```powershell
pytest
cd frontend
npm run build
```

## Deferred or low-priority areas

- `live_scanner.py` default mode already routes through `scan_actionable_production(...)`; the explicit `--full-replay` mode is not a Step 6 production optimization target.
- `tools/historical_validation.py` still contains manual research-style replay loops and can remain a low-priority tooling cleanup item.
- New trading logic, daily-entry triggers, SMC confirmation, and confidence modifiers should wait until the cleanup milestone is finished.

## Non-goals

This Step 6 work does not change detector rules or VSA evidence semantics; scoring, ranking, qualification, or actionability; checkpoint validation policy; API or frontend behavior; replay/manual-review behavior; HVR, stopping-volume, or climactic-action logic; trade plans, alerts, or orders.
