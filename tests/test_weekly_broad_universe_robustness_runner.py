from __future__ import annotations

from types import SimpleNamespace

import pytest

from audit.weekly_broad_universe_robustness_runner import (
    preflight_weekly_research_universe,
    run_weekly_broad_universe_robustness_study,
)
from weekly_audit_input_reproducibility import WeeklyAuditInputFingerprint


COLUMNS = ("week_beginning", "open", "high", "low", "close", "volume")


def _fingerprint(symbol: str, digest: str = "a" * 64) -> WeeklyAuditInputFingerprint:
    return WeeklyAuditInputFingerprint(
        symbol=symbol,
        version="weekly-ohlcv-v1",
        row_count=100,
        first_week="2020-01-06T00:00:00",
        last_week="2026-09-07T00:00:00",
        sha256=digest,
        columns=COLUMNS,
    )


def test_preflight_is_fail_fast_by_default() -> None:
    calls: list[str] = []

    def preflight_one(symbol: str) -> WeeklyAuditInputFingerprint:
        calls.append(symbol)
        if symbol == "BAD.NS":
            raise RuntimeError("download failed")
        return _fingerprint(symbol)

    with pytest.raises(RuntimeError, match="download failed"):
        preflight_weekly_research_universe(
            ("GOOD.NS", "BAD.NS", "LATER.NS"),
            preflight_one=preflight_one,
        )

    assert calls == ["GOOD.NS", "BAD.NS"]


def test_opt_in_continuation_records_every_failed_symbol_and_preserves_success_order() -> None:
    def preflight_one(symbol: str) -> WeeklyAuditInputFingerprint:
        if symbol in {"BAD1.NS", "BAD2.NS"}:
            raise ValueError(f"no usable history for {symbol}")
        return _fingerprint(symbol)

    result = preflight_weekly_research_universe(
        ("GOOD1.NS", "BAD1.NS", "GOOD2.NS", "BAD2.NS"),
        preflight_one=preflight_one,
        continue_on_symbol_error=True,
    )

    assert result.requested_symbols == (
        "GOOD1.NS",
        "BAD1.NS",
        "GOOD2.NS",
        "BAD2.NS",
    )
    assert result.successful_symbols == ("GOOD1.NS", "GOOD2.NS")
    assert result.failed_symbols == ("BAD1.NS", "BAD2.NS")
    assert tuple(item.stage for item in result.failures) == ("preflight", "preflight")
    assert all(item.error_type == "ValueError" for item in result.failures)
    assert tuple(item.symbol for item in result.input_fingerprints) == (
        "GOOD1.NS",
        "GOOD2.NS",
    )


def test_external_fingerprint_mismatch_is_visible_in_failure_ledger() -> None:
    expected = (
        _fingerprint("GOOD.NS", "a" * 64),
        _fingerprint("CHANGED.NS", "b" * 64),
    )

    def preflight_one(symbol: str) -> WeeklyAuditInputFingerprint:
        if symbol == "CHANGED.NS":
            return _fingerprint(symbol, "c" * 64)
        return _fingerprint(symbol, "a" * 64)

    result = preflight_weekly_research_universe(
        ("GOOD.NS", "CHANGED.NS"),
        preflight_one=preflight_one,
        expected_fingerprints=expected,
        continue_on_symbol_error=True,
    )

    assert result.successful_symbols == ("GOOD.NS",)
    assert result.failed_symbols == ("CHANGED.NS",)
    failure = result.failures[0]
    assert failure.stage == "fingerprint_gate"
    assert failure.error_type == "_FingerprintGateError"
    assert "sha256" in failure.message
    assert result.external_baseline_used is True


def test_continuation_refuses_to_silently_produce_empty_universe() -> None:
    def preflight_one(symbol: str) -> WeeklyAuditInputFingerprint:
        raise RuntimeError(f"failed {symbol}")

    with pytest.raises(ValueError, match="no symbols survived"):
        preflight_weekly_research_universe(
            ("BAD1.NS", "BAD2.NS"),
            preflight_one=preflight_one,
            continue_on_symbol_error=True,
        )


def test_broad_runner_feeds_only_survivors_into_unchanged_wf7c1_analysis() -> None:
    captured: dict[str, object] = {}

    def preflight_one(symbol: str) -> WeeklyAuditInputFingerprint:
        if symbol == "BAD.NS":
            raise RuntimeError("provider failure")
        return _fingerprint(symbol, ("a" if symbol == "ONE.NS" else "b") * 64)

    analysis = SimpleNamespace(
        fingerprint_comparison=SimpleNamespace(matches=True),
    )

    def analysis_runner(symbols, **kwargs):
        captured["symbols"] = tuple(symbols)
        captured.update(kwargs)
        return analysis

    result = run_weekly_broad_universe_robustness_study(
        ("ONE.NS", "BAD.NS", "TWO.NS"),
        horizons_weeks=(15, 5, 10, 10),
        out_of_sample_start_week="2024-01-01",
        continue_on_symbol_error=True,
        preflight_one=preflight_one,
        analysis_runner=analysis_runner,
    )

    assert result.preflight.successful_symbols == ("ONE.NS", "TWO.NS")
    assert result.preflight.failed_symbols == ("BAD.NS",)
    assert captured["symbols"] == ("ONE.NS", "TWO.NS")
    assert captured["horizons_weeks"] == (5, 10, 15)
    assert captured["out_of_sample_start_week"] == "2024-01-01"
    expected = captured["expected_fingerprints"]
    assert tuple(item.symbol for item in expected) == ("ONE.NS", "TWO.NS")
    assert result.is_actionable is False


def test_broad_runner_rejects_aggregate_data_drift_after_preflight() -> None:
    analysis = SimpleNamespace(
        fingerprint_comparison=SimpleNamespace(matches=False),
    )

    with pytest.raises(RuntimeError, match="did not match preflight fingerprints"):
        run_weekly_broad_universe_robustness_study(
            ("ONE.NS",),
            preflight_one=lambda symbol: _fingerprint(symbol),
            analysis_runner=lambda symbols, **kwargs: analysis,
        )
