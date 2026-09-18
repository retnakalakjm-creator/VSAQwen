from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.frozen_daily_sequence_study import (  # noqa: E402
    FROZEN_DAILY_SEQUENCE_STUDY_RUNNER_ID,
    run_frozen_daily_sequence_study,
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


def _default_output(dataset_path: Path) -> Path:
    return Path("reports/daily-behavior-sequences/studies") / dataset_path.stem


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run one frozen K4 daily-sequence dataset through the unchanged "
            "K3/K2/K1 research stack."
        )
    )
    parser.add_argument(
        "dataset",
        type=Path,
        help="Path to a frozen K4 daily-sequence JSON dataset.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Study artifact directory. Defaults to "
            "reports/daily-behavior-sequences/studies/<dataset-stem>."
        ),
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
        help="Daily sequence evidence lookback. Default: 5.",
    )
    args = parser.parse_args(argv)

    if args.lookback_bars <= 0:
        parser.error("--lookback-bars must be positive")

    output_dir = args.output_dir or _default_output(args.dataset)

    try:
        result = run_frozen_daily_sequence_study(
            dataset_path=args.dataset,
            output_dir=output_dir,
            horizons_bars=args.horizons,
            lookback_bars=args.lookback_bars,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    study = result.study
    payload = {
        "runner_id": FROZEN_DAILY_SEQUENCE_STUDY_RUNNER_ID,
        "dataset_id": result.dataset.dataset_id,
        "symbols": list(study.successful_symbols),
        "input_fingerprints": [
            item.sha256
            for item in study.input_fingerprints
        ],
        "horizons_bars": list(study.horizons_bars),
        "lookback_bars": study.lookback_bars,
        "record_count": study.record_count,
        "fresh_sequence_count": study.fresh_sequence_count,
        "outcome_observation_count": study.outcome_observation_count,
        "signature_summary_count": len(study.summaries),
        "weekly_direction_assignment_counts": {
            "bullish": result.bullish_assignment_count,
            "bearish": result.bearish_assignment_count,
            "other": result.other_assignment_count,
        },
        "external_baseline_used": study.external_baseline_used,
        "output_files": result.paths.as_dict(),
        "is_actionable": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
