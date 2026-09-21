from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_event_inventory_replay_parity import (  # noqa: E402
    build_inventory_replay_parity_audit,
    write_inventory_replay_parity_audit,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare a cached daily-event inventory against the canonical "
            "legacy prefix-replay inventory on the same frozen snapshot."
        )
    )
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    audit = build_inventory_replay_parity_audit(
        reference_dir=args.reference_dir,
        candidate_dir=args.candidate_dir,
    )
    paths = write_inventory_replay_parity_audit(
        audit,
        args.output_dir,
    )

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "summary_equal": audit.summary_equal,
                "inventory_equal": audit.inventory_equal,
                "emissions_equal": audit.emissions_equal,
                "duplicates_equal": audit.duplicates_equal,
                "exact_match": audit.exact_match,
                "reference_evidence_emission_count": (
                    audit.reference_evidence_emission_count
                ),
                "candidate_evidence_emission_count": (
                    audit.candidate_evidence_emission_count
                ),
                "reference_event_bar_count": (
                    audit.reference_event_bar_count
                ),
                "candidate_event_bar_count": (
                    audit.candidate_event_bar_count
                ),
                "inventory_row_symmetric_difference_count": (
                    audit.inventory_row_symmetric_difference_count
                ),
                "emission_row_symmetric_difference_count": (
                    audit.emission_row_symmetric_difference_count
                ),
                "duplicate_row_symmetric_difference_count": (
                    audit.duplicate_row_symmetric_difference_count
                ),
                "source_lineage": asdict(audit.source_lineage),
                "output_files": paths.as_dict(),
                "is_actionable": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if audit.exact_match else 2


if __name__ == "__main__":
    raise SystemExit(main())
