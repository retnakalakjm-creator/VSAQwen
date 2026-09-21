from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_event_inventory import (  # noqa: E402
    DailyEventAuditFailure,
    DailyEventInventoryInputProvenance,
    build_daily_event_inventory_audit,
    write_daily_event_inventory_audit,
)
from audit.daily_event_inventory_runner import (  # noqa: E402
    run_frozen_snapshot_replay,
)
from audit.daily_input_reproducibility import (  # noqa: E402
    daily_audit_input_manifest_sha256,
    load_daily_audit_input_bundle,
)
from audit.offline_daily_evidence import (  # noqa: E402
    DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    produce_offline_daily_evidence,
)
from data import download_data  # noqa: E402
from vsa_standard_audit_basket import (  # noqa: E402
    STANDARD_VSA_AUDIT_BASKET_NAME,
    get_vsa_audit_basket,
    list_vsa_audit_basket_names,
)


def _default_output(
    basket_name: str,
    *,
    snapshot_cutoff: str | None = None,
) -> Path:
    root = Path("reports/daily-events/inventory")
    if snapshot_cutoff is None:
        return root / basket_name
    cutoff_session = str(snapshot_cutoff).split("T", 1)[0]
    return root / f"{basket_name}_frozen_{cutoff_session}"


def _symbols_from_args(
    *,
    basket_name: str,
    explicit_symbols: list[str] | None,
) -> tuple[str, ...]:
    if explicit_symbols:
        return tuple(
            str(symbol).strip().upper()
            for symbol in explicit_symbols
            if str(symbol).strip()
        )
    return tuple(get_vsa_audit_basket(basket_name).symbols)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Inventory existing daily Evidence events and measure point-in-time "
            "emissions using the existing K5 prefix replay."
        )
    )
    parser.add_argument(
        "--basket",
        choices=list_vsa_audit_basket_names(),
        default=STANDARD_VSA_AUDIT_BASKET_NAME,
    )
    parser.add_argument("--symbols", nargs="*", default=None)
    parser.add_argument("--now", required=True)
    parser.add_argument(
        "--min-target-index",
        type=int,
        default=DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--input-snapshot-dir", type=Path, default=None)
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=(
            "Frozen snapshot replay worker processes. "
            "Defaults to up to 4, leaving one CPU free."
        ),
    )
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)

    symbols = _symbols_from_args(
        basket_name=args.basket,
        explicit_symbols=args.symbols,
    )
    if not symbols:
        raise ValueError("at least one symbol is required")
    if args.input_snapshot_dir is not None and args.refresh:
        raise ValueError(
            "--refresh cannot be used with --input-snapshot-dir"
        )
    if args.input_snapshot_dir is None and args.workers is not None:
        raise ValueError(
            "--workers is only supported with --input-snapshot-dir"
        )

    snapshot_bundle = None
    if args.input_snapshot_dir is not None:
        snapshot_bundle = load_daily_audit_input_bundle(
            args.input_snapshot_dir
        )
        if snapshot_bundle.basket_name != args.basket:
            raise ValueError(
                "daily audit input basket does not match requested basket"
            )
        snapshot_symbols = tuple(
            item.symbol for item in snapshot_bundle.fingerprints
        )
        missing_symbols = sorted(set(symbols) - set(snapshot_symbols))
        if missing_symbols:
            raise ValueError(
                "daily audit input bundle missing requested symbols: "
                f"{missing_symbols}"
            )
        if args.symbols is None and snapshot_symbols != symbols:
            raise ValueError(
                "full-basket snapshot symbol order does not match basket"
            )

        input_provenance = DailyEventInventoryInputProvenance(
            source="FROZEN_DAILY_INPUT_SNAPSHOT",
            snapshot_audit_id=snapshot_bundle.audit_id,
            snapshot_manifest_sha256=(
                daily_audit_input_manifest_sha256(
                    args.input_snapshot_dir
                )
            ),
            snapshot_basket_name=snapshot_bundle.basket_name,
            snapshot_period=snapshot_bundle.period,
            snapshot_cutoff=snapshot_bundle.cutoff,
        )
    else:
        input_provenance = DailyEventInventoryInputProvenance(
            source="PRODUCTION_DATA_LOADER"
        )

    snapshot_worker_count = None
    if args.input_snapshot_dir is not None:
        replay = run_frozen_snapshot_replay(
            symbols,
            bundle=snapshot_bundle,
            input_snapshot_dir=args.input_snapshot_dir,
            now=args.now,
            min_target_index=args.min_target_index,
            workers=args.workers,
            progress_writer=lambda message: print(
                message,
                file=sys.stderr,
                flush=True,
            ),
        )
        archives = list(replay.archives)
        failures = list(replay.failures)
        snapshot_worker_count = replay.worker_count
    else:
        archives = []
        failures = []
        for symbol in symbols:
            try:
                daily = download_data(
                    symbol,
                    refresh=args.refresh,
                    cache_max_age=(0 if args.refresh else 10**12),
                )
                archives.append(
                    produce_offline_daily_evidence(
                        symbol=symbol,
                        daily=daily,
                        now=args.now,
                        min_target_index=args.min_target_index,
                    )
                )
            except Exception as exc:
                failures.append(
                    DailyEventAuditFailure(
                        symbol=symbol,
                        exception_type=type(exc).__name__,
                        reason=str(exc),
                    )
                )

    audit = build_daily_event_inventory_audit(
        requested_symbols=symbols,
        archives=tuple(archives),
        failures=tuple(failures),
        input_provenance=input_provenance,
    )
    output_dir = args.output_dir or _default_output(
        args.basket,
        snapshot_cutoff=(
            None
            if snapshot_bundle is None
            else snapshot_bundle.cutoff
        ),
    )
    paths = write_daily_event_inventory_audit(audit, output_dir)

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "requested_symbol_count": audit.requested_symbol_count,
                "succeeded_symbol_count": audit.succeeded_symbol_count,
                "failed_symbol_count": audit.failed_symbol_count,
                "evaluated_bar_count": audit.evaluated_bar_count,
                "defined_code_count": audit.defined_code_count,
                "profile_registered_code_count": (
                    audit.profile_registered_code_count
                ),
                "legacy_registry_code_count": audit.legacy_registry_code_count,
                "active_collector_code_count": audit.active_collector_code_count,
                "behavior_mapped_code_count": audit.behavior_mapped_code_count,
                "emitted_code_count": audit.emitted_code_count,
                "evidence_emission_count": audit.evidence_emission_count,
                "event_bar_count": audit.event_bar_count,
                "duplicate_group_count": audit.duplicate_group_count,
                "duplicate_extra_emission_count": (
                    audit.duplicate_extra_emission_count
                ),
                "active_not_observed_code_count": (
                    audit.active_not_observed_code_count
                ),
                "behavior_mapped_inactive_code_count": (
                    audit.behavior_mapped_inactive_code_count
                ),
                "behavior_direction_mismatch_count": (
                    audit.behavior_direction_mismatch_count
                ),
                "input_provenance": (
                    None
                    if audit.input_provenance is None
                    else asdict(audit.input_provenance)
                ),
                "snapshot_worker_count": snapshot_worker_count,
                "output_files": paths.as_dict(),
                "is_actionable": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
