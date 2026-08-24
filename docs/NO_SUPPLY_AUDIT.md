# NO_SUPPLY Audit Record

## Frozen production state

- Production path: YES
- Production role: contextual / non-scoring
- Registry/reference weight: 1.00
- Configurable professional scoring-map entry: NONE
- Weight sensitivity: not applicable because NO_SUPPLY is absent from both professional scoring maps.

## Candidate audit

- Symbols: 8
- Cheap candidates: 225
- Production emissions: 23
- Expected emissions: 23
- Normal detector rejections: 202
- Positive outcomes: 14
- Negative outcomes: 9
- Flat outcomes: 0
- Positive decisive rate: 60.87%
- Mean 8-bar return: +1.02%

## Semantic-quality audit

Mandatory production requirements:

1. Bullish Environment label using the production predicate `ctx.is_bearish_environment()`.
2. Bearish Bar.
3. Low Volume.
4. Narrow Spread.

All 23 emitted events satisfied all mandatory requirements.

Confirmations are non-mandatory:

- Volume Decreasing: 16 / 23.
- Weak Close: 12 / 23.

Semantic failures: 0.

## Interaction audit

- Interaction rate: 100%.
- Supply interaction: `SUPPLY_DRYING_UP` on 23 / 23 events.
- Demand interaction: `TEST` on 4 / 23 events.
- Self-conflict excluded: YES.
- No automatic contradiction penalty is justified.

## Interaction outcome audit

- `NO_SUPPLY + SUPPLY_DRYING_UP`: 19 events, 63.16% positive decisive rate, +0.45% mean 8-bar return.
- `NO_SUPPLY + SUPPLY_DRYING_UP + TEST`: 4 events, 50.00% positive decisive rate, +3.73% mean 8-bar return.

The interaction population is too small and does not establish a reliable production penalty or rejection rule.

## Decision-value audit

Compared with the eligible-market population:

- Candidate positive decisive rate: 60.87%.
- Eligible-market positive decisive rate: 60.80%.
- Positive-rate lift: +0.07 pp.
- Candidate mean 8-bar return: +1.02%.
- Eligible-market mean return: +3.83%.
- Mean-return lift: -2.81 pp.
- Candidate share of eligible events: 0.20%.

The current NO_SUPPLY definition does not demonstrate incremental decision value over the eligible-market baseline. It therefore remains contextual/non-scoring.

## Production-path readiness

- Cheap candidates: 225.
- Production emissions: 23 / 23 expected.
- Registry entry: YES.
- Supply scoring-map entry: NO.
- Demand scoring-map entry: NO.
- Runtime Evidence.weight model: dynamic WeightCalculator.
- Observed runtime Evidence.weight: 0.90–1.50.
- Validated runtime bounds: 0.50–2.00.
- Duplicate emissions: 0.
- Semantic/provenance failures: 0.
- Production-path mutation: FALSE.
- Point-in-time: TRUE.
- Target-bar only: TRUE.

## Frozen decision

- NO_SUPPLY remains production-connected contextual/non-scoring evidence.
- No professional scoring weight is introduced.
- No interaction penalty is introduced.
- No rejection rule is introduced.
- No production detector logic is changed by this audit campaign.
