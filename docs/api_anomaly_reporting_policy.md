# API Anomaly Reporting Policy

The API exposes corporate-action/data-quality anomaly metadata so consumers can audit why a signal was suppressed without having to recompute metrics locally.

## Bar-level fields

Each returned weekly bar includes:

- `price_gap_ratio`
- `price_anomaly`
- `volume_anomaly`
- `corporate_action_anomaly`

These fields are copied from the canonical metrics dataframe after weekly aggregation, completed-week filtering, and metric calculation.

## Analysis-level fields

The analysis response includes:

- `anomaly_bar_indices`: every weekly bar index where `corporate_action_anomaly` is true.
- `signal_bar_anomaly`: whether the evaluated signal bar was flagged as a corporate-action anomaly.
- `signal_bar_anomaly_reason`: the suppression reason when the signal bar is anomalous.

## Trading behavior

This policy does not change scanner scoring or evidence generation. The scanner already suppresses actionable candidates when the evaluated signal bar has `corporate_action_anomaly=True`.

The API now reports that condition explicitly so downstream clients can distinguish a weak/no-signal result from a data-quality suppression.