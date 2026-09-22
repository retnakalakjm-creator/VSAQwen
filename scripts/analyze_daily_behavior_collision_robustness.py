from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_behavior_collision_robustness import (  # noqa: E402
    run_daily_behavior_collision_robustness,
)


def _parse_horizons(value: str) -> tuple[int, ...]:
    try:
        horizons = tuple(
            sorted(
                {
                    int(item.strip())
                    for item in value.split(",")
                    if item.strip()
                }
            )
        )
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "horizons must be comma-separated integers"
        ) from exc

    if not horizons or any(item <= 0 for item in horizons):
        raise argparse.ArgumentTypeError("horizons must be positive integers")
    return horizons


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run CSV-only robustness checks for broad DailyBehavior "
            "evidence-identity contrasts."
        )
    )
    parser.add_argument(
        "--raw-outcomes-csv",
        type=Path,
        required=True,
        help="Existing #365 daily_sequence_outcomes.csv.",
    )
    parser.add_argument(
        "--pairwise-contrasts-csv",
        type=Path,
        required=True,
        help="Existing #366 within-coarse pairwise contrasts CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for robustness outputs.",
    )
    parser.add_argument(
        "--horizons",
        type=_parse_horizons,
        default=(1, 3, 5, 10, 15),
        help="Comma-separated forward horizons. Default: 1,3,5,10,15.",
    )
    parser.add_argument(
        "--min-complete-per-variant",
        type=int,
        default=100,
        help="Minimum complete outcomes per variant at every horizon.",
    )
    parser.add_argument(
        "--min-symbols-per-variant",
        type=int,
        default=20,
        help="Minimum symbol breadth per variant at every horizon.",
    )
    parser.add_argument(
        "--max-time-gap-bars",
        type=int,
        default=20,
        help="Maximum within-symbol signal-index gap for nearest-time matching.",
    )
    args = parser.parse_args(argv)

    if args.min_complete_per_variant <= 0:
        parser.error("--min-complete-per-variant must be positive")
    if args.min_symbols_per_variant <= 0:
        parser.error("--min-symbols-per-variant must be positive")
    if args.max_time_gap_bars < 0:
        parser.error("--max-time-gap-bars cannot be negative")

    try:
        paths = run_daily_behavior_collision_robustness(
            raw_outcomes_csv=args.raw_outcomes_csv,
            pairwise_contrasts_csv=args.pairwise_contrasts_csv,
            output_dir=args.output_dir,
            horizons=args.horizons,
            min_complete_per_variant=args.min_complete_per_variant,
            min_symbols_per_variant=args.min_symbols_per_variant,
            max_time_gap_bars=args.max_time_gap_bars,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    summary["output_files"] = paths.as_dict()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
