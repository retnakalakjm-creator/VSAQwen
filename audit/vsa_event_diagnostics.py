"""VSA event outcome diagnostics for Milestone 3 reviews.

This module is analysis-only. It summarizes candidate outcome datasets by the
VSA event contracts documented in :mod:`audit.vsa_events` before any production
scoring or detector changes are proposed.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from audit.calibration import completed_scored_frame, summarize_outcomes
from audit.stability import (
    DEFAULT_STABILITY_MIN_SAMPLES,
    DEFAULT_STABILITY_Z_SCORE,
    summarize_return_stability,
)
from audit.vsa_events import contracts_by_code, vsa_event_contract_frame


DEFAULT_VSA_EVENT_EVIDENCE_COLUMNS = (
    "target_bar_evidence_codes",
    "qualifying_evidence_codes",
    "scoring_evidence_codes",
    "campaign_evidence_codes",
)
DEFAULT_VSA_EVENT_OUTPUT_COLUMN = "vsa_event_code"
DEFAULT_VSA_EVENT_SOURCE_COLUMN = "vsa_event_source_column"
CONTRACT_JOIN_COLUMNS = (
    "evidence_code",
    "module",
    "detector",
    "direction",
    "recognition_timing",
    "emitted_bar",
    "uses_future_bars",
)


@dataclass(frozen=True, slots=True)
class VSAEventDiagnosticPaths:
    """Paths written by :func:`write_vsa_event_diagnostic_bundle`."""

    output_dir: Path
    event_summary: Path
    event_stability: Path
    event_contracts: Path
    metadata: Path

    def as_dict(self) -> dict[str, str]:
        """Return string paths for JSON/log output."""
        return {key: str(value) for key, value in asdict(self).items()}


def explode_vsa_event_rows(
    frame: pd.DataFrame,
    *,
    evidence_columns: str | Sequence[str] = DEFAULT_VSA_EVENT_EVIDENCE_COLUMNS,
    output_column: str = DEFAULT_VSA_EVENT_OUTPUT_COLUMN,
    source_column: str = DEFAULT_VSA_EVENT_SOURCE_COLUMN,
    drop_non_vsa: bool = True,
) -> pd.DataFrame:
    """Return one candidate-outcome row per detected VSA event code.

    Codes are read from the configured pipe-delimited evidence columns and
    normalized to uppercase names matching :mod:`audit.vsa_events`. If the same
    event appears in multiple evidence columns for the same source row, it is
    counted once to avoid overstating a single candidate/horizon observation.
    """
    columns = _available_evidence_columns(frame, evidence_columns)
    vsa_codes = set(contracts_by_code())
    records: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()

    for row_number, row in enumerate(frame.to_dict(orient="records")):
        for evidence_column in columns:
            for raw_code in _split_codes(row.get(evidence_column)):
                code = _canonical_code(raw_code)
                if drop_non_vsa and code not in vsa_codes:
                    continue
                key = (row_number, code)
                if key in seen:
                    continue
                seen.add(key)
                record = dict(row)
                record[output_column] = code
                record[source_column] = evidence_column
                records.append(record)

    output_columns = [*frame.columns, output_column, source_column]
    if not records:
        return pd.DataFrame(columns=output_columns)
    return pd.DataFrame(records, columns=output_columns).reset_index(drop=True)


def summarize_vsa_event_outcomes(
    frame: pd.DataFrame,
    *,
    evidence_columns: str | Sequence[str] = DEFAULT_VSA_EVENT_EVIDENCE_COLUMNS,
    extra_group_by: Iterable[str] = ("horizon_bars", "side"),
    min_samples: int = 1,
    require_complete: bool = True,
) -> pd.DataFrame:
    """Summarize completed outcomes by VSA event, horizon, and side."""
    _validate_positive_int("min_samples", min_samples)
    scored = completed_scored_frame(frame, require_complete=require_complete)
    exploded = explode_vsa_event_rows(scored, evidence_columns=evidence_columns)
    group_by = [DEFAULT_VSA_EVENT_OUTPUT_COLUMN, *tuple(extra_group_by)]
    summary = summarize_outcomes(exploded, group_by=group_by, min_samples=min_samples)
    return _attach_contract_metadata(summary)


def summarize_vsa_event_stability(
    frame: pd.DataFrame,
    *,
    evidence_columns: str | Sequence[str] = DEFAULT_VSA_EVENT_EVIDENCE_COLUMNS,
    extra_group_by: Iterable[str] = ("horizon_bars", "side"),
    min_samples: int = DEFAULT_STABILITY_MIN_SAMPLES,
    require_complete: bool = True,
    z_score: float = DEFAULT_STABILITY_Z_SCORE,
) -> pd.DataFrame:
    """Summarize confidence-aware stability by VSA event, horizon, and side."""
    _validate_positive_int("min_samples", min_samples)
    _validate_positive_number("z_score", z_score)
    exploded = explode_vsa_event_rows(frame, evidence_columns=evidence_columns)
    group_by = [DEFAULT_VSA_EVENT_OUTPUT_COLUMN, *tuple(extra_group_by)]
    summary = summarize_return_stability(
        exploded,
        group_by=group_by,
        min_samples=min_samples,
        require_complete=require_complete,
        z_score=z_score,
    )
    return _attach_contract_metadata(summary)


def build_vsa_event_diagnostic_tables(
    frame: pd.DataFrame,
    *,
    evidence_columns: str | Sequence[str] = DEFAULT_VSA_EVENT_EVIDENCE_COLUMNS,
    min_samples: int = 1,
    stability_min_samples: int = DEFAULT_STABILITY_MIN_SAMPLES,
    require_complete: bool = True,
    stability_z_score: float = DEFAULT_STABILITY_Z_SCORE,
) -> dict[str, pd.DataFrame]:
    """Build CSV-ready VSA event diagnostic tables."""
    _validate_positive_int("min_samples", min_samples)
    _validate_positive_int("stability_min_samples", stability_min_samples)
    _validate_positive_number("stability_z_score", stability_z_score)
    return {
        "vsa_event_summary": summarize_vsa_event_outcomes(
            frame,
            evidence_columns=evidence_columns,
            min_samples=min_samples,
            require_complete=require_complete,
        ),
        "vsa_event_stability": summarize_vsa_event_stability(
            frame,
            evidence_columns=evidence_columns,
            min_samples=stability_min_samples,
            require_complete=require_complete,
            z_score=stability_z_score,
        ),
        "vsa_event_contracts": _csv_ready_contract_frame(),
    }


def write_vsa_event_diagnostic_bundle(
    frame: pd.DataFrame,
    output_dir: str | Path,
    *,
    evidence_columns: str | Sequence[str] = DEFAULT_VSA_EVENT_EVIDENCE_COLUMNS,
    min_samples: int = 1,
    stability_min_samples: int = DEFAULT_STABILITY_MIN_SAMPLES,
    require_complete: bool = True,
    stability_z_score: float = DEFAULT_STABILITY_Z_SCORE,
) -> VSAEventDiagnosticPaths:
    """Write VSA event diagnostics as a small CSV bundle."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    tables = build_vsa_event_diagnostic_tables(
        frame,
        evidence_columns=evidence_columns,
        min_samples=min_samples,
        stability_min_samples=stability_min_samples,
        require_complete=require_complete,
        stability_z_score=stability_z_score,
    )
    paths = VSAEventDiagnosticPaths(
        output_dir=destination,
        event_summary=destination / "vsa_event_summary.csv",
        event_stability=destination / "vsa_event_stability.csv",
        event_contracts=destination / "vsa_event_contracts.csv",
        metadata=destination / "vsa_event_metadata.csv",
    )
    tables["vsa_event_summary"].to_csv(paths.event_summary, index=False)
    tables["vsa_event_stability"].to_csv(paths.event_stability, index=False)
    tables["vsa_event_contracts"].to_csv(paths.event_contracts, index=False)
    _metadata_frame(
        frame,
        tables=tables,
        evidence_columns=_available_evidence_columns(frame, evidence_columns),
        min_samples=min_samples,
        stability_min_samples=stability_min_samples,
        require_complete=require_complete,
        stability_z_score=stability_z_score,
    ).to_csv(paths.metadata, index=False)
    return paths


def _attach_contract_metadata(summary: pd.DataFrame) -> pd.DataFrame:
    result = summary.copy()
    if DEFAULT_VSA_EVENT_OUTPUT_COLUMN not in result.columns:
        result.insert(
            0,
            DEFAULT_VSA_EVENT_OUTPUT_COLUMN,
            result.get("group_key", pd.Series(dtype="object")).map(_group_event_code),
        )

    contracts = vsa_event_contract_frame()
    join_columns = [column for column in CONTRACT_JOIN_COLUMNS if column in contracts.columns]
    metadata = contracts[join_columns].rename(
        columns={"evidence_code": DEFAULT_VSA_EVENT_OUTPUT_COLUMN}
    )
    return result.merge(metadata, how="left", on=DEFAULT_VSA_EVENT_OUTPUT_COLUMN)


def _csv_ready_contract_frame() -> pd.DataFrame:
    frame = vsa_event_contract_frame().copy()
    tuple_columns = (
        "mandatory_requirements",
        "diagnostic_confirmations",
        "source_documents",
        "known_review_notes",
    )
    for column in tuple_columns:
        if column in frame.columns:
            frame[column] = frame[column].map(_pipe_join)
    return frame


def _metadata_frame(
    frame: pd.DataFrame,
    *,
    tables: dict[str, pd.DataFrame],
    evidence_columns: Sequence[str],
    min_samples: int,
    stability_min_samples: int,
    require_complete: bool,
    stability_z_score: float,
) -> pd.DataFrame:
    rows: list[tuple[str, object]] = [
        ("source_rows", len(frame)),
        ("evidence_columns", "|".join(evidence_columns)),
        ("min_samples", min_samples),
        ("stability_min_samples", stability_min_samples),
        ("require_complete", require_complete),
        ("stability_z_score", stability_z_score),
    ]
    rows.extend((f"{name}_rows", len(table)) for name, table in tables.items())
    return pd.DataFrame(rows, columns=["metric", "value"])


def _available_evidence_columns(
    frame: pd.DataFrame,
    evidence_columns: str | Sequence[str],
) -> tuple[str, ...]:
    columns = _normalize_evidence_columns(evidence_columns)
    available = tuple(column for column in columns if column in frame.columns)
    if not available:
        raise ValueError(f"Missing VSA evidence code columns: {columns}")
    return available


def _normalize_evidence_columns(evidence_columns: str | Sequence[str]) -> tuple[str, ...]:
    if isinstance(evidence_columns, str):
        columns = (evidence_columns,)
    else:
        columns = tuple(evidence_columns)
    normalized = tuple(str(column).strip() for column in columns if str(column).strip())
    if not normalized:
        raise ValueError("evidence_columns must contain at least one column")
    return normalized


def _split_codes(value: Any) -> list[str]:
    if value is None:
        return []
    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        return [part.strip() for part in value.split("|") if part.strip()]
    return [str(part).strip() for part in value if str(part).strip()]


def _canonical_code(value: Any) -> str:
    return str(value).strip().upper()


def _group_event_code(group_key: Any) -> str:
    return str(group_key).split("|", maxsplit=1)[0]


def _pipe_join(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (tuple, list)):
        return "|".join(str(part) for part in value)
    return str(value)


def _validate_positive_int(name: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")


def _validate_positive_number(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")


__all__ = [
    "DEFAULT_VSA_EVENT_EVIDENCE_COLUMNS",
    "DEFAULT_VSA_EVENT_OUTPUT_COLUMN",
    "DEFAULT_VSA_EVENT_SOURCE_COLUMN",
    "VSAEventDiagnosticPaths",
    "build_vsa_event_diagnostic_tables",
    "explode_vsa_event_rows",
    "summarize_vsa_event_outcomes",
    "summarize_vsa_event_stability",
    "write_vsa_event_diagnostic_bundle",
]
