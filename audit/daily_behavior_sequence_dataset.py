"""Frozen interchange contract for prepared daily behavior sequence datasets.

This module is analysis-only. It serializes the exact K3 prepared-input boundary
without deriving evidence or weekly direction from prices.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from audit.daily_behavior_sequence_runner import (
    DailyBehaviorSequenceDirectionAssignment,
    DailyBehaviorSequenceInputFingerprint,
    DailyBehaviorSequenceStudyInput,
    fingerprint_daily_behavior_sequence_input,
)
from engine.columns import COL_CLOSE, COL_HIGH, COL_LOW
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection
from weekly_setup import WeeklySetupDirection


DAILY_SEQUENCE_DATASET_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class DailyBehaviorSequenceDatasetSource:
    kind: str
    reference: str
    prepared_at_utc: str
    notes: str = ""


@dataclass(frozen=True, slots=True)
class FrozenDailyBehaviorSequenceDataset:
    dataset_id: str
    source: DailyBehaviorSequenceDatasetSource
    inputs: tuple[DailyBehaviorSequenceStudyInput, ...]
    fingerprints: tuple[DailyBehaviorSequenceInputFingerprint, ...]
    schema_version: int = DAILY_SEQUENCE_DATASET_SCHEMA_VERSION
    price_timeframe: str = "1D"
    evidence_timeframe: str = "1D"

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(item.symbol.strip().upper() for item in self.inputs)

    @property
    def is_actionable(self) -> bool:
        return False


def _clean_text(value: str, field: str) -> str:
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{field} cannot be blank")
    return cleaned


def _validate_timeframes(price_timeframe: str, evidence_timeframe: str) -> None:
    if str(price_timeframe).strip().upper() != "1D":
        raise ValueError("price_timeframe must be 1D")
    if str(evidence_timeframe).strip().upper() != "1D":
        raise ValueError("evidence_timeframe must be 1D")


def _evidence_to_dict(item: Evidence) -> dict[str, object]:
    return {
        "code": item.code.value,
        "category": int(item.category),
        "direction": int(item.direction),
        "strength": item.strength,
        "weight": item.weight,
        "observation": item.observation,
        "description": item.description,
        "bar_index": item.bar_index,
        "week_beginning": item.week_beginning,
        "test_index": item.test_index,
        "recovery_index": item.recovery_index,
        "quality": item.quality,
    }


def _evidence_from_dict(payload: dict[str, Any]) -> Evidence:
    return Evidence(
        code=EvidenceCode(str(payload["code"])),
        category=EvidenceCategory(int(payload["category"])),
        direction=EvidenceDirection(int(payload["direction"])),
        strength=float(payload["strength"]),
        weight=float(payload["weight"]),
        observation=str(payload["observation"]),
        description=str(payload["description"]),
        bar_index=int(payload["bar_index"]),
        week_beginning=str(payload["week_beginning"]),
        test_index=(
            None if payload.get("test_index") is None else int(payload["test_index"])
        ),
        recovery_index=(
            None
            if payload.get("recovery_index") is None
            else int(payload["recovery_index"])
        ),
        quality=float(payload.get("quality", 1.0)),
    )


def _input_to_dict(
    study_input: DailyBehaviorSequenceStudyInput,
    fingerprint: DailyBehaviorSequenceInputFingerprint,
) -> dict[str, object]:
    return {
        "symbol": study_input.symbol.strip().upper(),
        "bars": [
            {
                "index": str(index),
                COL_CLOSE: float(row[COL_CLOSE]),
                COL_HIGH: float(row[COL_HIGH]),
                COL_LOW: float(row[COL_LOW]),
            }
            for index, row in study_input.bars.iterrows()
        ],
        "weekly_directions": [
            {
                "bar_index": item.bar_index,
                "direction": item.direction.value,
            }
            for item in study_input.weekly_directions
        ],
        "evidence": [_evidence_to_dict(item) for item in study_input.evidence],
        "fingerprint": {
            "symbol": fingerprint.symbol,
            "bar_count": fingerprint.bar_count,
            "direction_assignment_count": fingerprint.direction_assignment_count,
            "evidence_count": fingerprint.evidence_count,
            "first_index": fingerprint.first_index,
            "last_index": fingerprint.last_index,
            "sha256": fingerprint.sha256,
        },
    }


def _input_from_dict(payload: dict[str, Any]) -> DailyBehaviorSequenceStudyInput:
    bars_payload = list(payload.get("bars", ()))
    if not bars_payload:
        raise ValueError("prepared symbol bars cannot be empty")

    bars = pd.DataFrame(
        [
            {
                COL_CLOSE: float(item[COL_CLOSE]),
                COL_HIGH: float(item[COL_HIGH]),
                COL_LOW: float(item[COL_LOW]),
            }
            for item in bars_payload
        ],
        index=pd.Index([str(item["index"]) for item in bars_payload], name="date"),
    )

    directions = tuple(
        DailyBehaviorSequenceDirectionAssignment(
            bar_index=int(item["bar_index"]),
            direction=WeeklySetupDirection(str(item["direction"])),
        )
        for item in payload.get("weekly_directions", ())
    )
    evidence = tuple(
        _evidence_from_dict(dict(item))
        for item in payload.get("evidence", ())
    )

    return DailyBehaviorSequenceStudyInput(
        symbol=_clean_text(str(payload["symbol"]), "symbol").upper(),
        bars=bars,
        weekly_directions=directions,
        evidence=evidence,
    )


def freeze_daily_behavior_sequence_dataset(
    *,
    dataset_id: str,
    source: DailyBehaviorSequenceDatasetSource,
    inputs: tuple[DailyBehaviorSequenceStudyInput, ...],
) -> FrozenDailyBehaviorSequenceDataset:
    """Create a validated immutable dataset wrapper around prepared K3 inputs."""

    clean_dataset_id = _clean_text(dataset_id, "dataset_id")
    _clean_text(source.kind, "source.kind")
    _clean_text(source.reference, "source.reference")
    _clean_text(source.prepared_at_utc, "source.prepared_at_utc")

    if not inputs:
        raise ValueError("inputs must contain at least one symbol")

    fingerprints = tuple(
        fingerprint_daily_behavior_sequence_input(item)
        for item in inputs
    )
    symbols = tuple(item.symbol for item in fingerprints)
    if len(set(symbols)) != len(symbols):
        raise ValueError("inputs require unique symbols")

    return FrozenDailyBehaviorSequenceDataset(
        dataset_id=clean_dataset_id,
        source=source,
        inputs=inputs,
        fingerprints=fingerprints,
    )


def write_daily_behavior_sequence_dataset(
    dataset: FrozenDailyBehaviorSequenceDataset,
    path: str | Path,
) -> Path:
    """Write a canonical JSON dataset with embedded K3 fingerprints."""

    if dataset.schema_version != DAILY_SEQUENCE_DATASET_SCHEMA_VERSION:
        raise ValueError(
            "unsupported daily sequence dataset schema_version: "
            f"{dataset.schema_version}"
        )
    _validate_timeframes(dataset.price_timeframe, dataset.evidence_timeframe)
    if len(dataset.inputs) != len(dataset.fingerprints):
        raise ValueError("dataset inputs/fingerprints length mismatch")

    current_fingerprints = tuple(
        fingerprint_daily_behavior_sequence_input(item)
        for item in dataset.inputs
    )
    if current_fingerprints != dataset.fingerprints:
        raise ValueError("dataset inputs no longer match retained fingerprints")

    payload = {
        "schema_version": dataset.schema_version,
        "dataset_id": dataset.dataset_id,
        "price_timeframe": dataset.price_timeframe,
        "evidence_timeframe": dataset.evidence_timeframe,
        "source": {
            "kind": dataset.source.kind,
            "reference": dataset.source.reference,
            "prepared_at_utc": dataset.source.prepared_at_utc,
            "notes": dataset.source.notes,
        },
        "is_actionable": False,
        "symbols": [
            _input_to_dict(study_input, fingerprint)
            for study_input, fingerprint in zip(
                dataset.inputs,
                dataset.fingerprints,
                strict=True,
            )
        ],
    }

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return destination


def load_daily_behavior_sequence_dataset(
    path: str | Path,
) -> FrozenDailyBehaviorSequenceDataset:
    """Load and fingerprint-verify one frozen prepared dataset."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    schema_version = int(payload.get("schema_version", 0))
    if schema_version != DAILY_SEQUENCE_DATASET_SCHEMA_VERSION:
        raise ValueError(
            "unsupported daily sequence dataset schema_version: "
            f"{schema_version}"
        )

    _validate_timeframes(
        str(payload.get("price_timeframe", "")),
        str(payload.get("evidence_timeframe", "")),
    )

    source_payload = dict(payload.get("source", {}))
    source = DailyBehaviorSequenceDatasetSource(
        kind=_clean_text(str(source_payload.get("kind", "")), "source.kind"),
        reference=_clean_text(
            str(source_payload.get("reference", "")),
            "source.reference",
        ),
        prepared_at_utc=_clean_text(
            str(source_payload.get("prepared_at_utc", "")),
            "source.prepared_at_utc",
        ),
        notes=str(source_payload.get("notes", "")),
    )

    symbol_payloads = tuple(dict(item) for item in payload.get("symbols", ()))
    if not symbol_payloads:
        raise ValueError("dataset symbols cannot be empty")

    inputs: list[DailyBehaviorSequenceStudyInput] = []
    fingerprints: list[DailyBehaviorSequenceInputFingerprint] = []

    for item_payload in symbol_payloads:
        study_input = _input_from_dict(item_payload)
        actual = fingerprint_daily_behavior_sequence_input(study_input)

        stored_payload = dict(item_payload.get("fingerprint", {}))
        stored_sha256 = str(stored_payload.get("sha256", ""))
        if actual.sha256 != stored_sha256:
            raise ValueError(
                f"{actual.symbol} dataset fingerprint mismatch: "
                f"stored {stored_sha256!r}, observed {actual.sha256!r}"
            )

        stored = DailyBehaviorSequenceInputFingerprint(
            symbol=str(stored_payload["symbol"]),
            bar_count=int(stored_payload["bar_count"]),
            direction_assignment_count=int(
                stored_payload["direction_assignment_count"]
            ),
            evidence_count=int(stored_payload["evidence_count"]),
            first_index=(
                None
                if stored_payload.get("first_index") is None
                else str(stored_payload["first_index"])
            ),
            last_index=(
                None
                if stored_payload.get("last_index") is None
                else str(stored_payload["last_index"])
            ),
            sha256=stored_sha256,
        )
        if stored != actual:
            raise ValueError(
                f"{actual.symbol} stored fingerprint metadata does not match input"
            )

        inputs.append(study_input)
        fingerprints.append(actual)

    if len({item.symbol for item in fingerprints}) != len(fingerprints):
        raise ValueError("dataset requires unique symbols")

    return FrozenDailyBehaviorSequenceDataset(
        dataset_id=_clean_text(str(payload.get("dataset_id", "")), "dataset_id"),
        source=source,
        inputs=tuple(inputs),
        fingerprints=tuple(fingerprints),
        schema_version=schema_version,
        price_timeframe="1D",
        evidence_timeframe="1D",
    )


__all__ = [
    "DAILY_SEQUENCE_DATASET_SCHEMA_VERSION",
    "DailyBehaviorSequenceDatasetSource",
    "FrozenDailyBehaviorSequenceDataset",
    "freeze_daily_behavior_sequence_dataset",
    "load_daily_behavior_sequence_dataset",
    "write_daily_behavior_sequence_dataset",
]
