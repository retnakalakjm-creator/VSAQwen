from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_event_cofiring import (  # noqa: E402
    build_daily_event_cofiring_audit,
    load_frozen_daily_event_ledger,
    write_daily_event_cofiring_audit,
)
from vsa_standard_audit_basket import (  # noqa: E402
    STANDARD_VSA_AUDIT_BASKET_NAME,
    list_vsa_audit_basket_names,
)


def _default_input(basket_name: str) -> Path:
    return Path("reports/daily-events/inventory") / basket_name


def _default_output(
    basket_name: str,
    *,
    input_dir: Path,
) -> Path:
    source_name = input_dir.name or basket_name
    return Path("reports/daily-events/cofiring") / source_name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit frozen L1 daily-event frequency, co-firing, clustering, "
            "and detector confirmation-gate semantics."
        )
    )
    parser.add_argument(
        "--basket",
        choices=list_vsa_audit_basket_names(),
        default=STANDARD_VSA_AUDIT_BASKET_NAME,
    )
    parser.add_argument("--input-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    input_dir = args.input_dir or _default_input(args.basket)
    ledger = load_frozen_daily_event_ledger(input_dir)
    if (
        ledger.source_lineage is None
        or ledger.source_lineage.snapshot_basket_name != args.basket
    ):
        raise ValueError(
            "L1 snapshot basket does not match requested L2 basket"
        )
    audit = build_daily_event_cofiring_audit(ledger)
    output_dir = args.output_dir or _default_output(
        args.basket,
        input_dir=input_dir,
    )
    paths = write_daily_event_cofiring_audit(audit, output_dir)

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "source_audit_id": audit.source_audit_id,
                "requested_symbol_count": audit.requested_symbol_count,
                "succeeded_symbol_count": audit.succeeded_symbol_count,
                "evaluated_bar_count": audit.evaluated_bar_count,
                "raw_emission_count": audit.raw_emission_count,
                "unique_event_count": audit.unique_event_count,
                "event_bar_count": audit.event_bar_count,
                "emitted_code_count": audit.emitted_code_count,
                "pair_count": audit.pair_count,
                "identical_pair_count": audit.identical_pair_count,
                "strict_subset_pair_count": audit.strict_subset_pair_count,
                "partial_overlap_pair_count": (
                    audit.partial_overlap_pair_count
                ),
                "disjoint_pair_count": audit.disjoint_pair_count,
                "multi_code_bar_count": audit.multi_code_bar_count,
                "three_plus_code_bar_count": (
                    audit.three_plus_code_bar_count
                ),
                "max_codes_on_bar": audit.max_codes_on_bar,
                "cluster_signature_count": audit.cluster_signature_count,
                "confirmation_sensitive_detector_count": (
                    audit.confirmation_sensitive_detector_count
                ),
                "non_gating_confirmation_detector_count": (
                    audit.non_gating_confirmation_detector_count
                ),
                "source_lineage": (
                    None
                    if audit.source_lineage is None
                    else asdict(audit.source_lineage)
                ),
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
