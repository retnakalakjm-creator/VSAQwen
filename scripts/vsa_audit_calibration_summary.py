from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vsa_audit_calibration import build_effort_absorption_calibration_summary


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert /api/vsa-audit/events JSON into an audit-only "
            "Effort-vs-Result / absorption calibration summary."
        )
    )
    parser.add_argument(
        "audit_json",
        type=Path,
        help="Path to a saved VSA audit JSON file, including .txt files containing JSON.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Optional path to write the summary JSON. Defaults to stdout.",
    )
    return parser.parse_args(argv)


def load_audit_payload(path: Path) -> Any:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(f"audit file not found: {path}") from exc
    except OSError as exc:
        raise SystemExit(f"unable to read audit file {path}: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"audit file is not valid JSON: {path}: {exc}") from exc


def render_summary(payload: Any) -> str:
    summary = build_effort_absorption_calibration_summary(payload)
    return json.dumps(summary.to_dict(), indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    summary_json = render_summary(load_audit_payload(args.audit_json))

    if args.output is not None:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(summary_json + "\n", encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"unable to write summary file {args.output}: {exc}") from exc
    else:
        print(summary_json)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
