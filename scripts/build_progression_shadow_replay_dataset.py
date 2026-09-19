from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.progression_shadow_replay_dataset import (  # noqa: E402
    ProgressionShadowReplayFailure,
    build_progression_shadow_replay_dataset_audit,
    build_symbol_shadow_replay_sequences,
    load_frozen_shadow_semantic_artifact,
    write_progression_shadow_replay_dataset,
)
from data import download_data  # noqa: E402
from vsa_standard_audit_basket import (  # noqa: E402
    STANDARD_VSA_AUDIT_BASKET_NAME,
    get_vsa_audit_basket,
    list_vsa_audit_basket_names,
)


def _default_k24_dir(basket_name: str) -> Path:
    return (
        Path("reports/daily-behavior-sequences/progression-shadow-semantic")
        / basket_name
    )


def _default_output(basket_name: str) -> Path:
    return (
        Path("reports/daily-behavior-sequences/progression-shadow-replay")
        / basket_name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build replay-ready offline weekly windows from frozen K24 "
            "shadow semantic projections."
        )
    )
    parser.add_argument(
        "--basket",
        choices=list_vsa_audit_basket_names(),
        default=STANDARD_VSA_AUDIT_BASKET_NAME,
    )
    parser.add_argument("--now", required=True)
    parser.add_argument("--lookback-bars", type=int, default=4)
    parser.add_argument("--forward-bars", type=int, default=4)
    parser.add_argument("--k24-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)

    basket = get_vsa_audit_basket(args.basket)
    symbols = tuple(basket.symbols)
    input_dir = args.k24_dir or _default_k24_dir(basket.name)
    artifact = load_frozen_shadow_semantic_artifact(
        input_dir=input_dir,
        expected_basket_name=basket.name,
    )
    if artifact.requested_symbol_count != len(symbols):
        raise ValueError(
            "K24 requested-symbol count does not match basket size"
        )

    symbol_sequences = []
    failures = []
    for symbol in symbols:
        events = artifact.rows_by_symbol.get(symbol, ())
        if not events:
            symbol_sequences.append(())
            continue
        try:
            daily = download_data(
                symbol,
                refresh=args.refresh,
                cache_max_age=(0 if args.refresh else 10**12),
            )
            symbol_sequences.append(
                build_symbol_shadow_replay_sequences(
                    symbol=symbol,
                    daily=daily,
                    events=events,
                    now=args.now,
                    lookback_bars=args.lookback_bars,
                    forward_bars=args.forward_bars,
                )
            )
        except Exception as exc:
            failures.append(
                ProgressionShadowReplayFailure(
                    symbol=symbol,
                    exception_type=type(exc).__name__,
                    reason=str(exc),
                )
            )

    audit = build_progression_shadow_replay_dataset_audit(
        artifact=artifact,
        requested_symbols=symbols,
        symbol_sequences=tuple(symbol_sequences),
        lookback_bars=args.lookback_bars,
        forward_bars=args.forward_bars,
        failures=tuple(failures),
    )
    output_dir = args.output_dir or _default_output(basket.name)
    paths = write_progression_shadow_replay_dataset(audit, output_dir)

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "basket_name": audit.basket_name,
                "requested_symbol_count": audit.requested_symbol_count,
                "source_event_count": audit.source_event_count,
                "sequence_count": audit.sequence_count,
                "total_frame_count": audit.total_frame_count,
                "failed_symbol_count": len(audit.failures),
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
