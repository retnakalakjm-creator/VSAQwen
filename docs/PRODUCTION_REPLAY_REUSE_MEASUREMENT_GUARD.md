# Production Replay Reuse Measurement Guard

## Purpose

This Step 6 guard protects the production bootstrap/fallback replay-reuse optimization introduced after the production parity guard.

The guarded behavior is narrow:

1. production needs a full replay because there is no usable checkpoint, or the checkpoint is corrupt/stale;
2. the latest candidate is produced through the historical full-replay boundary;
3. the durable snapshot is built from the transition state already produced by that same replay;
4. production does not perform a second transition replay just to refresh the snapshot.

## What the guard measures

`tests/test_production_replay_reuse_measurement_guard.py` patches `ScannerTransitionEngine.run_to_index(...)` and records actual replay calls through the production path.

The expected bootstrap/fallback shape is one replay:

```text
[(len(metrics), latest_index, resumed_from_state=False)]
```

The test fails if a future change accidentally reintroduces this older shape:

```text
candidate full replay
+ separate snapshot full replay
```

## Covered paths

- first-run bootstrap with no saved checkpoint;
- corrupt checkpoint fallback;
- stale data-fingerprint checkpoint fallback;
- latest-valid checkpoint behavior, which still evaluates the latest candidate but skips snapshot refresh.

## Boundaries

This guard is tests/docs only. It does not change detector logic, VSA semantics, scoring, ranking, qualification, actionability, checkpoint policy, API shape, frontend runtime, replay/manual-review behavior, HVR policy, trade plans, alerts, or orders.
