from __future__ import annotations

import json
import subprocess
import sys
from urllib.parse import parse_qs, urlparse

from vsa_standard_audit_basket import (
    EXPANDED_VSA_AUDIT_BASKET_NAME,
    EXPANDED_VSA_AUDIT_MAX_SYMBOLS,
    MIDCAP_FOCUS_VSA_AUDIT_BASKET_NAME,
    MIDCAP_FOCUS_VSA_AUDIT_MAX_SYMBOLS,
    STANDARD_VSA_AUDIT_BASKET_NAME,
    STANDARD_VSA_AUDIT_MAX_SYMBOLS,
    STANDARD_VSA_AUDIT_SYMBOLS,
    build_standard_basket_commands,
    build_vsa_audit_url,
    format_basket_symbols,
    get_standard_vsa_audit_basket,
    get_vsa_audit_basket,
    list_vsa_audit_basket_names,
)


def test_standard_basket_has_exactly_thirty_unique_nse_symbols() -> None:
    basket = get_standard_vsa_audit_basket()

    assert basket.audit_only is True
    assert basket.name == STANDARD_VSA_AUDIT_BASKET_NAME
    assert basket.max_symbols == STANDARD_VSA_AUDIT_MAX_SYMBOLS == 30
    assert len(basket.symbols) == 30
    assert len(set(basket.symbols)) == 30
    assert basket.symbols == STANDARD_VSA_AUDIT_SYMBOLS
    assert all(symbol.endswith(".NS") for symbol in basket.symbols)
    assert all(symbol == symbol.upper() for symbol in basket.symbols)
    assert {"LT.NS", "RELIANCE.NS", "SRF.NS"}.issubset(set(basket.symbols))


def test_expanded_large_mid_basket_keeps_standard_baseline_and_adds_symbols() -> None:
    standard = get_standard_vsa_audit_basket()
    expanded = get_vsa_audit_basket(EXPANDED_VSA_AUDIT_BASKET_NAME)

    assert expanded.audit_only is True
    assert expanded.max_symbols == EXPANDED_VSA_AUDIT_MAX_SYMBOLS == 60
    assert len(expanded.symbols) == 60
    assert len(set(expanded.symbols)) == 60
    assert expanded.symbols[:30] == standard.symbols
    assert {"SBICARD.NS", "HAL.NS", "TRENT.NS", "BANKBARODA.NS"}.issubset(set(expanded.symbols))


def test_midcap_focus_basket_has_own_thirty_symbol_noise_baseline() -> None:
    basket = get_vsa_audit_basket(MIDCAP_FOCUS_VSA_AUDIT_BASKET_NAME)

    assert basket.audit_only is True
    assert basket.max_symbols == MIDCAP_FOCUS_VSA_AUDIT_MAX_SYMBOLS == 30
    assert len(basket.symbols) == 30
    assert len(set(basket.symbols)) == 30
    assert {"SBICARD.NS", "AUBANK.NS", "PERSISTENT.NS", "POLYCAB.NS"}.issubset(set(basket.symbols))


def test_all_named_baskets_have_unique_uppercase_nse_symbols() -> None:
    for name in list_vsa_audit_basket_names():
        basket = get_vsa_audit_basket(name)
        assert basket.max_symbols == len(basket.symbols)
        assert len(set(basket.symbols)) == len(basket.symbols)
        assert all(symbol.endswith(".NS") for symbol in basket.symbols)
        assert all(symbol == symbol.upper() for symbol in basket.symbols)


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


def test_expanded_basket_builds_repeatable_audit_url() -> None:
    url = build_vsa_audit_url(basket_name=EXPANDED_VSA_AUDIT_BASKET_NAME)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.path == "/api/vsa-audit/events"
    assert query["start_week"] == ["2026-03-02"]
    assert query["horizon_weeks"] == ["8"]
    assert query["max_symbols"] == ["60"]
    assert len(query["symbols"][0].split(",")) == 60


def test_standard_basket_commands_chain_existing_audit_tools() -> None:
    commands = build_standard_basket_commands()

    assert commands["audit_url"].startswith("http://127.0.0.1:8000/api/vsa-audit/events?")
    assert commands["save_audit"].startswith("curl.exe ")
    assert "standard_basket_audit.json" in commands["save_audit"]
    assert "scripts/vsa_audit_candidate_events.py" in commands["candidate_events"]
    assert "scripts/vsa_audit_batch_review.py" in commands["batch_review"]
    assert "--min-priority high" in commands["candidate_events"]
    assert "--csv-output standard_basket_review.csv" in commands["batch_review"]


def test_expanded_basket_commands_use_distinct_output_files() -> None:
    commands = build_standard_basket_commands(basket_name=EXPANDED_VSA_AUDIT_BASKET_NAME)

    assert "max_symbols=60" in commands["audit_url"]
    assert "expanded_large_mid_basket_audit.json" in commands["save_audit"]
    assert "expanded_large_mid_basket_candidate_events_high.json" in commands["candidate_events"]
    assert "expanded_large_mid_basket_review.csv" in commands["batch_review"]


def test_standard_basket_url_rejects_too_small_max_symbols() -> None:
    try:
        build_vsa_audit_url(max_symbols=29)
    except ValueError as exc:
        assert "max_symbols" in str(exc)
    else:
        raise AssertionError("expected max_symbols validation error")


def test_unknown_basket_name_is_rejected() -> None:
    try:
        get_vsa_audit_basket("unknown")
    except ValueError as exc:
        assert "unknown VSA audit basket" in str(exc)
    else:
        raise AssertionError("expected unknown basket validation error")


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
    assert payload["name"] == STANDARD_VSA_AUDIT_BASKET_NAME
    assert payload["symbol_count"] == 30
    assert payload["commands"]["save_audit"].startswith("curl.exe ")
    assert "LT.NS" in payload["symbols"]


def test_expanded_basket_cli_prints_json() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/vsa_standard_audit_basket.py",
            "--basket",
            EXPANDED_VSA_AUDIT_BASKET_NAME,
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["audit_only"] is True
    assert payload["name"] == EXPANDED_VSA_AUDIT_BASKET_NAME
    assert payload["symbol_count"] == 60
    assert payload["commands"]["save_audit"].startswith("curl.exe ")
    assert "SBICARD.NS" in payload["symbols"]
