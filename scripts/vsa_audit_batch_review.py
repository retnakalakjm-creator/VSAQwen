from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CORE_MODULE_PATH = ROOT / "vsa_audit_batch_review.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_batch_review_helpers() -> tuple[Callable[..., Any], Callable[[Any], str]]:
    """Load the root helper without importing this script by the same name."""

    spec = importlib.util.spec_from_file_location(
        "_vsa_audit_batch_review_core",
        CORE_MODULE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load batch review helper from {CORE_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.build_vsa_audit_batch_review, module.render_vsa_audit_batch_review_csv


build_vsa_audit_batch_review, render_vsa_audit_batch_review_csv = _load_batch_review_helpers()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build audit-only basket review JSON/CSV from saved VSA audit "
            "or candidate-event JSON."
        )
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help=(
            "Path to saved /api/vsa-audit/events JSON or candidate-event JSON. "
            ".txt files containing JSON are accepted."
        ),
    )
    parser.add_argument(
        "--json-output",
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Optional path to write the batch review JSON.",
    )
    parser.add_argument(
        "--csv-output",
        type=Path,
        default=None,
        help="Optional path to write review rows as CSV.",
    )
    parser.add_argument(
        "--min-priority",
        choices=("medium", "high"),
        default="medium",
        help="Filter emitted review rows by minimum priority. Default: medium.",
    )
    args = parser.parse_args(argv)

    try:
        payload = _read_json(args.input_file)
        review = build_vsa_audit_batch_review(
            payload,
            min_priority=args.min_priority,
        )
        review_dict = review.to_dict()
        rendered_json = json.dumps(review_dict, indent=2, sort_keys=True)
        rendered_csv = render_vsa_audit_batch_review_csv(review)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json_output is not None:
        args.json_output.write_text(rendered_json + "\n", encoding="utf-8")
    if args.csv_output is not None:
        args.csv_output.write_text(rendered_csv, encoding="utf-8")
    if args.json_output is None and args.csv_output is None:
        print(rendered_json)
    return 0


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
