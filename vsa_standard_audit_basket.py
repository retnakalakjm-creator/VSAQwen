from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

STANDARD_VSA_AUDIT_BASKET_NAME = "milestone6_standard_india_large_cap_30"
EXPANDED_VSA_AUDIT_BASKET_NAME = "milestone6_expanded_india_large_mid_60"
MIDCAP_FOCUS_VSA_AUDIT_BASKET_NAME = "milestone6_midcap_focus_30"

STANDARD_VSA_AUDIT_START_WEEK = "2026-03-02"
STANDARD_VSA_AUDIT_HORIZON_WEEKS = 8
STANDARD_VSA_AUDIT_MAX_SYMBOLS = 30
EXPANDED_VSA_AUDIT_MAX_SYMBOLS = 60
MIDCAP_FOCUS_VSA_AUDIT_MAX_SYMBOLS = 30

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
    "TMPV.NS",
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

EXPANDED_VSA_AUDIT_ADDITIONAL_SYMBOLS: tuple[str, ...] = (
    "SBICARD.NS",
    "ABB.NS",
    "BEL.NS",
    "HAL.NS",
    "PFC.NS",
    "RECLTD.NS",
    "DLF.NS",
    "TRENT.NS",
    "PIDILITIND.NS",
    "GODREJCP.NS",
    "DABUR.NS",
    "BRITANNIA.NS",
    "EICHERMOT.NS",
    "HEROMOTOCO.NS",
    "BAJAJ-AUTO.NS",
    "TMCV.NS",
    "APOLLOHOSP.NS",
    "DIVISLAB.NS",
    "TECHM.NS",
    "HCLTECH.NS",
    "WIPRO.NS",
    "BPCL.NS",
    "HINDALCO.NS",
    "VEDL.NS",
    "AMBUJACEM.NS",
    "SHREECEM.NS",
    "INDUSINDBK.NS",
    "BANKBARODA.NS",
    "PNB.NS",
    "GAIL.NS",
)

EXPANDED_VSA_AUDIT_SYMBOLS: tuple[str, ...] = (
    *STANDARD_VSA_AUDIT_SYMBOLS,
    *EXPANDED_VSA_AUDIT_ADDITIONAL_SYMBOLS,
)

MIDCAP_FOCUS_VSA_AUDIT_SYMBOLS: tuple[str, ...] = (
    "SBICARD.NS",
    "AUBANK.NS",
    "IDFCFIRSTB.NS",
    "FEDERALBNK.NS",
    "BANDHANBNK.NS",
    "LICHSGFIN.NS",
    "CHOLAFIN.NS",
    "MUTHOOTFIN.NS",
    "CUMMINSIND.NS",
    "BHEL.NS",
    "ASHOKLEY.NS",
    "TVSMOTOR.NS",
    "BALKRISIND.NS",
    "EXIDEIND.NS",
    "TATACHEM.NS",
    "DEEPAKNTR.NS",
    "NAVINFLUOR.NS",
    "LALPATHLAB.NS",
    "METROPOLIS.NS",
    "IPCALAB.NS",
    "TORNTPHARM.NS",
    "GLENMARK.NS",
    "BIOCON.NS",
    "LAURUSLABS.NS",
    "PERSISTENT.NS",
    "COFORGE.NS",
    "MPHASIS.NS",
    "POLYCAB.NS",
    "ASTRAL.NS",
    "CROMPTON.NS",
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
    description: str = ""
    audit_only: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "symbols": list(self.symbols),
            "symbol_count": len(self.symbols),
            "start_week": self.start_week,
            "horizon_weeks": self.horizon_weeks,
            "max_symbols": self.max_symbols,
            "audit_only": self.audit_only,
        }


VSA_AUDIT_BASKETS: dict[str, StandardVSAAuditBasket] = {
    STANDARD_VSA_AUDIT_BASKET_NAME: StandardVSAAuditBasket(
        name=STANDARD_VSA_AUDIT_BASKET_NAME,
        symbols=STANDARD_VSA_AUDIT_SYMBOLS,
        start_week=STANDARD_VSA_AUDIT_START_WEEK,
        horizon_weeks=STANDARD_VSA_AUDIT_HORIZON_WEEKS,
        max_symbols=STANDARD_VSA_AUDIT_MAX_SYMBOLS,
        description="Original 30-symbol largecap regression baseline.",
    ),
    EXPANDED_VSA_AUDIT_BASKET_NAME: StandardVSAAuditBasket(
        name=EXPANDED_VSA_AUDIT_BASKET_NAME,
        symbols=EXPANDED_VSA_AUDIT_SYMBOLS,
        start_week=STANDARD_VSA_AUDIT_START_WEEK,
        horizon_weeks=STANDARD_VSA_AUDIT_HORIZON_WEEKS,
        max_symbols=EXPANDED_VSA_AUDIT_MAX_SYMBOLS,
        description="Expanded 60-symbol largecap plus selected midcap consistency baseline.",
    ),
    MIDCAP_FOCUS_VSA_AUDIT_BASKET_NAME: StandardVSAAuditBasket(
        name=MIDCAP_FOCUS_VSA_AUDIT_BASKET_NAME,
        symbols=MIDCAP_FOCUS_VSA_AUDIT_SYMBOLS,
        start_week=STANDARD_VSA_AUDIT_START_WEEK,
        horizon_weeks=STANDARD_VSA_AUDIT_HORIZON_WEEKS,
        max_symbols=MIDCAP_FOCUS_VSA_AUDIT_MAX_SYMBOLS,
        description="30-symbol midcap-focused false-positive and noise review basket.",
    ),
}


def list_vsa_audit_basket_names() -> tuple[str, ...]:
    """Return available repeatable VSA audit basket names."""

    return tuple(VSA_AUDIT_BASKETS)


def get_vsa_audit_basket(name: str = STANDARD_VSA_AUDIT_BASKET_NAME) -> StandardVSAAuditBasket:
    """Return a named repeatable Milestone 6 audit basket."""

    if name not in VSA_AUDIT_BASKETS:
        available = ", ".join(list_vsa_audit_basket_names())
        raise ValueError(f"unknown VSA audit basket {name!r}; available: {available}")
    basket = VSA_AUDIT_BASKETS[name]
    _validate_basket(basket)
    return basket


def get_standard_vsa_audit_basket() -> StandardVSAAuditBasket:
    """Return the original 30-symbol basket for repeatable Milestone 6 audits."""

    return get_vsa_audit_basket(STANDARD_VSA_AUDIT_BASKET_NAME)


def format_basket_symbols(symbols: tuple[str, ...] | None = None, *, basket_name: str = STANDARD_VSA_AUDIT_BASKET_NAME) -> str:
    """Return comma-separated symbols for the VSA audit endpoint."""

    selected = get_vsa_audit_basket(basket_name).symbols if symbols is None else symbols
    _validate_symbols(selected, label="selected symbols")
    return ",".join(selected)


def build_vsa_audit_url(
    *,
    base_url: str = "http://127.0.0.1:8000",
    basket_name: str = STANDARD_VSA_AUDIT_BASKET_NAME,
    symbols: tuple[str, ...] | None = None,
    start_week: str | None = None,
    horizon_weeks: int | None = None,
    max_symbols: int | None = None,
) -> str:
    """Build the local API URL for a repeatable basket audit run."""

    basket = get_vsa_audit_basket(basket_name)
    selected = basket.symbols if symbols is None else symbols
    selected_start_week = basket.start_week if start_week is None else start_week
    selected_horizon_weeks = basket.horizon_weeks if horizon_weeks is None else horizon_weeks
    selected_max_symbols = basket.max_symbols if max_symbols is None else max_symbols

    _validate_symbols(selected, label="selected symbols")
    if selected_horizon_weeks < 1:
        raise ValueError("horizon_weeks must be positive")
    if selected_max_symbols < len(selected):
        raise ValueError("max_symbols must be at least the selected symbol count")
    query = urlencode(
        {
            "symbols": format_basket_symbols(selected),
            "start_week": selected_start_week,
            "horizon_weeks": str(selected_horizon_weeks),
            "max_symbols": str(selected_max_symbols),
        }
    )
    return f"{base_url.rstrip('/')}/api/vsa-audit/events?{query}"


def build_standard_basket_commands(
    *,
    basket_name: str = STANDARD_VSA_AUDIT_BASKET_NAME,
    base_url: str = "http://127.0.0.1:8000",
    start_week: str | None = None,
    horizon_weeks: int | None = None,
    audit_output: str | None = None,
    candidate_output: str | None = None,
    review_json_output: str | None = None,
    review_csv_output: str | None = None,
) -> dict[str, str]:
    """Build local PowerShell commands for a selected basket review workflow."""

    basket = get_vsa_audit_basket(basket_name)
    output_prefix = _default_output_prefix(basket.name)
    selected_audit_output = audit_output or f"{output_prefix}_audit.json"
    selected_candidate_output = candidate_output or f"{output_prefix}_candidate_events_high.json"
    selected_review_json_output = review_json_output or f"{output_prefix}_review.json"
    selected_review_csv_output = review_csv_output or f"{output_prefix}_review.csv"

    url = build_vsa_audit_url(
        base_url=base_url,
        basket_name=basket.name,
        start_week=start_week,
        horizon_weeks=horizon_weeks,
        max_symbols=basket.max_symbols,
    )
    return {
        "audit_url": url,
        "save_audit": f'curl.exe "{url}" -o {selected_audit_output}',
        "candidate_events": (
            "python scripts/vsa_audit_candidate_events.py "
            f"{selected_audit_output} --min-priority high --output {selected_candidate_output}"
        ),
        "batch_review": (
            "python scripts/vsa_audit_batch_review.py "
            f"{selected_candidate_output} --min-priority high --json-output {selected_review_json_output} "
            f"--csv-output {selected_review_csv_output}"
        ),
    }


def _default_output_prefix(basket_name: str) -> str:
    if basket_name == STANDARD_VSA_AUDIT_BASKET_NAME:
        return "standard_basket"
    if basket_name == EXPANDED_VSA_AUDIT_BASKET_NAME:
        return "expanded_large_mid_basket"
    if basket_name == MIDCAP_FOCUS_VSA_AUDIT_BASKET_NAME:
        return "midcap_focus_basket"
    return basket_name.replace("milestone6_", "").replace("_", "-")


def _validate_basket(basket: StandardVSAAuditBasket) -> None:
    _validate_symbols(basket.symbols, expected_count=basket.max_symbols, label=basket.name)


def _validate_symbols(
    symbols: tuple[str, ...],
    *,
    expected_count: int | None = None,
    label: str = "basket",
) -> None:
    if expected_count is not None and len(symbols) != expected_count:
        raise ValueError(f"{label} must contain exactly {expected_count} symbols")
    if len(set(symbols)) != len(symbols):
        raise ValueError(f"{label} symbols must be unique")
    invalid = [symbol for symbol in symbols if not symbol.endswith(".NS") or symbol != symbol.upper()]
    if invalid:
        raise ValueError(f"invalid NSE symbol format: {invalid}")
