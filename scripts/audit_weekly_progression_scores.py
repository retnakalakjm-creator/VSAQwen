from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.weekly_progression_score_input_audit import (  # noqa: E402
    build_weekly_progression_score_input_audit,
    write_weekly_progression_score_input_audit,
)
from data import download_data  # noqa: E402


def _default_output(symbol: str) -> Path:
    clean = symbol.strip().upper().replace(".", "_")
    return (
        Path("reports/daily-behavior-sequences/weekly-progression-scores")
        / clean
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit structural-swing score windows behind production weekly "
            "progression events."
        )
    )
    parser.add_argument("symbol", help="Market-data symbol, for example LT.NS.")
    parser.add_argument(
        "--now",
        required=True,
        help="Point-in-time cutoff, preferably timezone-aware.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Output directory. Defaults to "
            "reports/daily-behavior-sequences/weekly-progression-scores/"
            "<SYMBOL>."
        ),
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh the configured read-only market-data cache first.",
    )
    args = parser.parse_args(argv)

    symbol = args.symbol.strip().upper()
    output_dir = args.output_dir or _default_output(symbol)

    try:
        daily = download_data(symbol, refresh=args.refresh)
        audit = build_weekly_progression_score_input_audit(
            symbol=symbol,
            daily=daily,
            now=args.now,
        )
        paths = write_weekly_progression_score_input_audit(
            audit,
            output_dir,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    payload = {
        "symbol": audit.symbol,
        "candidate_count": audit.candidate_count,
        "unique_structural_swing_count": audit.unique_structural_swing_count,
        "progression_event_count": audit.progression_event_count,
        "event_direction_counts": {
            "bullish": audit.bullish_event_count,
            "bearish": audit.bearish_event_count,
        },
        "production_weekly_source_fingerprint": (
            audit.source_fingerprint.sha256
        ),
        "output_files": paths.as_dict(),
        "is_actionable": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
