from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_event_inventory import (  # noqa: E402
    DailyEventAuditFailure,
    build_daily_event_inventory_audit,
    write_daily_event_inventory_audit,
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


def _default_output(basket_name: str) -> Path:
    return Path("reports/daily-events/inventory") / basket_name


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
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)

    symbols = _symbols_from_args(
        basket_name=args.basket,
        explicit_symbols=args.symbols,
    )
    if not symbols:
        raise ValueError("at least one symbol is required")

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
    )
    output_dir = args.output_dir or _default_output(args.basket)
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
