# Daily Behavior Sequence Outcome Study

## Purpose

K1 records when existing daily behavior dimensions appeared. K2 attaches the
existing analysis-only forward-outcome contract so those observed temporal
relationships can be measured before any sequence is considered for promotion.

This is a research harness, not a production signal engine.

## Causal outcome contract

K2 reuses `audit.outcomes.compute_forward_outcome()`.

For a sequence observed on bar N:

```text
signal / fresh sequence bar = N
execution bar = N + 1
entry price = execution-bar close
horizon exit = execution bar + requested horizon
```

There is no same-bar execution.

## Fresh-sequence requirement

A bounded sequence can contain behavior whose latest supported step occurred
before its requested end bar. K2 does not score that stale snapshot.

An outcome is attached only when:

```text
at least one sequence step.bar_index == sequence.end_bar_index
```

This prevents retrospectively observing a sequence on a later bar and then
crediting returns that began before that later observation existed.

## Sequence identity

Exact study cohorts use relative temporal offsets from the signal bar.

Example:

```text
-2 bars: opposing pressure receding
 0 bars: aligned pressure emerging
```

The same relative pattern can therefore be compared across different calendar
dates and absolute dataframe indices without losing order or spacing.

No sequence is ranked or labeled good/bad by this identity.

## Outcome availability

Latest signals with no following execution bar are retained with
`outcome=None`.

Partially available horizons retain the existing `ForwardOutcome.complete=False`
state.

Descriptive return/MFE/MAE summaries use fully completed outcomes only while
still reporting:

- total observations;
- observations with an execution bar;
- fully completed outcomes.

## Direction

WeeklySetup direction supplies the research side:

- bullish → long;
- bearish → short.

This does not create a trade recommendation. It only makes forward-return signs
comparable to the pre-existing weekly thesis.

## Safety boundary

K2 remains analysis-only.

It does not:

- modify DailyBehavior mappings;
- change F3 fresh-signal identity;
- select a preferred sequence;
- define a sequence score;
- set an entry threshold;
- affect production qualification/ranking/actionability;
- mutate WeeklySetup;
- generate alerts or orders.

Summary statistics are descriptive evidence only. Promotion requires a later,
explicit historical study with sufficient sample size, robustness checks, and
manual review.
