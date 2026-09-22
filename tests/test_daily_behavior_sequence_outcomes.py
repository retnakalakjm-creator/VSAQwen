import pandas as pd

from audit.daily_behavior_sequence_outcomes import (
    build_daily_behavior_sequence_outcomes,
    daily_behavior_sequence_evidence_signature,
    daily_behavior_sequence_signature,
    sequence_has_fresh_behavior,
    summarize_daily_behavior_sequence_outcomes,
)
from daily_behavior import DailyBehaviorDimension
from daily_behavior_sequence import (
    DailyBehaviorSequence,
    DailyBehaviorSequenceStep,
)
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection
from weekly_setup import WeeklySetupDirection


def _bars(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "close": closes,
            "high": [value + 1.0 for value in closes],
            "low": [value - 1.0 for value in closes],
        }
    )


def _sequence(
    *,
    direction: WeeklySetupDirection,
    end_bar_index: int,
    steps: tuple[DailyBehaviorSequenceStep, ...],
    lookback_bars: int = 5,
) -> DailyBehaviorSequence:
    return DailyBehaviorSequence(
        weekly_direction=direction,
        start_bar_index=max(0, end_bar_index - lookback_bars + 1),
        end_bar_index=end_bar_index,
        lookback_bars=lookback_bars,
        steps=steps,
    )


def _step(
    bar_index: int,
    *dimensions: DailyBehaviorDimension,
    evidence: tuple[Evidence, ...] = (),
) -> DailyBehaviorSequenceStep:
    return DailyBehaviorSequenceStep(
        bar_index=bar_index,
        dimensions=tuple(dimensions),
        evidence=evidence,
    )


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
        week_beginning="2026-01-01",
    )


def test_fresh_sequence_uses_next_bar_execution_not_same_bar() -> None:
    bars = _bars([100.0, 101.0, 102.0, 104.0, 108.0, 110.0])
    sequence = _sequence(
        direction=WeeklySetupDirection.BULLISH,
        end_bar_index=2,
        steps=(
            _step(1, DailyBehaviorDimension.OPPOSING_PRESSURE_RECEDING),
            _step(2, DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING),
        ),
    )

    observations = build_daily_behavior_sequence_outcomes(
        bars,
        sequence=sequence,
        horizons=(1,),
    )

    assert len(observations) == 1
    observation = observations[0]
    assert observation.signal_bar_index == 2
    assert observation.outcome is not None
    assert observation.outcome.signal_bar_index == 2
    assert observation.outcome.execution_bar_index == 3
    assert observation.outcome.entry_price == 104.0
    assert observation.outcome.exit_bar_index == 4
    assert observation.outcome.exit_price == 108.0
    assert observation.outcome.favorable_return > 0.0
    assert observation.is_actionable is False


def test_sequence_without_fresh_current_behavior_is_not_scored_retroactively() -> None:
    bars = _bars([100.0, 101.0, 102.0, 104.0, 108.0, 110.0])
    sequence = _sequence(
        direction=WeeklySetupDirection.BULLISH,
        end_bar_index=4,
        steps=(
            _step(1, DailyBehaviorDimension.OPPOSING_PRESSURE_RECEDING),
            _step(2, DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING),
        ),
    )

    assert sequence_has_fresh_behavior(sequence) is False
    assert build_daily_behavior_sequence_outcomes(
        bars,
        sequence=sequence,
        horizons=(1, 2),
    ) == ()


def test_latest_fresh_sequence_retains_unavailable_outcome() -> None:
    bars = _bars([100.0, 101.0, 102.0])
    sequence = _sequence(
        direction=WeeklySetupDirection.BULLISH,
        end_bar_index=2,
        steps=(_step(2, DailyBehaviorDimension.ABSORPTION),),
    )

    observations = build_daily_behavior_sequence_outcomes(
        bars,
        sequence=sequence,
        horizons=(1, 3),
    )

    assert len(observations) == 2
    assert all(item.outcome is None for item in observations)
    assert all(item.outcome_available is False for item in observations)
    assert all(item.complete is False for item in observations)


def test_bearish_sequence_uses_short_favorable_return() -> None:
    bars = _bars([110.0, 109.0, 108.0, 106.0, 100.0, 98.0])
    sequence = _sequence(
        direction=WeeklySetupDirection.BEARISH,
        end_bar_index=2,
        steps=(
            _step(1, DailyBehaviorDimension.OPPOSING_PRESSURE_RECEDING),
            _step(2, DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING),
        ),
    )

    observation = build_daily_behavior_sequence_outcomes(
        bars,
        sequence=sequence,
        horizons=(1,),
    )[0]

    assert observation.outcome is not None
    assert observation.outcome.raw_return < 0.0
    assert observation.outcome.favorable_return > 0.0


def test_signature_uses_relative_offsets_not_absolute_bar_indices() -> None:
    first = _sequence(
        direction=WeeklySetupDirection.BULLISH,
        end_bar_index=5,
        steps=(
            _step(3, DailyBehaviorDimension.OPPOSING_PRESSURE_RECEDING),
            _step(5, DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING),
        ),
    )
    second = _sequence(
        direction=WeeklySetupDirection.BULLISH,
        end_bar_index=20,
        steps=(
            _step(18, DailyBehaviorDimension.OPPOSING_PRESSURE_RECEDING),
            _step(20, DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING),
        ),
    )

    assert daily_behavior_sequence_signature(first) == daily_behavior_sequence_signature(
        second
    )


def test_exact_evidence_signature_preserves_distinct_rejection_narratives() -> None:
    buying_climax = _sequence(
        direction=WeeklySetupDirection.BEARISH,
        end_bar_index=5,
        steps=(
            _step(
                5,
                DailyBehaviorDimension.REJECTION_OF_OPPOSING_MOVE,
                evidence=(
                    _evidence(
                        EvidenceCode.BUYING_CLIMAX,
                        EvidenceDirection.BEARISH,
                        5,
                    ),
                ),
            ),
        ),
    )
    upthrust = _sequence(
        direction=WeeklySetupDirection.BEARISH,
        end_bar_index=20,
        steps=(
            _step(
                20,
                DailyBehaviorDimension.REJECTION_OF_OPPOSING_MOVE,
                evidence=(
                    _evidence(
                        EvidenceCode.UPTHRUST,
                        EvidenceDirection.BEARISH,
                        20,
                    ),
                ),
            ),
        ),
    )

    assert daily_behavior_sequence_signature(
        buying_climax
    ) == daily_behavior_sequence_signature(upthrust)
    assert daily_behavior_sequence_evidence_signature(
        buying_climax
    ) != daily_behavior_sequence_evidence_signature(upthrust)


def test_summary_uses_complete_outcomes_only_for_return_metrics() -> None:
    bars = _bars([100.0, 101.0, 102.0, 104.0, 108.0, 110.0])
    first = _sequence(
        direction=WeeklySetupDirection.BULLISH,
        end_bar_index=2,
        steps=(
            _step(1, DailyBehaviorDimension.OPPOSING_PRESSURE_RECEDING),
            _step(2, DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING),
        ),
    )
    second = _sequence(
        direction=WeeklySetupDirection.BULLISH,
        end_bar_index=4,
        steps=(
            _step(3, DailyBehaviorDimension.OPPOSING_PRESSURE_RECEDING),
            _step(4, DailyBehaviorDimension.ALIGNED_PRESSURE_EMERGING),
        ),
    )

    observations = (
        *build_daily_behavior_sequence_outcomes(
            bars,
            sequence=first,
            horizons=(1,),
        ),
        *build_daily_behavior_sequence_outcomes(
            bars,
            sequence=second,
            horizons=(1,),
        ),
    )
    summary = summarize_daily_behavior_sequence_outcomes(observations)[0]

    assert summary.observation_count == 2
    assert summary.outcome_available_count == 2
    assert summary.complete_outcome_count == 1
    assert summary.mean_favorable_return is not None
    assert summary.median_favorable_return == summary.mean_favorable_return
    assert summary.is_actionable is False


def test_outcome_horizons_must_be_positive() -> None:
    bars = _bars([100.0, 101.0, 102.0, 103.0])
    sequence = _sequence(
        direction=WeeklySetupDirection.BULLISH,
        end_bar_index=2,
        steps=(_step(2, DailyBehaviorDimension.ABSORPTION),),
    )

    try:
        build_daily_behavior_sequence_outcomes(
            bars,
            sequence=sequence,
            horizons=(0,),
        )
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("zero horizon should fail")
