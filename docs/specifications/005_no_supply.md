# NO_SUPPLY

## Status

**Contextual / validation-complete for its current non-scoring role.**

`NO_SUPPLY` is retained as demand-absence evidence. It is not promoted to an independently scored demand event.

## Role

`NO_SUPPLY` is a **contextual demand-absence probe**.

It describes reduced selling pressure / absence of meaningful supply in a bearish bar. It is not, by itself, proof of demand dominance or a standalone reversal signal.

## Canonical Semantics

A `NO_SUPPLY` observation requires the following point-in-time conditions:

1. Bullish environment / non-bearish structural context.
2. Bearish current bar.
3. Low VSA volume.
4. Narrow VSA spread.

Supporting confirmations include:

- weak/narrow spread evidence;
- decreasing volume;
- weak selling result;
- higher-low context where available.

The supporting confirmations are quality evidence and are not individually mandatory production gates.

The detector should continue to accept imperfect but meaningful real-market VSA evidence rather than forcing textbook-perfect bars.

## Point-in-Time Rule

`NO_SUPPLY` qualification must use only information available on the observation bar and prior confirmed context.

A future bar must never be used to qualify, emit, or strengthen the `NO_SUPPLY` event itself.

## Production Role

`NO_SUPPLY` is enabled in `EvidenceEngine.collect()` through the demand collection path.

It remains available to the evidence layer but is intentionally excluded from standalone demand-pressure scoring. The existing regression test enforces this role by requiring that `EvidenceCode.NO_SUPPLY` is not present in `config.DEMAND_EVIDENCE_WEIGHTS`, while remaining present in the evidence model. 

## Validation Record

Across the eight-symbol validation universe:

- symbols requested: `8`
- symbols with events: `7 / 8`
- validated events: `23`
- positive 8-bar outcomes: `14`
- negative 8-bar outcomes: `9`
- flat outcomes: `0`
- insufficient forward data: `0`
- decisive outcomes: `23`
- positive decisive rate: `60.87%`
- replay failures: `0`

Per-symbol event counts were:

| Symbol | Events | Positive | Negative | Positive decisive rate |
|---|---:|---:|---:|---:|
| `BHARTIARTL.NS` | 3 | 1 | 2 | 33.33% |
| `RELIANCE.NS` | 3 | 1 | 2 | 33.33% |
| `HDFCBANK.NS` | 3 | 2 | 1 | 66.67% |
| `ICICIBANK.NS` | 0 | 0 | 0 | — |
| `INFY.NS` | 4 | 2 | 2 | 50.00% |
| `TCS.NS` | 5 | 3 | 2 | 60.00% |
| `SBIN.NS` | 1 | 1 | 0 | 100.00% |
| `LT.NS` | 4 | 4 | 0 | 100.00% |

## Robustness Record

The 23-event population remained present under leave-one-symbol-out analysis.

Positive decisive rates across exclusions ranged from `52.63%` to `65.00%`.

This indicates that the observed population is not dependent on one symbol, but the sample is not strong enough to justify independent scoring.

## Semantic-Quality Record

Across the 23 validated events:

- low-effort probe: `23 / 23`
- meaningful selling context: `23 / 23`
- higher low: `12 / 23`
- volume decreasing: `16 / 23`
- weak selling result: `12 / 23`
- semantic-quality-like: `21 / 23` (`91.30%`)

The audit also found `10 / 23` cases in confirmed-downtrend context. A context-refinement comparison showed that simply excluding healthy/confirmed downtrend cases would collapse the event population to only `2` or `1` events respectively. Therefore confirmed-downtrend context is **not** adopted as a mandatory rejection rule.

This preserves real-market VSA interpretation instead of overfitting the detector to a small historical sample.

## Sequence / Support-Value Record

A targeted sequence-support audit compared primary `STOPPING_VOLUME` anchors with and without prior `NO_SUPPLY` in the preceding `4`, `8`, `12`, and `20` weekly bars.

The audit remained strictly point-in-time: only `NO_SUPPLY` observations **before** the primary anchor were treated as potential support.

Population:

- primary anchor events: `59`
- primary candidate bars examined: `1022`
- `NO_SUPPLY` candidate bars inside anchor windows: `177`
- validated `NO_SUPPLY` bars: `20`

Support comparison:

| Prior window | Anchors with prior `NO_SUPPLY` | Positive rate with `NO_SUPPLY` | Anchors without prior `NO_SUPPLY` | Positive rate without `NO_SUPPLY` |
|---|---:|---:|---:|---:|
| 4 bars | 1 | 100.00% | 58 | 74.14% |
| 8 bars | 1 | 100.00% | 58 | 74.14% |
| 12 bars | 1 | 100.00% | 58 | 74.14% |
| 20 bars | 4 | 75.00% | 55 | 74.55% |

The short-window 100% values are each based on a single event and are not statistically meaningful. The 20-bar comparison provides the largest support population and shows only a `+0.45` percentage-point difference.

Therefore the audit does **not** establish measurable incremental support value for `NO_SUPPLY` when paired with the existing `STOPPING_VOLUME` anchor sample.

## Scoring Decision

```text
NO_SUPPLY = 0.00
```

No standalone demand weight is assigned.

`NO_SUPPLY` may continue to appear as contextual evidence in reports, evidence aggregation, and future interaction analysis, but it must not independently create demand pressure or actionability.

## Promotion Decision

`NO_SUPPLY` is **not** promoted to a production-scored primary event.

The current role is frozen as:

```text
Status: Contextual
Weight: 0.00
Role: Demand-absence probe
```

Future scoring consideration requires a materially larger and independent evidence sample demonstrating incremental value beyond existing primary events.

## Audit Boundary

This specification freezes the current semantic and scoring role only. It does not change detector implementation, evidence collection, scanner qualification, or production weights.
