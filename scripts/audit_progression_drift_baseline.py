from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.progression_drift_baseline import (  # noqa: E402
    ProgressionDriftBaselineFailure,
    build_progression_drift_baseline_audit,
    build_symbol_progression_drift_baseline,
    load_frozen_progression_outcomes,
    write_progression_drift_baseline_audit,
)
from data import download_data  # noqa: E402
from vsa_standard_audit_basket import (  # noqa: E402
    STANDARD_VSA_AUDIT_BASKET_NAME,
    get_vsa_audit_basket,
    list_vsa_audit_basket_names,
)


def _default_k15_dir(basket_name: str) -> Path:
    return (
        Path("reports/daily-behavior-sequences/progression-outcomes")
        / basket_name
    )


def _default_output(basket_name: str) -> Path:
    return (
        Path("reports/daily-behavior-sequences/progression-drift-baseline")
        / basket_name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare frozen progression-event outcomes with same-symbol "
            "non-event weekly drift controls."
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
        help="Point-in-time cutoff used by the frozen K15 run.",
    )
    parser.add_argument(
        "--k15-dir",
        type=Path,
        default=None,
        help="Validated K15 artifact directory.",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh market-data caches explicitly before baseline scoring.",
    )
    args = parser.parse_args(argv)

    basket = get_vsa_audit_basket(args.basket)
    symbols = tuple(basket.symbols)
    k15_dir = args.k15_dir or _default_k15_dir(basket.name)
    artifact = load_frozen_progression_outcomes(
        input_dir=k15_dir,
        expected_basket_name=basket.name,
    )
    if artifact.requested_symbol_count != len(symbols):
        raise ValueError(
            "K15 requested-symbol count does not match basket size"
        )

    baselines = []
    lifts = []
    failures = []
    for symbol in symbols:
        try:
            symbol_observations = artifact.observations_by_symbol.get(
                symbol,
                (),
            )
            if not symbol_observations:
                baselines.append(())
                lifts.append(())
                continue

            daily = download_data(
                symbol,
                refresh=args.refresh,
                cache_max_age=(0 if args.refresh else 10**12),
            )
            symbol_baselines, symbol_lifts = (
                build_symbol_progression_drift_baseline(
                    symbol=symbol,
                    daily=daily,
                    observations=symbol_observations,
                    now=args.now,
                )
            )
            baselines.append(symbol_baselines)
            lifts.append(symbol_lifts)
        except Exception as exc:
            failures.append(
                ProgressionDriftBaselineFailure(
                    symbol=symbol,
                    exception_type=type(exc).__name__,
                    reason=str(exc),
                )
            )

    audit = build_progression_drift_baseline_audit(
        artifact=artifact,
        requested_symbols=symbols,
        symbol_baselines=tuple(baselines),
        symbol_lifts=tuple(lifts),
        failures=tuple(failures),
    )
    output_dir = args.output_dir or _default_output(basket.name)
    paths = write_progression_drift_baseline_audit(
        audit,
        output_dir,
    )

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "basket_name": audit.basket_name,
                "requested_symbol_count": audit.requested_symbol_count,
                "successful_symbol_count": audit.successful_symbol_count,
                "failed_symbol_count": audit.failed_symbol_count,
                "source_event_count": audit.source_event_count,
                "source_observation_count": audit.source_observation_count,
                "event_count": audit.event_count,
                "observation_count": audit.observation_count,
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
