"""Generate a genuine K4 daily sequence case from production weekly authority.

This module is analysis-only. It derives historical WeeklySetup objects only
through the existing production weekly scanner/materializer path, then delegates
daily Evidence + weekly-direction composition to K7.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

import pandas as pd

from audit.daily_behavior_sequence_prepare import (
    PreparedDailyBehaviorSequenceCase,
    prepare_daily_behavior_sequence_case,
    write_prepared_daily_behavior_sequence_case,
)
from audit.offline_daily_evidence import (
    DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    DailyEvidencePrefixEvaluator,
)
from daily_completion import completed_daily_only
from data import completed_weekly_only, daily_to_weekly
from engine.columns import (
    COL_CLOSE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_VOLUME,
    COL_WEEK,
)
from historical_scanner import HistoricalScannerRunner
from metrics_engine import MetricsEngine
from scanner import ScannerCandidate
from trading_calendar import NSETradingCalendar, TradingCalendar
from weekly_setup import WeeklySetup
from weekly_setup_materializer import materialize_production_weekly_setup


GENUINE_DAILY_SEQUENCE_GENERATOR_ID = (
    "production-weekly-k5-k6-k4-generator-v1"
)
_REQUIRED_DAILY_COLUMNS = (
    COL_OPEN,
    COL_HIGH,
    COL_LOW,
    COL_CLOSE,
    COL_VOLUME,
)


class _HistoricalRunner(Protocol):
    def scan(self, metrics: pd.DataFrame) -> list[ScannerCandidate]:
        ...


class _MetricsEngine(Protocol):
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        ...


@dataclass(frozen=True, slots=True)
class ProductionWeeklySourceFingerprint:
    symbol: str
    row_count: int
    first_week: str | None
    last_week: str | None
    sha256: str


@dataclass(frozen=True, slots=True)
class HistoricalProductionWeeklySetupArchive:
    symbol: str
    completed_weekly: pd.DataFrame
    source_fingerprint: ProductionWeeklySourceFingerprint
    candidate_count: int
    setups: tuple[WeeklySetup, ...]

    @property
    def setup_count(self) -> int:
        return len(self.setups)

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class GenuineDailyBehaviorSequenceCase:
    symbol: str
    generator_id: str
    weekly_archive: HistoricalProductionWeeklySetupArchive
    prepared_case: PreparedDailyBehaviorSequenceCase

    @property
    def dataset(self):
        return self.prepared_case.dataset

    @property
    def study_input(self):
        return self.prepared_case.study_input

    @property
    def is_actionable(self) -> bool:
        return False


def _normalize_symbol(symbol: str) -> str:
    normalized = str(symbol).strip().upper()
    if not normalized:
        raise ValueError("symbol cannot be blank")
    return normalized


def _validate_daily_source(daily: pd.DataFrame) -> None:
    if daily.empty:
        raise ValueError("daily data cannot be empty")
    if not isinstance(daily.index, pd.DatetimeIndex):
        raise TypeError("daily data must use a DatetimeIndex")
    if not daily.index.is_monotonic_increasing:
        raise ValueError("daily sessions must be sorted")
    if daily.index.has_duplicates:
        raise ValueError("daily sessions must be unique")

    missing = [
        column
        for column in _REQUIRED_DAILY_COLUMNS
        if column not in daily.columns
    ]
    if missing:
        raise ValueError(f"daily data missing required columns: {missing}")


def fingerprint_production_weekly_source(
    *,
    symbol: str,
    completed_weekly: pd.DataFrame,
) -> ProductionWeeklySourceFingerprint:
    clean_symbol = _normalize_symbol(symbol)
    if completed_weekly.empty:
        raise ValueError("completed weekly data cannot be empty")
    if COL_WEEK not in completed_weekly.columns:
        raise ValueError("completed weekly data must contain week_beginning")

    rows = [
        {
            COL_WEEK: pd.Timestamp(row[COL_WEEK]).isoformat(),
            COL_OPEN: float(row[COL_OPEN]),
            COL_HIGH: float(row[COL_HIGH]),
            COL_LOW: float(row[COL_LOW]),
            COL_CLOSE: float(row[COL_CLOSE]),
            COL_VOLUME: float(row[COL_VOLUME]),
        }
        for _, row in completed_weekly.iterrows()
    ]
    payload = {
        "symbol": clean_symbol,
        "rows": rows,
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return ProductionWeeklySourceFingerprint(
        symbol=clean_symbol,
        row_count=len(completed_weekly),
        first_week=rows[0][COL_WEEK],
        last_week=rows[-1][COL_WEEK],
        sha256=f"sha256:{digest}",
    )


def derive_historical_production_weekly_setups(
    *,
    symbol: str,
    daily: pd.DataFrame,
    now: datetime | pd.Timestamp | str | None = None,
    calendar: TradingCalendar | None = None,
    historical_runner: _HistoricalRunner | None = None,
    metrics_engine: _MetricsEngine | None = None,
) -> HistoricalProductionWeeklySetupArchive:
    """Derive WeeklySetup history through the existing production weekly path."""

    clean_symbol = _normalize_symbol(symbol)
    _validate_daily_source(daily)
    exchange_calendar = calendar or NSETradingCalendar()

    completed_daily = completed_daily_only(
        daily,
        now=now,
        calendar=exchange_calendar,
    )
    if completed_daily.empty:
        raise ValueError("no completed daily bars are available")

    weekly = daily_to_weekly(completed_daily)
    completed_weekly = completed_weekly_only(
        weekly,
        now=now,
    )
    if completed_weekly.empty:
        raise ValueError("no completed weekly bars are available")

    engine = metrics_engine or MetricsEngine()
    metrics = engine.calculate(completed_weekly)
    runner = historical_runner or HistoricalScannerRunner()
    candidates = tuple(runner.scan(metrics))

    setups: list[WeeklySetup] = []
    for candidate in candidates:
        setup = materialize_production_weekly_setup(
            candidate,
            symbol=clean_symbol,
        )
        if setup is not None:
            setups.append(setup)

    setup_ids = tuple(setup.setup_id for setup in setups)
    if len(set(setup_ids)) != len(setup_ids):
        raise ValueError("historical production weekly setups require unique ids")

    return HistoricalProductionWeeklySetupArchive(
        symbol=clean_symbol,
        completed_weekly=completed_weekly.copy(),
        source_fingerprint=fingerprint_production_weekly_source(
            symbol=clean_symbol,
            completed_weekly=completed_weekly,
        ),
        candidate_count=len(candidates),
        setups=tuple(setups),
    )


def prepare_genuine_daily_behavior_sequence_case(
    *,
    dataset_id: str,
    symbol: str,
    daily: pd.DataFrame,
    source_reference: str,
    prepared_at_utc: str,
    now: datetime | pd.Timestamp | str | None = None,
    calendar: TradingCalendar | None = None,
    min_target_index: int = DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    prefix_evaluator: DailyEvidencePrefixEvaluator | None = None,
    historical_runner: _HistoricalRunner | None = None,
    metrics_engine: _MetricsEngine | None = None,
    require_weekly_setup: bool = True,
    notes: str = "",
) -> GenuineDailyBehaviorSequenceCase:
    """Prepare one real-source K4 case using production weekly authority."""

    weekly_archive = derive_historical_production_weekly_setups(
        symbol=symbol,
        daily=daily,
        now=now,
        calendar=calendar,
        historical_runner=historical_runner,
        metrics_engine=metrics_engine,
    )
    if require_weekly_setup and not weekly_archive.setups:
        raise ValueError(
            "no actionable production weekly setups were found in the completed "
            "weekly history"
        )

    provenance_notes = (
        f"generator={GENUINE_DAILY_SEQUENCE_GENERATOR_ID}; "
        f"production_weekly_source={weekly_archive.source_fingerprint.sha256}; "
        f"production_weekly_candidate_count={weekly_archive.candidate_count}; "
        f"production_weekly_setup_count={weekly_archive.setup_count}"
    )
    clean_notes = str(notes).strip()
    if clean_notes:
        provenance_notes += f"; {clean_notes}"

    prepared_case = prepare_daily_behavior_sequence_case(
        dataset_id=dataset_id,
        symbol=weekly_archive.symbol,
        daily=daily,
        weekly_setups=weekly_archive.setups,
        source_reference=source_reference,
        prepared_at_utc=prepared_at_utc,
        now=now,
        calendar=calendar,
        min_target_index=min_target_index,
        prefix_evaluator=prefix_evaluator,
        notes=provenance_notes,
    )

    return GenuineDailyBehaviorSequenceCase(
        symbol=weekly_archive.symbol,
        generator_id=GENUINE_DAILY_SEQUENCE_GENERATOR_ID,
        weekly_archive=weekly_archive,
        prepared_case=prepared_case,
    )


def write_genuine_daily_behavior_sequence_case(
    case: GenuineDailyBehaviorSequenceCase,
    path: str | Path,
) -> Path:
    if case.is_actionable:
        raise ValueError("genuine daily sequence research case cannot be actionable")
    return write_prepared_daily_behavior_sequence_case(
        case.prepared_case,
        path,
    )


__all__ = [
    "GENUINE_DAILY_SEQUENCE_GENERATOR_ID",
    "GenuineDailyBehaviorSequenceCase",
    "HistoricalProductionWeeklySetupArchive",
    "ProductionWeeklySourceFingerprint",
    "derive_historical_production_weekly_setups",
    "fingerprint_production_weekly_source",
    "prepare_genuine_daily_behavior_sequence_case",
    "write_genuine_daily_behavior_sequence_case",
]
