from __future__ import annotations

import json

import pandas as pd
import pytest

from audit.audit_effort_result_decision_value import (
    EFFORT_RESULT_EVENTS,
    READINESS_CANDIDATE,
    READINESS_INSUFFICIENT_SAMPLE,
    READINESS_OBSERVATION_ONLY,
    audit,
    decision_value_readiness,
    events,
)


def _csv(path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _event_payload(*codes: str) -> str:
    return json.dumps([{"code": code} for code in codes])


def test_events_normalizes_effort_result_codes_from_engine_payloads() -> None:
    payload = json.dumps(
        [
            {"code": "EvidenceCode.EFFORT_GT_RESULT"},
            {"code": "absorption"},
            "EvidenceCode.RESULT_GT_EFFORT",
            "effort_result",
        ]
    )

    assert events(payload) == set(EFFORT_RESULT_EVENTS)


def test_audit_adds_effort_result_event_and_relationship_cohorts(tmp_path) -> None:
    path = tmp_path / "historical_effort_result_validation.csv"
    _csv(
        path,
        [
            {
                "symbol": "LT.NS",
                "bar_index": 0,
                "close": 100.0,
                "volume_ratio": 2.0,
                "spread_ratio": 0.5,
                "existing_events": _event_payload("EvidenceCode.EFFORT_GT_RESULT"),
            },
            {
                "symbol": "LT.NS",
                "bar_index": 1,
                "close": 110.0,
                "volume_ratio": 1.0,
                "spread_ratio": 1.0,
                "existing_events": "[]",
            },
            {
                "symbol": "LT.NS",
                "bar_index": 2,
                "close": 120.0,
                "volume_ratio": 0.5,
                "spread_ratio": 2.0,
                "existing_events": _event_payload("EvidenceCode.RESULT_GT_EFFORT"),
            },
            {
                "symbol": "LT.NS",
                "bar_index": 3,
                "close": 108.0,
                "volume_ratio": 1.0,
                "spread_ratio": 1.0,
                "existing_events": "[]",
            },
            {
                "symbol": "RELIANCE.NS",
                "bar_index": 0,
                "close": 200.0,
                "volume_ratio": 2.0,
                "spread_ratio": 2.0,
                "existing_events": _event_payload("EvidenceCode.ABSORPTION"),
            },
            {
                "symbol": "RELIANCE.NS",
                "bar_index": 1,
                "close": 198.0,
                "volume_ratio": 1.0,
                "spread_ratio": 1.0,
                "existing_events": _event_payload("EvidenceCode.EFFORT_RESULT"),
            },
            {
                "symbol": "RELIANCE.NS",
                "bar_index": 2,
                "close": 204.0,
                "volume_ratio": 1.0,
                "spread_ratio": 1.0,
                "existing_events": "[]",
            },
        ],
    )

    report = audit(path, horizons=(1,))
    cohorts = {
        (comparison["scope"], comparison["condition"])
        for comparison in report["comparisons"]
    }

    assert report["audit_only"] is True
    assert report["rows"] == 7
    assert report["outcome_rows"] == 5
    assert ("effort_result_event", "EFFORT_GT_RESULT") in cohorts
    assert ("effort_result_event", "RESULT_GT_EFFORT") in cohorts
    assert ("effort_result_event", "ABSORPTION") in cohorts
    assert ("effort_result_event", "EFFORT_RESULT") in cohorts
    assert (
        "effort_result_event_plus_relationship",
        "EFFORT_GT_RESULT+high_effort_low_result",
    ) in cohorts
    assert (
        "effort_result_event_plus_relationship",
        "RESULT_GT_EFFORT+low_effort_high_result",
    ) in cohorts
    assert report["readiness"]
    assert all(row["may_change_scoring"] is False for row in report["readiness"])
    assert all(row["may_change_ranking"] is False for row in report["readiness"])
    assert all(row["may_change_actionability"] is False for row in report["readiness"])
    assert all(row["may_activate_detector"] is False for row in report["readiness"])


def test_decision_value_readiness_is_review_only_not_production_permission() -> None:
    comparisons = [
        {
            "horizon": 1,
            "scope": "effort_result_event",
            "condition": "EFFORT_GT_RESULT",
            "bars": 5,
            "mean_forward_return": 0.025,
            "up_rate": 0.80,
            "delta_vs_baseline": 0.02,
        },
        {
            "horizon": 1,
            "scope": "effort_result_event",
            "condition": "RESULT_GT_EFFORT",
            "bars": 2,
            "mean_forward_return": -0.01,
            "up_rate": 0.25,
            "delta_vs_baseline": -0.02,
        },
        {
            "horizon": 1,
            "scope": "effort_result_event_plus_relationship",
            "condition": "ABSORPTION+high_effort_low_result",
            "bars": 5,
            "mean_forward_return": 0.004,
            "up_rate": 0.50,
            "delta_vs_baseline": 0.002,
        },
        {
            "horizon": 1,
            "scope": "event",
            "condition": "UPTHRUST",
            "bars": 20,
            "mean_forward_return": -0.02,
            "up_rate": 0.20,
            "delta_vs_baseline": -0.03,
        },
    ]

    readiness = decision_value_readiness(
        comparisons,
        min_bars=5,
        min_abs_delta=0.01,
    )

    assert [(row["condition"], row["readiness"]) for row in readiness] == [
        ("EFFORT_GT_RESULT", READINESS_CANDIDATE),
        ("RESULT_GT_EFFORT", READINESS_INSUFFICIENT_SAMPLE),
        (
            "ABSORPTION+high_effort_low_result",
            READINESS_OBSERVATION_ONLY,
        ),
    ]
    assert all(row["may_change_scoring"] is False for row in readiness)
    assert all(row["may_change_ranking"] is False for row in readiness)
    assert all(row["may_change_actionability"] is False for row in readiness)
    assert all(row["may_activate_detector"] is False for row in readiness)
    assert all(row["requires_separate_production_pr"] is True for row in readiness)


def test_readiness_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="min_bars"):
        decision_value_readiness([], min_bars=0)

    with pytest.raises(ValueError, match="min_abs_delta"):
        decision_value_readiness([], min_abs_delta=-0.01)
