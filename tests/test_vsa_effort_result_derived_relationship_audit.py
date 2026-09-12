from __future__ import annotations

import json

import pandas as pd

from audit.audit_effort_result_decision_value import CONSENSUS_CANDIDATE, audit


def _csv(path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _event_payload(*codes: str) -> str:
    return json.dumps([{"code": code} for code in codes])


def _derived_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for symbol, offset in (("LT.NS", 0.0), ("RELIANCE.NS", 100.0)):
        closes = [
            100.0 + offset,
            120.0 + offset,
            100.0 + offset,
            120.0 + offset,
            130.0 + offset,
        ]
        for bar_index, close in enumerate(closes):
            rows.append(
                {
                    "symbol": symbol,
                    "bar_index": bar_index,
                    "close": close,
                    "volume_ratio": 2.0 if bar_index in {0, 2} else 1.0,
                    "spread_ratio": 0.5 if bar_index in {0, 2} else 1.0,
                    "existing_events": _event_payload("EvidenceCode.NO_SUPPLY")
                    if bar_index in {0, 2}
                    else "[]",
                }
            )
    return rows


def _by_scope_and_condition(
    rows: list[dict[str, object]],
) -> dict[tuple[str, str], dict[str, object]]:
    return {
        (str(row["scope"]), str(row["condition"])): row
        for row in rows
    }


def test_audit_derives_effort_result_review_scope_without_event_labels(tmp_path) -> None:
    path = tmp_path / "historical_effort_result_validation.csv"
    _csv(path, _derived_rows())

    report = audit(
        path,
        horizons=(1, 2),
        min_readiness_bars=4,
        min_readiness_abs_delta=0.001,
        min_consensus_horizons=2,
        min_consensus_candidate_bars=8,
    )

    readiness = _by_scope_and_condition(report["readiness"])
    consensus = _by_scope_and_condition(report["readiness_consensus"])

    assert ("effort_result_event", "EFFORT_GT_RESULT") not in readiness
    assert readiness[("effort_result_relationship", "EFFORT_GT_RESULT")][
        "readiness"
    ] == "candidate_for_calibration_review"
    assert consensus[("effort_result_relationship", "EFFORT_GT_RESULT")][
        "consensus"
    ] == CONSENSUS_CANDIDATE
    assert consensus[("effort_result_relationship", "EFFORT_GT_RESULT")][
        "candidate_direction"
    ] == "positive"


def test_audit_derives_effort_result_relationship_plus_existing_event_scope(
    tmp_path,
) -> None:
    path = tmp_path / "historical_effort_result_validation.csv"
    _csv(path, _derived_rows())

    report = audit(
        path,
        horizons=(1, 2),
        min_readiness_bars=4,
        min_readiness_abs_delta=0.001,
        min_consensus_horizons=2,
        min_consensus_candidate_bars=8,
    )

    consensus = _by_scope_and_condition(report["readiness_consensus"])
    row = consensus[("effort_result_relationship_plus_event", "EFFORT_GT_RESULT+NO_SUPPLY")]

    assert row["consensus"] == CONSENSUS_CANDIDATE
    assert row["candidate_horizons"] == [1, 2]
    assert row["candidate_bars"] == 8
    assert row["may_change_scoring"] is False
    assert row["may_change_ranking"] is False
    assert row["may_change_actionability"] is False
    assert row["may_activate_detector"] is False
    assert row["requires_manual_case_review"] is True
    assert row["requires_separate_production_pr"] is True
