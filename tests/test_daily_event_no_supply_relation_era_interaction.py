from __future__ import annotations

import pandas as pd
import pytest

from audit.daily_event_no_supply_alternate_context_profile import (
    GROUP_LATEST,
    GROUP_PRIOR,
)
from audit.daily_event_no_supply_relation_era_interaction import (
    ESTIMAND_EVENT_WEIGHTED,
    METRIC_MFE,
    RELATION_HIGHER_CLASS,
    RELATION_SAME_CLASS,
    build_era_relation_count_rows,
    build_era_relation_outcome_rows,
    build_interaction_contrast_rows,
    build_prior_latest_rows,
    build_relation_temporal_consistency_rows,
)
from audit.daily_event_no_supply_temporal_stability import (
    ERA_2023_2026,
    ERA_ORDER,
)


def _contexts() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for era_index, era in enumerate(ERA_ORDER):
        group = GROUP_LATEST if era == ERA_2023_2026 else GROUP_PRIOR
        for relation_index, relation in enumerate(
            (RELATION_SAME_CLASS, RELATION_HIGHER_CLASS)
        ):
            rows.append(
                {
                    "symbol": f"S{era_index}{relation_index}.NS",
                    "session": (
                        f"{2005 + era_index * 5}-06-"
                        f"{10 + relation_index:02d}T00:00:00"
                    ),
                    "era": era,
                    "comparison_group": group,
                    "volume_class_relation": relation,
                }
            )
    return pd.DataFrame(rows)


def _pairs() -> pd.DataFrame:
    values: dict[tuple[str, str], float] = {}
    for era in ERA_ORDER:
        if era == ERA_2023_2026:
            values[(era, RELATION_SAME_CLASS)] = -1.0
            values[(era, RELATION_HIGHER_CLASS)] = -0.5
        else:
            values[(era, RELATION_SAME_CLASS)] = 1.0
            values[(era, RELATION_HIGHER_CLASS)] = 2.0

    rows: list[dict[str, object]] = []
    for target in _contexts().itertuples(index=False):
        base = values[(target.era, target.volume_class_relation)]
        for horizon in (1, 3, 5):
            scale = horizon / 1.0
            rows.append(
                {
                    "symbol": target.symbol,
                    "target_session": target.session,
                    "era": target.era,
                    "comparison_group": target.comparison_group,
                    "volume_class_relation": target.volume_class_relation,
                    "horizon_sessions": horizon,
                    "paired_return_delta_pct": base * scale / 2.0,
                    "paired_mfe_delta_pct": base * scale,
                    "clean_pair": True,
                }
            )
    return pd.DataFrame(rows)


def test_era_relation_counts_cover_fixed_grid() -> None:
    rows = build_era_relation_count_rows(_contexts())

    assert len(rows) == 10
    assert all(row.source_target_count == 1 for row in rows)
    assert all(row.symbol_count == 1 for row in rows)


def test_era_relation_outcomes_keep_latest_relations_separate() -> None:
    rows = build_era_relation_outcome_rows(
        contexts=_contexts(),
        pair_outcomes=_pairs(),
        horizons=(1, 3, 5),
    )

    assert len(rows) == 30

    latest_same_h3 = next(
        row
        for row in rows
        if row.era == ERA_2023_2026
        and row.volume_class_relation == RELATION_SAME_CLASS
        and row.horizon_sessions == 3
    )
    latest_higher_h3 = next(
        row
        for row in rows
        if row.era == ERA_2023_2026
        and row.volume_class_relation == RELATION_HIGHER_CLASS
        and row.horizon_sessions == 3
    )

    assert latest_same_h3.event_weighted_mfe_delta_pct == pytest.approx(
        -3.0
    )
    assert latest_higher_h3.event_weighted_mfe_delta_pct == pytest.approx(
        -1.5
    )


def test_temporal_consistency_reports_latest_failure() -> None:
    outcomes = build_era_relation_outcome_rows(
        contexts=_contexts(),
        pair_outcomes=_pairs(),
        horizons=(1,),
    )
    rows = build_relation_temporal_consistency_rows(
        outcomes,
        horizons=(1,),
    )

    same_mfe = next(
        row
        for row in rows
        if row.volume_class_relation == RELATION_SAME_CLASS
        and row.metric == METRIC_MFE
        and row.estimand == ESTIMAND_EVENT_WEIGHTED
    )
    higher_mfe = next(
        row
        for row in rows
        if row.volume_class_relation == RELATION_HIGHER_CLASS
        and row.metric == METRIC_MFE
        and row.estimand == ESTIMAND_EVENT_WEIGHTED
    )

    assert same_mfe.available_era_count == 5
    assert same_mfe.positive_era_count == 4
    assert same_mfe.negative_era_count == 1
    assert same_mfe.min_era == ERA_2023_2026

    assert higher_mfe.positive_era_count == 4
    assert higher_mfe.negative_era_count == 1
    assert higher_mfe.min_era == ERA_2023_2026


def test_prior_latest_rows_show_both_relations_failing_latest() -> None:
    rows = build_prior_latest_rows(
        contexts=_contexts(),
        pair_outcomes=_pairs(),
        horizons=(1,),
    )

    same = next(
        row
        for row in rows
        if row.volume_class_relation == RELATION_SAME_CLASS
    )
    higher = next(
        row
        for row in rows
        if row.volume_class_relation == RELATION_HIGHER_CLASS
    )

    assert same.prior_source_target_count == 4
    assert same.latest_source_target_count == 1
    assert same.prior_event_weighted_mfe_delta_pct == pytest.approx(1.0)
    assert same.latest_event_weighted_mfe_delta_pct == pytest.approx(-1.0)
    assert same.latest_minus_prior_event_mfe_pct == pytest.approx(-2.0)

    assert higher.prior_event_weighted_mfe_delta_pct == pytest.approx(2.0)
    assert higher.latest_event_weighted_mfe_delta_pct == pytest.approx(-0.5)
    assert higher.latest_minus_prior_event_mfe_pct == pytest.approx(-2.5)


def test_interaction_contrast_is_same_change_minus_higher_change() -> None:
    prior_latest = build_prior_latest_rows(
        contexts=_contexts(),
        pair_outcomes=_pairs(),
        horizons=(1,),
    )
    rows = build_interaction_contrast_rows(
        prior_latest,
        horizons=(1,),
    )

    mfe = next(
        row
        for row in rows
        if row.metric == METRIC_MFE
        and row.estimand == ESTIMAND_EVENT_WEIGHTED
    )

    assert mfe.same_class_latest_minus_prior == pytest.approx(-2.0)
    assert mfe.higher_class_latest_minus_prior == pytest.approx(-2.5)
    assert mfe.same_minus_higher_change == pytest.approx(0.5)
