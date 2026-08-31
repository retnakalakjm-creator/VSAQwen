from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from models import Swing, SwingSearchState, SwingType


@dataclass(frozen=True, slots=True)
class CandidateState:
    """Serializable continuation state for the active swing candidate."""

    bar_index: int
    week_beginning: str
    type: SwingType
    price: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "bar_index": self.bar_index,
            "week_beginning": self.week_beginning,
            "type": self.type.value,
            "price": self.price,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateState":
        return cls(
            bar_index=int(data["bar_index"]),
            week_beginning=str(data["week_beginning"]),
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
    confirmed_swings: tuple[Swing, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "last_closed_bar": self.last_closed_bar,
            "search_state": self.search_state.value,
            "candidate": None if self.candidate is None else self.candidate.to_dict(),
            "confirmed_swings": [
                {
                    "type": swing.type.value,
                    "price": swing.price,
                    "bar_index": swing.bar_index,
                    "confirmation_index": swing.confirmation_index,
                    "week_beginning": swing.week_beginning,
                    "metrics_index": swing.metrics_index,
                }
                for swing in self.confirmed_swings
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScannerState":
        swings = tuple(
            Swing(
                type=SwingType(item["type"]),
                price=float(item["price"]),
                bar_index=int(item["bar_index"]),
                confirmation_index=int(item["confirmation_index"]),
                week_beginning=str(item["week_beginning"]),
                metrics_index=(
                    None
                    if item.get("metrics_index") is None
                    else int(item["metrics_index"])
                ),
            )
            for item in data.get("confirmed_swings", ())
        )
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
            confirmed_swings=swings,
        )
