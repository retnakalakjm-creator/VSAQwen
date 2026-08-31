from __future__ import annotations

from scanner_state import CandidateState, ConfirmedSwingState, ScannerState
from models import SwingSearchState, SwingType


def _state() -> ScannerState:
    return ScannerState(
        schema_version=2,
        symbol="TEST.NS",
        timeframe="1w",
        last_closed_bar="2026-08-28",
        search_state=SwingSearchState.TRACKING_LOW,
        candidate=CandidateState(
            bar_key="2026-08-28",
            type=SwingType.LOW,
            price=101.25,
        ),
        confirmed_swings=(
            ConfirmedSwingState(
                pivot_bar_key="2026-05-01",
                confirmation_bar_key="2026-05-22",
                type=SwingType.HIGH,
                price=110.0,
            ),
            ConfirmedSwingState(
                pivot_bar_key="2026-06-26",
                confirmation_bar_key="2026-07-17",
                type=SwingType.LOW,
                price=101.5,
            ),
        ),
    )


def test_scanner_state_round_trip() -> None:
    original = _state()
    restored = ScannerState.from_dict(original.to_dict())
    assert restored == original


def test_scanner_state_uses_stable_bar_identities() -> None:
    payload = _state().to_dict()
    assert payload["candidate"]["bar_key"] == "2026-08-28"
    assert "bar_index" not in payload["candidate"]
    assert "bar_index" not in payload["confirmed_swings"][0]
    assert "confirmation_bar_key" in payload["confirmed_swings"][0]


def test_scanner_state_is_causal_not_output_state() -> None:
    payload = _state().to_dict()
    assert "candidate" in payload
    assert "confirmed_swings" in payload
    assert "professional_score" not in payload
    assert "evidence" not in payload
    assert "ranking" not in payload
