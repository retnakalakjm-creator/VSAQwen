# Progression Role Horizon-Trajectory Audit

## Purpose

K22 removes the final repeated-observation layer from the progression semantic
study.

K21 produces one consensus role for each:

    progression event x forward horizon

The same underlying event therefore still appears at:

    1 week
    3 weeks
    5 weeks
    10 weeks
    15 weeks

These are outcome trajectories, not independent progression events.

K22 collapses them into one row per progression event while preserving the exact
five-horizon role path.

Expected full-basket reduction:

    2,955 K21 event-horizon rows
    -> 591 event-level trajectory rows

## Trajectory contract

Every event must contain exactly:

    1, 3, 5, 10, 15 weeks

K22 records:

- exact horizon-to-role signature;
- usable and window-robust horizon counts;
- actual-reversal horizons;
- consensus and window-sensitive deceleration counts;
- failed counter-trend counts;
- continuation-outperform / weaker / failed counts;
- neutral and incomplete counts.

## Majority summaries

For descriptive comparison only, K22 records whether at least three of the five
study horizons support:

- actual reversal;
- transition evidence (actual reversal + consensus deceleration);
- continuation outperformance;
- continuation failure.

These are audit summaries, not production thresholds. Incomplete recent events
cannot satisfy majority with only one or two observed horizons.

## Signatures

K22 also counts exact five-horizon role signatures by event direction and trend
alignment. This lets the study distinguish persistent reversal trajectories from
late reversal, transient reversal, persistent failure, and mixed paths without
inventing a production semantic rule.

## Safety

Read-only and explicitly non-actionable.

K22 does not change progression scoring, direction mapping, qualification,
actionability, WeeklySetup materialization, daily behavior, alerts, execution,
or orders.
