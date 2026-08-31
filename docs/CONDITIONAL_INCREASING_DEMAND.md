# Conditional `increasing_demand` Confirmation

## Decision

`increasing_demand` remains a valid VSA observation and remains **confirmation-only** for professional pressure scoring. It is not given a professional pressure weight and must not, by itself, upgrade a setup outside the validated market-structure context.

## Validated actionability behavior

The production gate treats `increasing_demand` by VSA code semantics rather than relying on the optional evidence-direction field.

When `increasing_demand` is the only bullish directional VSA evidence in the current scoring window, the candidate remains eligible for actionability only when:

1. Trend direction is `UP`.
2. Trend state is `HEALTHY`.
3. No opposing bearish directional VSA evidence is present.

The gate does **not** require positive professional demand-minus-supply pressure from `increasing_demand` itself, because the event is intentionally confirmation-only and has no professional pressure weight.

## Evidence supporting the rule

The 30-symbol historical audit initially showed unconditional `increasing_demand` upgrades (`False -> True`) underperformed matched controls across 3-, 5-, and 10-week horizons. Unique-control bootstrap testing preserved the negative point estimate, but the 95% intervals crossed zero, so this was treated as evidence for conservative conditioning rather than causal proof.

The post-gate outcome audit then showed that blocked cases were concentrated in correcting, exhausted, and healthy-downtrend contexts. The production gate therefore preserves healthy-uptrend `increasing_demand` while blocking the clearly conflicting structural contexts.

## Scope

This is a scanner actionability rule. It does not delete or reclassify the VSA observation, does not assign it professional pressure weight, and does not alter unrelated confirmation events.

## Validation status

This target is considered complete for the current scoring architecture. Future changes should be revalidated with the same universe, matched-control, robustness, and post-gate outcome methodology rather than tuned from isolated examples.
