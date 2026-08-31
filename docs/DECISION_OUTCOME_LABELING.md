# Decision Outcome Labeling

## Status

**Type:** Audit-only methodology

**State:** PROVISIONAL

This document defines the future-outcome labels used for decision-value studies. It does not alter production scoring or qualification.

## Entry

The entry price is the closing price of the signal bar.

Only bars strictly after the signal bar may contribute to the outcome label.

## Horizon

A label with horizon `H` uses the next `H` bars, inclusive of the bar at `signal_index + H`.

If fewer than `H` future bars are available, the outcome is marked incomplete and no return/excursion values are produced.

## Forward return

Forward return is direction-adjusted:

```text
bullish = exit_close / entry_close - 1
bearish = -(exit_close / entry_close - 1)
```

Positive values therefore represent movement in the signalled direction.

## Maximum favorable excursion

For a bullish signal:

```text
max(high / entry - 1)
```

For a bearish signal:

```text
max(1 - low / entry)
```

MFE is reported as a non-negative magnitude.

## Maximum adverse excursion

For a bullish signal:

```text
max(1 - low / entry)
```

For a bearish signal:

```text
max(high / entry - 1)
```

MAE is reported as a non-negative magnitude.

## Point-in-time rule

The labeler is intentionally allowed to read future bars because it is an **outcome label**, not a production decision input. Future data must never flow backward into the scanner during the signal-generation replay.

## Decision-value study

The first counterfactual study should compare:

```text
baseline production decision
        vs
same decision with confirmation-only evidence removed
```

Outcome labels should then be compared by signal cohort using forward return, MFE, MAE, and sample count.

No production weight or qualification rule should be changed solely from this audit until the effect is consistent across suitable historical samples.
