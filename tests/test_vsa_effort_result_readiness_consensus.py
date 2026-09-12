from __future__ import annotations

import json

import pandas as pd
import pytest

from audit.audit_effort_result_decision_value import (
    CONSENSUS_CANDIDATE,
    CONSENSUS_INCONSISTENT_DIRECTION,
    CONSENSUS_INSUFFICIENT_SAMPLE,
    CONSENSUS_OBSERVATION_ONLY,
    READINESS_CANDIDATE,
    READINESS_OBSERVATION_ONLY,
    audit,
    readiness_consensus,
)


def _readiness_row(
    *,
    horizon: int,
    scope: str = "effort_result_event",
    condition: str,
    bars: int,
    delta_vs_baseline: float,
    readiness: str = READINESS_CANDIDATE,
) -> dict[str, object]:
    return {
        "horizon": horizon,
        "scope": scope,
        "condition": condition,
        "bars": bars,
        "mean_forward_return": delta_vs_baseline,
        "up_rate": 0.50,
        "delta_vs_baseline": delta_vs_baseline,
        "readiness": readiness,
        "may_change_scoring": False,
        "may_change_ranking": False,
        "may_change_actionability": False,
        "may_activate_detector": False,
        "requires_separate_production_pr": True,
    }


def _csv(path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _event_payload(*codes: str) -> str:
    return json.dumps([{"code": code} for code in codes])


def test_readiness_consensus_promotes_only_consistent_multi_horizon_candidates() -> None:
    consensus = readiness_consensus(
        [
            _readiness_row(
                horizon=1,
                condition="EFFORT_GT_RESULT",
                bars=12,
                delta_vs_baseline=0.020,
            ),
            _readiness_row(
                horizon=2,
                condition="EFFORT_GT_RESULT",
                bars=11,
                delta_vs_baseline=0.015,
            ),
            _readiness_row(
                horizon=1,
                condition="RESULT_GT_EFFORT",
                bars=12,
                delta_vs_baseline=-0.020,
            ),
            _readiness_row(
                horizon=1,
                condition="ABSORPTION+high_effort_low_result",
                scope="effort_result_event_plus_relationship",
                bars=13,
                delta_vs_baseline=0.020,
            ),
            _readiness_row(
                horizon=2,
                condition="ABSORPTION+high_effort_low_result",
                scope="effort_result_event_plus_relationship",
                bars=13,
                delta_vs_baseline=-0.015,
            ),
            _readiness_row(
                horizon=1,
                condition="EFFORT_RESULT",
                bars=25,
                delta_vs_baseline=0.001,
                readiness=READINESS_OBSERVATION_ONLY,
            ),
            _readiness_row(
                horizon=1,
                scope="event",
                condition="UPTHRUST",
                bars=40,
                delta_vs_baseline=-0.030,
            ),
        ],
        min_horizons=2,
        min_candidate_bars=20,
    )
    by_condition = {row["condition"]: row for row in consensus}

    assert by_condition["EFFORT_GT_RESULT"]["consensus"] == CONSENSUS_CANDIDATE
    assert by_condition["EFFORT_GT_RESULT"]["candidate_direction"] == "positive"
    assert by_condition["EFFORT_GT_RESULT"]["candidate_horizons"] == [1, 2]
    assert by_condition["EFFORT_GT_RESULT"]["candidate_bars"] == 23

    assert (
        by_condition["RESULT_GT_EFFORT"]["consensus"]
        == CONSENSUS_INSUFFICIENT_SAMPLE
    )
    assert (
        by_condition["ABSORPTION+high_effort_low_result"]["consensus"]
        == CONSENSUS_INCONSISTENT_DIRECTION
    )
    assert by_condition["EFFORT_RESULT"]["consensus"] == CONSENSUS_OBSERVATION_ONLY
    assert "UPTHRUST" not in by_condition


def test_readiness_consensus_is_a_review_gate_not_production_permission() -> None:
    consensus = readiness_consensus(
        [
            _readiness_row(
                horizon=1,
                condition="EFFORT_GT_RESULT",
                bars=20,
                delta_vs_baseline=0.020,
            ),
            _readiness_row(
                horizon=2,
                condition="EFFORT_GT_RESULT",
                bars=20,
                delta_vs_baseline=0.010,
            ),
        ],
        min_horizons=2,
        min_candidate_bars=20,
    )

    assert consensus[0]["consensus"] == CONSENSUS_CANDIDATE
    assert consensus[0]["may_change_scoring"] is False
    assert consensus[0]["may_change_ranking"] is False
    assert consensus[0]["may_change_actionability"] is False
    assert consensus[0]["may_activate_detector"] is False
    assert consensus[0]["requires_manual_case_review"] is True
    assert consensus[0]["requires_separate_production_pr"] is True


def test_audit_includes_readiness_consensus_without_replay_or_production_changes(
    tmp_path,
) -> None:
    path = tmp_path / "historical_effort_result_validation.csv"
    rows: list[dict[str, object]] = []
    for symbol, base_close in (("LT.NS", 100.0), ("RELIANCE.NS", 200.0)):
        for bar_index in range(12):
            rows.append(
                {
                    "symbol": symbol,
                    "bar_index": bar_index,
                    "close": base_close + float(bar_index),
                    "volume_ratio": 2.0 if bar_index % 2 == 0 else 1.0,
                    "spread_ratio": 0.5 if bar_index % 2 == 0 else 1.0,
                    "existing_events": _event_payload("EvidenceCode.EFFORT_GT_RESULT")
                    if bar_index % 2 == 0
                    else "[]",
                }
            )
    _csv(path, rows)

    report = audit(path, horizons=(1, 2))

    assert report["audit_only"] is True
    assert report["readiness_consensus"]
    assert all(
        row["scope"] in {
            "effort_result_event",
            "effort_result_event_plus_relationship",
        }
        for row in report["readiness_consensus"]
    )
    assert all(
        row["may_change_scoring"] is False
        and row["may_change_ranking"] is False
        and row["may_change_actionability"] is False
        and row["may_activate_detector"] is False
        and row["requires_separate_production_pr"] is True
        for row in report["readiness_consensus"]
    )


def test_readiness_consensus_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="min_horizons"):
        readiness_consensus([], min_horizons=0)

    with pytest.raises(ValueError, match="min_candidate_bars"):
        readiness_consensus([], min_candidate_bars=0)
