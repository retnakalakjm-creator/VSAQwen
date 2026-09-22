# TEST Event Specification

This is the canonical event specification for the VSA `TEST` event.

`TEST` is production-integrated as a **professional-non-scoring contextual confirmation event** with **M12 detector semantics frozen**. This specification defines the production identity and validation record; it does not independently change scoring or scanner actionability.

## Frozen semantic definition

> **TEST is a low-effort probe after meaningful recent selling pressure. It establishes an observation, not proof of demand control. Its meaning comes from the combined context and later validation rather than from a textbook-perfect single-bar pattern.**

## Mandatory event evidence

The current production event requires:

1. Recent meaningful selling campaign / selling pressure.
2. Bearish/down current bar.
3. Low VSA volume.
4. Narrow VSA spread.
5. No strong-downtrend contradiction: a confirmed downtrend is rejected when
   recent structural weakness is absent.

All five conditions are mandatory production identity.

## Non-mandatory confirmations

The detector evaluates the following formal confirmations:

- volume decreasing;
- strong close;
- higher low.

These observations are **diagnostic confirmations, not mandatory emission
gates**.

Supply drying and other same-bar/nearby VSA observations remain interaction
context rather than formal TEST detector confirmations.

## Structural and contextual interpretation

Structural location is contextual rather than mandatory. A TEST does not have
to occur exactly at a recent structural low.

Production does, however, enforce one audited contradiction gate: a confirmed
downtrend **without recent structural weakness** suppresses TEST emission.
A confirmed downtrend is not automatically disqualifying when recent structural
weakness is present.

Other materially bearish context remains interpretive evidence rather than an
additional blanket TEST gate.

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

`TEST` remains **non-scoring in ProfessionalScoringEngine demand pressure**.

`config.DEMAND_EVIDENCE_WEIGHTS` has no TEST entry, so TEST contributes
`0.0` to professional demand score.

The emitted evidence object still receives dynamic `Evidence.weight` metadata
through `WeightCalculator._test_weight(ctx)`. The current scanner does not use
that metadata as an independent professional demand-score contribution.

TEST can serve as bullish directional VSA confirmation for an already-qualified
structural setup. It does not create structural qualification or standalone
trade actionability by itself.

## Production constraints

The production implementation must preserve these constraints:

- detection is point-in-time;
- no future response data is used to decide whether TEST emits;
- the audited strong-downtrend/no-structural-weakness contradiction remains a mandatory gate;
- supporting confirmations remain non-mandatory;
- other contextual contradictions remain interpretation/interaction evidence unless separately promoted;
- the event does not independently create structural qualification or trade actionability.

## M12 detector closure

```text
semantic contract      RETAIN
distinctness           PASS
confirmation behavior  PASS
obvious detector fix   NONE

M12 detector status    PARKED
detector semantics     FROZEN
production emission    UNCHANGED
```

The canonical spec previously understated the mandatory contract by omitting
the audited strong-downtrend contradiction gate and used "non-scoring" without
distinguishing professional demand scoring from emitted weight metadata. M12
corrects those documentation points only.

See `docs/DAILY_EVENT_TEST_DETECTOR_VERDICT.md`.

## Current status

**Status: Production — contextual confirmation / M12 PARKED**

**Professional demand scoring: 0.0**

**Directional VSA confirmation: YES**

**Standalone qualification/actionability: NO**

**Role: Primary confirmation event**

**Direction: Bullish / demand-side context**
