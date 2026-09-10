from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CORE_MODULE_PATH = ROOT / "vsa_audit_candidate_events.py"


def _load_candidate_summary_builder() -> Callable[[Any], Any]:
    """Load the root helper without importing this script by the same name."""
    spec = importlib.util.spec_from_file_location(
        "_vsa_audit_candidate_events_core",
        CORE_MODULE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"cannot load candidate event helper from {CORE_MODULE_PATH}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.build_audit_candidate_event_summary


build_audit_candidate_event_summary = _load_candidate_summary_builder()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build audit-only candidate events from saved /api/vsa-audit/events JSON."
        )
    )
    parser.add_argument(
        "audit_file",
        type=Path,
        help="Path to saved audit JSON. .txt files containing JSON are accepted.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Optional path to write the candidate-event summary JSON.",
    )
    parser.add_argument(
        "--min-priority",
        choices=("medium", "high"),
        default="medium",
        help="Filter emitted rows by minimum priority. Default: medium.",
    )
    args = parser.parse_args(argv)

    try:
        payload = _read_json(args.audit_file)
        summary = build_audit_candidate_event_summary(payload).to_dict()
        summary = _filter_by_priority(summary, args.min_priority)
        rendered = json.dumps(summary, indent=2, sort_keys=True)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.output is not None:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"audit file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _filter_by_priority(summary: dict[str, Any], min_priority: str) -> dict[str, Any]:
    if min_priority == "medium":
        return summary

    rows = [row for row in summary.get("rows", []) if row.get("priority") == "high"]
    return {
        **summary,
        "rows": rows,
        "candidate_counts": _count(row["candidate_code"] for row in rows),
        "family_counts": _count(row["candidate_family"] for row in rows),
        "priority_counts": _count(row["priority"] for row in rows),
        "symbol_counts": _count(row["symbol"] for row in rows),
    }


def _count(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


if __name__ == "__main__":
    raise SystemExit(main())
