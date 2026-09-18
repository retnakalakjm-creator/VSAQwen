# Causal Weekly-Direction Assignment Exporter

## Purpose

K6 supplies the remaining point-in-time input required by the frozen K4 daily
sequence dataset: the weekly direction that was causally visible to each
completed daily bar.

It does not infer direction from daily prices and does not introduce a new
weekly qualification rule.

## Authoritative source

K6 reuses the already-validated weekly/daily boundary:

```text
WeeklySetup
    ↓
WeeklyDailyCoordinator
    ↓
completed daily session
    ↓
armed weekly direction assignment
```

For each completed daily bar, the coordinator decides which weekly setup was
causally available.

A setup created from a weekly bar ending on Friday cannot affect any session
inside that same week. Its first possible daily consumer is the next valid
exchange session.

Holiday and special-session behavior remains delegated to the injected
`TradingCalendar`.

## Active-thesis boundary

K6 emits a direction assignment only when:

```text
context.setup is not None
AND
context.is_armed
```

This matches the existing `DailyEntryEngine` behavior boundary.

A terminal setup remains visible as coordinator context but is not reinterpreted
as an active daily thesis.

K6 does not invent historical lifecycle transitions. If a caller supplies a
terminal setup snapshot without point-in-time lifecycle history, K6 conservatively
does not emit an active direction for sessions selecting that snapshot.

## Completed daily bars

K6 applies `completed_daily_only()` before assigning directions.

Therefore a forming current-session candle cannot receive a weekly-direction
assignment or shift the bar indices consumed by K3/K4.

The emitted `bar_index` is the exact positional index inside the retained
completed-daily dataframe.

## K3/K4 compatibility

The archive exposes:

```python
archive.assignments
```

as a tuple of `DailyBehaviorSequenceDirectionAssignment` objects, which can be
passed directly into `DailyBehaviorSequenceStudyInput.weekly_directions`.

This keeps the K3 prepared-input boundary unchanged.

## Source fingerprint

K6 fingerprints the exact inputs that determine direction visibility:

- normalized symbol;
- retained completed daily session identities;
- relevant WeeklySetup identities;
- signal week;
- setup direction;
- setup lifecycle status;
- calendar-derived weekly completion session;
- calendar-derived first available session.

Daily OHLCV values are intentionally not part of this fingerprint because they
do not determine weekly-direction visibility. K4's full prepared-input
fingerprint separately covers consumed daily price history.

## Safety

K6 is analysis-only.

It does not:

- run the weekly scanner;
- create weekly qualification;
- infer weekly direction from daily bars;
- alter WeeklySetup lifecycle;
- run daily behavior scoring;
- rank sequences;
- change F3;
- create production actionability;
- create alerts or orders.

The output remains non-actionable research input.
