# Outcome Validation Policy

Milestone 3 focuses on measuring which scanner evidence actually adds forward
value before changing production weights or adding more signal rules.

## Execution timing

Historical validation must not assume a same-bar entry. A signal observed on bar
`N` is evaluated from the close of bar `N + 1`.

This matches the production scanner's signal/execution split:

- signal bar: where VSA evidence or scanner qualification appears;
- execution bar: the following bar/session;
- horizon exit: `execution_bar + horizon_bars`.

If there is no execution bar after a signal, the signal is not scored.

## Forward returns

`audit.outcomes.compute_forward_outcome()` reports:

- `raw_return`: exit close / entry close - 1;
- `favorable_return`: raw return adjusted for long or short direction;
- `mfe`: maximum favorable excursion after the execution close;
- `mae`: maximum adverse excursion after the execution close;
- `complete`: whether the full requested horizon exists.

For long outcomes, positive raw returns are favorable. For short outcomes,
negative raw returns are favorable. Neutral outcomes report zero favorable return.

## Partial horizons

Partially available horizons are retained with `complete=False` instead of being
silently dropped. This lets audit reports decide explicitly whether to:

- use only fully completed horizons;
- include partial horizons for exploratory diagnostics;
- report both full-sample and latest-edge samples separately.

Production calibration should use completed horizons unless a report clearly
labels the partial-horizon treatment.

## Production boundary

Outcome utilities are analysis-only. They must not be imported by production
scanner paths to decide actionability, qualification, ranking, or evidence
weights directly.

Recommended calibration workflow:

1. Generate point-in-time event/candidate observations.
2. Attach next-bar-execution outcomes with this module.
3. Aggregate by evidence code, trend state, anomaly flag, qualification, and
   horizon.
4. Propose weight or gating changes in separate production PRs only after the
   evidence is reviewed.

## Test-suite boundary

Fast deterministic regression tests stay in the default `pytest` path. Historical
research scripts, long-running audit checks, and stale robustness reports are
quarantined from default pytest collection by `tests/conftest.py`.

Run those archived checks explicitly by filename only when doing calibration
research.
