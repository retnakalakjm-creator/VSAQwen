from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.nse_session_integrity import (  # noqa: E402
    DEFAULT_REFERENCE_PATH,
    run_nse_session_integrity_universe,
    write_nse_session_integrity_bundle,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit a frozen daily OHLCV snapshot against a bounded authoritative "
            "NSE cash-session exception reference."
        )
    )
    parser.add_argument(
        "--input-snapshot-dir",
        type=Path,
        required=True,
        help="Frozen daily OHLCV snapshot directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for session-integrity artifacts.",
    )
    parser.add_argument(
        "--reference-csv",
        type=Path,
        default=DEFAULT_REFERENCE_PATH,
        help="Bounded NSE cash-session exception reference.",
    )
    args = parser.parse_args(argv)

    try:
        audit = run_nse_session_integrity_universe(
            input_snapshot_dir=args.input_snapshot_dir,
            reference_path=args.reference_csv,
        )
        paths = write_nse_session_integrity_bundle(
            audit,
            output_dir=args.output_dir,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    payload = dict(audit.summary)
    payload["output_files"] = paths.as_dict()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
