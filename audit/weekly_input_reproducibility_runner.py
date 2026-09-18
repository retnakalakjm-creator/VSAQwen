"""WF7C0 reproducibility wrapper for weekly historical studies.

The wrapper captures a deterministic fingerprint of the exact completed-week
OHLCV frame passed into MetricsEngine for every symbol in the run.  It remains
analysis-only and does not alter production scanner behavior.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from audit.weekly_foundation_runner import (
    DEFAULT_STUDY_HORIZONS,
    WeeklyFoundationStudyResult,
    WeeklyFoundationSymbolStudy,
    run_weekly_foundation_historical_study,
    run_weekly_foundation_symbol_study,
)
from data import completed_weekly_only, daily_to_weekly, download_data
from historical_scanner import HistoricalScannerRunner
from metrics_engine import MetricsEngine
from weekly_audit_input_reproducibility import (
    WeeklyAuditInputFingerprint,
    fingerprint_weekly_audit_input,
)


DEFAULT_WF7C0_OUTPUT_DIR = Path("reports/weekly-foundation/wf7c0-latest")

DailyLoader = Callable[[str], pd.DataFrame]
MetricsCalculator = Callable[[pd.DataFrame], pd.DataFrame]
ScannerFactory = Callable[[], Any]


@dataclass(frozen=True, slots=True)
class ReproducibleWeeklyFoundationStudy:
    foundation: WeeklyFoundationStudyResult
    input_fingerprints: tuple[WeeklyAuditInputFingerprint, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ReproducibleWeeklyFoundationSymbolSnapshot:
    """One frozen symbol result plus the exact weekly input fingerprint used."""

    foundation: WeeklyFoundationSymbolStudy
    input_fingerprint: WeeklyAuditInputFingerprint
    horizons_weeks: tuple[int, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ReproducibleWeeklyFoundationSnapshot:
    """Frozen multi-symbol WF7 input without rerunning WF1-WF6 or market data."""

    symbols: tuple[str, ...]
    horizons_weeks: tuple[int, ...]
    symbol_results: tuple[WeeklyFoundationSymbolStudy, ...]
    input_fingerprints: tuple[WeeklyAuditInputFingerprint, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class WeeklyInputFingerprintBundlePaths:
    manifest_json: Path
    manifest_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "manifest_json": str(self.manifest_json),
            "manifest_csv": str(self.manifest_csv),
        }


def _default_weekly_transformer(daily: pd.DataFrame) -> pd.DataFrame:
    return completed_weekly_only(daily_to_weekly(daily))


def _default_metrics_calculator(weekly: pd.DataFrame) -> pd.DataFrame:
    return MetricsEngine().calculate(weekly)


def _normalize_horizons(horizons_weeks: Iterable[int]) -> tuple[int, ...]:
    horizons = tuple(sorted(set(int(item) for item in horizons_weeks)))
    if not horizons or any(item <= 0 for item in horizons):
        raise ValueError("horizons must contain positive week counts")
    return horizons


def run_reproducible_weekly_foundation_symbol_snapshot(
    symbol: str,
    *,
    horizons_weeks: Iterable[int] = DEFAULT_STUDY_HORIZONS,
    out_of_sample_start_week: str | None = None,
    daily_loader: DailyLoader = download_data,
    metrics_calculator: MetricsCalculator = _default_metrics_calculator,
    scanner_factory: ScannerFactory = HistoricalScannerRunner,
) -> ReproducibleWeeklyFoundationSymbolSnapshot:
    """Run one symbol once and retain the exact read-only historical result.

    WF7C2 uses this frozen object for both its preflight fingerprint contract and
    the later aggregate WF7C1 analysis.  This prevents a second market-data
    refresh/cache round-trip from changing exact floating-point fingerprints and
    avoids repeating the expensive historical scanner pass.
    """

    normalized_symbol = str(symbol).strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol cannot be blank")
    horizons = _normalize_horizons(horizons_weeks)
    captured: WeeklyAuditInputFingerprint | None = None

    def capturing_weekly_transformer(daily: pd.DataFrame) -> pd.DataFrame:
        nonlocal captured
        weekly = _default_weekly_transformer(daily)
        if captured is not None:
            raise RuntimeError(
                f"weekly input captured more than once for {normalized_symbol}"
            )
        captured = fingerprint_weekly_audit_input(normalized_symbol, weekly)
        return weekly

    foundation = run_weekly_foundation_symbol_study(
        normalized_symbol,
        horizons_weeks=horizons,
        out_of_sample_start_week=out_of_sample_start_week,
        daily_loader=daily_loader,
        weekly_transformer=capturing_weekly_transformer,
        metrics_calculator=metrics_calculator,
        scanner_factory=scanner_factory,
    )
    if captured is None:
        raise RuntimeError(f"did not capture completed weekly input for {normalized_symbol}")
    if foundation.symbol != normalized_symbol or captured.symbol != normalized_symbol:
        raise RuntimeError("frozen symbol snapshot identity mismatch")

    return ReproducibleWeeklyFoundationSymbolSnapshot(
        foundation=foundation,
        input_fingerprint=captured,
        horizons_weeks=horizons,
    )


def combine_reproducible_weekly_foundation_snapshots(
    snapshots: Sequence[ReproducibleWeeklyFoundationSymbolSnapshot]
    | Iterable[ReproducibleWeeklyFoundationSymbolSnapshot],
) -> ReproducibleWeeklyFoundationSnapshot:
    """Combine already-frozen symbol results without recalculating market history."""

    items = tuple(snapshots)
    if not items:
        raise ValueError("at least one frozen weekly foundation snapshot is required")

    horizons = items[0].horizons_weeks
    symbols = tuple(item.foundation.symbol for item in items)
    if len(set(symbols)) != len(symbols):
        raise ValueError("frozen weekly foundation snapshots require unique symbols")
    if any(item.horizons_weeks != horizons for item in items):
        raise ValueError("frozen weekly foundation snapshots require identical horizons")
    if any(item.input_fingerprint.symbol != item.foundation.symbol for item in items):
        raise ValueError("frozen weekly foundation fingerprint symbol mismatch")

    return ReproducibleWeeklyFoundationSnapshot(
        symbols=symbols,
        horizons_weeks=horizons,
        symbol_results=tuple(item.foundation for item in items),
        input_fingerprints=tuple(item.input_fingerprint for item in items),
    )


def run_reproducible_weekly_foundation_study(
    symbols: Sequence[str] | Iterable[str],
    *,
    horizons_weeks: Iterable[int] = DEFAULT_STUDY_HORIZONS,
    location_distance_thresholds_pct: Iterable[float] = (),
    out_of_sample_start_week: str | None = None,
    daily_loader: DailyLoader = download_data,
    metrics_calculator: MetricsCalculator = _default_metrics_calculator,
    scanner_factory: ScannerFactory = HistoricalScannerRunner,
) -> ReproducibleWeeklyFoundationStudy:
    """Run the foundation study and capture the exact weekly input per symbol.

    The capture happens inside the same weekly-transform callback consumed by
    the existing historical runner, so the fingerprint identifies the exact
    completed weekly frame used by MetricsEngine rather than a separately
    re-downloaded or reconstructed frame.
    """

    fingerprints: dict[str, WeeklyAuditInputFingerprint] = {}
    active_symbol: str | None = None

    def capturing_daily_loader(symbol: str) -> pd.DataFrame:
        nonlocal active_symbol
        active_symbol = str(symbol).strip().upper()
        return daily_loader(symbol)

    def capturing_weekly_transformer(daily: pd.DataFrame) -> pd.DataFrame:
        if active_symbol is None:
            raise RuntimeError("weekly transform invoked before symbol loader")
        weekly = _default_weekly_transformer(daily)
        if active_symbol in fingerprints:
            raise RuntimeError(f"weekly input captured more than once for {active_symbol}")
        fingerprints[active_symbol] = fingerprint_weekly_audit_input(active_symbol, weekly)
        return weekly

    foundation = run_weekly_foundation_historical_study(
        symbols,
        horizons_weeks=horizons_weeks,
        location_distance_thresholds_pct=location_distance_thresholds_pct,
        out_of_sample_start_week=out_of_sample_start_week,
        daily_loader=capturing_daily_loader,
        weekly_transformer=capturing_weekly_transformer,
        metrics_calculator=metrics_calculator,
        scanner_factory=scanner_factory,
    )

    ordered = tuple(fingerprints[symbol] for symbol in foundation.symbols)
    if len(ordered) != len(foundation.symbols):
        raise RuntimeError("did not capture every symbol's completed weekly input")

    return ReproducibleWeeklyFoundationStudy(
        foundation=foundation,
        input_fingerprints=ordered,
    )


def write_weekly_input_fingerprint_bundle(
    study: ReproducibleWeeklyFoundationStudy,
    output_dir: str | Path = DEFAULT_WF7C0_OUTPUT_DIR,
) -> WeeklyInputFingerprintBundlePaths:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths = WeeklyInputFingerprintBundlePaths(
        manifest_json=destination / "weekly_input_fingerprints.json",
        manifest_csv=destination / "weekly_input_fingerprints.csv",
    )

    records = [asdict(item) for item in study.input_fingerprints]
    payload = {
        "symbols": list(study.foundation.symbols),
        "symbol_count": len(study.foundation.symbols),
        "audited_bars": study.foundation.audited_bars,
        "is_actionable": False,
        "fingerprints": records,
    }
    paths.manifest_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    pd.DataFrame(records).to_csv(paths.manifest_csv, index=False)
    return paths


def _parse_csv_strings(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item) for item in _parse_csv_strings(value))


def _parse_csv_floats(value: str) -> tuple[float, ...]:
    return tuple(float(item) for item in _parse_csv_strings(value))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the weekly foundation audit with exact input fingerprints."
    )
    parser.add_argument("--symbols", required=True, help="Comma-separated symbols.")
    parser.add_argument("--horizons", default="5,10,15")
    parser.add_argument("--out-of-sample-start-week", default=None)
    parser.add_argument("--location-thresholds-pct", default="")
    parser.add_argument("--output-dir", default=str(DEFAULT_WF7C0_OUTPUT_DIR))
    args = parser.parse_args(argv)

    study = run_reproducible_weekly_foundation_study(
        _parse_csv_strings(args.symbols),
        horizons_weeks=_parse_csv_ints(args.horizons),
        location_distance_thresholds_pct=_parse_csv_floats(args.location_thresholds_pct),
        out_of_sample_start_week=args.out_of_sample_start_week,
    )
    paths = write_weekly_input_fingerprint_bundle(study, args.output_dir)
    print(
        json.dumps(
            {
                "symbols": list(study.foundation.symbols),
                "symbol_count": len(study.foundation.symbols),
                "audited_bars": study.foundation.audited_bars,
                "is_actionable": False,
                "output_paths": paths.as_dict(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_WF7C0_OUTPUT_DIR",
    "ReproducibleWeeklyFoundationSnapshot",
    "ReproducibleWeeklyFoundationStudy",
    "ReproducibleWeeklyFoundationSymbolSnapshot",
    "combine_reproducible_weekly_foundation_snapshots",
    "run_reproducible_weekly_foundation_symbol_snapshot",
    "WeeklyInputFingerprintBundlePaths",
    "run_reproducible_weekly_foundation_study",
    "write_weekly_input_fingerprint_bundle",
]
