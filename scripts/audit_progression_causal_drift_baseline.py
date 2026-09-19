from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.progression_causal_drift_baseline import (  # noqa: E402
    DEFAULT_CONTROL_WINDOWS,
    ProgressionCausalDriftFailure,
    build_progression_causal_drift_audit,
    build_symbol_progression_causal_drift,
    write_progression_causal_drift_audit,
)
from audit.progression_drift_baseline import (  # noqa: E402
    load_frozen_progression_outcomes,
)
from data import download_data  # noqa: E402
from vsa_standard_audit_basket import (  # noqa: E402
    STANDARD_VSA_AUDIT_BASKET_NAME,
    get_vsa_audit_basket,
    list_vsa_audit_basket_names,
)


def _parse_windows(value: str) -> tuple[int, ...]:
    try:
        windows = tuple(
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
            "control windows must be comma-separated integers"
        ) from exc
    if not windows or any(item <= 0 for item in windows):
        raise argparse.ArgumentTypeError(
            "control windows must be positive integers"
        )
    return windows


def _default_k15_dir(basket_name: str) -> Path:
    return (
        Path("reports/daily-behavior-sequences/progression-outcomes")
        / basket_name
    )


def _default_output(basket_name: str) -> Path:
    return (
        Path("reports/daily-behavior-sequences/progression-causal-drift")
        / basket_name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare progression outcomes with causal pre-event "
            "same-symbol drift controls."
        )
    )
    parser.add_argument(
        "--basket",
        choices=list_vsa_audit_basket_names(),
        default=STANDARD_VSA_AUDIT_BASKET_NAME,
    )
    parser.add_argument("--now", required=True)
    parser.add_argument(
        "--control-windows",
        type=_parse_windows,
        default=DEFAULT_CONTROL_WINDOWS,
        help="Most recent eligible control counts. Default: 26,52,104.",
    )
    parser.add_argument("--k15-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh market-data caches explicitly first.",
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

    symbol_rows = []
    failures = []
    for symbol in symbols:
        try:
            observations = artifact.observations_by_symbol.get(
                symbol,
                (),
            )
            if not observations:
                symbol_rows.append(())
                continue
            daily = download_data(
                symbol,
                refresh=args.refresh,
                cache_max_age=(0 if args.refresh else 10**12),
            )
            rows = build_symbol_progression_causal_drift(
                symbol=symbol,
                daily=daily,
                observations=observations,
                now=args.now,
                control_windows=args.control_windows,
            )
            symbol_rows.append(rows)
        except Exception as exc:
            failures.append(
                ProgressionCausalDriftFailure(
                    symbol=symbol,
                    exception_type=type(exc).__name__,
                    reason=str(exc),
                )
            )

    audit = build_progression_causal_drift_audit(
        artifact=artifact,
        requested_symbols=symbols,
        symbol_rows=tuple(symbol_rows),
        control_windows=args.control_windows,
        failures=tuple(failures),
    )
    output_dir = args.output_dir or _default_output(basket.name)
    paths = write_progression_causal_drift_audit(
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
                "comparison_row_count": audit.comparison_row_count,
                "control_windows": list(audit.control_windows),
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
