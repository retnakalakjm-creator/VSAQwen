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

Upstox is selected only when `MARKET_DATA_PROVIDER=upstox` is set explicitly. Even then, the current implementation returns the disabled scaffold unless `UPSTOX_PROVIDER_ENABLED=true` is also set. Enabling the scaffold still does not make external calls because the read-only OHLCV adapter is not implemented yet.

Upstox config environment variables:

```text
UPSTOX_PROVIDER_ENABLED=true|false
UPSTOX_ACCESS_TOKEN_ENV=UPSTOX_ACCESS_TOKEN
UPSTOX_API_BASE_URL=<optional read-only API base URL>
```

`UPSTOX_ACCESS_TOKEN_ENV` stores the name of the environment variable that contains a token. It must not contain the token value itself. Repository files, decision-context files, journal files, and frontend config must not store broker credentials.

Invalid provider names and invalid boolean values should fail fast rather than silently changing market-data behavior.

## Upstox scaffold boundary

`UpstoxMarketDataProvider` is an explicit scaffold for a future read-only daily OHLCV adapter.

It is not selected automatically and is disabled by default.

```text
create_market_data_provider("upstox")
```

returns a scaffold instance, but calling `download_daily()` raises until a real read-only adapter is implemented and explicitly enabled.

`UpstoxProviderConfig` references token values by environment-variable name only. It must not store access-token values, refresh-token values, API secrets, broker credentials, positions, orders, or account data in repository files, decision-context files, or journal files.

The scaffold does not implement any endpoint calls yet. This is intentional so the project can establish the integration boundary before adding provider-specific mapping, rate limiting, pagination, symbol conversion, and response normalization tests.

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

Future providers, including any Upstox read-only adapter, must respect the same boundary:

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
4. Add rate-limit/backoff handling and explicit stale-cache fallback tests.
5. Add developing/live data mode only after confirmed weekly behavior is unchanged.

No broker order scope should be added to this feature.
