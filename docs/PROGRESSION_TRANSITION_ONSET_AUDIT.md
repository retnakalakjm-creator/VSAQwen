# Progression Transition Onset Audit

## Purpose

K23 focuses on the 250 K22 events where progression direction was opposed to the
same-bar trend.

K22 showed that opposed progression behaves more like transition/reversal
evidence than aligned continuation evidence, but it does not summarize when the
reversal first appears or whether it persists.

K23 answers:

- when does actual reversal first appear?
- once reversal appears, does it persist across later usable horizons?
- does broader transition support persist even when actual reversal does not?
- how often is there no reversal at any studied horizon?

## Frozen input

K23 consumes only:

    progression_role_trajectory_summary.json
    progression_role_trajectories.csv

No market-data access or scanner replay occurs.

## Onset classes

    IMMEDIATE_1W
    EARLY_3W
    MEDIUM_5W
    LATE_10_15W
    NO_REVERSAL_TRANSITION_SUPPORT
    NO_REVERSAL_NO_SUPPORT

Actual reversal comes directly from the K22 ACTUAL_REVERSAL role.

Stable transition support is:

    ACTUAL_REVERSAL
    or
    CONSENSUS_DECELERATION

Window-sensitive deceleration is not counted as stable transition support.

## Persistence

Reversal persistence means every later usable horizon from first reversal onward
remains ACTUAL_REVERSAL.

Transition persistence allows either ACTUAL_REVERSAL or
CONSENSUS_DECELERATION after first stable transition support.

## Safety

Read-only and explicitly non-actionable.

K23 does not alter progression scoring, progression direction, qualification,
actionability, WeeklySetup materialization, daily behavior, alerts, execution,
or orders.
