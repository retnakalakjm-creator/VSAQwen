"""Audit structural-swing score inputs behind weekly progression events.

This module is analysis-only. It observes existing production ScannerCandidate
context and reconstructs the exact score windows used by professional
progression. It does not change swing scoring, progression thresholds, or
qualification semantics.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

import pandas as pd

import config
from audit.genuine_daily_sequence_case import (
    ProductionWeeklySourceFingerprint,
    fingerprint_production_weekly_source,
)
from daily_completion import completed_daily_only
from data import completed_weekly_only, daily_to_weekly
from historical_scanner import HistoricalScannerRunner
from market_structure.progression import calculate_professional_progression
from metrics_engine import MetricsEngine
from models import EvidenceCode, StructuralSwing
from scanner import ScannerCandidate
from trading_calendar import NSETradingCalendar, TradingCalendar


WEEKLY_PROGRESSION_SCORE_INPUT_AUDIT_ID = (
    "production-weekly-progression-score-input-ledger-v1"
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
class StructuralSwingScoreRow:
    confirmation_index: int
    pivot_index: int
    week: str
    swing_type: str
    swing_label: str | None
    grade: str
    is_failed: bool
    structure_price: float
    structure_structural_size: float
    structure_duration: float
    structure_volume: float
    structure_spread: float
    structure_overall: float
    smart_money_stopping_volume: float
    smart_money_climactic_volume: float
    smart_money_overall: float
    professional_overall: float
    current_amplitude: float
    current_duration: int
    current_spread_adjusted_amplitude: float | None
    history_amplitude_count: int
    history_volume_count: int
    history_spread_count: int


@dataclass(frozen=True, slots=True)
class ProgressionScoreWindowRow:
    event_bar_index: int
    event_week: str
    event_code: str
    event_direction: str
    structural_swing_count: int
    window_size: int
    older_first_confirmation: int
    older_last_confirmation: int
    recent_first_confirmation: int
    recent_last_confirmation: int
    reported_progression_difference: float
    reconstructed_progression_difference: float
    reconstruction_matches: bool
    older_professional_overall: float
    recent_professional_overall: float
    professional_overall_delta: float
    structure_overall_delta: float
    smart_money_overall_delta: float
    structure_price_delta: float
    structure_structural_size_delta: float
    structure_duration_delta: float
    structure_volume_delta: float
    structure_spread_delta: float
    smart_money_stopping_volume_delta: float
    smart_money_climactic_volume_delta: float


@dataclass(frozen=True, slots=True)
class WeeklyProgressionScoreInputAudit:
    symbol: str
    audit_id: str
    source_fingerprint: ProductionWeeklySourceFingerprint
    candidate_count: int
    unique_structural_swing_count: int
    progression_event_count: int
    bullish_event_count: int
    bearish_event_count: int
    swing_rows: tuple[StructuralSwingScoreRow, ...]
    window_rows: tuple[ProgressionScoreWindowRow, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class WeeklyProgressionScoreInputAuditPaths:
    summary_json: Path
    swing_ledger_csv: Path
    progression_window_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "swing_ledger_csv": str(self.swing_ledger_csv),
            "progression_window_csv": str(self.progression_window_csv),
        }


def _normalize_symbol(symbol: str) -> str:
    clean = str(symbol).strip().upper()
    if not clean:
        raise ValueError("symbol cannot be blank")
    return clean


def _weighted_average(values: list[float]) -> float:
    if not values:
        return 0.0
    weights = range(1, len(values) + 1)
    return sum(
        value * weight
        for value, weight in zip(values, weights)
    ) / sum(weights)


def _weighted_attr(
    swings: tuple[StructuralSwing, ...],
    getter,
) -> float:
    return _weighted_average([float(getter(item)) for item in swings])


def _direction_for_code(code: EvidenceCode) -> str:
    if code is EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING:
        return "bullish"
    if code is EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING:
        return "bearish"
    raise ValueError(f"unsupported progression code: {code}")


def _swing_key(swing: StructuralSwing) -> tuple[int, int, str, str]:
    return (
        swing.swing.confirmation_index,
        swing.swing.bar_index,
        swing.swing.type.value,
        swing.swing.week_beginning,
    )


def _swing_row(swing: StructuralSwing) -> StructuralSwingScoreRow:
    structure = swing.evaluation.professional.structure
    smart_money = swing.evaluation.professional.smart_money
    history = swing.evaluation.structure.snapshot

    return StructuralSwingScoreRow(
        confirmation_index=swing.swing.confirmation_index,
        pivot_index=swing.swing.bar_index,
        week=swing.swing.week_beginning,
        swing_type=swing.swing.type.value,
        swing_label=(
            None
            if swing.swing.label is None
            else swing.swing.label.value
        ),
        grade=swing.grade.name.lower(),
        is_failed=bool(swing.is_failed),
        structure_price=float(structure.price),
        structure_structural_size=float(structure.structural_size),
        structure_duration=float(structure.duration),
        structure_volume=float(structure.volume),
        structure_spread=float(structure.spread),
        structure_overall=float(structure.overall),
        smart_money_stopping_volume=float(smart_money.stopping_volume),
        smart_money_climactic_volume=float(smart_money.climactic_volume),
        smart_money_overall=float(smart_money.overall),
        professional_overall=float(swing.evaluation.professional.overall),
        current_amplitude=float(history.current_amplitude),
        current_duration=int(history.current_duration),
        current_spread_adjusted_amplitude=(
            None
            if history.current_spread_adjusted_amplitude is None
            else float(history.current_spread_adjusted_amplitude)
        ),
        history_amplitude_count=len(history.amplitudes),
        history_volume_count=len(history.volumes),
        history_spread_count=len(history.spreads),
    )


def _window_row(
    *,
    candidate: ScannerCandidate,
    event_code: EvidenceCode,
    event_bar_index: int,
    event_week: str,
) -> ProgressionScoreWindowRow:
    swings = tuple(candidate.evidence.context.structural_swings)
    _, reported = calculate_professional_progression(swings)
    if reported is None:
        raise ValueError("progression event has no progression difference")

    window = min(5, len(swings) // 2)
    if window <= 0:
        raise ValueError("progression event has no valid score window")
    older = swings[-(window * 2):-window]
    recent = swings[-window:]
    if not older or not recent:
        raise ValueError("progression event has incomplete score windows")

    older_professional = _weighted_attr(
        older,
        lambda item: item.evaluation.professional.overall,
    )
    recent_professional = _weighted_attr(
        recent,
        lambda item: item.evaluation.professional.overall,
    )
    reconstructed = recent_professional - older_professional

    def delta(getter) -> float:
        return _weighted_attr(recent, getter) - _weighted_attr(older, getter)

    return ProgressionScoreWindowRow(
        event_bar_index=event_bar_index,
        event_week=event_week,
        event_code=event_code.value,
        event_direction=_direction_for_code(event_code),
        structural_swing_count=len(swings),
        window_size=window,
        older_first_confirmation=older[0].swing.confirmation_index,
        older_last_confirmation=older[-1].swing.confirmation_index,
        recent_first_confirmation=recent[0].swing.confirmation_index,
        recent_last_confirmation=recent[-1].swing.confirmation_index,
        reported_progression_difference=float(reported),
        reconstructed_progression_difference=float(reconstructed),
        reconstruction_matches=abs(float(reported) - reconstructed) < 1e-12,
        older_professional_overall=float(older_professional),
        recent_professional_overall=float(recent_professional),
        professional_overall_delta=float(reconstructed),
        structure_overall_delta=delta(
            lambda item: item.evaluation.professional.structure.overall
        ),
        smart_money_overall_delta=delta(
            lambda item: item.evaluation.professional.smart_money.overall
        ),
        structure_price_delta=delta(
            lambda item: item.evaluation.professional.structure.price
        ),
        structure_structural_size_delta=delta(
            lambda item: (
                item.evaluation.professional.structure.structural_size
            )
        ),
        structure_duration_delta=delta(
            lambda item: item.evaluation.professional.structure.duration
        ),
        structure_volume_delta=delta(
            lambda item: item.evaluation.professional.structure.volume
        ),
        structure_spread_delta=delta(
            lambda item: item.evaluation.professional.structure.spread
        ),
        smart_money_stopping_volume_delta=delta(
            lambda item: (
                item.evaluation.professional.smart_money.stopping_volume
            )
        ),
        smart_money_climactic_volume_delta=delta(
            lambda item: (
                item.evaluation.professional.smart_money.climactic_volume
            )
        ),
    )


def audit_weekly_progression_score_inputs(
    *,
    symbol: str,
    candidates: tuple[ScannerCandidate, ...],
    source_fingerprint: ProductionWeeklySourceFingerprint,
) -> WeeklyProgressionScoreInputAudit:
    """Audit exact swing-score inputs used by emitted progression events."""

    clean_symbol = _normalize_symbol(symbol)
    unique_swings: dict[tuple[int, int, str, str], StructuralSwing] = {}
    window_rows: list[ProgressionScoreWindowRow] = []
    seen_events: set[tuple[int, EvidenceCode]] = set()

    for candidate in candidates:
        for swing in candidate.evidence.context.structural_swings:
            unique_swings[_swing_key(swing)] = swing

        for event in candidate.target_bar_evidence:
            if event.code not in _STRUCTURAL_CODES:
                continue
            key = (event.bar_index, event.code)
            if key in seen_events:
                continue
            seen_events.add(key)
            window_rows.append(
                _window_row(
                    candidate=candidate,
                    event_code=event.code,
                    event_bar_index=event.bar_index,
                    event_week=str(event.week_beginning),
                )
            )

    swing_rows = tuple(
        _swing_row(unique_swings[key])
        for key in sorted(unique_swings)
    )
    bullish = sum(
        1 for row in window_rows if row.event_direction == "bullish"
    )
    bearish = sum(
        1 for row in window_rows if row.event_direction == "bearish"
    )

    return WeeklyProgressionScoreInputAudit(
        symbol=clean_symbol,
        audit_id=WEEKLY_PROGRESSION_SCORE_INPUT_AUDIT_ID,
        source_fingerprint=source_fingerprint,
        candidate_count=len(candidates),
        unique_structural_swing_count=len(swing_rows),
        progression_event_count=len(window_rows),
        bullish_event_count=bullish,
        bearish_event_count=bearish,
        swing_rows=swing_rows,
        window_rows=tuple(window_rows),
    )


def build_weekly_progression_score_input_audit(
    *,
    symbol: str,
    daily: pd.DataFrame,
    now: datetime | pd.Timestamp | str | None = None,
    calendar: TradingCalendar | None = None,
    historical_runner: _HistoricalRunner | None = None,
    metrics_engine: _MetricsEngine | None = None,
) -> WeeklyProgressionScoreInputAudit:
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

    return audit_weekly_progression_score_inputs(
        symbol=clean_symbol,
        candidates=candidates,
        source_fingerprint=fingerprint_production_weekly_source(
            symbol=clean_symbol,
            completed_weekly=completed_weekly,
        ),
    )


def write_weekly_progression_score_input_audit(
    audit: WeeklyProgressionScoreInputAudit,
    output_dir: str | Path,
) -> WeeklyProgressionScoreInputAuditPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = WeeklyProgressionScoreInputAuditPaths(
        summary_json=root / "weekly_progression_score_input_summary.json",
        swing_ledger_csv=root / "weekly_structural_swing_score_ledger.csv",
        progression_window_csv=(
            root / "weekly_progression_score_window_ledger.csv"
        ),
    )

    summary = {
        "symbol": audit.symbol,
        "audit_id": audit.audit_id,
        "candidate_count": audit.candidate_count,
        "unique_structural_swing_count": audit.unique_structural_swing_count,
        "progression_event_count": audit.progression_event_count,
        "event_direction_counts": {
            "bullish": audit.bullish_event_count,
            "bearish": audit.bearish_event_count,
        },
        "progression_neutral_margin": config.PROGRESSION_NEUTRAL_MARGIN,
        "professional_weights": {
            "structure": config.PROFESSIONAL_STRUCTURE_WEIGHT,
            "smart_money": config.PROFESSIONAL_SMART_MONEY_WEIGHT,
        },
        "structure_weights": {
            "price": config.STRUCTURE_PRICE_WEIGHT,
            "structural_size": config.STRUCTURE_STRUCTURAL_SIZE_WEIGHT,
            "duration": config.STRUCTURE_DURATION_WEIGHT,
            "volume": config.STRUCTURE_VOLUME_WEIGHT,
            "spread": config.STRUCTURE_SPREAD_WEIGHT,
        },
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
        [asdict(row) for row in audit.swing_rows],
    ).to_csv(paths.swing_ledger_csv, index=False)
    pd.DataFrame(
        [asdict(row) for row in audit.window_rows],
    ).to_csv(paths.progression_window_csv, index=False)
    return paths


__all__ = [
    "WEEKLY_PROGRESSION_SCORE_INPUT_AUDIT_ID",
    "ProgressionScoreWindowRow",
    "StructuralSwingScoreRow",
    "WeeklyProgressionScoreInputAudit",
    "WeeklyProgressionScoreInputAuditPaths",
    "audit_weekly_progression_score_inputs",
    "build_weekly_progression_score_input_audit",
    "write_weekly_progression_score_input_audit",
]
