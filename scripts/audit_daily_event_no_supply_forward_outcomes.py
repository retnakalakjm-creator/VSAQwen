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
    DEFAULT_FORWARD_PRICE_DISCONTINUITY_RATIO,
    build_no_supply_forward_outcome_audit,
    load_no_supply_forward_outcome_sources,
    write_no_supply_forward_outcome_audit,
)
from vsa_standard_audit_basket import (  # noqa: E402
    STANDARD_VSA_AUDIT_BASKET_NAME,
    list_vsa_audit_basket_names,
)


def _default_output(replay_dir: Path) -> Path:
    return (
        Path("reports/daily-events/no-supply-forward-outcomes")
        / replay_dir.name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare forward price outcomes for canonical CURRENT vs "
            "ALTERNATE NO_SUPPLY populations from L6."
        )
    )
    parser.add_argument(
        "--basket",
        choices=list_vsa_audit_basket_names(),
        default=STANDARD_VSA_AUDIT_BASKET_NAME,
    )
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument(
        "--input-snapshot-dir",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--horizons",
        nargs="+",
        type=int,
        default=list(DEFAULT_FORWARD_HORIZONS),
        help="Completed-session forward horizons.",
    )
    parser.add_argument(
        "--price-discontinuity-ratio",
        type=float,
        default=DEFAULT_FORWARD_PRICE_DISCONTINUITY_RATIO,
        help=(
            "Flag an event/horizon window when any event-or-future "
            "OHLC value moves at least this ratio from the previous "
            "session close. Default: 0.35."
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    sources = load_no_supply_forward_outcome_sources(
        replay_dir=args.replay_dir,
        input_snapshot_dir=args.input_snapshot_dir,
        basket_name=args.basket,
    )
    audit = build_no_supply_forward_outcome_audit(
        sources=sources,
        input_snapshot_dir=args.input_snapshot_dir,
        horizons=args.horizons,
        price_discontinuity_ratio=args.price_discontinuity_ratio,
    )
    paths = write_no_supply_forward_outcome_audit(
        audit,
        args.output_dir or _default_output(args.replay_dir),
    )

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "requested_symbol_count": audit.requested_symbol_count,
                "source_event_count": audit.source_event_count,
                "current_source_event_count": (
                    audit.current_source_event_count
                ),
                "alternate_source_event_count": (
                    audit.alternate_source_event_count
                ),
                "horizon_count": audit.horizon_count,
                "horizons": list(audit.horizons),
                "price_discontinuity_ratio": (
                    audit.price_discontinuity_ratio
                ),
                "outcome_row_count": audit.outcome_row_count,
                "censored_event_horizon_count": (
                    audit.censored_event_horizon_count
                ),
                "cohort_summary_row_count": len(
                    audit.cohort_summary_rows
                ),
                "symbol_summary_row_count": len(
                    audit.symbol_summary_rows
                ),
                "comparison_row_count": len(audit.comparison_rows),
                "censoring_row_count": len(audit.censoring_rows),
                "data_quality_row_count": len(
                    audit.data_quality_rows
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
