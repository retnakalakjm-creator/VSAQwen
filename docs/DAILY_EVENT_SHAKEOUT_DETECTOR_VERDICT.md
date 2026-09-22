# M12 — SHAKEOUT Detector Verdict

## Status

**PARKED — current recovery-anchored detector semantics retained and frozen.**

This is a detector-layer verdict only.

It does not alter thresholds, weights, scoring, DailyBehavior, qualification,
actionability, alerts, or orders.

## Stop-rule review

### 1. Is the semantic contract correct?

Yes, for the currently validated production contract.

Candidate identity:

```text
Selling pressure / campaign present
Bearish / down bar
Wide spread
Very high volume
Lower low versus previous bar
```

Sequence validation:

```text
candidate
    ->
valid low-effort test
    ->
valid recovery
    ->
emit SHAKEOUT on the recovery bar
```

A strong candidate-bar close is not mandatory.

The production event is delayed-recognition evidence. It is not emitted on the
original candidate bar.

### 2. Is it distinct from other detectors?

Yes.

`SELLING_CLIMAX` and `STOPPING_VOLUME` are current-bar observations.

`SHAKEOUT` requires a completed multi-stage sequence:

```text
high-effort lower-low candidate
+
later low-effort test
+
later bullish recovery
```

Therefore a SHAKEOUT is not merely a high-volume bearish bar.

Its candidate can resemble `SELLING_CLIMAX` or `STOPPING_VOLUME`, but the
event identity is the later confirmed sequence and the evidence is anchored to
the recovery bar.

### 3. Is recognition / confirmation behavior correct?

Yes.

Production causality is explicitly point-in-time:

- candidate campaign context is reconstructed through the candidate bar;
- candidate structural swings are limited to swings confirmed by the candidate;
- validation metrics are sliced through the current bar;
- test/recovery search cannot see beyond that slice;
- emission requires `recovery_index == current_index`;
- evidence is attached to the recovery bar with `test_index` and
  `recovery_index`.

The historical recovery-anchor replay verified:

```text
validated events          18
candidate-bar emissions    0
recovery-bar emissions    18
correct recovery anchors  18
failures                   0
```

No look-ahead defect is present in the current recovery-anchored path.

### 4. Is there an obvious correction?

No production detector correction is justified.

One documentation mismatch was found in the canonical specification.

The specification stated that production recovery additionally requires:

```text
minimum recovery up-bars
minimum recovery strong closes
```

Current production `_validate_shakeout_recovery()` does not use those count
thresholds. The historical 18-event semantic and recovery-anchor audits were
also built on `validate_shakeout()`, so the validated production contract is
the current single qualifying recovery-bar rule.

Turning the legacy count settings into mandatory gates now would create a new,
unaudited detector population.

Therefore M12 corrects the specification, not production code.

## Validated recovery rule

After a valid test, production scans the configured recovery window and accepts
the first bar satisfying all of:

```text
bullish/up direction
close position >= SHAKEOUT_RECOVERY_MIN_CLOSE_POSITION
close > test close
low >= test low
```

The recovery-quality function then describes the quality of that valid
recovery. Quality affects emitted runtime weight but is not an additional
recognition gate.

## Legacy configuration boundary

These settings currently remain present in `config.py`:

```text
SHAKEOUT_RECOVERY_MIN_UP_BARS
SHAKEOUT_RECOVERY_MIN_STRONG_CLOSES
```

They are not consumed by the validated production recovery detector.

M12 leaves them untouched because removing or activating configuration is a
separate cleanup/semantic-change decision. They must not be interpreted as
current production gates.

## Detector-layer decision

```text
semantic contract      RETAIN
distinctness           PASS
recovery causality     PASS
obvious detector fix   NONE

M12 detector status    PARKED
detector semantics     FROZEN
production emission    UNCHANGED
```

"PARKED" means no further detector-specific calibration is justified under the
current evidence.

## Weight boundary

Current layers remain distinct:

```text
registry/profile weight        = 1.00
professional demand-map weight = 0.50
runtime Evidence.weight        = dynamic _shakeout_weight(ctx, quality)
```

M12 changes none of these.

## Reopening rule

Reopen SHAKEOUT detector semantics only for:

1. independent out-of-sample evidence showing a contract defect;
2. a first-principles contradiction in the candidate/test/recovery sequence;
3. a newly discovered causal/look-ahead defect;
4. a deliberate proposal to introduce a materially different recovery gate,
   followed by a new audit/replay cycle.

Do not reopen it merely to tune weight, quality, ranking, or interaction
subgroups.

## Architecture boundary

SHAKEOUT remains one recovery-confirmed observation inside the evolving
supply-demand story.

It should contribute evidence that aggressive selling was tested and then
rejected; it should not become a standalone trade trigger or mandatory
textbook-label prerequisite.
