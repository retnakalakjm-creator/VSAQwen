# Historical Scanner Transition Runner

## Purpose

This document records the next safe Phase 4 migration slice after the transition contract and runner parity work.

The goal is to give non-production historical, audit, and future replay callers a named transition-runner adapter before changing production scanning. This keeps the architecture moving toward one deterministic scanner transition path while preserving current production behavior.

## Added boundary

`HistoricalScannerRunner` is a thin adapter over `ScannerTransitionEngine`:

```python
HistoricalScannerRunner().scan_to_index(metrics, target_index)
HistoricalScannerRunner().scan(metrics)
HistoricalScannerRunner().scan_actionable(metrics)
```

It is intended for historical and audit-style callers. It is not a production scanner replacement.

## Production boundary

`production_scanner.py` must remain isolated from this adapter until a later, explicitly approved production-wiring PR.

This slice does not change:

- production checkpoint loading
- production fallback behavior
- persisted scanner state
- scoring, ranking, qualification, or actionability
- detector rules
- frontend behavior

## Validation

The runner is tested against the current `ScannerEngine` semantics for:

- target candidate via `scan_to_index`
- full candidate sequence via `scan`
- latest actionable output via `scan_actionable`
- empty behavior before the minimum replay window
- production scanner isolation

## Next safe migration step

After this adapter is stable, move one non-production caller at a time onto `HistoricalScannerRunner`, starting with audit/historical endpoints. Each migration should have parity tests proving the output remains unchanged before and after the switch.

Do not optimize away prefix recomputation yet. Performance work belongs after runner migration and equivalence are stable.
