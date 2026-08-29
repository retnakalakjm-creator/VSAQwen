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
from market_structure.structural_swing_scorer import StructuralSwingScorer
from utils.ranking import percentile_rank_sorted
from utils.scoring import combine_scores, component, band_score


def _line_profile(datasets) -> None:
    from line_profiler import LineProfiler

    profiler = LineProfiler()
    profiler.add_function(StructureFilter.filter)
    profiler.add_function(ProfessionalScorer.score)
    profiler.add_function(ProfessionalScorer._build_context)
    profiler.add_function(ProfessionalScorer._metric_arrays)
    profiler.add_function(ProfessionalScorer._metric_snapshot)
    profiler.add_function(ProfessionalScorer._smart_money_snapshot)
    profiler.add_function(ProfessionalScorer.prepare_history_snapshots)
    profiler.add_function(StructuralSwingScorer.score)
    profiler.add_function(StructuralSwingScorer._percentile_score)
    profiler.add_function(StructuralSwingScorer._evaluate_amplitude)
    profiler.add_function(StructuralSwingScorer._evaluate_structural_size)
    profiler.add_function(StructuralSwingScorer._evaluate_duration)
    profiler.add_function(StructuralSwingScorer._evaluate_volume)
    profiler.add_function(StructuralSwingScorer._evaluate_spread)
    profiler.add_function(StructuralSwingScorer._combine_scores)
    profiler.add_function(combine_scores)
    profiler.add_function(component)
    profiler.add_function(band_score)
    profiler.add_function(percentile_rank_sorted)

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
