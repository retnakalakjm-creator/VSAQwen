from __future__ import annotations

from market_data import (
    MARKET_DATA_PROVIDER_ENV,
    PROVIDER_UPSTOX,
    UPSTOX_ACCESS_TOKEN_ENV_VAR_ENV,
    UPSTOX_ENABLED_ENV,
    UPSTOX_SYMBOL_MAP_ENV,
)
from tools.check_upstox_provider_config import main


def _clear_upstox_env(monkeypatch) -> None:
    for name in (
        MARKET_DATA_PROVIDER_ENV,
        UPSTOX_ENABLED_ENV,
        UPSTOX_ACCESS_TOKEN_ENV_VAR_ENV,
        UPSTOX_SYMBOL_MAP_ENV,
        "UPSTOX_ACCESS_TOKEN",
        "TEST_UPSTOX_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)


def test_checker_accepts_default_yfinance_without_upstox(monkeypatch, capsys) -> None:
    _clear_upstox_env(monkeypatch)

    assert main([]) == 0

    output = capsys.readouterr().out
    assert "active_provider: yfinance" in output
    assert "upstox_selected: no" in output
    assert "UPSTOX_ACCESS_TOKEN" not in output


def test_checker_reports_upstox_not_ready_without_token_or_symbol_mapping(
    monkeypatch,
    capsys,
) -> None:
    _clear_upstox_env(monkeypatch)
    monkeypatch.setenv(MARKET_DATA_PROVIDER_ENV, PROVIDER_UPSTOX)

    assert main(["--symbol", "SRF.NS"]) == 1

    output = capsys.readouterr().out
    assert "upstox_selected: yes" in output
    assert "upstox_enabled: no" in output
    assert "token_present: no" in output
    assert "symbol_mapped: no" in output
    assert "result: not_ready" in output


def test_checker_reports_ready_upstox_without_leaking_token_value(
    monkeypatch,
    capsys,
) -> None:
    _clear_upstox_env(monkeypatch)
    monkeypatch.setenv(MARKET_DATA_PROVIDER_ENV, PROVIDER_UPSTOX)
    monkeypatch.setenv(UPSTOX_ENABLED_ENV, "true")
    monkeypatch.setenv(UPSTOX_ACCESS_TOKEN_ENV_VAR_ENV, "TEST_UPSTOX_TOKEN")
    monkeypatch.setenv("TEST_UPSTOX_TOKEN", "secret-token-value")
    monkeypatch.setenv(UPSTOX_SYMBOL_MAP_ENV, "SRF.NS=NSE_EQ|INE647A01010")

    assert main(["--symbol", "SRF.NS"]) == 0

    output = capsys.readouterr().out
    assert "active_provider: upstox" in output
    assert "upstox_enabled: yes" in output
    assert "token_env: TEST_UPSTOX_TOKEN" in output
    assert "token_present: yes" in output
    assert "symbol_mapped: yes" in output
    assert "result: ready" in output
    assert "secret-token-value" not in output
