# Transition Suffix Reuse Consumer Measurement

This note records the measurement follow-up for the Step 6 suffix-reuse consumer migrations.

## Purpose

The migrated historical and audit consumers should route repeated replay targets through batch suffix-reuse boundaries without changing scanner semantics.

This is a measurement-only guard. It documents the expected work-shape after the consumer migrations and is backed by `tests/test_transition_suffix_reuse_consumer_measurements.py`.

## Measured consumers

| Consumer | Expected suffix-reuse shape |
| --- | --- |
| `HistoricalScannerRunner.scan(...)` | Requests one continuous `scan_to_indices(...)` span from `ScannerEngine.MIN_REPLAY_BARS` through the final historical bar. |
| `audit.runner.run_symbol_candidate_audit(...)` | Reaches the historical runner scan boundary, so the full candidate audit path uses the same continuous suffix-reuse span when driven by `HistoricalScannerRunner`. |
| `build_vsa_event_audit(...)` | Requests only the selected replay target range from `scan_to_indices(...)` while still bounding metrics at the resolved `end_index`. |

## Measurement contract

The measurement tests use recording doubles around the existing public seams. They do not alter scanner logic, detector rules, scoring, ranking, production checkpoint policy, API shape, frontend behavior, replay/manual-review behavior, HVR policy, trade plans, alerts, or orders.

The tests assert that migrated consumers ask for fewer replay target evaluations than independent prefix replay would require for the same target set.

## Deferred areas

Production latest-candidate paths remain deferred until a production-specific guard proves checkpoint, resume, snapshot, and fallback behavior unchanged.

`tools/historical_validation.py` remains a lower-priority tooling/research path and is not part of this measurement closure.
