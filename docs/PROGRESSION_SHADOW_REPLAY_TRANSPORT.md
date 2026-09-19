# Progression Shadow Replay Transport

## Purpose

K29 adds TradingView-style replay transport controls to the validated K28
candlestick replay.

It changes only replay navigation.

## Controls

The dev-only replay provides:

- Reset;
- previous bar;
- Play / Pause;
- next bar;
- cursor scrubber;
- 0.5x / 1x / 2x playback speed.

Playback advances exactly one replay frame per timer tick.

At the end of a sequence, playback stops automatically. Pressing Replay at the
end restarts from the first bar.

## Causality

The transport changes only the existing cursor.

The chart and audit table still receive:

    visibleFrames = sequence.frames.slice(0, cursor + 1)

Moving the cursor forward intentionally reveals that historical replay step.
Nothing beyond the selected cursor is passed to the chart.

Changing sequence, loading a dataset, switching back to synthetic fixtures, or
scrubbing manually stops autoplay and resets/sets the cursor deterministically.

## Safety

K29 adds no:

- market-data source;
- API call;
- network upload;
- browser storage;
- scanner state;
- qualification;
- scoring/ranking;
- actionability;
- persistence;
- alerts;
- orders.

The route remains dev-only and disabled in production by default.
