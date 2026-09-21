# M12 — SUPPLY_DRYING_UP Detector Verdict

## Status

**PARKED — current detector semantics retained and frozen.**

This is a detector-layer verdict only.

It does not recalibrate weights, alter professional scoring, change DailyBehavior,
qualification, actionability, alerts, or orders.

## Stop-rule review

### 1. Is the semantic contract correct?

Yes for the current contextual role.

Production identity:

```text
Down / bearish bar
Low volume
Narrow spread
```

Production profile direction:

```text
EvidenceDirection.BULLISH
```

This is coherent as supply-exhaustion evidence: price is moving down, but the
decline occurs with weak effort and limited result.

The existing semantic audit reproduced all three clauses with zero mandatory
semantic failures.

### 2. Is it distinct from other detectors?

Yes, although it has an intentional nested relationship with `NO_SUPPLY`.

`SUPPLY_DRYING_UP`:

```text
down bar
low volume
narrow spread
```

`NO_SUPPLY`:

```text
environment-qualified context
down / bearish bar
low volume
narrow spread
diagnostic confirmations
```

Therefore:

- `SUPPLY_DRYING_UP` is the generic current-bar observation that selling
  pressure is drying up;
- `NO_SUPPLY` is the narrower named VSA interpretation that adds environment
  context.

The shared bar-pattern core is deliberate and does not make the detectors
semantic aliases.

The existing interaction audit observed same-bar `NO_SUPPLY` and `TEST`
overlaps without establishing a contradiction or detector correction.

### 3. Are confirmations behaving as intended?

`SUPPLY_DRYING_UP` has no separate confirmation list.

All three clauses are mandatory identity requirements and the detector emits
directly through `add_evidence()`.

Therefore there is no confirmation-gating issue.

### 4. Is there an obvious correction?

No production-safe detector correction is justified.

The current implementation is:

- current-bar only;
- point-in-time;
- mechanically aligned with the documented identity;
- directionally consistent with supply-exhaustion interpretation;
- distinct from neighboring detectors by role and contextual scope.

The existing audit did not justify a rejection rule, interaction penalty,
qualification change, actionability change, or detector mutation.

## Detector-layer decision

```text
semantic contract      RETAIN
distinctness           PASS
confirmation issue     NONE
obvious detector fix   NONE

M12 detector status    PARKED
detector semantics     FROZEN
production emission    UNCHANGED
```

"PARKED" means no further detector-specific research is justified under the
current evidence. It does **not** disable the production collector.

## Direction / architecture boundary

`SUPPLY_DRYING_UP` belongs to the supply category but carries bullish evidence
direction because it describes **receding opposing pressure**, not increasing
bearish pressure.

That is consistent with the DailyBehavior mapping:

```text
bullish weekly thesis
    ->
OPPOSING_PRESSURE_RECEDING
    ->
SUPPLY_DRYING_UP
```

This detector review does not change the separate professional supply-map
weighting architecture.

Current scoring references remain:

```text
registry/profile weight       0.90
configured supply-map weight  0.60
runtime emitted weight        1.00 observed in prior audit
```

Any future scoring cleanup must be handled independently and must not reopen the
detector identity by default.

## Reopening rule

Reopen `SUPPLY_DRYING_UP` detector semantics only for:

1. independent out-of-sample evidence showing a contract defect;
2. a first-principles semantic contradiction;
3. a newly discovered causal/look-ahead defect;
4. a demonstrated identity collision that the current contextual distinction
   cannot explain.

Do not reopen it merely to tune weights, ranking influence, or interaction
subgroups.

## Architecture boundary

`SUPPLY_DRYING_UP` remains one contextual observation inside the evolving
supply/demand story.

It should contribute evidence that selling pressure is receding; it should not
become a standalone trade trigger or a mandatory textbook-label prerequisite.
