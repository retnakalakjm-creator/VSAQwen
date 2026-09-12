from __future__ import annotations

import json

import pandas as pd
import pytest

from audit.audit_effort_result_decision_value import (
    CONSENSUS_CANDIDATE,
    CONSENSUS_OBSERVATION_ONLY,
    READINESS_CANDIDATE,
    READINESS_INSUFFICIENT_SAMPLE,
    audit,
)


def _csv(path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _event_payload(*codes: str) -> str:
    return json.dumps([{"code": code} for code in codes])


def _threshold_fixture(path) -> None:
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


def _first_row(rows: list[dict[str, object]], *, condition: str) -> dict[str, object]:
    for row in rows:
        if row["condition"] == condition:
            return row
    raise AssertionError(f"Missing condition: {condition}")


def test_audit_exposes_default_thresholds_in_report(tmp_path) -> None:
    path = tmp_path / "historical_effort_result_validation.csv"
    _threshold_fixture(path)

    report = audit(path, horizons=(1, 2))

    assert report["audit_only"] is True
    assert report["thresholds"] == {
        "readiness": {"min_bars": 10, "min_abs_delta": 0.005},
        "consensus": {"min_horizons": 2, "min_candidate_bars": 20},
    }
    assert report["readiness"]
    assert report["readiness_consensus"]
    assert all(row["may_change_scoring"] is False for row in report["readiness"])
    assert all(
        row["may_activate_detector"] is False
        for row in report["readiness_consensus"]
    )


def test_audit_threshold_controls_change_review_gate_without_production_permission(
    tmp_path,
) -> None:
    path = tmp_path / "historical_effort_result_validation.csv"
    _threshold_fixture(path)

    loose = audit(
        path,
        horizons=(1, 2),
        min_readiness_bars=5,
        min_readiness_abs_delta=0.0000001,
        min_consensus_horizons=2,
        min_consensus_candidate_bars=10,
    )
    strict = audit(
        path,
        horizons=(1, 2),
        min_readiness_bars=50,
        min_readiness_abs_delta=0.0000001,
        min_consensus_horizons=2,
        min_consensus_candidate_bars=10,
    )

    loose_readiness = _first_row(
        loose["readiness"], condition="EFFORT_GT_RESULT"
    )
    strict_readiness = _first_row(
        strict["readiness"], condition="EFFORT_GT_RESULT"
    )
    loose_consensus = _first_row(
        loose["readiness_consensus"], condition="EFFORT_GT_RESULT"
    )
    strict_consensus = _first_row(
        strict["readiness_consensus"], condition="EFFORT_GT_RESULT"
    )

    assert loose["thresholds"] == {
        "readiness": {"min_bars": 5, "min_abs_delta": 0.0000001},
        "consensus": {"min_horizons": 2, "min_candidate_bars": 10},
    }
    assert strict["thresholds"] == {
        "readiness": {"min_bars": 50, "min_abs_delta": 0.0000001},
        "consensus": {"min_horizons": 2, "min_candidate_bars": 10},
    }
    assert loose_readiness["readiness"] == READINESS_CANDIDATE
    assert strict_readiness["readiness"] == READINESS_INSUFFICIENT_SAMPLE
    assert loose_consensus["consensus"] == CONSENSUS_CANDIDATE
    assert strict_consensus["consensus"] == CONSENSUS_OBSERVATION_ONLY
    assert loose_readiness["may_change_scoring"] is False
    assert loose_consensus["may_change_ranking"] is False
    assert loose_consensus["may_change_actionability"] is False
    assert loose_consensus["may_activate_detector"] is False
    assert loose_consensus["requires_separate_production_pr"] is True


def test_audit_rejects_invalid_threshold_controls_before_file_read(tmp_path) -> None:
    missing_path = tmp_path / "missing.csv"

    with pytest.raises(ValueError, match="min_readiness_bars"):
        audit(missing_path, horizons=(1,), min_readiness_bars=0)

    with pytest.raises(ValueError, match="min_readiness_abs_delta"):
        audit(missing_path, horizons=(1,), min_readiness_abs_delta=-0.01)

    with pytest.raises(ValueError, match="min_consensus_horizons"):
        audit(missing_path, horizons=(1,), min_consensus_horizons=0)

    with pytest.raises(ValueError, match="min_consensus_candidate_bars"):
        audit(missing_path, horizons=(1,), min_consensus_candidate_bars=0)
