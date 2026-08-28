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


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile multi-symbol scanner processing")
    parser.add_argument("--symbols", type=int, default=50)
    parser.add_argument("--daily-size", type=int, default=5000)
    parser.add_argument("--sort", default="cumtime")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    datasets = prepare(args.symbols, args.daily_size)
    profiler = cProfile.Profile()
    profiler.enable()
    scan_sequential(datasets)
    profiler.disable()

    stats = pstats.Stats(profiler).strip_dirs().sort_stats(args.sort)
    stats.print_stats(args.limit)


if __name__ == "__main__":
    main()
