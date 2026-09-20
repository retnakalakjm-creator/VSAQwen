from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_input_reproducibility import (  # noqa: E402
    build_daily_audit_input_bundle,
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
        return tuple(
            str(symbol).strip().upper()
            for symbol in explicit
            if str(symbol).strip()
        )
    return tuple(get_vsa_audit_basket(basket_name).symbols)


def _default_output(basket_name: str, cutoff: str) -> Path:
    session = str(cutoff).split("T", 1)[0]
    return (
        Path("reports/daily-events/input-snapshots")
        / basket_name
        / session
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build immutable full-history daily OHLCV inputs for research "
            "audits without reading or mutating the production cache."
        )
    )
    parser.add_argument(
        "--basket",
        choices=list_vsa_audit_basket_names(),
        default=STANDARD_VSA_AUDIT_BASKET_NAME,
    )
    parser.add_argument("--symbols", nargs="*", default=None)
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    symbols = _symbols(args.basket, args.symbols)
    if not symbols:
        raise ValueError("at least one symbol is required")

    bundle, paths = build_daily_audit_input_bundle(
        symbols,
        basket_name=args.basket,
        cutoff=args.cutoff,
        output_dir=(
            args.output_dir
            or _default_output(args.basket, args.cutoff)
        ),
        overwrite=args.overwrite,
    )

    print(
        json.dumps(
            {
                "audit_id": bundle.audit_id,
                "basket_name": bundle.basket_name,
                "provider": bundle.provider,
                "period": bundle.period,
                "cutoff": bundle.cutoff,
                "symbol_count": bundle.symbol_count,
                "first_sessions": {
                    item.symbol: item.first_session
                    for item in bundle.fingerprints
                },
                "last_sessions": {
                    item.symbol: item.last_session
                    for item in bundle.fingerprints
                },
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
