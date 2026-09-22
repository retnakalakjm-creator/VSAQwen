from __future__ import annotations

from pathlib import Path

import pandas as pd

from audit.nse_session_integrity import (
    REFERENCE_END_SESSION,
    REFERENCE_START_SESSION,
    audit_symbol_session_integrity,
    load_nse_session_exception_reference,
)


def _daily(*sessions: str) -> pd.DataFrame:
    index = pd.DatetimeIndex(pd.to_datetime(list(sessions)), name="session")
    values = [100.0 + index for index in range(len(sessions))]
    return pd.DataFrame(
        {
            "open": values,
            "high": [value + 1.0 for value in values],
            "low": [value - 1.0 for value in values],
            "close": [value + 0.5 for value in values],
            "volume": [1_000.0 for _ in values],
        },
        index=index,
    )


def _reference(tmp_path: Path) -> Path:
    path = tmp_path / "reference.csv"
    path.write_text(
        "\n".join(
            [
                "session,expected_session,event_type,source_ref",
                "2026-05-01,closed,weekday_holiday,NSE-CMTR-71775",
                "2026-02-01,open,special_weekend_session,NSE-CMTR-72349",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_committed_reference_is_bounded_and_exception_only() -> None:
    reference = load_nse_session_exception_reference()

    assert reference["session"].min().date() >= REFERENCE_START_SESSION
    assert reference["session"].max().date() <= REFERENCE_END_SESSION
    assert set(reference["expected_session"]) == {"open", "closed"}

    closed = reference.loc[reference["expected_session"] == "closed"]
    opened = reference.loc[reference["expected_session"] == "open"]

    assert (closed["session"].dt.dayofweek < 5).all()
    assert (opened["session"].dt.dayofweek >= 5).all()
    assert pd.Timestamp("2026-05-01") in set(closed["session"])
    assert pd.Timestamp("2026-02-01") in set(opened["session"])


def test_detects_phantom_closed_row_and_missing_special_session(
    tmp_path: Path,
) -> None:
    reference = load_nse_session_exception_reference(_reference(tmp_path))
    daily = _daily("2026-01-30", "2026-02-02", "2026-05-01")
    daily.loc[pd.Timestamp("2026-05-01"), ["open", "high", "low", "close"]] = 123.0
    daily.loc[pd.Timestamp("2026-05-01"), "volume"] = 0.0

    summary, anomalies = audit_symbol_session_integrity(
        symbol="LT.NS",
        daily=daily,
        reference=reference,
    )

    assert summary.unexpected_closed_row_count == 1
    assert summary.missing_special_session_row_count == 1
    assert summary.unexpected_closed_flat_zero_volume_count == 1
    assert set(anomalies["anomaly"]) == {
        "UNEXPECTED_CLOSED_SESSION_ROW",
        "MISSING_SPECIAL_SESSION_ROW",
    }


def test_valid_exception_handling_produces_no_anomaly(tmp_path: Path) -> None:
    reference = load_nse_session_exception_reference(_reference(tmp_path))
    daily = _daily("2026-01-30", "2026-02-01", "2026-02-02", "2026-05-04")

    summary, anomalies = audit_symbol_session_integrity(
        symbol="LT.NS",
        daily=daily,
        reference=reference,
    )

    assert summary.anomaly_count == 0
    assert anomalies.empty


def test_unreferenced_weekend_row_fails_visible_as_unknown(tmp_path: Path) -> None:
    reference = load_nse_session_exception_reference(_reference(tmp_path))
    daily = _daily("2026-01-30", "2026-02-01", "2026-02-07", "2026-02-09")

    summary, anomalies = audit_symbol_session_integrity(
        symbol="LT.NS",
        daily=daily,
        reference=reference,
    )

    assert summary.unreferenced_weekend_row_count == 1
    row = anomalies.loc[
        anomalies["anomaly"] == "UNREFERENCED_WEEKEND_ROW"
    ].iloc[0]
    assert row["session"] == "2026-02-07"
    assert row["expected_session"] == "unknown"
