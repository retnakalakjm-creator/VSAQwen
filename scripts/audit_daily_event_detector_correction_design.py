from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_event_detector_correction_design import (  # noqa: E402
    build_detector_correction_design_audit,
    write_detector_correction_design_audit,
)


def _default_output(semantics_dir: Path) -> Path:
    return (
        Path("reports/daily-events/detector-correction-design")
        / semantics_dir.name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build read-only detector correction candidates from canonical "
            "L3/L4B ledgers without changing production semantics."
        )
    )
    parser.add_argument("--semantics-dir", type=Path, required=True)
    parser.add_argument("--confirmation-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    audit = build_detector_correction_design_audit(
        semantics_dir=args.semantics_dir,
        confirmation_dir=args.confirmation_dir,
    )
    paths = write_detector_correction_design_audit(
        audit,
        args.output_dir or _default_output(args.semantics_dir),
    )

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "requested_symbol_count": audit.requested_symbol_count,
                "event_count": audit.event_count,
                "finding_count": audit.finding_count,
                "mandatory_collision_pair_count": (
                    audit.mandatory_collision_pair_count
                ),
                "gate_candidate_count": audit.gate_candidate_count,
                "collision_projection_row_count": (
                    audit.collision_projection_row_count
                ),
                "correction_candidate_count": (
                    audit.correction_candidate_count
                ),
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
