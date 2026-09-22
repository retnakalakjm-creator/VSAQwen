# M12 — STOPPING_VOLUME Detector Verdict

## Status

**PARKED — current detector semantics retained and frozen.**

This is a detector-layer verdict only.

It does not alter weights, professional scoring, DailyBehavior, qualification,
actionability, alerts, or orders.

## Stop-rule review

### 1. Is the semantic contract correct?

Yes.

Production identity:

```text
Selling campaign
Bearish / down bar
High volume
Above-average spread
Close off the low
```

Diagnostic confirmations:

```text
Very high volume
Wide spread
Increasing volume versus previous bar
Higher low versus previous bar
```

This is coherent as stopping/absorption evidence: substantial selling effort is
present, but the bar does not finish with a weak/lower close.

The canonical specification and current source agree on all five mandatory
requirements.

### 2. Is it distinct from other detectors?

Yes.

The closest active detector is `SELLING_CLIMAX`.

`STOPPING_VOLUME`:

```text
selling campaign
bearish/down bar
high volume
above-average spread
close off low
```

`SELLING_CLIMAX`:

```text
selling campaign
bearish/down bar
very high volume
above-average spread
```

The contracts can overlap, but the semantic roles differ:

- `STOPPING_VOLUME` requires evidence that selling is being stopped/absorbed
  through the close-off-low result;
- `SELLING_CLIMAX` identifies climactic selling effort and does not require
  that close behavior.

Neither contract implies the other.

Historical interaction evidence treats same-bar overlap as confirming rather
than contradictory.

### 3. Are confirmations behaving as intended?

Yes.

`Very High Volume`, `Wide Spread`, `Increasing Volume`, and `Higher Low`
are diagnostic confirmations only.

Shared `evaluate_detector()` records the confirmation count but does not gate
emission on it.

That matches the canonical specification.

### 4. Is there an obvious correction?

No production-safe detector correction is justified.

The implementation is:

- current-bar / point-in-time;
- aligned with the canonical specification;
- distinct from `SELLING_CLIMAX`;
- free of a confirmation-gating defect;
- already validation-complete.

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

## Weight provenance

Current production source does not have a dedicated dynamic
`STOPPING_VOLUME` branch in `WeightCalculator.calculate()`.

It therefore follows the generic default:

```text
emitted Evidence.weight = 1.00
```

This aligns with:

```text
registry/profile weight              = 1.00
professional DEMAND_EVIDENCE_WEIGHTS = 1.00
```

The Primary VSA Event Matrix previously described the runtime weight as
dynamic. That wording is stale and is corrected by this M12 closure.

No weight value is changed in this PR.

## DailyBehavior boundary

`STOPPING_VOLUME` carries bullish evidence direction and contributes to:

```text
bullish weekly thesis
    ->
REJECTION_OF_OPPOSING_MOVE
    ->
STOPPING_VOLUME
```

This is consistent with its role as evidence that heavy selling is being
rejected or absorbed.

No DailyBehavior change is included.

## Reopening rule

Reopen `STOPPING_VOLUME` detector semantics only for:

1. independent out-of-sample evidence showing a contract defect;
2. a first-principles semantic contradiction;
3. a newly discovered causal/look-ahead defect;
4. a demonstrated identity collision that current semantics do not explain.

Do not reopen it merely to tune weight, confirmation frequency, ranking
influence, or interaction subgroups.

## Architecture boundary

`STOPPING_VOLUME` remains one evidence item inside the evolving supply-demand
story.

It should contribute evidence that selling pressure is being stopped or
absorbed; it should not become a standalone trade trigger or a mandatory
textbook-label prerequisite.
