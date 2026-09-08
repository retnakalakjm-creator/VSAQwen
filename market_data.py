from __future__ import annotations

import json
import os
import time as time_module
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf

PROVIDER_YFINANCE = "yfinance"
PROVIDER_UPSTOX = "upstox"
MARKET_DATA_PROVIDER_ENV = "MARKET_DATA_PROVIDER"
UPSTOX_ENABLED_ENV = "UPSTOX_PROVIDER_ENABLED"
UPSTOX_ACCESS_TOKEN_ENV_VAR_ENV = "UPSTOX_ACCESS_TOKEN_ENV"
UPSTOX_API_BASE_URL_ENV = "UPSTOX_API_BASE_URL"
UPSTOX_SYMBOL_MAP_ENV = "UPSTOX_SYMBOL_MAP"
UPSTOX_MAX_RETRIES_ENV = "UPSTOX_MAX_RETRIES"
UPSTOX_RETRY_BACKOFF_SECONDS_ENV = "UPSTOX_RETRY_BACKOFF_SECONDS"
DEFAULT_UPSTOX_ACCESS_TOKEN_ENV = "UPSTOX_ACCESS_TOKEN"
DEFAULT_UPSTOX_API_BASE_URL = "https://api.upstox.com"
DEFAULT_UPSTOX_MAX_HISTORY_DAYS = 3650
DEFAULT_UPSTOX_MAX_RETRIES = 2
DEFAULT_UPSTOX_RETRY_BACKOFF_SECONDS = 0.5

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off", ""})
HttpGet = Callable[[str, Mapping[str, str]], bytes]
Sleep = Callable[[float], None]


class MarketDataProvider(Protocol):
    """Read-only market-data provider contract for daily OHLCV downloads.

    Providers must return the raw provider payload. The canonical ProVSA
    normalization, validation, caching, weekly resampling, and completed-bar
    policy remain owned by `data.py`.
    """

    name: str

    def download_daily(
        self,
        symbol: str,
        *,
        period: str,
        interval: str,
        auto_adjust: bool,
    ) -> pd.DataFrame:
        """Return raw daily OHLCV bars for one symbol."""


class MarketDataProviderError(RuntimeError):
    """Raised when a configured market-data provider cannot serve data safely."""


class MarketDataRateLimitError(MarketDataProviderError):
    """Raised when a provider reports a temporary rate-limit condition."""


class MarketDataTransportError(MarketDataProviderError):
    """Raised when provider transport fails before a valid payload is returned."""


class UnsupportedMarketDataProviderError(ValueError):
    """Raised when a provider name is not registered."""


@dataclass(frozen=True, slots=True)
class YFinanceMarketDataProvider:
    """Default read-only provider backed by yfinance."""

    progress: bool = False
    name: str = PROVIDER_YFINANCE

    def download_daily(
        self,
        symbol: str,
        *,
        period: str,
        interval: str,
        auto_adjust: bool,
    ) -> pd.DataFrame:
        return yf.download(
            tickers=symbol,
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            progress=self.progress,
        )


def _default_http_get(url: str, headers: Mapping[str, str]) -> bytes:
    request = Request(url, headers=dict(headers), method="GET")
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - explicit user-configured market-data URL.
            return response.read()
    except HTTPError as exc:
        message = f"Upstox HTTP {exc.code}: {exc.reason}"
        if exc.code == 429:
            raise MarketDataRateLimitError(f"Upstox rate limit exceeded: {message}") from exc
        raise MarketDataTransportError(message) from exc
    except URLError as exc:
        raise MarketDataTransportError(f"Upstox transport error: {exc.reason}") from exc


@dataclass(frozen=True, slots=True)
class UpstoxProviderConfig:
    """Configuration for a read-only Upstox daily OHLCV adapter.

    Tokens are referenced by environment-variable name only. The config never
    stores token values and this provider intentionally exposes no broker/order
    capability.
    """

    enabled: bool = False
    access_token_env: str = DEFAULT_UPSTOX_ACCESS_TOKEN_ENV
    api_base_url: str | None = None
    symbol_map: Mapping[str, str] = field(default_factory=dict)
    max_retries: int = DEFAULT_UPSTOX_MAX_RETRIES
    retry_backoff_seconds: float = DEFAULT_UPSTOX_RETRY_BACKOFF_SECONDS
    http_get: HttpGet = field(default=_default_http_get, repr=False, compare=False)
    sleep: Sleep = field(default=time_module.sleep, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be greater than or equal to zero")
        if self.retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must be greater than or equal to zero")

    def access_token(self) -> str | None:
        """Return a token from the environment, if configured externally."""
        token = os.environ.get(self.access_token_env, "").strip()
        return token or None

    def base_url(self) -> str:
        """Return the configured Upstox API base URL without a trailing slash."""
        return (self.api_base_url or DEFAULT_UPSTOX_API_BASE_URL).rstrip("/")

    def instrument_key_for(self, symbol: str) -> str:
        """Resolve a ProVSA symbol or explicit Upstox key to an instrument key."""
        normalized_symbol = symbol.strip()
        if not normalized_symbol:
            raise MarketDataProviderError("symbol is required for Upstox market data")
        if "|" in normalized_symbol:
            return normalized_symbol

        mapped = self.symbol_map.get(normalized_symbol) or self.symbol_map.get(
            normalized_symbol.upper()
        )
        if mapped:
            return mapped.strip()

        raise MarketDataProviderError(
            "Upstox requires an explicit instrument key such as "
            "'NSE_EQ|INE002A01018' or a mapping in UPSTOX_SYMBOL_MAP. "
            f"No mapping exists for {symbol!r}."
        )


@dataclass(frozen=True, slots=True)
class UpstoxMarketDataProvider:
    """Read-only Upstox daily OHLCV adapter.

    This provider retrieves historical daily candles only. It has no order,
    position, account, quote-streaming, or broker mutation capability.
    """

    config: UpstoxProviderConfig = field(default_factory=UpstoxProviderConfig)
    name: str = PROVIDER_UPSTOX

    def download_daily(
        self,
        symbol: str,
        *,
        period: str,
        interval: str,
        auto_adjust: bool,
    ) -> pd.DataFrame:
        if not self.config.enabled:
            raise MarketDataProviderError(
                "Upstox provider is disabled. Keep MARKET_DATA_PROVIDER as "
                "'yfinance' unless read-only Upstox data is explicitly enabled."
            )
        if auto_adjust:
            raise MarketDataProviderError("Upstox daily OHLCV adapter returns raw data only")
        if interval.strip().lower() not in {"1d", "1day", "day", "daily"}:
            raise MarketDataProviderError("Upstox adapter currently supports daily candles only")

        access_token = self.config.access_token()
        if access_token is None:
            raise MarketDataProviderError(
                f"Upstox access token is missing from {self.config.access_token_env!r}"
            )

        instrument_key = self.config.instrument_key_for(symbol)
        from_date, to_date = _date_range_for_period(period)
        url = _upstox_historical_daily_url(
            self.config.base_url(),
            instrument_key,
            from_date=from_date,
            to_date=to_date,
        )
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        payload = _http_get_with_retries(
            self.config.http_get,
            url,
            headers,
            max_retries=self.config.max_retries,
            backoff_seconds=self.config.retry_backoff_seconds,
            sleep=self.config.sleep,
        )
        return _upstox_candles_to_frame(payload)


DEFAULT_MARKET_DATA_PROVIDER = YFinanceMarketDataProvider()


def _normalize_provider_name(provider_name: str | None) -> str:
    return (provider_name or PROVIDER_YFINANCE).strip().lower()


def _env_value(env: Mapping[str, str], name: str, default: str = "") -> str:
    return env.get(name, default).strip()


def _env_bool(env: Mapping[str, str], name: str, *, default: bool = False) -> bool:
    raw = _env_value(env, name)
    if raw == "":
        return default
    normalized = raw.lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(
        f"{name} must be one of: "
        "1, true, yes, on, 0, false, no, off"
    )


def _env_int(env: Mapping[str, str], name: str, *, default: int) -> int:
    raw = _env_value(env, name)
    if raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 0:
        raise ValueError(f"{name} must be greater than or equal to zero")
    return value


def _env_float(env: Mapping[str, str], name: str, *, default: float) -> float:
    raw = _env_value(env, name)
    if raw == "":
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value < 0:
        raise ValueError(f"{name} must be greater than or equal to zero")
    return value


def _parse_symbol_map(value: str) -> dict[str, str]:
    """Parse SYMBOL=UPSTOX_KEY pairs from an environment string."""
    result: dict[str, str] = {}
    for item in value.split(","):
        entry = item.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise ValueError(
                f"{UPSTOX_SYMBOL_MAP_ENV} entries must use SYMBOL=INSTRUMENT_KEY format"
            )
        symbol, instrument_key = (part.strip() for part in entry.split("=", 1))
        if not symbol or not instrument_key:
            raise ValueError(
                f"{UPSTOX_SYMBOL_MAP_ENV} entries must include both symbol and instrument key"
            )
        result[symbol] = instrument_key
        result[symbol.upper()] = instrument_key
    return result


def _date_range_for_period(period: str, *, today: date | None = None) -> tuple[date, date]:
    current = today or date.today()
    normalized = period.strip().lower()
    if normalized in {"", "max"}:
        return current - timedelta(days=DEFAULT_UPSTOX_MAX_HISTORY_DAYS), current

    try:
        amount = int(normalized[:-1])
    except ValueError as exc:
        raise MarketDataProviderError(f"Unsupported Upstox period: {period!r}") from exc

    suffix = normalized[-1]
    if amount <= 0:
        raise MarketDataProviderError(f"Unsupported Upstox period: {period!r}")
    if suffix == "d":
        delta = timedelta(days=amount)
    elif suffix == "w":
        delta = timedelta(weeks=amount)
    elif suffix == "m":
        delta = timedelta(days=amount * 30)
    elif suffix == "y":
        delta = timedelta(days=amount * 365)
    else:
        raise MarketDataProviderError(f"Unsupported Upstox period: {period!r}")
    return current - delta, current


def _upstox_historical_daily_url(
    base_url: str,
    instrument_key: str,
    *,
    from_date: date,
    to_date: date,
) -> str:
    encoded_key = quote(instrument_key, safe="")
    return (
        f"{base_url}/v3/historical-candle/"
        f"{encoded_key}/days/1/{to_date.isoformat()}/{from_date.isoformat()}"
    )


def _http_get_with_retries(
    http_get: HttpGet,
    url: str,
    headers: Mapping[str, str],
    *,
    max_retries: int,
    backoff_seconds: float,
    sleep: Sleep,
) -> bytes:
    """Call a provider HTTP function with bounded retry for transient failures."""
    for attempt in range(max_retries + 1):
        try:
            return http_get(url, headers)
        except (MarketDataRateLimitError, MarketDataTransportError):
            if attempt >= max_retries:
                raise
            if backoff_seconds > 0:
                sleep(backoff_seconds * (2**attempt))
    raise AssertionError("unreachable retry state")


def _upstox_candles_to_frame(payload: bytes | str | Mapping[str, object]) -> pd.DataFrame:
    if isinstance(payload, Mapping):
        data = payload
    else:
        data = json.loads(payload)

    candles = data.get("data", {})
    if not isinstance(candles, Mapping):
        raise MarketDataProviderError("Upstox response has invalid data payload")
    rows = candles.get("candles", [])
    if not isinstance(rows, list):
        raise MarketDataProviderError("Upstox response has invalid candles payload")
    if not rows:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    parsed_rows: list[dict[str, float]] = []
    timestamps: list[pd.Timestamp] = []
    for row in rows:
        if not isinstance(row, list | tuple) or len(row) < 6:
            raise MarketDataProviderError("Upstox candle rows must contain timestamp/OHLCV")
        timestamps.append(pd.Timestamp(row[0]))
        parsed_rows.append(
            {
                "Open": float(row[1]),
                "High": float(row[2]),
                "Low": float(row[3]),
                "Close": float(row[4]),
                "Volume": float(row[5]),
            }
        )

    frame = pd.DataFrame(parsed_rows, index=pd.to_datetime(timestamps))
    frame.sort_index(inplace=True)
    return frame


def create_market_data_provider(
    provider_name: str | None = None,
    *,
    upstox_config: UpstoxProviderConfig | None = None,
) -> MarketDataProvider:
    """Create a registered market-data provider by name.

    The default remains yfinance. Upstox is available only as an explicit,
    disabled scaffold so it cannot be selected accidentally.
    """
    normalized = _normalize_provider_name(provider_name)
    if normalized in ("", PROVIDER_YFINANCE):
        return DEFAULT_MARKET_DATA_PROVIDER
    if normalized == PROVIDER_UPSTOX:
        return UpstoxMarketDataProvider(config=upstox_config or UpstoxProviderConfig())
    raise UnsupportedMarketDataProviderError(f"Unsupported market data provider: {provider_name!r}")


def create_market_data_provider_from_env(
    env: Mapping[str, str] | None = None,
) -> MarketDataProvider:
    """Create the process-configured read-only market-data provider.

    `MARKET_DATA_PROVIDER` is intentionally the only selector. When it is absent
    or blank, yfinance remains the active provider. Selecting Upstox is explicit
    and still requires explicit enablement for read-only OHLCV retrieval.
    """
    source = os.environ if env is None else env
    provider_name = _env_value(source, MARKET_DATA_PROVIDER_ENV, PROVIDER_YFINANCE)
    normalized = _normalize_provider_name(provider_name)

    if normalized != PROVIDER_UPSTOX:
        return create_market_data_provider(normalized)

    token_env = _env_value(
        source,
        UPSTOX_ACCESS_TOKEN_ENV_VAR_ENV,
        DEFAULT_UPSTOX_ACCESS_TOKEN_ENV,
    )
    api_base_url = _env_value(source, UPSTOX_API_BASE_URL_ENV) or None
    symbol_map = _parse_symbol_map(_env_value(source, UPSTOX_SYMBOL_MAP_ENV))
    upstox_config = UpstoxProviderConfig(
        enabled=_env_bool(source, UPSTOX_ENABLED_ENV, default=False),
        access_token_env=token_env,
        api_base_url=api_base_url,
        symbol_map=symbol_map,
        max_retries=_env_int(
            source,
            UPSTOX_MAX_RETRIES_ENV,
            default=DEFAULT_UPSTOX_MAX_RETRIES,
        ),
        retry_backoff_seconds=_env_float(
            source,
            UPSTOX_RETRY_BACKOFF_SECONDS_ENV,
            default=DEFAULT_UPSTOX_RETRY_BACKOFF_SECONDS,
        ),
    )
    return create_market_data_provider(
        PROVIDER_UPSTOX,
        upstox_config=upstox_config,
    )


def resolve_market_data_provider(
    provider: MarketDataProvider | None = None,
) -> MarketDataProvider:
    """Return the supplied provider or the default yfinance adapter."""
    return DEFAULT_MARKET_DATA_PROVIDER if provider is None else provider


__all__ = [
    "DEFAULT_MARKET_DATA_PROVIDER",
    "DEFAULT_UPSTOX_ACCESS_TOKEN_ENV",
    "DEFAULT_UPSTOX_API_BASE_URL",
    "DEFAULT_UPSTOX_MAX_RETRIES",
    "DEFAULT_UPSTOX_RETRY_BACKOFF_SECONDS",
    "MARKET_DATA_PROVIDER_ENV",
    "MarketDataProvider",
    "MarketDataProviderError",
    "MarketDataRateLimitError",
    "MarketDataTransportError",
    "PROVIDER_UPSTOX",
    "PROVIDER_YFINANCE",
    "UPSTOX_ACCESS_TOKEN_ENV_VAR_ENV",
    "UPSTOX_API_BASE_URL_ENV",
    "UPSTOX_ENABLED_ENV",
    "UPSTOX_MAX_RETRIES_ENV",
    "UPSTOX_RETRY_BACKOFF_SECONDS_ENV",
    "UPSTOX_SYMBOL_MAP_ENV",
    "UnsupportedMarketDataProviderError",
    "UpstoxMarketDataProvider",
    "UpstoxProviderConfig",
    "YFinanceMarketDataProvider",
    "create_market_data_provider",
    "create_market_data_provider_from_env",
    "resolve_market_data_provider",
]
