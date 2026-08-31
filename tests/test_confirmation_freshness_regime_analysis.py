from __future__ import annotations

from tests.confirmation_freshness_regime_analysis import summarize


def test_summary_splits_code_change_and_trend_state() -> None:
    rows = [
        {
            "confirmation_only_codes": "increasing_demand",
            "change": "False->True",
            "trend_state": "TrendState.HEALTHY",
            "confirmation_age": 0,
            "forward_return": 0.02,
            "mfe": 0.03,
            "mae": 0.01,
        },
        {
            "confirmation_only_codes": "increasing_demand",
            "change": "False->True",
            "trend_state": "TrendState.HEALTHY",
            "confirmation_age": 2,
            "forward_return": 0.04,
            "mfe": 0.05,
            "mae": 0.02,
        },
    ]

    result = summarize(rows)

    assert result == [
        {
            "code": "increasing_demand",
            "change": "False->True",
            "trend_state": "TrendState.HEALTHY",
            "cases": 2,
            "mean_age": 1.0,
            "current_or_recent": 1,
            "mean_return": 0.03,
            "mean_mfe": 0.04,
            "mean_mae": 0.015,
        }
    ]


def test_summary_handles_multiple_confirmation_codes() -> None:
    rows = [
        {
            "confirmation_only_codes": "increasing_demand,selling_climax",
            "change": "False->True",
            "trend_state": "TrendState.DEVELOPING",
            "confirmation_age": 1,
            "forward_return": 0.01,
            "mfe": 0.02,
            "mae": 0.03,
        }
    ]

    result = summarize(rows)

    assert [row["code"] for row in result] == ["increasing_demand", "selling_climax"]
    assert all(row["cases"] == 1 for row in result)
