from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd

from engine.columns import COL_CLOSE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME, COL_WEEK
from weekly_audit_input_reproducibility import (
    compare_weekly_audit_inputs,
    fingerprint_weekly_audit_input,
)


def _weekly() -> pd.DataFrame:
    return pd.DataFrame(
        {
            COL_WEEK: ["2026-01-05", "2026-01-12", "2026-01-19"],
            COL_OPEN: [100.0, 102.0, 101.0],
            COL_HIGH: [104.0, 105.0, 106.0],
            COL_LOW: [99.0, 100.0, 100.5],
            COL_CLOSE: [103.0, 101.0, 105.0],
            COL_VOLUME: [1_000_000.0, 900_000.0, 1_200_000.0],
        }
    )


def test_fingerprint_is_deterministic_and_descriptive() -> None:
    frame = _weekly()
    first = fingerprint_weekly_audit_input("abc.ns", frame)
    second = fingerprint_weekly_audit_input("ABC.NS", frame.copy())

    assert first == second
    assert first.symbol == "ABC.NS"
    assert first.row_count == 3
    assert first.first_week.startswith("2026-01-05")
    assert first.last_week.startswith("2026-01-19")
    assert len(first.sha256) == 64


def test_fingerprint_changes_when_market_input_changes() -> None:
    original = _weekly()
    changed = original.copy()
    changed.loc[1, COL_CLOSE] = 101.25

    assert (
        fingerprint_weekly_audit_input("ABC.NS", original).sha256
        != fingerprint_weekly_audit_input("ABC.NS", changed).sha256
    )


def test_fingerprint_preserves_row_order() -> None:
    original = _weekly()
    reversed_rows = original.iloc[::-1].reset_index(drop=True)

    assert (
        fingerprint_weekly_audit_input("ABC.NS", original).sha256
        != fingerprint_weekly_audit_input("ABC.NS", reversed_rows).sha256
    )


def test_comparison_reports_exact_mismatch_fields() -> None:
    original = fingerprint_weekly_audit_input("ABC.NS", _weekly())
    changed_frame = _weekly()
    changed_frame.loc[2, COL_VOLUME] += 1.0
    changed = fingerprint_weekly_audit_input("ABC.NS", changed_frame)
    other = fingerprint_weekly_audit_input("XYZ.NS", _weekly())

    comparison = compare_weekly_audit_inputs((original,), (changed, other))

    assert comparison.matches is False
    assert comparison.missing_from_left == ("XYZ.NS",)
    assert comparison.missing_from_right == ()
    assert len(comparison.mismatches) == 1
    assert comparison.mismatches[0].symbol == "ABC.NS"
    assert comparison.mismatches[0].fields == ("sha256",)


def test_reproducible_runner_fingerprints_exact_transform_input(monkeypatch, tmp_path) -> None:
    import audit.weekly_input_reproducibility_runner as runner

    daily = pd.DataFrame({"unused": [1, 2, 3]})
    weekly = _weekly()

    def fake_download(symbol: str) -> pd.DataFrame:
        assert symbol == "ABC.NS"
        return daily.copy()

    def fake_foundation(symbols, **kwargs):
        assert tuple(symbols) == ("ABC.NS",)
        loaded = kwargs["daily_loader"]("ABC.NS")
        assert loaded.equals(daily)
        captured_weekly = kwargs["weekly_transformer"](loaded)
        assert captured_weekly.equals(weekly)
        return SimpleNamespace(symbols=("ABC.NS",), audited_bars=12)

    monkeypatch.setattr(runner, "_default_weekly_transformer", lambda _: weekly.copy())
    monkeypatch.setattr(runner, "run_weekly_foundation_historical_study", fake_foundation)

    study = runner.run_reproducible_weekly_foundation_study(
        ("ABC.NS",),
        daily_loader=fake_download,
    )

    expected = fingerprint_weekly_audit_input("ABC.NS", weekly)
    assert study.input_fingerprints == (expected,)
    assert study.is_actionable is False

    paths = runner.write_weekly_input_fingerprint_bundle(study, tmp_path)
    payload = json.loads(paths.manifest_json.read_text(encoding="utf-8"))
    assert payload["is_actionable"] is False
    assert payload["fingerprints"][0]["sha256"] == expected.sha256
    assert paths.manifest_csv.exists()
