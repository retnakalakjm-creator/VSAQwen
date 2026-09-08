"""Stock lookup and autocomplete helpers for the ProVSA GUI.

GUI code should depend on this module rather than embedding lookup logic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StockSearchResult:
    """A normalized stock search result."""

    symbol: str
    name: str


# Lightweight NSE symbol/name index.
# The index can be replaced by a larger data source later without changing GUI code.
NSE_STOCKS: tuple[StockSearchResult, ...] = (
    StockSearchResult("RELIANCE.NS", "Reliance Industries"),
    StockSearchResult("TCS.NS", "Tata Consultancy Services"),
    StockSearchResult("INFY.NS", "Infosys"),
    StockSearchResult("HDFCBANK.NS", "HDFC Bank"),
    StockSearchResult("ICICIBANK.NS", "ICICI Bank"),
    StockSearchResult("SBIN.NS", "State Bank of India"),
    StockSearchResult("BHARTIARTL.NS", "Bharti Airtel"),
    StockSearchResult("ITC.NS", "ITC"),
    StockSearchResult("LT.NS", "Larsen & Toubro"),
    StockSearchResult("AXISBANK.NS", "Axis Bank"),
    StockSearchResult("KOTAKBANK.NS", "Kotak Mahindra Bank"),
    StockSearchResult("HINDUNILVR.NS", "Hindustan Unilever"),
    StockSearchResult("MARUTI.NS", "Maruti Suzuki India"),
    StockSearchResult("SUNPHARMA.NS", "Sun Pharmaceutical Industries"),
    StockSearchResult("TATAMOTORS.NS", "Tata Motors"),
    StockSearchResult("TATASTEEL.NS", "Tata Steel"),
    StockSearchResult("HCLTECH.NS", "HCL Technologies"),
    StockSearchResult("WIPRO.NS", "Wipro"),
    StockSearchResult("ADANIENT.NS", "Adani Enterprises"),
    StockSearchResult("ADANIPORTS.NS", "Adani Ports & SEZ"),
)


def normalize_symbol(value: str) -> str:
    """Normalize a user-entered NSE symbol."""
    symbol = value.strip().upper()
    if not symbol:
        return ""
    if symbol.endswith(".NS"):
        return symbol
    return f"{symbol}.NS"


def search_stocks(query: str, limit: int = 8) -> list[StockSearchResult]:
    """Return name/symbol matches suitable for GUI autocomplete."""
    text = query.strip().lower()
    if not text or limit <= 0:
        return []

    matches = [
        stock
        for stock in NSE_STOCKS
        if text in stock.name.lower() or text in stock.symbol.lower()
    ]

    matches.sort(
        key=lambda stock: (
            not stock.symbol.lower().startswith(text),
            not stock.name.lower().startswith(text),
            stock.name,
        )
    )
    return matches[:limit]


def resolve_stock(value: str) -> StockSearchResult | None:
    """Resolve an exact symbol or exact stock name from the local index."""
    text = value.strip().lower()
    if not text:
        return None

    normalized = normalize_symbol(text).lower()
    for stock in NSE_STOCKS:
        if stock.symbol.lower() == normalized or stock.name.lower() == text:
            return stock
    return None
