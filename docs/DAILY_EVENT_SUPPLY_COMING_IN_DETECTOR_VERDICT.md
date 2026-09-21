# M12 — SUPPLY_COMING_IN Detector Verdict

## Status

**PARKED — current target-bar detector semantics retained and frozen.**

This is a detector-layer verdict only.

It does not change campaign logic, weights, evidence aggregation, DailyBehavior,
qualification, actionability, alerts, or orders.

## Stop-rule review

### 1. Is the semantic contract correct?

Yes for the current primary supply role.

Production identity:

```text
Buying campaign
Down / bearish bar
High volume
Above-average spread
Weak close
Volume increasing versus previous bar
```

This is coherent as evidence that supply is entering after a buying campaign:
selling result appears on a down bar while effort is elevated, spread is
meaningful, the close is weak, and volume expands versus the prior bar.

The existing semantic-quality audit found zero mandatory semantic failures in
the frozen production population.

### 2. Is it distinct from other detectors?

Yes.

The closest active detector is `INCREASING_SUPPLY`.

`SUPPLY_COMING_IN`:

```text
buying campaign
down bar
high volume
above-average spread
weak close
volume increasing
```

`INCREASING_SUPPLY`:

```text
down bar
volume increasing
spread increasing
```

The contracts share down-bar and increasing-volume evidence, but they represent
different observations:

- `SUPPLY_COMING_IN` requires absolute high-effort / weak-result supply inside
  a buying campaign;
- `INCREASING_SUPPLY` requires relative expansion of volume and spread versus
  the previous bar.

Neither contract implies the other.

The existing interaction audit found frequent overlap, but the overlap was
outcome-confirming rather than contradictory.

### 3. Are confirmations behaving as intended?

There is no separate confirmation list.

All six clauses are mandatory identity requirements and emission occurs only
when all six pass.

Therefore there is no confirmation-gating issue.

### 4. Is there an obvious correction?

No production-safe detector correction is justified.

The current target-bar implementation is:

- point-in-time under the canonical prefix/cached replay;
- mechanically aligned with the documented identity;
- distinct from neighboring supply detectors;
- already validated through production-path and interaction audits.

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

## Campaign-snapshot causality boundary

`collect_supply()` builds one `CampaignSnapshot` from the current
`BackgroundContext` and reuses it while iterating the recent bars in that
engine result.

For the canonical target-bar event replay, this is causal: the context is built
from a prefix ending at the target bar, and only evidence attributed to that
target bar is retained.

The same collection call can also contain older recent-bar evidence evaluated
using the current target's campaign snapshot. Whether that historical
reattribution should remain part of the broader evidence-history architecture
is a separate post-detector concern.

It is **not** used here to reopen the `SUPPLY_COMING_IN` target-bar identity or
to start another detector calibration cycle.

## Scoring boundary

Detector correctness remains separate from weighting policy.

Current documented values remain:

```text
registry/profile weight       = 1.00
empirical reference weight    = 0.38
production runtime weight     = dynamic
observed audit range          = 0.70–1.70
```

This M12 review does not reconcile or retune them.

## Reopening rule

Reopen `SUPPLY_COMING_IN` detector semantics only for:

1. independent out-of-sample evidence showing a contract defect;
2. a first-principles semantic contradiction;
3. a newly discovered target-bar causal/look-ahead defect;
4. a demonstrated detector identity collision that current semantics do not
   explain.

Do not reopen it merely to tune weights, ranking influence, or overlap
subgroups.

## Architecture boundary

`SUPPLY_COMING_IN` remains one event inside the evolving supply/demand story.

It should contribute evidence that active supply is appearing after a buying
campaign; it should not become a standalone trade trigger or a mandatory
textbook-label prerequisite.
