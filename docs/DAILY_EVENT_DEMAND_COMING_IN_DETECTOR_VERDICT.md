# M12 — DEMAND_COMING_IN Detector Verdict

## Status

**PARKED — current detector semantics retained and frozen.**

This is a detector-layer verdict only.

It does not promote or recalibrate scoring, contextual suppression, qualification,
DailyBehavior, or actionability.

## Stop-rule review

### 1. Is the semantic contract correct?

Yes for the current role.

Production identity:

```text
Bullish Bar
High Volume
Above Average Spread
Strong Close
```

This is coherent as bullish effort/result evidence showing demand entering with
a strong bar result.

The detector does not claim a complete reversal sequence, structural breakout,
or accumulation state. It records one current-bar demand observation.

Existing point-in-time semantic, production-path, interaction, temporal,
ranking, and qualification audits support retaining this identity.

### 2. Is it distinct from other detectors?

Yes.

The closest active demand detector is `INCREASING_DEMAND`.

Shared core:

```text
Bullish Bar
High Volume
Above Average Spread
```

Identity split:

```text
DEMAND_COMING_IN
    -> Strong Close

INCREASING_DEMAND
    -> Volume Increasing
```

Therefore the two events represent different observations:

- `DEMAND_COMING_IN`: strong bullish result / acceptance on the bar;
- `INCREASING_DEMAND`: increasing effort / demand pressure.

They may overlap, but they are not semantic aliases and do not have identical
mandatory contracts.

### 3. Are confirmations behaving as intended?

There is no separate confirmation list for `DEMAND_COMING_IN`.

All four clauses are mandatory identity requirements.

Therefore the shared non-gating confirmation behavior does not create ambiguity
for this detector.

### 4. Is there an obvious correction?

No production detector correction is justified.

Existing audit policy already concludes:

```text
emission semantic change = NO
rejection rule           = NO
qualification change     = NO
actionability change     = NO
```

The existing contextual suppression behavior and the frozen provisional
`0.38` scoring/integration weight are separate policy layers. They are not a
reason to change detector identity.

The only obvious correction in this M12 pass is documentation accuracy:
the event now lives in `evidence/demand_coming_in.py`, not
`evidence/demand.py`.

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
current evidence. It does **not** mean the detector is disabled.

## Scoring / actionability boundary

Detector correctness remains separate from downstream policy.

Current downstream state remains:

```text
runtime emitted weight    0.38
scoring status            FROZEN PROVISIONAL
contextual suppression    existing production policy
general promotion         NO
```

Those policies must not be used to reopen detector semantics by default.

## Reopening rule

Reopen `DEMAND_COMING_IN` detector semantics only for:

1. independent out-of-sample evidence showing a contract defect;
2. a first-principles semantic contradiction;
3. a newly discovered causal/look-ahead defect;
4. a demonstrated detector collision that current semantics do not explain.

Do not reopen it merely to retune weights, subgroup outcomes, or actionability.

## Architecture boundary

`DEMAND_COMING_IN` remains one evidence item inside the larger progression
model.

It should contribute to the evolving supply/demand story; it should not become
a standalone trade trigger or a textbook-label prerequisite.
