from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.weekly_structural_progression_audit import (  # noqa: E402
    build_weekly_structural_progression_audit,
    write_weekly_structural_progression_audit,
)
from data import download_data  # noqa: E402


def _default_output(symbol: str) -> Path:
    clean = symbol.strip().upper().replace(".", "_")
    return Path("reports/daily-behavior-sequences/weekly-progression") / clean


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit raw production weekly structural-progression events feeding "
            "PatternQualificationEngine."
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
            "reports/daily-behavior-sequences/weekly-progression/<SYMBOL>."
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
        audit = build_weekly_structural_progression_audit(
            symbol=symbol,
            daily=daily,
            now=args.now,
        )
        paths = write_weekly_structural_progression_audit(
            audit,
            output_dir,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    payload = {
        "symbol": audit.symbol,
        "candidate_count": audit.candidate_count,
        "event_count": audit.event_count,
        "event_direction_counts": {
            "bullish": audit.improving_event_count,
            "bearish": audit.weakening_event_count,
        },
        "first_improving_week": audit.first_improving_week,
        "last_improving_week": audit.last_improving_week,
        "first_weakening_week": audit.first_weakening_week,
        "last_weakening_week": audit.last_weakening_week,
        "first_persistent_bullish_week": (
            audit.first_persistent_bullish_week
        ),
        "first_persistent_bearish_week": (
            audit.first_persistent_bearish_week
        ),
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
