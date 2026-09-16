from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

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
from weekly_behavior import WeeklyBehaviorState, WeeklyBehaviorStateBuilder
from weekly_behavior_evolution import (
    WeeklyBehaviorEvolutionEngine,
    WeeklyContradictionState,
)
from weekly_thesis import (
    ShadowWeeklyThesisBasis,
    ShadowWeeklyThesisBuilder,
    ShadowWeeklyThesisState,
)


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
        description="shadow weekly thesis fixture",
        bar_index=bar_index,
        week_beginning=f"W{bar_index:03d}",
    )


def _state(
    bar_index: int,
    *,
    trend_direction: TrendDirection = TrendDirection.UP,
    trend_state: TrendState = TrendState.HEALTHY,
    structural_pattern: StructuralPattern = StructuralPattern.IMPROVING,
    current_evidence: tuple[Evidence, ...] = (),
    recent_evidence: tuple[Evidence, ...] | None = None,
    net_pressure: float = 0.4,
    symbol: str = "TEST.NS",
) -> WeeklyBehaviorState:
    return WeeklyBehaviorStateBuilder.build(
        symbol=symbol,
        week=f"W{bar_index:03d}",
        bar_index=bar_index,
        trend_direction=trend_direction,
        trend_state=trend_state,
        structural_pattern=structural_pattern,
        current_evidence=current_evidence,
        recent_evidence=current_evidence if recent_evidence is None else recent_evidence,
        professional_strength=0.7,
        professional_weakness=0.3,
        professional_net_strength=0.4,
        professional_net_pressure=net_pressure,
        professional_confidence=0.8,
    )


def _build(states: list[WeeklyBehaviorState]):
    evolution = WeeklyBehaviorEvolutionEngine.evaluate(states)
    return ShadowWeeklyThesisBuilder.build(
        behavior=states[-1],
        evolution=evolution,
    )


def test_non_directional_structure_produces_no_thesis() -> None:
    bullish = _evidence(
        EvidenceCode.NO_SUPPLY,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    state = _state(
        10,
        trend_direction=TrendDirection.RANGE,
        trend_state=TrendState.CORRECTING,
        structural_pattern=StructuralPattern.STABLE,
        current_evidence=(bullish,),
    )

    thesis = _build([state])

    assert thesis.state is ShadowWeeklyThesisState.NO_THESIS
    assert thesis.basis is ShadowWeeklyThesisBasis.NO_DIRECTIONAL_REFERENCE
    assert thesis.direction is EvidenceDirection.NEUTRAL
    assert thesis.has_directional_thesis is False
    assert thesis.is_actionable is False


def test_directional_reference_without_support_is_developing() -> None:
    thesis = _build([_state(10)])

    assert thesis.direction is EvidenceDirection.BULLISH
    assert thesis.state is ShadowWeeklyThesisState.BULLISH_DEVELOPING
    assert thesis.basis is ShadowWeeklyThesisBasis.DIRECTIONAL_REFERENCE_ONLY
    assert thesis.supporting_evidence == ()
    assert thesis.opposing_evidence == ()


def test_bullish_aligned_behavior_creates_supported_shadow_thesis() -> None:
    demand = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    thesis = _build([_state(10, current_evidence=(demand,))])

    assert thesis.direction is EvidenceDirection.BULLISH
    assert thesis.state is ShadowWeeklyThesisState.BULLISH_SUPPORTED
    assert thesis.basis is ShadowWeeklyThesisBasis.ALIGNED_BEHAVIOR_PRESENT
    assert thesis.supporting_evidence == (demand,)
    assert thesis.current_supporting_evidence == (demand,)
    assert thesis.contradiction_state is WeeklyContradictionState.NONE
    assert thesis.professional_confidence == pytest.approx(0.8)


def test_single_minor_contradiction_does_not_reverse_or_challenge_supported_thesis() -> None:
    demand = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    supply = _evidence(
        EvidenceCode.SUPPLY_COMING_IN,
        11,
        EvidenceDirection.BEARISH,
        EvidenceCategory.SUPPLY,
    )
    states = [
        _state(10, current_evidence=(demand,)),
        _state(
            11,
            current_evidence=(supply,),
            recent_evidence=(demand, supply),
            net_pressure=0.2,
        ),
    ]

    thesis = _build(states)

    assert thesis.state is ShadowWeeklyThesisState.BULLISH_SUPPORTED
    assert thesis.direction is EvidenceDirection.BULLISH
    assert thesis.contradiction_state is WeeklyContradictionState.MINOR
    assert thesis.supporting_evidence == (demand,)
    assert thesis.opposing_evidence == (supply,)
    assert thesis.current_opposing_evidence == (supply,)
    assert thesis.is_challenged is False


def test_repeated_fresh_opposition_becomes_challenged_thesis() -> None:
    demand = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    supply_1 = _evidence(
        EvidenceCode.SUPPLY_COMING_IN,
        11,
        EvidenceDirection.BEARISH,
        EvidenceCategory.SUPPLY,
    )
    supply_2 = _evidence(
        EvidenceCode.NO_DEMAND,
        12,
        EvidenceDirection.BEARISH,
        EvidenceCategory.SUPPLY,
    )
    states = [
        _state(10, current_evidence=(demand,)),
        _state(11, current_evidence=(supply_1,), net_pressure=0.1),
        _state(
            12,
            current_evidence=(supply_2,),
            recent_evidence=(demand, supply_1, supply_2),
            net_pressure=0.1,
        ),
    ]

    thesis = _build(states)

    assert thesis.state is ShadowWeeklyThesisState.BULLISH_CHALLENGED
    assert thesis.basis is ShadowWeeklyThesisBasis.MEANINGFUL_CONTRADICTION
    assert thesis.contradiction_state is WeeklyContradictionState.MEANINGFUL
    assert thesis.is_challenged is True
    assert thesis.has_invalidation_evidence is False


def test_structural_campaign_weakening_is_challenged_not_invalidated() -> None:
    demand = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    current = _state(
        11,
        structural_pattern=StructuralPattern.WEAKENING,
        current_evidence=(),
        recent_evidence=(demand,),
    )

    thesis = _build([_state(10, current_evidence=(demand,)), current])

    assert thesis.state is ShadowWeeklyThesisState.BULLISH_CHALLENGED
    assert thesis.basis is ShadowWeeklyThesisBasis.CAMPAIGN_WEAKENING
    assert thesis.contradiction_state is WeeklyContradictionState.CAMPAIGN_WEAKENING
    assert thesis.has_invalidation_evidence is False


def test_structural_direction_flip_preserves_old_thesis_identity_as_invalidation() -> None:
    demand = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    supply = _evidence(
        EvidenceCode.INCREASING_SUPPLY,
        11,
        EvidenceDirection.BEARISH,
        EvidenceCategory.SUPPLY,
    )
    states = [
        _state(10, current_evidence=(demand,)),
        _state(
            11,
            trend_direction=TrendDirection.DOWN,
            trend_state=TrendState.DEVELOPING,
            structural_pattern=StructuralPattern.WEAKENING,
            current_evidence=(supply,),
            recent_evidence=(demand, supply),
            net_pressure=-0.5,
        ),
    ]

    thesis = _build(states)

    assert thesis.direction is EvidenceDirection.BULLISH
    assert thesis.current_structural_direction is EvidenceDirection.BEARISH
    assert thesis.state is ShadowWeeklyThesisState.BULLISH_INVALIDATION_EVIDENCE
    assert thesis.basis is ShadowWeeklyThesisBasis.STRUCTURAL_INVALIDATION_EVIDENCE
    assert thesis.supporting_evidence == (demand,)
    assert thesis.opposing_evidence == (supply,)
    assert thesis.has_invalidation_evidence is True
    assert thesis.is_actionable is False


def test_bearish_path_is_directionally_symmetric() -> None:
    supply = _evidence(
        EvidenceCode.SUPPLY_COMING_IN,
        10,
        EvidenceDirection.BEARISH,
        EvidenceCategory.SUPPLY,
    )
    thesis = _build(
        [
            _state(
                10,
                trend_direction=TrendDirection.DOWN,
                structural_pattern=StructuralPattern.WEAKENING,
                current_evidence=(supply,),
                net_pressure=-0.4,
            )
        ]
    )

    assert thesis.direction is EvidenceDirection.BEARISH
    assert thesis.state is ShadowWeeklyThesisState.BEARISH_SUPPORTED
    assert thesis.basis is ShadowWeeklyThesisBasis.ALIGNED_BEHAVIOR_PRESENT
    assert thesis.supporting_evidence == (supply,)


def test_builder_rejects_mismatched_behavior_and_evolution_identity() -> None:
    state = _state(10)
    evolution = WeeklyBehaviorEvolutionEngine.evaluate([state])

    with pytest.raises(ValueError, match="symbol must match"):
        ShadowWeeklyThesisBuilder.build(
            behavior=state,
            evolution=replace(evolution, symbol="OTHER.NS"),
        )

    with pytest.raises(ValueError, match="bar_index must match"):
        ShadowWeeklyThesisBuilder.build(
            behavior=state,
            evolution=replace(evolution, bar_index=11),
        )

    with pytest.raises(ValueError, match="week must match"):
        ShadowWeeklyThesisBuilder.build(
            behavior=state,
            evolution=replace(evolution, week="OTHER"),
        )


def test_builder_requires_bar_index_and_thesis_is_immutable() -> None:
    state = WeeklyBehaviorState(
        symbol="TEST.NS",
        week="W010",
        bar_index=None,
        trend_direction=TrendDirection.UP,
        trend_state=TrendState.HEALTHY,
        structural_pattern=StructuralPattern.IMPROVING,
    )
    valid = _state(10)
    evolution = WeeklyBehaviorEvolutionEngine.evaluate([valid])

    with pytest.raises(ValueError, match="requires behavior bar_index"):
        ShadowWeeklyThesisBuilder.build(behavior=state, evolution=evolution)

    thesis = _build([valid])
    with pytest.raises(FrozenInstanceError):
        thesis.symbol = "OTHER.NS"  # type: ignore[misc]
