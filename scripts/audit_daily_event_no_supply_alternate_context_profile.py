from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_event_no_supply_alternate_context_profile import (  # noqa: E402
    build_candidate_contexts,
    build_no_supply_alternate_context_profile_audit,
    load_no_supply_alternate_context_sources,
    write_no_supply_alternate_context_profile_audit,
)
from vsa_standard_audit_basket import (  # noqa: E402
    STANDARD_VSA_AUDIT_BASKET_NAME,
    list_vsa_audit_basket_names,
)


def _default_output(temporal_dir: Path) -> Path:
    return (
        Path("reports/daily-events/no-supply-alternate-context-profile")
        / temporal_dir.name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Profile exact production-derived context for ALTERNATE/UP "
            "WEAK_RESULT_ONLY targets and compare 2023-2026 with prior history."
        )
    )
    parser.add_argument(
        "--basket",
        choices=list_vsa_audit_basket_names(),
        default=STANDARD_VSA_AUDIT_BASKET_NAME,
    )
    parser.add_argument("--temporal-dir", type=Path, required=True)
    parser.add_argument("--matched-dir", type=Path, required=True)
    parser.add_argument(
        "--input-snapshot-dir",
        type=Path,
        required=True,
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    sources = load_no_supply_alternate_context_sources(
        temporal_dir=args.temporal_dir,
        matched_dir=args.matched_dir,
        input_snapshot_dir=args.input_snapshot_dir,
        basket_name=args.basket,
    )
    contexts = build_candidate_contexts(
        sources=sources,
        input_snapshot_dir=args.input_snapshot_dir,
        progress_writer=lambda message: print(
            message,
            file=sys.stderr,
            flush=True,
        ),
    )
    audit = build_no_supply_alternate_context_profile_audit(
        sources=sources,
        contexts=contexts,
    )
    paths = write_no_supply_alternate_context_profile_audit(
        audit,
        contexts,
        args.output_dir or _default_output(args.temporal_dir),
    )

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "requested_symbol_count": audit.requested_symbol_count,
                "alternate_target_count": audit.alternate_target_count,
                "prior_target_count": audit.prior_target_count,
                "latest_target_count": audit.latest_target_count,
                "context_row_count": audit.context_row_count,
                "continuous_shift_row_count": len(
                    audit.continuous_shift_rows
                ),
                "categorical_shift_row_count": len(
                    audit.categorical_shift_rows
                ),
                "context_outcome_row_count": len(
                    audit.context_outcome_rows
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
