# SPRING Decision Synthesis

## Status

`SPRING` is **production-integrated but remains provisional**. The existing Spring validation record is frozen; no new audit replay is authorized unless production semantics, scoring architecture, population contract, or an independent validation window materially changes.

## Frozen production semantics

`SPRING` is a bullish reversal/trap event built from four conceptual stages:

1. Structural support exists.
2. Price penetrates below support in a controlled, spread-normalized manner.
3. A low-effort test occurs after the break.
4. Bullish follow-through confirms recovery.

The detector is point-in-time and accepts imperfect but meaningful real-market VSA evidence without requiring textbook-perfect visual structure.

## Candidate / test / confirmation contract

Candidate filters:

```text
support touches       >= 2
candidate penetration <= 0.50 spread-normalized
```

Test filters:

```text
test distance       <= 1.00 spread-normalized
test penetration    <= 0.50 spread-normalized
test volume ratio   <= 0.75
test close position >= 2
```

A low-effort test and bullish confirmation remain required for production Spring qualification.

## Existing validated production evidence

Current production replay baseline:

```text
production Spring events = 13
symbols with events      = 6 / 8
POSITIVE_8_BAR            = 6
NEGATIVE_8_BAR            = 4
FLAT_8_BAR                = 3
failures                  = 0
```

The sample is explicitly considered too small for confident calibration.

## Current weight policy

```text
base production weight = 0.75
status                 = PROVISIONAL
weight promotion       = NO
weight tightening      = NO
```

The current evidence does not justify increasing the base weight or tightening the detector further.

## Conflict policy

A same-bar `UPTHRUST` or `BUYING_CLIMAX` is treated as a direct bearish contradiction to the bullish Spring interpretation.

The production policy is:

```text
Spring detected                  KEEP
normal quality                   1.00
same-bar bearish conflict quality 0.50
rejection                        NO
```

The conflict therefore changes evidence quality/confidence rather than acting as a hard rejection gate.

## Decision synthesis

`SPRING` should remain a **provisional production-integrated event at base weight 0.75**.

No production promotion is justified because the validated population contains only 13 events. No detector tightening is justified because the current semantics already enforce the key VSA sequence: structural support, controlled penetration, low-effort test, and bullish confirmation.

No hard rejection should be introduced for same-bar `UPTHRUST` or `BUYING_CLIMAX`; the existing quality reduction to `0.50` is the appropriate contextual treatment.

## Frozen production state

```text
production path        = YES
role                   = primary reversal / trap
base weight            = 0.75
runtime policy         = existing Spring evidence path
bearish conflict       = quality 0.50
rejection              = NO
qualification change   = NO
actionability change   = NO
status                 = PROVISIONAL
```

## Why no new audit is required now

The current canonical Spring specification already contains the validated semantics, production replay baseline, weight policy, and conflict policy. Replaying the same 13-event sample would not add decision value.

Future review is justified only if:

- production Spring semantics change;
- professional scoring architecture changes;
- the point-in-time candidate population contract changes;
- a materially larger independent validation population is introduced; or
- the conflict-quality mechanism itself changes.

## Real-market VSA constraint

The project deliberately allows imperfect but meaningful real-market VSA evidence. `SPRING` must remain faithful to the VSA sequence without being forced into a textbook-perfect Wyckoff drawing.
