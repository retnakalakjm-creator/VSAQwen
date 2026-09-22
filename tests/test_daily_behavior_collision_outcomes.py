from __future__ import annotations

import json

import pandas as pd
import pytest

from audit.daily_behavior_collision_outcomes import (
    _dimension_family,
    run_daily_behavior_collision_outcome_analysis,
)


def _write_bundle(root) -> None:
    records = pd.DataFrame(
        [
            {
                "symbol": "A.NS",
                "bar_index": 10,
                "weekly_direction": "bearish",
                "fresh_behavior": True,
                "signature": "0:aligned_pressure_emerging",
                "evidence_signature": "0:increasing_supply",
            },
            {
                "symbol": "B.NS",
                "bar_index": 11,
                "weekly_direction": "bearish",
                "fresh_behavior": True,
                "signature": "0:aligned_pressure_emerging",
                "evidence_signature": "0:increasing_supply",
            },
            {
                "symbol": "A.NS",
                "bar_index": 12,
                "weekly_direction": "bearish",
                "fresh_behavior": True,
                "signature": "0:aligned_pressure_emerging",
                "evidence_signature": "0:hidden_supply",
            },
            {
                "symbol": "C.NS",
                "bar_index": 13,
                "weekly_direction": "bearish",
                "fresh_behavior": True,
                "signature": "0:aligned_pressure_emerging",
                "evidence_signature": "0:hidden_supply",
            },
            {
                "symbol": "A.NS",
                "bar_index": 14,
                "weekly_direction": "bearish",
                "fresh_behavior": True,
                "signature": "0:structural_alignment",
                "evidence_signature": "0:structural_progression_weakening",
            },
            {
                "symbol": "A.NS",
                "bar_index": 20,
                "weekly_direction": "bullish",
                "fresh_behavior": True,
                "signature": "0:rejection_of_opposing_move",
                "evidence_signature": "0:selling_climax",
            },
            {
                "symbol": "B.NS",
                "bar_index": 21,
                "weekly_direction": "bullish",
                "fresh_behavior": True,
                "signature": "0:rejection_of_opposing_move",
                "evidence_signature": "0:spring",
            },
            {
                "symbol": "B.NS",
                "bar_index": 22,
                "weekly_direction": "bullish",
                "fresh_behavior": False,
                "signature": "-1:rejection_of_opposing_move",
                "evidence_signature": "-1:spring",
            },
        ]
    )
    records.to_csv(root / "daily_sequence_records.csv", index=False)

    outcomes = pd.DataFrame(
        [
            {
                "symbol": "A.NS",
                "signal_bar_index": 10,
                "weekly_direction": "bearish",
                "signature": "0:aligned_pressure_emerging",
                "evidence_signature": "0:increasing_supply",
                "horizon_bars": 3,
                "outcome_available": True,
                "complete": True,
                "favorable_return": 0.03,
                "mfe": 0.05,
                "mae": -0.01,
            },
            {
                "symbol": "B.NS",
                "signal_bar_index": 11,
                "weekly_direction": "bearish",
                "signature": "0:aligned_pressure_emerging",
                "evidence_signature": "0:increasing_supply",
                "horizon_bars": 3,
                "outcome_available": True,
                "complete": True,
                "favorable_return": 0.01,
                "mfe": 0.03,
                "mae": -0.02,
            },
            {
                "symbol": "A.NS",
                "signal_bar_index": 12,
                "weekly_direction": "bearish",
                "signature": "0:aligned_pressure_emerging",
                "evidence_signature": "0:hidden_supply",
                "horizon_bars": 3,
                "outcome_available": True,
                "complete": True,
                "favorable_return": -0.01,
                "mfe": 0.01,
                "mae": -0.04,
            },
            {
                "symbol": "C.NS",
                "signal_bar_index": 13,
                "weekly_direction": "bearish",
                "signature": "0:aligned_pressure_emerging",
                "evidence_signature": "0:hidden_supply",
                "horizon_bars": 3,
                "outcome_available": True,
                "complete": True,
                "favorable_return": -0.03,
                "mfe": 0.00,
                "mae": -0.05,
            },
            {
                "symbol": "A.NS",
                "signal_bar_index": 14,
                "weekly_direction": "bearish",
                "signature": "0:structural_alignment",
                "evidence_signature": "0:structural_progression_weakening",
                "horizon_bars": 3,
                "outcome_available": True,
                "complete": True,
                "favorable_return": 0.01,
                "mfe": 0.02,
                "mae": -0.01,
            },
            {
                "symbol": "A.NS",
                "signal_bar_index": 20,
                "weekly_direction": "bullish",
                "signature": "0:rejection_of_opposing_move",
                "evidence_signature": "0:selling_climax",
                "horizon_bars": 3,
                "outcome_available": True,
                "complete": True,
                "favorable_return": 0.04,
                "mfe": 0.06,
                "mae": -0.01,
            },
            {
                "symbol": "B.NS",
                "signal_bar_index": 21,
                "weekly_direction": "bullish",
                "signature": "0:rejection_of_opposing_move",
                "evidence_signature": "0:spring",
                "horizon_bars": 3,
                "outcome_available": True,
                "complete": True,
                "favorable_return": 0.02,
                "mfe": 0.04,
                "mae": -0.02,
            },
        ]
    )
    outcomes.to_csv(root / "daily_sequence_outcomes.csv", index=False)

    collisions = pd.DataFrame(
        [
            {
                "weekly_direction": "bearish",
                "signature": "0:aligned_pressure_emerging",
                "distinct_evidence_signature_count": 2,
                "observation_count": 4,
            },
            {
                "weekly_direction": "bullish",
                "signature": "0:rejection_of_opposing_move",
                "distinct_evidence_signature_count": 2,
                "observation_count": 2,
            },
        ]
    )
    collisions.to_csv(
        root / "daily_sequence_signature_collisions.csv",
        index=False,
    )


def test_dimension_family_is_offset_independent_and_unique() -> None:
    assert (
        _dimension_family(
            "-3:aligned_pressure_emerging;"
            "0:aligned_pressure_emerging,rejection_of_opposing_move"
        )
        == "aligned_pressure_emerging+rejection_of_opposing_move"
    )


def test_csv_only_analysis_reconciles_and_stratifies(tmp_path) -> None:
    study_dir = tmp_path / "study"
    output_dir = tmp_path / "output"
    study_dir.mkdir()
    _write_bundle(study_dir)

    paths = run_daily_behavior_collision_outcome_analysis(
        study_dir=study_dir,
        output_dir=output_dir,
        min_complete_per_variant=1,
    )

    summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    directions = pd.read_csv(paths.direction_summary_csv)
    breadth = pd.read_csv(paths.evidence_variant_breadth_csv)
    variants = pd.read_csv(paths.evidence_variant_outcomes_csv)
    spreads = pd.read_csv(paths.within_coarse_outcome_spreads_csv)
    contrasts = pd.read_csv(paths.within_coarse_pairwise_contrasts_csv)

    assert summary["record_count"] == 8
    assert summary["fresh_sequence_count"] == 7
    assert summary["collision_observation_count"] == 6
    assert summary["coarse_signature_collision_count"] == 2
    assert summary["is_actionable"] is False

    bearish = directions.loc[
        directions["weekly_direction"] == "bearish"
    ].iloc[0]
    assert bearish["fresh_sequence_count"] == 5
    assert bearish["collision_observation_count"] == 4
    assert bearish["collision_rate"] == pytest.approx(0.8)

    increasing = breadth.loc[
        breadth["evidence_signature"] == "0:increasing_supply"
    ].iloc[0]
    assert increasing["observation_count"] == 2
    assert increasing["symbol_count"] == 2

    bearish_variants = variants.loc[
        (variants["weekly_direction"] == "bearish")
        & (variants["signature"] == "0:aligned_pressure_emerging")
    ]
    assert len(bearish_variants) == 2

    bearish_spread = spreads.loc[
        (spreads["weekly_direction"] == "bearish")
        & (spreads["signature"] == "0:aligned_pressure_emerging")
    ].iloc[0]
    assert bearish_spread["mean_favorable_return_spread"] == pytest.approx(0.04)

    bearish_contrast = contrasts.loc[
        (contrasts["weekly_direction"] == "bearish")
        & (contrasts["signature"] == "0:aligned_pressure_emerging")
    ].iloc[0]
    assert abs(
        bearish_contrast["delta_mean_favorable_return_a_minus_b"]
    ) == pytest.approx(0.04)
    assert contrasts["is_actionable"].eq(False).all()


def test_analysis_fails_when_collision_ledger_does_not_reconcile(
    tmp_path,
) -> None:
    study_dir = tmp_path / "study"
    study_dir.mkdir()
    _write_bundle(study_dir)

    collisions_path = study_dir / "daily_sequence_signature_collisions.csv"
    collisions = pd.read_csv(collisions_path)
    collisions.loc[0, "observation_count"] = 99
    collisions.to_csv(collisions_path, index=False)

    with pytest.raises(ValueError, match="reconciliation failed"):
        run_daily_behavior_collision_outcome_analysis(
            study_dir=study_dir,
            output_dir=tmp_path / "output",
            min_complete_per_variant=1,
        )
