from __future__ import annotations

import argparse
import cProfile
import pstats
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark_multi_symbol import prepare, scan_sequential
from market_structure.professional_scorer import ProfessionalScorer
from market_structure.structure_filter import StructureFilter


def _line_profile(datasets) -> None:
    from line_profiler import LineProfiler

    profiler = LineProfiler()
    profiler.add_function(StructureFilter.filter)
    profiler.add_function(ProfessionalScorer.score)
    profiler.add_function(ProfessionalScorer._build_context)
    profiler.add_function(ProfessionalScorer._history_snapshot)
    profiler.add_function(ProfessionalScorer._metric_arrays)
    profiler.add_function(ProfessionalScorer._metric_snapshot)
    profiler.add_function(ProfessionalScorer._smart_money_snapshot)
    profiler.add_function(ProfessionalScorer.prepare_history_snapshots)

    # Enable tracing around the real scanner path. This preserves the real
    # swing construction and call context while collecting line timings for
    # the registered target functions.
    profiler.enable()
    try:
        scan_sequential(datasets)
    finally:
        profiler.disable()

    profiler.print_stats()


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile multi-symbol scanner processing")
    parser.add_argument("--symbols", type=int, default=50)
    parser.add_argument("--daily-size", type=int, default=5000)
    parser.add_argument("--sort", default="cumtime")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument(
        "--line-profile",
        action="store_true",
        help="Run line_profiler on StructureFilter and ProfessionalScorer internals",
    )
    args = parser.parse_args()

    datasets = prepare(args.symbols, args.daily_size)

    if args.line_profile:
        _line_profile(datasets)
        return

    profiler = cProfile.Profile()
    profiler.enable()
    scan_sequential(datasets)
    profiler.disable()

    stats = pstats.Stats(profiler).strip_dirs().sort_stats(args.sort)
    stats.print_stats(args.limit)


if __name__ == "__main__":
    main()
