from __future__ import annotations

import pandas as pd
import pytest

from audit.daily_event_no_supply_confirmation_strata import (
    CONFIRMATION_GATES,
    CONFIRMATION_STRATA,
    GATE_BOTH,
    GATE_VOLUME_DECREASING,
    GATE_WEAK_SELLING_RESULT,
    STRATUM_BOTH,
    STRATUM_NEITHER,
    STRATUM_VOLUME_ONLY,
    STRATUM_WEAK_RESULT_ONLY,
    build_confirmation_count_rows,
    build_confirmation_outcome_rows,
    confirmation_stratum,
)
from audit.daily_event_no_supply_forward_outcomes import (
    COHORT_ALTERNATE,
    COHORT_CURRENT,
)


def _targets() -> pd.DataFrame:
    rows = [
        {
            "symbol": "AAA.NS",
            "session": "2026-01-01T00:00:00",
            "bar_index": 1,
            "cohort": COHORT_CURRENT,
            "trend_direction": "DOWN",
            "volume_decreasing": False,
            "weak_selling_result": False,
            "stratum": STRATUM_NEITHER,
        },
        {
            "symbol": "AAA.NS",
            "session": "2026-01-02T00:00:00",
            "bar_index": 2,
            "cohort": COHORT_CURRENT,
            "trend_direction": "DOWN",
            "volume_decreasing": True,
            "weak_selling_result": False,
            "stratum": STRATUM_VOLUME_ONLY,
        },
        {
            "symbol": "BBB.NS",
            "session": "2026-01-03T00:00:00",
            "bar_index": 3,
            "cohort": COHORT_CURRENT,
            "trend_direction": "DOWN",
            "volume_decreasing": False,
            "weak_selling_result": True,
            "stratum": STRATUM_WEAK_RESULT_ONLY,
        },
        {
            "symbol": "BBB.NS",
            "session": "2026-01-04T00:00:00",
            "bar_index": 4,
            "cohort": COHORT_CURRENT,
            "trend_direction": "DOWN",
            "volume_decreasing": True,
            "weak_selling_result": True,
            "stratum": STRATUM_BOTH,
        },
        {
            "symbol": "AAA.NS",
            "session": "2026-01-05T00:00:00",
            "bar_index": 5,
            "cohort": COHORT_ALTERNATE,
            "trend_direction": "UP",
            "volume_decreasing": True,
            "weak_selling_result": False,
            "stratum": STRATUM_VOLUME_ONLY,
        },
        {
            "symbol": "BBB.NS",
            "session": "2026-01-06T00:00:00",
            "bar_index": 6,
            "cohort": COHORT_ALTERNATE,
            "trend_direction": "UP",
            "volume_decreasing": True,
            "weak_selling_result": True,
            "stratum": STRATUM_BOTH,
        },
    ]
    return pd.DataFrame(rows)


def _pair_rows() -> pd.DataFrame:
    targets = _targets()
    deltas = {
        "2026-01-01T00:00:00": -2.0,
        "2026-01-02T00:00:00": 4.0,
        "2026-01-03T00:00:00": -1.0,
        "2026-01-04T00:00:00": 6.0,
        "2026-01-05T00:00:00": 2.0,
        "2026-01-06T00:00:00": 8.0,
    }
    rows: list[dict[str, object]] = []
    for target in targets.itertuples(index=False):
        delta = deltas[target.session]
        rows.append(
            {
                "symbol": target.symbol,
                "cohort": target.cohort,
                "trend_direction": target.trend_direction,
                "target_session": target.session,
                "target_bar_index": target.bar_index,
                "horizon_sessions": 5,
                "paired_return_delta_pct": delta,
                "target_positive_close": delta > 0.0,
                "control_positive_close": False,
                "paired_mfe_delta_pct": delta / 2.0,
                "paired_mae_delta_pct": delta / 4.0,
                "clean_pair": target.session
                != "2026-01-06T00:00:00",
            }
        )
    return pd.DataFrame(rows)


@pytest.mark.parametrize(
    ("volume", "weak_result", "expected"),
    [
        (False, False, STRATUM_NEITHER),
        (True, False, STRATUM_VOLUME_ONLY),
        (False, True, STRATUM_WEAK_RESULT_ONLY),
        (True, True, STRATUM_BOTH),
    ],
)
def test_confirmation_stratum(
    volume: bool,
    weak_result: bool,
    expected: str,
) -> None:
    assert (
        confirmation_stratum(
            volume_decreasing=volume,
            weak_selling_result=weak_result,
        )
        == expected
    )


def test_stratum_counts_partition_each_cohort() -> None:
    targets = _targets()
    rows = build_confirmation_count_rows(
        targets,
        dimension="STRATUM",
        segments=CONFIRMATION_STRATA,
    )

    current = [
        row for row in rows if row.cohort == COHORT_CURRENT
    ]
    alternate = [
        row for row in rows if row.cohort == COHORT_ALTERNATE
    ]

    assert sum(row.target_count for row in current) == 4
    assert sum(row.target_count for row in alternate) == 2

    current_by_segment = {
        row.segment: row.target_count for row in current
    }
    assert current_by_segment == {
        STRATUM_NEITHER: 1,
        STRATUM_VOLUME_ONLY: 1,
        STRATUM_WEAK_RESULT_ONLY: 1,
        STRATUM_BOTH: 1,
    }


def test_gate_counts_overlap_by_design() -> None:
    rows = build_confirmation_count_rows(
        _targets(),
        dimension="GATE",
        segments=CONFIRMATION_GATES,
    )
    current = {
        row.segment: row.target_count
        for row in rows
        if row.cohort == COHORT_CURRENT
    }
    alternate = {
        row.segment: row.target_count
        for row in rows
        if row.cohort == COHORT_ALTERNATE
    }

    assert current[GATE_VOLUME_DECREASING] == 2
    assert current[GATE_WEAK_SELLING_RESULT] == 2
    assert current[GATE_BOTH] == 1

    assert alternate[GATE_VOLUME_DECREASING] == 2
    assert alternate[GATE_WEAK_SELLING_RESULT] == 1
    assert alternate[GATE_BOTH] == 1


def test_stratum_outcomes_preserve_clean_and_raw_views() -> None:
    outcomes, symbols = build_confirmation_outcome_rows(
        targets=_targets(),
        pair_outcomes=_pair_rows(),
        dimension="STRATUM",
        segments=CONFIRMATION_STRATA,
        horizons=(5,),
    )

    current_both = next(
        row
        for row in outcomes
        if row.cohort == COHORT_CURRENT
        and row.segment == STRATUM_BOTH
    )
    assert current_both.source_target_count == 1
    assert current_both.pair_count == 1
    assert current_both.clean_pair_count == 1
    assert current_both.clean_mean_paired_return_delta_pct == 6.0

    # A segment with no clean pairs remains visible in the count
    # ledger, but is omitted from outcome summaries rather than emitting
    # NaN clean statistics.
    assert not any(
        row.cohort == COHORT_ALTERNATE
        and row.segment == STRATUM_BOTH
        for row in outcomes
    )
    assert not any(
        row.cohort == COHORT_ALTERNATE
        and row.segment == STRATUM_BOTH
        for row in symbols
    )


def test_volume_gate_aggregates_volume_only_and_both() -> None:
    outcomes, symbols = build_confirmation_outcome_rows(
        targets=_targets(),
        pair_outcomes=_pair_rows(),
        dimension="GATE",
        segments=CONFIRMATION_GATES,
        horizons=(5,),
    )

    current_volume = next(
        row
        for row in outcomes
        if row.cohort == COHORT_CURRENT
        and row.segment == GATE_VOLUME_DECREASING
    )
    assert current_volume.source_target_count == 2
    assert current_volume.clean_pair_count == 2
    assert current_volume.clean_mean_paired_return_delta_pct == 5.0

    current_symbol_rows = [
        row
        for row in symbols
        if row.cohort == COHORT_CURRENT
        and row.segment == GATE_VOLUME_DECREASING
    ]
    assert len(current_symbol_rows) == 2
    assert (
        current_volume.clean_symbol_normalized_return_delta_pct
        == pytest.approx(5.0)
    )
    assert current_volume.clean_positive_return_symbol_count == 2
    assert current_volume.clean_negative_return_symbol_count == 0
    assert current_volume.clean_zero_return_symbol_count == 0
