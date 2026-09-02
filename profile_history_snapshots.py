from __future__ import annotations

import argparse

from benchmark_history_snapshots import make_inputs
from line_profiler import LineProfiler
from market_structure.professional_scorer import ProfessionalScorer


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Line-profile ProfessionalScorer history snapshot preparation."
    )
    parser.add_argument("--size", type=int, default=20_000)
    parser.add_argument("--lookback", type=int, default=10)
    args = parser.parse_args()

    if args.size <= 0 or args.lookback <= 0:
        raise SystemExit("--size and --lookback must be greater than zero")

    metrics, swings = make_inputs(args.size)
    scorer = ProfessionalScorer()
    arrays = scorer._metric_arrays(metrics)

    profiler = LineProfiler()
    profiler.add_function(ProfessionalScorer.prepare_history_snapshots)
    profiler.runcall(
        scorer.prepare_history_snapshots,
        swings,
        arrays,
        args.lookback,
    )
    profiler.print_stats()


if __name__ == "__main__":
    main()
