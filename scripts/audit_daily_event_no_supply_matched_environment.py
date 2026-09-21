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
)
from audit.daily_event_no_supply_matched_environment import (  # noqa: E402
    DEFAULT_MAX_MATCH_DISTANCE_SESSIONS,
    build_no_supply_matched_environment_audit,
    load_no_supply_matched_sources,
    subset_no_supply_matched_sources,
    write_no_supply_matched_environment_audit,
)
from audit.daily_event_no_supply_matched_runner import (  # noqa: E402
    build_matched_checkpoint_signature,
    run_frozen_matched_control_discovery,
)
from audit.offline_daily_evidence import (  # noqa: E402
    DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
)
from vsa_standard_audit_basket import (  # noqa: E402
    STANDARD_VSA_AUDIT_BASKET_NAME,
    get_vsa_audit_basket,
    list_vsa_audit_basket_names,
)


def _default_output(forward_dir: Path) -> Path:
    return (
        Path("reports/daily-events/no-supply-matched-environment")
        / forward_dir.name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Match NO_SUPPLY common-signature targets to nearby "
            "same-symbol, same-environment bearish control bars."
        )
    )
    parser.add_argument(
        "--basket",
        choices=list_vsa_audit_basket_names(),
        default=STANDARD_VSA_AUDIT_BASKET_NAME,
    )
    parser.add_argument("--symbols", nargs="*", default=None)
    parser.add_argument("--forward-dir", type=Path, required=True)
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument(
        "--input-snapshot-dir",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--max-match-distance",
        type=int,
        default=DEFAULT_MAX_MATCH_DISTANCE_SESSIONS,
    )
    parser.add_argument(
        "--min-target-index",
        type=int,
        default=DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    )
    parser.add_argument(
        "--horizons",
        nargs="+",
        type=int,
        default=list(DEFAULT_FORWARD_HORIZONS),
    )
    parser.add_argument(
        "--price-discontinuity-ratio",
        type=float,
        default=DEFAULT_FORWARD_PRICE_DISCONTINUITY_RATIO,
    )
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--checkpoint-dir", type=Path, default=None)
    parser.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
    )
    parser.set_defaults(resume=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    sources = load_no_supply_matched_sources(
        forward_dir=args.forward_dir,
        replay_dir=args.replay_dir,
        input_snapshot_dir=args.input_snapshot_dir,
        basket_name=args.basket,
    )
    basket_symbols = tuple(get_vsa_audit_basket(args.basket).symbols)
    selected_symbols = (
        tuple(
            str(symbol).strip().upper()
            for symbol in args.symbols
            if str(symbol).strip()
        )
        if args.symbols
        else basket_symbols
    )
    if len(selected_symbols) != len(set(selected_symbols)):
        raise ValueError("selected symbols must be unique")
    selected_sources = (
        sources
        if selected_symbols == basket_symbols
        else subset_no_supply_matched_sources(
            sources,
            selected_symbols,
        )
    )

    canonical_output = _default_output(args.forward_dir)
    output_dir = args.output_dir or (
        canonical_output
        if selected_symbols == basket_symbols
        else canonical_output / "smoke" / "-".join(selected_symbols)
    )
    checkpoint_dir = (
        args.checkpoint_dir
        if args.checkpoint_dir is not None
        else canonical_output / "checkpoints"
    )
    checkpoint_signature = build_matched_checkpoint_signature(
        source_lineage=sources.lineage,
        max_match_distance_sessions=args.max_match_distance,
        min_target_index=args.min_target_index,
    )

    replay = run_frozen_matched_control_discovery(
        selected_symbols,
        bundle=sources.bundle,
        input_snapshot_dir=args.input_snapshot_dir,
        targets=selected_sources.targets,
        common_signature_sessions=(
            selected_sources.common_signature_sessions
        ),
        max_match_distance_sessions=args.max_match_distance,
        min_target_index=args.min_target_index,
        workers=args.workers,
        checkpoint_dir=checkpoint_dir,
        checkpoint_signature=checkpoint_signature,
        resume=args.resume,
        progress_writer=lambda message: print(
            message,
            file=sys.stderr,
            flush=True,
        ),
    )
    if replay.failures:
        for failure in replay.failures:
            print(failure, file=sys.stderr)
        return 2

    audit = build_no_supply_matched_environment_audit(
        sources=selected_sources,
        controls=replay.controls,
        unmatched_targets=replay.unmatched_targets,
        symbol_match_rows=replay.symbol_rows,
        input_snapshot_dir=args.input_snapshot_dir,
        max_match_distance_sessions=args.max_match_distance,
        min_target_index=args.min_target_index,
        horizons=args.horizons,
        price_discontinuity_ratio=args.price_discontinuity_ratio,
    )
    paths = write_no_supply_matched_environment_audit(
        audit,
        output_dir,
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
                "common_signature_count": audit.common_signature_count,
                "matched_target_count": audit.matched_target_count,
                "unmatched_target_count": audit.unmatched_target_count,
                "match_rate": audit.match_rate,
                "max_match_distance_sessions": (
                    audit.max_match_distance_sessions
                ),
                "horizon_count": audit.horizon_count,
                "horizons": list(audit.horizons),
                "price_discontinuity_ratio": (
                    audit.price_discontinuity_ratio
                ),
                "pair_outcome_row_count": (
                    audit.pair_outcome_row_count
                ),
                "censoring_row_count": len(audit.censoring_rows),
                "outcome_summary_row_count": len(
                    audit.outcome_summary_rows
                ),
                "symbol_outcome_row_count": len(
                    audit.symbol_outcome_rows
                ),
                "checkpoint_dir": str(checkpoint_dir),
                "checkpoint_signature": checkpoint_signature,
                "checkpoint_reused_count": (
                    replay.checkpoint_reused_count
                ),
                "checkpoint_written_count": (
                    replay.checkpoint_written_count
                ),
                "worker_count": replay.worker_count,
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
