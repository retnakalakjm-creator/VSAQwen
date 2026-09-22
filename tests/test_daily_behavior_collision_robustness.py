from __future__ import annotations

import json

import pandas as pd
import pytest

from audit.daily_behavior_collision_robustness import (
    run_daily_behavior_collision_robustness,
)


HORIZONS = (1, 3, 5)


def _write_inputs(root) -> tuple:
    outcomes_path = root / "daily_sequence_outcomes.csv"
    pairwise_path = root / "pairwise.csv"

    outcome_rows = []
    for horizon in HORIZONS:
        for symbol, base_index, a_return, b_return in (
            ("A.NS", 100, 0.03 + horizon / 1000, 0.01),
            ("B.NS", 200, 0.02 + horizon / 1000, 0.00),
        ):
            outcome_rows.extend(
                [
                    {
                        "symbol": symbol,
                        "signal_bar_index": base_index,
                        "weekly_direction": "bearish",
                        "signature": "0:aligned_pressure_emerging",
                        "evidence_signature": "0:increasing_supply",
                        "horizon_bars": horizon,
                        "complete": True,
                        "favorable_return": a_return,
                        "mfe": a_return + 0.01,
                        "mae": -0.01,
                    },
                    {
                        "symbol": symbol,
                        "signal_bar_index": base_index + 2,
                        "weekly_direction": "bearish",
                        "signature": "0:aligned_pressure_emerging",
                        "evidence_signature": "0:supply_coming_in",
                        "horizon_bars": horizon,
                        "complete": True,
                        "favorable_return": b_return,
                        "mfe": b_return + 0.01,
                        "mae": -0.02,
                    },
                ]
            )
    pd.DataFrame(outcome_rows).to_csv(outcomes_path, index=False)

    pair_rows = []
    for horizon in HORIZONS:
        left = pd.DataFrame(outcome_rows)
        a = left.loc[
            (left["horizon_bars"] == horizon)
            & (left["evidence_signature"] == "0:increasing_supply")
        ]["favorable_return"].mean()
        b = left.loc[
            (left["horizon_bars"] == horizon)
            & (left["evidence_signature"] == "0:supply_coming_in")
        ]["favorable_return"].mean()
        pair_rows.append(
            {
                "weekly_direction": "bearish",
                "signature": "0:aligned_pressure_emerging",
                "dimension_family": "aligned_pressure_emerging",
                "horizon_bars": horizon,
                "evidence_signature_a": "0:increasing_supply",
                "evidence_signature_b": "0:supply_coming_in",
                "complete_outcome_count_a": 2,
                "complete_outcome_count_b": 2,
                "symbol_count_a": 2,
                "symbol_count_b": 2,
                "delta_mean_favorable_return_a_minus_b": a - b,
            }
        )
    pd.DataFrame(pair_rows).to_csv(pairwise_path, index=False)
    return outcomes_path, pairwise_path


def test_robustness_reconciles_pooled_and_preserves_sign(tmp_path) -> None:
    outcomes_path, pairwise_path = _write_inputs(tmp_path)

    paths = run_daily_behavior_collision_robustness(
        raw_outcomes_csv=outcomes_path,
        pairwise_contrasts_csv=pairwise_path,
        output_dir=tmp_path / "output",
        horizons=HORIZONS,
        min_complete_per_variant=1,
        min_symbols_per_variant=1,
        max_time_gap_bars=5,
    )

    summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    broad = pd.read_csv(paths.broad_pairs_csv)
    horizons = pd.read_csv(paths.horizon_robustness_csv)
    pairs = pd.read_csv(paths.pair_summary_csv)

    assert summary["broad_pair_count"] == 1
    assert summary["pooled_sign_stable_pair_count"] == 1
    assert summary["all_methods_sign_stable_pair_count"] == 1
    assert summary["raw_outcome_row_count"] == 12
    assert summary["is_actionable"] is False

    assert broad["pooled_sign_stable_across_horizons"].eq(True).all()
    assert horizons["paired_symbol_count"].eq(2).all()
    assert horizons["loo_all_same_sign_as_pooled"].eq(True).all()
    assert horizons["matched_pair_count"].eq(2).all()
    assert horizons["matched_symbol_count"].eq(2).all()
    assert horizons["matched_mean_gap_bars"].eq(2.0).all()
    assert (
        horizons["matched_delta_mean_favorable_return_a_minus_b"] > 0
    ).all()

    pair = pairs.iloc[0]
    assert bool(pair["pooled_sign_stable_across_horizons"])
    assert bool(pair["symbol_balanced_sign_stable_across_horizons"])
    assert bool(pair["matched_sign_stable_across_horizons"])
    assert bool(pair["loo_all_same_sign_as_pooled_all_horizons"])
    assert bool(pair["all_methods_sign_stable_across_horizons"])


def test_robustness_fails_when_raw_pooled_delta_disagrees_with_366(
    tmp_path,
) -> None:
    outcomes_path, pairwise_path = _write_inputs(tmp_path)
    pairwise = pd.read_csv(pairwise_path)
    pairwise.loc[0, "delta_mean_favorable_return_a_minus_b"] = -99.0
    pairwise.to_csv(pairwise_path, index=False)

    with pytest.raises(ValueError, match="pooled contrast mismatch"):
        run_daily_behavior_collision_robustness(
            raw_outcomes_csv=outcomes_path,
            pairwise_contrasts_csv=pairwise_path,
            output_dir=tmp_path / "output",
            horizons=HORIZONS,
            min_complete_per_variant=1,
            min_symbols_per_variant=1,
            max_time_gap_bars=5,
        )


def test_broad_pair_requires_every_requested_horizon(tmp_path) -> None:
    outcomes_path, pairwise_path = _write_inputs(tmp_path)
    pairwise = pd.read_csv(pairwise_path)
    pairwise = pairwise.loc[pairwise["horizon_bars"] != 5]
    pairwise.to_csv(pairwise_path, index=False)

    with pytest.raises(ValueError, match="no broad evidence-variant pairs"):
        run_daily_behavior_collision_robustness(
            raw_outcomes_csv=outcomes_path,
            pairwise_contrasts_csv=pairwise_path,
            output_dir=tmp_path / "output",
            horizons=HORIZONS,
            min_complete_per_variant=1,
            min_symbols_per_variant=1,
            max_time_gap_bars=5,
        )
