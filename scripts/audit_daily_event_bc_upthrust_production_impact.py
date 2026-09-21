from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_event_bc_upthrust_production_impact import (  # noqa: E402
    build_bc_upthrust_production_impact_audit,
    write_bc_upthrust_production_impact_audit,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare canonical pre-change and post-change daily-event "
            "inventories for the promoted BUYING_CLIMAX / UPTHRUST "
            "production semantics."
        )
    )
    parser.add_argument("--before-dir", type=Path, required=True)
    parser.add_argument("--after-dir", type=Path, required=True)
    parser.add_argument("--semantic-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    audit = build_bc_upthrust_production_impact_audit(
        before_dir=args.before_dir,
        after_dir=args.after_dir,
        semantic_dir=args.semantic_dir,
    )
    paths = write_bc_upthrust_production_impact_audit(
        audit,
        args.output_dir,
    )

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "requested_symbol_count": audit.requested_symbol_count,
                "evaluated_bar_count": audit.evaluated_bar_count,
                "before_bc_count": audit.before_bc_count,
                "before_ut_count": audit.before_ut_count,
                "before_overlap_count": audit.before_overlap_count,
                "after_bc_count": audit.after_bc_count,
                "after_ut_count": audit.after_ut_count,
                "after_overlap_count": audit.after_overlap_count,
                "expected_bc_count": audit.expected_bc_count,
                "expected_ut_count": audit.expected_ut_count,
                "expected_overlap_count": audit.expected_overlap_count,
                "bc_candidate_identity_mismatch_count": (
                    audit.bc_candidate_identity_mismatch_count
                ),
                "ut_candidate_identity_mismatch_count": (
                    audit.ut_candidate_identity_mismatch_count
                ),
                "non_target_identity_drift_count": (
                    audit.non_target_identity_drift_count
                ),
                "unexpected_non_target_attribute_drift_count": (
                    audit.unexpected_non_target_attribute_drift_count
                ),
                "spring_conflict_quality_change_count": (
                    audit.spring_conflict_quality_change_count
                ),
                "non_target_emission_drift_count": (
                    audit.non_target_emission_drift_count
                ),
                "changed_event_group_count": (
                    audit.changed_event_group_count
                ),
                "increased_event_group_count": (
                    audit.increased_event_group_count
                ),
                "decreased_event_group_count": (
                    audit.decreased_event_group_count
                ),
                "total_before_event_contribution": (
                    audit.total_before_event_contribution
                ),
                "total_after_event_contribution": (
                    audit.total_after_event_contribution
                ),
                "total_event_contribution_delta": (
                    audit.total_event_contribution_delta
                ),
                "mean_absolute_changed_group_delta": (
                    audit.mean_absolute_changed_group_delta
                ),
                "max_absolute_changed_group_delta": (
                    audit.max_absolute_changed_group_delta
                ),
                "code_row_count": len(audit.code_rows),
                "pair_row_count": len(audit.pair_rows),
                "contribution_change_row_count": len(
                    audit.contribution_rows
                ),
                "symbol_impact_row_count": len(audit.symbol_rows),
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
