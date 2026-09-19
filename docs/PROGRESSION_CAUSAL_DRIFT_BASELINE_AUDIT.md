# Progression Causal Pre-Event Drift Baseline Audit

## Purpose

K19 tests whether K18's drift-adjusted progression lift survives when the control
baseline itself is causal and event-local.

K18 used same-symbol non-event weeks through the fixed study cutoff. That is useful
for descriptive drift normalization, but later control weeks were not known when
an earlier progression event occurred.

K19 removes that remaining concern.

## Frozen event input

K19 reuses the validated K15 event metadata and resolves every event by exact
event_week in the local completed-weekly history.

No scanner replay occurs.

## Causal control eligibility

For an event at weekly bar E and horizon H, a non-event control is eligible only
when:

    control signal bar is not a progression-event bar
    control outcome is complete
    control exit bar < E
    no progression event occurs anywhere from control signal through control exit

Therefore the entire control outcome was already known before the event.

Controls use the same direction and horizon as the event.

## Local windows

For every event/horizon K19 evaluates the most recent:

    26
    52
    104

eligible controls.

If fewer controls exist, all available eligible controls are retained and the
actual count is recorded.

This is a sensitivity analysis over roughly half-year, one-year, and two-year
weekly control depths without changing production logic.

## Lift

    event lift
    =
    recomputed event favorable return
    -
    causal pre-event control mean favorable return

K19 reports event-weighted and equal-weighted per-symbol results by:

- event direction;
- trend alignment;
- direction x trend alignment;
- horizon;
- control-window size.

## Safety

Read-only and non-actionable.

K19 does not modify progression scoring, progression direction, qualification,
scanner actionability, WeeklySetup materialization, daily coordination, alerts,
execution, or orders.
