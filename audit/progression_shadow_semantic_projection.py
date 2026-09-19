"""Shadow semantic projection for structural progression evidence.

K24 is deliberately descriptive. It projects already-emitted progression events
and their validated same-bar trend alignment into a read-only semantic role.
It does not modify production evidence, qualification, scoring, ranking,
WeeklySetup materialization, actionability, alerts, or orders.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from audit.progression_directionality_semantics import (
    ProgressionDirectionalityRow,
)


PROGRESSION_SHADOW_SEMANTIC_AUDIT_ID = (
    "progression-shadow-semantic-projection-v1"
)

ROLE_TRANSITION_WARNING = "TRANSITION_WARNING"
ROLE_ALIGNED_OBSERVATION = "ALIGNED_PROGRESSION_OBSERVATION"
ROLE_NEUTRAL_OBSERVATION = "NEUTRAL_PROGRESSION_OBSERVATION"
ROLE_UNKNOWN_CONTEXT = "UNKNOWN_TREND_CONTEXT_OBSERVATION"

_SUPPORTED_ALIGNMENTS = {
    "opposed",
    "aligned",
    "neutral",
    "unknown",
}


@dataclass(frozen=True, slots=True)
class ProgressionShadowSemanticRow:
    symbol: str
    event_bar_index: int
    event_week: str
    event_code: str
    event_direction: str
    trend_direction: str
    trend_alignment: str
    semantic_role: str
    projected_transition_direction: str | None
    reversal_confirmed: bool
    persistent_direction_claim: bool
    affects_qualification: bool
    affects_scoring: bool
    is_actionable: bool


@dataclass(frozen=True, slots=True)
class ProgressionShadowSemanticSymbolSummary:
    symbol: str
    event_count: int
    transition_warning_count: int
    aligned_observation_count: int
    neutral_observation_count: int
    unknown_context_count: int
    bullish_transition_warning_count: int
    bearish_transition_warning_count: int


@dataclass(frozen=True, slots=True)
class ProgressionShadowSemanticAudit:
    audit_id: str
    basket_name: str
    requested_symbol_count: int
    event_count: int
    semantic_role_counts: dict[str, int]
    transition_warning_direction_counts: dict[str, int]
    rows: tuple[ProgressionShadowSemanticRow, ...]
    symbol_summaries: tuple[ProgressionShadowSemanticSymbolSummary, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ProgressionShadowSemanticAuditPaths:
    summary_json: Path
    rows_csv: Path
    symbol_summary_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "rows_csv": str(self.rows_csv),
            "symbol_summary_csv": str(self.symbol_summary_csv),
        }


def _semantic_role(trend_alignment: str) -> str:
    normalized = trend_alignment.strip().lower()
    if normalized not in _SUPPORTED_ALIGNMENTS:
        raise ValueError(
            f"unsupported progression trend alignment: {trend_alignment!r}"
        )
    return {
        "opposed": ROLE_TRANSITION_WARNING,
        "aligned": ROLE_ALIGNED_OBSERVATION,
        "neutral": ROLE_NEUTRAL_OBSERVATION,
        "unknown": ROLE_UNKNOWN_CONTEXT,
    }[normalized]


def project_progression_shadow_semantic(
    row: ProgressionDirectionalityRow,
) -> ProgressionShadowSemanticRow:
    """Project one validated progression event into a shadow-only role."""

    role = _semantic_role(row.trend_alignment)
    transition_direction = (
        row.event_direction
        if role == ROLE_TRANSITION_WARNING
        else None
    )
    return ProgressionShadowSemanticRow(
        symbol=row.symbol,
        event_bar_index=row.event_bar_index,
        event_week=row.event_week,
        event_code=row.event_code,
        event_direction=row.event_direction,
        trend_direction=row.trend_direction,
        trend_alignment=row.trend_alignment,
        semantic_role=role,
        projected_transition_direction=transition_direction,
        reversal_confirmed=False,
        persistent_direction_claim=False,
        affects_qualification=False,
        affects_scoring=False,
        is_actionable=False,
    )


def _symbol_summary(
    *,
    symbol: str,
    rows: tuple[ProgressionShadowSemanticRow, ...],
) -> ProgressionShadowSemanticSymbolSummary:
    roles = Counter(item.semantic_role for item in rows)
    warnings = Counter(
        item.event_direction
        for item in rows
        if item.semantic_role == ROLE_TRANSITION_WARNING
    )
    return ProgressionShadowSemanticSymbolSummary(
        symbol=symbol,
        event_count=len(rows),
        transition_warning_count=roles[ROLE_TRANSITION_WARNING],
        aligned_observation_count=roles[ROLE_ALIGNED_OBSERVATION],
        neutral_observation_count=roles[ROLE_NEUTRAL_OBSERVATION],
        unknown_context_count=roles[ROLE_UNKNOWN_CONTEXT],
        bullish_transition_warning_count=warnings["bullish"],
        bearish_transition_warning_count=warnings["bearish"],
    )


def build_progression_shadow_semantic_audit(
    *,
    basket_name: str,
    requested_symbols: tuple[str, ...],
    rows_by_symbol: dict[
        str,
        tuple[ProgressionDirectionalityRow, ...],
    ],
    expected_event_counts: dict[str, int] | None = None,
) -> ProgressionShadowSemanticAudit:
    requested = tuple(
        str(symbol).strip().upper() for symbol in requested_symbols
    )
    if len(set(requested)) != len(requested):
        raise ValueError("requested symbols must be unique")

    missing = sorted(set(requested) - set(rows_by_symbol))
    if missing:
        raise ValueError(
            f"projection input is missing requested symbols: {missing}"
        )

    all_rows: list[ProgressionShadowSemanticRow] = []
    symbol_summaries: list[ProgressionShadowSemanticSymbolSummary] = []
    seen: set[tuple[str, int, str]] = set()

    for symbol in requested:
        source_rows = rows_by_symbol[symbol]
        if expected_event_counts is not None:
            expected = expected_event_counts.get(symbol)
            if expected is None:
                raise ValueError(
                    f"missing expected event count for {symbol}"
                )
            if len(source_rows) != expected:
                raise ValueError(
                    f"{symbol} event count mismatch: "
                    f"{len(source_rows)} != {expected}"
                )

        projected: list[ProgressionShadowSemanticRow] = []
        for source in source_rows:
            if source.symbol != symbol:
                raise ValueError(
                    f"{symbol} received progression row for {source.symbol}"
                )
            key = (
                source.symbol,
                source.event_bar_index,
                source.event_code,
            )
            if key in seen:
                raise ValueError(
                    f"duplicate progression projection input: {key}"
                )
            seen.add(key)
            item = project_progression_shadow_semantic(source)
            projected.append(item)
            all_rows.append(item)

        symbol_summaries.append(
            _symbol_summary(
                symbol=symbol,
                rows=tuple(projected),
            )
        )

    rows = tuple(
        sorted(
            all_rows,
            key=lambda item: (
                item.symbol,
                item.event_bar_index,
                item.event_code,
            ),
        )
    )
    roles = Counter(item.semantic_role for item in rows)
    directions = Counter(
        item.projected_transition_direction
        for item in rows
        if item.semantic_role == ROLE_TRANSITION_WARNING
    )

    return ProgressionShadowSemanticAudit(
        audit_id=PROGRESSION_SHADOW_SEMANTIC_AUDIT_ID,
        basket_name=basket_name,
        requested_symbol_count=len(requested),
        event_count=len(rows),
        semantic_role_counts={
            ROLE_TRANSITION_WARNING: roles[ROLE_TRANSITION_WARNING],
            ROLE_ALIGNED_OBSERVATION: roles[ROLE_ALIGNED_OBSERVATION],
            ROLE_NEUTRAL_OBSERVATION: roles[ROLE_NEUTRAL_OBSERVATION],
            ROLE_UNKNOWN_CONTEXT: roles[ROLE_UNKNOWN_CONTEXT],
        },
        transition_warning_direction_counts={
            "bullish": directions["bullish"],
            "bearish": directions["bearish"],
        },
        rows=rows,
        symbol_summaries=tuple(
            sorted(symbol_summaries, key=lambda item: item.symbol)
        ),
    )


def write_progression_shadow_semantic_audit(
    audit: ProgressionShadowSemanticAudit,
    output_dir: str | Path,
) -> ProgressionShadowSemanticAuditPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = ProgressionShadowSemanticAuditPaths(
        summary_json=root / "progression_shadow_semantic_summary.json",
        rows_csv=root / "progression_shadow_semantic_rows.csv",
        symbol_summary_csv=root / "progression_shadow_semantic_symbols.csv",
    )

    summary = {
        "audit_id": audit.audit_id,
        "basket_name": audit.basket_name,
        "requested_symbol_count": audit.requested_symbol_count,
        "event_count": audit.event_count,
        "semantic_role_counts": audit.semantic_role_counts,
        "transition_warning_direction_counts": (
            audit.transition_warning_direction_counts
        ),
        "projection_contract": {
            "opposed": ROLE_TRANSITION_WARNING,
            "aligned": ROLE_ALIGNED_OBSERVATION,
            "neutral": ROLE_NEUTRAL_OBSERVATION,
            "unknown": ROLE_UNKNOWN_CONTEXT,
        },
        "reversal_confirmed": False,
        "persistent_direction_claim": False,
        "affects_qualification": False,
        "affects_scoring": False,
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    pd.DataFrame(
        [asdict(item) for item in audit.rows],
    ).to_csv(paths.rows_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.symbol_summaries],
    ).to_csv(paths.symbol_summary_csv, index=False)
    return paths


__all__ = [
    "PROGRESSION_SHADOW_SEMANTIC_AUDIT_ID",
    "ROLE_ALIGNED_OBSERVATION",
    "ROLE_NEUTRAL_OBSERVATION",
    "ROLE_TRANSITION_WARNING",
    "ROLE_UNKNOWN_CONTEXT",
    "ProgressionShadowSemanticAudit",
    "ProgressionShadowSemanticAuditPaths",
    "ProgressionShadowSemanticRow",
    "ProgressionShadowSemanticSymbolSummary",
    "build_progression_shadow_semantic_audit",
    "project_progression_shadow_semantic",
    "write_progression_shadow_semantic_audit",
]
