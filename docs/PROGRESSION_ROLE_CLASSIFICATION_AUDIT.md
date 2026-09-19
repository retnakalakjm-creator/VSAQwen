# Progression Role Classification Audit

## Purpose

K20 converts K19's causal lift results into an explicit semantic-role audit.

The question is no longer simply:

    bullish progression -> up?
    bearish progression -> down?

K19 indicates that the relationship to the already-observed trend matters more.

K20 therefore distinguishes:

    trend-opposed progression
    -> transition / early-warning hypothesis

    trend-aligned progression
    -> continuation hypothesis

## Trend-opposed roles

For a trend-opposed event:

### ACTUAL_REVERSAL

The realized forward return favors the progression-event direction.

### DECELERATION_WITHOUT_REVERSAL

The realized forward return does not reverse into the event direction, but it is
better for the event direction than the causal pre-event baseline.

This is interpreted only as relative deceleration / early-warning evidence.

### FAILED_COUNTERTREND_WARNING

No realized reversal and no positive causal lift.

## Trend-aligned roles

### CONTINUATION_OUTPERFORMS_BASELINE

Forward return favors the aligned event/trend direction and exceeds its causal
continuation baseline.

### CONTINUATION_WEAKER_THAN_BASELINE

Forward return still favors the aligned direction, but does not beat baseline.

### CONTINUATION_FAILED

Forward return does not favor the aligned direction.

## Input

K20 consumes frozen K19 artifacts:

    progression_causal_drift_summary.json
    progression_causal_drift_rows.csv

No scanner replay or market-data access is required.

## Output

K20 reports role counts/rates by:

- event direction;
- trend alignment;
- direction x trend alignment;
- horizon;
- K19 control window.

This keeps bullish/bearish asymmetry visible instead of collapsing it into one
overall role statistic.

## Safety

Read-only and explicitly non-actionable.

K20 does not modify progression scoring, direction, qualification, WeeklySetup
materialization, actionability, daily behavior, alerts, execution, or orders.
