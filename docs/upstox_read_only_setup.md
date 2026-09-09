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
UPSTOX_MAX_RETRIES=2
UPSTOX_RETRY_BACKOFF_SECONDS=0.5
```

Do not commit token values, refresh tokens, API secrets, account identifiers, orders, positions, holdings, or broker-side data.

## Symbol mapping

Upstox historical candles use instrument keys such as:

```text
NSE_EQ|INE002A01018
```

ProVSA does not guess instrument keys from yfinance-style symbols. Either pass the Upstox instrument key directly to the provider or configure `UPSTOX_SYMBOL_MAP`.

## Local readiness check

After configuring the environment, run the diagnostic helper:

```bash
python tools/check_upstox_provider_config.py --symbol RELIANCE.NS
```

The helper reports whether Upstox is selected, enabled, whether the configured token environment variable is present, and whether the symbol has an explicit mapping. It prints only readiness booleans and the token environment-variable name; it must never print the token value.

To optionally validate one read-only OHLCV fetch through the configured provider, pass `--fetch`:

```bash
python tools/check_upstox_provider_config.py --symbol RELIANCE.NS --fetch
```

The fetch check uses the read-only daily OHLCV provider path only. It does not call order, position, holdings, funds, margins, or account APIs.

## Retry and stale-cache behavior

The Upstox adapter classifies temporary provider failures before they reach scanner code:

```text
HTTP 429 -> rate-limit error
other HTTP/URL failures -> transport error
```

`UPSTOX_MAX_RETRIES` controls how many retry attempts are allowed after the first failed request. `UPSTOX_RETRY_BACKOFF_SECONDS` controls the initial backoff delay; retry waits grow exponentially.

When a cached dataset already exists, `data.download_data()` keeps the local scanner usable during temporary Upstox failures by returning the validated stale cache and writing the failure reason to the cache metadata sidecar.

First-time historical downloads still fail if Upstox cannot return enough valid daily bars, because there is no safe baseline cache to use.

## Supported scope

The current adapter supports only:

```text
historical daily OHLCV candles
raw Open/High/Low/Close/Volume payloads
read-only HTTP GET calls
bounded retry for temporary transport/rate-limit failures
local readiness checks without token disclosure
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
