"""Audit semantic alignment of progression evidence direction across symbols.

This module is analysis-only. It compares already-emitted production structural
progression evidence against same-bar trend direction and structural pattern.
It does not change progression scoring or evidence direction.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from audit.weekly_structural_progression_audit import (
    WeeklyStructuralProgressionAudit,
    WeeklyStructuralProgressionEventRow,
)


PROGRESSION_DIRECTIONALITY_AUDIT_ID = (
    "production-progression-directionality-semantics-v1"
)


@dataclass(frozen=True, slots=True)
class ProgressionDirectionalityRow:
    symbol: str
    event_bar_index: int
    event_week: str
    event_code: str
    event_direction: str
    progression_difference: float | None
    trend_direction: str
    trend_state: str
    structural_pattern: str
    trend_alignment: str
    structural_pattern_alignment: str
    qualification_after_event: str


@dataclass(frozen=True, slots=True)
class ProgressionDirectionalitySymbolSummary:
    symbol: str
    event_count: int
    bullish_event_count: int
    bearish_event_count: int
    trend_aligned_count: int
    trend_opposed_count: int
    trend_neutral_count: int
    trend_unknown_count: int
    pattern_aligned_count: int
    pattern_opposed_count: int
    pattern_ambiguous_count: int


@dataclass(frozen=True, slots=True)
class ProgressionDirectionalityFailure:
    symbol: str
    exception_type: str
    reason: str


@dataclass(frozen=True, slots=True)
class ProgressionDirectionalityAudit:
    audit_id: str
    basket_name: str
    requested_symbol_count: int
    successful_symbol_count: int
    failed_symbol_count: int
    event_count: int
    event_direction_counts: dict[str, int]
    trend_alignment_counts: dict[str, int]
    structural_pattern_alignment_counts: dict[str, int]
    trend_direction_matrix: dict[str, dict[str, int]]
    structural_pattern_matrix: dict[str, dict[str, int]]
    rows: tuple[ProgressionDirectionalityRow, ...]
    symbol_summaries: tuple[ProgressionDirectionalitySymbolSummary, ...]
    failures: tuple[ProgressionDirectionalityFailure, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ProgressionDirectionalityAuditPaths:
    summary_json: Path
    event_ledger_csv: Path
    symbol_summary_csv: Path
    failure_ledger_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "event_ledger_csv": str(self.event_ledger_csv),
            "symbol_summary_csv": str(self.symbol_summary_csv),
            "failure_ledger_csv": str(self.failure_ledger_csv),
        }


def _trend_alignment(
    *,
    event_direction: str,
    trend_direction: str,
) -> str:
    normalized = trend_direction.strip().lower()
    expected = {
        "up": "bullish",
        "down": "bearish",
    }.get(normalized)
    if expected is None:
        if normalized == "range":
            return "neutral"
        return "unknown"
    return "aligned" if event_direction == expected else "opposed"


def _pattern_alignment(
    *,
    event_direction: str,
    structural_pattern: str,
) -> str:
    normalized = structural_pattern.strip().lower()
    expected = {
        "improving": "bullish",
        "weakening": "bearish",
    }.get(normalized)
    if expected is None:
        return "ambiguous"
    return "aligned" if event_direction == expected else "opposed"


def _convert_row(
    *,
    symbol: str,
    row: WeeklyStructuralProgressionEventRow,
) -> ProgressionDirectionalityRow:
    return ProgressionDirectionalityRow(
        symbol=symbol,
        event_bar_index=row.event_bar_index,
        event_week=row.event_week,
        event_code=row.event_code,
        event_direction=row.event_direction,
        progression_difference=row.progression_difference,
        trend_direction=row.trend_direction,
        trend_state=row.trend_state,
        structural_pattern=row.structural_pattern,
        trend_alignment=_trend_alignment(
            event_direction=row.event_direction,
            trend_direction=row.trend_direction,
        ),
        structural_pattern_alignment=_pattern_alignment(
            event_direction=row.event_direction,
            structural_pattern=row.structural_pattern,
        ),
        qualification_after_event=row.qualification_after_event.value,
    )


def _symbol_summary(
    *,
    symbol: str,
    rows: tuple[ProgressionDirectionalityRow, ...],
) -> ProgressionDirectionalitySymbolSummary:
    direction = Counter(item.event_direction for item in rows)
    trend = Counter(item.trend_alignment for item in rows)
    pattern = Counter(item.structural_pattern_alignment for item in rows)
    return ProgressionDirectionalitySymbolSummary(
        symbol=symbol,
        event_count=len(rows),
        bullish_event_count=direction["bullish"],
        bearish_event_count=direction["bearish"],
        trend_aligned_count=trend["aligned"],
        trend_opposed_count=trend["opposed"],
        trend_neutral_count=trend["neutral"],
        trend_unknown_count=trend["unknown"],
        pattern_aligned_count=pattern["aligned"],
        pattern_opposed_count=pattern["opposed"],
        pattern_ambiguous_count=pattern["ambiguous"],
    )


def _matrix(
    rows: tuple[ProgressionDirectionalityRow, ...],
    *,
    dimension: str,
) -> dict[str, dict[str, int]]:
    outer: dict[str, Counter[str]] = {}
    for row in rows:
        key = str(getattr(row, dimension))
        outer.setdefault(key, Counter())
        outer[key][row.event_direction] += 1
    return {
        key: {
            "bullish": counts["bullish"],
            "bearish": counts["bearish"],
        }
        for key, counts in sorted(outer.items())
    }


def summarize_progression_directionality(
    *,
    basket_name: str,
    requested_symbols: tuple[str, ...],
    audits: tuple[WeeklyStructuralProgressionAudit, ...],
    failures: tuple[ProgressionDirectionalityFailure, ...] = (),
) -> ProgressionDirectionalityAudit:
    """Summarize semantic alignment from already-built production audits."""

    rows_list: list[ProgressionDirectionalityRow] = []
    symbol_summaries: list[ProgressionDirectionalitySymbolSummary] = []
    for audit in audits:
        converted = tuple(
            _convert_row(symbol=audit.symbol, row=row)
            for row in audit.rows
        )
        rows_list.extend(converted)
        symbol_summaries.append(
            _symbol_summary(
                symbol=audit.symbol,
                rows=converted,
            )
        )

    rows = tuple(
        sorted(
            rows_list,
            key=lambda item: (
                item.symbol,
                item.event_bar_index,
                item.event_code,
            ),
        )
    )
    direction = Counter(item.event_direction for item in rows)
    trend = Counter(item.trend_alignment for item in rows)
    pattern = Counter(item.structural_pattern_alignment for item in rows)

    return ProgressionDirectionalityAudit(
        audit_id=PROGRESSION_DIRECTIONALITY_AUDIT_ID,
        basket_name=basket_name,
        requested_symbol_count=len(requested_symbols),
        successful_symbol_count=len(audits),
        failed_symbol_count=len(failures),
        event_count=len(rows),
        event_direction_counts={
            "bullish": direction["bullish"],
            "bearish": direction["bearish"],
        },
        trend_alignment_counts={
            "aligned": trend["aligned"],
            "opposed": trend["opposed"],
            "neutral": trend["neutral"],
            "unknown": trend["unknown"],
        },
        structural_pattern_alignment_counts={
            "aligned": pattern["aligned"],
            "opposed": pattern["opposed"],
            "ambiguous": pattern["ambiguous"],
        },
        trend_direction_matrix=_matrix(
            rows,
            dimension="trend_direction",
        ),
        structural_pattern_matrix=_matrix(
            rows,
            dimension="structural_pattern",
        ),
        rows=rows,
        symbol_summaries=tuple(
            sorted(symbol_summaries, key=lambda item: item.symbol)
        ),
        failures=tuple(sorted(failures, key=lambda item: item.symbol)),
    )


def write_progression_directionality_audit(
    audit: ProgressionDirectionalityAudit,
    output_dir: str | Path,
) -> ProgressionDirectionalityAuditPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = ProgressionDirectionalityAuditPaths(
        summary_json=root / "progression_directionality_summary.json",
        event_ledger_csv=root / "progression_directionality_events.csv",
        symbol_summary_csv=root / "progression_directionality_symbols.csv",
        failure_ledger_csv=root / "progression_directionality_failures.csv",
    )

    summary = {
        "audit_id": audit.audit_id,
        "basket_name": audit.basket_name,
        "requested_symbol_count": audit.requested_symbol_count,
        "successful_symbol_count": audit.successful_symbol_count,
        "failed_symbol_count": audit.failed_symbol_count,
        "event_count": audit.event_count,
        "event_direction_counts": audit.event_direction_counts,
        "trend_alignment_counts": audit.trend_alignment_counts,
        "structural_pattern_alignment_counts": (
            audit.structural_pattern_alignment_counts
        ),
        "trend_direction_matrix": audit.trend_direction_matrix,
        "structural_pattern_matrix": audit.structural_pattern_matrix,
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    import pandas as pd

    pd.DataFrame(
        [asdict(row) for row in audit.rows],
    ).to_csv(paths.event_ledger_csv, index=False)
    pd.DataFrame(
        [asdict(row) for row in audit.symbol_summaries],
    ).to_csv(paths.symbol_summary_csv, index=False)
    pd.DataFrame(
        [asdict(row) for row in audit.failures],
        columns=("symbol", "exception_type", "reason"),
    ).to_csv(paths.failure_ledger_csv, index=False)
    return paths


__all__ = [
    "PROGRESSION_DIRECTIONALITY_AUDIT_ID",
    "ProgressionDirectionalityAudit",
    "ProgressionDirectionalityAuditPaths",
    "ProgressionDirectionalityFailure",
    "ProgressionDirectionalityRow",
    "ProgressionDirectionalitySymbolSummary",
    "summarize_progression_directionality",
    "write_progression_directionality_audit",
]
