from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from models import (
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    SwingSearchState,
    SwingType,
)

SCANNER_STATE_SCHEMA_VERSION = 3


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


class ScannerStateStore:
    """Durable JSON storage for one causal ScannerState per symbol/timeframe."""

    def __init__(self, root: str | Path = "state") -> None:
        self._root = Path(root)

    @staticmethod
    def _safe_name(value: str) -> str:
        name = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
        if not name:
            raise ValueError("State identity cannot produce an empty filename.")
        return name

    def path_for(self, symbol: str, timeframe: str) -> Path:
        if not symbol or not timeframe:
            raise ValueError("symbol and timeframe are required")
        return self._root / (
            f"{self._safe_name(symbol)}__{self._safe_name(timeframe)}.json"
        )

    def save(self, state: ScannerState) -> Path:
        if state.schema_version != SCANNER_STATE_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported ScannerState schema version: {state.schema_version}"
            )

        destination = self.path_for(state.symbol, state.timeframe)
        self._root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            state.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )

        fd, temp_name = tempfile.mkstemp(
            dir=self._root,
            prefix=f".{destination.stem}.",
            suffix=".tmp",
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, destination)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise
        return destination

    def load(self, symbol: str, timeframe: str) -> ScannerState:
        path = self.path_for(symbol, timeframe)
        if not path.exists():
            raise FileNotFoundError(path)

        try:
            with path.open("r", encoding="utf-8") as handle:
                state = ScannerState.from_dict(json.load(handle))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid ScannerState file: {path}") from exc

        if state.schema_version != SCANNER_STATE_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported ScannerState schema version: {state.schema_version}"
            )
        if state.symbol != symbol or state.timeframe != timeframe:
            raise ValueError("ScannerState identity does not match requested state")
        return state

    def delete(self, symbol: str, timeframe: str) -> None:
        self.path_for(symbol, timeframe).unlink(missing_ok=True)
