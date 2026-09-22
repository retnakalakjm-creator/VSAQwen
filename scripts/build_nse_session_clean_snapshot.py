from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.nse_session_clean_snapshot import (  # noqa: E402
    build_nse_session_clean_snapshot,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the immutable NSE-session-clean v2 snapshot from the exact "
            "frozen 30-symbol baseline and official NSE bhavcopy files."
        )
    )
    parser.add_argument(
        "--input-snapshot-dir",
        type=Path,
        required=True,
        help="Exact frozen 30-symbol baseline snapshot directory.",
    )
    parser.add_argument(
        "--bhavcopy",
        type=Path,
        nargs="+",
        required=True,
        help=(
            "Ten official NSE CM bhavcopy CSV/ZIP files: the five missing "
            "special sessions plus calibration sessions 2023-11-10, "
            "2024-01-19, 2024-03-01, 2024-05-17 and 2026-01-30."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="New immutable output snapshot directory.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly replace an existing v2 output bundle.",
    )
    args = parser.parse_args(argv)

    try:
        result = build_nse_session_clean_snapshot(
            input_snapshot_dir=args.input_snapshot_dir,
            official_bhavcopy_paths=args.bhavcopy,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "version": "nse-session-clean-v2",
                "is_actionable": False,
                "baseline_manifest_sha256": result.baseline_manifest_sha256,
                "output_manifest_sha256": result.output_manifest_sha256,
                "symbol_count": result.symbol_count,
                "removed_row_count": result.removed_row_count,
                "added_row_count": result.added_row_count,
                "net_row_change": result.added_row_count - result.removed_row_count,
                "output_dir": str(result.output_dir),
                "manifest_json": str(result.manifest_json),
                "repairs_csv": str(result.repairs_csv),
                "source_files_csv": str(result.source_files_csv),
                "production_calendar_change_authorized": False,
                "downstream_rerun_authorized": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
