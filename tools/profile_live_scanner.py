from __future__ import annotations

import argparse
import cProfile
import pstats
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Profile the existing live scanner entry point."
    )
    parser.add_argument(
        "entrypoint",
        help="Python module:function to profile, e.g. live_scanner:scan_symbol",
    )
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--sort", default="cumulative")
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()

    if ":" not in args.entrypoint:
        parser.error("entrypoint must use module:function format")
    if args.limit <= 0:
        parser.error("--limit must be greater than zero")

    module_name, function_name = args.entrypoint.split(":", 1)
    if not module_name or not function_name:
        parser.error("entrypoint must use module:function format")

    module = __import__(module_name, fromlist=[function_name])
    function = getattr(module, function_name)

    profiler = cProfile.Profile()
    profiler.enable()
    if args.symbol is None:
        function()
    else:
        function(args.symbol)
    profiler.disable()

    stats = pstats.Stats(profiler).strip_dirs().sort_stats(args.sort)
    stats.print_stats(args.limit)


if __name__ == "__main__":
    main()
