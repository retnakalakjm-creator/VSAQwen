# BUYING_CLIMAX — Production & Audit Record

## Status

**Production-active, audit-complete for the current detector and runtime-weight architecture.**

`BUYING_CLIMAX` is emitted by the real `EvidenceEngine.collect()` production path through `evidence/supply.py::_collect_buying_climax`.

## Production semantics

The detector requires, point-in-time:

1. Buying campaign context.
2. Bullish bar.
3. Very-high volume.
4. Above-average spread.

Confirmations currently include:

- wide spread,
- weak close,
- increasing volume.

The detector intentionally preserves meaningful imperfect real-market VSA evidence rather than requiring textbook-perfect patterns.

## Production-path verification

Latest validated production-path audit:

- symbols requested: `8`
- symbols with results: `8`
- cheap candidates: `432`
- engine replays: `432`
- campaign-qualified / production emissions: `181`
- expected campaign events: `181`
- duplicate emissions: `0`
- campaign mismatches: `0`
- runtime weights out of bounds: `0`
- runtime bounds: `0.50 .. 2.00`
- interaction penalty configured in production: `NO`
- production score mutation: `NO`
- errors: `0`
- status: `PASS`

## Weight provenance

Three different weight concepts must not be conflated:

| Weight concept | BUYING_CLIMAX value | Meaning |
|---|---:|---|
| Registry/profile weight | `1.00` | Static metadata in `evidence/profiles.py`. |
| Runtime weight | Dynamic | Calculated by `WeightCalculator._buying_climax_weight(ctx)` from market environment, trend state, structural progression, and climactic evaluation. |
| Empirical reference weight | `0.38` | Analysis/calibration reference used in decision-value experiments; **not** the current production runtime weight. |

Runtime provenance audit across the 8-symbol universe showed:

- runtime emissions: `289` in the full replay population,
- runtime minimum: `0.90`,
- runtime maximum: `2.00`,
- runtime mean: approximately `1.4464`,
- runtime weights are dynamic.

Therefore a production audit must validate the runtime calculator architecture and bounds; it must **not** require every BUYING_CLIMAX emission to equal `0.38`.

## Interaction findings

Across the 181 campaign-qualified BUYING_CLIMAX events:

- `UPTHRUST` overlap: `181 / 181`
- `INCREASING_DEMAND + UPTHRUST`: `119`
- `UPTHRUST` only: `53`
- small remaining combinations: `9`

The overlap with `UPTHRUST` is not itself harmful evidence:

- `UPTHRUST` only: `66.04%` positive decisive rate, `+4.75%` mean 8-bar return.

The large `INCREASING_DEMAND + UPTHRUST` combination is weaker:

- `119` events,
- `51.69%` positive decisive rate,
- `+2.20%` mean 8-bar return.

A provisional interaction penalty of `0.20` was tested analytically for this specific combination.

## Decision-value conclusion

Aggregate BUYING_CLIMAX decision-value audit:

| Mode | Positive decisive rate | Mean 8-bar return |
|---|---:|---:|
| Unpenalized | `56.35%` | `+3.03%` |
| Provisional `0.20` interaction penalty | `57.12%` | `+3.15%` |
| Eligible market | `60.79%` | `+3.83%` |

The interaction penalty improves the measured BUYING_CLIMAX population, but the detector remains below the eligible-market baseline.

## Frozen decision

```text
production collector       = YES
production emission        = YES
registry weight             = 1.00
runtime weight              = DYNAMIC (0.90 .. 2.00 observed)
empirical reference weight  = 0.38
interaction penalty         = 0.20 (PROVISIONAL / ANALYSIS-ONLY)
production interaction rule = NO
production mutation         = NO
standalone decision value   = BELOW MARKET BASELINE
status                      = PRODUCTION-ACTIVE / AUDIT-COMPLETE
```

`BUYING_CLIMAX` must remain available as production evidence. The provisional interaction penalty must not be promoted into production scoring until separately authorized by a production-path audit and decision-value review.
