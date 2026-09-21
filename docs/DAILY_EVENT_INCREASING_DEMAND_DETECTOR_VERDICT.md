# M12 — INCREASING_DEMAND Detector Verdict

## Status

**PARKED — current detector semantics retained and frozen.**

This is a detector-layer verdict only.

It does not promote or recalibrate scoring, conflict penalties, qualification,
DailyBehavior, or actionability.

## Stop-rule review

### 1. Is the semantic contract correct?

Yes for the current role.

Production identity:

```text
Bullish Bar
High Volume
Above Average Spread
Volume Increasing
```

This is coherent as increasing bullish effort / demand pressure evidence.

The detector does not claim a completed reversal or structural acceptance event.
It records increasing demand effort on a bullish result bar.

Existing point-in-time semantic, production-path, interaction, decision-impact,
and robustness audits already support retaining this identity.

No new semantic replay is justified without independent evidence.

### 2. Is it distinct from other detectors?

Yes.

The closest active demand detector is `DEMAND_COMING_IN`.

Shared core:

```text
Bullish Bar
High Volume
Above Average Spread
```

Identity split:

```text
INCREASING_DEMAND
    -> Volume Increasing

DEMAND_COMING_IN
    -> Strong Close
```

Therefore the two detectors represent different observations:

- `INCREASING_DEMAND`: increasing effort / pressure;
- `DEMAND_COMING_IN`: strong bullish result / acceptance on the bar.

They may overlap on some bars, but they are not semantic aliases and do not have
identical mandatory contracts.

### 3. Are confirmations behaving as intended?

There is no separate confirmation list for `INCREASING_DEMAND`.

All four clauses are mandatory identity requirements.

Therefore the shared non-gating confirmation behavior does not create ambiguity
for this detector.

### 4. Is there an obvious correction?

No production detector correction is justified.

Existing audit conclusions already say:

```text
emission semantics change = NO
rejection rule            = NO
qualification change      = NO
actionability change      = NO
```

The previously studied `0.10` conflict penalty is a scoring-policy question,
not a detector-contract correction, and remains provisional / inactive.

## Detector-layer decision

```text
semantic contract      RETAIN
distinctness           PASS
confirmation issue     NONE
obvious correction     NONE

M12 detector status    PARKED
detector semantics     FROZEN
production emission    UNCHANGED
```

This means "parked" under the M12 stopping rule: no more detector-specific
research unless there is new independent evidence or a first-principles reason
to change the event definition.

It does **not** mean the production detector is disabled.

## Scoring boundary

Detector correctness and scoring policy remain separate.

Current production-connected state remains:

```text
runtime/base weight    0.85
conflict penalty       0.10 provisional / NOT ACTIVE
```

Any future scoring recalibration must be justified independently and must not
reopen detector semantics by default.

## Reopening rule

Reopen `INCREASING_DEMAND` detector semantics only for:

1. independent out-of-sample evidence showing a contract defect;
2. a first-principles semantic contradiction;
3. a newly discovered causal/look-ahead defect;
4. a demonstrated detector collision that current semantics do not explain.

Do not reopen it merely to retune outcomes, weights, or subgroup performance.

## Architecture boundary

`INCREASING_DEMAND` remains one evidence item inside the larger progression
model.

It should contribute to the evolving supply/demand story; it should not become
a standalone trade trigger or a textbook-label prerequisite.
