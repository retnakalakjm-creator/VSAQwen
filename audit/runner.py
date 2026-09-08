"""Historical scanner audit runner for Milestone 3 validation.

This module connects the production full-replay scanner to the analysis-only
audit utilities. It builds candidate outcome datasets and, optionally, writes
calibration report bundles. It must not change production scanner decisions.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import pandas as pd

from audit.candidates import CandidateOutcomeRow, build_candidate_outcome_frame
from audit.reports import CalibrationReportPaths, write_calibration_report_bundle
from data import completed_weekly_only, daily_to_weekly, download_data
from metrics_engine import MetricsEngine
from scanner import ScannerEngine


DEFAULT_AUDIT_HORIZONS = (1, 2, 4, 8)
DEFAULT_AUDIT_OUTPUT_DIR = Path("reports/calibration/latest")
DEFAULT_DATASET_FILENAME = "candidate_outcomes.csv"
CANDIDATE_OUTCOME_COLUMNS = tuple(field.name for field in fields(CandidateOutcomeRow))

DailyLoader = Callable[[str], pd.DataFrame]
WeeklyTransformer = Callable[[pd.DataFrame], pd.DataFrame]
MetricsCalculator = Callable[[pd.DataFrame], pd.DataFrame]
ScannerFactory = Callable[[], Any]


@dataclass(frozen=True, slots=True)
class SymbolAuditResult:
    """Audit output for one symbol."""

    symbol: str
    daily_bars: int
    weekly_bars: int
    metric_bars: int
    candidate_count: int
    outcome_rows: int
    frame: pd.DataFrame


@dataclass(frozen=True, slots=True)
class HistoricalAuditResult:
    """Combined audit output for a symbol universe."""

    symbols: tuple[str, ...]
    horizons: tuple[int, ...]
    symbol_results: tuple[SymbolAuditResult, ...]
    frame: pd.DataFrame
    dataset_path: Path | None = None
    report_paths: CalibrationReportPaths | None = None

    @property
    def candidate_count(self) -> int:
        """Total candidates scanned across all symbols."""
        return sum(result.candidate_count for result in self.symbol_results)

    @property
    def outcome_rows(self) -> int:
        """Total candidate/horizon rows produced across all symbols."""
        return len(self.frame)

    def summary(self) -> dict[str, object]:
        """Return a compact JSON/log-friendly summary."""
        return {
            "symbols": list(self.symbols),
            "horizons": list(self.horizons),
            "symbol_count": len(self.symbols),
            "candidate_count": self.candidate_count,
            "outcome_rows": self.outcome_rows,
            "dataset_path": None if self.dataset_path is None else str(self.dataset_path),
            "report_paths": None if self.report_paths is None else self.report_paths.as_dict(),
        }


def run_symbol_candidate_audit(
    symbol: str,
    *,
    horizons: Iterable[int] = DEFAULT_AUDIT_HORIZONS,
    daily_loader: DailyLoader = download_data,
    weekly_transformer: WeeklyTransformer | None = None,
    metrics_calculator: MetricsCalculator | None = None,
    scanner_factory: ScannerFactory = ScannerEngine,
    include_unscored: bool = True,
) -> SymbolAuditResult:
    """Run a full historical candidate audit for one symbol.

    The default pipeline mirrors the full-replay scanner path:

    ``download_data -> daily_to_weekly -> completed_weekly_only -> MetricsEngine -> ScannerEngine.scan``

    Dependency injection keeps tests deterministic and lets future research use
    already-loaded bars without changing production modules.
    """
    normalized_symbol = _normalize_symbol(symbol)
    normalized_horizons = _normalize_horizons(horizons)

    transform = weekly_transformer or _default_weekly_transformer
    calculate_metrics = metrics_calculator or _default_metrics_calculator

    daily = daily_loader(normalized_symbol)
    weekly = transform(daily)
    metrics = calculate_metrics(weekly)
    candidates = list(scanner_factory().scan(metrics))
    frame = build_candidate_outcome_frame(
        metrics,
        candidates,
        horizons=normalized_horizons,
        symbol=normalized_symbol,
        include_unscored=include_unscored,
    )
    if frame.empty:
        frame = _empty_candidate_outcome_frame()

    return SymbolAuditResult(
        symbol=normalized_symbol,
        daily_bars=len(daily),
        weekly_bars=len(weekly),
        metric_bars=len(metrics),
        candidate_count=len(candidates),
        outcome_rows=len(frame),
        frame=frame,
    )


def run_historical_candidate_audit(
    symbols: Sequence[str] | Iterable[str],
    *,
    horizons: Iterable[int] = DEFAULT_AUDIT_HORIZONS,
    output_dir: str | Path | None = None,
    write_dataset: bool = True,
    write_reports: bool = True,
    report_min_samples: int = 30,
    report_top_n: int = 25,
    daily_loader: DailyLoader = download_data,
    weekly_transformer: WeeklyTransformer | None = None,
    metrics_calculator: MetricsCalculator | None = None,
    scanner_factory: ScannerFactory = ScannerEngine,
    include_unscored: bool = True,
) -> HistoricalAuditResult:
    """Run historical candidate audits for a symbol universe."""
    normalized_symbols = _normalize_symbols(symbols)
    normalized_horizons = _normalize_horizons(horizons)
    if report_min_samples <= 0:
        raise ValueError("report_min_samples must be greater than zero")
    if report_top_n <= 0:
        raise ValueError("report_top_n must be greater than zero")

    symbol_results = tuple(
        run_symbol_candidate_audit(
            symbol,
            horizons=normalized_horizons,
            daily_loader=daily_loader,
            weekly_transformer=weekly_transformer,
            metrics_calculator=metrics_calculator,
            scanner_factory=scanner_factory,
            include_unscored=include_unscored,
        )
        for symbol in normalized_symbols
    )
    frame = _combine_frames(result.frame for result in symbol_results)

    destination = None if output_dir is None else Path(output_dir)
    dataset_path: Path | None = None
    report_paths: CalibrationReportPaths | None = None

    if destination is not None and write_dataset:
        destination.mkdir(parents=True, exist_ok=True)
        dataset_path = destination / DEFAULT_DATASET_FILENAME
        frame.to_csv(dataset_path, index=False)

    if destination is not None and write_reports:
        report_paths = write_calibration_report_bundle(
            frame,
            destination,
            min_samples=report_min_samples,
            top_n=report_top_n,
        )

    return HistoricalAuditResult(
        symbols=normalized_symbols,
        horizons=normalized_horizons,
        symbol_results=symbol_results,
        frame=frame,
        dataset_path=dataset_path,
        report_paths=report_paths,
    )


def _default_weekly_transformer(daily: pd.DataFrame) -> pd.DataFrame:
    return completed_weekly_only(daily_to_weekly(daily))


def _default_metrics_calculator(weekly: pd.DataFrame) -> pd.DataFrame:
    return MetricsEngine().calculate(weekly)


def _combine_frames(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    materialized = [frame for frame in frames if not frame.empty]
    if not materialized:
        return _empty_candidate_outcome_frame()
    return pd.concat(materialized, ignore_index=True)


def _empty_candidate_outcome_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=CANDIDATE_OUTCOME_COLUMNS)


def _normalize_symbols(symbols: Sequence[str] | Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(_normalize_symbol(symbol) for symbol in symbols)
    if not normalized:
        raise ValueError("symbols must contain at least one symbol")
    if len(set(normalized)) != len(normalized):
        raise ValueError("symbols must be unique")
    return normalized


def _normalize_symbol(symbol: str) -> str:
    normalized = str(symbol).strip().upper()
    if not normalized:
        raise ValueError("symbol cannot be blank")
    return normalized


def _normalize_horizons(horizons: Iterable[int]) -> tuple[int, ...]:
    normalized = tuple(int(horizon) for horizon in horizons)
    if not normalized:
        raise ValueError("horizons must contain at least one value")
    if any(horizon <= 0 for horizon in normalized):
        raise ValueError("all horizons must be greater than zero")
    if len(set(normalized)) != len(normalized):
        raise ValueError("horizons must be unique")
    return normalized


__all__ = [
    "CANDIDATE_OUTCOME_COLUMNS",
    "DEFAULT_AUDIT_HORIZONS",
    "DEFAULT_AUDIT_OUTPUT_DIR",
    "DEFAULT_DATASET_FILENAME",
    "HistoricalAuditResult",
    "SymbolAuditResult",
    "run_historical_candidate_audit",
    "run_symbol_candidate_audit",
]
