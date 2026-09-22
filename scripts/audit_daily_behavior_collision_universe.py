from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_behavior_collision_universe import (  # noqa: E402
    run_daily_behavior_collision_universe,
)


def _parse_horizons(value: str) -> tuple[int, ...]:
    try:
        result = tuple(
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
    if not result or any(item <= 0 for item in result):
        raise argparse.ArgumentTypeError("horizons must be positive integers")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the audit-only DailyBehavior evidence-identity collision study "
            "from a frozen daily OHLCV snapshot universe."
        )
    )
    parser.add_argument(
        "--input-snapshot-dir",
        type=Path,
        required=True,
        help="Frozen daily audit input snapshot directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for the collision study bundle.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Independent symbol workers. Default: 4.",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="Optional symbol subset for smoke validation.",
    )
    parser.add_argument(
        "--min-target-index",
        type=int,
        default=20,
        help="First daily target index for cached K5 evidence. Default: 20.",
    )
    parser.add_argument(
        "--horizons",
        type=_parse_horizons,
        default=(1, 3, 5, 10, 15),
        help="Comma-separated forward horizons. Default: 1,3,5,10,15.",
    )
    parser.add_argument(
        "--lookback-bars",
        type=int,
        default=5,
        help="Daily behavior sequence lookback. Default: 5.",
    )
    args = parser.parse_args(argv)

    if args.workers <= 0:
        parser.error("--workers must be positive")
    if args.min_target_index < 0:
        parser.error("--min-target-index cannot be negative")
    if args.lookback_bars <= 0:
        parser.error("--lookback-bars must be positive")

    try:
        result = run_daily_behavior_collision_universe(
            input_snapshot_dir=args.input_snapshot_dir,
            output_dir=args.output_dir,
            workers=args.workers,
            symbols=args.symbols,
            min_target_index=args.min_target_index,
            horizons_bars=args.horizons,
            lookback_bars=args.lookback_bars,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    payload = json.loads(result.summary_json.read_text(encoding="utf-8"))
    payload["output_files"] = {
        "universe_summary_json": str(result.summary_json),
        "universe_symbol_summary_csv": str(result.symbol_summary_csv),
        "universe_failures_csv": str(result.failures_csv),
    }
    if result.study_paths is not None:
        payload["output_files"].update(
            {
                f"study_{key}": value
                for key, value in result.study_paths.as_dict().items()
            }
        )

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.failed_symbol_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
