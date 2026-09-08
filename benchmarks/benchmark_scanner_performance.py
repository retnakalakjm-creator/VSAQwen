"""Benchmark current ProVSA production scanner performance.

This script is intentionally outside pytest. It measures the current scanner
pipeline before incremental trend/evidence internals are refactored.

Examples
--------
Run the requested one-symbol cache scenarios:

    python benchmarks/benchmark_scanner_performance.py --scenarios cold_1_symbol warm_1_symbol

Run full baseline with a real symbol universe file:

    python benchmarks/benchmark_scanner_performance.py --symbols-file symbols.txt

The symbol file should contain one ticker per line, for example ``SRF.NS``.
Use ``--allow-repeat`` only for smoke testing the benchmark harness; repeated
symbols do not represent real 100/500-symbol production throughput.
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import shutil
import sys
import tempfile
import time
import tracemalloc
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from itertools import cycle, islice
from pathlib import Path
from typing import Final

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data import CACHE_DIR, completed_weekly_only, daily_to_weekly, download_data
from metrics_engine import MetricsEngine
from production_scanner import scan_latest_candidate_production

DEFAULT_SYMBOL: Final = "SRF.NS"
DEFAULT_SCENARIOS: Final = (
    "cold_1_symbol",
    "warm_1_symbol",
    "scan_100_symbols",
    "scan_500_symbols",
)
SCENARIO_SIZES: Final = {
    "cold_1_symbol": 1,
    "warm_1_symbol": 1,
    "scan_100_symbols": 100,
    "scan_500_symbols": 500,
}
OUTPUT_DIR: Final = Path("benchmarks") / "results"
WARM_CACHE_MAX_AGE_SECONDS: Final = 10 * 365 * 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class SymbolScanResult:
    """One symbol scan result used to aggregate benchmark output."""

    symbol: str
    daily_bars: int
    weekly_bars: int
    candidate_count: int
    actionable_candidate_count: int


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Serializable benchmark result row."""

    scenario: str
    symbols: int
    total_daily_bars: int
    total_weekly_bars: int
    total_bars: int
    wall_time_seconds: float
    peak_memory_mb: float
    bars_per_second: float
    candidates: int
    actionable_candidates: int
    cold_cache: bool
    isolated_state: bool


def _read_symbols_file(path: Path) -> list[str]:
    symbols: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        symbol = line.strip().upper()
        if not symbol or symbol.startswith("#"):
            continue
        symbols.append(symbol)
    return symbols


def _unique_preserving_order(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value.strip().upper() for value in values if value.strip()))


def _select_symbols(
    symbols: Sequence[str],
    *,
    count: int,
    allow_repeat: bool,
) -> list[str]:
    if len(symbols) >= count:
        return list(symbols[:count])
    if not allow_repeat:
        raise ValueError(
            f"Need at least {count} unique symbols for this scenario; got {len(symbols)}. "
            "Pass --symbols-file with a larger universe, reduce --scenarios, "
            "or use --allow-repeat for smoke testing only."
        )
    return list(islice(cycle(symbols), count))


def _cache_paths(symbol: str) -> tuple[Path, ...]:
    return (
        CACHE_DIR / f"{symbol}.parquet",
        CACHE_DIR / f"{symbol}.csv",
        CACHE_DIR / f"{symbol}.metadata.json",
    )


def _clear_symbol_cache(symbol: str) -> None:
    for path in _cache_paths(symbol):
        path.unlink(missing_ok=True)


def _clear_state_root(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _scan_symbol(symbol: str, *, state_root: Path, cache_max_age: int) -> SymbolScanResult:
    daily = download_data(symbol, refresh=False, cache_max_age=cache_max_age)
    weekly = completed_weekly_only(daily_to_weekly(daily))
    metrics = MetricsEngine().calculate(weekly)
    candidate = scan_latest_candidate_production(
        metrics,
        symbol=symbol,
        state_root=state_root,
    )
    candidate_count = 0 if candidate is None else 1
    actionable_count = 1 if candidate is not None and candidate.actionable else 0
    return SymbolScanResult(
        symbol=symbol,
        daily_bars=len(daily),
        weekly_bars=len(metrics),
        candidate_count=candidate_count,
        actionable_candidate_count=actionable_count,
    )


def _measure_scenario(
    scenario: str,
    symbols: Sequence[str],
    *,
    state_root: Path,
    isolated_state: bool,
) -> BenchmarkResult:
    if isolated_state:
        _clear_state_root(state_root)

    cold_cache = scenario == "cold_1_symbol"
    if cold_cache:
        _clear_symbol_cache(symbols[0])

    cache_max_age = 0 if cold_cache else WARM_CACHE_MAX_AGE_SECONDS

    gc.collect()
    tracemalloc.start()
    started = time.perf_counter()
    scan_results = [
        _scan_symbol(symbol, state_root=state_root, cache_max_age=cache_max_age)
        for symbol in symbols
    ]
    wall_time = time.perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    total_daily_bars = sum(item.daily_bars for item in scan_results)
    total_weekly_bars = sum(item.weekly_bars for item in scan_results)
    total_bars = total_daily_bars + total_weekly_bars

    return BenchmarkResult(
        scenario=scenario,
        symbols=len(symbols),
        total_daily_bars=total_daily_bars,
        total_weekly_bars=total_weekly_bars,
        total_bars=total_bars,
        wall_time_seconds=wall_time,
        peak_memory_mb=peak_bytes / (1024 * 1024),
        bars_per_second=(total_bars / wall_time if wall_time > 0.0 else 0.0),
        candidates=sum(item.candidate_count for item in scan_results),
        actionable_candidates=sum(item.actionable_candidate_count for item in scan_results),
        cold_cache=cold_cache,
        isolated_state=isolated_state,
    )


def _write_json(results: Sequence[BenchmarkResult], path: Path) -> None:
    path.write_text(
        json.dumps([asdict(item) for item in results], indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _write_csv(results: Sequence[BenchmarkResult], path: Path) -> None:
    if not results:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for result in results:
            writer.writerow(asdict(result))


def _print_results(results: Sequence[BenchmarkResult]) -> None:
    headers = (
        "scenario",
        "symbols",
        "total_bars",
        "wall_time_seconds",
        "peak_memory_mb",
        "bars_per_second",
        "candidates",
        "actionable_candidates",
    )
    print(",".join(headers))
    for result in results:
        row = asdict(result)
        print(
            ",".join(
                str(round(row[item], 4)) if isinstance(row[item], float) else str(row[item])
                for item in headers
            )
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark current ProVSA production scanner performance."
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=[DEFAULT_SYMBOL],
        help="Symbols to scan when --symbols-file is not supplied.",
    )
    parser.add_argument(
        "--symbols-file",
        type=Path,
        help="Text file with one symbol per line. Required for realistic 100/500-symbol runs.",
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=DEFAULT_SCENARIOS,
        default=list(DEFAULT_SCENARIOS),
        help="Benchmark scenarios to execute.",
    )
    parser.add_argument(
        "--allow-repeat",
        action="store_true",
        help="Repeat supplied symbols to satisfy 100/500-symbol scenarios; smoke-test only.",
    )
    parser.add_argument(
        "--state-root",
        type=Path,
        default=None,
        help="Scanner state root. Defaults to a temporary directory.",
    )
    parser.add_argument(
        "--reuse-state",
        action="store_true",
        help="Reuse scanner state between scenarios instead of clearing it per scenario.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory for benchmark JSON and CSV results.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_symbols = (
        _read_symbols_file(args.symbols_file)
        if args.symbols_file is not None
        else _unique_preserving_order(args.symbols)
    )
    if not source_symbols:
        raise ValueError("At least one symbol is required")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")

    with tempfile.TemporaryDirectory(prefix="provsa-benchmark-state-") as temp_state:
        state_root = args.state_root if args.state_root is not None else Path(temp_state)
        state_root.mkdir(parents=True, exist_ok=True)

        results: list[BenchmarkResult] = []
        for scenario in args.scenarios:
            selected_symbols = _select_symbols(
                source_symbols,
                count=SCENARIO_SIZES[scenario],
                allow_repeat=args.allow_repeat,
            )
            results.append(
                _measure_scenario(
                    scenario,
                    selected_symbols,
                    state_root=state_root,
                    isolated_state=not args.reuse_state,
                )
            )

    json_path = args.output_dir / f"scanner_performance_{timestamp}.json"
    csv_path = args.output_dir / f"scanner_performance_{timestamp}.csv"
    _write_json(results, json_path)
    _write_csv(results, csv_path)
    _print_results(results)
    print(f"\nWrote {json_path}")
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
