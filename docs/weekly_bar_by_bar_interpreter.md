# Weekly Bar-by-Bar Professional Interpretation

## Purpose

The weekly bar-by-bar interpreter turns recent completed weekly OHLCV bars into a compact professional reading table.

It is designed to match the uploaded Excel-style report direction:

```text
week | professional_reading
```

The interpreter is not a trading-plan engine. It does not produce entries, stops, targets, position sizing, order instructions, broker actions, holdings, funds, margins, or account operations.

## API

```text
GET /api/symbols/{symbol}/weekly-bar-readings?lookback=15
```

Default lookback:

```text
15 completed weekly bars
```

Maximum lookback:

```text
52 completed weekly bars
```

Response shape:

```json
{
  "symbol": "SRF.NS",
  "timeframe": "1W",
  "latest_week": "2026-08-31 00:00:00",
  "lookback": 15,
  "readings": [
    {
      "week": "2026-08-24 00:00:00",
      "professional_reading": "The weekly bar was narrow and bearish, closing in the lower part of the range with low volume. Price moved lower without strong selling effort. That often means supply is drying up rather than aggressive distribution continuing. Bias: Neutral to Mildly Bullish."
    }
  ]
}
```

## Field naming

Rows intentionally use:

```text
week
professional_reading
```

Do not rename `week` to `week_ending` in the API contract.

## Completed-bar boundary

The confirmed endpoint uses completed weekly bars only through the existing data pipeline. It must not include the developing/incomplete current week.

## Implementation boundary

The interpreter is a deterministic narrative layer over the already computed weekly metric rows. It:

- does not run historical audit loops;
- does not persist decision context or journal entries;
- does not mutate scanner state;
- does not call broker/order/account APIs;
- does not expose raw model scores in the API rows.

## Future work

After this PR, the next major feature can be a dedicated trade-planning layer. That layer should remain separate from this weekly interpretation API and should explicitly define entry posture, pullback/breakout setup, target range, stop/invalidation mapping, and risk language without adding broker mutation behavior.
