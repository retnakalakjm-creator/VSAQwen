# VSA Event Causality Audit Policy

This document records the current Milestone 3 baseline for VSA event detector
review. The goal is to make every production evidence event explicit before any
future calibration PR changes weights, thresholds, or gating rules.

## Scope

The audit catalog lives in `audit.vsa_events`. It is analysis-only and must not
be imported by production scanner paths to change signal generation.

The catalog is intentionally aligned with the existing documentation layer under
`docs/` instead of replacing it.

Canonical and audit source documents include:

```text
docs/PRIMARY_VSA_EVENT_MATRIX.md
docs/specifications/001_stopping_volume.md
docs/specifications/002_shakeout.md
docs/specifications/003_test.md
docs/specifications/004_spring.md
docs/specifications/005_no_supply.md
docs/ABSORPTION_AUDIT.md
docs/BUYING_CLIMAX_AUDIT.md
docs/DEMAND_COMING_IN_AUDIT.md
docs/INCREASING_DEMAND_AUDIT.md
docs/NO_DEMAND_AUDIT.md
docs/SUPPLY_COMING_IN_AUDIT.md
docs/UPTHRUST_AUDIT.md
```

The current catalog covers these core VSA events:

```text
STOPPING_VOLUME
SELLING_CLIMAX
TEST
NO_SUPPLY
INCREASING_DEMAND
SHAKEOUT
SPRING
BUYING_CLIMAX
UPTHRUST
NO_DEMAND
SUPPLY_COMING_IN
ABSORPTION
```

## Causality definitions

### Current-bar recognition

Most VSA events are recognized on the current candidate bar using only:

- the current bar,
- the previous bar,
- rolling classifications already present in the metrics frame,
- recent background context available up to that bar, and
- structural context confirmed at or before that point in time.

These events must not require a future bar before being emitted.

Current-bar catalog members include:

```text
STOPPING_VOLUME
SELLING_CLIMAX
TEST
NO_SUPPLY
INCREASING_DEMAND
BUYING_CLIMAX
UPTHRUST
NO_DEMAND
SUPPLY_COMING_IN
ABSORPTION
```

### Recovery-anchored recognition

`SHAKEOUT` is different. The original shakeout candidate requires a later test
and later recovery. The event is therefore emitted only when the recovery bar is
the current bar. This is delayed recognition, not candidate-bar look-ahead.

The implementation must preserve this boundary:

```python
point_in_time_metrics = validation_metrics.iloc[: current_index + 1]
```

and should emit the evidence with both `test_index` and `recovery_index` so
future audit reports can distinguish the original test from the recognized
signal bar.

### Confirmation-anchored recognition

`SPRING` is also delayed. The original support-break candidate is not emitted as
a completed Spring until a later low-effort test and bullish confirmation are
present. Production collection slices the metrics frame through the current
confirmation bar before validating the sequence.

The implementation must preserve this boundary:

```python
point_in_time = metrics.iloc[: current_index + 1].copy()
```

This is confirmation-anchored recognition, not candidate-bar look-ahead.

## Confirmation behavior

The current shared detector helper uses mandatory requirements as the gate.
Optional confirmations are counted but do not prevent evidence emission once all
mandatory requirements pass.

That means confirmations are currently diagnostic only for events such as:

- `STOPPING_VOLUME`,
- `SELLING_CLIMAX`,
- `TEST`,
- `NO_SUPPLY`,
- `BUYING_CLIMAX`,
- `UPTHRUST`, and
- `NO_DEMAND`.

Any future PR that turns confirmations into mandatory gates is a production logic
change. It should include separate calibration evidence and regression tests.

## Documentation alignment notes

### ABSORPTION matrix conflict

`docs/ABSORPTION_AUDIT.md` and current source code describe ABSORPTION as
production-connected / non-scoring / frozen through the demand collection path.

Current source path:

```text
EvidenceEngine.collect()
  -> collect_demand()
  -> collect_absorption(ctx)
```

However, `docs/PRIMARY_VSA_EVENT_MATRIX.md` still contains older wording saying
ABSORPTION has no active production detector / no production path.

This PR records the conflict in `audit.vsa_events`; it does not modify the older
matrix document. A later documentation-cleanup PR should reconcile the matrix
with the current code and ABSORPTION audit record.

### NO_DEMAND path typo

`docs/NO_DEMAND_AUDIT.md` describes the collector as
`evidence/demand.py::_collect_no_demand`, but the current source defines the
production detector in `evidence/supply.py::_collect_no_demand`.

This PR records the mismatch; it does not move the detector or alter production
behavior. A later documentation-cleanup PR can correct the audit record wording.

### NO_SUPPLY naming mismatch

The current source labels one mandatory requirement as `Bullish Environment` but
calls `ctx.is_bearish_environment()`.

This PR documents the mismatch; it does not rename or change the production
behavior. A future cleanup PR can rename the requirement label if tests confirm
that downstream output formatting is unaffected.

### Campaign snapshots

Some detectors use `CampaignSnapshot.from_context(ctx)`. This remains causal only
when `ctx` is built from a point-in-time metrics prefix. Future replay or batch
optimizations must preserve that property.

### Confirmed structural context

Structural swing context should be filtered to swings confirmed at or before the
candidate bar. The shakeout path already does this in its candidate snapshot.
Future detector work should keep the same principle.

## Safe calibration workflow

Use this order before changing VSA rules:

1. confirm the detector's causality contract,
2. confirm the relevant `docs/` audit/specification record,
3. generate `candidate_outcomes.csv`,
4. review `evidence_summary.csv`,
5. review `evidence_stability.csv`,
6. check whether the event is stable across horizons and sides,
7. inspect a few chart examples manually, and
8. only then propose a production scoring or gating PR.

This avoids turning noisy small-sample calibration artifacts into production
logic changes.

## Production boundary

This audit catalog must remain analysis-only. It may describe current production
behavior, documentation conflicts, and audit observations, but it must not change
scanner scoring, event emission, actionability, API payloads, or live-scanner
behavior.
