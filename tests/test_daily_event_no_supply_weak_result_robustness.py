from __future__ import annotations

import pandas as pd
import pytest

from audit.daily_event_no_supply_forward_outcomes import (
    COHORT_ALTERNATE,
    COHORT_CURRENT,
)
from audit.daily_event_no_supply_weak_result_robustness import (
    ESTIMAND_EVENT_WEIGHTED,
    ESTIMAND_SYMBOL_NORMALIZED,
    METRIC_RETURN,
    build_bootstrap_rows,
    build_leave_one_out_rows,
    build_robustness_rows,
    build_semantic_rows,
)


def _pair_outcomes() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for cohort in (COHORT_CURRENT, COHORT_ALTERNATE):
        for symbol_index in range(30):
            symbol = f"S{symbol_index:02d}.NS"
            value = 10.0 if symbol_index == 0 else -1.0
            repeat = 10 if symbol_index == 0 else 1
            for event_index in range(repeat):
                rows.append(
                    {
                        "symbol": symbol,
                        "cohort": cohort,
                        "target_session": (
                            f"2026-01-{(event_index % 20) + 1:02d}"
                            "T00:00:00"
                        ),
                        "horizon_sessions": 5,
                        "paired_return_delta_pct": value,
                        "positive_delta": (
                            1.0 if value > 0.0 else -1.0
                        ),
                        "paired_mfe_delta_pct": value / 2.0,
                        "paired_mae_delta_pct": value / 4.0,
                        "clean_pair": True,
                    }
                )
    return pd.DataFrame(rows)


def test_semantic_rows_define_actual_predicate_contract() -> None:
    rows = build_semantic_rows()
    assert len(rows) == 8

    close = {
        row.input_state: row.predicate_result
        for row in rows
        if row.semantic_dimension == "WEAK_CLOSE_POSITION"
    }
    assert close == {
        "ON_LOW": True,
        "LOWER": True,
        "MIDDLE": False,
        "UPPER": False,
        "ON_HIGH": False,
    }

    volume = {
        row.input_state: row.predicate_result
        for row in rows
        if row.semantic_dimension == "VOLUME_CLASS_RELATION"
    }
    assert volume == {
        "CURRENT_CLASS_LOWER_THAN_PREVIOUS": False,
        "CURRENT_CLASS_EQUAL_PREVIOUS": True,
        "CURRENT_CLASS_HIGHER_THAN_PREVIOUS": True,
    }


def test_robustness_rows_distinguish_event_and_symbol_weighting() -> None:
    rows = build_robustness_rows(
        _pair_outcomes(),
        horizons=(5,),
    )
    assert len(rows) == 2

    current = next(
        row for row in rows if row.cohort == COHORT_CURRENT
    )
    assert current.clean_pair_count == 39
    assert current.clean_symbol_count == 30
    assert current.event_weighted_return_delta_pct == pytest.approx(
        71.0 / 39.0
    )
    assert current.symbol_normalized_return_delta_pct == pytest.approx(
        -19.0 / 30.0
    )
    assert current.positive_return_symbol_count == 1
    assert current.negative_return_symbol_count == 29


def test_cluster_bootstrap_is_deterministic_and_reports_both_estimands() -> None:
    first = build_bootstrap_rows(
        _pair_outcomes(),
        horizons=(5,),
        iterations=200,
        seed=1234,
    )
    second = build_bootstrap_rows(
        _pair_outcomes(),
        horizons=(5,),
        iterations=200,
        seed=1234,
    )
    assert first == second
    assert len(first) == 16

    event = next(
        row
        for row in first
        if row.cohort == COHORT_CURRENT
        and row.metric == METRIC_RETURN
        and row.estimand == ESTIMAND_EVENT_WEIGHTED
    )
    normalized = next(
        row
        for row in first
        if row.cohort == COHORT_CURRENT
        and row.metric == METRIC_RETURN
        and row.estimand == ESTIMAND_SYMBOL_NORMALIZED
    )

    assert event.observed_value == pytest.approx(71.0 / 39.0)
    assert normalized.observed_value == pytest.approx(-19.0 / 30.0)
    assert event.bootstrap_iterations == 200
    assert event.bootstrap_seed == 1234
    assert 0.0 <= event.bootstrap_fraction_gt_zero <= 1.0
    assert 0.0 <= normalized.bootstrap_fraction_gt_zero <= 1.0


def test_leave_one_symbol_out_exposes_dominant_symbol() -> None:
    rows = build_leave_one_out_rows(
        _pair_outcomes(),
        horizons=(5,),
    )

    event = next(
        row
        for row in rows
        if row.cohort == COHORT_CURRENT
        and row.estimand == ESTIMAND_EVENT_WEIGHTED
    )
    normalized = next(
        row
        for row in rows
        if row.cohort == COHORT_CURRENT
        and row.estimand == ESTIMAND_SYMBOL_NORMALIZED
    )

    assert event.full_return_delta_pct > 0.0
    assert event.min_leave_one_out_return_delta_pct == pytest.approx(
        -1.0
    )
    assert event.min_leave_one_out_symbol == "S00.NS"
    assert event.negative_leave_one_out_count >= 1

    assert normalized.full_return_delta_pct < 0.0
    assert normalized.max_leave_one_out_return_delta_pct < 0.0
    assert normalized.negative_leave_one_out_count == 30
