from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from models import (
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    StructuralPattern,
    TrendDirection,
    TrendState,
)
from weekly_behavior import WeeklyBehaviorStateBuilder
from weekly_setup import WeeklyPriceZone


def _evidence(
    code: EvidenceCode,
    bar_index: int,
    direction: EvidenceDirection,
    category: EvidenceCategory,
) -> Evidence:
    return Evidence(
        code=code,
        category=category,
        direction=direction,
        strength=0.8,
        weight=1.0,
        observation=str(code),
        description="weekly behavior fixture",
        bar_index=bar_index,
        week_beginning=f"W{bar_index:03d}",
    )


def test_behavior_state_groups_existing_point_in_time_evidence() -> None:
    supply = _evidence(
        EvidenceCode.SUPPLY_COMING_IN,
        8,
        EvidenceDirection.BEARISH,
        EvidenceCategory.SUPPLY,
    )
    demand = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        9,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    effort = _evidence(
        EvidenceCode.EFFORT_GT_RESULT,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.EFFORT,
    )
    absorption = _evidence(
        EvidenceCode.ABSORPTION,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.ABSORPTION,
    )
    progression = _evidence(
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.TREND,
    )

    state = WeeklyBehaviorStateBuilder.build(
        symbol="lt.ns",
        week="W010",
        bar_index=10,
        trend_direction=TrendDirection.UP,
        trend_state=TrendState.HEALTHY,
        structural_pattern=StructuralPattern.IMPROVING,
        current_evidence=(effort, absorption, progression),
        recent_evidence=(supply, demand, effort, absorption, progression),
        professional_strength=0.8,
        professional_weakness=0.2,
        professional_net_strength=0.6,
        professional_net_pressure=0.4,
        professional_confidence=0.75,
    )

    assert state.symbol == "LT.NS"
    assert state.supply_evidence == (supply,)
    assert state.demand_evidence == (demand,)
    assert state.effort_result_evidence == (effort,)
    assert state.absorption_evidence == (absorption,)
    assert state.progression_evidence == (progression,)
    assert state.structural_reference_direction is EvidenceDirection.BULLISH
    assert state.aligned_evidence == (demand, effort, absorption, progression)
    assert state.opposing_evidence == (supply,)
    assert state.professional_net_strength == pytest.approx(0.6)
    assert state.professional_net_pressure == pytest.approx(0.4)
    assert state.professional_confidence == pytest.approx(0.75)
    assert state.is_actionable is False


def test_future_evidence_is_excluded_defensively() -> None:
    current = _evidence(
        EvidenceCode.NO_SUPPLY,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    future = _evidence(
        EvidenceCode.TEST,
        11,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    stale_current_argument = _evidence(
        EvidenceCode.NO_DEMAND,
        9,
        EvidenceDirection.BEARISH,
        EvidenceCategory.SUPPLY,
    )

    state = WeeklyBehaviorStateBuilder.build(
        symbol="TEST.NS",
        week="W010",
        bar_index=10,
        trend_direction=TrendDirection.UP,
        trend_state=TrendState.DEVELOPING,
        structural_pattern=StructuralPattern.STABLE,
        current_evidence=(stale_current_argument, current, future),
        recent_evidence=(stale_current_argument, current, future),
    )

    assert state.current_evidence == (current,)
    assert future not in state.recent_evidence
    assert tuple(item.bar_index for item in state.recent_evidence) == (9, 10)


def test_downtrend_alignment_keeps_bullish_evidence_as_opposition() -> None:
    bullish = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    bearish = _evidence(
        EvidenceCode.SUPPLY_COMING_IN,
        10,
        EvidenceDirection.BEARISH,
        EvidenceCategory.SUPPLY,
    )

    state = WeeklyBehaviorStateBuilder.build(
        symbol="TEST.NS",
        week="W010",
        bar_index=10,
        trend_direction=TrendDirection.DOWN,
        trend_state=TrendState.HEALTHY,
        structural_pattern=StructuralPattern.WEAKENING,
        current_evidence=(bullish, bearish),
        recent_evidence=(bullish, bearish),
    )

    assert state.structural_reference_direction is EvidenceDirection.BEARISH
    assert state.aligned_evidence == (bearish,)
    assert state.opposing_evidence == (bullish,)


def test_range_does_not_invent_directional_alignment() -> None:
    bullish = _evidence(
        EvidenceCode.NO_SUPPLY,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    bearish = _evidence(
        EvidenceCode.NO_DEMAND,
        10,
        EvidenceDirection.BEARISH,
        EvidenceCategory.SUPPLY,
    )

    state = WeeklyBehaviorStateBuilder.build(
        symbol="TEST.NS",
        week="W010",
        bar_index=10,
        trend_direction=TrendDirection.RANGE,
        trend_state=TrendState.CORRECTING,
        structural_pattern=StructuralPattern.STABLE,
        current_evidence=(bullish, bearish),
        recent_evidence=(bullish, bearish),
    )

    assert state.structural_reference_direction is EvidenceDirection.NEUTRAL
    assert state.bullish_evidence == (bullish,)
    assert state.bearish_evidence == (bearish,)
    assert state.aligned_evidence == ()
    assert state.opposing_evidence == ()
    assert state.has_directional_structural_reference is False


def test_from_audit_projects_wf1_snapshot_without_reinterpreting_it() -> None:
    demand = _evidence(
        EvidenceCode.INCREASING_DEMAND,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    support = WeeklyPriceZone(lower=95.0, upper=100.0)
    resistance = WeeklyPriceZone(lower=115.0, upper=120.0)
    audit = SimpleNamespace(
        symbol="ABC.NS",
        week="W010",
        bar_index=10,
        trend_direction=TrendDirection.UP,
        trend_state=TrendState.HEALTHY,
        structural_pattern=StructuralPattern.IMPROVING,
        structural_swing_lineage=(),
        current_evidence=(demand,),
        recent_evidence=(demand,),
        support_zone=support,
        resistance_zone=resistance,
        professional_strength=0.9,
        professional_weakness=0.1,
        professional_net_strength=0.8,
        professional_net_pressure=0.6,
        professional_confidence=0.85,
    )

    state = WeeklyBehaviorStateBuilder.from_audit(audit)  # type: ignore[arg-type]

    assert state.current_evidence == (demand,)
    assert state.recent_evidence == (demand,)
    assert state.support_zone == support
    assert state.resistance_zone == resistance
    assert state.aligned_evidence == (demand,)
    assert state.professional_strength == pytest.approx(0.9)
    assert state.professional_weakness == pytest.approx(0.1)
    assert state.professional_confidence == pytest.approx(0.85)


def test_state_is_immutable_and_has_no_actionability_authority() -> None:
    state = WeeklyBehaviorStateBuilder.build(
        symbol="TEST.NS",
        week="W010",
        bar_index=10,
        trend_direction=TrendDirection.UNKNOWN,
        trend_state=TrendState.UNKNOWN,
        structural_pattern=StructuralPattern.UNKNOWN,
    )

    assert state.is_actionable is False
    with pytest.raises(FrozenInstanceError):
        state.symbol = "OTHER.NS"  # type: ignore[misc]


def test_invalid_identity_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="symbol cannot be empty"):
        WeeklyBehaviorStateBuilder.build(
            symbol="  ",
            week="W010",
            bar_index=10,
            trend_direction=TrendDirection.UNKNOWN,
            trend_state=TrendState.UNKNOWN,
            structural_pattern=StructuralPattern.UNKNOWN,
        )

    with pytest.raises(ValueError, match="bar_index cannot be negative"):
        WeeklyBehaviorStateBuilder.build(
            symbol="TEST.NS",
            week="W010",
            bar_index=-1,
            trend_direction=TrendDirection.UNKNOWN,
            trend_state=TrendState.UNKNOWN,
            structural_pattern=StructuralPattern.UNKNOWN,
        )
