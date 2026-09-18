from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.progression_directionality_semantics import (  # noqa: E402
    ProgressionDirectionalityFailure,
    summarize_progression_directionality,
    write_progression_directionality_audit,
)
from audit.weekly_structural_progression_audit import (  # noqa: E402
    build_weekly_structural_progression_audit,
)
from data import download_data  # noqa: E402
from vsa_standard_audit_basket import (  # noqa: E402
    STANDARD_VSA_AUDIT_BASKET_NAME,
    get_vsa_audit_basket,
    list_vsa_audit_basket_names,
)


def _default_output(basket_name: str) -> Path:
    return (
        Path("reports/daily-behavior-sequences/progression-directionality")
        / basket_name
    )


def main(argv: list[str] | None = None) -> int:
    basket_names = list_vsa_audit_basket_names()
    parser = argparse.ArgumentParser(
        description=(
            "Audit whether production progression evidence direction agrees "
            "with same-bar trend and structural-pattern context."
        )
    )
    parser.add_argument(
        "--basket",
        choices=basket_names,
        default=STANDARD_VSA_AUDIT_BASKET_NAME,
    )
    parser.add_argument(
        "--now",
        required=True,
        help="Point-in-time cutoff, preferably timezone-aware.",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=None,
        help="Optional prefix limit for staged local validation.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh each symbol's configured read-only market-data cache.",
    )
    args = parser.parse_args(argv)

    basket = get_vsa_audit_basket(args.basket)
    symbols = basket.symbols
    if args.max_symbols is not None:
        if args.max_symbols < 1:
            parser.error("--max-symbols must be positive")
        symbols = symbols[: args.max_symbols]

    audits = []
    failures = []
    for symbol in symbols:
        try:
            daily = download_data(symbol, refresh=args.refresh)
            audits.append(
                build_weekly_structural_progression_audit(
                    symbol=symbol,
                    daily=daily,
                    now=args.now,
                )
            )
        except Exception as exc:
            failures.append(
                ProgressionDirectionalityFailure(
                    symbol=symbol,
                    exception_type=type(exc).__name__,
                    reason=str(exc),
                )
            )

    audit = summarize_progression_directionality(
        basket_name=basket.name,
        requested_symbols=tuple(symbols),
        audits=tuple(audits),
        failures=tuple(failures),
    )
    output_dir = args.output_dir or _default_output(basket.name)
    paths = write_progression_directionality_audit(
        audit,
        output_dir,
    )

    payload = {
        "audit_id": audit.audit_id,
        "basket_name": audit.basket_name,
        "requested_symbol_count": audit.requested_symbol_count,
        "successful_symbol_count": audit.successful_symbol_count,
        "failed_symbol_count": audit.failed_symbol_count,
        "event_count": audit.event_count,
        "event_direction_counts": audit.event_direction_counts,
        "trend_alignment_counts": audit.trend_alignment_counts,
        "structural_pattern_alignment_counts": (
            audit.structural_pattern_alignment_counts
        ),
        "output_files": paths.as_dict(),
        "is_actionable": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
