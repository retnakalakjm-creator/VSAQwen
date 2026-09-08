"""Command-line entry point for historical candidate outcome audits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit.runner import (
    DEFAULT_AUDIT_HORIZONS,
    DEFAULT_AUDIT_OUTPUT_DIR,
    run_historical_candidate_audit,
)
from audit.stability import DEFAULT_STABILITY_MIN_SAMPLES, DEFAULT_STABILITY_Z_SCORE


def build_parser() -> argparse.ArgumentParser:
    """Build the candidate audit command-line parser."""
    parser = argparse.ArgumentParser(
        description="Run a historical scanner candidate outcome audit.",
    )
    parser.add_argument(
        "symbols",
        nargs="+",
        help="Symbols to audit, for example SRF.NS RELIANCE.NS TCS.NS.",
    )
    parser.add_argument(
        "--horizons",
        nargs="+",
        type=int,
        default=list(DEFAULT_AUDIT_HORIZONS),
        help="Forward holding horizons in bars after the execution bar.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_AUDIT_OUTPUT_DIR,
        help="Directory for candidate_outcomes.csv and report CSVs.",
    )
    parser.add_argument(
        "--no-dataset",
        action="store_true",
        help="Do not write candidate_outcomes.csv.",
    )
    parser.add_argument(
        "--no-reports",
        action="store_true",
        help="Do not write calibration report CSVs.",
    )
    parser.add_argument(
        "--no-stability-reports",
        action="store_true",
        help="Do not write stability diagnostic CSVs inside the report bundle.",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=30,
        help="Minimum sample count for calibration report groups.",
    )
    parser.add_argument(
        "--stability-min-samples",
        type=int,
        default=DEFAULT_STABILITY_MIN_SAMPLES,
        help="Minimum sample count for stability diagnostic groups.",
    )
    parser.add_argument(
        "--stability-z-score",
        type=float,
        default=DEFAULT_STABILITY_Z_SCORE,
        help="Z-score used for stability confidence intervals.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=25,
        help="Number of top/bottom evidence groups to export.",
    )
    parser.add_argument(
        "--drop-unscored",
        action="store_true",
        help="Drop latest candidates that do not yet have an execution bar.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run the historical candidate audit CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    result = run_historical_candidate_audit(
        args.symbols,
        horizons=args.horizons,
        output_dir=args.output,
        write_dataset=not args.no_dataset,
        write_reports=not args.no_reports,
        report_min_samples=args.min_samples,
        report_top_n=args.top_n,
        include_stability_reports=not args.no_stability_reports,
        stability_min_samples=args.stability_min_samples,
        stability_z_score=args.stability_z_score,
        include_unscored=not args.drop_unscored,
    )
    print(json.dumps(result.summary(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
