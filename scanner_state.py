from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

from models import (
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    SwingSearchState,
    SwingType,
)

SCANNER_STATE_SCHEMA_VERSION = 4
SCANNER_STATE_ENGINE_FINGERPRINT = "scanner-state-v4.incremental-production-v1"
SCANNER_STATE_DATA_FINGERPRINT_COLUMNS = (
    "week_beginning",
    "open",
    "high",
    "low",
    "close",
    "volume",
)


class ScannerStateFingerprintMismatch(ValueError):
    """Saved scanner state does not match the current runtime or data prefix."""


def _stable_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(_stable_value(key)): _stable_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_stable_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_stable_value(item) for item in value), key=str)
    return repr(value)


def _metric_value(value: Any) -> Any:
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return _stable_value(value)


def _sha256_json(payload: Any) -> str:
    encoded = json.dumps(
        _stable_value(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def scanner_state_config_fingerprint() -> str:
    """Stable fingerprint of public scanner/trend/evidence configuration."""

    import config

    payload = {
        name: _stable_value(getattr(config, name))
        for name in dir(config)
        if name.isupper()
    }
    return _sha256_json(payload)


def scanner_state_data_fingerprint(
    metrics: pd.DataFrame,
    last_closed_bar: str,
) -> str:
    """Stable fingerprint of source OHLCV data up to the state checkpoint."""

    if "week_beginning" not in metrics.columns:
        raise ValueError("metrics must include week_beginning for state fingerprinting")

    weeks = [str(value) for value in metrics["week_beginning"]]
    matches = [index for index, week in enumerate(weeks) if week == str(last_closed_bar)]
    if not matches:
        raise ValueError(
            f"ScannerState checkpoint bar is not present in current metrics: {last_closed_bar}"
        )
    if len(matches) > 1:
        raise ValueError(f"Metrics contain duplicate bar identity: {last_closed_bar!r}.")

    checkpoint_index = matches[0]
    columns = [
        column
        for column in SCANNER_STATE_DATA_FINGERPRINT_COLUMNS
        if column in metrics.columns
    ]
    if not columns:
        raise ValueError("metrics do not contain state fingerprint columns")

    prefix = metrics.iloc[: checkpoint_index + 1][columns]
    rows = [
        [_metric_value(value) for value in row]
        for row in prefix.itertuples(index=False, name=None)
    ]
    return _sha256_json(
        {
            "checkpoint": str(last_closed_bar),
            "columns": columns,
            "rows": rows,
        }
    )


def scanner_state_fingerprints(
    metrics: pd.DataFrame,
    last_closed_bar: str,
) -> dict[str, str]:
    return {
        "engine_fingerprint": SCANNER_STATE_ENGINE_FINGERPRINT,
        "config_fingerprint": scanner_state_config_fingerprint(),
        "data_fingerprint": scanner_state_data_fingerprint(metrics, last_closed_bar),
    }


def stamp_scanner_state(
    state: "ScannerState",
    metrics: pd.DataFrame,
) -> "ScannerState":
    """Attach runtime/config/data fingerprints before persisting scanner state."""

    return replace(state, **scanner_state_fingerprints(metrics, state.last_closed_bar))


def validate_scanner_state_fingerprints(
    state: "ScannerState",
    metrics: pd.DataFrame,
) -> None:
    """Reject stale state instead of silently resuming an incompatible snapshot."""

    expected = scanner_state_fingerprints(metrics, state.last_closed_bar)
    mismatches = [
        name.removesuffix("_fingerprint")
        for name, expected_value in expected.items()
        if getattr(state, name) != expected_value
    ]
    if mismatches:
        raise ScannerStateFingerprintMismatch(
            "ScannerState fingerprint mismatch: " + ", ".join(sorted(mismatches))
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
    engine_fingerprint: str = SCANNER_STATE_ENGINE_FINGERPRINT
    config_fingerprint: str | None = None
    data_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "last_closed_bar": self.last_closed_bar,
            "engine_fingerprint": self.engine_fingerprint,
            "config_fingerprint": self.config_fingerprint,
            "data_fingerprint": self.data_fingerprint,
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
            engine_fingerprint=str(
                data.get("engine_fingerprint", SCANNER_STATE_ENGINE_FINGERPRINT)
            ),
            config_fingerprint=(
                None
                if data.get("config_fingerprint") is None
                else str(data["config_fingerprint"])
            ),
            data_fingerprint=(
                None
                if data.get("data_fingerprint") is None
                else str(data["data_fingerprint"])
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


__all__ = [
    "CandidateState",
    "ConfirmedSwingState",
    "SCANNER_STATE_DATA_FINGERPRINT_COLUMNS",
    "SCANNER_STATE_ENGINE_FINGERPRINT",
    "SCANNER_STATE_SCHEMA_VERSION",
    "ScannerState",
    "ScannerStateFingerprintMismatch",
    "ScannerStateStore",
    "StructuralEventState",
    "scanner_state_config_fingerprint",
    "scanner_state_data_fingerprint",
    "scanner_state_fingerprints",
    "stamp_scanner_state",
    "validate_scanner_state_fingerprints",
]
