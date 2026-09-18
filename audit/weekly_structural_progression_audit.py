"""Audit the raw weekly structural-progression event stream.

This module is analysis-only. It observes the production ScannerCandidate stream
and records structural progression events exactly as emitted by the existing
EvidenceEngine. It does not alter swing scoring, progression thresholds, or
qualification semantics.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

import pandas as pd

from audit.genuine_daily_sequence_case import (
    ProductionWeeklySourceFingerprint,
    fingerprint_production_weekly_source,
)
from background.qualification import PatternQualification, PatternQualificationEngine
from daily_completion import completed_daily_only
from data import completed_weekly_only, daily_to_weekly
from historical_scanner import HistoricalScannerRunner
from market_structure.progression import calculate_professional_progression
from metrics_engine import MetricsEngine
from models import EvidenceCode
from scanner import ScannerCandidate
from trading_calendar import NSETradingCalendar, TradingCalendar


WEEKLY_STRUCTURAL_PROGRESSION_AUDIT_ID = (
    "production-weekly-structural-progression-ledger-v1"
)
_STRUCTURAL_CODES = frozenset(
    {
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
        EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
    }
)


class _HistoricalRunner(Protocol):
    def scan(self, metrics: pd.DataFrame) -> list[ScannerCandidate]:
        ...


class _MetricsEngine(Protocol):
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        ...


@dataclass(frozen=True, slots=True)
class WeeklyStructuralProgressionEventRow:
    event_bar_index: int
    event_week: str
    event_code: str
    event_direction: str
    event_strength: float
    progression_difference: float | None
    trend_direction: str
    trend_state: str
    structural_pattern: str
    structural_swing_count: int
    latest_swing_type: str | None
    latest_swing_label: str | None
    latest_swing_pivot_index: int | None
    latest_swing_confirmation_index: int | None
    latest_swing_week: str | None
    latest_swing_grade: str | None
    latest_swing_professional_overall: float | None
    previous_event_code: str | None
    previous_event_bar_index: int | None
    bars_since_previous_event: int | None
    previous_same_direction_bar_index: int | None
    bars_since_previous_same_direction: int | None
    meets_min_same_direction_spacing: bool | None
    qualification_after_event: PatternQualification
    qualification_actionable_after_event: bool
    event_used_in_qualification: bool


@dataclass(frozen=True, slots=True)
class WeeklyStructuralProgressionAudit:
    symbol: str
    audit_id: str
    source_fingerprint: ProductionWeeklySourceFingerprint
    candidate_count: int
    event_count: int
    improving_event_count: int
    weakening_event_count: int
    first_improving_week: str | None
    last_improving_week: str | None
    first_weakening_week: str | None
    last_weakening_week: str | None
    first_persistent_bullish_week: str | None
    first_persistent_bearish_week: str | None
    rows: tuple[WeeklyStructuralProgressionEventRow, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class WeeklyStructuralProgressionAuditPaths:
    summary_json: Path
    event_ledger_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "event_ledger_csv": str(self.event_ledger_csv),
        }


def _normalize_symbol(symbol: str) -> str:
    clean = str(symbol).strip().upper()
    if not clean:
        raise ValueError("symbol cannot be blank")
    return clean


def _direction_for_code(code: EvidenceCode) -> str:
    if code is EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING:
        return "bullish"
    if code is EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING:
        return "bearish"
    raise ValueError(f"unsupported structural progression code: {code}")


def _first_candidate_week(
    candidates: tuple[ScannerCandidate, ...],
    qualification: PatternQualification,
) -> str | None:
    for candidate in candidates:
        if candidate.qualification is qualification:
            return candidate.week
    return None


def audit_weekly_structural_progression_candidates(
    *,
    symbol: str,
    candidates: tuple[ScannerCandidate, ...],
    source_fingerprint: ProductionWeeklySourceFingerprint,
) -> WeeklyStructuralProgressionAudit:
    """Audit progression events already emitted in production candidate replay."""

    clean_symbol = _normalize_symbol(symbol)
    rows: list[WeeklyStructuralProgressionEventRow] = []
    seen: set[tuple[int, EvidenceCode]] = set()
    previous_event_bar: int | None = None
    previous_event_code: EvidenceCode | None = None
    previous_by_direction: dict[str, int] = {}

    for candidate in candidates:
        current_events = tuple(
            item
            for item in candidate.target_bar_evidence
            if item.code in _STRUCTURAL_CODES
        )
        for event in current_events:
            key = (event.bar_index, event.code)
            if key in seen:
                continue
            seen.add(key)

            direction = _direction_for_code(event.code)
            structural_swings = tuple(
                candidate.evidence.context.structural_swings
            )
            _, difference = calculate_professional_progression(
                structural_swings
            )
            latest = (
                structural_swings[-1]
                if structural_swings
                and structural_swings[-1].swing.confirmation_index
                == event.bar_index
                else None
            )

            if (
                previous_event_code is not None
                and _direction_for_code(previous_event_code) != direction
            ):
                previous_by_direction.clear()

            previous_same = previous_by_direction.get(direction)
            same_spacing = (
                None
                if previous_same is None
                else event.bar_index - previous_same
            )
            qualifies_by_spacing = (
                None
                if same_spacing is None
                else same_spacing
                >= PatternQualificationEngine.MIN_EVENT_SPACING_BARS
            )
            qualifying_keys = {
                (item.bar_index, item.code)
                for item in candidate.qualifying_evidence
            }

            rows.append(
                WeeklyStructuralProgressionEventRow(
                    event_bar_index=event.bar_index,
                    event_week=str(event.week_beginning),
                    event_code=event.code.value,
                    event_direction=direction,
                    event_strength=float(event.strength),
                    progression_difference=(
                        None if difference is None else float(difference)
                    ),
                    trend_direction=(
                        candidate.evidence.context.trend.direction.value
                    ),
                    trend_state=(
                        candidate.evidence.context.trend.state.value
                    ),
                    structural_pattern=(
                        candidate.evidence.context.structural_pattern.name.lower()
                    ),
                    structural_swing_count=len(structural_swings),
                    latest_swing_type=(
                        None if latest is None else latest.swing.type.value
                    ),
                    latest_swing_label=(
                        None
                        if latest is None or latest.swing.label is None
                        else latest.swing.label.value
                    ),
                    latest_swing_pivot_index=(
                        None if latest is None else latest.swing.bar_index
                    ),
                    latest_swing_confirmation_index=(
                        None
                        if latest is None
                        else latest.swing.confirmation_index
                    ),
                    latest_swing_week=(
                        None if latest is None else latest.swing.week_beginning
                    ),
                    latest_swing_grade=(
                        None if latest is None else latest.grade.name.lower()
                    ),
                    latest_swing_professional_overall=(
                        None
                        if latest is None
                        else float(latest.evaluation.professional.overall)
                    ),
                    previous_event_code=(
                        None
                        if previous_event_code is None
                        else previous_event_code.value
                    ),
                    previous_event_bar_index=previous_event_bar,
                    bars_since_previous_event=(
                        None
                        if previous_event_bar is None
                        else event.bar_index - previous_event_bar
                    ),
                    previous_same_direction_bar_index=previous_same,
                    bars_since_previous_same_direction=same_spacing,
                    meets_min_same_direction_spacing=qualifies_by_spacing,
                    qualification_after_event=candidate.qualification,
                    qualification_actionable_after_event=(
                        candidate.qualification_result.is_actionable_evidence
                    ),
                    event_used_in_qualification=key in qualifying_keys,
                )
            )

            previous_event_bar = event.bar_index
            previous_event_code = event.code
            previous_by_direction[direction] = event.bar_index

    improving = tuple(
        row for row in rows if row.event_direction == "bullish"
    )
    weakening = tuple(
        row for row in rows if row.event_direction == "bearish"
    )

    return WeeklyStructuralProgressionAudit(
        symbol=clean_symbol,
        audit_id=WEEKLY_STRUCTURAL_PROGRESSION_AUDIT_ID,
        source_fingerprint=source_fingerprint,
        candidate_count=len(candidates),
        event_count=len(rows),
        improving_event_count=len(improving),
        weakening_event_count=len(weakening),
        first_improving_week=(
            None if not improving else improving[0].event_week
        ),
        last_improving_week=(
            None if not improving else improving[-1].event_week
        ),
        first_weakening_week=(
            None if not weakening else weakening[0].event_week
        ),
        last_weakening_week=(
            None if not weakening else weakening[-1].event_week
        ),
        first_persistent_bullish_week=_first_candidate_week(
            candidates,
            PatternQualification.PERSISTENT_BULLISH,
        ),
        first_persistent_bearish_week=_first_candidate_week(
            candidates,
            PatternQualification.PERSISTENT_BEARISH,
        ),
        rows=tuple(rows),
    )


def build_weekly_structural_progression_audit(
    *,
    symbol: str,
    daily: pd.DataFrame,
    now: datetime | pd.Timestamp | str | None = None,
    calendar: TradingCalendar | None = None,
    historical_runner: _HistoricalRunner | None = None,
    metrics_engine: _MetricsEngine | None = None,
) -> WeeklyStructuralProgressionAudit:
    clean_symbol = _normalize_symbol(symbol)
    exchange_calendar = calendar or NSETradingCalendar()
    completed_daily = completed_daily_only(
        daily,
        now=now,
        calendar=exchange_calendar,
    )
    if completed_daily.empty:
        raise ValueError("no completed daily bars are available")

    weekly = daily_to_weekly(completed_daily)
    completed_weekly = completed_weekly_only(weekly, now=now)
    if completed_weekly.empty:
        raise ValueError("no completed weekly bars are available")

    engine = metrics_engine or MetricsEngine()
    metrics = engine.calculate(completed_weekly)
    runner = historical_runner or HistoricalScannerRunner()
    candidates = tuple(runner.scan(metrics))

    return audit_weekly_structural_progression_candidates(
        symbol=clean_symbol,
        candidates=candidates,
        source_fingerprint=fingerprint_production_weekly_source(
            symbol=clean_symbol,
            completed_weekly=completed_weekly,
        ),
    )


def _row_payload(
    row: WeeklyStructuralProgressionEventRow,
) -> dict[str, object]:
    payload = asdict(row)
    payload["qualification_after_event"] = (
        row.qualification_after_event.value
    )
    return payload


def write_weekly_structural_progression_audit(
    audit: WeeklyStructuralProgressionAudit,
    output_dir: str | Path,
) -> WeeklyStructuralProgressionAuditPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = WeeklyStructuralProgressionAuditPaths(
        summary_json=root / "weekly_structural_progression_summary.json",
        event_ledger_csv=root / "weekly_structural_progression_ledger.csv",
    )

    summary = {
        "symbol": audit.symbol,
        "audit_id": audit.audit_id,
        "candidate_count": audit.candidate_count,
        "event_count": audit.event_count,
        "event_direction_counts": {
            "bullish": audit.improving_event_count,
            "bearish": audit.weakening_event_count,
        },
        "first_improving_week": audit.first_improving_week,
        "last_improving_week": audit.last_improving_week,
        "first_weakening_week": audit.first_weakening_week,
        "last_weakening_week": audit.last_weakening_week,
        "first_persistent_bullish_week": (
            audit.first_persistent_bullish_week
        ),
        "first_persistent_bearish_week": (
            audit.first_persistent_bearish_week
        ),
        "min_qualifying_events": (
            PatternQualificationEngine.MIN_QUALIFYING_EVENTS
        ),
        "min_event_spacing_bars": (
            PatternQualificationEngine.MIN_EVENT_SPACING_BARS
        ),
        "production_weekly_source_fingerprint": (
            audit.source_fingerprint.sha256
        ),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    pd.DataFrame(
        [_row_payload(row) for row in audit.rows],
    ).to_csv(paths.event_ledger_csv, index=False)
    return paths


__all__ = [
    "WEEKLY_STRUCTURAL_PROGRESSION_AUDIT_ID",
    "WeeklyStructuralProgressionAudit",
    "WeeklyStructuralProgressionAuditPaths",
    "WeeklyStructuralProgressionEventRow",
    "audit_weekly_structural_progression_candidates",
    "build_weekly_structural_progression_audit",
    "write_weekly_structural_progression_audit",
]
