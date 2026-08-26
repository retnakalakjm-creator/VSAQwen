# Effort vs Result Semantic Contract

## Status

**Design-frozen / analysis-only.** This document defines the canonical interpretation and production calculation contract. It does not enable `evidence/effort.py` invocation or introduce new scoring behavior.

## 1. Purpose

Effort vs Result is a cross-event analytical layer. It interprets the relationship between the market effort applied to a bar and the price result produced by that effort.

It is contextual evidence. It must not independently create, override, reject, or score an existing VSA event.

Historical audit evidence supports its use as contextual information, but does not justify a standalone numeric Effort/Result score.

## 2. Canonical VSA Semantics

### Effort

Effort represents the amount of market activity expressed through volume, interpreted relative to the historical baseline used by the metrics layer.

### Result

Result represents the price movement produced by that effort, expressed through spread/price-result measures relative to the same point-in-time baseline.

### Relationship

The relationship asks whether the observed effort is proportionate to the resulting price movement.

The canonical interpretation is:

- **High effort / low result:** substantial activity produced limited price progress. This is evidence of resistance, absorption, or lack of corresponding price response, depending on directional/contextual evidence. It is not itself an `ABSORPTION` event.
- **Low effort / high result:** substantial price progress occurred with comparatively little volume effort. This can be meaningful evidence of ease of movement, but requires context and must not be treated as an automatic bullish/bearish signal.
- **Normal effort / low result:** price response is weak relative to ordinary effort. Interpret only with directional, spread, close, trend, and event context.
- **Normal effort / high result:** price response is strong relative to ordinary effort. Interpret as supporting evidence, not as an independent event.
- **High effort / high result:** both effort and result are elevated. The relationship is not inherently bullish or bearish; directional result and existing VSA context determine interpretation.
- **Low effort / low result:** both are subdued. This is generally weak contextual information unless supported by other evidence.

## 3. Point-in-Time Contract

Effort and Result must use only information available at the target bar.

No future bars may contribute to:

- volume baseline
- spread/result baseline
- classification
- event interaction
- evidence strength or weight

Historical rolling/relative metrics must therefore be evaluated at the target bar's point in time.

## 4. Production Boundary

The production flow remains:

```text
point-in-time metrics
        ↓
Effort / Result relationship
        ↓
contextual evidence
        ↓
existing VSA events and structural context
        ↓
existing aggregation/scoring
```

Effort/Result must not:

- introduce `EFFORT_GT_RESULT` or `RESULT_GT_EFFORT` as standalone scoring signals merely because those codes already exist;
- create an event solely from the Effort/Result relationship;
- override an existing event;
- apply an interaction penalty without separate evidence and audit justification;
- bypass the existing evidence aggregation and professional scoring path.

## 5. Existing Implementation Boundary

`evidence/effort.py` currently contains detectors named `EFFORT_GT_RESULT`, `RESULT_GT_EFFORT`, and `ABSORPTION`. Their existence is not treated as the canonical semantic contract.

In particular, the current `ABSORPTION` detector is an implementation candidate, not proof that every high-effort/low-result observation is absorption.

Engine invocation remains disabled until the implementation is audited against this contract.

## 6. Historical Decision-Value Finding

The historical Effort/Result audit used point-in-time observations and forward horizons. The persistence screen retained combinations with at least 100 observations at both 2 and 4 bars.

The audit found 12 qualifying event-plus-relationship combinations, with 8 preserving the direction of their return delta at both horizons. This supports contextual decision value but does not justify a standalone score.

The observed duplicated `BUYING_CLIMAX` / `UPTHRUST` pattern is an existing event-layer characteristic and is not treated as new Effort/Result evidence.

## 7. Implementation Rule

Before production invocation is enabled, the Effort/Result implementation must be audited for:

1. point-in-time metric usage;
2. production-path consistency;
3. correct `BackgroundContext` / metrics API usage;
4. duplicate emission behavior;
5. interaction with existing evidence roles;
6. scoring-map behavior;
7. real-market imperfect-but-meaningful VSA evidence rather than textbook-only conformity.

Only after that audit may the engine invocation be considered for enablement.
