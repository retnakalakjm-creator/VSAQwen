from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_event_bc_upthrust_semantic_replay import (  # noqa: E402
    load_bc_upthrust_semantic_sources,
    run_bc_upthrust_semantic_replay,
    write_bc_upthrust_semantic_replay_audit,
)
from audit.offline_daily_evidence import (  # noqa: E402
    DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
)
from vsa_standard_audit_basket import (  # noqa: E402
    STANDARD_VSA_AUDIT_BASKET_NAME,
)


def _default_output(input_snapshot_dir: Path) -> Path:
    return (
        Path("reports/daily-events/bc-upthrust-semantic-replay")
        / input_snapshot_dir.parent.name
        / input_snapshot_dir.name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Causally replay the predeclared BUYING_CLIMAX acceptance "
            "geometry and UPTHRUST rejection semantics from frozen daily "
            "snapshots. No outcome analysis or production mutation."
        )
    )
    parser.add_argument("--confirmation-dir", type=Path, required=True)
    parser.add_argument("--input-snapshot-dir", type=Path, required=True)
    parser.add_argument("--now", required=True)
    parser.add_argument(
        "--basket",
        default=STANDARD_VSA_AUDIT_BASKET_NAME,
    )
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument(
        "--min-target-index",
        type=int,
        default=DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    sources = load_bc_upthrust_semantic_sources(
        confirmation_dir=args.confirmation_dir,
        input_snapshot_dir=args.input_snapshot_dir,
        basket_name=args.basket,
    )
    audit = run_bc_upthrust_semantic_replay(
        sources=sources,
        input_snapshot_dir=args.input_snapshot_dir,
        now=args.now,
        symbols=args.symbols,
        min_target_index=args.min_target_index,
        progress_writer=lambda message: print(
            message,
            file=sys.stderr,
            flush=True,
        ),
    )
    paths = write_bc_upthrust_semantic_replay_audit(
        audit,
        args.output_dir or _default_output(args.input_snapshot_dir),
    )

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "requested_symbol_count": audit.requested_symbol_count,
                "succeeded_symbol_count": audit.succeeded_symbol_count,
                "failed_symbol_count": audit.failed_symbol_count,
                "evaluated_target_count": audit.evaluated_target_count,
                "structural_reference_available_count": (
                    audit.structural_reference_available_count
                ),
                "baseline_bc_event_count": audit.baseline_bc_event_count,
                "replay_bc_event_count": audit.replay_bc_event_count,
                "bc_identity_mismatch_count": (
                    audit.bc_identity_mismatch_count
                ),
                "bc_effort_core_count": audit.bc_effort_core_count,
                "ut_local_rejection_count": (
                    audit.ut_local_rejection_count
                ),
                "ut_structural_rejection_count": (
                    audit.ut_structural_rejection_count
                ),
                "union_candidate_count": audit.union_candidate_count,
                "population_row_count": len(audit.population_rows),
                "bc_acceptance_row_count": len(audit.acceptance_rows),
                "descriptor_row_count": len(audit.descriptor_rows),
                "pairwise_row_count": len(audit.pairwise_rows),
                "symbol_row_count": len(audit.symbol_rows),
                "observation_row_count": len(audit.observations),
                "bc_parity_mismatch_row_count": len(
                    audit.bc_parity_mismatches
                ),
                "failure_row_count": len(audit.failures),
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
