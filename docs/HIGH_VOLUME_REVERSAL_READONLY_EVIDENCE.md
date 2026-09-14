# High Volume Reversal Read-Only Evidence

## Status

High Volume Reversal is connected as production-visible read-only evidence.

It can appear in API, audit, CLI/candidate evidence accessors, and the selected-week Bar-by-Bar read-only detector block, but it is not promoted into scoring or actionability.

## Detector intent

High Volume Reversal captures a bullish reversal-style bar where heavy volume pushes price to a lower low, but the same bar recovers off the low enough to show possible professional demand.

The detector is point-in-time and does not use future bars.

## Generic trigger profile

```text
High volume
Lower low versus previous completed bar
Close off the low
Mid/upper recovery or bullish recovery body
```

This is not symbol-specific and does not hardcode any JUBLFOOD, LT, or other ticker behavior.

## Read-only boundary

```text
Evidence visibility              = YES
Historical audit visibility       = YES
Selected-week frontend visibility = YES
Scanner scoring                   = NO
Ranking                           = NO
Qualification                     = NO
Actionability                     = NO
Trade plan                        = NO
Alerts/orders                     = NO
Manual-review workflow            = NO
Replay engine                     = NO
```

## Implementation notes

The detector is connected through the existing read-only Effort/Result collection path, the same practical integration path used when Absorption was first connected.

Scanner scoring explicitly excludes High Volume Reversal from meaningful VSA evidence so `high_volume_reversal` does not become a directional confirmation or fallback scoring event.
