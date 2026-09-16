# Transition Prefix Recomputation Measurement

## Purpose

This note captures the optimization target after the production transition migration was closed.

Production now reaches the transition path for:

- full replay/bootstrap/fallback candidates;
- valid checkpoint resume candidates;
- scanner snapshot creation and refresh.

Before changing production behavior, this guardrail documents and tests the current repeated-prefix recomputation shape so later optimization PRs can prove they only reduce duplicate work, not scanner semantics.

## Current measured behavior

`ScannerTransitionEngine.scan_to_index(metrics, target_index)` starts from an empty `ScanState` and calls `run_to_index(...)` through every bar from `ScannerEngine.MIN_REPLAY_BARS` to `target_index`.

Each step calls `features_for(metrics, index)`, and `features_for(...)` currently builds a copied point-in-time metrics prefix with:

```python
metrics.iloc[: index + 1].copy()
```

Therefore repeated independent `scan_to_index(...)` calls for increasing target bars rebuild earlier prefixes again. This behavior remains covered by `tests/test_transition_prefix_recomputation_measurement.py` so future optimization can be measured against a locked baseline.

## First suffix-reuse API

`ScannerTransitionEngine.scan_to_indices(metrics, target_indices)` is the first safe suffix-reuse API.

It accepts a strictly increasing target sequence and reuses one `ScanState` across those targets. The runner still evaluates every bar sequentially and still constructs point-in-time prefixes for each evaluated bar, but it does not replay earlier bars again for each later target.

For example, independent calls for targets `[53, 55, 57]` replay from `MIN_REPLAY_BARS` three times. `scan_to_indices(...)` evaluates from `MIN_REPLAY_BARS` through `57` once and records candidates at each requested target.

The API deliberately rejects duplicate or descending target sequences so no caller can accidentally treat it as a random-access cache.

## First historical consumer

`HistoricalScannerRunner.scan(...)` now consumes `ScannerTransitionEngine.scan_to_indices(...)` for the complete historical target range.

The historical runner still returns the same ordered candidate sequence, preserves strict point-in-time transition stepping, and keeps `scan_to_index(...)` and `scan_actionable(...)` on their existing boundaries.

Production scanner call sites and checkpoint policy are unchanged.

## Historical selected-target adapter

`HistoricalScannerRunner.scan_to_indices(...)` exposes the same suffix-reuse contract at the historical adapter boundary for callers that already know sparse target indices.

The method delegates to `ScannerTransitionEngine.scan_to_indices(...)`, so target validation, sequential stepping, and point-in-time behavior stay centralized in the transition engine.

This keeps future audit or historical callers on the named historical runner boundary instead of importing the transition engine directly just to use suffix reuse.

## First VSA event audit consumer

`build_vsa_event_audit(...)` now uses the selected-target `scan_to_indices(...)` boundary when the configured scanner exposes it.

The audit still bounds metrics at the resolved `end_index`, but it asks only for candidates in the resolved replay window instead of materializing the full candidate list and filtering it later. Scanner doubles that only implement `scan(...)` remain supported for focused tests.

This remains an audit-only optimization seam. It does not change production scanner call sites, checkpoint policy, detector rules, VSA semantics, scoring, ranking, qualification, actionability, API response shape, frontend runtime, replay/manual-review behavior, HVR policy, trade plans, alerts, or orders.

## Replay caller inventory

Current active migration status after the selected-target VSA event audit consumer:

| Area | Current boundary | Migration status | Next action |
| --- | --- | --- | --- |
| `ScannerTransitionEngine.scan_to_indices(...)` | Reuses one transition `ScanState` for strictly increasing target indices. | Migrated API. | Keep validation centralized here. |
| `HistoricalScannerRunner.scan(...)` | Calls `ScannerTransitionEngine.scan_to_indices(...)` for the complete historical target range. | Migrated consumer. | Keep parity and measurement coverage active. |
| `HistoricalScannerRunner.scan_to_indices(...)` | Exposes the selected-target batch boundary for historical and audit callers. | Migrated adapter. | Prefer this boundary over direct transition-engine imports in callers. |
| `build_vsa_event_audit(...)` | Resolves the replay window once, bounds metrics at `end_index`, and calls `scan_to_indices(...)` when available. | Migrated audit consumer. | Keep transition parity tests active. |
| `audit.runner.run_symbol_candidate_audit(...)` and `run_historical_candidate_audit(...)` | Default to `ScannerEngine` through `scanner_factory` and call `scanner_factory().scan(metrics)`. | Remaining high-value audit candidate. | Add candidate-audit parity first, then consider defaulting the analysis-only path to `HistoricalScannerRunner`. |
| `production_scanner.scan_latest_candidate_production(...)` | Latest target only; validated checkpoints resume through `ScannerTransitionResumeAdapter`, fallback uses `HistoricalScannerRunner().scan_to_index(...)`, and snapshots refresh through `ScannerTransitionSnapshotAdapter`. | Production path migrated but intentionally not optimized further here. | Defer until a production-specific guard proves checkpoint, resume, snapshot, and fallback behavior unchanged. |
| `live_scanner.py` | Default live path uses `scan_actionable_production(...)`; the `--full-replay` option still calls the original scanner actionable path. | Not a repeated historical replay migration target by default. | Leave unchanged unless full-replay live mode becomes a current optimization target. |
| `tools/historical_validation.py` | Manually loops over target bars and builds `metrics.iloc[: target_index + 1].copy()` for validation evidence collection. | Remaining low-priority tooling candidate. | Migrate only after audit-runner work, or keep as an explicit research script. |

## Follow-up PR queue

1. Add candidate-audit parity coverage proving `audit.runner` outputs match when driven by `ScannerEngine` and `HistoricalScannerRunner`.
2. Move the analysis-only candidate audit default to `HistoricalScannerRunner` after parity is locked.
3. Keep production latest-candidate optimization deferred until checkpoint, resume, snapshot, and fallback guardrails are specific enough for that path.
4. Consider a tooling-only migration for `tools/historical_validation.py` after the audit-runner path is finished.
5. Add a final measurement follow-up that records reduced replay work for migrated consumers without changing scanner logic.

## Existing safe reuse seam

`ScannerTransitionEngine.run_to_index(metrics, target_index, state=existing_state)` continues to support continuing from a prior `ScanState`.

When a caller supplies a state whose `last_bar_index` is behind the target, the runner starts at `last_bar_index + 1` and evaluates only the new suffix. The measurement tests lock this seam because it is the safest optimization boundary.

## Optimization contract for later PRs

A later optimization may reuse transition state or cached per-prefix work only if it preserves:

- candidate output parity for every target bar;
- strict sequential step ordering;
- point-in-time metrics visibility;
- engine/config/data fingerprint behavior at production state boundaries;
- fallback diagnostics and checkpoint validation behavior.

## Non-goals for this consumer work

This work does not change:

- detector rules or VSA evidence semantics;
- scoring, ranking, qualification, or actionability;
- production scanner call sites or checkpoint policy;
- API or frontend behavior;
- replay/manual-review behavior;
- HVR, stopping-volume, or climactic-action logic;
- trade plans, alerts, or orders.
