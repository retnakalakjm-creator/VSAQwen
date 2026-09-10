from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

STANDARD_VSA_AUDIT_BASKET_NAME = "milestone6_standard_india_large_cap_30"
STANDARD_VSA_AUDIT_START_WEEK = "2026-03-02"
STANDARD_VSA_AUDIT_HORIZON_WEEKS = 8
STANDARD_VSA_AUDIT_MAX_SYMBOLS = 30

STANDARD_VSA_AUDIT_SYMBOLS: tuple[str, ...] = (
    "LT.NS",
    "RELIANCE.NS",
    "SRF.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "AXISBANK.NS",
    "SBIN.NS",
    "KOTAKBANK.NS",
    "BAJFINANCE.NS",
    "HINDUNILVR.NS",
    "ITC.NS",
    "BHARTIARTL.NS",
    "ASIANPAINT.NS",
    "MARUTI.NS",
    "M&M.NS",
    "TATAMOTORS.NS",
    "TATASTEEL.NS",
    "JSWSTEEL.NS",
    "SUNPHARMA.NS",
    "CIPLA.NS",
    "DRREDDY.NS",
    "ULTRACEMCO.NS",
    "GRASIM.NS",
    "ONGC.NS",
    "NTPC.NS",
    "POWERGRID.NS",
    "ADANIPORTS.NS",
    "COALINDIA.NS",
)


@dataclass(frozen=True, slots=True)
class StandardVSAAuditBasket:
    """Repeatable audit basket definition for Milestone 6 review.

    This object only describes symbols and default audit parameters. It does not
    fetch market data, call providers, replay the scanner, persist results, or
    change production detector/scoring behavior.
    """

    name: str
    symbols: tuple[str, ...]
    start_week: str
    horizon_weeks: int
    max_symbols: int
    audit_only: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "symbols": list(self.symbols),
            "symbol_count": len(self.symbols),
            "start_week": self.start_week,
            "horizon_weeks": self.horizon_weeks,
            "max_symbols": self.max_symbols,
            "audit_only": self.audit_only,
        }


def get_standard_vsa_audit_basket() -> StandardVSAAuditBasket:
    """Return the standard 30-symbol basket for repeatable Milestone 6 audits."""

    _validate_symbols(STANDARD_VSA_AUDIT_SYMBOLS)
    return StandardVSAAuditBasket(
        name=STANDARD_VSA_AUDIT_BASKET_NAME,
        symbols=STANDARD_VSA_AUDIT_SYMBOLS,
        start_week=STANDARD_VSA_AUDIT_START_WEEK,
        horizon_weeks=STANDARD_VSA_AUDIT_HORIZON_WEEKS,
        max_symbols=STANDARD_VSA_AUDIT_MAX_SYMBOLS,
    )


def format_basket_symbols(symbols: tuple[str, ...] | None = None) -> str:
    """Return comma-separated symbols for the VSA audit endpoint."""

    selected = STANDARD_VSA_AUDIT_SYMBOLS if symbols is None else symbols
    _validate_symbols(selected)
    return ",".join(selected)


def build_vsa_audit_url(
    *,
    base_url: str = "http://127.0.0.1:8000",
    symbols: tuple[str, ...] | None = None,
    start_week: str = STANDARD_VSA_AUDIT_START_WEEK,
    horizon_weeks: int = STANDARD_VSA_AUDIT_HORIZON_WEEKS,
    max_symbols: int = STANDARD_VSA_AUDIT_MAX_SYMBOLS,
) -> str:
    """Build the local API URL for a repeatable basket audit run."""

    selected = STANDARD_VSA_AUDIT_SYMBOLS if symbols is None else symbols
    _validate_symbols(selected)
    if horizon_weeks < 1:
        raise ValueError("horizon_weeks must be positive")
    if max_symbols < len(selected):
        raise ValueError("max_symbols must be at least the selected symbol count")
    query = urlencode(
        {
            "symbols": format_basket_symbols(selected),
            "start_week": start_week,
            "horizon_weeks": str(horizon_weeks),
            "max_symbols": str(max_symbols),
        }
    )
    return f"{base_url.rstrip('/')}/api/vsa-audit/events?{query}"


def build_standard_basket_commands(
    *,
    audit_output: str = "standard_basket_audit.json",
    candidate_output: str = "standard_basket_candidate_events_high.json",
    review_json_output: str = "standard_basket_review.json",
    review_csv_output: str = "standard_basket_review.csv",
) -> dict[str, str]:
    """Build local PowerShell commands for the full basket review workflow."""

    url = build_vsa_audit_url()
    return {
        "audit_url": url,
        "save_audit": f'curl.exe "{url}" -o {audit_output}',
        "candidate_events": (
            "python scripts/vsa_audit_candidate_events.py "
            f"{audit_output} --min-priority high --output {candidate_output}"
        ),
        "batch_review": (
            "python scripts/vsa_audit_batch_review.py "
            f"{candidate_output} --min-priority high --json-output {review_json_output} "
            f"--csv-output {review_csv_output}"
        ),
    }


def _validate_symbols(symbols: tuple[str, ...]) -> None:
    if len(symbols) != STANDARD_VSA_AUDIT_MAX_SYMBOLS:
        raise ValueError("standard audit basket must contain exactly 30 symbols")
    if len(set(symbols)) != len(symbols):
        raise ValueError("standard audit basket symbols must be unique")
    invalid = [symbol for symbol in symbols if not symbol.endswith(".NS") or symbol != symbol.upper()]
    if invalid:
        raise ValueError(f"invalid NSE symbol format: {invalid}")
