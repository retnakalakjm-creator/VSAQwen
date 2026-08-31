# Professional Scoring Audit

## Status

**State:** AUDIT IN PROGRESS

**Scope:** Professional scoring → qualification → final candidate decision.

## 1. Current production scoring contract

`ProfessionalScoringEngine` currently produces four direct category/context scores:

- trend
- supply
- demand
- effort

It then derives strength, weakness, and confidence from those scores.

Supply and demand evidence are scored by category-specific weight maps. Each category score is capped at `1.0`.

`net_pressure = demand - supply`.

`net_strength = strength - weakness`.

The scanner separately uses directional VSA evidence for qualification and contradiction checks.

## 2. Current directional-role finding

The scanner recognizes a broader set of directional VSA events than the professional scoring maps currently weight.

This is **not automatically a defect**. It represents two different roles that must remain explicit:

```text
PROFESSIONAL-SCORED EVENT
    contributes to supply/demand pressure

CONFIRMATION-ONLY EVENT
    can confirm or contradict direction
    but contributes zero direct pressure weight
```

### Bullish

| Role | Events |
|---|---|
| Scored | `STOPPING_VOLUME`, `SHAKEOUT` |
| Confirmation-only | `DEMAND_COMING_IN`, `INCREASING_DEMAND`, `HIDDEN_DEMAND`, `DEMAND_DRYING_UP`, `NO_SUPPLY`, `SPRING`, `TEST`, `SELLING_CLIMAX` |

### Bearish

| Role | Events |
|---|---|
| Scored | `BUYING_CLIMAX`, `UPTHRUST`, `SUPPLY_COMING_IN`, `INCREASING_SUPPLY`, `SUPPLY_DRYING_UP`, `NO_DEMAND` |
| Confirmation-only | `HIDDEN_SUPPLY`, `SUPPLY_HIGH_VOLUME`, `SUPPLY_WIDE_SPREAD`, `SUPPLY_ABSORPTION` |

## 3. Why this matters

A confirmation-only event can make a candidate directionally actionable while adding no direct contribution to `net_pressure` or `net_strength` through the professional supply/demand maps.

That can be correct when an event is intentionally contextual, provisional, or reserved for another decision layer. It is incorrect only when the event is expected to contribute to professional pressure but has been omitted from the scoring contract.

Therefore no weight promotion should occur until the role of each event is empirically justified.

## 4. Qualification interaction

The scanner currently applies additional decision gates after professional scoring:

1. persistent structural qualification;
2. current or recent directional VSA evidence;
3. maximum actionable VSA age of 3 bars;
4. contradiction detection;
5. clean directional support when no contradiction exists.

Thus professional score and actionability are intentionally not identical concepts.

## 5. Audit findings so far

- Low-level professional scorer behavior is covered by existing scorer tests.
- Structural qualification behavior is covered by existing qualification tests.
- Scanner-level freshness and contradiction behavior is covered by `test_scanner_decision_contract.py`.
- Directional confirmation versus professional-weight membership is now explicitly tested by `test_professional_scoring_contract.py`.

No scoring weights or formulas have been changed as part of this audit.

## 6. Next audit step

Evaluate the confirmation-only events against point-in-time outcomes and determine whether each should remain contextual or be promoted into professional scoring.

Promotion requires decision-value evidence, not merely a numerical score change.

The study must also examine whether current `net_strength`, `net_pressure`, and `confidence` behave coherently with qualification and contradiction outcomes.

## 7. Audit harness requirements

Before committing any future audit/debug harness, verify:

- loop structure;
- data-loading and replay count;
- production-path consistency;
- imports;
- obvious object/API mismatches;
- deterministic behavior;
- no hidden look-ahead.

Performance changes remain secondary to decision quality for this audit.
