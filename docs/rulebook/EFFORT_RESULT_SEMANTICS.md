# Effort vs Result — Canonical Semantics

## Purpose

Define the canonical measurement layer for Effort vs Result before any production invocation or event scoring is enabled.

This document is intentionally analytical. It does not define trading signals, scores, weights, or automatic interpretations.

## 1. Effort

For a completed bar, **Effort** is the amount of market activity represented by volume relative to its established volume baseline.

Canonical measurement:

```text
Effort = current_volume / current_average_volume
```

In the current ProVSA metrics this is represented by `volume_ratio`.

Interpretation of the measurement is continuous:

- `1.0` means volume is approximately at its baseline.
- `> 1.0` means greater effort than baseline.
- `< 1.0` means less effort than baseline.

The categorical `VolumeClass` remains useful for event rules, but it is not the canonical Effort measurement.

## 2. Result

For a completed bar, **Result** is the amount of price movement produced by the bar relative to its established spread baseline.

Canonical measurement:

```text
Result = current_spread / current_average_spread
```

In the current ProVSA metrics this is represented by `spread_ratio`.

Interpretation of the measurement is continuous:

- `1.0` means spread is approximately at its baseline.
- `> 1.0` means greater price-range result than baseline.
- `< 1.0` means less price-range result than baseline.

The categorical `SpreadClass` remains useful for event rules, but it is not the canonical Result measurement.

## 3. Close position is not folded into Result

Close position is an essential VSA observation, but it is kept separate from the Result measurement.

A wide spread closing near the high and a wide spread closing near the low have similar **magnitude of Result** but very different VSA meaning.

Therefore:

```text
Result magnitude = spread_ratio
Result character = close_position + bar direction + price location/context
```

This prevents the analytical layer from hiding important VSA evidence inside a single composite number.

## 4. Effort vs Result relationship

The relationship is initially represented by the two normalized measurements:

```text
Effort = volume_ratio
Result = spread_ratio
```

No `EFFORT_GT_RESULT` or `RESULT_GT_EFFORT` score is defined here.

A comparison may be made descriptively only when both measurements are available on the same completed bar. The comparison must preserve the underlying values rather than replacing them with a binary label.

Examples:

```text
Effort 2.2, Result 0.7
→ substantially more activity than price-range result

Effort 0.7, Result 1.8
→ substantially more price-range result than activity baseline
```

These are observations, not automatic bullish or bearish conclusions.

## 5. Context remains external

Effort and Result describe what happened on the bar. They do not, by themselves, determine why it happened or what it means for the market.

The interpretation layer must retain:

- bar direction
- close position
- preceding trend/background
- market location
- recent VSA evidence
- structural context

Thus the intended architecture is:

```text
Raw market data
      ↓
Normalized measurements
      ↓
Effort = volume_ratio
Result = spread_ratio
      ↓
Effort ↔ Result relationship
      ↓
VSA context
      ↓
Interpretation / event interaction
```

## 6. Point-in-time contract

The measurement for a bar must use information available at that bar's close and its established historical baselines only.

No future bars, future event outcomes, or post-event confirmation may be used to calculate the Effort or Result measurement itself.

This distinction is important for later historical auditing and prevents look-ahead contamination.

## 7. Current implementation status

The existing `evidence/effort.py` contains categorical detectors for `EFFORT_GT_RESULT`, `RESULT_GT_EFFORT`, and `ABSORPTION`. Those detectors are **not** treated as the canonical definition by this document.

The production call to the Effort collector remains disabled until the analytical semantics, historical audit, and decision-value audit are complete.

## 8. Explicit non-goals

This phase does not define:

- an Effort/Result score
- thresholds for bullish/bearish decisions
- automatic absorption detection
- event-specific modifiers
- replacement rules for existing VSA events
- production engine invocation

Those decisions belong to later phases after the canonical measurements have been audited on historical data.
