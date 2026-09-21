from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_event_bc_upthrust_identity_separation import (  # noqa: E402
    build_bc_upthrust_identity_separation_audit,
    write_bc_upthrust_identity_separation_audit,
)


def _default_output(input_dir: Path) -> Path:
    return (
        Path("reports/daily-events/bc-upthrust-identity-separation")
        / input_dir.name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Measure the BUYING_CLIMAX vs UPTHRUST identity collision and "
            "apply only their unique confirmation clauses as a read-only "
            "counterfactual separation."
        )
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    audit = build_bc_upthrust_identity_separation_audit(args.input_dir)
    paths = write_bc_upthrust_identity_separation_audit(
        audit,
        args.output_dir or _default_output(args.input_dir),
    )

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "requested_symbol_count": audit.requested_symbol_count,
                "baseline_bc_event_count": audit.baseline_bc_event_count,
                "baseline_ut_event_count": audit.baseline_ut_event_count,
                "baseline_overlap_count": audit.baseline_overlap_count,
                "baseline_identical_firing_set": (
                    audit.baseline_identical_firing_set
                ),
                "shared_mandatory_contract": (
                    audit.shared_mandatory_contract
                ),
                "mandatory_requirement_count": (
                    audit.mandatory_requirement_count
                ),
                "shared_confirmation_count": audit.shared_confirmation_count,
                "bc_unique_confirmation": audit.bc_unique_confirmation,
                "ut_unique_confirmation": audit.ut_unique_confirmation,
                "bc_unique_gate_event_count": (
                    audit.bc_unique_gate_event_count
                ),
                "bc_unique_gate_survival_rate": (
                    audit.bc_unique_gate_survival_rate
                ),
                "ut_unique_gate_event_count": (
                    audit.ut_unique_gate_event_count
                ),
                "ut_unique_gate_survival_rate": (
                    audit.ut_unique_gate_survival_rate
                ),
                "unique_gate_overlap_count": audit.unique_gate_overlap_count,
                "unique_gate_union_count": audit.unique_gate_union_count,
                "unique_gate_jaccard": audit.unique_gate_jaccard,
                "unique_gate_identical_firing_set": (
                    audit.unique_gate_identical_firing_set
                ),
                "partition_row_count": len(audit.partition_rows),
                "symbol_row_count": len(audit.symbol_rows),
                "identity_row_count": len(audit.identity_rows),
                "source_lineage": asdict(audit.source_lineage),
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
