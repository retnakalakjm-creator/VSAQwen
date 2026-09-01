from __future__ import annotations

from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection, SwingSearchState, SwingType
from scanner_state import CandidateState, ConfirmedSwingState, ScannerState, StructuralEventState


def test_scanner_state_event_round_trip() -> None:
    event = StructuralEventState(
        bar_key="2026-08-21",
        code=EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
        category=EvidenceCategory.TREND,
        direction=EvidenceDirection.BEARISH,
        strength=0.8,
        weight=1.0,
        observation="weakening",
        description="structural quality weakened",
        quality=1.0,
    )
    state = ScannerState(
        schema_version=3,
        symbol="TCS.NS",
        timeframe="weekly",
        last_closed_bar="2026-08-28",
        search_state=SwingSearchState.TRACKING_HIGH,
        candidate=CandidateState("2026-08-28", SwingType.HIGH, 100.0),
        confirmed_swings=(
            ConfirmedSwingState("2026-08-07", "2026-08-14", SwingType.LOW, 95.0),
        ),
        structural_events=(event,),
    )
    restored = ScannerState.from_dict(state.to_dict())
    assert restored == state


def test_structural_event_rehydrates_evidence() -> None:
    event = StructuralEventState(
        bar_key="2026-08-21",
        code=EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
        category=EvidenceCategory.TREND,
        direction=EvidenceDirection.BULLISH,
        strength=0.5,
        weight=1.0,
        observation="improving",
        description="structural quality improved",
        quality=1.0,
    )
    evidence = event.to_evidence(42)
    assert isinstance(evidence, Evidence)
    assert evidence.bar_index == 42
    assert evidence.week_beginning == event.bar_key
    assert evidence.code == event.code
    assert evidence.direction == event.direction
