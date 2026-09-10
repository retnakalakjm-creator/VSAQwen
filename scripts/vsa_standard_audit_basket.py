from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CORE_MODULE_PATH = ROOT / "vsa_standard_audit_basket.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_standard_basket_helpers() -> tuple[Callable[..., Any], Callable[..., str], Callable[[], Any]]:
    """Load the root helper without importing this script by the same name."""

    spec = importlib.util.spec_from_file_location(
        "_vsa_standard_audit_basket_core",
        CORE_MODULE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load standard basket helper from {CORE_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return (
        module.build_standard_basket_commands,
        module.build_vsa_audit_url,
        module.get_standard_vsa_audit_basket,
    )


(
    build_standard_basket_commands,
    build_vsa_audit_url,
    get_standard_vsa_audit_basket,
) = _load_standard_basket_helpers()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print the standard Milestone 6 VSA audit basket and local commands."
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Local backend base URL. Default: http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--start-week",
        default=None,
        help="Override the basket default start week.",
    )
    parser.add_argument(
        "--horizon-weeks",
        type=int,
        default=None,
        help="Override the basket default horizon weeks.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of PowerShell commands.",
    )
    args = parser.parse_args(argv)

    try:
        basket = get_standard_vsa_audit_basket()
        start_week = args.start_week or basket.start_week
        horizon_weeks = args.horizon_weeks or basket.horizon_weeks
        url = build_vsa_audit_url(
            base_url=args.base_url,
            start_week=start_week,
            horizon_weeks=horizon_weeks,
            max_symbols=basket.max_symbols,
        )
        commands = build_standard_basket_commands()
        if args.base_url != "http://127.0.0.1:8000" or start_week != basket.start_week or horizon_weeks != basket.horizon_weeks:
            commands = {
                **commands,
                "audit_url": url,
                "save_audit": f'curl.exe "{url}" -o standard_basket_audit.json',
            }
        payload: dict[str, Any] = {
            **basket.to_dict(),
            "audit_url": url,
            "commands": commands,
        }
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print("Standard Milestone 6 VSA audit basket")
    print(f"Name: {payload['name']}")
    print(f"Symbols ({payload['symbol_count']}): {','.join(payload['symbols'])}")
    print(f"Start week: {payload['start_week']}")
    print(f"Horizon weeks: {payload['horizon_weeks']}")
    print()
    print("Run backend separately, then run:")
    print(payload["commands"]["save_audit"])
    print(payload["commands"]["candidate_events"])
    print(payload["commands"]["batch_review"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
