# UPTHRUST Audit Record

## Frozen production state

- Production path: YES
- Production role: active supply trap
- Registry/reference weight: 1.00
- Professional supply-map weight: 0.90
- Runtime Evidence.weight: dynamic WeightCalculator metadata

## Candidate audit

- Symbols: 8
- Cheap candidates: 1,319
- Production candidate events: 289
- Expected events: 289
- Normal detector rejections: 1,030
- Positive outcomes: 170
- Negative outcomes: 118
- Flat outcomes: 1
- Decisive outcomes: 288
- Positive decisive rate: 59.03%
- Mean 8-bar return: +2.81%
- Semantic failures: 0
- Duplicate emissions: 0

Candidate population and production-emission replay are point-in-time and use the production emission as the authority.

## Semantic-quality audit

All 289 production UPTHRUST emissions satisfied every mandatory production requirement:

1. Buying Campaign.
2. Bullish Bar.
3. Very High Volume.
4. Above-Average Spread.

Confirmations are non-mandatory:

- Wide Spread: 185 / 289.
- Weak Close: 13 / 289.
- Lower Close Than Previous: 8 / 289.

Semantic failures: 0.

## Interaction audit

All 289 UPTHRUST events had same-bar interaction with additional evidence.

- Supply interaction: 289 / 289.
- `BUYING_CLIMAX`: 289 / 289.
- `HIDDEN_SUPPLY`: 13 / 289.
- Demand interaction: 224 / 289.
- `INCREASING_DEMAND`: 224 / 289.
- `SPRING`: 1 / 289.
- Self-conflict excluded: YES.

Exact interaction combinations:

- `UPTHRUST + BUYING_CLIMAX`: 63 events.
- `UPTHRUST + BUYING_CLIMAX + INCREASING_DEMAND`: 212 events.
- `UPTHRUST + BUYING_CLIMAX + HIDDEN_SUPPLY`: 2 events.
- `UPTHRUST + BUYING_CLIMAX + HIDDEN_SUPPLY + INCREASING_DEMAND`: 11 events.
- `UPTHRUST + BUYING_CLIMAX + INCREASING_DEMAND + SPRING`: 1 event.

Unexpected combinations: none.

## Exact interaction outcomes

| Combination | Events | Positive | Negative | Flat | Positive decisive rate | Mean 8-bar return |
|---|---:|---:|---:|---:|---:|---:|
| `UPTHRUST + BUYING_CLIMAX` | 63 | 42 | 21 | 0 | 66.67% | +4.80% |
| `UPTHRUST + BUYING_CLIMAX + INCREASING_DEMAND` | 212 | 120 | 91 | 1 | 56.87% | +2.27% |
| `UPTHRUST + BUYING_CLIMAX + HIDDEN_SUPPLY` | 2 | 1 | 1 | 0 | 50.00% | -2.85% |
| `UPTHRUST + BUYING_CLIMAX + HIDDEN_SUPPLY + INCREASING_DEMAND` | 11 | 7 | 4 | 0 | 63.64% | +3.77% |
| `UPTHRUST + BUYING_CLIMAX + INCREASING_DEMAND + SPRING` | 1 | 0 | 1 | 0 | 0.00% | -8.43% |

The pure `UPTHRUST + BUYING_CLIMAX + INCREASING_DEMAND` subgroup is materially weaker than the `UPTHRUST + BUYING_CLIMAX` reference:

- Positive decisive rate delta: -9.28 percentage points.
- Mean-return delta: -2.29 percentage points.

This is an empirical association, not sufficient evidence for an automatic production penalty.

## Decision-value audit

Compared with the eligible-market population:

- Candidate positive decisive rate: 59.03%.
- Eligible-market positive decisive rate: 60.80%.
- Positive-rate lift vs market: -1.77 pp.
- Candidate mean 8-bar return: +2.81%.
- Eligible-market mean 8-bar return: +3.83%.
- Mean-return lift vs market: -1.02 pp.
- Candidate share of eligible events: 2.55%.

The current UPTHRUST population does not demonstrate positive standalone incremental decision value over the eligible-market baseline.

This does not invalidate the VSA event semantically and does not justify removing the production detector.

## Production-path readiness

- Cheap candidates: 1,319.
- Production emissions: 289 / 289 expected.
- Normal detector rejections: 1,030.
- Registry entry: YES.
- Professional supply-map entry: YES.
- Demand-map entry: NO.
- Production role: active supply trap.
- Runtime Evidence.weight observed: 0.80–2.00.
- Runtime Evidence.weight mean: 1.2194.
- Validated runtime bounds: 0.50–2.00.
- Duplicate emissions: 0.
- Point-in-time: TRUE.
- Target-bar only: TRUE.
- Production context used: TRUE.
- Production emission authority: TRUE.
- Production-path mutation: FALSE.

## INCREASING_DEMAND interaction penalty study

A dedicated exact-subgroup study isolated the 212-event pure interaction.

Observed association:

- `UPTHRUST + BUYING_CLIMAX`: 66.15% positive decisive rate, +4.56% mean return.
- `+ INCREASING_DEMAND` pure subgroup: 56.87% positive decisive rate, +2.27% mean return.

A counterfactual study tested hypothetical deductions of 0.02, 0.04, 0.06, 0.08, and 0.10 from the professional SUPPLY score for only the 212 pure interaction events.

Counterfactual result:

- 0.00 penalty: no score change and no rank change.
- 0.02 penalty: 212 supply scores changed; 222 rank positions changed.
- 0.04 penalty: 212 supply scores changed; 259 rank positions changed.
- 0.06 penalty: 212 supply scores changed; 275 rank positions changed.
- 0.08 penalty: 212 supply scores changed; 276 rank positions changed.
- 0.10 penalty: 212 supply scores changed; 279 rank positions changed.

However, under the current production scoring formula, reducing SUPPLY score moves the interaction group's net_strength toward zero rather than making it weaker. Therefore this hypothetical penalty is directionally opposite to the intended effect of a penalty.

## Frozen production decision

- UPTHRUST remains production-active.
- No global UPTHRUST weight change.
- No explicit `INCREASING_DEMAND` interaction penalty.
- No new rejection rule.
- No qualification change.
- No actionability change.
- The weaker `UPTHRUST + INCREASING_DEMAND` relationship remains diagnostic evidence for future calibration.
- Future tuning must avoid double-counting an interaction already represented by the professional scoring model.

## Final status

Production wiring and semantic correctness are PASS.
Standalone decision value is currently negative versus the eligible market.
The `INCREASING_DEMAND` overlap is a material empirical relationship but remains study-only.
