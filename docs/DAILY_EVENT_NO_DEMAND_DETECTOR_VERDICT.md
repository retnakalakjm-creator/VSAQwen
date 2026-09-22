# M12 — NO_DEMAND Detector Verdict

## Status

**PARKED — current detector semantics retained and frozen.**

This is a detector-layer verdict only.

It does not recalibrate weights, alter professional scoring, change DailyBehavior,
qualification, actionability, alerts, or orders.

## Stop-rule review

### 1. Is the semantic contract correct?

Yes for the current role.

Production identity:

```text
Bullish environment
Bullish / up bar
Low volume
Narrow spread
```

Diagnostic confirmations:

```text
Volume decreasing versus previous bar
Weak close
```

The mandatory contract is coherent as a demand-absence observation: price
advances, but the move occurs with low effort and limited spread inside the
configured bullish environment.

The existing semantic audit reproduced all four mandatory clauses with zero
mandatory failures.

### 2. Is it distinct from other detectors?

Yes.

The closest active low-effort event is `SUPPLY_DRYING_UP`.

`NO_DEMAND`:

```text
bullish environment
up bar
low volume
narrow spread
```

`SUPPLY_DRYING_UP`:

```text
down bar
low volume
narrow spread
```

They share low-volume / narrow-spread evidence but describe opposite sides of
the supply-demand story:

- `NO_DEMAND` = an advance with insufficient buying interest;
- `SUPPLY_DRYING_UP` = a decline with insufficient selling pressure.

`HIDDEN_SUPPLY` is also distinct because it requires an up bar with **high**
volume and a lower close, rather than low-volume demand absence.

The inactive `DEMAND_DRYING_UP` concept is not a competing production
detector.

### 3. Are confirmations behaving as intended?

Yes.

`Volume Decreasing` and `Weak Close` are diagnostic confirmations only.
Shared `evaluate_detector()` records the confirmation count but does not gate
emission on it.

Therefore there is no confirmation-layer defect.

### 4. Is there an obvious correction?

No production-safe detector correction is justified.

The current implementation is:

- point-in-time;
- mechanically aligned with the documented four-clause identity;
- directionally consistent with bearish demand-absence evidence;
- distinct from neighboring active detectors;
- already validated through production-path and interaction audits.

## Detector-layer decision

```text
semantic contract      RETAIN
distinctness           PASS
confirmation behavior  PASS
obvious detector fix   NONE

M12 detector status    PARKED
detector semantics     FROZEN
production emission    UNCHANGED
```

"PARKED" means no further detector-specific research is justified under the
current evidence. It does **not** disable the production collector.

## DailyBehavior boundary

`NO_DEMAND` carries bearish evidence direction and contributes to:

```text
bearish weekly thesis
    ->
OPPOSING_PRESSURE_RECEDING
    ->
NO_DEMAND
```

This is consistent with its role: demand is absent/receding during an advance.

No DailyBehavior change is included.

## Scoring boundary

Detector correctness remains separate from weighting policy.

Current documented values remain:

```text
registry/profile weight       = 1.00
configured supply-map weight  = 0.60
runtime Evidence.weight       = dynamic
historically observed range   = 0.70–1.50
```

This M12 review does not reconcile or retune them.

## Documentation correction

An older audit summary once pointed to
`evidence/demand.py::_collect_no_demand`. The current audit record and current
source already use the correct collector:

```text
evidence/supply.py::_collect_no_demand
```

The central contract catalog still carried the obsolete note about the old path.
This M12 closure removes that stale description and records the corrected
provenance.

## Reopening rule

Reopen `NO_DEMAND` detector semantics only for:

1. independent out-of-sample evidence showing a contract defect;
2. a first-principles semantic contradiction;
3. a newly discovered causal/look-ahead defect;
4. a demonstrated identity collision that current semantics do not explain.

Do not reopen it merely to tune weights, ranking influence, confirmation
frequency, or interaction subgroups.

## Architecture boundary

`NO_DEMAND` remains one evidence item inside the evolving supply-demand story.

It should contribute evidence that buying interest is weak; it should not become
a standalone trade trigger or a mandatory textbook-label prerequisite.
