from __future__ import annotations

import json
import subprocess
import sys
from urllib.parse import parse_qs, urlparse

from vsa_standard_audit_basket import (
    STANDARD_VSA_AUDIT_MAX_SYMBOLS,
    STANDARD_VSA_AUDIT_SYMBOLS,
    build_standard_basket_commands,
    build_vsa_audit_url,
    format_basket_symbols,
    get_standard_vsa_audit_basket,
)


def test_standard_basket_has_exactly_thirty_unique_nse_symbols() -> None:
    basket = get_standard_vsa_audit_basket()

    assert basket.audit_only is True
    assert basket.max_symbols == STANDARD_VSA_AUDIT_MAX_SYMBOLS == 30
    assert len(basket.symbols) == 30
    assert len(set(basket.symbols)) == 30
    assert basket.symbols == STANDARD_VSA_AUDIT_SYMBOLS
    assert all(symbol.endswith(".NS") for symbol in basket.symbols)
    assert all(symbol == symbol.upper() for symbol in basket.symbols)
    assert {"LT.NS", "RELIANCE.NS", "SRF.NS"}.issubset(set(basket.symbols))


def test_standard_basket_builds_repeatable_audit_url() -> None:
    url = build_vsa_audit_url()
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "http"
    assert parsed.netloc == "127.0.0.1:8000"
    assert parsed.path == "/api/vsa-audit/events"
    assert query["start_week"] == ["2026-03-02"]
    assert query["horizon_weeks"] == ["8"]
    assert query["max_symbols"] == ["30"]
    assert query["symbols"] == [format_basket_symbols()]


def test_standard_basket_commands_chain_existing_audit_tools() -> None:
    commands = build_standard_basket_commands()

    assert commands["audit_url"].startswith("http://127.0.0.1:8000/api/vsa-audit/events?")
    assert commands["save_audit"].startswith("curl.exe ")
    assert "scripts/vsa_audit_candidate_events.py" in commands["candidate_events"]
    assert "scripts/vsa_audit_batch_review.py" in commands["batch_review"]
    assert "--min-priority high" in commands["candidate_events"]
    assert "--csv-output standard_basket_review.csv" in commands["batch_review"]


def test_standard_basket_url_rejects_too_small_max_symbols() -> None:
    try:
        build_vsa_audit_url(max_symbols=29)
    except ValueError as exc:
        assert "max_symbols" in str(exc)
    else:
        raise AssertionError("expected max_symbols validation error")


def test_standard_basket_cli_prints_json() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/vsa_standard_audit_basket.py", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["audit_only"] is True
    assert payload["symbol_count"] == 30
    assert payload["commands"]["save_audit"].startswith("curl.exe ")
    assert "LT.NS" in payload["symbols"]
