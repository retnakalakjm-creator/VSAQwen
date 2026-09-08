# Market Data Provider Policy

## Purpose

The market-data provider layer separates external daily OHLCV retrieval from ProVSA's scanner, metrics, cache, and decision-support logic.

This foundation exists so the local Command Centre can later support alternate read-only providers without rewriting scanner code.

## Provider contract

`market_data.py` defines:

```text
MarketDataProvider
YFinanceMarketDataProvider
UpstoxProviderConfig
UpstoxMarketDataProvider
DEFAULT_MARKET_DATA_PROVIDER
create_market_data_provider
create_market_data_provider_from_env
resolve_market_data_provider
```

A provider implements one read-only method:

```text
download_daily(symbol, period, interval, auto_adjust)
```

The provider returns the raw external payload. It does not decide scanner semantics.

## Default behavior

`YFinanceMarketDataProvider` is the default implementation and preserves the existing yfinance call shape:

```text
tickers=symbol
period=DEFAULT_PERIOD or INCREMENTAL_PERIOD
interval=1d
auto_adjust=False
progress=False
```

`data.download_data()` accepts an optional provider. When no provider is supplied, it resolves to the default yfinance-compatible provider.

The yfinance path remains the only active default path.

## Provider selection/config resolver boundary

Provider selection is explicit and environment driven for future CLI/API entry points.

```text
MARKET_DATA_PROVIDER=yfinance
MARKET_DATA_PROVIDER=upstox
```

When `MARKET_DATA_PROVIDER` is absent, blank, or set to `yfinance`, the resolver returns the yfinance provider.

Upstox is selected only when `MARKET_DATA_PROVIDER=upstox` is set explicitly. Even then, the implementation remains disabled unless `UPSTOX_PROVIDER_ENABLED=true` is also set.

Upstox config environment variables:

```text
UPSTOX_PROVIDER_ENABLED=true|false
UPSTOX_ACCESS_TOKEN_ENV=UPSTOX_ACCESS_TOKEN
UPSTOX_API_BASE_URL=<optional read-only API base URL>
UPSTOX_SYMBOL_MAP=RELIANCE.NS=NSE_EQ|INE002A01018,TCS.NS=NSE_EQ|INE467B01029
UPSTOX_MAX_RETRIES=2
UPSTOX_RETRY_BACKOFF_SECONDS=0.5
```

`UPSTOX_ACCESS_TOKEN_ENV` stores the name of the environment variable that contains a token. It must not contain the token value itself. Repository files, decision-context files, journal files, and frontend config must not store broker credentials.

`UPSTOX_SYMBOL_MAP` stores local-symbol to Upstox-instrument-key mappings. The map is configuration only; it must not include credentials, order identifiers, account identifiers, or position data.

Invalid provider names, invalid boolean values, malformed symbol-map entries, negative retry counts, and negative backoff values should fail fast rather than silently changing market-data behavior.

## API runtime selection boundary

The FastAPI runtime creates `ProVSAService` through a small service factory that calls `create_market_data_provider_from_env()` once at the application boundary.

`ProVSAService` accepts an optional `market_data_provider`. When a provider is injected, service-level symbol analysis, compact decision-context refreshes, and decision-journal evaluations download daily data through `data.download_data(symbol, provider=provider)`.

When no provider is injected, the service intentionally preserves the legacy `data.download_data(symbol)` path so existing tests, local scripts, and the yfinance default behavior remain unchanged.

This runtime wiring must remain outside scanner, metrics, VSA detector, scoring, qualification, actionability, and journal-evaluation logic. Provider selection changes where raw daily OHLCV is retrieved from; it must not change how confirmed weekly decisions are calculated.

## Upstox read-only OHLCV boundary

`UpstoxMarketDataProvider` is a read-only daily OHLCV adapter for Upstox historical candles.

It is not selected automatically and is disabled by default.

```text
create_market_data_provider("upstox")
```

returns an Upstox provider instance, but calling `download_daily()` raises unless the provider is explicitly enabled and an access token is available through the configured environment-variable name.

The adapter supports only raw daily OHLCV retrieval. It does not support auto-adjusted data, intraday candles, live streaming, option chains, order placement, order modification, order cancellation, positions, funds, margins, holdings, or account APIs.

Symbols must be explicit Upstox instrument keys, such as:

```text
NSE_EQ|INE002A01018
```

or configured through `UPSTOX_SYMBOL_MAP`. The adapter must not guess or synthesize instrument keys from yfinance-style symbols because an incorrect mapping would silently contaminate scanner inputs.

The adapter maps Upstox candle rows into the raw yfinance-compatible shape expected by `data.py`:

```text
Open
High
Low
Close
Volume
```

`data.py` still owns canonical normalization to lowercase columns, validation, caching, weekly resampling, and completed weekly bar filtering.

## Rate-limit, retry, and stale-cache boundary

Provider transport failures are classified before they reach the scanner. HTTP 429 responses are surfaced as rate-limit errors, while non-429 HTTP and URL failures are surfaced as transport errors.

Upstox retry behavior is bounded by `UPSTOX_MAX_RETRIES` and `UPSTOX_RETRY_BACKOFF_SECONDS`. Retries apply only to provider transport/rate-limit failures and must remain outside scanner loops.

If a cached dataset already exists and an incremental refresh fails, `data.download_data()` returns the validated stale cache and records the failure reason in the cache metadata sidecar. This keeps the local UI usable during temporary provider/rate-limit outages without silently rewriting scanner rules.

First-time historical downloads still fail if the provider cannot return enough valid data, because no safe cache baseline exists yet.

## Ownership boundary

The provider layer owns only external data retrieval.

`data.py` continues to own:

```text
raw OHLCV normalization
required-column validation
minimum-bar validation
cache read/write behavior
CSV/Parquet fallback behavior
stale-cache behavior
historical vs incremental refresh policy
daily-to-weekly resampling
completed weekly bar filtering
incremental replay-window construction
```

## Financial correctness boundary

This abstraction does not change:

```text
scanner execution logic
VSA detectors
metrics calculations
rolling-stat causality
completed weekly bar policy
signal qualification
actionability
ranking
journal evaluation rules
frontend decisions
broker integration
order placement
position sizing
```

The provider interface is architecture-only. It is not a trading feature.

## Future provider rules

Future providers, including any Upstox extensions, must respect the same boundary:

```text
read market data only
return raw daily OHLCV payloads
never place, modify, cancel, or size orders
never persist broker credentials in decision context or journal files
never bypass completed-bar policy for confirmed scanner decisions
```

Developing/live-bar data can be added later, but it must be labeled separately from confirmed weekly signals.

## Recommended implementation order

1. Keep yfinance as the default provider.
2. Add provider-specific tests before enabling any alternate provider.
3. Add Upstox symbol mapping for read-only daily OHLCV data.
4. Add API/runtime provider injection only at the outer service boundary.
5. Add rate-limit/backoff handling and explicit stale-cache fallback tests.
6. Add developing/live data mode only after confirmed weekly behavior is unchanged.

No broker order scope should be added to this feature.
