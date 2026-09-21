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
from audit.qualification_spacing_impact import (  # noqa: E402
    build_qualification_spacing_impact_audit,
    write_qualification_spacing_impact_audit,
)
from vsa_standard_audit_basket import (  # noqa: E402
    STANDARD_VSA_AUDIT_BASKET_NAME,
    get_vsa_audit_basket,
    list_vsa_audit_basket_names,
)


def _default_input(basket_name: str) -> Path:
    return (
        Path("reports/daily-behavior-sequences/progression-directionality")
        / basket_name
    )


def _default_output(basket_name: str) -> Path:
    return (
        Path("reports/daily-behavior-sequences/qualification-spacing")
        / basket_name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare current production qualification spacing selection "
            "with a strict pairwise-spacing counterfactual."
        )
    )
    parser.add_argument(
        "--basket",
        choices=list_vsa_audit_basket_names(),
        default=STANDARD_VSA_AUDIT_BASKET_NAME,
    )
    parser.add_argument(
        "--directionality-dir",
        type=Path,
        default=None,
        help="Validated K14 progression-directionality artifact directory.",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    basket = get_vsa_audit_basket(args.basket)
    input_dir = args.directionality_dir or _default_input(basket.name)
    artifact_input = load_progression_directionality_artifacts(
        input_dir=input_dir,
        basket_name=basket.name,
        requested_symbols=tuple(basket.symbols),
    )
    audit = build_qualification_spacing_impact_audit(artifact_input)
    output_dir = args.output_dir or _default_output(basket.name)
    paths = write_qualification_spacing_impact_audit(
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
                "affected_symbol_count": audit.affected_symbol_count,
                "affected_campaign_count": audit.affected_campaign_count,
                "divergence_event_count": audit.divergence_event_count,
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
