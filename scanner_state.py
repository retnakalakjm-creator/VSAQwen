from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from models import Swing, SwingSearchState, SwingType


@dataclass(frozen=True, slots=True)
class CandidateState:
    """Stable continuation state for the active swing candidate."""

    bar_key: str
    type: SwingType
    price: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "bar_key": self.bar_key,
            "type": self.type.value,
            "price": self.price,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateState":
        return cls(
            bar_key=str(data["bar_key"]),
            type=SwingType(data["type"]),
            price=float(data["price"]),
        )


@dataclass(frozen=True, slots=True)
class ConfirmedSwingState:
    """Stable identity for one confirmed swing."""

    pivot_bar_key: str
    confirmation_bar_key: str
    type: SwingType
    price: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "pivot_bar_key": self.pivot_bar_key,
            "confirmation_bar_key": self.confirmation_bar_key,
            "type": self.type.value,
            "price": self.price,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConfirmedSwingState":
        return cls(
            pivot_bar_key=str(data["pivot_bar_key"]),
            confirmation_bar_key=str(data["confirmation_bar_key"]),
            type=SwingType(data["type"]),
            price=float(data["price"]),
        )


@dataclass(frozen=True, slots=True)
class ScannerState:
    """Minimal causal state required to resume incremental scanning."""

    schema_version: int
    symbol: str
    timeframe: str
    last_closed_bar: str
    search_state: SwingSearchState
    candidate: CandidateState | None
    confirmed_swings: tuple[ConfirmedSwingState, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "last_closed_bar": self.last_closed_bar,
            "search_state": self.search_state.value,
            "candidate": None if self.candidate is None else self.candidate.to_dict(),
            "confirmed_swings": [
                swing.to_dict() for swing in self.confirmed_swings
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScannerState":
        candidate_data = data.get("candidate")
        return cls(
            schema_version=int(data["schema_version"]),
            symbol=str(data["symbol"]),
            timeframe=str(data["timeframe"]),
            last_closed_bar=str(data["last_closed_bar"]),
            search_state=SwingSearchState(data["search_state"]),
            candidate=(
                None
                if candidate_data is None
                else CandidateState.from_dict(candidate_data)
            ),
            confirmed_swings=tuple(
                ConfirmedSwingState.from_dict(item)
                for item in data.get("confirmed_swings", ())
            ),
        )
