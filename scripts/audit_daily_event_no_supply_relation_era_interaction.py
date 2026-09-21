from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_event_no_supply_relation_era_interaction import (  # noqa: E402
    DEFAULT_INTERACTION_HORIZONS,
    build_no_supply_relation_era_interaction_audit,
    load_no_supply_relation_era_sources,
    write_no_supply_relation_era_interaction_audit,
)


def _default_output(context_dir: Path) -> Path:
    return (
        Path("reports/daily-events/no-supply-relation-era-interaction")
        / context_dir.name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate ALTERNATE NO_SUPPLY SAME_CLASS vs HIGHER_CLASS "
            "behavior across fixed eras and prior-vs-2023-2026."
        )
    )
    parser.add_argument("--context-dir", type=Path, required=True)
    parser.add_argument("--matched-dir", type=Path, required=True)
    parser.add_argument(
        "--horizons",
        nargs="+",
        type=int,
        default=list(DEFAULT_INTERACTION_HORIZONS),
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    sources = load_no_supply_relation_era_sources(
        context_dir=args.context_dir,
        matched_dir=args.matched_dir,
    )
    audit = build_no_supply_relation_era_interaction_audit(
        sources=sources,
        horizons=args.horizons,
    )
    paths = write_no_supply_relation_era_interaction_audit(
        audit,
        args.output_dir or _default_output(args.context_dir),
    )

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "requested_symbol_count": audit.requested_symbol_count,
                "alternate_target_count": audit.alternate_target_count,
                "same_class_target_count": audit.same_class_target_count,
                "higher_class_target_count": audit.higher_class_target_count,
                "prior_same_class_target_count": (
                    audit.prior_same_class_target_count
                ),
                "prior_higher_class_target_count": (
                    audit.prior_higher_class_target_count
                ),
                "latest_same_class_target_count": (
                    audit.latest_same_class_target_count
                ),
                "latest_higher_class_target_count": (
                    audit.latest_higher_class_target_count
                ),
                "era_count": audit.era_count,
                "relation_count": audit.relation_count,
                "horizon_count": audit.horizon_count,
                "horizons": list(audit.horizons),
                "era_relation_count_row_count": len(audit.count_rows),
                "era_relation_outcome_row_count": len(audit.outcome_rows),
                "relation_consistency_row_count": len(
                    audit.consistency_rows
                ),
                "prior_latest_row_count": len(audit.prior_latest_rows),
                "interaction_contrast_row_count": len(
                    audit.interaction_rows
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
