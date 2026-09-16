# Production Replay Reuse Measurement Guard

## Purpose

This Step 6 guard protects the production replay-reuse optimizations introduced after the production parity guard.

The guarded behavior is narrow:

1. production needs a full replay because there is no usable checkpoint, or the checkpoint is corrupt/stale;
2. the latest candidate is produced through the historical full-replay boundary;
3. the durable snapshot is built from the transition state already produced by that same replay;
4. production does not perform a second transition replay just to refresh the snapshot.

It also protects the validated behind-checkpoint resume path:

1. production loads a fingerprint-valid checkpoint that is behind the latest completed bar;
2. the resume adapter advances from the checkpoint to the latest bar;
3. the refreshed durable snapshot is built from that already-resumed transition state;
4. production does not perform a second transition replay after resume just to refresh the snapshot.

## What the guard measures

`tests/test_production_replay_reuse_measurement_guard.py` patches `ScannerTransitionEngine.run_to_index(...)` and records actual replay calls through the production path.

The expected bootstrap/fallback shape is one full replay:

```text
[(len(metrics), latest_index, resumed_from_state=False)]
```

The expected behind-checkpoint resume shape is one stateful replay:

```text
[(len(metrics), latest_index, resumed_from_state=True)]
```

The test fails if a future change accidentally reintroduces either older shape:

```text
candidate full replay
+ separate snapshot full replay
```

or:

```text
resume latest candidate
+ separate snapshot replay
```

## Covered paths

- first-run bootstrap with no saved checkpoint;
- corrupt checkpoint fallback;
- stale data-fingerprint checkpoint fallback;
- valid behind-checkpoint resume with snapshot refresh;
- latest-valid checkpoint behavior, which still evaluates the latest candidate but skips snapshot refresh.

## Boundaries

This guard is tests/docs only. It does not change detector logic, VSA semantics, scoring, ranking, qualification, actionability, checkpoint policy, API shape, frontend runtime, replay/manual-review behavior, HVR policy, trade plans, alerts, or orders.
