# Future Milestone: Point-in-Time Replay and Visual Casebook

Status: Deferred future milestone.

Priority: Start only after the backend VSA event foundation, lifecycle handling, supersession behavior, and core event calibration are stable.

Guiding principle:

```text
Foundation first, visualization second.
```

## Purpose

Build a TradingView-style ProVSA replay environment that allows visual validation of scanner behavior while preserving strict point-in-time causality.

The replay should show what the scanner knew at each completed weekly bar, not what became obvious after the full chart was visible.

## Existing foundation

ProVSA is structurally close to supporting this because the project already has:

- completed-weekly data handling;
- point-in-time audit/replay surfaces;
- incremental scanner state;
- `/api/vsa-audit/events`;
- VSA event and structural-event outputs;
- signal timing and confirmation logic;
- lifecycle, conflict, expiry, invalidation, and pending-supersession labels.

## Replay workflow

A first version should work like this:

1. Select a symbol and historical start week, such as `LT.NS / 2025-02-24`.
2. Display only bars available up to that week.
3. Advance one completed weekly bar at a time.
4. Re-run the scanner using only data known at that point.
5. Draw newly detected VSA events, structural swings, qualification, confidence, support/resistance, and story changes on the chart.
6. Show whether previous evidence remains active, becomes stale, becomes conflicted, is invalidated, or is followed by demand/recovery.
7. Optionally play automatically at different speeds.

## Visual layout

Potential layout:

- candlestick chart with replay cursor;
- play, pause, next-bar, previous-bar, and reset controls;
- event markers such as `STOPPING_VOLUME`, `SPRING`, `DEMAND_COMING_IN`, and structural weakening;
- support and resistance overlays;
- structural swing markers;
- qualification and lifecycle badges;
- confidence and pressure indicators;
- side panel showing scanner state and evidence age;
- timeline showing when an event fired, confirmed, became conflicted, expired, invalidated, or was superseded;
- separate `What was known then` panel that never includes future-derived outcome information.

## Causality requirements

This milestone must preserve causality:

- use completed weekly bars only;
- use the same point-in-time scanner path as production;
- never load the final chart and annotate earlier bars using later information;
- never mix future outcome labels into the historical replay view;
- keep any eventual outcome comparison in a separate post-replay mode.

## Example case: LT.NS

The replay should make LT-style lifecycle issues visually obvious:

```text
24 Feb 2025 -> structural context
17 Mar 2025 -> demand appears
24 Mar 2025 -> structural weakening confirms
Later weeks -> rally and failed bearish continuation
```

This would show the current class of problem clearly: demand recovery can appear while the scanner may still retain or carry a `persistent_bearish` context unless lifecycle/supersession logic handles the transition correctly.

## Phase 1 scope

Phase 1 should be a research and analysis tool only.

It must not:

- place, modify, cancel, route, or simulate executable orders;
- alter production scanner state;
- persist developing signals as confirmed context;
- activate disabled detectors;
- change production scoring or ranking;
- leak future outcome information into the replay view.

## Phase 2 possibility

After replay reaches the end of the selected period, a separate comparison mode may show:

- what the scanner believed at each replay step;
- what actually happened later;
- which events followed through;
- which events were invalidated;
- which contexts became conflicted;
- which qualifications were superseded.

## Decision

Keep this milestone deferred until the foundation is stable.

Do not build this UI while core lifecycle, supersession, and event-calibration rules are still changing.
