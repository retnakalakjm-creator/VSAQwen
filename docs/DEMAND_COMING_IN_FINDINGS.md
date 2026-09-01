# DEMAND_COMING_IN Findings

Status: audit-complete; contextual suppression gate implemented and leakage-tested.

## Validated evidence

The 30-symbol NSE audit produced 2,046 unique matched target-control pairs.

Aggregate matched-control return delta:
- 3 weeks: +0.143%, 95% bootstrap interval -0.515% to +0.762%
- 5 weeks: +0.101%, 95% bootstrap interval -0.612% to +0.787%
- 10 weeks: +0.318%, 95% bootstrap interval -0.495% to +1.161%

These intervals cross zero, so the event does not have robust unconditional incremental return value.

## Context finding

The strongest regime was `correcting + bullish`:
- 3 weeks: -5.662%, 95% interval -10.477% to -2.023%
- 5 weeks: -4.653%, 95% interval -9.282% to -0.595%
- 10 weeks: -3.023%, 95% interval -6.076% to -0.008%

The negative effect is broad enough to justify treating this combination as a warning/suppressive context.

`healthy + bearish` showed a positive 10-week effect (+1.673%, 95% interval +0.011% to +3.402%), but the symbol-level audit was heterogeneous. It remains contextual evidence rather than a production directional weight.

## Symbol-level validation

The `correcting + bullish` negative effect was observed across multiple symbols, including materially negative 3/5-week results for SBIN, SUNPHARMA, TATASTEEL, LT, and TCS. The effect is therefore not dependent on a single symbol, although individual symbol buckets remain heterogeneous.

The `healthy + bearish` positive effect was heterogeneous at symbol level, with strong positive and strong negative contributors. It is not promoted to a directional production rule.

## Production policy

Do not promote `DEMAND_COMING_IN` to a general bullish score or unconditional actionability trigger.

Implemented contextual policy:

`correcting + bullish + DEMAND_COMING_IN` -> suppressive/negative professional confidence gate.

The production leakage audit across the 30-symbol universe found **0 actionable cases remaining after the gate**.

All other regimes remain evidence/context until additional validation supports promotion.
