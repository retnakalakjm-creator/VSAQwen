from __future__ import annotations

from scanner_state import CandidateState, ScannerState
from models import Swing, SwingSearchState, SwingType


def _state() -> ScannerState:
    return ScannerState(
        schema_version=1,
        symbol="TEST.NS",
        timeframe="1w",
        last_closed_bar="2026-08-28",
        search_state=SwingSearchState.TRACKING_LOW,
        candidate=CandidateState(
            bar_index=117,
            week_beginning="2026-08-28",
            type=SwingType.LOW,
            price=101.25,
        ),
        confirmed_swings=(
            Swing(
                type=SwingType.HIGH,
                price=110.0,
                bar_index=100,
                confirmation_index=103,
                week_beginning="2026-05-01",
            ),
            Swing(
                type=SwingType.LOW,
                price=101.5,
                bar_index=108,
                confirmation_index=111,
                week_beginning="2026-06-26",
            ),
        ),
    )


def test_scanner_state_round_trip() -> None:
    original = _state()
    restored = ScannerState.from_dict(original.to_dict())

    assert restored == original


def test_scanner_state_is_causal_not_output_state() -> None:
    state = _state()
    payload = state.to_dict()

    assert "candidate" in payload
    assert "confirmed_swings" in payload
    assert "professional_score" not in payload
    assert "evidence" not in payload
    assert "ranking" not in payload
