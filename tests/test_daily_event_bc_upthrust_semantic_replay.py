from __future__ import annotations

import pytest

from audit.daily_event_bc_upthrust_semantic_replay import (
    BC_ACCEPTANCE_MIDDLE,
    BC_ACCEPTANCE_STRONG,
    BC_ACCEPTANCE_WEAK,
    POPULATION_BC_CORE,
    POPULATION_UT_LOCAL,
    POPULATION_UT_STRUCTURAL,
    BcUpthrustSemanticObservation,
    build_pairwise_rows,
    classify_bc_acceptance,
    rejects_reference_high,
)
from models import (
    BarContext,
    ClosePosition,
    Direction,
    SpreadClass,
    VolumeClass,
)


def _bar(
    *,
    high: float = 110.0,
    low: float = 100.0,
    close: float = 105.0,
    close_position: ClosePosition = ClosePosition.MIDDLE,
) -> BarContext:
    return BarContext(
        week_beginning="2026-01-01T00:00:00",
        bar_index=10,
        spread=SpreadClass.ABOVE_AVERAGE,
        volume=VolumeClass.VERY_HIGH,
        direction=Direction.UP,
        close_position=close_position,
        spread_ratio=1.2,
        volume_ratio=1.5,
        open=103.0,
        high=high,
        low=low,
        close_price=close,
        body=2.0,
        upper_shadow=max(0.0, high - max(103.0, close)),
        lower_shadow=max(0.0, min(103.0, close) - low),
        close_ratio=(close - low) / (high - low),
        prev_high=108.0,
        prev_low=99.0,
        prev_close=104.0,
        prev_spread=9.0,
    )


@pytest.mark.parametrize(
    ("close_position", "expected"),
    (
        (ClosePosition.ON_HIGH, BC_ACCEPTANCE_STRONG),
        (ClosePosition.UPPER, BC_ACCEPTANCE_STRONG),
        (ClosePosition.MIDDLE, BC_ACCEPTANCE_MIDDLE),
        (ClosePosition.LOWER, BC_ACCEPTANCE_WEAK),
        (ClosePosition.ON_LOW, BC_ACCEPTANCE_WEAK),
    ),
)
def test_bc_acceptance_uses_existing_close_position_buckets(
    close_position: ClosePosition,
    expected: str,
) -> None:
    assert classify_bc_acceptance(
        _bar(close_position=close_position)
    ) == expected


def test_rejects_reference_high_is_threshold_free_probe_and_failure() -> None:
    assert rejects_reference_high(
        _bar(high=110.0, close=108.0),
        108.0,
    )
    assert not rejects_reference_high(
        _bar(high=108.0, close=107.0),
        108.0,
    )
    assert not rejects_reference_high(
        _bar(high=110.0, close=108.5),
        108.0,
    )


def _observation(
    *,
    session: str,
    bc: bool,
    local: bool,
    structural: bool,
) -> BcUpthrustSemanticObservation:
    return BcUpthrustSemanticObservation(
        symbol="A.NS",
        bar_index=int(session[-2:]),
        session=f"2026-01-{session}T00:00:00",
        bc_effort_core=bc,
        bc_acceptance=BC_ACCEPTANCE_MIDDLE if bc else "",
        ut_local_rejection=local,
        ut_structural_rejection=structural,
        direction="UP",
        volume_class="VERY_HIGH",
        spread_class="ABOVE_AVERAGE",
        close_position="MIDDLE",
        close_ratio=0.5,
        upper_shadow_ratio=0.3,
        volume_ratio=1.5,
        spread_ratio=1.2,
        previous_high=100.0,
        structural_high_reference=99.0 if structural else None,
        structural_high_pivot_index=5 if structural else None,
        structural_high_confirmation_index=7 if structural else None,
    )


def test_pairwise_reports_partial_overlap_and_subset_relationships() -> None:
    observations = (
        _observation(session="01", bc=True, local=True, structural=True),
        _observation(session="02", bc=True, local=False, structural=False),
        _observation(session="03", bc=False, local=True, structural=True),
        _observation(session="04", bc=False, local=True, structural=False),
    )

    rows = build_pairwise_rows(observations)

    bc_local = next(
        row
        for row in rows
        if row.population_a == POPULATION_BC_CORE
        and row.population_b == POPULATION_UT_LOCAL
    )
    bc_structural = next(
        row
        for row in rows
        if row.population_a == POPULATION_BC_CORE
        and row.population_b == POPULATION_UT_STRUCTURAL
    )
    local_structural = next(
        row
        for row in rows
        if row.population_a == POPULATION_UT_LOCAL
        and row.population_b == POPULATION_UT_STRUCTURAL
    )

    assert bc_local.population_a_count == 2
    assert bc_local.population_b_count == 3
    assert bc_local.overlap_count == 1
    assert bc_local.relationship == "PARTIAL_OVERLAP"

    assert bc_structural.population_a_count == 2
    assert bc_structural.population_b_count == 2
    assert bc_structural.overlap_count == 1
    assert bc_structural.relationship == "PARTIAL_OVERLAP"

    assert local_structural.population_a_count == 3
    assert local_structural.population_b_count == 2
    assert local_structural.overlap_count == 2
    assert local_structural.relationship == "B_STRICT_SUBSET_OF_A"
