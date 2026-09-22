from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_behavior_collision_outcomes import (  # noqa: E402
    run_daily_behavior_collision_outcome_analysis,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Post-process an existing DailyBehavior collision study bundle "
            "without replaying detectors or market data."
        )
    )
    parser.add_argument(
        "--study-dir",
        type=Path,
        required=True,
        help="Existing directory containing daily_sequence_*.csv artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for CSV-only collision/outcome analysis outputs.",
    )
    parser.add_argument(
        "--min-complete-per-variant",
        type=int,
        default=20,
        help=(
            "Minimum complete forward outcomes required per exact evidence "
            "variant for within-coarse comparisons. Default: 20."
        ),
    )
    args = parser.parse_args(argv)

    if args.min_complete_per_variant <= 0:
        parser.error("--min-complete-per-variant must be positive")

    try:
        paths = run_daily_behavior_collision_outcome_analysis(
            study_dir=args.study_dir,
            output_dir=args.output_dir,
            min_complete_per_variant=args.min_complete_per_variant,
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
