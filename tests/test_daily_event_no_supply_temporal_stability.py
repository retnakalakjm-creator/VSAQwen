from __future__ import annotations

import pandas as pd
import pytest

from audit.daily_event_no_supply_forward_outcomes import (
    COHORT_ALTERNATE,
    COHORT_CURRENT,
)
from audit.daily_event_no_supply_temporal_stability import (
    ERA_2010_2014,
    ERA_2015_2019,
    ERA_2020_2022,
    ERA_2023_2026,
    ERA_EARLY,
    ESTIMAND_EVENT_WEIGHTED,
    ESTIMAND_SYMBOL_NORMALIZED,
    METRIC_MFE,
    METRIC_RETURN,
    build_era_count_rows,
    build_era_outcome_rows,
    build_leave_one_era_out_rows,
    build_temporal_consistency_rows,
    era_for_session,
)


def _targets() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    eras = [
        ("2009-06-01T00:00:00", ERA_EARLY),
        ("2012-06-01T00:00:00", ERA_2010_2014),
        ("2017-06-01T00:00:00", ERA_2015_2019),
        ("2021-06-01T00:00:00", ERA_2020_2022),
        ("2025-06-01T00:00:00", ERA_2023_2026),
    ]
    for cohort in (COHORT_CURRENT, COHORT_ALTERNATE):
        for index, (session, era) in enumerate(eras):
            rows.append(
                {
                    "symbol": f"S{index:02d}.NS",
                    "session": session,
                    "bar_index": index,
                    "cohort": cohort,
                    "trend_direction": (
                        "DOWN"
                        if cohort == COHORT_CURRENT
                        else "UP"
                    ),
                    "volume_decreasing": False,
                    "weak_selling_result": True,
                    "stratum": "WEAK_RESULT_ONLY",
                    "era": era,
                }
            )
    return pd.DataFrame(rows)


def _pairs() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    values = {
        ERA_EARLY: -1.0,
        ERA_2010_2014: 1.0,
        ERA_2015_2019: 2.0,
        ERA_2020_2022: 3.0,
        ERA_2023_2026: 4.0,
    }
    for target in _targets().itertuples(index=False):
        value = values[target.era]
        rows.append(
            {
                "symbol": target.symbol,
                "cohort": target.cohort,
                "trend_direction": target.trend_direction,
                "target_session": target.session,
                "target_bar_index": target.bar_index,
                "horizon_sessions": 5,
                "paired_return_delta_pct": value,
                "positive_delta": 1.0 if value > 0.0 else -1.0,
                "paired_mfe_delta_pct": value + 0.5,
                "paired_mae_delta_pct": value / 2.0,
                "clean_pair": True,
                "era": target.era,
            }
        )
    return pd.DataFrame(rows)


@pytest.mark.parametrize(
    ("session", "expected"),
    [
        ("2009-12-31", ERA_EARLY),
        ("2010-01-01", ERA_2010_2014),
        ("2014-12-31", ERA_2010_2014),
        ("2015-01-01", ERA_2015_2019),
        ("2019-12-31", ERA_2015_2019),
        ("2020-01-01", ERA_2020_2022),
        ("2022-12-31", ERA_2020_2022),
        ("2023-01-01", ERA_2023_2026),
        ("2026-12-31", ERA_2023_2026),
    ],
)
def test_era_for_session_uses_fixed_calendar_boundaries(
    session: str,
    expected: str,
) -> None:
    assert era_for_session(session) == expected


def test_era_count_rows_cover_all_cohort_era_cells() -> None:
    rows = build_era_count_rows(_targets())
    assert len(rows) == 10
    assert all(row.source_target_count == 1 for row in rows)
    assert all(row.symbol_count == 1 for row in rows)


def test_era_outcomes_and_consistency_preserve_sign_by_era() -> None:
    outcomes = build_era_outcome_rows(
        targets=_targets(),
        pair_outcomes=_pairs(),
        horizons=(5,),
    )
    assert len(outcomes) == 10

    consistency = build_temporal_consistency_rows(
        outcomes,
        horizons=(5,),
    )
    assert len(consistency) == 16

    current_return = next(
        row
        for row in consistency
        if row.cohort == COHORT_CURRENT
        and row.metric == METRIC_RETURN
        and row.estimand == ESTIMAND_EVENT_WEIGHTED
    )
    assert current_return.available_era_count == 5
    assert current_return.positive_era_count == 4
    assert current_return.negative_era_count == 1
    assert current_return.min_era == ERA_EARLY
    assert current_return.min_era_value == -1.0
    assert current_return.max_era == ERA_2023_2026
    assert current_return.max_era_value == 4.0

    mfe = next(
        row
        for row in consistency
        if row.cohort == COHORT_CURRENT
        and row.metric == METRIC_MFE
        and row.estimand == ESTIMAND_SYMBOL_NORMALIZED
    )
    assert mfe.positive_era_count == 4
    assert mfe.negative_era_count == 1


def test_leave_one_era_out_reports_each_omission() -> None:
    rows = build_leave_one_era_out_rows(
        _pairs(),
        horizons=(5,),
    )
    assert len(rows) == 20

    current_event = [
        row
        for row in rows
        if row.cohort == COHORT_CURRENT
        and row.estimand == ESTIMAND_EVENT_WEIGHTED
    ]
    assert len(current_event) == 5
    assert all(row.full_return_delta_pct == pytest.approx(1.8) for row in current_event)

    omit_early = next(
        row for row in current_event if row.omitted_era == ERA_EARLY
    )
    assert omit_early.leave_one_era_out_return_delta_pct == pytest.approx(2.5)
    assert omit_early.remains_positive is True

    omit_latest = next(
        row
        for row in current_event
        if row.omitted_era == ERA_2023_2026
    )
    assert omit_latest.leave_one_era_out_return_delta_pct == pytest.approx(1.25)
    assert omit_latest.remains_positive is True


def test_event_and_symbol_estimands_match_with_one_event_per_symbol() -> None:
    rows = build_leave_one_era_out_rows(
        _pairs(),
        horizons=(5,),
    )
    for cohort in (COHORT_CURRENT, COHORT_ALTERNATE):
        event = {
            row.omitted_era: row.leave_one_era_out_return_delta_pct
            for row in rows
            if row.cohort == cohort
            and row.estimand == ESTIMAND_EVENT_WEIGHTED
        }
        normalized = {
            row.omitted_era: row.leave_one_era_out_return_delta_pct
            for row in rows
            if row.cohort == cohort
            and row.estimand == ESTIMAND_SYMBOL_NORMALIZED
        }
        assert event == normalized
