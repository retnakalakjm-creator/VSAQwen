from daily_behavior import DailyBehaviorDimension
from daily_behavior_sequence import evaluate_daily_behavior_sequence
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection
from weekly_setup import WeeklySetupDirection


def _evidence(
    code: EvidenceCode,
    direction: EvidenceDirection,
    bar_index: int,
) -> Evidence:
    return Evidence(
        code=code,
        category=EvidenceCategory.SIGNAL,
        direction=direction,
        strength=0.8,
        weight=1.0,
        observation=str(code),
        description=str(code),
        bar_index=bar_index,
        week_beginning="2026-03-09",
    )


def test_sequence_preserves_multi_bar_behavior_order_without_carry_forward() -> None:
    receding = _evidence(
        EvidenceCode.NO_SUPPLY,
        EvidenceDirection.BULLISH,
        6,
    )
    emerging = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        EvidenceDirection.BULLISH,
        8,
    )
    absorption = _evidence(
        EvidenceCode.ABSORPTION,
        EvidenceDirection.BULLISH,
        10,
    )

    result = evaluate_daily_behavior_sequence(
        weekly_direction=WeeklySetupDirection.BULLISH,
        daily_bar_index=10,
        evidence=(absorption, emerging, receding),
        lookback_bars=5,
    )

    assert result.start_bar_index == 6
    assert result.end_bar_index == 10
    assert tuple(step.bar_index for step in result.steps) == (6, 8, 10)
    assert result.steps[0].dimensions == (
        DailyBehaviorDimension.OPPOSING_PRESSURE_RECEDING,
    )
    assert result.steps[1].dimensions == (
        DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING,
    )
    assert result.steps[2].dimensions == (DailyBehaviorDimension.ABSORPTION,)
    assert result.first_bar_for(
        DailyBehaviorDimension.OPPOSING_PRESSURE_RECEDING
    ) == 6
    assert result.last_bar_for(
        DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING
    ) == 8
    assert result.is_actionable is False


def test_sequence_excludes_stale_future_and_opposing_evidence() -> None:
    stale = _evidence(
        EvidenceCode.NO_SUPPLY,
        EvidenceDirection.BULLISH,
        4,
    )
    aligned = _evidence(
        EvidenceCode.HIDDEN_DEMAND,
        EvidenceDirection.BULLISH,
        9,
    )
    opposing = _evidence(
        EvidenceCode.NO_DEMAND,
        EvidenceDirection.BEARISH,
        10,
    )
    future = _evidence(
        EvidenceCode.STOPPING_VOLUME,
        EvidenceDirection.BULLISH,
        11,
    )

    result = evaluate_daily_behavior_sequence(
        weekly_direction=WeeklySetupDirection.BULLISH,
        daily_bar_index=10,
        evidence=(future, opposing, aligned, stale),
        lookback_bars=3,
    )

    assert result.start_bar_index == 8
    assert tuple(step.bar_index for step in result.steps) == (9,)
    assert result.steps[0].evidence == (aligned,)
    assert stale not in result.steps[0].evidence
    assert future not in result.steps[0].evidence
    assert opposing not in result.steps[0].evidence


def test_sequence_keeps_repeated_dimension_occurrences_distinct() -> None:
    first = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        EvidenceDirection.BULLISH,
        7,
    )
    second = _evidence(
        EvidenceCode.INCREASING_DEMAND,
        EvidenceDirection.BULLISH,
        9,
    )

    result = evaluate_daily_behavior_sequence(
        weekly_direction=WeeklySetupDirection.BULLISH,
        daily_bar_index=10,
        evidence=(first, second),
        lookback_bars=5,
    )

    dimension = DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING
    assert result.bar_indices_for(dimension) == (7, 9)
    assert result.first_bar_for(dimension) == 7
    assert result.last_bar_for(dimension) == 9
    assert result.dimensions == (dimension,)


def test_sequence_uses_bearish_direction_relative_mapping() -> None:
    no_demand = _evidence(
        EvidenceCode.NO_DEMAND,
        EvidenceDirection.BEARISH,
        8,
    )
    supply = _evidence(
        EvidenceCode.SUPPLY_COMING_IN,
        EvidenceDirection.BEARISH,
        10,
    )

    result = evaluate_daily_behavior_sequence(
        weekly_direction=WeeklySetupDirection.BEARISH,
        daily_bar_index=10,
        evidence=(no_demand, supply),
        lookback_bars=4,
    )

    assert tuple(step.bar_index for step in result.steps) == (8, 10)
    assert DailyBehaviorDimension.OPPOSING_PRESSURE_RECEDING in result.dimensions
    assert DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING in result.dimensions


def test_sequence_returns_empty_read_only_audit_when_no_supported_behavior() -> None:
    opposing = _evidence(
        EvidenceCode.NO_DEMAND,
        EvidenceDirection.BEARISH,
        10,
    )

    result = evaluate_daily_behavior_sequence(
        weekly_direction=WeeklySetupDirection.BULLISH,
        daily_bar_index=10,
        evidence=(opposing,),
    )

    assert result.steps == ()
    assert result.dimensions == ()
    assert result.first_bar_for(
        DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING
    ) is None
    assert result.last_bar_for(
        DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING
    ) is None
    assert result.is_actionable is False


def test_sequence_rejects_invalid_window_arguments() -> None:
    try:
        evaluate_daily_behavior_sequence(
            weekly_direction=WeeklySetupDirection.BULLISH,
            daily_bar_index=-1,
            evidence=(),
        )
    except ValueError as exc:
        assert "daily_bar_index" in str(exc)
    else:
        raise AssertionError("negative daily_bar_index should fail")

    try:
        evaluate_daily_behavior_sequence(
            weekly_direction=WeeklySetupDirection.BULLISH,
            daily_bar_index=10,
            evidence=(),
            lookback_bars=0,
        )
    except ValueError as exc:
        assert "lookback_bars" in str(exc)
    else:
        raise AssertionError("zero lookback_bars should fail")
