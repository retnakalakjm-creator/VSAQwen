# Production Scoring / Ranking Milestone

## Scope

This milestone freezes the current production policy for the four previously provisional demand/effort events and establishes the regression gate for the production scanner.

## Frozen policy matrix

| Evidence | Production path | Professional scoring | Actionability / qualification | Conflict / rejection |
| --- | --- | --- | --- | --- |
| `DEMAND_COMING_IN` | YES | Runtime evidence weight `0.38` | No global promotion; `UP + CORRECTING` + bullish DCI is suppressed by the existing soft gate | No additional penalty; no hard rejection |
| `INCREASING_DEMAND` | YES | Confirmation-only; no professional demand weight | When it is the only bullish VSA evidence, actionable confidence is retained only in `UP + HEALTHY` with no bearish evidence | No separate rejection rule |
| `DEMAND_DRYING_UP` | NO | None | No production suppression/penalty | No production rule |
| `ABSORPTION` | YES | Runtime weight `0.00` | No validated ranking/actionability contribution | Hard rejection: NO; soft `0.20` penalty remains research-only |

## Decision basis

### `DEMAND_COMING_IN`

Keep the audited runtime weight at `0.38` as a frozen provisional production/integration value. The event has meaningful but not dominant ranking influence, and current evidence does not justify full actionability promotion or another weight change.

The corrected production ranking-impact audit is valid:

```text
symbols requested     = 8
symbols with results  = 8
target events         = 967
bias changes          = 198
bias change rate      = 20.48%
all emitted weights   = 0.38
failures              = 0
status                = PASS
```

This confirms that `0.38` is the actual emitted runtime weight and that DCI materially participates in ranking/bias calculation. It does not establish that a different weight is superior.

### `INCREASING_DEMAND`

Keep confirmation-only semantics. It must not become a professional pressure contributor. The validated production gate already limits its sole-bullish actionability to a healthy uptrend without opposing bearish evidence.

### `DEMAND_DRYING_UP`

Do not integrate into the production evidence path and do not add a production score, penalty, suppression rule, or rejection rule from the current evidence. Its negative incremental research result remains research-only because the detector is not emitted by the production evidence pipeline.

### `ABSORPTION`

Keep the detector production-connected but non-scoring at runtime weight `0.00`. The completed production-path counterfactual confirmed deterministic monotonic score sensitivity across tested nonzero weights, but no tested weight produced a scanner actionability gain or validated ranking benefit.

## Regression gate

Any future production-scoring change touching these codes must preserve:

1. `INCREASING_DEMAND` remains absent from the professional demand weight map.
2. `DEMAND_COMING_IN`, `INCREASING_DEMAND`, and `DEMAND_DRYING_UP` do not silently acquire professional demand pressure weights.
3. `ABSORPTION` remains `0.00` in the production effort weight map unless a new validated ranking/decision study explicitly authorizes promotion.
4. The existing `INCREASING_DEMAND` and `DEMAND_COMING_IN` gates remain intact.
5. ABSORPTION at zero weight cannot change professional effort score.
6. Full production scanner regression and ranking/actionability safety must pass before any scoring-policy promotion.

### Final regression result

The full repository regression suite has now passed:

```text
python -m pytest -q
210 passed
```

This establishes the current production scoring policy as regression-safe. It does not authorize a scoring promotion; promotion still requires new validated decision/ranking evidence.

## Status

```text
DEMAND_COMING_IN = FROZEN PROVISIONAL 0.38
INCREASING_DEMAND = FROZEN CONFIRMATION-ONLY
DEMAND_DRYING_UP = FROZEN RESEARCH-ONLY / NOT PRODUCTION-INTEGRATED
ABSORPTION = FROZEN PRODUCTION-CONNECTED / NON-SCORING 0.00

production regression gate = PASS (210 passed)
production scoring promotion = NOT AUTHORIZED
next gate                  = NEXT PRODUCTION MILESTONE
```
