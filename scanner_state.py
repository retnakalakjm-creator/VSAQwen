from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from models import (
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    SwingSearchState,
    SwingType,
)


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
class StructuralEventState:
    """Causal structural-progression evidence needed by qualification."""

    bar_key: str
    code: EvidenceCode
    category: EvidenceCategory
    direction: EvidenceDirection
    strength: float
    weight: float
    observation: str
    description: str
    quality: float

    @classmethod
    def from_evidence(cls, evidence: Evidence) -> "StructuralEventState":
        return cls(
            bar_key=str(evidence.week_beginning),
            code=evidence.code,
            category=evidence.category,
            direction=evidence.direction,
            strength=float(evidence.strength),
            weight=float(evidence.weight),
            observation=str(evidence.observation),
            description=str(evidence.description),
            quality=float(evidence.quality),
        )

    def to_evidence(self, bar_index: int) -> Evidence:
        return Evidence(
            code=self.code,
            category=self.category,
            direction=self.direction,
            strength=self.strength,
            weight=self.weight,
            observation=self.observation,
            description=self.description,
            bar_index=bar_index,
            week_beginning=self.bar_key,
            quality=self.quality,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "bar_key": self.bar_key,
            "code": self.code.value,
            "category": int(self.category),
            "direction": int(self.direction),
            "strength": self.strength,
            "weight": self.weight,
            "observation": self.observation,
            "description": self.description,
            "quality": self.quality,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StructuralEventState":
        return cls(
            bar_key=str(data["bar_key"]),
            code=EvidenceCode(data["code"]),
            category=EvidenceCategory(int(data["category"])),
            direction=EvidenceDirection(int(data["direction"])),
            strength=float(data["strength"]),
            weight=float(data["weight"]),
            observation=str(data["observation"]),
            description=str(data["description"]),
            quality=float(data.get("quality", 1.0)),
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
    structural_events: tuple[StructuralEventState, ...] = ()

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
            "structural_events": [
                event.to_dict() for event in self.structural_events
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
            structural_events=tuple(
                StructuralEventState.from_dict(item)
                for item in data.get("structural_events", ())
            ),
        )
