from __future__ import annotations

from dataclasses import dataclass

from background.qualification import (
    PatternQualification,
    PatternQualificationEngine,
    PatternQualificationState,
)
from models import (
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
)


@dataclass(frozen=True)
class _Result:
    evidence: tuple[Evidence, ...]


def _event(bar_index: int, *, bullish: bool) -> Evidence:
    code = (
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING
        if bullish
        else EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING
    )
    direction = (
        EvidenceDirection.BULLISH
        if bullish
        else EvidenceDirection.BEARISH
    )
    return Evidence(
        code=code,
        category=EvidenceCategory.TREND,
        direction=direction,
        strength=0.8,
        weight=1.0,
        observation="structural progression",
        description="test event",
        bar_index=bar_index,
        week_beginning=f"W{bar_index:03d}",
    )


def _signature(result) -> tuple[object, ...]:
    return (
        result.qualification,
        result.is_actionable_evidence,
        result.evidence_codes,
        result.evidence_bar_indices,
    )


def test_first_class_state_matches_legacy_history_evaluation() -> None:
    engine = PatternQualificationEngine()
    state = PatternQualificationState()
    history: list[_Result] = []

    events = (
        _event(1, bullish=True),
        _event(5, bullish=True),
        _event(9, bullish=True),
        _event(10, bullish=False),
        _event(14, bullish=False),
        _event(18, bullish=False),
        _event(19, bullish=True),
        _event(23, bullish=True),
        _event(27, bullish=True),
    )

    for event in events:
        history.append(_Result(evidence=(event,)))
        state = engine.advance(state, (event,))

        legacy = engine.evaluate(history)  # type: ignore[arg-type]
        incremental = engine.evaluate_state(state)

        assert _signature(incremental) == _signature(legacy)


def test_opposing_event_discards_invalidated_campaign_state() -> None:
    engine = PatternQualificationEngine()
    bullish = (
        _event(1, bullish=True),
        _event(5, bullish=True),
        _event(9, bullish=True),
    )
    state = engine.state_from_events(bullish)

    assert engine.evaluate_state(state).qualification is PatternQualification.PERSISTENT_BULLISH

    bearish = _event(10, bullish=False)
    state = engine.advance(state, (bearish,))

    assert state.active_events == (bearish,)
    assert engine.evaluate_state(state).qualification is PatternQualification.UNQUALIFIED


def test_state_preserves_spacing_semantics_and_ignores_duplicates() -> None:
    engine = PatternQualificationEngine()
    first = _event(1, bullish=True)
    too_close = _event(3, bullish=True)
    second = _event(5, bullish=True)
    third = _event(9, bullish=True)

    state = engine.state_from_events((first, too_close, second, third, third))
    result = engine.evaluate_state(state)

    assert result.qualification is PatternQualification.PERSISTENT_BULLISH
    # Preserve the current legacy qualification algorithm exactly. It walks
    # backward from the newest event and stops once three spaced events are
    # found, so the current selected sequence is 3, 5, 9 rather than 1, 5, 9.
    assert result.evidence_bar_indices == (3, 5, 9)
    assert tuple(item.bar_index for item in state.active_events) == (1, 3, 5, 9)


def test_qualifying_events_are_available_without_evidence_result_history() -> None:
    engine = PatternQualificationEngine()
    state = engine.state_from_events(
        (
            _event(2, bullish=False),
            _event(6, bullish=False),
            _event(10, bullish=False),
        )
    )

    qualifying = engine.qualifying_events(state)

    assert tuple(item.bar_index for item in qualifying) == (2, 6, 10)
    assert all(
        item.code is EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING
        for item in qualifying
    )
