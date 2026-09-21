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
from audit.daily_event_no_supply_temporal_stability import (  # noqa: E402
    build_no_supply_temporal_stability_audit,
    load_no_supply_temporal_sources,
    write_no_supply_temporal_stability_audit,
)


def _default_output(robustness_dir: Path) -> Path:
    return (
        Path("reports/daily-events/no-supply-temporal-stability")
        / robustness_dir.name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate WEAK_RESULT_ONLY NO_SUPPLY matched behavior across "
            "fixed historical eras and leave-one-era-out return checks."
        )
    )
    parser.add_argument("--robustness-dir", type=Path, required=True)
    parser.add_argument("--matched-dir", type=Path, required=True)
    parser.add_argument(
        "--horizons",
        nargs="+",
        type=int,
        default=list(DEFAULT_FORWARD_HORIZONS),
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    sources = load_no_supply_temporal_sources(
        robustness_dir=args.robustness_dir,
        matched_dir=args.matched_dir,
    )
    audit = build_no_supply_temporal_stability_audit(
        sources=sources,
        horizons=args.horizons,
    )
    paths = write_no_supply_temporal_stability_audit(
        audit,
        sources.targets,
        args.output_dir or _default_output(args.robustness_dir),
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
                "era_count": audit.era_count,
                "eras": [
                    item.era for item in audit.era_definitions
                ],
                "horizon_count": audit.horizon_count,
                "horizons": list(audit.horizons),
                "era_count_row_count": len(audit.era_count_rows),
                "era_outcome_row_count": len(audit.era_outcome_rows),
                "consistency_row_count": len(audit.consistency_rows),
                "leave_one_era_out_row_count": len(
                    audit.leave_one_era_out_rows
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
