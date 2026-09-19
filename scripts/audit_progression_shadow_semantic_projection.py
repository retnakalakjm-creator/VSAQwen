from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.progression_directional_outcomes import (  # noqa: E402
    load_progression_directionality_artifacts,
)
from audit.progression_shadow_semantic_projection import (  # noqa: E402
    build_progression_shadow_semantic_audit,
    write_progression_shadow_semantic_audit,
)
from vsa_standard_audit_basket import (  # noqa: E402
    STANDARD_VSA_AUDIT_BASKET_NAME,
    get_vsa_audit_basket,
    list_vsa_audit_basket_names,
)


def _default_k14_dir(basket_name: str) -> Path:
    return (
        Path("reports/daily-behavior-sequences/progression-directionality")
        / basket_name
    )


def _default_output(basket_name: str) -> Path:
    return (
        Path("reports/daily-behavior-sequences/progression-shadow-semantic")
        / basket_name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Project validated progression events into read-only "
            "shadow semantic roles."
        )
    )
    parser.add_argument(
        "--basket",
        choices=list_vsa_audit_basket_names(),
        default=STANDARD_VSA_AUDIT_BASKET_NAME,
    )
    parser.add_argument("--k14-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    basket = get_vsa_audit_basket(args.basket)
    symbols = tuple(basket.symbols)
    input_dir = args.k14_dir or _default_k14_dir(basket.name)
    artifact = load_progression_directionality_artifacts(
        input_dir=input_dir,
        basket_name=basket.name,
        requested_symbols=symbols,
    )

    audit = build_progression_shadow_semantic_audit(
        basket_name=basket.name,
        requested_symbols=symbols,
        rows_by_symbol=artifact.rows_by_symbol,
        expected_event_counts=artifact.event_counts_by_symbol,
    )
    output_dir = args.output_dir or _default_output(basket.name)
    paths = write_progression_shadow_semantic_audit(
        audit,
        output_dir,
    )

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "basket_name": audit.basket_name,
                "requested_symbol_count": audit.requested_symbol_count,
                "event_count": audit.event_count,
                "semantic_role_counts": audit.semantic_role_counts,
                "transition_warning_direction_counts": (
                    audit.transition_warning_direction_counts
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
