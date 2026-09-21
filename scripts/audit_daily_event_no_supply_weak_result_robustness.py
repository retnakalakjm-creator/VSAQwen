from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_event_no_supply_forward_outcomes import (  # noqa: E402
    DEFAULT_FORWARD_HORIZONS,
)
from audit.daily_event_no_supply_weak_result_robustness import (  # noqa: E402
    DEFAULT_CLUSTER_BOOTSTRAP_ITERATIONS,
    DEFAULT_CLUSTER_BOOTSTRAP_SEED,
    build_no_supply_weak_result_robustness_audit,
    load_no_supply_weak_result_sources,
    write_no_supply_weak_result_robustness_audit,
)


def _default_output(confirmation_dir: Path) -> Path:
    return (
        Path("reports/daily-events/no-supply-weak-result-robustness")
        / confirmation_dir.name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate WEAK_RESULT_ONLY NO_SUPPLY matched lift with "
            "symbol-clustered bootstrap, leave-one-symbol-out checks, "
            "and direct predicate semantics."
        )
    )
    parser.add_argument(
        "--confirmation-dir",
        type=Path,
        required=True,
    )
    parser.add_argument("--matched-dir", type=Path, required=True)
    parser.add_argument(
        "--horizons",
        nargs="+",
        type=int,
        default=list(DEFAULT_FORWARD_HORIZONS),
    )
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=DEFAULT_CLUSTER_BOOTSTRAP_ITERATIONS,
    )
    parser.add_argument(
        "--bootstrap-seed",
        type=int,
        default=DEFAULT_CLUSTER_BOOTSTRAP_SEED,
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    sources = load_no_supply_weak_result_sources(
        confirmation_dir=args.confirmation_dir,
        matched_dir=args.matched_dir,
    )
    audit = build_no_supply_weak_result_robustness_audit(
        sources=sources,
        horizons=args.horizons,
        bootstrap_iterations=args.bootstrap_iterations,
        bootstrap_seed=args.bootstrap_seed,
    )
    paths = write_no_supply_weak_result_robustness_audit(
        audit,
        sources.targets,
        args.output_dir or _default_output(args.confirmation_dir),
    )

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "requested_symbol_count": audit.requested_symbol_count,
                "candidate_target_count": audit.candidate_target_count,
                "current_candidate_target_count": (
                    audit.current_candidate_target_count
                ),
                "alternate_candidate_target_count": (
                    audit.alternate_candidate_target_count
                ),
                "horizon_count": audit.horizon_count,
                "horizons": list(audit.horizons),
                "bootstrap_iterations": audit.bootstrap_iterations,
                "bootstrap_seed": audit.bootstrap_seed,
                "robustness_row_count": len(audit.robustness_rows),
                "bootstrap_row_count": len(audit.bootstrap_rows),
                "leave_one_out_row_count": len(
                    audit.leave_one_out_rows
                ),
                "semantic_row_count": len(audit.semantic_rows),
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
