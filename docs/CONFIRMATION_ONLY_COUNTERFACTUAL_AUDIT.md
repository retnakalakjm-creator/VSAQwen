# Confirmation-Only VSA Counterfactual Audit

## Status

**State:** PROVISIONAL — audit scaffold only.

This document records the first counterfactual layer for VSA events that currently participate in scanner confirmation but do not contribute directly to professional supply/demand pressure weights.

## Current production contract

The scanner maintains directional VSA confirmation sets independently from the professional supply/demand weight maps. Therefore an event may affect actionability without changing the professional pressure score.

This distinction is intentional and must remain explicit until empirical testing supports a production change.

## Current confirmation-only set

Bullish confirmation-only events:

- DEMAND_COMING_IN
- INCREASING_DEMAND
- HIDDEN_DEMAND
- DEMAND_DRYING_UP
- NO_SUPPLY
- SPRING
- TEST
- SELLING_CLIMAX

Bearish confirmation-only events:

- HIDDEN_SUPPLY
- SUPPLY_HIGH_VOLUME
- SUPPLY_WIDE_SPREAD
- SUPPLY_ABSORPTION

The production professional pressure maps currently score STOPPING_VOLUME and SHAKEOUT on the demand side, and BUYING_CLIMAX, UPTHRUST, SUPPLY_COMING_IN, INCREASING_SUPPLY, SUPPLY_DRYING_UP, and NO_DEMAND on the supply side.

## Counterfactual question

For each confirmation-only event:

```text
production evidence
        ↓
production decision
        ↓
remove confirmation-only event
        ↓
counterfactual decision
```

The initial audit verifies decision-contract stability and ensures that confirmation-only events do not accidentally acquire professional pressure weight.

## Important limitation

A genuine **decision-value** result requires future outcome labels, such as a fixed-horizon return/risk definition evaluated strictly after the decision bar.

Without those labels, this audit can measure:

- actionability changes;
- qualification changes;
- score changes;
- ranking changes;
- contradiction/freshness interaction changes;

but it cannot establish whether an event improves trading outcomes.

No production weight or qualification rule should be changed based on this scaffold alone.

## Validation requirements

Any future historical outcome study must verify:

- point-in-time replay;
- fixed decision timestamp/bar;
- no future-derived features in the predictor;
- deterministic replay count;
- production scoring path;
- identical baseline and counterfactual datasets;
- explicit outcome horizon and risk definition;
- sufficiently broad sample size;
- separation of exploratory calibration from production promotion.
