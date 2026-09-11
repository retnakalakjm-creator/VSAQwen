from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Sequence


MODULE_NAME = "_pro_vsa_recovery_sequence_validation_report"


def _ensure_repo_root_imports_first(repo_root: Path) -> None:
    """Prevent scripts/ wrappers from shadowing root helper modules."""

    repo_root_text = str(repo_root)
    sys.path[:] = [path for path in sys.path if path != repo_root_text]
    sys.path.insert(0, repo_root_text)


def _load_report_module() -> Any:
    repo_root = Path(__file__).resolve().parents[1]
    _ensure_repo_root_imports_first(repo_root)
    module_path = repo_root / "vsa_recovery_sequence_validation_report.py"
    spec = importlib.util.spec_from_file_location(MODULE_NAME, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load 6C validation report module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the saved-output-only Milestone 6C validation chain."
    )
    parser.add_argument("input_json", help="Path to saved audit/replay JSON")
    parser.add_argument("--report-output", help="Optional path for Markdown report output")
    parser.add_argument("--stage-seed-json-output", help="Optional path for stage-seed JSON output")
    parser.add_argument("--stage-seed-csv-output", help="Optional path for stage-seed CSV output")
    parser.add_argument("--casebook-json-output", help="Optional path for casebook JSON output")
    parser.add_argument("--casebook-csv-output", help="Optional path for casebook CSV output")
    parser.add_argument(
        "--label-firing-json-output",
        help="Optional path for label-firing audit JSON output",
    )
    parser.add_argument(
        "--label-firing-csv-output",
        help="Optional path for label-firing audit CSV output",
    )
    parser.add_argument(
        "--lookback-rows",
        type=int,
        default=3,
        help="Saved rows before a seed row to use for prior weakness/anchor context",
    )
    parser.add_argument(
        "--lookahead-rows",
        type=int,
        default=3,
        help="Saved rows after a seed row to use for Spring/Shakeout and demand follow-through",
    )
    parser.add_argument(
        "--production-only",
        action="store_true",
        help="Ignore diagnostic hint rows and seed only from production anchor/test codes",
    )
    parser.add_argument(
        "--skip-production-only-check",
        action="store_true",
        help="Do not include the separate production-only stage-seed comparison in the report",
    )
    return parser


def _write_json(path: str | None, payload: dict[str, Any]) -> None:
    if path:
        Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: str | None, text: str) -> None:
    if path:
        Path(path).write_text(text, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    module = _load_report_module()

    input_path = Path(args.input_json)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    artifacts = module.build_vsa_recovery_sequence_validation_artifacts(
        payload,
        lookback_rows=args.lookback_rows,
        lookahead_rows=args.lookahead_rows,
        include_diagnostic_hints=not args.production_only,
        include_production_only_stage_seed=not args.skip_production_only_check,
    )

    _write_text(args.report_output, artifacts.report_markdown)
    _write_json(args.stage_seed_json_output, artifacts.stage_seed_json)
    _write_text(args.stage_seed_csv_output, artifacts.stage_seed_csv)
    _write_json(args.casebook_json_output, artifacts.casebook_json)
    _write_text(args.casebook_csv_output, artifacts.casebook_csv)
    _write_json(args.label_firing_json_output, artifacts.label_firing_audit_json)
    _write_text(args.label_firing_csv_output, artifacts.label_firing_audit_csv)

    if not any(
        (
            args.report_output,
            args.stage_seed_json_output,
            args.stage_seed_csv_output,
            args.casebook_json_output,
            args.casebook_csv_output,
            args.label_firing_json_output,
            args.label_firing_csv_output,
        )
    ):
        print(artifacts.report_markdown)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
