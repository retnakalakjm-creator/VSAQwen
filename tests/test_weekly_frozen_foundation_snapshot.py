from __future__ import annotations

from types import SimpleNamespace

import pytest

import audit.weekly_opposite_supported_thesis_runner as runner
from audit.weekly_input_reproducibility_runner import (
    ReproducibleWeeklyFoundationSnapshot,
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


def test_wf7c1_frozen_snapshot_bypasses_foundation_rerun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fingerprint = _fingerprint("ONE.NS")
    symbol_result = SimpleNamespace(
        symbol="ONE.NS",
        audits=(),
        prices=(),
        out_of_sample_start_bar_index=None,
    )
    snapshot = ReproducibleWeeklyFoundationSnapshot(
        symbols=("ONE.NS",),
        horizons_weeks=(5, 10, 15),
        symbol_results=(symbol_result,),
        input_fingerprints=(fingerprint,),
    )

    def forbidden_rerun(*args, **kwargs):
        raise AssertionError("full weekly foundation rerun must not be called")

    monkeypatch.setattr(
        runner,
        "run_reproducible_weekly_foundation_study",
        forbidden_rerun,
    )
    monkeypatch.setattr(
        runner.WeeklyActionabilityCounterfactualEngine,
        "audit",
        staticmethod(lambda **kwargs: SimpleNamespace()),
    )
    monkeypatch.setattr(
        runner.WeeklyContradictionReasonAuditEngine,
        "audit",
        staticmethod(lambda **kwargs: SimpleNamespace()),
    )
    report = SimpleNamespace()
    monkeypatch.setattr(
        runner.WeeklyOppositeSupportedThesisAuditEngine,
        "audit",
        staticmethod(lambda **kwargs: report),
    )

    study = runner.run_reproducible_weekly_opposite_supported_study(
        ("ONE.NS",),
        expected_fingerprints=(fingerprint,),
        horizons_weeks=(5, 10, 15),
        foundation_snapshot=snapshot,
    )

    assert study.report is report
    assert study.input_fingerprints == (fingerprint,)
    assert study.fingerprint_comparison.matches is True
    assert study.is_actionable is False


def test_wf7c1_rejects_frozen_snapshot_identity_mismatch() -> None:
    snapshot = ReproducibleWeeklyFoundationSnapshot(
        symbols=("TWO.NS",),
        horizons_weeks=(5, 10, 15),
        symbol_results=(),
        input_fingerprints=(_fingerprint("TWO.NS"),),
    )

    with pytest.raises(ValueError, match="symbols do not match"):
        runner.run_reproducible_weekly_opposite_supported_study(
            ("ONE.NS",),
            expected_fingerprints=(_fingerprint("ONE.NS"),),
            horizons_weeks=(5, 10, 15),
            foundation_snapshot=snapshot,
        )
