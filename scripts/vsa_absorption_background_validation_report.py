from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Sequence


MODULE_NAME = "_pro_vsa_absorption_background_validation_report"


def _load_report_module() -> Any:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    module_path = repo_root / "vsa_absorption_background_validation_report.py"
    spec = importlib.util.spec_from_file_location(MODULE_NAME, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load 6D validation report module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the saved-output 6D absorption-background validation report."
    )
    parser.add_argument("input_json", help="Path to saved audit/replay JSON")
    parser.add_argument("--json-output", help="Optional path for validation summary JSON")
    parser.add_argument("--report-output", help="Optional path for Markdown report output")
    parser.add_argument("--casebook-json-output", help="Optional path for casebook JSON output")
    parser.add_argument("--casebook-csv-output", help="Optional path for casebook CSV output")
    parser.add_argument(
        "--lookback-rows",
        type=int,
        default=3,
        help="Saved rows before a seed row to use for prior supply context",
    )
    parser.add_argument(
        "--lookahead-rows",
        type=int,
        default=3,
        help="Saved rows after a seed row to use for demand/reversal follow-through",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    module = _load_report_module()

    input_path = Path(args.input_json)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    report = module.build_vsa_absorption_background_validation_report(
        payload,
        lookback_rows=args.lookback_rows,
        lookahead_rows=args.lookahead_rows,
    )
    output_payload = report.to_dict()

    if args.json_output:
        Path(args.json_output).write_text(
            json.dumps(output_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if args.report_output:
        Path(args.report_output).write_text(
            module.render_vsa_absorption_background_validation_report_markdown(report),
            encoding="utf-8",
        )

    if args.casebook_json_output:
        Path(args.casebook_json_output).write_text(
            json.dumps(report.casebook_summary.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if args.casebook_csv_output:
        Path(args.casebook_csv_output).write_text(
            module.render_vsa_absorption_background_validation_casebook_csv(report),
            encoding="utf-8",
        )

    if not any(
        (
            args.json_output,
            args.report_output,
            args.casebook_json_output,
            args.casebook_csv_output,
        )
    ):
        print(json.dumps(output_payload, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
