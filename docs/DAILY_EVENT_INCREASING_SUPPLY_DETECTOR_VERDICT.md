# M12 — INCREASING_SUPPLY Detector Verdict

## Status

**PARKED — current detector semantics retained and frozen.**

This is a detector-layer verdict only.

It does not recalibrate weights, alter evidence aggregation, change
DailyBehavior, qualification, actionability, alerts, or orders.

## Stop-rule review

### 1. Is the semantic contract correct?

Yes for the current role.

Production identity:

```text
Down / bearish bar
Volume increasing versus previous bar
Spread increasing versus previous bar
```

This is coherent as a relative-pressure observation: selling result is present
while both effort and price range expand versus the prior bar.

The existing semantic audit reproduced all three clauses with zero semantic
failures in its frozen population.

### 2. Is it distinct from other detectors?

Yes.

The closest active supply detector is `SUPPLY_COMING_IN`.

`INCREASING_SUPPLY`:

```text
down bar
volume increasing
spread increasing
```

`SUPPLY_COMING_IN`:

```text
buying campaign
down bar
high volume
above-average spread
weak close
volume increasing
```

The contracts share down-bar and increasing-volume evidence, but differ in the
core observation:

- `INCREASING_SUPPLY` is a relative expansion event;
- `SUPPLY_COMING_IN` is an absolute high-effort / weak-result supply event
  inside a buying campaign.

Neither contract implies the other because `SUPPLY_COMING_IN` does not require
spread increasing and `INCREASING_SUPPLY` does not require campaign context,
absolute high volume, above-average spread, or weak close.

The existing interaction audit found substantial overlap, but classified that
overlap as confirming rather than a semantic collision.

### 3. Are confirmations behaving as intended?

There is no separate confirmation list.

All three clauses are mandatory identity requirements and the detector emits
directly through `add_evidence()`.

Therefore there is no confirmation-gating issue.

### 4. Is there an obvious correction?

No production-safe detector correction is justified.

The current implementation is:

- current-bar / previous-bar only;
- point-in-time;
- mechanically aligned with the documented identity;
- distinct from neighboring supply detectors.

The existing audit did not justify a rejection rule, interaction penalty,
qualification change, actionability change, or production detector mutation.

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

## Scoring boundary

Detector correctness remains separate from scoring policy.

Current documented scoring concepts remain distinct:

```text
registry / empirical reference = 0.85
configured supply-map          = 0.70
runtime emitted weight         = 1.00 observed
```

This detector review does not reconcile or retune those values.

Any future scoring recalibration must be justified independently and must not
reopen detector semantics by default.

## Reopening rule

Reopen `INCREASING_SUPPLY` detector semantics only for:

1. independent out-of-sample evidence showing a contract defect;
2. a first-principles semantic contradiction;
3. a newly discovered causal/look-ahead defect;
4. a demonstrated detector identity collision that current semantics do not
   explain.

Do not reopen it merely to tune weights, ranking influence, or subgroup
performance.

## Architecture boundary

`INCREASING_SUPPLY` remains one evidence item inside the evolving
supply/demand story.

It should contribute evidence about increasing selling pressure; it should not
become a standalone trade trigger or a textbook-label prerequisite.
