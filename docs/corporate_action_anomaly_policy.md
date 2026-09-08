# Corporate-action anomaly flags

The scanner adds conservative OHLCV anomaly flags in the metrics layer.

These flags are warnings, not final classifications. A flagged bar may represent a stock split, bonus issue, data vendor adjustment, bad candle, market halt, or another exceptional event.

## Current checks

- `price_gap_ratio`: absolute open-versus-previous-close gap ratio.
- `price_anomaly`: true when OHLC prices are invalid or the price gap is unusually large.
- `volume_anomaly`: true when volume is extremely high versus the causal rolling average.
- `corporate_action_anomaly`: true when either price or volume anomaly is true.

## Scanner behavior

A candidate whose evaluated signal bar has `corporate_action_anomaly=True` is not actionable. The scanner still returns the candidate metadata and scores for review, but `candidate.actionable` becomes false and `candidate.reason` explains that adjusted OHLCV data should be reviewed first.

This suppression applies only to the signal bar being evaluated. Historical context bars remain visible to the evidence engine and scoring layer so analysts can inspect the broader setup without silently deleting data.

## Why this matters

VSA patterns are sensitive to spread, close location, and volume. Corporate actions and vendor-adjustment artifacts can create candles that look like climactic supply/demand even though they are not normal tradable market behavior.

Blocking same-bar actionability on flagged signal bars prevents obvious false positives while keeping the implementation conservative and auditable.
