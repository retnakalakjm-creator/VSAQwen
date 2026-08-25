# Effort vs Result — Historical Audit Protocol

## Purpose

Define the historical audit required before Effort vs Result can influence production decisions.

This phase is observational only. It does not enable the Effort collector or introduce scoring.

## Audit population

Use completed historical bars from the same market/timeframe pipeline used by ProVSA.

The audit must preserve the original point-in-time metric values:

- `volume_ratio` → Effort
- `spread_ratio` → Result
- close position
- bar direction
- trend/background context
- existing VSA evidence

Do not recalculate a bar using future information.

## Measurements to record

For every audited bar record:

```text
week / timestamp
volume_ratio
spread_ratio
close_position
direction
trend context
existing VSA events
```

The relationship itself should remain continuous. At minimum record:

```text
Effort = volume_ratio
Result = spread_ratio
Effort / Result
```

The ratio is descriptive only and must not become a production score.

## Distribution audit

First establish how frequently the following naturally occur:

- high effort / low result
- high effort / normal result
- high effort / high result
- normal effort / low result
- low effort / high result
- low effort / normal result
- low effort / low result

Use the actual distributions rather than assuming textbook frequency or thresholds.

## Context audit

For each meaningful Effort/Result relationship, inspect the surrounding VSA context:

- trend direction/state
- recent supply/demand evidence
- market location
- spread character
- close character
- preceding bars
- subsequent bars only for **post-hoc evaluation**, never for calculating the original measurement

This separates what the bar objectively showed from what happened afterward.

## Existing-event interaction audit

Specifically examine relationships involving:

- `NO_DEMAND`
- `NO_SUPPLY`
- `STOPPING_VOLUME`
- `BUYING_CLIMAX`
- `SUPPLY_COMING_IN`
- `UPTHRUST`
- related contextual events

The question is not whether Effort/Result should automatically modify each event. The question is whether the relationship consistently adds independent information beyond the event's existing evidence.

## Decision-value test

An Effort/Result relationship should only progress toward production use if it demonstrates **incremental decision value**.

For each candidate relationship ask:

1. Does it occur often enough to matter?
2. Is the observation stable across different market conditions?
3. Does it add information not already captured by the existing event?
4. Does its interpretation remain valid when textbook candle structure is imperfect?
5. Does it improve contextual interpretation without creating contradictory evidence?
6. Does it remain point-in-time valid?

No production threshold should be selected merely because it produces attractive historical outcomes.

## Post-hoc outcome analysis

Future bars may be used only to evaluate whether an observed relationship had useful subsequent consequences.

They must never be used to construct or classify the original Effort or Result measurement.

Outcome analysis should remain descriptive during this phase. Avoid optimizing thresholds against historical outcomes.

## Audit conclusion categories

Each relationship should eventually be classified as one of:

- **Useful independent evidence** — adds meaningful information.
- **Context-dependent evidence** — useful only with defined contextual conditions.
- **Redundant evidence** — substantially duplicates existing VSA evidence.
- **Ambiguous evidence** — insufficiently stable for production use.
- **Not useful** — no meaningful decision value observed.

## Production gate

Effort vs Result remains disabled until:

```text
canonical semantics
        ↓
historical measurement audit
        ↓
context interaction audit
        ↓
decision-value audit
        ↓
production design decision
```

Only after that gate may the existing `evidence/effort.py` implementation be redesigned and its invocation considered for activation.
