from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.genuine_daily_sequence_case import (  # noqa: E402
    prepare_genuine_daily_behavior_sequence_case,
    write_genuine_daily_behavior_sequence_case,
)
from data import download_data, read_cache_metadata  # noqa: E402


def _default_output(symbol: str) -> Path:
    clean = symbol.strip().upper().replace(".", "_")
    return Path("reports/daily-behavior-sequences/genuine") / f"{clean}.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate one research-only frozen K4 daily sequence case from "
            "actual market data and production weekly scanner authority."
        )
    )
    parser.add_argument("symbol", help="Market-data symbol, for example LT.NS.")
    parser.add_argument(
        "--dataset-id",
        default=None,
        help="Frozen K4 dataset id. Defaults to genuine-<SYMBOL>.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Output JSON path. Defaults to "
            "reports/daily-behavior-sequences/genuine/<SYMBOL>.json"
        ),
    )
    parser.add_argument(
        "--now",
        required=True,
        help=(
            "Point-in-time cutoff, preferably timezone-aware, for example "
            "2026-09-18T16:00:00+05:30."
        ),
    )
    parser.add_argument(
        "--prepared-at-utc",
        default=None,
        help="Optional provenance timestamp. Defaults to current UTC.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh the configured read-only daily market-data cache first.",
    )
    args = parser.parse_args(argv)

    symbol = args.symbol.strip().upper()
    dataset_id = args.dataset_id or f"genuine-{symbol}"
    output = args.output or _default_output(symbol)
    prepared_at_utc = (
        args.prepared_at_utc
        or datetime.now(timezone.utc).isoformat()
    )

    try:
        daily = download_data(symbol, refresh=args.refresh)
        metadata = read_cache_metadata(symbol)
        source_reference = (
            f"market-data-cache:{symbol}:"
            f"{getattr(metadata, 'generation_id', None) or 'unknown-generation'}"
        )
        case = prepare_genuine_daily_behavior_sequence_case(
            dataset_id=dataset_id,
            symbol=symbol,
            daily=daily,
            source_reference=source_reference,
            prepared_at_utc=prepared_at_utc,
            now=args.now,
        )
        path = write_genuine_daily_behavior_sequence_case(case, output)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    summary = {
        "dataset_id": case.dataset.dataset_id,
        "symbol": case.symbol,
        "output": str(path),
        "daily_bar_count": len(case.study_input.bars),
        "daily_evidence_count": len(case.study_input.evidence),
        "weekly_direction_assignment_count": len(
            case.study_input.weekly_directions
        ),
        "production_weekly_candidate_count": (
            case.weekly_archive.candidate_count
        ),
        "production_weekly_setup_count": case.weekly_archive.setup_count,
        "production_weekly_source_fingerprint": (
            case.weekly_archive.source_fingerprint.sha256
        ),
        "k4_input_fingerprint": case.dataset.fingerprints[0].sha256,
        "is_actionable": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
