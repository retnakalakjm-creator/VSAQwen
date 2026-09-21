from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_event_confirmation_semantics import (  # noqa: E402
    build_detector_confirmation_semantics_audit,
    write_detector_confirmation_semantics_audit,
)


def _default_output(input_dir: Path) -> Path:
    return (
        Path("reports/daily-events/confirmation-semantics")
        / input_dir.name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze detector-specific confirmation contracts and empirical "
            "patterns from a canonical L3 confirmation counterfactual."
        )
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    audit = build_detector_confirmation_semantics_audit(
        args.input_dir
    )
    paths = write_detector_confirmation_semantics_audit(
        audit,
        args.output_dir or _default_output(args.input_dir),
    )

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "requested_symbol_count": audit.requested_symbol_count,
                "detector_count": audit.detector_count,
                "event_count": audit.event_count,
                "contract_row_count": audit.contract_row_count,
                "confirmation_requirement_row_count": (
                    audit.confirmation_requirement_row_count
                ),
                "pattern_row_count": audit.pattern_row_count,
                "source_lineage": {
                    "l3_audit_id": audit.source_lineage.l3_audit_id,
                    "l3_summary_sha256": (
                        audit.source_lineage.l3_summary_sha256
                    ),
                    "l3_observations_sha256": (
                        audit.source_lineage.l3_observations_sha256
                    ),
                    "snapshot_manifest_sha256": (
                        audit.source_lineage.snapshot_manifest_sha256
                    ),
                    "l1_summary_sha256": (
                        audit.source_lineage.l1_summary_sha256
                    ),
                    "l1_emissions_sha256": (
                        audit.source_lineage.l1_emissions_sha256
                    ),
                    "l2_summary_sha256": (
                        audit.source_lineage.l2_summary_sha256
                    ),
                },
                "output_files": paths.as_dict(),
                "is_actionable": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
