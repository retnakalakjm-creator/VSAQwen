# Progression Role Window-Consensus Audit

## Purpose

K21 removes control-window repetition from K20.

K20 classified each event/horizon three times because K19 used 26, 52, and 104
causal control windows. Those rows are sensitivity views, not independent events.

K21 collapses them into one event x horizon consensus row.

Expected full-basket reduction:

    8,865 K20 rows
    -> 2,955 event x horizon consensus rows

## Consensus rules

The three control windows are:

    26
    52
    104

A baseline-dependent role needs a majority of windows:

    2 of 3

### Trend-opposed

Actual reversal depends only on realized event return and must therefore be
identical across windows.

If no actual reversal occurred:

    2/3 or 3/3 positive transition windows
    -> CONSENSUS_DECELERATION

    1/3 positive transition windows
    -> WINDOW_SENSITIVE_DECELERATION

    0/3 positive transition windows
    -> FAILED_COUNTERTREND_WARNING

### Trend-aligned

If realized continuation itself failed:

    -> CONTINUATION_FAILED

Otherwise:

    2/3 or 3/3 baseline-outperform windows
    -> CONSENSUS_CONTINUATION_OUTPERFORMS

    1/3 outperform windows
    -> WINDOW_SENSITIVE_CONTINUATION_OUTPERFORMANCE

    0/3 outperform windows
    -> CONTINUATION_WEAKER_THAN_BASELINE

## Robustness flag

Roles that are baseline-independent or unanimous across all windows are marked
robust_across_windows.

Majority-only and one-window-only roles remain explicitly window-sensitive.

## Safety

Read-only and non-actionable.

K21 does not change progression scoring, direction, qualification, actionability,
WeeklySetup materialization, daily behavior, alerts, execution, or orders.
