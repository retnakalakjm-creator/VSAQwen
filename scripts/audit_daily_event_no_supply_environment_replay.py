from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_event_no_supply_environment_replay import (  # noqa: E402
    build_no_supply_environment_replay_audit,
    load_no_supply_environment_sources,
    write_no_supply_environment_replay_audit,
)
from audit.daily_event_no_supply_environment_runner import (  # noqa: E402
    build_no_supply_checkpoint_signature,
    run_frozen_no_supply_environment_replay,
    select_symbol_shard,
)
from audit.offline_daily_evidence import (  # noqa: E402
    DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
)
from vsa_standard_audit_basket import (  # noqa: E402
    STANDARD_VSA_AUDIT_BASKET_NAME,
    get_vsa_audit_basket,
    list_vsa_audit_basket_names,
)


def _symbols(
    basket_name: str,
    explicit: list[str] | None,
) -> tuple[str, ...]:
    if explicit:
        normalized = tuple(
            str(symbol).strip().upper()
            for symbol in explicit
            if str(symbol).strip()
        )
        if len(set(normalized)) != len(normalized):
            raise ValueError("symbols must be unique")
        return normalized
    return tuple(get_vsa_audit_basket(basket_name).symbols)


def _default_output(design_dir: Path) -> Path:
    return (
        Path("reports/daily-events/no-supply-environment-replay")
        / design_dir.name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Causally replay current vs bullish-environment NO_SUPPLY "
            "eligibility on canonical frozen daily inputs."
        )
    )
    parser.add_argument(
        "--basket",
        choices=list_vsa_audit_basket_names(),
        default=STANDARD_VSA_AUDIT_BASKET_NAME,
    )
    parser.add_argument("--symbols", nargs="*", default=None)
    parser.add_argument("--now", required=True)
    parser.add_argument("--design-dir", type=Path, required=True)
    parser.add_argument("--confirmation-dir", type=Path, required=True)
    parser.add_argument(
        "--input-snapshot-dir",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--min-target-index",
        type=int,
        default=DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=(
            "Frozen snapshot worker processes. Defaults to up to 4, "
            "leaving one CPU free."
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=None,
        help=(
            "Per-symbol checkpoint directory. Defaults to the canonical "
            "L6 report root / checkpoints."
        ),
    )
    parser.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="Ignore matching checkpoints and recompute selected symbols.",
    )
    parser.set_defaults(resume=True)
    parser.add_argument("--shard-index", type=int, default=None)
    parser.add_argument("--shard-count", type=int, default=None)
    args = parser.parse_args(argv)

    if (args.shard_index is None) != (args.shard_count is None):
        raise ValueError(
            "--shard-index and --shard-count must be supplied together"
        )

    base_symbols = _symbols(args.basket, args.symbols)
    selected_symbols = (
        select_symbol_shard(
            base_symbols,
            shard_index=args.shard_index,
            shard_count=args.shard_count,
        )
        if args.shard_index is not None
        and args.shard_count is not None
        else base_symbols
    )
    if not selected_symbols:
        raise ValueError("at least one symbol is required")

    sources = load_no_supply_environment_sources(
        design_dir=args.design_dir,
        confirmation_dir=args.confirmation_dir,
        input_snapshot_dir=args.input_snapshot_dir,
        basket_name=args.basket,
    )
    snapshot_symbols = tuple(
        item.symbol for item in sources.bundle.fingerprints
    )
    missing = sorted(set(selected_symbols) - set(snapshot_symbols))
    if missing:
        raise ValueError(
            "daily audit input bundle missing requested symbols: "
            f"{missing}"
        )
    if args.symbols is None:
        basket_symbols = tuple(
            get_vsa_audit_basket(args.basket).symbols
        )
        if snapshot_symbols != basket_symbols:
            raise ValueError(
                "full-basket snapshot symbol order does not match basket"
            )

    canonical_output_dir = _default_output(args.design_dir)
    if args.output_dir is not None:
        output_dir = args.output_dir
    elif (
        args.shard_index is not None
        and args.shard_count is not None
    ):
        output_dir = (
            canonical_output_dir
            / "shards"
            / (
                f"shard-{args.shard_index + 1:02d}"
                f"-of-{args.shard_count:02d}"
            )
        )
    else:
        output_dir = canonical_output_dir

    checkpoint_dir = (
        args.checkpoint_dir
        if args.checkpoint_dir is not None
        else canonical_output_dir / "checkpoints"
    )
    checkpoint_signature = build_no_supply_checkpoint_signature(
        source_lineage=sources.lineage,
        now=args.now,
        min_target_index=args.min_target_index,
    )

    replay = run_frozen_no_supply_environment_replay(
        selected_symbols,
        bundle=sources.bundle,
        input_snapshot_dir=args.input_snapshot_dir,
        now=args.now,
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
    audit = build_no_supply_environment_replay_audit(
        source_lineage=sources.lineage,
        requested_symbols=selected_symbols,
        baseline_current=sources.baseline_current,
        observations=replay.observations,
        symbol_rows=replay.symbol_rows,
        failures=replay.failures,
        snapshot_worker_count=replay.worker_count,
    )
    paths = write_no_supply_environment_replay_audit(
        audit,
        output_dir,
    )

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "requested_symbol_count": audit.requested_symbol_count,
                "succeeded_symbol_count": audit.succeeded_symbol_count,
                "failed_symbol_count": audit.failed_symbol_count,
                "snapshot_worker_count": audit.snapshot_worker_count,
                "checkpoint_dir": str(checkpoint_dir),
                "checkpoint_signature": checkpoint_signature,
                "checkpoint_reused_count": (
                    replay.checkpoint_reused_count
                ),
                "checkpoint_written_count": (
                    replay.checkpoint_written_count
                ),
                "progress_manifest": replay.progress_manifest,
                "resume": args.resume,
                "shard_index": args.shard_index,
                "shard_count": args.shard_count,
                "evaluated_target_count": audit.evaluated_target_count,
                "replayed_bearish_target_count": (
                    audit.replayed_bearish_target_count
                ),
                "skipped_non_bearish_target_count": (
                    audit.skipped_non_bearish_target_count
                ),
                "common_signature_count": audit.common_signature_count,
                "trend_context_replay_count": (
                    audit.common_signature_count
                ),
                "current_baseline_event_count": (
                    audit.current_baseline_event_count
                ),
                "current_replay_event_count": (
                    audit.current_replay_event_count
                ),
                "alternate_replay_event_count": (
                    audit.alternate_replay_event_count
                ),
                "current_identity_mismatch_count": (
                    audit.current_identity_mismatch_count
                ),
                "current_bar_index_mismatch_count": (
                    audit.current_bar_index_mismatch_count
                ),
                "current_alternate_overlap_count": (
                    audit.current_alternate_overlap_count
                ),
                "current_only_count": audit.current_only_count,
                "alternate_only_count": audit.alternate_only_count,
                "neither_environment_count": (
                    audit.neither_environment_count
                ),
                "source_lineage": asdict(audit.source_lineage),
                "output_files": paths.as_dict(),
                "is_actionable": False,
            },
            indent=2,
            sort_keys=True,
        )
    )

    if (
        audit.failed_symbol_count
        or audit.current_identity_mismatch_count
        or audit.current_bar_index_mismatch_count
        or audit.current_alternate_overlap_count
    ):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
