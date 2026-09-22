from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from audit.nse_session_clean_snapshot import (
    load_backfill_aliases,
    normalize_official_bhavcopy_frame,
    nse_symbol_for_backfill,
    repair_symbol_daily,
)


def test_normalizes_legacy_cm_bhavcopy_schema() -> None:
    frame = pd.DataFrame(
        [
            {
                "SYMBOL": "LT",
                "SERIES": "EQ",
                "OPEN": 100.0,
                "HIGH": 105.0,
                "LOW": 99.0,
                "CLOSE": 104.0,
                "TOTTRDQTY": 12345,
                "TIMESTAMP": "12-NOV-2023",
            },
            {
                "SYMBOL": "LT",
                "SERIES": "BE",
                "OPEN": 1.0,
                "HIGH": 1.0,
                "LOW": 1.0,
                "CLOSE": 1.0,
                "TOTTRDQTY": 1,
                "TIMESTAMP": "12-NOV-2023",
            },
        ]
    )

    result = normalize_official_bhavcopy_frame(
        frame,
        source_name="cm12NOV2023bhav.csv",
    )

    assert len(result) == 1
    row = result.iloc[0]
    assert row["nse_symbol"] == "LT"
    assert row["series"] == "EQ"
    assert row["session"] == pd.Timestamp("2023-11-12")
    assert row["close"] == 104.0
    assert row["volume"] == 12345


def test_normalizes_udiff_cm_bhavcopy_schema() -> None:
    frame = pd.DataFrame(
        [
            {
                "TckrSymb": "LT",
                "SctySrs": "EQ",
                "OpnPric": 200.0,
                "HghPric": 210.0,
                "LwPric": 198.0,
                "ClsPric": 207.0,
                "TtlTradgVol": 98765,
                "TradDt": "2026-02-01",
            }
        ]
    )

    result = normalize_official_bhavcopy_frame(
        frame,
        source_name="BhavCopy_NSE_CM.csv",
    )

    row = result.iloc[0]
    assert row["nse_symbol"] == "LT"
    assert row["session"] == pd.Timestamp("2026-02-01")
    assert row["open"] == 200.0
    assert row["close"] == 207.0
    assert row["volume"] == 98765


def test_filename_can_supply_session_when_legacy_frame_has_no_date() -> None:
    frame = pd.DataFrame(
        [
            {
                "SYMBOL": "LT",
                "SERIES": "EQ",
                "OPEN": 100.0,
                "HIGH": 101.0,
                "LOW": 99.0,
                "CLOSE": 100.5,
                "TOTTRDQTY": 1000,
            }
        ]
    )

    result = normalize_official_bhavcopy_frame(
        frame,
        source_name="cm18MAY2024bhav.csv",
    )

    assert result.iloc[0]["session"] == pd.Timestamp("2024-05-18")


def test_historical_tmpv_alias_is_pinned_only_for_required_sessions() -> None:
    aliases = load_backfill_aliases()

    assert (
        nse_symbol_for_backfill(
            "TMPV.NS",
            date(2024, 3, 1),
            aliases=aliases,
        )
        == "TATAMOTORS"
    )
    assert (
        nse_symbol_for_backfill(
            "TMPV.NS",
            date(2024, 3, 2),
            aliases=aliases,
        )
        == "TATAMOTORS"
    )
    assert (
        nse_symbol_for_backfill(
            "TMPV.NS",
            date(2026, 2, 1),
            aliases=aliases,
        )
        == "TMPV"
    )
    assert (
        nse_symbol_for_backfill(
            "M&M.NS",
            date(2024, 3, 2),
            aliases=aliases,
        )
        == "M&M"
    )


def _daily() -> pd.DataFrame:
    index = pd.DatetimeIndex(
        pd.to_datetime(
            [
                "2024-05-17",
                "2025-02-01",
                "2026-05-01",
                "2026-05-04",
            ]
        ),
        name="session",
    )
    return pd.DataFrame(
        {
            "open": [100.0, 120.0, 130.0, 131.0],
            "high": [102.0, 125.0, 130.0, 133.0],
            "low": [99.0, 119.0, 130.0, 129.0],
            "close": [101.0, 124.0, 130.0, 132.0],
            "volume": [1000.0, 2000.0, 0.0, 3000.0],
        },
        index=index,
    )


def _reference() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "session": pd.to_datetime(
                [
                    "2024-05-18",
                    "2025-02-01",
                    "2026-05-01",
                ]
            ),
            "expected_session": ["open", "open", "closed"],
            "event_type": [
                "special_weekend_session",
                "special_weekend_session",
                "weekday_holiday",
            ],
            "source_ref": ["A", "B", "C"],
        }
    )


def _bhavcopy() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "nse_symbol": "LT",
                "series": "EQ",
                "open": 500.0,
                "high": 510.0,
                "low": 495.0,
                "close": 505.0,
                "volume": 200.0,
                "session": pd.Timestamp("2024-05-17"),
                "source_path": "calibration.zip",
                "source_sha256": "cal",
                "source_member": "cm17MAY2024bhav.csv",
            },
            {
                "nse_symbol": "LT",
                "series": "EQ",
                "open": 505.0,
                "high": 530.0,
                "low": 500.0,
                "close": 525.0,
                "volume": 1000.0,
                "session": pd.Timestamp("2024-05-18"),
                "source_path": "official.zip",
                "source_sha256": "abc",
                "source_member": "cm18MAY2024bhav.csv",
            },
        ]
    )


def test_repair_adds_missing_special_session_keeps_existing_and_removes_placeholder() -> None:
    aliases: dict[tuple[str, date], str] = {}

    repaired, records = repair_symbol_daily(
        symbol="LT.NS",
        daily=_daily(),
        reference=_reference(),
        bhavcopy=_bhavcopy(),
        aliases=aliases,
    )

    assert pd.Timestamp("2024-05-18") in repaired.index
    assert pd.Timestamp("2025-02-01") in repaired.index
    assert pd.Timestamp("2026-05-01") not in repaired.index
    assert repaired.loc[pd.Timestamp("2024-05-18"), "close"] == 105.0
    assert repaired.loc[pd.Timestamp("2024-05-18"), "volume"] == 5000.0
    assert len(records) == 2
    assert {item.action for item in records} == {
        "ADD_OFFICIAL_SPECIAL_SESSION",
        "REMOVE_CLOSED_SESSION_PLACEHOLDER",
    }
    added = next(
        item
        for item in records
        if item.action == "ADD_OFFICIAL_SPECIAL_SESSION"
    )
    assert added.calibration_session == "2024-05-17"
    assert added.price_scale == pytest.approx(0.2)
    assert added.volume_scale == pytest.approx(5.0)


def test_repair_refuses_to_delete_real_shaped_row_on_closed_date() -> None:
    daily = _daily()
    daily.loc[pd.Timestamp("2026-05-01"), "high"] = 131.0

    with pytest.raises(ValueError, match="refusing to delete"):
        repair_symbol_daily(
            symbol="LT.NS",
            daily=daily,
            reference=_reference(),
            bhavcopy=_bhavcopy(),
            aliases={},
        )


def test_repair_requires_exact_official_eq_identity() -> None:
    with pytest.raises(ValueError, match="exactly one official EQ bhavcopy row"):
        repair_symbol_daily(
            symbol="LT.NS",
            daily=_daily(),
            reference=_reference(),
            bhavcopy=_bhavcopy().iloc[0:0],
            aliases={},
        )


def test_udiff_missing_or_nonpositive_prices_fail_closed() -> None:
    frame = pd.DataFrame(
        [
            {
                "TckrSymb": "LT",
                "SctySrs": "EQ",
                "OpnPric": 0,
                "HghPric": 210,
                "LwPric": 198,
                "ClsPric": 207,
                "TtlTradgVol": 10,
                "TradDt": "2026-02-01",
            }
        ]
    )

    with pytest.raises(ValueError, match="open must be positive"):
        normalize_official_bhavcopy_frame(
            frame,
            source_name="udiff.csv",
        )
