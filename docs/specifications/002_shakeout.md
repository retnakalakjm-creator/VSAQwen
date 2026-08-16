# SHAKEOUT — Production Specification

## Status

**Production-integrated — replay verified**

Configured base demand weight: **0.50**

Validated recovery-anchored sample: **18 events across 8 symbols**

## Semantic definition

> **A SHAKEOUT is a bullish reversal event in which meaningful selling pressure drives price to a lower low on unusually high effort and a wide spread, followed by a valid low-effort test and confirmed recovery. The production event is emitted at the confirmed recovery bar, not at the original candidate bar.**

The implementation intentionally supports imperfect real-market examples. A textbook-perfect candidate close is not required. The later test and recovery carry the confirmation meaning.

## Point-in-time sequence

```text
candidate
    ↓
validated TEST
    ↓
validated recovery
    ↓
SHAKEOUT evidence emitted at recovery bar
```

All candidate, test, and recovery validation uses only information available through the recovery bar.

## Candidate semantics

The candidate must satisfy:

1. Down direction.
2. Very-high volume class or higher.
3. Wide spread class or higher.
4. Bearish price action.
5. Meaningful selling pressure / campaign context.
6. Lower low relative to the previous bar.

A strong candidate-bar close is **not** mandatory.

## Test and recovery

The existing point-in-time SHAKEOUT validator must produce:

- a valid low-effort TEST;
- a valid recovery;
- recovery within the configured recovery lookahead;
- the configured minimum recovery up-bars;
- the configured minimum recovery strong-close condition;
- required recovery close-position quality.

Configured recovery parameters are defined in `config.py`:

```text
SHAKEOUT_TEST_LOOKAHEAD = 15
SHAKEOUT_TEST_MAX_DISTANCE_RATIO = 0.05
SHAKEOUT_TEST_MAX_PENETRATION_RATIO = 0.10
SHAKEOUT_TEST_MAX_VOLUME_RATIO = 1.00
SHAKEOUT_TEST_MAX_SPREAD_RATIO = 1.00
SHAKEOUT_TEST_MIN_CLOSE_POSITION = 3
SHAKEOUT_RECOVERY_LOOKAHEAD = 5
SHAKEOUT_RECOVERY_MIN_UP_BARS = 3
SHAKEOUT_RECOVERY_MIN_STRONG_CLOSES = 1
SHAKEOUT_RECOVERY_MIN_CLOSE_POSITION = 3
SHAKEOUT_RECOVERY_SPREAD_TARGET = 0.75
SHAKEOUT_RECOVERY_VOLUME_TARGET = 0.75
SHAKEOUT_RECOVERY_CLOSE_CHANGE_TARGET = 0.10
SHAKEOUT_RECOVERY_LOW_CLEARANCE_TARGET = 0.25
```

## Validation record

Across the eight-symbol validation universe:

- confirmed SHAKEOUTs: **18**
- symbols with confirmed SHAKEOUTs: **7 / 8**
- positive 8-bar outcomes: **12**
- negative 8-bar outcomes: **6**
- flat outcomes: **0**
- decisive outcomes: **18**
- positive decisive rate: **66.67%**
- leave-one-symbol-out positive decisive rate range: **62.50%–70.59%**
- semantic-quality audit: **18 / 18** valid candidate/test/recovery sequences
- replay failures: **0**

## Interaction audit

Among the 18 confirmed events:

- same-bar conflicts: **1 / 18**
- nearby conflicts: **6 / 18**
- same-bar conflict: `NO_DEMAND`
- nearby conflicts: primarily `INCREASING_SUPPLY`, with one `SUPPLY_COMING_IN`

These interactions are treated as contextual quality information rather than hard rejection gates. The observed sample does not justify rejecting an otherwise valid SHAKEOUT solely because nearby supply evidence remains present.

## Weight decision

An event-specific counterfactual sweep from **0.50 through 1.00** produced the same directional beneficial/harmful classification at every tested weight: **12 beneficial / 6 harmful**.

Therefore the data supports the **directional usefulness of SHAKEOUT evidence**, but does not distinguish one higher weight from another.

The conservative production base weight is therefore fixed at:

```text
SHAKEOUT = 0.50
```

Dynamic evidence-quality/context adjustment may produce a final runtime evidence weight above or below the configured base weight.

## Production replay gate

The recovery-anchor replay was completed against the validated 18-event population:

```text
validated_events:       18
candidate_bar_emissions: 0
recovery_bar_emissions: 18
correct_recovery_anchors: 18
failures:                0
```

This verifies that the production detector reproduces the validated recovery-anchor population exactly and does not emit SHAKEOUT prematurely at the original candidate bar.

## Production rule

SHAKEOUT is now considered a **production-integrated demand-side primary reversal event**.

Future optimization should revisit thresholds or weight only with a new audit campaign and should not be based solely on the current 18-event sample.
