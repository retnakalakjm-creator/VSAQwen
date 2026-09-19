from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.progression_directional_outcomes import (  # noqa: E402
    DEFAULT_PROGRESSION_OUTCOME_HORIZONS,
    build_progression_directional_outcome_audit,
    build_symbol_progression_directional_outcomes,
    load_progression_directionality_artifacts,
    write_progression_directional_outcome_audit,
)
from audit.progression_directionality_semantics import (  # noqa: E402
    ProgressionDirectionalityFailure,
)
from data import download_data  # noqa: E402
from vsa_standard_audit_basket import (  # noqa: E402
    STANDARD_VSA_AUDIT_BASKET_NAME,
    get_vsa_audit_basket,
    list_vsa_audit_basket_names,
)


def _parse_horizons(value: str) -> tuple[int, ...]:
    try:
        result = tuple(
            sorted(
                {
                    int(item.strip())
                    for item in value.split(",")
                    if item.strip()
                }
            )
        )
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "horizons must be comma-separated integers"
        ) from exc
    if not result or any(item <= 0 for item in result):
        raise argparse.ArgumentTypeError(
            "horizons must be positive integers"
        )
    return result


def _default_output(basket_name: str) -> Path:
    return (
        Path("reports/daily-behavior-sequences/progression-outcomes")
        / basket_name
    )


def _default_directionality_dir(basket_name: str) -> Path:
    return (
        Path("reports/daily-behavior-sequences/progression-directionality")
        / basket_name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit causal future weekly outcomes of production structural "
            "progression direction labels."
        )
    )
    parser.add_argument(
        "--basket",
        choices=list_vsa_audit_basket_names(),
        default=STANDARD_VSA_AUDIT_BASKET_NAME,
    )
    parser.add_argument(
        "--now",
        required=True,
        help="Point-in-time cutoff, preferably timezone-aware.",
    )
    parser.add_argument(
        "--horizons",
        type=_parse_horizons,
        default=DEFAULT_PROGRESSION_OUTCOME_HORIZONS,
        help="Comma-separated weekly horizons. Default: 1,3,5,10,15.",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=None,
        help="Optional prefix limit for staged local validation.",
    )
    parser.add_argument(
        "--directionality-dir",
        type=Path,
        default=None,
        help=(
            "Validated K14 artifact directory. Defaults to "
            "reports/daily-behavior-sequences/progression-directionality/"
            "<BASKET>."
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh each read-only market-data cache first.",
    )
    args = parser.parse_args(argv)

    basket = get_vsa_audit_basket(args.basket)
    symbols = basket.symbols
    if args.max_symbols is not None:
        if args.max_symbols < 1:
            parser.error("--max-symbols must be positive")
        symbols = symbols[: args.max_symbols]

    directionality_dir = (
        args.directionality_dir
        or _default_directionality_dir(basket.name)
    )
    artifact_input = load_progression_directionality_artifacts(
        input_dir=directionality_dir,
        basket_name=basket.name,
        requested_symbols=tuple(symbols),
    )

    observations = []
    event_counts = []
    failures = []
    for symbol in symbols:
        try:
            daily = download_data(
                symbol,
                refresh=args.refresh,
                cache_max_age=(
                    0
                    if args.refresh
                    else 10**12
                ),
            )
            rows = artifact_input.rows_by_symbol[symbol]
            symbol_observations, event_count = (
                build_symbol_progression_directional_outcomes(
                    symbol=symbol,
                    daily=daily,
                    rows=rows,
                    now=args.now,
                    horizons_weeks=args.horizons,
                )
            )
            observations.append(symbol_observations)
            event_counts.append(event_count)
        except Exception as exc:
            failures.append(
                ProgressionDirectionalityFailure(
                    symbol=symbol,
                    exception_type=type(exc).__name__,
                    reason=str(exc),
                )
            )

    audit = build_progression_directional_outcome_audit(
        basket_name=basket.name,
        requested_symbols=tuple(symbols),
        symbol_observations=tuple(observations),
        event_counts=tuple(event_counts),
        failures=tuple(failures),
        horizons_weeks=args.horizons,
    )
    output_dir = args.output_dir or _default_output(basket.name)
    paths = write_progression_directional_outcome_audit(
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
        "observation_count": audit.observation_count,
        "horizons_weeks": list(audit.horizons_weeks),
        "directionality_input_dir": str(directionality_dir),
        "output_files": paths.as_dict(),
        "is_actionable": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
