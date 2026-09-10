from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CORE_MODULE_PATH = ROOT / "vsa_audit_candidate_triage.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_triage_helpers() -> tuple[Callable[..., Any], Callable[[Any], str]]:
    """Load the root helper without importing this script by the same name."""

    spec = importlib.util.spec_from_file_location(
        "_vsa_audit_candidate_triage_core",
        CORE_MODULE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load triage helper from {CORE_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.build_vsa_audit_candidate_triage, module.render_vsa_audit_candidate_triage_csv


build_vsa_audit_candidate_triage, render_vsa_audit_candidate_triage_csv = _load_triage_helpers()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Triage audit-only VSA candidate-event rows into cleaner review buckets."
        )
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help=(
            "Path to saved VSA audit, candidate-event, or batch-review JSON. "
            ".txt files containing JSON are accepted."
        ),
    )
    parser.add_argument(
        "--json-output",
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Optional path to write triage JSON.",
    )
    parser.add_argument(
        "--csv-output",
        type=Path,
        default=None,
        help="Optional path to write triage rows as CSV.",
    )
    parser.add_argument(
        "--min-priority",
        choices=("medium", "high"),
        default="high",
        help="Filter emitted candidate rows by minimum priority before triage. Default: high.",
    )
    args = parser.parse_args(argv)

    try:
        payload = _read_json(args.input_file)
        triage = build_vsa_audit_candidate_triage(
            payload,
            min_priority=args.min_priority,
        )
        triage_dict = triage.to_dict()
        rendered_json = json.dumps(triage_dict, indent=2, sort_keys=True)
        rendered_csv = render_vsa_audit_candidate_triage_csv(triage)
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
