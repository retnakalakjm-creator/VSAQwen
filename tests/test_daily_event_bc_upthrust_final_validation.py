from __future__ import annotations

import pandas as pd

from audit.daily_event_bc_upthrust_final_validation import (
    BC_CANDIDATE,
    ERA_2023_2026,
    PARTITION_BC_ONLY,
    PARTITION_BOTH,
    PARTITION_UT_ONLY,
    TRANSITION_BC_TO_UT,
    TRANSITION_UT_TO_BC,
    UT_CANDIDATE,
    build_behavior_mapping_rows,
    build_era_rows,
    build_partition_rows,
    build_symbol_summary_rows,
    build_transition_rows,
    CandidateSymbolRow,
)
from daily_behavior import DailyBehaviorDimension
from models import EvidenceCode
from weekly_setup import WeeklySetupDirection


def _observations() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "AAA.NS",
                "bar_index": 10,
                "session": "2026-01-10T00:00:00",
                "era": ERA_2023_2026,
                "bc_candidate": True,
                "ut_candidate": False,
            },
            {
                "symbol": "AAA.NS",
                "bar_index": 12,
                "session": "2026-01-12T00:00:00",
                "era": ERA_2023_2026,
                "bc_candidate": False,
                "ut_candidate": True,
            },
            {
                "symbol": "AAA.NS",
                "bar_index": 15,
                "session": "2026-01-15T00:00:00",
                "era": ERA_2023_2026,
                "bc_candidate": True,
                "ut_candidate": True,
            },
            {
                "symbol": "BBB.NS",
                "bar_index": 20,
                "session": "2026-02-20T00:00:00",
                "era": ERA_2023_2026,
                "bc_candidate": False,
                "ut_candidate": True,
            },
            {
                "symbol": "BBB.NS",
                "bar_index": 24,
                "session": "2026-02-24T00:00:00",
                "era": ERA_2023_2026,
                "bc_candidate": True,
                "ut_candidate": False,
            },
        ]
    )


def test_partition_keeps_same_bar_overlap_explicit() -> None:
    rows = build_partition_rows(_observations())
    lookup = {row.partition: row.event_count for row in rows}

    assert lookup[PARTITION_BC_ONLY] == 2
    assert lookup[PARTITION_UT_ONLY] == 2
    assert lookup[PARTITION_BOTH] == 1


def test_transition_uses_existing_five_bar_window_as_positive_offsets_1_to_4() -> None:
    rows, offsets, eras = build_transition_rows(
        _observations(),
        lookback_bars=5,
    )

    bc_to_ut = next(
        row for row in rows if row.transition == TRANSITION_BC_TO_UT
    )
    ut_to_bc = next(
        row for row in rows if row.transition == TRANSITION_UT_TO_BC
    )

    assert bc_to_ut.source_event_count == 3
    assert bc_to_ut.source_with_target_count == 1
    assert bc_to_ut.ordered_pair_count == 1
    assert bc_to_ut.median_positive_offset == 2.0

    assert ut_to_bc.source_event_count == 3
    assert ut_to_bc.source_with_target_count == 2
    assert ut_to_bc.ordered_pair_count == 2
    assert ut_to_bc.median_positive_offset == 3.5

    bc_offset_2 = next(
        row
        for row in offsets
        if row.transition == TRANSITION_BC_TO_UT
        and row.positive_offset == 2
    )
    ut_offset_3 = next(
        row
        for row in offsets
        if row.transition == TRANSITION_UT_TO_BC
        and row.positive_offset == 3
    )
    ut_offset_4 = next(
        row
        for row in offsets
        if row.transition == TRANSITION_UT_TO_BC
        and row.positive_offset == 4
    )

    assert bc_offset_2.ordered_pair_count == 1
    assert ut_offset_3.ordered_pair_count == 1
    assert ut_offset_4.ordered_pair_count == 1

    assert len(eras) == 10


def test_era_rows_keep_candidates_separate() -> None:
    rows = build_era_rows(_observations())

    bc_latest = next(
        row
        for row in rows
        if row.candidate == BC_CANDIDATE
        and row.era == ERA_2023_2026
    )
    ut_latest = next(
        row
        for row in rows
        if row.candidate == UT_CANDIDATE
        and row.era == ERA_2023_2026
    )

    assert bc_latest.event_count == 3
    assert ut_latest.event_count == 3
    assert bc_latest.symbol_count == 2
    assert ut_latest.symbol_count == 2


def test_symbol_summary_reports_cross_symbol_distribution() -> None:
    rows = (
        CandidateSymbolRow(
            symbol="AAA.NS",
            evaluated_target_count=100,
            bc_candidate_count=2,
            bc_candidate_rate=0.02,
            ut_candidate_count=10,
            ut_candidate_rate=0.10,
            same_bar_overlap_count=1,
        ),
        CandidateSymbolRow(
            symbol="BBB.NS",
            evaluated_target_count=200,
            bc_candidate_count=4,
            bc_candidate_rate=0.02,
            ut_candidate_count=20,
            ut_candidate_rate=0.10,
            same_bar_overlap_count=0,
        ),
    )

    summaries = build_symbol_summary_rows(rows)
    bc = next(row for row in summaries if row.candidate == BC_CANDIDATE)
    ut = next(row for row in summaries if row.candidate == UT_CANDIDATE)

    assert bc.event_count == 6
    assert bc.symbol_count == 2
    assert bc.median_symbol_count == 3.0
    assert bc.max_symbol_share_of_candidate == 4 / 6

    assert ut.event_count == 30
    assert ut.symbol_count == 2
    assert ut.median_symbol_count == 15.0


def test_current_behavior_layer_collapses_bc_and_ut_to_same_dimension() -> None:
    rows = build_behavior_mapping_rows()

    assert {
        (row.evidence_code, row.weekly_direction, row.dimension)
        for row in rows
    } == {
        (
            EvidenceCode.BUYING_CLIMAX.value,
            WeeklySetupDirection.BEARISH.value,
            DailyBehaviorDimension.REJECTION_OF_OPPOSING_MOVE.value,
        ),
        (
            EvidenceCode.UPTHRUST.value,
            WeeklySetupDirection.BEARISH.value,
            DailyBehaviorDimension.REJECTION_OF_OPPOSING_MOVE.value,
        ),
    }
