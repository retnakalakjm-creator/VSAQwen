# Progression Shadow Candlestick Replay

## Purpose

K28 turns the validated K25/K27 table replay into a candlestick-style visual
review surface while preserving the same offline and causal boundaries.

## Data flow

The chart receives only:

    visibleFrames = sequence.frames.slice(0, cursor + 1)

It never receives the sequence's future bars.

As the replay cursor advances, the chart is rebuilt from only the bars that are
causally visible at that point.

## Rendering

The chart uses the existing frontend dependency:

    lightweight-charts

It renders:

- weekly candlesticks;
- weekly volume;
- a semantic event marker only when the event bar becomes visible.

Transition warnings use directional markers:

    bullish -> arrow below bar
    bearish -> arrow above bar

Aligned/neutral observations use a neutral marker.

## Safety

K28 adds no data source and changes no replay contract.

The chart has no:

- fetch or XMLHttpRequest;
- API path;
- browser persistence;
- scanner access;
- qualification mutation;
- scoring/ranking;
- actionability;
- alerting;
- order execution.

The existing K27 local JSON validator remains the only path from K26 artifacts
into the dev-only replay UI.
