# TEST Scoring Integration Audit

This is an audit-only record. It does not change TEST semantics, detector logic, evidence weights, qualification, or scanner actionability.

## Current production state

`TEST` is currently emitted by `evidence/demand.py::_collect_test()` through `collect_demand()`.

The detector audit retained five production-path TEST observations after the strong-downtrend contradiction gate:

- bars `149`, `152`, `248`, `942`, `1084`

## Professional scoring result

The first production-path contribution audit produced exactly zero TEST contribution across all five events:

- average demand-score delta: `0.0`
- average strength delta: `0.0`
- average net-pressure delta: `0.0`
- average net-strength delta: `0.0`
- average confidence delta: `0.0`

## Cause

`professional/scoring_engine.py` calculates demand pressure from `config.DEMAND_EVIDENCE_WEIGHTS`.

The current demand weight map contains `STOPPING_VOLUME` and `SHAKEOUT`, but no `TEST` entry. Therefore TEST evidence is emitted and preserved in the evidence stream, but contributes `0.0` to professional demand scoring.

## Decision

Do **not** assign a numeric TEST weight based on the current five-event sample.

The detector audit establishes TEST semantics, but it does not establish a stable numeric weight. A numeric weight would currently be arbitrary and could make the scanner appear more confident without validated evidence that the weight improves decisions.

## Next audit

Run a dedicated TEST weight calibration audit against the historical TEST population and the existing scoring architecture.

The audit should compare candidate weights without modifying production configuration and measure:

- demand-score delta;
- net-pressure delta;
- professional-strength delta;
- confidence delta;
- outcome direction and forward returns;
- hold/failure classification;
- stability across the retained TEST observations.

Only after that audit should a production TEST weight be considered.

## Real-market constraint

The calibration must preserve the project rule that real markets do not reliably produce textbook-perfect VSA scenarios. The goal is not to reward textbook conformity; it is to determine whether a modest TEST contribution improves interpretation of genuine, imperfect low-effort probes without overpowering stronger evidence or future-validated context.
