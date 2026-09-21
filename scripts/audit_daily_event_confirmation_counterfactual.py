from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_event_confirmation_counterfactual import (  # noqa: E402
    build_confirmation_counterfactual_audit,
    load_confirmation_sources,
    write_confirmation_counterfactual_audit,
)
from audit.daily_event_confirmation_runner import (  # noqa: E402
    run_frozen_confirmation_replay,
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


def _default_cofiring_dir(l1_dir: Path) -> Path:
    return Path("reports/daily-events/cofiring") / l1_dir.name


def _default_output(l1_dir: Path) -> Path:
    return (
        Path("reports/daily-events/confirmation-counterfactual")
        / l1_dir.name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Replay canonical frozen daily inputs and measure confirmation "
            "counterfactuals without changing production detectors."
        )
    )
    parser.add_argument(
        "--basket",
        choices=list_vsa_audit_basket_names(),
        default=STANDARD_VSA_AUDIT_BASKET_NAME,
    )
    parser.add_argument("--symbols", nargs="*", default=None)
    parser.add_argument("--now", required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--cofiring-dir", type=Path, default=None)
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
    args = parser.parse_args(argv)

    selected_symbols = _symbols(args.basket, args.symbols)
    if not selected_symbols:
        raise ValueError("at least one symbol is required")

    l2_dir = args.cofiring_dir or _default_cofiring_dir(args.input_dir)
    sources = load_confirmation_sources(
        l1_dir=args.input_dir,
        l2_dir=l2_dir,
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

    replay = run_frozen_confirmation_replay(
        selected_symbols,
        bundle=sources.bundle,
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
    audit = build_confirmation_counterfactual_audit(
        source_audit_id=sources.lineage.l1_audit_id,
        source_lineage=sources.lineage,
        requested_symbols=selected_symbols,
        baseline=sources.baseline,
        observations=replay.observations,
        failures=replay.failures,
        snapshot_worker_count=replay.worker_count,
    )
    paths = write_confirmation_counterfactual_audit(
        audit,
        args.output_dir or _default_output(args.input_dir),
    )

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "source_audit_id": audit.source_audit_id,
                "requested_symbol_count": audit.requested_symbol_count,
                "succeeded_symbol_count": audit.succeeded_symbol_count,
                "failed_symbol_count": audit.failed_symbol_count,
                "confirmation_sensitive_code_count": (
                    audit.confirmation_sensitive_code_count
                ),
                "physical_observation_count": (
                    audit.physical_observation_count
                ),
                "baseline_event_count": audit.baseline_event_count,
                "captured_event_count": audit.captured_event_count,
                "duplicate_observation_count": (
                    audit.duplicate_observation_count
                ),
                "identity_mismatch_count": audit.identity_mismatch_count,
                "bar_index_mismatch_count": (
                    audit.bar_index_mismatch_count
                ),
                "snapshot_worker_count": audit.snapshot_worker_count,
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
        or audit.identity_mismatch_count
        or audit.bar_index_mismatch_count
    ):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
