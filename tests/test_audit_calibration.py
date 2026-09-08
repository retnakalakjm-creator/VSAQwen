from __future__ import annotations

import pytest
import pandas as pd

from audit.calibration import (
    completed_scored_frame,
    explode_evidence_codes,
    rank_calibration_summary,
    summarize_evidence_outcomes,
    summarize_outcomes,
    summarize_qualification_outcomes,
)


def _candidate_outcome_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "AAA.NS",
                "horizon_bars": 2,
                "side": "long",
                "qualification": "persistent_bullish",
                "outcome_available": True,
                "complete": True,
                "actionable": True,
                "signal_bar_anomaly": False,
                "scoring_evidence_codes": "stopping_volume|no_supply",
                "target_bar_evidence_codes": "stopping_volume",
                "favorable_return": 0.10,
                "raw_return": 0.10,
                "mfe": 0.14,
                "mae": -0.02,
            },
            {
                "symbol": "BBB.NS",
                "horizon_bars": 2,
                "side": "long",
                "qualification": "persistent_bullish",
                "outcome_available": True,
                "complete": True,
                "actionable": True,
                "signal_bar_anomaly": False,
                "scoring_evidence_codes": "stopping_volume",
                "target_bar_evidence_codes": "stopping_volume",
                "favorable_return": -0.04,
                "raw_return": -0.04,
                "mfe": 0.03,
                "mae": -0.08,
            },
            {
                "symbol": "CCC.NS",
                "horizon_bars": 2,
                "side": "short",
                "qualification": "persistent_bearish",
                "outcome_available": True,
                "complete": True,
                "actionable": False,
                "signal_bar_anomaly": True,
                "scoring_evidence_codes": "upthrust",
                "target_bar_evidence_codes": "upthrust",
                "favorable_return": 0.06,
                "raw_return": -0.06,
                "mfe": 0.08,
                "mae": -0.01,
            },
            {
                "symbol": "DDD.NS",
                "horizon_bars": 4,
                "side": "long",
                "qualification": "persistent_bullish",
                "outcome_available": True,
                "complete": False,
                "actionable": True,
                "signal_bar_anomaly": False,
                "scoring_evidence_codes": "stopping_volume",
                "target_bar_evidence_codes": "stopping_volume",
                "favorable_return": 0.20,
                "raw_return": 0.20,
                "mfe": 0.25,
                "mae": -0.02,
            },
            {
                "symbol": "EEE.NS",
                "horizon_bars": 4,
                "side": "long",
                "qualification": "persistent_bullish",
                "outcome_available": False,
                "complete": False,
                "actionable": True,
                "signal_bar_anomaly": False,
                "scoring_evidence_codes": "no_supply",
                "target_bar_evidence_codes": "no_supply",
                "favorable_return": None,
                "raw_return": None,
                "mfe": None,
                "mae": None,
            },
        ]
    )


def test_completed_scored_frame_filters_unavailable_and_partial_rows() -> None:
    frame = _candidate_outcome_frame()

    scored = completed_scored_frame(frame)

    assert list(scored["symbol"]) == ["AAA.NS", "BBB.NS", "CCC.NS"]


def test_completed_scored_frame_can_include_partial_diagnostics() -> None:
    frame = _candidate_outcome_frame()

    scored = completed_scored_frame(frame, require_complete=False)

    assert list(scored["symbol"]) == ["AAA.NS", "BBB.NS", "CCC.NS", "DDD.NS"]


def test_explode_evidence_codes_creates_one_row_per_code() -> None:
    frame = _candidate_outcome_frame().iloc[:2]

    exploded = explode_evidence_codes(frame)

    assert list(exploded["evidence_code"]) == ["stopping_volume", "no_supply", "stopping_volume"]
    assert list(exploded["symbol"]) == ["AAA.NS", "AAA.NS", "BBB.NS"]


def test_summarize_evidence_outcomes_groups_by_evidence_horizon_and_side() -> None:
    frame = _candidate_outcome_frame()

    summary = summarize_evidence_outcomes(frame, min_samples=1)

    stopping = summary[summary["group_key"] == "stopping_volume|2|long"].iloc[0]
    assert stopping["sample_count"] == 2
    assert stopping["symbol_count"] == 2
    assert stopping["win_rate"] == 0.5
    assert stopping["avg_favorable_return"] == pytest.approx(0.03)
    assert stopping["median_favorable_return"] == pytest.approx(0.03)
    assert stopping["avg_raw_return"] == pytest.approx(0.03)
    assert stopping["avg_mfe"] == pytest.approx(0.085)
    assert stopping["avg_mae"] == pytest.approx(-0.05)

    upthrust = summary[summary["group_key"] == "upthrust|2|short"].iloc[0]
    assert upthrust["sample_count"] == 1
    assert upthrust["win_rate"] == 1.0
    assert upthrust["actionable_rate"] == 0.0
    assert upthrust["anomaly_rate"] == 1.0


def test_summarize_evidence_outcomes_applies_min_sample_gate() -> None:
    frame = _candidate_outcome_frame()

    summary = summarize_evidence_outcomes(frame, min_samples=2)

    assert list(summary["group_key"]) == ["stopping_volume|2|long"]


def test_summarize_qualification_outcomes_groups_candidate_segments() -> None:
    frame = _candidate_outcome_frame()

    summary = summarize_qualification_outcomes(frame)

    assert set(summary["group_key"]) == {
        "persistent_bullish|2|long",
        "persistent_bearish|2|short",
    }


def test_summarize_outcomes_accepts_custom_grouping() -> None:
    frame = completed_scored_frame(_candidate_outcome_frame())

    summary = summarize_outcomes(frame, group_by="side")

    assert set(summary["group_key"]) == {"long", "short"}
    long_row = summary[summary["group_key"] == "long"].iloc[0]
    assert long_row["sample_count"] == 2
    assert long_row["horizon_bars"] == 2
    assert long_row["side"] == "long"


def test_rank_calibration_summary_orders_best_groups_first() -> None:
    frame = _candidate_outcome_frame()
    summary = summarize_evidence_outcomes(frame)

    ranked = rank_calibration_summary(summary)

    assert ranked.iloc[0]["avg_favorable_return"] >= ranked.iloc[-1]["avg_favorable_return"]


def test_missing_required_columns_raise_clear_error() -> None:
    with pytest.raises(ValueError, match="Missing required calibration columns"):
        completed_scored_frame(pd.DataFrame({"complete": [True]}))

    with pytest.raises(ValueError, match="Missing required calibration columns"):
        summarize_outcomes(pd.DataFrame({"side": ["long"]}), group_by="side")


def test_invalid_min_samples_is_rejected() -> None:
    frame = completed_scored_frame(_candidate_outcome_frame())

    with pytest.raises(ValueError, match="min_samples"):
        summarize_outcomes(frame, group_by="side", min_samples=0)

    summary = summarize_outcomes(frame, group_by="side")
    with pytest.raises(ValueError, match="min_samples"):
        rank_calibration_summary(summary, min_samples=0)
