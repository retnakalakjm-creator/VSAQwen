from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.progression_role_horizon_trajectory import (  # noqa: E402
    build_progression_role_trajectory_audit,
    load_frozen_role_consensus_artifacts,
    write_progression_role_trajectory_audit,
)
from vsa_standard_audit_basket import (  # noqa: E402
    STANDARD_VSA_AUDIT_BASKET_NAME,
    get_vsa_audit_basket,
    list_vsa_audit_basket_names,
)


def _default_k21_dir(basket_name: str) -> Path:
    return (
        Path("reports/daily-behavior-sequences/progression-role-consensus")
        / basket_name
    )


def _default_output(basket_name: str) -> Path:
    return (
        Path("reports/daily-behavior-sequences/progression-role-trajectory")
        / basket_name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Collapse K21 event-horizon consensus rows into one "
            "horizon-role trajectory per progression event."
        )
    )
    parser.add_argument(
        "--basket",
        choices=list_vsa_audit_basket_names(),
        default=STANDARD_VSA_AUDIT_BASKET_NAME,
    )
    parser.add_argument("--k21-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    basket = get_vsa_audit_basket(args.basket)
    input_dir = args.k21_dir or _default_k21_dir(basket.name)
    artifact = load_frozen_role_consensus_artifacts(
        input_dir=input_dir,
        expected_basket_name=basket.name,
    )
    if artifact.requested_symbol_count != len(basket.symbols):
        raise ValueError(
            "K21 requested-symbol count does not match basket size"
        )

    audit = build_progression_role_trajectory_audit(artifact)
    output_dir = args.output_dir or _default_output(basket.name)
    paths = write_progression_role_trajectory_audit(
        audit,
        output_dir,
    )

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "basket_name": audit.basket_name,
                "source_event_count": audit.source_event_count,
                "source_observation_count": audit.source_observation_count,
                "source_consensus_row_count": (
                    audit.source_consensus_row_count
                ),
                "trajectory_row_count": audit.trajectory_row_count,
                "expected_horizons": list(audit.expected_horizons),
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
