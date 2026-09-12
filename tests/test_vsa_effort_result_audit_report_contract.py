from __future__ import annotations

import json

import pandas as pd

from audit.audit_effort_result_decision_value import CONSENSUS_CANDIDATE, audit


EXPECTED_REPORT_KEYS = {
    "source",
    "rows",
    "outcome_rows",
    "horizons",
    "thresholds",
    "comparisons",
    "readiness",
    "readiness_consensus",
    "audit_only",
}

PRODUCTION_PERMISSION_KEYS = (
    "may_change_scoring",
    "may_change_ranking",
    "may_change_actionability",
    "may_activate_detector",
)


def _csv(path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _event_payload(*codes: str) -> str:
    return json.dumps([{"code": code} for code in codes])


def _contract_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for symbol, offset in (("LT.NS", 0.0), ("RELIANCE.NS", 100.0)):
        closes = [100.0 + offset, 120.0 + offset, 100.0 + offset, 120.0 + offset, 130.0 + offset]
        for bar_index, close in enumerate(closes):
            rows.append(
                {
                    "symbol": symbol,
                    "bar_index": bar_index,
                    "close": close,
                    "volume_ratio": 2.0 if bar_index in {0, 2} else 1.0,
                    "spread_ratio": 0.5 if bar_index in {0, 2} else 1.0,
                    "existing_events": _event_payload("EvidenceCode.EFFORT_GT_RESULT")
                    if bar_index in {0, 2}
                    else "[]",
                }
            )
    return rows


def test_audit_report_contract_is_stable_and_json_serializable(tmp_path) -> None:
    path = tmp_path / "historical_effort_result_validation.csv"
    _csv(path, _contract_rows())

    report = audit(
        path,
        horizons=(1, 2),
        min_readiness_bars=4,
        min_readiness_abs_delta=0.001,
        min_consensus_horizons=2,
        min_consensus_candidate_bars=8,
    )

    assert set(report) == EXPECTED_REPORT_KEYS
    assert report["audit_only"] is True
    assert report["source"] == str(path)
    assert report["rows"] == 10
    assert report["outcome_rows"] == 14
    assert report["horizons"] == [1, 2]
    assert report["thresholds"] == {
        "readiness": {"min_bars": 4, "min_abs_delta": 0.001},
        "consensus": {"min_horizons": 2, "min_candidate_bars": 8},
    }

    # This is the saved artifact boundary: report output must remain plain JSON.
    json.dumps(report)


def test_audit_report_contract_preserves_review_only_permissions(tmp_path) -> None:
    path = tmp_path / "historical_effort_result_validation.csv"
    _csv(path, _contract_rows())

    report = audit(
        path,
        horizons=(1, 2),
        min_readiness_bars=4,
        min_readiness_abs_delta=0.001,
        min_consensus_horizons=2,
        min_consensus_candidate_bars=8,
    )

    assert report["readiness"]
    assert report["readiness_consensus"]
    assert all(
        row[key] is False
        for row in report["readiness"]
        for key in PRODUCTION_PERMISSION_KEYS
    )
    assert all(
        row[key] is False
        for row in report["readiness_consensus"]
        for key in PRODUCTION_PERMISSION_KEYS
    )
    assert all(
        row["requires_separate_production_pr"] is True
        for row in report["readiness"] + report["readiness_consensus"]
    )
    assert all(
        row["requires_manual_case_review"] is True
        for row in report["readiness_consensus"]
    )


def test_audit_report_contract_keeps_effort_result_consensus_separate_from_directional_events(tmp_path) -> None:
    path = tmp_path / "historical_effort_result_validation.csv"
    _csv(path, _contract_rows())

    report = audit(
        path,
        horizons=(1, 2),
        min_readiness_bars=4,
        min_readiness_abs_delta=0.001,
        min_consensus_horizons=2,
        min_consensus_candidate_bars=8,
    )
    consensus_by_condition = {
        (row["scope"], row["condition"]): row
        for row in report["readiness_consensus"]
    }

    effort_result_consensus = consensus_by_condition[
        ("effort_result_event", "EFFORT_GT_RESULT")
    ]
    assert effort_result_consensus["consensus"] == CONSENSUS_CANDIDATE
    assert effort_result_consensus["candidate_direction"] == "positive"
    assert effort_result_consensus["candidate_horizons"] == [1, 2]
    assert effort_result_consensus["candidate_bars"] == 8
    assert all(scope != "event" for scope, _ in consensus_by_condition)
