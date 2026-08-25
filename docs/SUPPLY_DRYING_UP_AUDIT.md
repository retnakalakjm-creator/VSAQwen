# SUPPLY_DRYING_UP Audit Record

## Frozen production state

- Production role: `contextual_supply_exhaustion`
- Registry/reference weight: `1.00`
- Professional supply-map weight: `0.60`
- Runtime `Evidence.weight`: dynamic emission metadata
- Observed runtime `Evidence.weight`: `1.00`–`1.00`, mean `1.00`
- Runtime bounds: `0.50`–`2.00`

## Candidate audit

- Symbols requested: `8`
- Symbols with results: `8`
- Cheap candidates: `547`
- Production emissions: `225`
- Normal detector rejections: `322`
- Positive outcomes: `139`
- Negative outcomes: `86`
- Flat outcomes: `0`
- Decisive outcomes: `225`
- Positive decisive rate: `61.78%`
- Mean 8-bar return: `+3.56%`
- Semantic failures: `0`
- Duplicate emissions: `0`

The candidate population and production emissions were evaluated point-in-time, at the target bar, using the production `EvidenceEngine` emission as the semantic authority. Production configuration was not mutated.

## Semantic-quality audit

All `225` production emissions satisfied the mandatory production definition:

1. Down bar.
2. Low volume.
3. Narrow spread.

Semantic counts:

- `down_bar`: `225 / 225`
- `low_volume`: `225 / 225`
- `narrow_spread`: `225 / 225`
- Mandatory semantic failures: `0`

There are no mandatory confirmations for `SUPPLY_DRYING_UP`.

## Interaction audit

The target evidence was excluded from self-conflict accounting.

- Supply-side interactions: `0 / 225`
- Demand-side interactions: `66 / 225`
- `TEST`: `47`
- `NO_SUPPLY`: `23`
- `NO_SUPPLY + TEST`: `4`

Exact same-bar combinations:

- Clean: `159`
- `SUPPLY_DRYING_UP + TEST`: `43`
- `SUPPLY_DRYING_UP + NO_SUPPLY`: `19`
- `SUPPLY_DRYING_UP + NO_SUPPLY + TEST`: `4`

Unexpected combinations: none.

## Exact interaction outcomes

Reference population:

- Clean `SUPPLY_DRYING_UP`: `159` events
- Positive decisive rate: `59.75%`
- Mean 8-bar return: `+4.21%`

Interaction groups:

### `SUPPLY_DRYING_UP + TEST`

- Events: `43`
- Positive: `30`
- Negative: `13`
- Flat: `0`
- Decisive: `43`
- Positive decisive rate: `69.77%`
- Delta vs clean: `+10.02 pp`
- Mean return: `+2.55%`
- Mean-return delta vs clean: `-1.66 pp`

This interaction improves hit rate but reduces average return magnitude relative to clean `SUPPLY_DRYING_UP`.

### `SUPPLY_DRYING_UP + NO_SUPPLY`

- Events: `19`
- Positive: `12`
- Negative: `7`
- Flat: `0`
- Decisive: `19`
- Positive decisive rate: `63.16%`
- Delta vs clean: `+3.41 pp`
- Mean return: `+0.45%`
- Mean-return delta vs clean: `-3.76 pp`

This interaction produces a slightly better hit rate but materially weaker follow-through magnitude. It is not classified as an automatic semantic contradiction.

### `SUPPLY_DRYING_UP + NO_SUPPLY + TEST`

- Events: `4`
- Positive: `2`
- Negative: `2`
- Flat: `0`
- Decisive: `4`
- Positive decisive rate: `50.00%`
- Delta vs clean: `-9.75 pp`
- Mean return: `+3.73%`
- Mean-return delta vs clean: `-0.48 pp`

The population is too small for scoring calibration.

## Decision-value audit

Compared with the eligible market population:

- Candidate events: `225`
- Eligible market events: `11,345`
- Candidate positive decisive rate: `61.78%`
- Eligible market positive decisive rate: `60.79%`
- Positive-rate lift vs market: `+0.99 pp`
- Candidate mean 8-bar return: `+3.56%`
- Eligible-market mean 8-bar return: `+3.83%`
- Mean-return lift vs market: `-0.26 pp`
- Candidate share of eligible events: `1.98%`

The event shows modest incremental selectivity by hit rate, but does not outperform the eligible market on mean return magnitude.

Therefore the evidence supports retaining the event as a contextual supply-exhaustion signal, but does not justify an automatic global scoring promotion.

## Production-path readiness

- Cheap candidates: `547`
- Production emissions: `225 / 225`
- Registry entry: present
- Registry/reference weight: `1.00`
- Professional `SUPPLY_EVIDENCE_WEIGHTS` entry: present
- Professional scoring-map weight: `0.60`
- Production role: `contextual_supply_exhaustion`
- Runtime weight model: dynamic `Evidence.weight` metadata
- Runtime observed weight: `1.00`–`1.00`, mean `1.00`
- Runtime within configured bounds: `True`
- Registry/config discrepancy: `True`
- Duplicate emissions: `0`
- Semantic failures: `0`
- Point-in-time: `True`
- Target-bar only: `True`
- Production context used: `True`
- Production emission authority: `True`
- Production-path mutation: `False`

The registry/config discrepancy is not itself a failure because `Evidence.weight` is runtime emission metadata while `SUPPLY_EVIDENCE_WEIGHTS` is the separate professional scoring map.

## Frozen production decision

- `SUPPLY_DRYING_UP` remains production-valid.
- Keep production role as contextual supply exhaustion.
- No global weight promotion based on current standalone decision value.
- No rejection rule.
- No qualification change.
- No actionability change.
- `TEST` remains a potentially useful confirming interaction for further study, but no automatic bonus is introduced.
- `NO_SUPPLY` remains a diagnostic interaction with materially reduced return magnitude; no automatic penalty is introduced.
- The 4-event `NO_SUPPLY + TEST` subgroup is too small for calibration.
- No production configuration is changed by this audit record.

## Final status

Production candidate population: PASS.
Semantic quality: PASS.
Interaction integrity: PASS.
Exact interaction population/outcomes: PASS.
Standalone decision value: PASS technically, with modest positive hit-rate lift and slightly negative mean-return lift.
Production readiness: PASS.
Production scoring change: NONE.
