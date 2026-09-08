# Market Data Provider Policy

## Purpose

The market-data provider layer separates external daily OHLCV retrieval from ProVSA's scanner, metrics, cache, and decision-support logic.

This foundation exists so the local Command Centre can later support alternate read-only providers without rewriting scanner code.

## Provider contract

`market_data.py` defines:

```text
MarketDataProvider
YFinanceMarketDataProvider
DEFAULT_MARKET_DATA_PROVIDER
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

`data.download_data()` accepts an optional provider. When no provider is supplied, it resolves to the default yfinance provider.

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
