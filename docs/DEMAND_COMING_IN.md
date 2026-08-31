# `DEMAND_COMING_IN` — Initial Audit-First Definition

## Status

`DEMAND_COMING_IN` is now implemented as an **audit-first detector**. It is not yet production-connected through `EvidenceEngine.collect()` and has no validated professional scoring weight or actionability rule.

## Initial VSA definition

The detector requires all four observations on the current bar:

- bullish/up bar
- high volume
- above-average spread
- strong close in the upper part of the range

These are treated as mandatory observations for the initial historical audit. No confirmation is used to weaken or strengthen the event at this stage.

## Relationship to `INCREASING_DEMAND`

`INCREASING_DEMAND` additionally requires volume to be increasing versus the previous bar. `DEMAND_COMING_IN` intentionally does not require that relationship, so the two observations remain distinct for audit purposes.

## Validation policy

The event must follow the same audit-first process used for previous VSA observations:

1. detector contract tests
2. historical candidate/event audit
3. large-universe audit
4. matched-control analysis
5. robustness analysis
6. conditional actionability study, only if the event demonstrates decision value

Until those stages are complete, the detector must not receive a new production weight or an actionability override.
