from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from market_data import (  # noqa: E402
    MARKET_DATA_PROVIDER_ENV,
    PROVIDER_UPSTOX,
    UPSTOX_SYMBOL_MAP_ENV,
    MarketDataProviderError,
    UpstoxMarketDataProvider,
    create_market_data_provider_from_env,
)


def _yes_no(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "yes" if value else "no"


def _print_line(name: str, value: object) -> None:
    print(f"{name}: {value}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Check local read-only Upstox market-data provider readiness without "
            "printing token values or touching broker/order/account APIs."
        ),
    )
    parser.add_argument(
        "--symbol",
        default="",
        help="Optional ProVSA symbol to validate against UPSTOX_SYMBOL_MAP, e.g. RELIANCE.NS.",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help=(
            "Optionally perform one read-only daily OHLCV fetch through the configured "
            "provider. This never calls order, account, holdings, funds, margins, or "
            "position APIs."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    symbol = args.symbol.strip().upper()

    try:
        provider = create_market_data_provider_from_env()
    except Exception as exc:
        _print_line("status", "configuration_error")
        _print_line("error", exc)
        return 2

    provider_name = getattr(provider, "name", "unknown")
    _print_line("status", "diagnostic_only")
    _print_line("active_provider", provider_name)
    _print_line("provider_selector_env", MARKET_DATA_PROVIDER_ENV)

    if not isinstance(provider, UpstoxMarketDataProvider):
        _print_line("upstox_selected", "no")
        _print_line("result", "ok: active provider is not Upstox")
        return 0

    config = provider.config
    token_present = config.access_token() is not None
    symbol_mapped: bool | None = None
    mapping_error: str | None = None

    if symbol:
        try:
            config.instrument_key_for(symbol)
            symbol_mapped = True
        except MarketDataProviderError as exc:
            symbol_mapped = False
            mapping_error = str(exc)

    _print_line("upstox_selected", "yes")
    _print_line("upstox_enabled", _yes_no(config.enabled))
    _print_line("token_env", config.access_token_env)
    _print_line("token_present", _yes_no(token_present))
    _print_line("symbol", symbol or "not_checked")
    _print_line("symbol_mapped", _yes_no(symbol_mapped))
    _print_line("symbol_map_env", UPSTOX_SYMBOL_MAP_ENV)
    _print_line("broker_scope", "not_checked_or_requested")

    ready = config.enabled and token_present and (symbol_mapped is not False)
    if mapping_error:
        _print_line("mapping_error", mapping_error)

    if args.fetch:
        if not symbol:
            _print_line("fetch_status", "skipped: --symbol is required with --fetch")
            return 1
        if not ready:
            _print_line("fetch_status", "skipped: Upstox provider is not ready")
            return 1
        try:
            frame = provider.download_daily(
                symbol,
                period="5d",
                interval="1d",
                auto_adjust=False,
            )
        except Exception as exc:
            _print_line("fetch_status", "failed")
            _print_line("fetch_error", exc)
            return 1
        _print_line("fetch_status", "ok")
        _print_line("rows", len(frame))
        _print_line("last_row", "none" if frame.empty else str(frame.index[-1]))

    if not ready:
        _print_line("result", "not_ready")
        return 1

    _print_line("result", "ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
