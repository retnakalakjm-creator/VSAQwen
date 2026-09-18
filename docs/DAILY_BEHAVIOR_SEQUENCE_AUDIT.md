# Daily Behavior Sequence Audit

## Purpose

The existing daily behavior snapshot answers which supported behavior dimensions
are visible inside a bounded recent window. It intentionally aggregates context.

The sequence audit adds one missing diagnostic dimension:

```text
when did each supported behavior dimension appear?
```

It preserves temporal ordering without changing the existing behavior mapping.

## Model

`evaluate_daily_behavior_sequence()` evaluates each bar independently using the
already-validated `evaluate_daily_behavior()` mapping with a one-bar window.

The result records sparse behavior steps:

```text
bar index
supported behavior dimensions
supporting evidence on that exact bar
```

It also exposes audit helpers for:

- all bars supporting one dimension;
- first bar supporting one dimension;
- last bar supporting one dimension;
- unique dimensions observed in the bounded sequence.

## Causal boundary

The sequence is bounded by:

```text
[daily_bar_index - lookback_bars + 1, daily_bar_index]
```

Evidence after the target bar cannot enter the sequence. Older context is not
carried forward and re-attributed to a later bar.

## Safety boundary

The sequence audit is read-only and non-actionable.

It does not:

- assign scores or confidence;
- rank behavior dimensions;
- define a mandatory pattern order;
- modify F3 fresh-signal rules;
- modify next-session execution;
- mutate WeeklySetup lifecycle;
- create alerts or orders.

A sequence such as:

```text
opposing pressure receding
→ aligned pressure emerging
→ absorption
```

is an observed temporal description only. It is not promoted as a required entry
template.

Promotion of any sequence relationship requires historical outcome evidence.
