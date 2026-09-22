# M12 — SELLING_CLIMAX Detector Verdict

## Status

**PARKED — current detector semantics retained and frozen.**

This is a detector-layer verdict only.

It does not alter weights, professional scoring, DailyBehavior, qualification,
actionability, alerts, or orders.

## Stop-rule review

### 1. Is the semantic contract correct?

Yes for the current primary reversal role.

Production identity:

```text
Selling campaign
Bearish / down bar
Very high volume
Above-average spread
```

Diagnostic confirmations:

```text
Wide spread
Strong close
Increasing volume versus previous bar
```

This is coherent as climactic selling effort after a decline. The mandatory
contract identifies exceptional selling effort; the confirmations describe
rejection/response quality without being required for the event to exist.

Historical audit work and post-integration production verification both passed
for this contract.

### 2. Is it distinct from other detectors?

Yes.

The closest event is `STOPPING_VOLUME`.

`SELLING_CLIMAX`:

```text
selling campaign
bearish/down bar
VERY_HIGH volume
above-average spread
```

`STOPPING_VOLUME`:

```text
selling campaign
bearish/down bar
HIGH volume
above-average spread
close off the low
```

Their roles differ:

- `SELLING_CLIMAX` identifies climactic selling effort;
- `STOPPING_VOLUME` identifies evidence that heavy selling is being stopped
  or absorbed, requiring a close off the low.

The contracts can overlap when a very-high-volume climax also closes off the
low, but neither contract implies the other.

Historical interaction evidence treated same-bar
`SELLING_CLIMAX + STOPPING_VOLUME` as confirming rather than contradictory.

### 3. Are confirmations behaving as intended?

Yes.

`Wide Spread`, `Strong Close`, and `Increasing Volume` are diagnostic
confirmations only.

Shared `evaluate_detector()` counts confirmations but does not gate emission
on them.

This matches the historical audit conclusion that textbook-perfect
confirmations should not be promoted into mandatory gates.

### 4. Is there an obvious correction?

No production-safe detector correction is justified.

The current implementation is:

- current-bar and point-in-time;
- mechanically aligned with the documented mandatory contract;
- distinct from `STOPPING_VOLUME`;
- already production-validated;
- free of a confirmation-gating defect.

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

Current production source does not emit a dynamic `SELLING_CLIMAX` weight.

`evidence.helpers.add_evidence()` explicitly assigns:

```text
SELLING_CLIMAX Evidence.weight = 0.38
```

This matches the existing post-integration production record:

```text
expected weight = 0.38
wrong weight    = 0
```

The Primary VSA Event Matrix previously described the runtime weight as
dynamic; that wording is stale and is corrected by this M12 closure.

No weight value is changed in this PR.

## DailyBehavior boundary

`SELLING_CLIMAX` carries bullish evidence direction and contributes to:

```text
bullish weekly thesis
    ->
REJECTION_OF_OPPOSING_MOVE
    ->
SELLING_CLIMAX
```

This is consistent with its role as reversal/rejection evidence after heavy
selling effort.

No DailyBehavior change is included.

## Reopening rule

Reopen `SELLING_CLIMAX` detector semantics only for:

1. independent out-of-sample evidence showing a contract defect;
2. a first-principles semantic contradiction;
3. a newly discovered causal/look-ahead defect;
4. a demonstrated identity collision that current semantics do not explain.

Do not reopen it merely to tune weight, ranking influence, confirmation
frequency, or interaction subgroups.

## Architecture boundary

`SELLING_CLIMAX` remains one evidence item inside the evolving supply-demand
story.

It should contribute evidence that selling effort has become climactic; it
should not become a standalone trade trigger or a mandatory textbook-label
prerequisite.
