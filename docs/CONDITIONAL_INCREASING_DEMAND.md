# Conditional `increasing_demand` Confirmation

## Decision

`increasing_demand` remains a valid VSA observation and remains **confirmation-only** for professional pressure scoring. It must not, by itself, upgrade a structurally qualified setup into an actionable decision.

## Actionability gate

When `increasing_demand` is the only bullish directional VSA evidence in the current scoring window, the confirmation can support actionability only when all of the following hold:

1. Trend direction is `UP`.
2. Trend state is `HEALTHY`.
3. Professional demand-minus-supply pressure is strictly positive.
4. There is no opposing bearish directional VSA evidence.

When these conditions are not met, professional confidence is forced to zero for that candidate, which prevents actionability without changing the underlying VSA evidence or its professional pressure weights.

## Why

The 30-symbol audit showed that unconditional `increasing_demand` upgrades (`False -> True`) underperformed matched controls across 3-, 5-, and 10-week horizons. The effect was consistently negative but bootstrap intervals crossed zero, so the implementation is intentionally conservative rather than treating the audit as causal proof.

The rule therefore preserves the VSA observation while requiring agreement from market structure and professional pressure before it can influence actionability.

## Scope

This is a scanner actionability rule. It does not delete, reclassify, or assign a professional pressure weight to `increasing_demand`, and it does not alter unrelated VSA confirmation events.
