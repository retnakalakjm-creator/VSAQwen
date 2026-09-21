from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_event_no_supply_confirmation_strata import (  # noqa: E402
    build_no_supply_confirmation_strata_audit,
    load_no_supply_confirmation_sources,
    write_no_supply_confirmation_strata_audit,
)
from audit.daily_event_no_supply_forward_outcomes import (  # noqa: E402
    DEFAULT_FORWARD_HORIZONS,
)


def _default_output(matched_dir: Path) -> Path:
    return (
        Path("reports/daily-events/no-supply-confirmation-strata")
        / matched_dir.name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Stratify canonical matched NO_SUPPLY outcomes by meaningful "
            "confirmation pattern and projected gate."
        )
    )
    parser.add_argument("--matched-dir", type=Path, required=True)
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument(
        "--horizons",
        nargs="+",
        type=int,
        default=list(DEFAULT_FORWARD_HORIZONS),
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    sources = load_no_supply_confirmation_sources(
        matched_dir=args.matched_dir,
        replay_dir=args.replay_dir,
    )
    audit = build_no_supply_confirmation_strata_audit(
        sources=sources,
        horizons=args.horizons,
    )
    paths = write_no_supply_confirmation_strata_audit(
        audit,
        sources.targets,
        args.output_dir or _default_output(args.matched_dir),
    )

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "requested_symbol_count": audit.requested_symbol_count,
                "source_target_count": audit.source_target_count,
                "current_source_target_count": (
                    audit.current_source_target_count
                ),
                "alternate_source_target_count": (
                    audit.alternate_source_target_count
                ),
                "weak_spread_target_count": (
                    audit.weak_spread_target_count
                ),
                "meaningful_confirmation_target_count": (
                    audit.meaningful_confirmation_target_count
                ),
                "horizon_count": audit.horizon_count,
                "horizons": list(audit.horizons),
                "stratum_count_row_count": len(
                    audit.stratum_count_rows
                ),
                "gate_count_row_count": len(audit.gate_count_rows),
                "stratum_outcome_row_count": len(
                    audit.stratum_outcome_rows
                ),
                "gate_outcome_row_count": len(
                    audit.gate_outcome_rows
                ),
                "stratum_symbol_row_count": len(
                    audit.stratum_symbol_rows
                ),
                "gate_symbol_row_count": len(
                    audit.gate_symbol_rows
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
