from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Sequence


MODULE_NAME = "_pro_vsa_recovery_sequence_label_firing_audit"


def _load_audit_module() -> Any:
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "vsa_recovery_sequence_label_firing_audit.py"
    spec = importlib.util.spec_from_file_location(MODULE_NAME, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load label-firing audit module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize saved 6C recovery-sequence label-firing casebook rows."
    )
    parser.add_argument("input_json", help="Path to saved 6C recovery-sequence casebook JSON")
    parser.add_argument("--json-output", help="Optional path for JSON output")
    parser.add_argument("--csv-output", help="Optional path for CSV output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    module = _load_audit_module()

    input_path = Path(args.input_json)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    summary = module.build_vsa_recovery_sequence_label_firing_audit(payload)
    output_payload = summary.to_dict()

    json_text = json.dumps(output_payload, indent=2, sort_keys=True)
    if args.json_output:
        Path(args.json_output).write_text(json_text + "\n", encoding="utf-8")
    else:
        print(json_text)

    if args.csv_output:
        csv_text = module.render_vsa_recovery_sequence_label_firing_audit_csv(summary)
        Path(args.csv_output).write_text(csv_text, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
