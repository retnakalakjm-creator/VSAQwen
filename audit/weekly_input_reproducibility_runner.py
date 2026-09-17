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
    run_weekly_foundation_historical_study,
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
    "ReproducibleWeeklyFoundationStudy",
    "WeeklyInputFingerprintBundlePaths",
    "run_reproducible_weekly_foundation_study",
    "write_weekly_input_fingerprint_bundle",
]
