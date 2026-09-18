from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.weekly_candidate_decision_audit import (  # noqa: E402
    build_weekly_candidate_decision_audit,
    write_weekly_candidate_decision_audit,
)
from data import download_data  # noqa: E402


def _default_output(symbol: str) -> Path:
    clean = symbol.strip().upper().replace(".", "_")
    return Path("reports/daily-behavior-sequences/weekly-candidates") / clean


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit all production weekly scanner candidate decisions before "
            "WeeklySetup materialization."
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
            "reports/daily-behavior-sequences/weekly-candidates/<SYMBOL>."
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
        audit = build_weekly_candidate_decision_audit(
            symbol=symbol,
            daily=daily,
            now=args.now,
        )
        paths = write_weekly_candidate_decision_audit(
            audit,
            output_dir,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    payload = {
        "symbol": audit.symbol,
        "candidate_count": audit.candidate_count,
        "qualification_counts": audit.qualification_counts,
        "actionable_counts": audit.actionable_counts,
        "materialized_setup_count": audit.materialized_setup_count,
        "materialized_direction_counts": audit.materialized_direction_counts,
        "signal_bar_anomaly_count": audit.signal_bar_anomaly_count,
        "fallback_evidence_count": audit.fallback_evidence_count,
        "persistent_bullish_reason_counts": (
            audit.persistent_bullish_reason_counts
        ),
        "persistent_bearish_reason_counts": (
            audit.persistent_bearish_reason_counts
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
