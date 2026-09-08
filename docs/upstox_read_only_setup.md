# Upstox Read-Only Market Data Setup

This setup is optional. yfinance remains the default provider for ProVSA.

Use Upstox only for read-only daily OHLCV validation after you have an Upstox access token and the correct instrument keys.

## Environment variables

```bash
MARKET_DATA_PROVIDER=upstox
UPSTOX_PROVIDER_ENABLED=true
UPSTOX_ACCESS_TOKEN_ENV=UPSTOX_ACCESS_TOKEN
UPSTOX_ACCESS_TOKEN=<token value outside the repository>
UPSTOX_SYMBOL_MAP=RELIANCE.NS=NSE_EQ|INE002A01018,TCS.NS=NSE_EQ|INE467B01029
```

Do not commit token values, refresh tokens, API secrets, account identifiers, orders, positions, holdings, or broker-side data.

## Symbol mapping

Upstox historical candles use instrument keys such as:

```text
NSE_EQ|INE002A01018
```

ProVSA does not guess instrument keys from yfinance-style symbols. Either pass the Upstox instrument key directly to the provider or configure `UPSTOX_SYMBOL_MAP`.

## Supported scope

The current adapter supports only:

```text
historical daily OHLCV candles
raw Open/High/Low/Close/Volume payloads
read-only HTTP GET calls
```

It does not support:

```text
auto-adjusted candles
intraday candles
live streaming
orders
positions
holdings
funds
margins
account APIs
```

`data.py` remains responsible for normalization, validation, caching, daily-to-weekly resampling, completed weekly bar filtering, and incremental scanner replay-window behavior.
