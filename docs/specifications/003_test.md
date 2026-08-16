# TEST Event Specification

This is the canonical event specification for the VSA `TEST` event.

`TEST` is production-integrated as a **non-scoring contextual confirmation event**. This specification defines the frozen VSA semantics and current validation record; it does not independently change scoring or scanner actionability.

## Frozen semantic definition

> **TEST is a low-effort probe after meaningful recent selling pressure. It establishes an observation, not proof of demand control. Its meaning comes from the combined context and later validation rather than from a textbook-perfect single-bar pattern.**

## Mandatory event evidence

The current production event requires:

1. Recent meaningful selling campaign / selling pressure.
2. Bearish/down current bar.
3. Low VSA volume.
4. Narrow VSA spread.

These conditions define the event itself.

## Non-mandatory confirmations

The detector may evaluate the following as supporting evidence:

- volume decreasing;
- higher low;
- strong or otherwise acceptable close;
- supply drying or related contextual evidence.

These observations are **confirmations, not mandatory emission gates**.

## Structural and contextual interpretation

Structural location is contextual rather than mandatory. A TEST does not have to occur exactly at a recent structural low.

A persistent confirmed downtrend or materially bearish structural context should weaken interpretation rather than automatically invalidate every TEST. This preserves realistic market behavior while preventing a TEST from being interpreted as demand dominance without supporting evidence.

## Effort/result interpretation

A preceding effort/result sequence may be informative, but it is not a mandatory prerequisite. The detector must not be forced into a rigid textbook sequence such as:

```text
high effort -> weak result -> TEST
```

The TEST remains a low-effort probe whose meaning depends on the broader VSA context.

## What TEST must not claim

A `TEST` event alone must not imply:

- confirmed accumulation;
- confirmed demand dominance;
- successful support;
- immediate bullish continuation;
- or a trade entry.

Those conclusions belong to downstream contextual qualification, persistence, and actionability logic.

## Point-in-time validation record

The optimized production audit validated the current TEST semantics across the eight-symbol universe:

- events: `47`;
- symbols with events: `8 / 8`;
- positive 8-bar outcomes: `27`;
- negative 8-bar outcomes: `14`;
- flat outcomes: `6`;
- decisive outcomes: `41`;
- positive decisive rate: `65.85%`;
- leave-one-symbol-out positive decisive rate: `62.86%–69.44%`;
- low-effort probes: `47 / 47`;
- meaningful selling context: `47 / 47`;
- persistent-downtrend contradictions: `0 / 47`;
- forward-data failures: `0`;

The result is robust enough for production integration, while the event remains contextual and non-scoring.

## Interaction policy

The interaction audit identified same-bar and nearby overlaps, including `NO_SUPPLY` and supply-side evidence. These interactions are retained as context and do not currently justify a blanket TEST rejection rule.

A future validation campaign may justify additional contextual quality adjustments, but no such gate is frozen by this specification.

## Scoring status

`TEST` remains **non-scoring**.

No independent production weight is assigned to TEST. Its contribution is contextual: it can support interpretation of demand-side reversal/continuation structures but does not itself create demand control.

## Production constraints

The production implementation must preserve these constraints:

- detection is point-in-time;
- no future response data is used to decide whether TEST emits;
- supporting confirmations remain non-mandatory;
- contextual contradictions weaken interpretation rather than automatically deleting realistic TEST observations;
- the event does not independently create trade actionability.

## Current status

**Status: Production — contextual confirmation**

**Scoring: Non-scoring**

**Role: Primary confirmation event**

**Direction: Bullish / demand-side context**
