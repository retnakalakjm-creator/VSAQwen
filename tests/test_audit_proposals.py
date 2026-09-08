from __future__ import annotations

import pandas as pd
import pytest

from audit.proposals import (
    CalibrationProposalCriteria,
    actionable_proposals,
    build_calibration_proposals,
    write_calibration_proposal_bundle,
)


def _summary() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _row(
                "stopping_volume|4|long",
                sample_count=80,
                symbol_count=12,
                horizon_bars=4,
                side="long",
                win_rate=0.61,
                avg_favorable_return=0.035,
                total_favorable_return=2.8,
                anomaly_rate=0.02,
            ),
            _row(
                "upthrust|4|short",
                sample_count=75,
                symbol_count=10,
                horizon_bars=4,
                side="short",
                win_rate=0.37,
                avg_favorable_return=-0.022,
                total_favorable_return=-1.65,
                anomaly_rate=0.03,
            ),
            _row(
                "no_supply|2|long",
                sample_count=10,
                symbol_count=3,
                horizon_bars=2,
                side="long",
                win_rate=0.7,
                avg_favorable_return=0.04,
                total_favorable_return=0.4,
                anomaly_rate=0.0,
            ),
            _row(
                "spring|8|long",
                sample_count=50,
                symbol_count=9,
                horizon_bars=8,
                side="long",
                win_rate=0.58,
                avg_favorable_return=0.03,
                total_favorable_return=1.5,
                anomaly_rate=0.4,
            ),
            _row(
                "test|1|long",
                sample_count=65,
                symbol_count=11,
                horizon_bars=1,
                side="long",
                win_rate=0.51,
                avg_favorable_return=0.001,
                total_favorable_return=0.065,
                anomaly_rate=0.01,
            ),
        ]
    )


def _stability() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "group_key": "stopping_volume|4|long",
                "stability_grade": "stable_positive",
                "favorable_return_ci_low": 0.012,
                "favorable_return_ci_high": 0.058,
            },
            {
                "group_key": "upthrust|4|short",
                "stability_grade": "stable_negative",
                "favorable_return_ci_low": -0.045,
                "favorable_return_ci_high": -0.005,
            },
            {
                "group_key": "no_supply|2|long",
                "stability_grade": "stable_positive",
                "favorable_return_ci_low": 0.01,
                "favorable_return_ci_high": 0.07,
            },
            {
                "group_key": "spring|8|long",
                "stability_grade": "stable_positive",
                "favorable_return_ci_low": 0.01,
                "favorable_return_ci_high": 0.05,
            },
            {
                "group_key": "test|1|long",
                "stability_grade": "mixed",
                "favorable_return_ci_low": -0.01,
                "favorable_return_ci_high": 0.012,
            },
        ]
    )


def _row(
    group_key: str,
    *,
    sample_count: int,
    symbol_count: int,
    horizon_bars: int,
    side: str,
    win_rate: float,
    avg_favorable_return: float,
    total_favorable_return: float,
    anomaly_rate: float,
) -> dict[str, object]:
    return {
        "group_key": group_key,
        "sample_count": sample_count,
        "symbol_count": symbol_count,
        "horizon_bars": horizon_bars,
        "side": side,
        "win_rate": win_rate,
        "avg_favorable_return": avg_favorable_return,
        "total_favorable_return": total_favorable_return,
        "anomaly_rate": anomaly_rate,
    }


def test_build_calibration_proposals_classifies_review_actions() -> None:
    proposals = build_calibration_proposals(
        _summary(),
        stability=_stability(),
        criteria=CalibrationProposalCriteria(min_samples=30, min_symbols=5),
    )

    actions = dict(zip(proposals["group_key"], proposals["proposed_action"], strict=True))
    assert actions["stopping_volume|4|long"] == "review_for_weight_increase"
    assert actions["upthrust|4|short"] == "review_for_weight_decrease"
    assert actions["no_supply|2|long"] == "collect_more_data"
    assert actions["spring|8|long"] == "collect_more_data"
    assert actions["test|1|long"] == "keep_current"


def test_actionable_proposals_excludes_keep_and_collect_rows() -> None:
    proposals = build_calibration_proposals(
        _summary(),
        stability=_stability(),
        criteria=CalibrationProposalCriteria(min_samples=30, min_symbols=5),
    )

    actionable = actionable_proposals(proposals)

    assert set(actionable["proposed_action"]) == {
        "review_for_weight_increase",
        "review_for_weight_decrease",
    }


def test_require_stability_can_be_disabled_for_exploratory_review() -> None:
    proposals = build_calibration_proposals(
        _summary().iloc[:1],
        criteria=CalibrationProposalCriteria(
            min_samples=30,
            min_symbols=5,
            require_stability=False,
        ),
    )

    assert proposals.loc[0, "proposed_action"] == "review_for_weight_increase"
    assert proposals.loc[0, "confidence"] == "medium"


def test_missing_stability_collects_more_data_by_default() -> None:
    proposals = build_calibration_proposals(
        _summary().iloc[:1],
        criteria=CalibrationProposalCriteria(min_samples=30, min_symbols=5),
    )

    assert proposals.loc[0, "proposed_action"] == "collect_more_data"
    assert "Stability" in proposals.loc[0, "rationale"]


def test_write_calibration_proposal_bundle_writes_csvs(tmp_path) -> None:
    paths = write_calibration_proposal_bundle(
        _summary(),
        tmp_path / "proposals",
        stability=_stability(),
        criteria=CalibrationProposalCriteria(min_samples=30, min_symbols=5),
        source="evidence_summary",
    )

    assert paths.output_dir.exists()
    assert paths.proposals.exists()
    assert paths.metadata.exists()

    proposals = pd.read_csv(paths.proposals)
    metadata = pd.read_csv(paths.metadata)
    metadata_values = dict(zip(metadata["metric"], metadata["value"], strict=True))

    assert len(proposals) == 5
    assert int(metadata_values["proposal_rows"]) == 5
    assert int(metadata_values["actionable_proposal_rows"]) == 2
    assert metadata_values["source"] == "evidence_summary"


def test_empty_summary_returns_schema_stable_frame() -> None:
    summary = _summary().iloc[:0]
    proposals = build_calibration_proposals(
        summary,
        criteria=CalibrationProposalCriteria(min_samples=30, min_symbols=5),
    )

    assert proposals.empty
    assert "proposed_action" in proposals.columns
    assert "group_key" in proposals.columns


def test_proposal_inputs_are_validated() -> None:
    with pytest.raises(ValueError, match="Missing required proposal columns"):
        build_calibration_proposals(pd.DataFrame({"group_key": ["x"]}))

    with pytest.raises(ValueError, match="min_samples"):
        build_calibration_proposals(
            _summary(),
            criteria=CalibrationProposalCriteria(min_samples=0),
        )

    with pytest.raises(ValueError, match="min_symbols"):
        build_calibration_proposals(
            _summary(),
            criteria=CalibrationProposalCriteria(min_symbols=0),
        )

    with pytest.raises(ValueError, match="min_win_rate"):
        build_calibration_proposals(
            _summary(),
            criteria=CalibrationProposalCriteria(min_win_rate=1.1),
        )

    with pytest.raises(ValueError, match="max_anomaly_rate"):
        build_calibration_proposals(
            _summary(),
            criteria=CalibrationProposalCriteria(max_anomaly_rate=1.1),
        )

    with pytest.raises(ValueError, match="Missing required proposal columns"):
        build_calibration_proposals(
            _summary(),
            stability=pd.DataFrame({"group_key": ["x"]}),
        )
