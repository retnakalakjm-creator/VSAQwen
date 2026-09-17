from __future__ import annotations

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
        description="weekly evolution fixture",
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
        professional_net_pressure=net_pressure,
    )


def test_single_opposing_week_is_minor_not_a_campaign_reversal() -> None:
    aligned = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )
    opposition = _evidence(
        EvidenceCode.SUPPLY_COMING_IN,
        11,
        EvidenceDirection.BEARISH,
        EvidenceCategory.SUPPLY,
    )

    evolution = WeeklyBehaviorEvolutionEngine.evaluate(
        [
            _state(10, current_evidence=(aligned,)),
            _state(11, current_evidence=(opposition,), net_pressure=0.2),
        ]
    )

    assert evolution.reference_direction is EvidenceDirection.BULLISH
    assert evolution.current_structural_direction is EvidenceDirection.BULLISH
    assert evolution.current_opposing_evidence == (opposition,)
    assert evolution.consecutive_opposing_weeks == 1
    assert evolution.contradiction_state is WeeklyContradictionState.MINOR
    assert evolution.structural_direction_changed is False
    assert evolution.is_actionable is False


def test_repeated_opposition_becomes_meaningful_without_reversing_structure() -> None:
    opposition_1 = _evidence(
        EvidenceCode.SUPPLY_COMING_IN,
        11,
        EvidenceDirection.BEARISH,
        EvidenceCategory.SUPPLY,
    )
    opposition_2 = _evidence(
        EvidenceCode.NO_DEMAND,
        12,
        EvidenceDirection.BEARISH,
        EvidenceCategory.SUPPLY,
    )

    evolution = WeeklyBehaviorEvolutionEngine.evaluate(
        [
            _state(10),
            _state(11, current_evidence=(opposition_1,), net_pressure=0.1),
            _state(12, current_evidence=(opposition_2,), net_pressure=0.1),
        ]
    )

    assert evolution.reference_direction is EvidenceDirection.BULLISH
    assert evolution.current_structural_direction is EvidenceDirection.BULLISH
    assert evolution.consecutive_opposing_weeks == 2
    assert evolution.contradiction_state is WeeklyContradictionState.MEANINGFUL
    assert evolution.structural_direction_changed is False


def test_professional_pressure_can_make_current_opposition_meaningful() -> None:
    opposition = _evidence(
        EvidenceCode.SUPPLY_COMING_IN,
        11,
        EvidenceDirection.BEARISH,
        EvidenceCategory.SUPPLY,
    )

    evolution = WeeklyBehaviorEvolutionEngine.evaluate(
        [
            _state(10),
            _state(11, current_evidence=(opposition,), net_pressure=-0.5),
        ]
    )

    assert evolution.consecutive_opposing_weeks == 1
    assert evolution.professional_pressure_opposes_reference is True
    assert evolution.contradiction_state is WeeklyContradictionState.MEANINGFUL


def test_structural_weakening_is_stronger_than_a_plain_opposing_bar() -> None:
    evolution = WeeklyBehaviorEvolutionEngine.evaluate(
        [
            _state(10),
            _state(
                11,
                trend_state=TrendState.EXHAUSTED,
                structural_pattern=StructuralPattern.WEAKENING,
            ),
        ]
    )

    assert evolution.structural_pattern_opposes_reference is True
    assert evolution.structural_weakening_present is True
    assert evolution.contradiction_state is WeeklyContradictionState.CAMPAIGN_WEAKENING
    assert evolution.structural_direction_changed is False


def test_structural_pattern_is_interpreted_relative_to_reference_direction() -> None:
    bearish_aligned = WeeklyBehaviorEvolutionEngine.evaluate(
        [
            _state(
                10,
                trend_direction=TrendDirection.DOWN,
                structural_pattern=StructuralPattern.WEAKENING,
                net_pressure=-0.4,
            ),
            _state(
                11,
                trend_direction=TrendDirection.DOWN,
                structural_pattern=StructuralPattern.WEAKENING,
                net_pressure=-0.4,
            ),
        ]
    )

    assert bearish_aligned.reference_direction is EvidenceDirection.BEARISH
    assert bearish_aligned.structural_pattern_opposes_reference is False
    assert bearish_aligned.structural_weakening_present is False
    assert bearish_aligned.contradiction_state is WeeklyContradictionState.NONE

    bearish_opposed = WeeklyBehaviorEvolutionEngine.evaluate(
        [
            _state(
                10,
                trend_direction=TrendDirection.DOWN,
                structural_pattern=StructuralPattern.WEAKENING,
                net_pressure=-0.4,
            ),
            _state(
                11,
                trend_direction=TrendDirection.DOWN,
                structural_pattern=StructuralPattern.IMPROVING,
                net_pressure=-0.4,
            ),
        ]
    )

    assert bearish_opposed.structural_pattern_opposes_reference is True
    assert bearish_opposed.structural_weakening_present is True
    assert bearish_opposed.contradiction_state is WeeklyContradictionState.CAMPAIGN_WEAKENING


def test_structural_direction_change_is_explicit_invalidation_evidence() -> None:
    bearish = _evidence(
        EvidenceCode.INCREASING_SUPPLY,
        11,
        EvidenceDirection.BEARISH,
        EvidenceCategory.SUPPLY,
    )

    evolution = WeeklyBehaviorEvolutionEngine.evaluate(
        [
            _state(10, trend_direction=TrendDirection.UP),
            _state(
                11,
                trend_direction=TrendDirection.DOWN,
                trend_state=TrendState.DEVELOPING,
                structural_pattern=StructuralPattern.WEAKENING,
                current_evidence=(bearish,),
                net_pressure=-0.5,
            ),
        ]
    )

    assert evolution.reference_direction is EvidenceDirection.BULLISH
    assert evolution.current_structural_direction is EvidenceDirection.BEARISH
    assert evolution.structural_direction_changed is True
    assert (
        evolution.contradiction_state
        is WeeklyContradictionState.STRUCTURAL_INVALIDATION_EVIDENCE
    )
    assert evolution.is_actionable is False


def test_reversing_state_plus_opposing_progression_is_invalidation_evidence() -> None:
    progression = _evidence(
        EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
        11,
        EvidenceDirection.BEARISH,
        EvidenceCategory.TREND,
    )

    evolution = WeeklyBehaviorEvolutionEngine.evaluate(
        [
            _state(10),
            _state(
                11,
                trend_state=TrendState.REVERSING,
                structural_pattern=StructuralPattern.WEAKENING,
                current_evidence=(progression,),
                recent_evidence=(progression,),
            ),
        ]
    )

    assert evolution.opposing_progression_present is True
    assert evolution.structural_direction_changed is False
    assert (
        evolution.contradiction_state
        is WeeklyContradictionState.STRUCTURAL_INVALIDATION_EVIDENCE
    )


def test_old_recent_opposition_does_not_fake_consecutive_current_opposition() -> None:
    old_opposition = _evidence(
        EvidenceCode.SUPPLY_COMING_IN,
        10,
        EvidenceDirection.BEARISH,
        EvidenceCategory.SUPPLY,
    )
    current_aligned = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        11,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )

    evolution = WeeklyBehaviorEvolutionEngine.evaluate(
        [
            _state(10, current_evidence=(old_opposition,), net_pressure=0.2),
            _state(
                11,
                current_evidence=(current_aligned,),
                recent_evidence=(old_opposition, current_aligned),
                net_pressure=0.4,
            ),
        ]
    )

    assert evolution.current_opposing_evidence == ()
    assert evolution.current_aligned_evidence == (current_aligned,)
    assert evolution.consecutive_opposing_weeks == 0
    assert evolution.contradiction_state is WeeklyContradictionState.NONE


def test_range_without_prior_direction_does_not_invent_campaign_reference() -> None:
    bullish = _evidence(
        EvidenceCode.NO_SUPPLY,
        10,
        EvidenceDirection.BULLISH,
        EvidenceCategory.DEMAND,
    )

    evolution = WeeklyBehaviorEvolutionEngine.evaluate(
        [
            _state(
                10,
                trend_direction=TrendDirection.RANGE,
                trend_state=TrendState.CORRECTING,
                structural_pattern=StructuralPattern.STABLE,
                current_evidence=(bullish,),
            )
        ]
    )

    assert evolution.reference_direction is EvidenceDirection.NEUTRAL
    assert evolution.current_structural_direction is EvidenceDirection.NEUTRAL
    assert evolution.current_aligned_evidence == ()
    assert evolution.current_opposing_evidence == ()
    assert evolution.contradiction_state is WeeklyContradictionState.NONE


def test_history_validation_rejects_mixed_symbols_and_non_monotonic_indices() -> None:
    with pytest.raises(ValueError, match="same symbol"):
        WeeklyBehaviorEvolutionEngine.evaluate(
            [_state(10, symbol="AAA.NS"), _state(11, symbol="BBB.NS")]
        )

    with pytest.raises(ValueError, match="strictly increasing"):
        WeeklyBehaviorEvolutionEngine.evaluate([_state(10), _state(10)])


def test_history_validation_requires_a_state_and_bar_index() -> None:
    with pytest.raises(ValueError, match="at least one"):
        WeeklyBehaviorEvolutionEngine.evaluate([])

    state = WeeklyBehaviorState(
        symbol="TEST.NS",
        week="W010",
        bar_index=None,
        trend_direction=TrendDirection.UP,
        trend_state=TrendState.HEALTHY,
        structural_pattern=StructuralPattern.IMPROVING,
    )
    with pytest.raises(ValueError, match="requires bar_index"):
        WeeklyBehaviorEvolutionEngine.evaluate([state])
